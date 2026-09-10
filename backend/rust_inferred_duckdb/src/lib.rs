//! `inferred_duckdb` — everything the engine infers about a folder, made durable.
//!
//! **Why this exists.** exp_42's Bench folded a file every time you opened it: 63.4 s for
//! `big_1000.sas` (`docs/plan/bronze/bronze_perf_receipts_exp42.md`). That is the whole
//! reason exp_005 exists. Here a folder is folded **once**, by `convert`, into DuckDB;
//! after that every question the UIs ask is a keyed read of a few rows, and none of them
//! touches the parser.
//!
//! **Inputs → outputs.** a pyDSL spec + a folder of SAS files → `convert()` → the eight
//! tables of `schema.rs` → `file()`, `blocks()`, `tablegraph()`, `search()` answer from
//! rows alone.
//!
//! The engine is called in-process through the `rules_converter` library, so nothing is
//! written to disk and re-parsed on the way.

pub mod datamatch;
pub mod lineage_blocks;
pub mod schema;

use duckdb::{params, Connection};
use rules_converter::{emit, emit_pretty, fold_file, lineage, parser, rebuild_source, spec, term, tokenise};
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::time::Instant;

pub type Res<T> = Result<T, Box<dyn std::error::Error>>;

/// Open (or create) a store and make sure every table exists.
pub fn open(db: &Path) -> Res<Connection> {
    let conn = Connection::open(db)?;
    conn.execute_batch(schema::DDL)?;
    Ok(conn)
}

// ---------------------------------------------------------------- convert

/// What one `convert` run did. Returned so the caller can print a receipt.
#[derive(Debug, Default, Serialize)]
pub struct ConvertReport {
    pub files: usize,
    pub ok: usize,
    pub failed: usize,
    pub blocks: usize,
    pub node4: usize,
    pub edges: usize,
    pub fold_ms: f64,
    pub store_ms: f64,
    pub total_ms: f64,
}

