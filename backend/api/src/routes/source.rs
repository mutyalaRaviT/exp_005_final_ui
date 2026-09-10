//! `source` — `GET /api/source?fileid=`.
//!
//! **Why this exists.** `file()` (Task 9) deliberately returns *no* text: that is the whole
//! point of splitting the two, so opening a 1000-block file does not ship the file's source
//! and every block's SAS and PySpark in one payload (`docs/plan/bronze/bronze_perf_receipts_exp42.md`
//! — the 63.4 s open that this track exists to kill). Something still has to be able to hand
//! back a file's raw text — the code pane, a diff, an export — and that is this route, one
//! keyed read of `files.source`, the column `convert` already fills.
//!
//! **Wire shape.** `{"fileid": ..., "text": ..., "size": <bytes of text>}`. No brief states
//! one: Task 8 creates this file and never says what it returns, and `tools/diff_route.py`
//! records that gap explicitly (`ROUTES["source"].no_oracle`) rather than guessing a
//! comparison. This shape is the closest honest thing to the oracle candidate that note
//! names — the Bench's `GET /api/file?path=` -> `{path, text, size}` — with `fileid` in
//! place of `path`, because a fileid is what this store keys by and what every other route
//! here takes. `size` is `text.len()`, i.e. bytes, matching the Bench's own `size`.
//!
//! **Not wired into `diff_route.py`.** Extending that tool's route table is outside M1's
//! write scope, so `source` still reports "no oracle to check" there. Whoever gains that
//! scope should add the Bench comparison against this shape; until then this route's proof
//! is `tests/source.rs`, not the differential oracle.
//!
//! **Inputs → outputs.** `files.source` + a fileid → the file's text, or 404 if the store
//! has never seen that fileid.

use crate::types::AppState;
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};

#[derive(Deserialize)]
pub struct SourceParams {
    #[serde(default)]
    fileid: String,
}

pub async fn source(
    State(state): State<AppState>,
    Query(params): Query<SourceParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let fileid = params.fileid.trim();
    if fileid.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "source(): fileid is required".into()));
    }
    let conn = state.db.lock().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let text: Option<String> = conn
        .query_row("SELECT source FROM files WHERE fileid = ?", duckdb::params![fileid], |r| r.get(0))
        .optional_row()
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    // A fileid nobody converted and a fileid whose row has a NULL source are the same
    // answer to the asker: there is no text here.
    let Some(text) = text else {
        return Err((StatusCode::NOT_FOUND, format!("source(): no such fileid {fileid}")));
    };
    let size = text.len();
    Ok(Json(json!({ "fileid": fileid, "text": text, "size": size })))
}

/// `query_row` returns `QueryReturnedNoRows` for "no such fileid", which is not an error
/// here — it is the 404 answer. This turns that one variant into `None` and leaves every
/// other DuckDB error alone.
trait OptionalRow<T> {
    fn optional_row(self) -> Result<Option<T>, duckdb::Error>;
}

impl<T> OptionalRow<T> for Result<Option<T>, duckdb::Error> {
    fn optional_row(self) -> Result<Option<T>, duckdb::Error> {
        match self {
            Ok(v) => Ok(v),
            Err(duckdb::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e),
        }
    }
}
