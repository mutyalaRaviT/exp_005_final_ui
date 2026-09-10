//! `story` — `GET /api/story?table=`.
//!
//! **Why this exists.** The question a person asks about a table they do not trust is not
//! "what does this file do" (that is `tablegraph`) but *who made this, and in what order?* —
//! and the answer crosses files, so it cannot be a per-file read. This is the store's answer:
//! every block anywhere in it that writes the named table, in run order.
//!
//! **Wire shape** (plan §6, Task 10 brief): `{makers: [{fileid, block_id, n}]}` in run order.
//! `n` is the block's 0-based position in its own file — the order the program runs — and the
//! ordering is joined back from `blocks`, because the `edges` table carries no order of its
//! own. `tools/diff_route.py` deliberately keeps `makers` out of its order-blind field list so
//! a regression to insertion order cannot pass unnoticed.
//!
//! **No oracle.** The Bench has no story surface at all — no route of its takes a table name
//! — so there is nothing to diff against, and `diff_route.py` says so rather than inventing a
//! comparison (`ROUTES["story"].no_oracle`). This route's proof is `tests/tablegraph.rs` plus
//! the hand-traced ledger row.
//!
//! **Inputs → outputs.** `edges` joined to `blocks` + a table name → its makers, oldest run
//! first; an empty list when nothing makes it, which is a real answer, not an error.

use crate::types::AppState;
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};

#[derive(Deserialize)]
pub struct StoryParams {
    #[serde(default)]
    table: String,
}

pub async fn story(
    State(state): State<AppState>,
    Query(params): Query<StoryParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let table = params.table.trim().to_string();
    if table.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "story(): table is required".into()));
    }
    let conn = state
        .db
        .lock()
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let makers = inferred_duckdb::story(&conn, &table)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    drop(conn);
    Ok(Json(json!({ "table": table, "makers": makers })))
}