/// Fold every `.sas` file under `folder` and write all eight tables.
///
/// Idempotent: a file already in the store with the same hash is skipped, and one that
/// changed has its rows deleted before the new ones land.
pub fn convert(conn: &mut Connection, spec_path: &Path, folder: &Path) -> Res<ConvertReport> {
    let t_all = Instant::now();
    let spec_text = std::fs::read_to_string(spec_path)?;
    let spec: spec::Spec = serde_json::from_str(&spec_text)?;
    let spec_hash = hash_of(&spec_text);
    let mut rep = ConvertReport::default();

    let mut sas: Vec<std::path::PathBuf> = Vec::new();
    collect_sas(folder, &mut sas)?;
    sas.sort();
    rep.files = sas.len();

    for path in &sas {
        let fileid = path
            .strip_prefix(folder)
            .unwrap_or(path)
            .to_string_lossy()
            .to_string();
        let text = std::fs::read_to_string(path)?;
        let hash = hash_of(&text);

        // unchanged file AND unchanged spec? leave it alone. If the spec changed, the
        // grammar that produced the stored rows changed too, so they are stale answers
        // even though the source file itself didn't move.
        let seen: Option<(String, String)> = conn
            .query_row(
                "SELECT f.hash, coalesce(m.value, '') FROM files f LEFT JOIN meta m ON m.key = 'spec_hash' WHERE f.fileid = ?",
                params![&fileid],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .ok();
        if seen.as_ref().map(|(h, s)| h == &hash && s == &spec_hash).unwrap_or(false) {
            rep.ok += 1;
            continue;
        }

        let t_fold = Instant::now();
        let folded = fold_one(&spec, &fileid, &text);
        rep.fold_ms += t_fold.elapsed().as_secs_f64() * 1000.0;

        let t_store = Instant::now();
        let tx = conn.transaction()?;
        for sql in schema::CLEAR_FILE {
            tx.execute(sql, params![&fileid])?;
        }
        match &folded {
            Ok(f) => {
                write_file(&tx, &fileid, &hash, &text, "ok", None)?;
                rep.blocks += write_blocks(&tx, &fileid, f)?;
                rep.node4 += write_node4(&tx, &fileid, f)?;
                rep.edges += write_edges(&tx, &fileid, f)?;
                write_tables(&tx, &fileid, f)?;
                write_receipt(&tx, &fileid, f)?;
                event(&tx, "convert.ok", &fileid, &format!("{} blocks", f.blocks.len()))?;
                rep.ok += 1;
            }
            Err(e) => {
                write_file(&tx, &fileid, &hash, &text, "error", Some(e))?;
                event(&tx, "convert.error", &fileid, e)?;
                rep.failed += 1;
            }
        }
        tx.commit()?;
        rep.store_ms += t_store.elapsed().as_secs_f64() * 1000.0;
    }

    // Written unconditionally, even when every file was skipped: if this only ran on a
    // conversion, the first run after a spec change would store the new hash *and* skip
    // every file (their file-hashes are unchanged), permanently masking the change.
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('spec_hash', ?)", params![&spec_hash])?;

    rep.total_ms = t_all.elapsed().as_secs_f64() * 1000.0;
    Ok(rep)
}

fn collect_sas(dir: &Path, out: &mut Vec<std::path::PathBuf>) -> Res<()> {
    if dir.is_file() {
        out.push(dir.to_path_buf());
        return Ok(());
    }
    for e in std::fs::read_dir(dir)? {
        let p = e?.path();
        if p.is_dir() {
            collect_sas(&p, out)?;
        } else if p.extension().map(|x| x == "sas").unwrap_or(false) {
            out.push(p);
        }
    }
    Ok(())
}

fn hash_of(s: &str) -> String {
    // FNV-1a: enough to notice a file changed; not a security hash.
    let mut h: u64 = 0xcbf29ce484222325;
    for b in s.as_bytes() {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    format!("{:016x}", h)
}

/// One file's fold, held in memory until it is written.
pub struct Folded {
    pub blocks: Vec<BlockRow>,
    pub node4: Vec<(String, usize, String, usize, usize, usize, usize)>, // block, seq, term, l0, l1, b0, b1
    pub edges: Vec<(String, String, String, String)>,      // src, dst, kind, block
    pub statements: usize,
    pub folded_n: usize,
    pub roundtrip: usize,
    pub source_match: bool,
    pub rust_us: u128,
}

pub struct BlockRow {
    pub block_id: String,
    pub n: usize,
    pub kind: String,
    pub name: String,
    pub l0: usize,
    pub l1: usize,
    pub sas_text: String,
    pub py_text: String,
    pub py_pretty: String,
    pub warn: bool,
}

/// The table named by a block's own head term, straight from the fold — used only as a
/// fallback when `ds_lineage` has nothing to say (see the call site). Mirrors exactly the
/// two shapes `lineage::sas::step` itself matches on: a `DATA` step's target, or a
/// `PROC SQL` block's `CREATE TABLE AS`.
fn block_write_target(bn: &[(String, &term::Term)]) -> Option<String> {
    for (_, t) in bn {
        match t.functor() {
            ("data", 1) | ("create_table_as", 2) => return Some(lineage::ds_key(&t.args()[0])),
            _ => {}
        }
    }
    None
}

/// Ruling D9. `emit::Emitter::program` and `emit_pretty::Pretty::program` are ports of
/// `codegen/*.pl` and refuse an unmapped SAS construct (e.g. `today()`, no
/// `raw/bench_stack/codegen/*.pl` rule for it either) by panicking — that is how the
/// engine signals "no rule for this", not a bug. Prolog is the reference and Rust mirrors
/// it (owner rule, exp_42): we do not add a mapping Prolog doesn't have (that was the
/// previous agent's mistake — see the Task 5 brief). But a library must not abort its
/// caller's process over a per-block gap, and Task 6b puts `convert` behind HTTP, so a
/// panic here would take the API down. `catch_unwind` is the right tool: the panic *is*
/// the failure signal, so catching it is catching the real outcome, not working around
/// one. A hook swap around the call keeps the default panic handler from spamming stderr
/// for every warn block on a real corpus — `main` still hears about it, just via the
/// return value instead of a printed backtrace. The caller stores empty text and sets
/// `warn = true` on `Err`; the panic message becomes the finding the Task 5 report lists.
fn catch_emit<F: FnOnce() -> String + std::panic::UnwindSafe>(f: F) -> Result<String, String> {
    let prev_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(|_| {}));
    let result = std::panic::catch_unwind(f);
    std::panic::set_hook(prev_hook);
    result.map_err(|payload| {
        payload
            .downcast_ref::<String>()
            .cloned()
            .or_else(|| payload.downcast_ref::<&str>().map(|s| s.to_string()))
            .unwrap_or_else(|| "panic with non-string payload".to_string())
    })
}

fn fold_one(spec: &spec::Spec, fileid: &str, text: &str) -> Result<Folded, String> {
    let t0 = Instant::now();
    let (stmts, terms, ids) = fold_file(spec, text);
    let statements = stmts.len();
    let folded_n = terms.iter().filter(|t| t.is_some()).count();
    if folded_n == 0 && statements > 0 {
        return Err(format!("nothing folded: {} statements, 0 terms", statements));
    }

    // node/4 rows and the emitter's nodes, in one pass
    let mut node4 = Vec::new();
    let mut nodes: Vec<emit::Node> = Vec::new();
    for (i, st) in stmts.iter().enumerate() {
        let Some(t) = &terms[i] else { continue };
        node4.push((ids[i].clone(), st.seq, format!("{}", t), st.l0, st.l1, st.b0, st.b1));
        nodes.push(emit::Node {
            block: ids[i].clone(),
            seq: st.seq,
            term: t.clone(),
            l0: st.l0,
            l1: st.l1,
            b0: st.b0,
            b1: st.b1,
        });
    }

    // L1, the round trip, done for real: print each term back to SAS, re-tokenise,
    // re-fold, and require the term to come back identical. Then the source-rebuild
    // law: splice the printed tokens into the original stream and require the result
    // to equal the source byte for byte. The earlier draft of this function counted
    // terms that printed non-null and called it a round trip, which would have
    // reported L1 green on a broken parse.
    let printer = parser::Printer { spec };
    let mut printed_texts: Vec<Option<Vec<String>>> = vec![None; terms.len()];
    let mut roundtrip = 0usize;
    for (i, t) in terms.iter().enumerate() {
        let Some(t) = t else { continue };
        let Some(texts) = printer.print_stmt(t) else { continue };
        printed_texts[i] = Some(texts.clone());
        let snippet = texts.join(" ");
        let toks2 = tokenise::tokenise(spec, &snippet);
        let st2 = tokenise::split_statements(&toks2);
        let again = st2.first().and_then(|s| parser::Parser::new(spec, &s.toks).fold());
        if matches!(again, Some(t2) if t2.to_string() == t.to_string()) {
            roundtrip += 1;
        }
    }
    let toks = tokenise::tokenise(spec, text);
    let (rebuilt, _mismatch) = rebuild_source(&toks, &printed_texts);
    let source_match = rebuilt == text;

    // per-block text, kind and the table it writes
    let src_lines: Vec<&str> = text.lines().collect();
    let mut order: Vec<String> = Vec::new();
    for id in &ids {
        if !order.contains(id) {
            order.push(id.clone());
        }
    }
    let mut blocks = Vec::new();
    for (n, bid) in order.iter().enumerate() {
        let idx: Vec<usize> = ids.iter().enumerate().filter(|(_, x)| *x == bid).map(|(i, _)| i).collect();
        if idx.is_empty() {
            continue;
        }
        let l0 = idx.iter().map(|i| stmts[*i].l0).min().unwrap_or(0);
        let l1 = idx.iter().map(|i| stmts[*i].l1).max().unwrap_or(0);
        let kind = idx
            .iter()
            .filter_map(|i| terms[*i].as_ref())
            .map(|t| t.functor().0.to_string())
            .next()
            .unwrap_or_default();
        let sas_text = src_lines
            .get(l0.saturating_sub(1)..l1.min(src_lines.len()))
            .map(|s| s.join("\n"))
            .unwrap_or_default();

        // what this block writes, from its own lineage facts
        let bn: Vec<(String, &term::Term)> = idx
            .iter()
            .filter_map(|i| terms[*i].as_ref().map(|t| (bid.clone(), t)))
            .collect();
        // What this block writes. `ds_lineage` only fires when the block also *reads*
        // another table (lineage.rs's `step`), so a block that only writes — a DATA step
        // seeded from `datalines`, with no `SET`/`MERGE` — leaves no ds_lineage fact even
        // though it plainly names its own output right in the block's own head term. Ask
        // that term directly before giving up, so `tables`/`search()` (Task 5) don't lose
        // every seed table in a corpus.
        let name = lineage::sas::run(&bn)
            .text()
            .lines()
            .find(|l| l.starts_with("ds_lineage("))
            .and_then(|l| l.split('\'').nth(1).map(|s| s.to_string()))
            .or_else(|| block_write_target(&bn))
            .unwrap_or_default();

        let bnodes: Vec<emit::Node> = nodes.iter().filter(|nd| &nd.block == bid).cloned().collect();
        let emit_bnodes = bnodes.clone();
        let emit_result = catch_emit(move || emit::Emitter::new().program(&emit_bnodes, ""));
        let pretty_bnodes = bnodes.clone();
        let pretty_result = catch_emit(move || emit_pretty::Pretty::new(text, &pretty_bnodes).program(""));
        let mut warn = false;
        if let Err(msg) = &emit_result {
            warn = true;
            eprintln!("LINEAGEQ warn: {} block {} (emit): {}", fileid, bid, msg);
        }
        if let Err(msg) = &pretty_result {
            warn = true;
            eprintln!("LINEAGEQ warn: {} block {} (emit_pretty): {}", fileid, bid, msg);
        }
        let py_text = emit_result.unwrap_or_default();
        let py_pretty = pretty_result.unwrap_or_default();

        blocks.push(BlockRow {
            block_id: bid.clone(),
            n,
            kind,
            name,
            l0,
            l1,
            sas_text,
            py_text,
            py_pretty,
            warn,
        });
    }

    // per-block edges, from ds_lineage(OUT, IN), attributed to the block that made them
    let edges: Vec<(String, String, String, String)> =
        crate::lineage_blocks::edges_per_block(&ids, &terms)
            .into_iter()
            .map(|e| (e.src, e.dst, e.kind, e.block_id))
            .collect();

    let _ = fileid;
    Ok(Folded {
        blocks,
        node4,
        edges,
        statements,
        folded_n,
        roundtrip,
        source_match,
        rust_us: t0.elapsed().as_micros(),
    })
}

// ---------------------------------------------------------------- writers

fn write_file(tx: &duckdb::Transaction, fileid: &str, hash: &str, text: &str, status: &str, err: Option<&String>) -> Res<()> {
    tx.execute(
        "INSERT INTO files (fileid, hash, loc, status, error, converted_at, source) VALUES (?,?,?,?,?, now(), ?)",
        params![fileid, hash, text.lines().count() as i32, status, err.map(|s| s.as_str()).unwrap_or(""), text],
    )?;
    Ok(())
}

fn write_blocks(tx: &duckdb::Transaction, fileid: &str, f: &Folded) -> Res<usize> {
    let mut st = tx.prepare(
        "INSERT INTO blocks (fileid, block_id, n, kind, name, l0, l1, sas_text, py_text, py_pretty, warn, block_hash)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
    )?;
    for b in &f.blocks {
        st.execute(params![
            fileid, b.block_id, b.n as i32, b.kind, b.name,
            b.l0 as i32, b.l1 as i32, b.sas_text, b.py_text, b.py_pretty, b.warn, hash_of(&b.sas_text)
        ])?;
    }
    Ok(f.blocks.len())
}

fn write_node4(tx: &duckdb::Transaction, fileid: &str, f: &Folded) -> Res<usize> {
    let mut st = tx.prepare(
        "INSERT INTO node4 (fileid, block_id, seq, term, trace_l0, trace_l1, trace_b0, trace_b1) VALUES (?,?,?,?,?,?,?,?)",
    )?;
    for (b, seq, t, l0, l1, b0, b1) in &f.node4 {
        st.execute(params![fileid, b, *seq as i32, t, *l0 as i32, *l1 as i32, *b0 as i32, *b1 as i32])?;
    }
    Ok(f.node4.len())
}

fn write_edges(tx: &duckdb::Transaction, fileid: &str, f: &Folded) -> Res<usize> {
    let mut st = tx.prepare("INSERT INTO edges (src_table, dst_table, kind, fileid, block_id, level) VALUES (?,?,?,?,?,?)")?;
    for (s, d, k, b) in &f.edges {
        st.execute(params![s, d, k, fileid, b, "file"])?;
    }
    Ok(f.edges.len())
}

fn write_tables(tx: &duckdb::Transaction, fileid: &str, f: &Folded) -> Res<()> {
    let mut st = tx.prepare("INSERT OR IGNORE INTO tables (name, lib, first_writer_fileid) VALUES (?,?,?)")?;
    for b in &f.blocks {
        if b.name.is_empty() {
            continue;
        }
        let lib = b.name.split('.').next().unwrap_or("work").to_string();
        st.execute(params![b.name, lib, fileid])?;
    }
    Ok(())
}

fn write_receipt(tx: &duckdb::Transaction, fileid: &str, f: &Folded) -> Res<()> {
    tx.execute(
        "INSERT INTO receipts (fileid, statements, folded, roundtrip, source_match, proof_state, rust_us)
         VALUES (?,?,?,?,?,?,?)",
        params![
            fileid, f.statements as i32, f.folded_n as i32, f.roundtrip as i32,
            f.source_match, "pending", f.rust_us as i64
        ],
    )?;
    Ok(())
}

fn event(tx: &duckdb::Transaction, kind: &str, fileid: &str, detail: &str) -> Res<()> {
    tx.execute("INSERT INTO events (at_ts, kind, fileid, detail) VALUES (now(), ?,?,?)", params![kind, fileid, detail])?;
    Ok(())
}


// ---------------------------------------------------------------- human edits

/// One human assertion about a flow — the `human_edits` row shape of `schema.rs`, which is
/// `raw/lineage_server`'s own (`server/indexer.py`) column for column.
///
/// **Why this exists (Task 7, 2026-09-10).** `edges()` answers the *merged* view: inferred
/// rows with un-flagged customer edits applied. Nothing in this store held a customer edit
/// before, so the merge had nothing to merge. `edited_at` is carried as the string DuckDB
/// prints it, not a chrono type: this crate has no date dependency, nothing sorts on it
/// today, and a string survives the JSON fixture round trip the API's tests load it from.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanEdit {
    pub edit_id: String,
    pub edited_at: String,
    pub editor: String,
    pub action: String,
    pub src: String,
    pub dst: String,
    pub table_name: String,
    pub level: String,
    pub comment: String,
    pub block_id: Option<String>,
    pub requires_check: bool,
    pub fileid: Option<String>,
    pub dismissed: bool,
    pub freshness: String,
}

