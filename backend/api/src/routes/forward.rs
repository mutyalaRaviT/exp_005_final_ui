//! `forward` — the `/api/*` fallback for every route that has not landed.
//!
//! **Why this exists (Ruling 5, 2026-09-09, Task 5 fix round 1).** The plan and this
//! track's own Task 5 report both claimed `edges`, `blocklinks`, `file` and the rest of
//! `crate::ALL_ROUTES` minus `crate::LANDED` already forwarded to the Python oracles —
//! `crate::oracle::forward` existed for exactly that. It did, but nothing ever called it:
//! `app()` wired only `health`/`files`/`search`/`neighborhood`/`bench`, so any other
//! `/api/*` path fell through to axum's own 404. Since Task 4 pointed UI1's dev proxy at
//! this API, that 404 is a real regression: UI1 loses its edges drawer, block-links and
//! code pane, not just an unimplemented nicety.
//!
//! **Why a fallback, not nine more `.route()` lines.** Nothing here is "landing" a
//! route — the store answers none of these questions yet, and adding named routes for
//! them would make `tests/landed.rs` (which checks `LANDED` against what `app()` actually
//! wires) start asserting they *are* landed. A fallback on the whole router, scoped to
//! the `/api/` prefix by hand (axum's `.fallback()` is otherwise router-wide — it would
//! also swallow a typo'd `/bnech` and other genuinely-missing paths, which should stay a
//! real 404), forwards every one of those nine questions to `oracle_a` (UI1's backend;
//! `oracle_b`, the Bench, is unused here — no landed or forwarded `/api/*` route in this
//! API serves the Bench, which reads `/bench`'s own embedded page instead) without naming
//! any of them, so the list in `crate::ALL_ROUTES` stays the only place that enumerates
//! them.
//!
//! **Inputs → outputs.** any `/api/*` request whose path axum did not already match a
//! real route for → the same path and query string, forwarded to `oracle_a` verbatim, its
//! JSON body and status returned unchanged. A non-`/api/` path (or `/api/` itself)
//! is a real 404, not forwarded anywhere.

use crate::oracle;
use crate::types::AppState;
use axum::extract::State;
use axum::http::{StatusCode, Uri};
use axum::response::{IntoResponse, Json, Response};

pub async fn fallback(State(state): State<AppState>, uri: Uri) -> Response {
    let path = uri.path();
    if !path.starts_with("/api/") || path == "/api/" {
        return (StatusCode::NOT_FOUND, "not found").into_response();
    }
    let path_and_query = uri
        .path_and_query()
        .map(|pq| pq.as_str())
        .unwrap_or(path);
    let (status, body) = oracle::forward(&state.oracle_a, path_and_query).await;
    (status, Json(body)).into_response()
}
