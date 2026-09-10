//! `file` — `GET /api/file?fileid=`.
//!
//! **Why this exists.** Opening a file must not ship the file. The Bench's `/api/open`
//! answers one question with everything it knows — source, every block's SAS *and* PySpark
//! text, the lineage facts — and that payload is 1.1 MB for `big_1000.sas`, which is the
//! measured reason a 1000-block file takes 63.4 s to open
//! (`docs/plan/bronze/bronze_perf_receipts_exp42.md`). Phase 2 splits that one answer into
//! three: `file()` (this route) is the header — the block list with **no text at all** —
//! `blocks()` is one window of text at a time, and `source()` is the raw file. That split is
//! what makes phase 3's windowed UI2 possible, so the "no `sas` key" assertion in
//! `tests/file.rs` is a contract, not a detail.
//!
//! **Wire shape** (plan §6, Task 9 brief): `{stem, path, ok, errors,
//! blocks:[{id,n,kind,name,lines,warn,reads,writes}], receipts}`.
//!
//! **Where each field comes from, and where it differs from the Bench.** Every one of these
//! is a row of this store; the Bench derives several of them from its *pretty-printed
//! PySpark* instead (`raw/bench_stack/server/bench_api.py:308-321`), which this store does
//! not re-parse. The three that therefore differ are hand-traced rows in
//! `docs/plan/bronze/bronze_phase2_route_ledger.md` (causes C1–C3), not bugs:
//! - `n` — the store's own 0-based block index, the same one `blocks(from,to)` windows on.
//!   The Bench prints `int(block_id.split("_")[1])`, i.e. 1-based. Emitting the Bench's
//!   number here would make `file()` and `blocks()` disagree about which block is which.
//! - `kind` — the parser's own head functor (`data`, `proc_sql`, `libname`, `proc_print`).
//!   The Bench prints the *section header of its pretty PySpark* when it can find one, and a
//!   hand-written display map (`{"libname": "LIBNAME", "data": "DATA step", ...}`) when it
//!   cannot.
//! - `name` — the table the block writes, empty when it writes none. The Bench falls back to
//!   the head functor there, so a `PROC PRINT` is `name: "proc_print"` on that side.
//!
//! `reads`/`writes` mirror the Bench statement for statement: `writes` is the single table
//! the block makes (`blocks.name`, null when there is none), `reads` is that table's sources
//! out of `edges` — except for a block that makes nothing, where the Bench falls back to
//! every `ds(lib,tab)` the block's node/4 terms name, and so does this.
//!
//! **A second shape on a second path: `GET /api/file/<fileid>` (`file_detail`).** UI1 has
//! asked `:8000` for `/api/file/<path segments>` since long before this plan — a *different*
//! answer to a different question (`api.ts::fetchFileDetail` -> `FileDetail`: the file's
//! code, its blocks with their table occurrences, and the intra-file edges the canvas draws
//! when you expand a file box). It is not `file()` with a path parameter; it is UI1's
//! thirteenth question, and until it reads the store UI1 shows `could not load blocks for
//! <fileid>` and a 502 the moment `:8000` is stopped (plan Part G, finding G7 — M2's to
//! close). Both live here because both are "what does the store know about one file", and
//! splitting them across two modules would hide that one of them exists.
//!
//! Its `occurrences[].id` is `"<block_id>:<table>"`, the same ref `blocklinks` emits, so
//! `graph2.ts::ownerOf` can match a link's `src_ref`/`dst_ref` to the block that owns it.
//! `:8000` numbers table tokens instead (`b_1_4505bc19:t_1`); that difference is already an
//! accepted divergence in the ledger (cause B1, Task 7) and is not re-litigated here.
//! `macro_calls`, `includes` and `missing_includes` are empty lists: the engine has no macro
//! handling at all (milestone plan, Part A — 0 hits), and an empty list is the honest answer
//! rather than a field UI1 would crash without. `file_edges` is empty for the same reason
//! `edges()`'s `file` level is: this store has no `FILE_FLOW` fact (ledger cause B2).
//!
//! **Inputs → outputs.** `files`, `blocks`, `edges`, `node4`, `receipts` + a fileid → the
//! header answer, or 404 if the store has never converted that fileid.