/// Write one human assertion. Idempotent on `edit_id` (a re-import of the same row
/// replaces it) so seeding a store twice cannot double the merged view.
pub fn insert_human_edit(conn: &Connection, e: &HumanEdit) -> Res<()> {
    conn.execute("DELETE FROM human_edits WHERE edit_id = ?", params![e.edit_id])?;
    conn.execute(
        "INSERT INTO human_edits VALUES (?, CAST(? AS TIMESTAMP), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        params![
            e.edit_id, e.edited_at, e.editor, e.action, e.src, e.dst, e.table_name,
            e.level, e.comment, e.block_id, e.requires_check, e.fileid, e.dismissed,
            e.freshness
        ],
    )?;
    Ok(())
}

/// Read a JSON array of `HumanEdit`s from a file and write every one of them.
///
/// **Why this exists (M2/G3, 2026-09-10).** `insert_human_edit` existed, but nothing on the
/// command line could call it: M1 seeded the dev store's one customer edit with a throwaway
/// Python script, which means the dev store could not be rebuilt from the repo alone (plan
/// Part G, finding G3). This is the store-side half of `lineageq_store human-edit <db>
/// <json>`; the JSON shape is exactly what `backend/api/tests/fixtures/human_edits.json`
/// holds, so the same file seeds the test store and the dev store.
///
/// Returns how many rows were written. Idempotent, because `insert_human_edit` is: running
/// it twice on the same file leaves the same rows.
///
/// **Inputs → outputs.** a connection + a path to a JSON array → that many `human_edits`
/// rows, and the count.
pub fn load_human_edits(conn: &Connection, path: &Path) -> Res<usize> {
    let text = std::fs::read_to_string(path)?;
    let edits: Vec<HumanEdit> = serde_json::from_str(&text)?;
    for e in &edits {
        insert_human_edit(conn, e)?;
    }
    Ok(edits.len())
}

