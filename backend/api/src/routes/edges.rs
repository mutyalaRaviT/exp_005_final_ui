//! `edges` — `GET /api/edges?files=&filter=&level=&offset=&limit=`.
//!
//! **Why this exists.** UI1's edges drawer: the flat, filterable, pageable table under the
//! canvas — every flow in the selected files, at whichever granularity you ask for, with a
//! `provenance` column saying whether the engine found it (`fact`), derived it (`inferred`)
//! or a human asserted it (`human_gold`).
//!
//! **The merge, from `:8000`.** `service.py::final_edges` reads one DuckDB view,
//! `_merged_edges` (`_materialize_provided`): the engine's own rows unioned with the
//! project-level roll-up, then customer edits applied — `reject` drops the matching block's
//! rows, `confirm` upgrades their provenance to `human_gold`, `add`/`correct` append a
//! `human_gold` row of their own, and any edit still `requires_check` is ignored entirely,
//! as if it did not exist. Ported here statement for statement over
//! `inferred_duckdb::human_edits` (the table Task 7 added to `schema.rs` for exactly this —
//! before it, this store had nowhere for a customer edit to live and the merge had nothing
//! to merge). Note what `_merged_edges` does *not* do: the `add`/`correct` arm is not
//! scoped by `files` at all, so a `human_gold` row shows up in every query. That is the
//! answer being mirrored, so it is mirrored, quirk included.
//!
//! **The three levels.**
//! - `block` / `fact` — one row of this store's per-block `edges` table: block B in
//!   `fileid` read `src_table` and wrote `dst_table`.
//! - `project` / `inferred` — the cross-file roll-up, identical to
//!   `neighborhood`'s `project_edges` (writer file -> reader file, one row per table
//!   moved), so the drawer and the canvas can never disagree.
//! - `file` — `:8000` emits a handful of these from its own `lineage` table's `FILE_FLOW`
//!   rows. This store has no `FILE_FLOW` fact; see the ledger for the one row in the
//!   `team_finance` corpus that is legitimately absent here.
//!
//! `tables` is a one-element list even though a merged row is always one table: UI1's
//! single `EdgeOut`/`EdgeRow` type covers every edge surface (`api.ts:76`), so every one of
//! them ships a list.
//!
//! **Inputs → outputs.** `blocks`, `edges`, `human_edits` + the five query params →
//! `{"total": N, "rows": [EdgeRow]}` (`raw/node4_viz/src/api.ts:85`).

use crate::routes::blocklinks::{block_facts, split_files};
use crate::types::{AppState, EdgeRow};
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

/// `app.py::edges`' own default (`DEFAULT_EDGES_LIMIT`).
const DEFAULT_LIMIT: i64 = 200;

#[derive(Deserialize)]
pub struct EdgesParams {
    #[serde(default)]
    files: String,
    #[serde(default)]
    filter: String,
    #[serde(default)]
    level: String,
    #[serde(default)]
    offset: Option<i64>,
    #[serde(default)]
    limit: Option<i64>,
}

pub async fn edges(
    State(state): State<AppState>,
    Query(params): Query<EdgesParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let ise = |e: duckdb::Error| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string());
    let conn = state.db.lock().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    // `app.py::edges`: an empty `files` means the whole store, not an empty answer.
    let mut scope = split_files(&params.files);
    if scope.is_empty() {
        let mut st = conn.prepare("SELECT DISTINCT fileid FROM files ORDER BY fileid").map_err(ise)?;
        let mut rows = st.query([]).map_err(ise)?;
        while let Some(r) = rows.next().map_err(ise)? {
            scope.push(r.get(0).map_err(ise)?);
        }
    }

    let facts = block_facts(&conn, &scope).map_err(ise)?;
    let block_rows = block_flow_rows(&conn, &scope).map_err(ise)?;
    let human = inferred_duckdb::human_edits(&conn)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    drop(conn);

    let provided = provided_rows(&block_rows, &facts);
    let merged = merge_human_edits(provided, &human);

    let level = params.level.trim().to_string();
    let filter = params.filter.trim().to_lowercase();
    let mut kept: Vec<EdgeRow> = merged
        .into_iter()
        .filter(|r| level.is_empty() || r.level == level)
        .filter(|r| {
            filter.is_empty()
                || r.src.to_lowercase().contains(&filter)
                || r.dst.to_lowercase().contains(&filter)
                || r.tables[0].to_lowercase().contains(&filter)
        })
        .collect();

    // `ORDER BY src, dst, table_name` — the only ordering `:8000` states.
    kept.sort_by(|a, b| (&a.src, &a.dst, &a.tables[0]).cmp(&(&b.src, &b.dst, &b.tables[0])));

    let total = kept.len() as i64;
    let offset = params.offset.unwrap_or(0).max(0) as usize;
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).max(0) as usize;
    let page: Vec<EdgeRow> = kept.into_iter().skip(offset).take(limit).collect();

    Ok(Json(json!({ "total": total, "rows": page })))
}

