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

/// Builds the response for a read failure. The absolute path and the `io::Error` go to the
/// server log — whoever runs the binary can still diagnose it — but never into the HTTP
/// body: a client-facing error page has no business naming this machine's filesystem
/// layout. Split out as its own function (rather than inlined in the `match`) so the body
/// it returns can be asserted on directly, without needing to make the real file read fail.
pub fn unreadable_response(e: &std::io::Error) -> (StatusCode, &'static str) {
    eprintln!("bench.html unreadable at {BENCH_HTML}: {e}");
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        "bench.html could not be read; see the server log",
    )
}

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
        Err(e) => unreadable_response(&e).into_response(),
    }
}