/// Every human assertion in the store, oldest first. `edges()` merges these over the
/// inferred rows exactly as `service.py::_materialize_provided`'s `_merged_edges` does.
pub fn human_edits(conn: &Connection) -> Res<Vec<HumanEdit>> {
    let mut st = conn.prepare(
        "SELECT edit_id, CAST(edited_at AS VARCHAR), editor, action, src, dst, table_name,
                level, comment, block_id, requires_check, fileid, dismissed, freshness
         FROM human_edits ORDER BY edited_at, edit_id",
    )?;
    Ok(st
        .query_map([], |r| {
            Ok(HumanEdit {
                edit_id: r.get(0)?,
                edited_at: r.get::<_, Option<String>>(1)?.unwrap_or_default(),
                editor: r.get::<_, Option<String>>(2)?.unwrap_or_default(),
                action: r.get::<_, Option<String>>(3)?.unwrap_or_default(),
                src: r.get::<_, Option<String>>(4)?.unwrap_or_default(),
                dst: r.get::<_, Option<String>>(5)?.unwrap_or_default(),
                table_name: r.get::<_, Option<String>>(6)?.unwrap_or_default(),
                level: r.get::<_, Option<String>>(7)?.unwrap_or_default(),
                comment: r.get::<_, Option<String>>(8)?.unwrap_or_default(),
                block_id: r.get(9)?,
                requires_check: r.get::<_, Option<bool>>(10)?.unwrap_or(false),
                fileid: r.get(11)?,
                dismissed: r.get::<_, Option<bool>>(12)?.unwrap_or(false),
                freshness: r.get::<_, Option<String>>(13)?.unwrap_or_else(|| "green".into()),
            })
        })?
        .collect::<Result<Vec<_>, _>>()?)
}

