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
//! real 404), forwards every one of those nine questions to `oracle_a` without naming any
//! of them, so the list in `crate::ALL_ROUTES` stays the only place that enumerates them.
//!
//! **Scope, corrected (Ruling 6, 2026-09-09, final review fix wave).** This fallback
//! serves exactly one job: UI1's unlanded `/api/*` GET questions (`edges`, `blocklinks`,
//! `file`, `source`, `blocks`, `tablegraph`, `story`, `run`, `convert`), forwarded to
//! `oracle_a`. It deliberately never touches `oracle_b`. The Bench is not reachable
//! through this door at all any more — `GET /bench` (`routes::bench`) 302s the browser to
//! `oracle_b`'s own origin, and from there every one of `bench.html`'s 13 distinct
//! `/api/*` calls (several of them POSTs, e.g. `/api/save`, `/api/run_block`,
//! `/api/exec`) goes straight to `oracle_b`, never through :8110. An earlier version of
//! this comment claimed "no landed or forwarded `/api/*` route in this API serves the
//! Bench" as if that were by design; it was actually a bug (this fallback dropped every
//! method to a GET, which would have silently mangled a forwarded Bench POST into a GET
//! against the wrong server). Ruling 6 makes the GET-only, oracle_a-only scope the actual
//! design instead of an accident, and the method check below makes a wrong call fail
//! loudly rather than mangling it.
//!
//! **Inputs → outputs.** any `/api/*` GET request whose path axum did not already match a
//! real route for → the same path and query string, forwarded to `oracle_a` verbatim, its
//! JSON body and status returned unchanged. A non-`/api/` path (or `/api/` itself) is a
//! real 404, not forwarded anywhere. Any non-GET method on an unlanded `/api/*` path is a
//! `405 Method Not Allowed` — this fallback has no oracle to send it to (oracle_a's
//! unlanded routes are all GETs; a POST/PUT/DELETE here is either a bug in the caller or,
//! most likely, a Bench request that has no business reaching this API at all) and must
//! never silently downgrade it to a GET against oracle_a.

use crate::oracle;
use crate::types::AppState;
use axum::extract::State;
use axum::http::{Method, StatusCode, Uri};
use axum::response::{IntoResponse, Json, Response};
use serde_json::json;

pub async fn fallback(State(state): State<AppState>, method: Method, uri: Uri) -> Response {
    let path = uri.path();
    if !path.starts_with("/api/") || path == "/api/" {
        return (StatusCode::NOT_FOUND, "not found").into_response();
    }
    if method != Method::GET {
        return (
            StatusCode::METHOD_NOT_ALLOWED,
            Json(json!({
                "error": "this fallback only forwards GET requests to oracle_a; \
                          the Bench's POST routes are served by oracle_b directly \
                          and never reach this API"
            })),
        )
            .into_response();
    }
    let path_and_query = uri
        .path_and_query()
        .map(|pq| pq.as_str())
        .unwrap_or(path);
    let (status, body) = oracle::forward(&state.oracle_a, path_and_query).await;
    (status, Json(body)).into_response()
}
