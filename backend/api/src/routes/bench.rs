//! `GET /bench` — UI2's page, served from the API's own origin.
//!
//! **Why here.** bench.html fetches relative `/api/...`. Served from :8042 those calls hit
//! the Python server; served from :8110 they hit this API, which answers what it has landed
//! and forwards the rest to the oracles. So this one route is what puts UI2 behind the same
//! door as UI1, with no change to the 1,300-line page itself.
//!
//! **Inputs → outputs.** no inputs → the bytes of raw/bench_stack/server/bench.html.
//!
//! Read at request time, not baked in with `include_str!`: the page is still being edited
//! in its own track, and a stale copy compiled into the binary would be a confusing lie.

use axum::http::{header, StatusCode};
use axum::response::IntoResponse;

const BENCH_HTML: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../raw/bench_stack/server/bench.html"
);

pub async fn bench() -> impl IntoResponse {
    match std::fs::read_to_string(BENCH_HTML) {
        Ok(body) => (
            StatusCode::OK,
            [
                (header::CONTENT_TYPE, "text/html; charset=utf-8"),
                (header::CACHE_CONTROL, "no-store"),
            ],
            body,
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("bench.html unreadable at {BENCH_HTML}: {e}"),
        )
            .into_response(),
    }
}