// ---------------------------------------------------------------- readers
// Every one of these is a keyed read. None folds anything.

#[derive(Debug, Serialize)]
pub struct FileAnswer {
    pub fileid: String,
    pub loc: i32,
    pub status: String,
    pub statements: i32,
    pub folded: i32,
    pub roundtrip: i32,
    pub source_match: bool,
    pub proof_state: String,
    pub rust_us: i64,
    /// block list without any text — the plan is explicit that `file()` returns no source
    pub blocks: Vec<BlockHead>,
}

#[derive(Debug, Serialize)]
pub struct BlockHead {
    pub block_id: String,
    pub n: i32,
    pub kind: String,
    pub name: String,
    pub l0: i32,
    pub l1: i32,
}

/// `file(fileid)` — header, block list (no text), receipts, proof state.
pub fn file(conn: &Connection, fileid: &str) -> Res<FileAnswer> {
    let (loc, status): (i32, String) =
        conn.query_row("SELECT loc, status FROM files WHERE fileid = ?", params![fileid], |r| {
            Ok((r.get(0)?, r.get(1)?))
        })?;
    let (statements, folded, roundtrip, source_match, proof_state, rust_us) = conn
        .query_row(
            "SELECT statements, folded, roundtrip, source_match, proof_state, rust_us FROM receipts WHERE fileid = ?",
            params![fileid],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?, r.get(5)?)),
        )
        .unwrap_or((0, 0, 0, false, "pending".into(), 0));

    let mut st = conn.prepare("SELECT block_id, n, kind, name, l0, l1 FROM blocks WHERE fileid = ? ORDER BY n")?;
    let blocks = st
        .query_map(params![fileid], |r| {
            Ok(BlockHead { block_id: r.get(0)?, n: r.get(1)?, kind: r.get(2)?, name: r.get(3)?, l0: r.get(4)?, l1: r.get(5)? })
        })?
        .collect::<Result<Vec<_>, _>>()?;

    Ok(FileAnswer { fileid: fileid.into(), loc, status, statements, folded, roundtrip, source_match, proof_state, rust_us, blocks })
}