use crate::types::AppState;
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Deserialize)]
pub struct FileParams {
    #[serde(default)]
    fileid: String,
}

pub async fn file(
    State(state): State<AppState>,
    Query(params): Query<FileParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let fileid = params.fileid.trim().to_string();
    if fileid.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "file(): fileid is required".into()));
    }
    let ise = |e: String| (StatusCode::INTERNAL_SERVER_ERROR, e);
    let conn = state.db.lock().map_err(|e| ise(e.to_string()))?;

    let ans = match inferred_duckdb::file(&conn, &fileid) {
        Ok(a) => a,
        // `inferred_duckdb::file` reads `files` by key first, so "no such fileid" surfaces
        // as DuckDB's own no-rows error. Everything else is a real failure.
        Err(e) if e.to_string().contains("no rows") || e.to_string().contains("NoRows") => {
            return Err((StatusCode::NOT_FOUND, format!("file(): no such fileid {fileid}")))
        }
        Err(e) => return Err(ise(e.to_string())),
    };
    let error: Option<String> = conn
        .query_row("SELECT error FROM files WHERE fileid = ?", duckdb::params![&fileid], |r| r.get(0))
        .map_err(|e| ise(e.to_string()))?;
    let warns = block_warns(&conn, &fileid).map_err(|e| ise(e.to_string()))?;
    let reads = block_reads(&conn, &fileid, &ans.blocks).map_err(|e| ise(e.to_string()))?;
    drop(conn);

    let blocks: Vec<Value> = ans
        .blocks
        .iter()
        .map(|b| {
            let writes: Option<&str> = if b.name.is_empty() { None } else { Some(b.name.as_str()) };
            json!({
                "id": b.block_id,
                "n": b.n,
                "kind": b.kind,
                "name": b.name,
                "lines": format!("{}-{}", b.l0, b.l1),
                "warn": warn_text(warns.get(&b.block_id).copied().unwrap_or(false)),
                "reads": reads.get(&b.block_id).cloned().unwrap_or_default(),
                "writes": writes,
            })
        })
        .collect();

    Ok(Json(json!({
        "stem": stem_of(&fileid),
        "path": fileid,
        "ok": ans.status == "ok",
        "errors": error.filter(|e| !e.is_empty()).map(|e| vec![e]).unwrap_or_default(),
        "blocks": blocks,
        "receipts": {
            "statements": ans.statements,
            "folded": ans.folded,
            "roundtrip": ans.roundtrip,
            "source_match": ans.source_match,
            "proof_state": ans.proof_state,
            "rust_us": ans.rust_us,
        },
    })))
}

/// `sales/raw/x.sas` -> `x`. The Bench's `stem` is the filename without its extension; a
/// fileid here is a path relative to the converted folder, so the last segment is taken
/// first.
pub fn stem_of(fileid: &str) -> String {
    let last = fileid.rsplit('/').next().unwrap_or(fileid);
    last.strip_suffix(".sas").unwrap_or(last).to_string()
}

/// The Bench's `warn` is the *text* of the pretty-printer's warning, or `""`. This store
/// keeps only the boolean (`blocks.warn`) — the message itself is written to stderr at
/// convert time, not to a column — so a warned block says so in one fixed sentence rather
/// than inventing a message it does not have. Recorded in the ledger, cause C4.
pub fn warn_text_pub(warn: bool) -> &'static str {
    warn_text(warn)
}

fn warn_text(warn: bool) -> &'static str {
    if warn { "block did not fold cleanly to PySpark" } else { "" }
}

fn block_warns(
    conn: &duckdb::Connection,
    fileid: &str,
) -> Result<BTreeMap<String, bool>, duckdb::Error> {
    let mut st = conn.prepare("SELECT block_id, warn FROM blocks WHERE fileid = ?")?;
    let mut rows = st.query(duckdb::params![fileid])?;
    let mut out = BTreeMap::new();
    while let Some(r) = rows.next()? {
        out.insert(r.get(0)?, r.get::<_, Option<bool>>(1)?.unwrap_or(false));
    }
    Ok(out)
}

