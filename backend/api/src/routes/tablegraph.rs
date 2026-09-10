//! `tablegraph` — `GET /api/tablegraph?fileid=`.
//!
//! **Why this exists.** UI2's second pane: inside one file, which tables exist and which
//! statement moved data from one to the next. It is the same `edges` facts `edges()` pages
//! through at project scope, read at the scope a person reading one program cares about.
//!
//! **Wire shape** (plan §6, Task 10 brief): `{tables: [{name, kind, block_id}],
//! edges: [{src, dst, kind, block_id}]}`.
//!
//! **`kind` on an edge** is the store's own `edges.kind` — `ds` for a dataset flow, `ctl` for
//! a control/conditional one — the same two the Bench's `ds_lineage` / `ctl_lineage` fact
//! lists carry.
//!
//! **`kind` on a table** is `source` for a table this file never writes and `derived` for one
//! it does. The plan names the field and nothing states its vocabulary; this is the smallest
//! honest thing the store can prove about a table (it either has a maker in this file or it
//! does not), and it is what the owner's Bench screenshot lays out left to right — the
//! sources on the left, everything derived to the right of them. `tools/diff_route.py`
//! projects it off both sides: the Bench's lineage facts carry no per-table classification
//! at all, so there is nothing to check it against, and inventing a comparison would be
//! worse than admitting the gap.
//!
//! **`block_id` on a table** is the block that writes it — the first one, in run order, when
//! more than one does — and null for a source.
//!
//! **Inputs → outputs.** `edges` + `blocks` + a fileid → the file's table graph.

use crate::types::AppState;
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Deserialize)]
pub struct TableGraphParams {
    #[serde(default)]
    fileid: String,
}

pub async fn tablegraph(
    State(state): State<AppState>,
    Query(params): Query<TableGraphParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let fileid = params.fileid.trim().to_string();
    if fileid.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "tablegraph(): fileid is required".into()));
    }
    let ise = |e: String| (StatusCode::INTERNAL_SERVER_ERROR, e);
    let conn = state.db.lock().map_err(|e| ise(e.to_string()))?;

    let mut st = conn
        .prepare(
            "SELECT e.src_table, e.dst_table, e.kind, e.block_id, b.n
             FROM edges e LEFT JOIN blocks b ON b.fileid = e.fileid AND b.block_id = e.block_id
             WHERE e.fileid = ?
             ORDER BY b.n, e.src_table, e.dst_table",
        )
        .map_err(|e| ise(e.to_string()))?;
    let mut rows = st.query(duckdb::params![&fileid]).map_err(|e| ise(e.to_string()))?;

    let mut edges: Vec<Value> = Vec::new();
    let mut names: BTreeSet<String> = BTreeSet::new();
    // first maker in run order wins, so a table rebuilt twice still names where it began
    let mut maker: BTreeMap<String, String> = BTreeMap::new();
    while let Some(r) = rows.next().map_err(|e| ise(e.to_string()))? {
        let src: String = r.get(0).map_err(|e| ise(e.to_string()))?;
        let dst: String = r.get(1).map_err(|e| ise(e.to_string()))?;
        let kind: String = r.get(2).map_err(|e| ise(e.to_string()))?;
        let block_id: String = r.get(3).map_err(|e| ise(e.to_string()))?;
        names.insert(src.clone());
        names.insert(dst.clone());
        maker.entry(dst.clone()).or_insert_with(|| block_id.clone());
        edges.push(json!({ "src": src, "dst": dst, "kind": kind, "block_id": block_id }));
    }
    drop(rows);
    drop(st);
    drop(conn);

    let tables: Vec<Value> = names
        .iter()
        .map(|n| {
            json!({
                "name": n,
                "kind": if maker.contains_key(n) { "derived" } else { "source" },
                "block_id": maker.get(n),
            })
        })
        .collect();

    Ok(Json(json!({ "tables": tables, "edges": edges })))
}