/// Every `(fileid, block_id, src_table, dst_table)` the fold recorded for the files in
/// scope, de-duplicated the way `SELECT DISTINCT` does — the store keeps one `edges` row
/// per lineage fact, and the same fact can be emitted twice for a statement that names a
/// table more than once.
pub fn block_flow_rows(
    conn: &duckdb::Connection,
    scope: &[String],
) -> Result<Vec<(String, String, String, String)>, duckdb::Error> {
    let in_scope: BTreeSet<&str> = scope.iter().map(|s| s.as_str()).collect();
    let mut seen: BTreeSet<(String, String, String, String)> = BTreeSet::new();
    let mut st = conn.prepare("SELECT fileid, block_id, src_table, dst_table FROM edges")?;
    let mut rows = st.query([])?;
    while let Some(r) = rows.next()? {
        let fileid: String = r.get(0)?;
        if !in_scope.contains(fileid.as_str()) {
            continue;
        }
        seen.insert((fileid, r.get(1)?, r.get(2)?, r.get(3)?));
    }
    Ok(seen.into_iter().collect())
}

/// `_provided_edges`: the engine's own view of the scope — every per-block flow, plus the
/// cross-file roll-up. Nothing human has touched it yet.
///
/// `block_rows` is `(fileid, block_id, src_table, dst_table)` straight off the store's
/// `edges` table — one row per flow the fold actually recorded, which is exactly what
/// `:8000`'s `BLOCK_FLOW` rows are. It is deliberately *not* re-derived as reads x writes
/// off `facts`: a block that writes a table its read side failed to fold contributes a
/// write to `facts` (so the file roll-up still sees it) but no flow, and inventing the
/// cross product would report a pair the engine never found.
pub fn provided_rows(
    block_rows: &[(String, String, String, String)],
    facts: &BTreeMap<(String, String), super::blocklinks::BlockFacts>,
) -> Vec<EdgeRow> {
    let mut out: Vec<EdgeRow> = Vec::new();

    for (fileid, block_id, src, dst) in block_rows {
        out.push(EdgeRow {
            fileid: fileid.clone(),
            block_id: Some(block_id.clone()),
            src: src.clone(),
            dst: dst.clone(),
            tables: vec![src.clone()],
            level: "block".into(),
            provenance: "fact".into(),
            freshness: "green".into(),
        });
    }

    // project level: writer file -> reader file, one row per table moved. Same rule as
    // `neighborhood::project_edges`, computed off the same facts.
    let mut writes_of_file: BTreeMap<&str, BTreeSet<&str>> = BTreeMap::new();
    let mut reads_of_file: BTreeMap<&str, BTreeSet<&str>> = BTreeMap::new();
    for ((fileid, _), f) in facts {
        for t in &f.writes {
            writes_of_file.entry(fileid).or_default().insert(t);
        }
        for t in &f.reads {
            reads_of_file.entry(fileid).or_default().insert(t);
        }
    }
    let mut writers: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    let mut readers: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for (fid, ts) in &writes_of_file {
        for t in ts {
            writers.entry(t).or_default().push(fid);
        }
    }
    for (fid, ts) in &reads_of_file {
        for t in ts {
            readers.entry(t).or_default().push(fid);
        }
    }
    for (table, ws) in &writers {
        let Some(rs) = readers.get(table) else { continue };
        for src in ws {
            for dst in rs {
                if src == dst {
                    continue;
                }
                out.push(EdgeRow {
                    fileid: (*src).to_string(),
                    block_id: None,
                    src: (*src).to_string(),
                    dst: (*dst).to_string(),
                    tables: vec![(*table).to_string()],
                    level: "project".into(),
                    provenance: "inferred".into(),
                    freshness: "green".into(),
                });
            }
        }
    }

    out
}