/// `block_id -> the tables it reads`, mirroring `bench_api.py:317-320` exactly: a block that
/// writes a table reads that table's sources (this store's `edges` rows for the block, which
/// are the same `ds_lineage`/`ctl_lineage` facts the Bench derives its own from); a block
/// that writes nothing — every `PROC PRINT` — reads every `ds(lib,tab)` its node/4 terms
/// name, because the lineage facts have nothing to say about a block that makes no table.
pub fn block_reads(
    conn: &duckdb::Connection,
    fileid: &str,
    heads: &[inferred_duckdb::BlockHead],
) -> Result<BTreeMap<String, Vec<String>>, duckdb::Error> {
    let mut out: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();

    let mut st = conn.prepare("SELECT block_id, src_table FROM edges WHERE fileid = ?")?;
    let mut rows = st.query(duckdb::params![fileid])?;
    while let Some(r) = rows.next()? {
        out.entry(r.get(0)?).or_default().insert(r.get(1)?);
    }
    drop(rows);
    drop(st);

    let makes_nothing: BTreeSet<&str> = heads
        .iter()
        .filter(|b| b.name.is_empty())
        .map(|b| b.block_id.as_str())
        .collect();
    if !makes_nothing.is_empty() {
        let mut st = conn.prepare("SELECT block_id, term FROM node4 WHERE fileid = ? ORDER BY seq")?;
        let mut rows = st.query(duckdb::params![fileid])?;
        while let Some(r) = rows.next()? {
            let block_id: String = r.get(0)?;
            if !makes_nothing.contains(block_id.as_str()) {
                continue;
            }
            let term: String = r.get(1)?;
            for t in ds_tables(&term) {
                out.entry(block_id.clone()).or_default().insert(t);
            }
        }
    }

    Ok(out.into_iter().map(|(k, v)| (k, v.into_iter().collect())).collect())
}

/// Every `ds(lib,tab)` in a printed node/4 term, as `lib.tab` — the Rust reading of
/// `bench_api.py`'s `re.finditer(r"ds\((\w+),(\w+)\)", t)`.
fn ds_tables(term: &str) -> Vec<String> {
    let mut out = Vec::new();
    let bytes = term.as_bytes();
    let mut i = 0;
    while let Some(p) = term[i..].find("ds(") {
        let start = i + p + 3;
        let Some(comma) = term[start..].find(',') else { break };
        let Some(close) = term[start..].find(')') else { break };
        if comma < close {
            let lib = &term[start..start + comma];
            let tab = &term[start + comma + 1..start + close];
            if is_word(lib) && is_word(tab) {
                out.push(format!("{lib}.{tab}"));
            }
        }
        i = start;
        let _ = bytes;
    }
    out
}

fn is_word(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_alphanumeric() || c == '_')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn folder_and_name_split_on_the_last_slash() {
        assert_eq!(split_folder("sas/raw/11_branch_rollup.sas"), ("sas/raw".into(), "11_branch_rollup.sas".into()));
        assert_eq!(split_folder("x.sas"), (String::new(), "x.sas".into()));
    }

    #[test]
    fn stem_drops_the_folder_and_the_extension() {
        assert_eq!(stem_of("sas/raw/11_branch_rollup.sas"), "11_branch_rollup");
        assert_eq!(stem_of("test_vishnu_testdata_fixed.sas"), "test_vishnu_testdata_fixed");
    }

    #[test]
    fn ds_tables_reads_every_dataset_token_in_a_term() {
        assert_eq!(ds_tables("proc_print(ds(sales,sales_data))"), vec!["sales.sales_data"]);
        assert_eq!(
            ds_tables("join(ds(sales,a),ds(sales,b))"),
            vec!["sales.a".to_string(), "sales.b".to_string()]
        );
        assert!(ds_tables("libname(sales,lit('C:\\SASData'))").is_empty());
    }
}

// ---------------------------------------------------------------- UI1's file detail

