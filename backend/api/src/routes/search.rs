//! `search` — `GET /api/search?q=`.
//!
//! **Why this exists.** UI1's typeahead. `:8000` (`indexer.py::suggest`) answers it from a
//! `mentions` index — a cheap regex scan of every `x.y`-shaped token in every file's raw
//! text, tables and stray column refs alike. This store has no such index and, per Ruling
//! D8 (`.superpowers/sdd/silver_phase2_implementation_plan/progress.md`), does not grow
//! one — `table_refs` is a later slice's table, not phase 2's. Search here is answer
//! quality over what phase 2 *does* have: `tables` (every table a block writes) and
//! `edges` (every table a block reads or writes, with the fileid), plus `files` for the
//! filename half of a hit. A table hit's `files` list is every file the table appears in
//! on either side of `edges`, unioned with `tables.first_writer_fileid` — `edges` alone
//! would miss a table that is written once and never read again by anything folded so
//! far, and `first_writer_fileid` alone would miss every downstream reader (the
//! `work.fx_rates` example in the Task 5 brief: written by `06_seed_fx_rates.sas`, read by
//! `07_enrich_fx.sas` — a search must return both).
//!
//! **Ranking.** Mirrors `:8000`'s `suggest()` exactly: exact match, then prefix, then
//! substring; ties broken to the hit named in more files; a table whose qualifier is a
//! single letter (`a.cust_id` — almost always a SQL alias the cheap scan picked up, not a
//! real table) is demoted below every real hit rather than dropped. Candidate pools are
//! capped at `SUGGEST_CANDIDATES` before ranking and the final list at `SUGGEST_LIMIT`,
//! the same two numbers `:8000` uses (`indexer.py`'s `_SUGGEST_CANDIDATES` /
//! `_SUGGEST_LIMIT`), so a query neither side has any real hits for still degrades the
//! same way.
//!
//! **Inputs → outputs.** `tables`, `edges`, `files` + a query string ->
//! `{"hits": [{"kind", "value", "files"}, ...]}`.

use crate::types::{AppState, SearchHit};
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

const SUGGEST_CANDIDATES: usize = 200;
const SUGGEST_LIMIT: usize = 20;

#[derive(Deserialize)]
pub struct SearchParams {
    #[serde(default)]
    q: String,
}