/// `_merged_edges`, the CTE, as three passes: drop what a `reject` removed, upgrade what a
/// `confirm` blessed, append what an `add`/`correct` asserted. An edit still
/// `requires_check` is skipped in all three — a re-parse moved the block it was pinned to,
/// so nobody has said yet that it still holds.
pub fn merge_human_edits(
    provided: Vec<EdgeRow>,
    human: &[inferred_duckdb::HumanEdit],
) -> Vec<EdgeRow> {
    let live = |e: &&inferred_duckdb::HumanEdit| !e.requires_check;

    let rejected: Vec<(&Option<String>, &str)> = human
        .iter()
        .filter(live)
        .filter(|e| e.action == "reject" && e.block_id.as_deref().is_some_and(|b| !b.is_empty()))
        .map(|e| (&e.fileid, e.block_id.as_deref().unwrap()))
        .collect();
    let confirmed: Vec<(&Option<String>, &str)> = human
        .iter()
        .filter(live)
        .filter(|e| e.action == "confirm" && e.block_id.as_deref().is_some_and(|b| !b.is_empty()))
        .map(|e| (&e.fileid, e.block_id.as_deref().unwrap()))
        .collect();

    // `c.fileid IS NULL OR c.fileid = provided.fileid`: an edit that names no file matches
    // that block id in any file.
    let hits = |pairs: &[(&Option<String>, &str)], row: &EdgeRow| -> bool {
        let Some(block_id) = row.block_id.as_deref() else { return false };
        pairs.iter().any(|(fileid, b)| {
            *b == block_id && fileid.as_ref().is_none_or(|f| f == &row.fileid)
        })
    };

    let mut out: Vec<EdgeRow> = provided
        .into_iter()
        .filter(|r| r.block_id.is_none() || !hits(&rejected, r))
        .map(|mut r| {
            if hits(&confirmed, &r) {
                r.provenance = "human_gold".into();
            }
            r
        })
        .collect();

    for e in human.iter().filter(live) {
        if e.action != "add" && e.action != "correct" {
            continue;
        }
        out.push(EdgeRow {
            fileid: e.fileid.clone().unwrap_or_else(|| e.src.clone()),
            block_id: e.block_id.clone().filter(|b| !b.is_empty()),
            src: e.src.clone(),
            dst: e.dst.clone(),
            tables: vec![e.table_name.clone()],
            level: e.level.clone(),
            provenance: "human_gold".into(),
            freshness: "green".into(),
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use inferred_duckdb::HumanEdit;

    fn row(fileid: &str, block: Option<&str>) -> EdgeRow {
        EdgeRow {
            fileid: fileid.into(),
            block_id: block.map(|b| b.into()),
            src: "work.a".into(),
            dst: "work.b".into(),
            tables: vec!["work.a".into()],
            level: "block".into(),
            provenance: "fact".into(),
            freshness: "green".into(),
        }
    }

    fn edit(action: &str, block_id: Option<&str>, requires_check: bool) -> HumanEdit {
        HumanEdit {
            edit_id: "e1".into(),
            edited_at: "2026-08-25 03:37:46".into(),
            editor: "web-ui".into(),
            action: action.into(),
            src: "a.sas".into(),
            dst: "b.sas".into(),
            table_name: "work.a".into(),
            level: "project".into(),
            comment: String::new(),
            block_id: block_id.map(|b| b.into()),
            requires_check,
            fileid: None,
            dismissed: false,
            freshness: "green".into(),
        }
    }

    #[test]
    fn reject_drops_that_block_confirm_upgrades_it() {
        let provided = vec![row("a.sas", Some("b_001")), row("a.sas", Some("b_002"))];
        let out = merge_human_edits(provided.clone(), &[edit("reject", Some("b_001"), false)]);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].block_id.as_deref(), Some("b_002"));

        let out = merge_human_edits(provided, &[edit("confirm", Some("b_001"), false)]);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].provenance, "human_gold");
        assert_eq!(out[1].provenance, "fact");
    }

    #[test]
    fn an_edit_that_requires_check_does_nothing_at_all() {
        let provided = vec![row("a.sas", Some("b_001"))];
        let out = merge_human_edits(provided, &[edit("reject", Some("b_001"), true), edit("add", None, true)]);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].provenance, "fact");
    }

    #[test]
    fn correct_appends_a_human_gold_row_and_leaves_the_engine_row_alone() {
        let provided = vec![row("a.sas", Some("b_001"))];
        let out = merge_human_edits(provided, &[edit("correct", None, false)]);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].provenance, "fact");
        assert_eq!(out[1].provenance, "human_gold");
        assert_eq!(out[1].level, "project");
        // `COALESCE(fileid, src)` — the edit names no file, so its src stands in
        assert_eq!(out[1].fileid, "a.sas");
    }
}
