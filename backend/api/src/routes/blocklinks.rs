//! `blocklinks` — `GET /api/blocklinks?files=a,b`.
//!
//! **Why this exists.** UI1's canvas draws a file box; expand it and the box becomes its
//! blocks. A file-level edge then has to be re-hung on the two *blocks* that actually move
//! the table (`graph2.ts::graph2Elements`), which needs a block-to-block answer:
//! "inside `a.sas`, block X writes `work.t`; inside `b.sas`, block Y reads it". That is
//! this route, the block-level counterpart of `neighborhood`'s file-level `project_edges`.
//!
//! **The rule, from `:8000`** (`sas_lineage/ui_export.py::project_edges_blocks`, reached
//! through `service.py::block_links`): for each `(file, table)` the **latest** writer block
//! in that file, joined to **every** reader block in each *other* file. Same-file links are
//! dropped — those are already the file's own internal flow (`edges` at `level=block`).
//! Dropping the block columns and grouping reproduces `project_edges` exactly, which is why
//! this and `neighborhood` can never disagree about which files are linked.
//!
//! **Where the block-level facts come from.** This store's `edges` table is per-block
//! (`neighborhood`'s doc comment spells the roll-up out): a row `(src_table, dst_table,
//! fileid, block_id)` means "this block read `src_table` and wrote `dst_table`". So a
//! block's reads are its rows' `src_table`, and its writes are its rows' `dst_table`
//! unioned with `blocks.name` — the write target of a block whose read side failed to
//! fold, which would otherwise vanish. "Latest" is the highest `blocks.n`, the same
//! last-one-wins the Python loop gets by iterating blocks in file order.
//!
//! **`src_ref`/`dst_ref` are not `:8000`'s occurrence ids.** `:8000` numbers every table
//! token it scanned (`b_1_4505bc19:t_1`, `:t_2`, … in order of appearance in the statement
//! text) and hands those ids out here. This store has no per-token occurrence index at all
//! — `node4` holds statements, not table tokens — so a `t_<n>` here would be a number
//! invented to look like the old one. The ref is `"<block_id>:<table>"` instead: it is what
//! the store can actually prove, it is stable, and it keeps the field's contract (a ref
//! identifies one table occurrence inside one block, and two links through different
//! tables get different refs — the property `elkLayout.ts` groups on). Recorded as an
//! accepted divergence in `docs/plan/bronze/bronze_phase2_route_ledger.md`.
//!
//! **Inputs → outputs.** `blocks`, `edges` + a CSV of fileids → `{"links": [BlockLink]}`,
//! `BlockLink` as UI1 types it (`raw/node4_viz/src/api.ts:62`).

use crate::types::{AppState, BlockLink};
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Deserialize)]
pub struct BlockLinksParams {
    #[serde(default)]
    files: String,
}

/// `app.py::_split_files`: a CSV, blanks dropped, order and duplicates preserved
/// otherwise.
pub fn split_files(files: &str) -> Vec<String> {
    files
        .split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .collect()
}

/// One block, with the tables it reads and the tables it writes — the store's answer to
/// what `:8000` calls a block's `occurrences`.
#[derive(Debug, Default, Clone)]
pub struct BlockFacts {
    pub n: i32,
    pub reads: BTreeSet<String>,
    pub writes: BTreeSet<String>,
}

/// `(fileid, block_id) -> BlockFacts` for exactly the files in scope. Shared with
/// `routes::edges`, which needs the same per-block rows to build its `level=block` view.
pub fn block_facts(
    conn: &duckdb::Connection,
    scope: &[String],
) -> Result<BTreeMap<(String, String), BlockFacts>, duckdb::Error> {
    let mut out: BTreeMap<(String, String), BlockFacts> = BTreeMap::new();
    if scope.is_empty() {
        return Ok(out);
    }
    let in_scope: BTreeSet<&str> = scope.iter().map(|s| s.as_str()).collect();

    let mut st = conn.prepare("SELECT fileid, block_id, n, name FROM blocks")?;
    let mut rows = st.query([])?;
    while let Some(r) = rows.next()? {
        let fileid: String = r.get(0)?;
        if !in_scope.contains(fileid.as_str()) {
            continue;
        }
        let block_id: String = r.get(1)?;
        let n: i32 = r.get(2)?;
        let name: Option<String> = r.get(3)?;
        let e = out.entry((fileid, block_id)).or_default();
        e.n = n;
        if let Some(name) = name {
            if !name.is_empty() {
                e.writes.insert(name);
            }
        }
    }
    drop(rows);
    drop(st);

    let mut st = conn.prepare("SELECT fileid, block_id, src_table, dst_table FROM edges")?;
    let mut rows = st.query([])?;
    while let Some(r) = rows.next()? {
        let fileid: String = r.get(0)?;
        if !in_scope.contains(fileid.as_str()) {
            continue;
        }
        let block_id: String = r.get(1)?;
        let src: String = r.get(2)?;
        let dst: String = r.get(3)?;
        let e = out.entry((fileid, block_id)).or_default();
        e.reads.insert(src);
        e.writes.insert(dst);
    }
    Ok(out)
}