/// `GET /api/file/<fileid>` — UI1's `FileDetail` (`raw/node4_viz/src/api.ts:50`). See this
/// module's doc comment for why this is a second shape on a second path rather than `file()`
/// with a path parameter.
pub async fn file_detail(
    State(state): State<AppState>,
    axum::extract::Path(fileid): axum::extract::Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let fileid = fileid.trim().trim_start_matches('/').to_string();
    if fileid.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "file(): fileid is required".into()));
    }
    let ise = |e: String| (StatusCode::INTERNAL_SERVER_ERROR, e);
    let conn = state.db.lock().map_err(|e| ise(e.to_string()))?;

    let ans = match inferred_duckdb::file(&conn, &fileid) {
        Ok(a) => a,
        Err(e) if e.to_string().contains("no rows") || e.to_string().contains("NoRows") => {
            return Err((StatusCode::NOT_FOUND, format!("file(): no such fileid {fileid}")))
        }
        Err(e) => return Err(ise(e.to_string())),
    };
    let code: Option<String> = conn
        .query_row("SELECT source FROM files WHERE fileid = ?", duckdb::params![&fileid], |r| r.get(0))
        .map_err(|e| ise(e.to_string()))?;

    let scope = vec![fileid.clone()];
    let facts = super::blocklinks::block_facts(&conn, &scope).map_err(|e| ise(e.to_string()))?;
    let block_rows = super::edges::block_flow_rows(&conn, &scope).map_err(|e| ise(e.to_string()))?;
    let human = inferred_duckdb::human_edits(&conn).map_err(|e| ise(e.to_string()))?;
    drop(conn);

    // The same merge `edges()` answers with, so the canvas and the drawer can never disagree
    // about a flow inside one file. Only the block level belongs in a *file's* detail; the
    // project level is the cross-file roll-up UI1 already gets from `neighborhood`.
    let merged = super::edges::merge_human_edits(
        super::edges::provided_rows(&block_rows, &facts),
        &human,
    );
    let block_edges: Vec<Value> = merged
        .into_iter()
        .filter(|r| r.level == "block" && r.fileid == fileid)
        .map(|r| {
            let b = r.block_id.clone().unwrap_or_default();
            json!({
                "src": r.src, "dst": r.dst, "tables": r.tables, "level": r.level,
                "provenance": r.provenance, "freshness": r.freshness, "fileid": r.fileid,
                "block": b, "src_ref": format!("{b}:{}", r.src), "dst_ref": format!("{b}:{}", r.dst),
            })
        })
        .collect();

    let blocks: Vec<Value> = ans
        .blocks
        .iter()
        .map(|b| {
            let f = facts.get(&(fileid.clone(), b.block_id.clone()));
            let reads: Vec<&String> = f.map(|f| f.reads.iter().collect()).unwrap_or_default();
            let writes: Vec<&String> = f.map(|f| f.writes.iter().collect()).unwrap_or_default();
            let mut occ: Vec<Value> = Vec::new();
            for t in &reads {
                occ.push(json!({ "id": format!("{}:{}", b.block_id, t), "name": t, "role": "read" }));
            }
            for t in &writes {
                occ.push(json!({ "id": format!("{}:{}", b.block_id, t), "name": t, "role": "write" }));
            }
            json!({
                "id": b.block_id,
                "status": if ans.status == "ok" { "PARSED" } else { "ERROR" },
                "kind": b.kind,
                "reads": reads.len(),
                "writes": writes.len(),
                "line_start": b.l0,
                "line_end": b.l1,
                "occurrences": occ,
            })
        })
        .collect();

    let (folder, name) = split_folder(&fileid);
    Ok(Json(json!({
        "fileid": fileid,
        "name": name,
        "folder": folder,
        "code": code.unwrap_or_default(),
        "blocks": blocks,
        "block_edges": block_edges,
        "file_edges": Vec::<Value>::new(),
        "macro_calls": Vec::<Value>::new(),
        "includes": Vec::<String>::new(),
        "missing_includes": Vec::<String>::new(),
    })))
}

/// `sas/raw/x.sas` -> `("sas/raw", "x.sas")`; a bare filename -> `("", "x.sas")`, the same
/// split `files()` already makes for its `folder`/`label` pair.
fn split_folder(fileid: &str) -> (String, String) {
    match fileid.rfind('/') {
        Some(i) => (fileid[..i].to_string(), fileid[i + 1..].to_string()),
        None => (String::new(), fileid.to_string()),
    }
}