pub async fn search(
    State(state): State<AppState>,
    Query(params): Query<SearchParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let q = params.q.trim().to_lowercase();
    if q.is_empty() {
        return Ok(Json(json!({ "hits": Vec::<SearchHit>::new() })));
    }

    let conn = state.db.lock().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let ise = |e: duckdb::Error| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string());

    // table_name -> every fileid it appears in, either side.
    let mut table_files: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    {
        let mut st = conn
            .prepare("SELECT name, first_writer_fileid FROM tables")
            .map_err(ise)?;
        let mut rows = st.query([]).map_err(ise)?;
        while let Some(r) = rows.next().map_err(ise)? {
            let name: String = r.get(0).map_err(ise)?;
            let writer: String = r.get(1).map_err(ise)?;
            let e = table_files.entry(name).or_default();
            if !writer.is_empty() {
                e.insert(writer);
            }
        }
    }
    {
        let mut st = conn
            .prepare("SELECT src_table, dst_table, fileid FROM edges")
            .map_err(ise)?;
        let mut rows = st.query([]).map_err(ise)?;
        while let Some(r) = rows.next().map_err(ise)? {
            let src: String = r.get(0).map_err(ise)?;
            let dst: String = r.get(1).map_err(ise)?;
            let fileid: String = r.get(2).map_err(ise)?;
            table_files.entry(src).or_default().insert(fileid.clone());
            table_files.entry(dst).or_default().insert(fileid);
        }
    }

    // basename -> every fileid with that basename.
    let mut name_files: BTreeMap<String, Vec<String>> = BTreeMap::new();
    {
        let mut st = conn.prepare("SELECT fileid FROM files ORDER BY fileid").map_err(ise)?;
        let mut rows = st.query([]).map_err(ise)?;
        while let Some(r) = rows.next().map_err(ise)? {
            let fileid: String = r.get(0).map_err(ise)?;
            let label = fileid.rsplit('/').next().unwrap_or(&fileid).to_string();
            name_files.entry(label).or_default().push(fileid);
        }
    }
    drop(conn);

    // candidates, ranked-before-capped exactly like `:8000`: sorted, then LIMIT
    // SUGGEST_CANDIDATES, then a `files` list is only built for the survivors.
    let mut table_candidates: Vec<&String> =
        table_files.keys().filter(|n| n.to_lowercase().contains(&q)).collect();
    table_candidates.sort();
    table_candidates.truncate(SUGGEST_CANDIDATES);

    let mut name_candidates: Vec<&String> =
        name_files.keys().filter(|n| n.to_lowercase().contains(&q)).collect();
    name_candidates.sort();
    name_candidates.truncate(SUGGEST_CANDIDATES);

    let mut hits: Vec<SearchHit> = Vec::new();
    for name in table_candidates {
        let mut files: Vec<String> = table_files[name].iter().cloned().collect();
        files.sort();
        hits.push(SearchHit { kind: "table", value: name.clone(), files });
    }
    for name in name_candidates {
        let mut files = name_files[name].clone();
        files.sort();
        hits.push(SearchHit { kind: "file", value: name.clone(), files });
    }

    hits.sort_by(|a, b| rank_key(a, &q).cmp(&rank_key(b, &q)));
    hits.truncate(SUGGEST_LIMIT);

    Ok(Json(json!({ "hits": hits })))
}

/// `(alias_demoted, exactness, -files.len(), kind, value)` — the exact tuple
/// `:8000`'s `suggest()` sorts hits by (`indexer.py:278-283`), so ties resolve the same
/// way: an alias-shaped table (single-letter qualifier) always sorts after a real hit;
/// among the rest, exact match beats prefix beats substring; then the hit named in more
/// files; then `"file"` before `"table"` (plain string order); then the value itself.
fn rank_key(h: &SearchHit, q: &str) -> (u8, u8, i64, &'static str, String) {
    let value_l = h.value.to_lowercase();
    let alias = if h.kind == "table" {
        let qualifier = value_l.split('.').next().unwrap_or("");
        u8::from(qualifier.chars().count() == 1)
    } else {
        0
    };
    let exactness = if value_l == q {
        0
    } else if value_l.starts_with(q) {
        1
    } else {
        2
    };
    (alias, exactness, -(h.files.len() as i64), h.kind, value_l)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hit(kind: &'static str, value: &str, n_files: usize) -> SearchHit {
        SearchHit { kind, value: value.to_string(), files: vec!["x".to_string(); n_files] }
    }

    #[test]
    fn exact_match_beats_prefix_beats_substring() {
        let mut hits = vec![
            hit("table", "work.fxx", 1),
            hit("table", "work.fx", 1),
            hit("table", "work.afx", 1),
        ];
        hits.sort_by(|a, b| rank_key(a, "work.fx").cmp(&rank_key(b, "work.fx")));
        assert_eq!(hits[0].value, "work.fx");
    }

    #[test]
    fn a_single_letter_qualifier_is_demoted_below_a_real_table() {
        let mut hits = vec![hit("table", "a.cust_id", 5), hit("table", "work.customers", 1)];
        hits.sort_by(|a, b| rank_key(a, "cust").cmp(&rank_key(b, "cust")));
        assert_eq!(hits[0].value, "work.customers");
    }

    #[test]
    fn ties_break_to_more_files() {
        let mut hits = vec![hit("table", "work.a", 1), hit("table", "work.b", 3)];
        hits.sort_by(|a, b| rank_key(a, "work").cmp(&rank_key(b, "work")));
        assert_eq!(hits[0].value, "work.b");
    }
}