/// The rule itself, over already-loaded facts — pure, so it is testable without a store.
pub fn links_from_facts(facts: &BTreeMap<(String, String), BlockFacts>) -> Vec<BlockLink> {
    // latest writer of a table inside one file: highest `n` wins, as `:8000`'s loop does
    // by overwriting as it walks the file's blocks in order.
    let mut latest_writer: BTreeMap<(String, String), (i32, String)> = BTreeMap::new();
    let mut readers: BTreeMap<String, Vec<(String, String, i32)>> = BTreeMap::new();
    for ((fileid, block_id), f) in facts {
        for t in &f.writes {
            let key = (fileid.clone(), t.clone());
            let better = match latest_writer.get(&key) {
                Some((n, _)) => f.n >= *n,
                None => true,
            };
            if better {
                latest_writer.insert(key, (f.n, block_id.clone()));
            }
        }
        for t in &f.reads {
            readers
                .entry(t.clone())
                .or_default()
                .push((fileid.clone(), block_id.clone(), f.n));
        }
    }

    let mut links: Vec<BlockLink> = Vec::new();
    for ((src_file, table), (_, src_block)) in &latest_writer {
        let Some(rs) = readers.get(table) else { continue };
        for (dst_file, dst_block, _) in rs {
            if dst_file == src_file {
                continue;
            }
            links.push(BlockLink {
                src_file: src_file.clone(),
                src_ref: format!("{src_block}:{table}"),
                src_block: src_block.clone(),
                dst_file: dst_file.clone(),
                dst_ref: format!("{dst_block}:{table}"),
                dst_block: dst_block.clone(),
                table: table.clone(),
            });
        }
    }
    links.sort_by(|a, b| {
        (&a.src_file, &a.src_block, &a.dst_file, &a.dst_block, &a.table).cmp(&(
            &b.src_file,
            &b.src_block,
            &b.dst_file,
            &b.dst_block,
            &b.table,
        ))
    });
    links
}

pub async fn blocklinks(
    State(state): State<AppState>,
    Query(params): Query<BlockLinksParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let scope = split_files(&params.files);
    let conn = state.db.lock().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let facts = block_facts(&conn, &scope)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(json!({ "links": links_from_facts(&facts) })))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn facts(rows: &[(&str, &str, i32, &[&str], &[&str])]) -> BTreeMap<(String, String), BlockFacts> {
        rows.iter()
            .map(|(f, b, n, reads, writes)| {
                (
                    (f.to_string(), b.to_string()),
                    BlockFacts {
                        n: *n,
                        reads: reads.iter().map(|s| s.to_string()).collect(),
                        writes: writes.iter().map(|s| s.to_string()).collect(),
                    },
                )
            })
            .collect()
    }

    #[test]
    fn splits_a_csv_and_drops_blanks() {
        assert_eq!(split_files("a.sas, b.sas,,"), vec!["a.sas".to_string(), "b.sas".to_string()]);
        assert!(split_files("").is_empty());
    }

    #[test]
    fn latest_writer_wins_and_every_reader_is_linked() {
        let f = facts(&[
            ("a.sas", "b_001", 0, &[], &["work.t"]),
            ("a.sas", "b_002", 1, &[], &["work.t"]), // later writer of the same table
            ("b.sas", "b_001", 0, &["work.t"], &["work.u"]),
            ("c.sas", "b_001", 0, &["work.t"], &[]),
        ]);
        let links = links_from_facts(&f);
        assert_eq!(links.len(), 2);
        assert!(links.iter().all(|l| l.src_block == "b_002"));
        assert_eq!(links[0].dst_file, "b.sas");
        assert_eq!(links[1].dst_file, "c.sas");
        assert_eq!(links[0].src_ref, "b_002:work.t");
    }

    #[test]
    fn a_same_file_read_is_not_a_cross_file_link() {
        let f = facts(&[
            ("a.sas", "b_001", 0, &[], &["work.t"]),
            ("a.sas", "b_002", 1, &["work.t"], &["work.u"]),
        ]);
        assert!(links_from_facts(&f).is_empty());
    }
}