#[derive(Debug, Serialize)]
pub struct BlockFull {
    pub block_id: String,
    pub n: i32,
    pub kind: String,
    pub name: String,
    pub l0: i32,
    pub l1: i32,
    pub sas_text: String,
    pub py_pretty: String,
}

/// `blocks(fileid, from, to)` — one window of blocks, with their text.
pub fn blocks(conn: &Connection, fileid: &str, from: i64, to: i64) -> Res<Vec<BlockFull>> {
    let mut st = conn.prepare(
        "SELECT block_id, n, kind, name, l0, l1, sas_text, py_pretty
         FROM blocks WHERE fileid = ? AND n >= ? AND n < ? ORDER BY n",
    )?;
    let out = st
        .query_map(params![fileid, from, to], |r| {
            Ok(BlockFull {
                block_id: r.get(0)?, n: r.get(1)?, kind: r.get(2)?, name: r.get(3)?,
                l0: r.get(4)?, l1: r.get(5)?, sas_text: r.get(6)?, py_pretty: r.get(7)?,
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(out)
}

/// `tablegraph(fileid)` — the tables and edges of one file.
pub fn tablegraph(conn: &Connection, fileid: &str) -> Res<Vec<(String, String, String)>> {
    let mut st = conn.prepare("SELECT src_table, dst_table, kind FROM edges WHERE fileid = ?")?;
    Ok(st
        .query_map(params![fileid], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))?
        .collect::<Result<Vec<_>, _>>()?)
}

/// One block that makes a table: which file it is in, which block, and where in that file's
/// run order it sits.
#[derive(Debug, Serialize)]
pub struct Maker {
    pub fileid: String,
    pub block_id: String,
    pub n: i32,
}

/// `story(table)` — every block anywhere in the store that writes `table`, in run order.
///
/// **Why this exists (Task 10, 2026-09-10).** `tablegraph()` answers "what does this *file*
/// do"; `story()` answers the question a person actually asks about a table they do not
/// trust — *who made this, in what order?* — and that question is not scoped to one file, so
/// it cannot be answered off `tablegraph`'s per-file read.
///
/// **Run order, not insertion order.** `ORDER BY fileid, n` — `blocks.n` is the block's
/// 0-based position in its file, which is the order the SAS program executes. The `edges`
/// table has no ordering of its own (a `SELECT` off it comes back in whatever order DuckDB
/// scanned), so the order has to be joined back from `blocks` or it is not an order at all.
/// Task 10's own test asserts exactly that, and `tools/diff_route.py` deliberately keeps
/// `makers` out of its order-blind field list for the same reason.
///
/// A table nobody writes — a source read from datalines, a typo — has no makers. That is an
/// empty list, not an error: "nothing made this" is a real answer.
///
/// **Inputs → outputs.** `edges` joined to `blocks` + a table name → its makers, in run
/// order.
pub fn story(conn: &Connection, table: &str) -> Res<Vec<Maker>> {
    let mut st = conn.prepare(
        "SELECT DISTINCT e.fileid, e.block_id, b.n
         FROM edges e JOIN blocks b ON b.fileid = e.fileid AND b.block_id = e.block_id
         WHERE e.dst_table = ?
         ORDER BY e.fileid, b.n",
    )?;
    Ok(st
        .query_map(params![table], |r| {
            Ok(Maker { fileid: r.get(0)?, block_id: r.get(1)?, n: r.get(2)? })
        })?
        .collect::<Result<Vec<_>, _>>()?)
}

/// `search(q)` — tables and files matching.
pub fn search(conn: &Connection, q: &str) -> Res<Vec<(String, String)>> {
    let like = format!("%{}%", q);
    let mut st = conn.prepare(
        "SELECT 'table' AS t, name FROM tables WHERE name ILIKE ?
         UNION ALL
         SELECT 'file', fileid FROM files WHERE fileid ILIKE ? LIMIT 50",
    )?;
    Ok(st
        .query_map(params![&like, &like], |r| Ok((r.get(0)?, r.get(1)?)))?
        .collect::<Result<Vec<_>, _>>()?)
}

/// Row counts, for the receipt.
pub fn counts(conn: &Connection) -> Res<Vec<(String, i64)>> {
    let mut out = Vec::new();
    for t in ["files", "blocks", "node4", "edges", "tables", "receipts", "runs", "events"] {
        let n: i64 = conn.query_row(&format!("SELECT count(*) FROM {}", t), [], |r| r.get(0))?;
        out.push((t.to_string(), n));
    }
    Ok(out)
}
