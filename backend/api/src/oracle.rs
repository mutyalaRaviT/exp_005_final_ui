//! `oracle` — the scaffold, not the destination.
//!
//! **Why this exists.** A question is answered from the store only once its route has
//! landed. Until then this forwards it to the Python implementation being replaced and
//! translates the reply into canonical shape. The same translation is what
//! `tools/diff_route.py` compares against, so it is written once, here, and each arm is
//! deleted as its route lands. When this file is empty the slice is done.
//!
//! **Ruling 5 (2026-09-09, Task 5 fix round 1).** The plan and the Task 5 report both
//! claimed unlanded routes already forwarded to the Python oracles; nothing actually
//! called `forward()`. `app()`'s `/api/*` fallback (`routes::forward::fallback`) is the
//! first caller — see its doc comment for why the fallback, not per-route handlers.

use axum::http::StatusCode;
use serde_json::{json, Value};

/// Forward `path_and_query` (e.g. `"/api/edges?files=sas%2Fraw%2F..."`) to the Python
/// oracle at `base` and return its status and JSON body, translated 1:1 — nothing here
/// counts as "landing" a route; the store answers none of these.
///
/// GET-only by construction (`reqwest::get`) — its one caller, `routes::forward::fallback`,
/// rejects any other method before this is reached (Ruling 6), so this never needs a body
/// or a method parameter of its own.
///
/// Never leaks `base` (the oracle's own address) or any filesystem path into the
/// response: on any failure (connection refused, non-200, a body that isn't JSON) this
/// returns a short, generic body and `502 Bad Gateway`, and logs the real detail with
/// `eprintln!` instead — the same rule `routes::bench::unreadable_response` follows for
/// the same reason (a client has no business learning this machine's layout).
pub async fn forward(base: &str, path_and_query: &str) -> (StatusCode, Value) {
    let url = format!("{base}{path_and_query}");
    let resp = match reqwest::get(&url).await {
        Ok(r) => r,
        Err(e) => {
            eprintln!("oracle forward {url}: {e}");
            return (StatusCode::BAD_GATEWAY, json!({ "error": "oracle unreachable" }));
        }
    };
    let status = StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    match resp.json::<Value>().await {
        Ok(body) => (status, body),
        Err(e) => {
            eprintln!("oracle forward {url}: response body was not JSON: {e}");
            (StatusCode::BAD_GATEWAY, json!({ "error": "oracle returned a bad response" }))
        }
    }
}
