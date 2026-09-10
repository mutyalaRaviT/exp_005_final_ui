//! `support` — in-process HTTP test helpers.
//!
//! **Why this exists.** Eight later tasks (5–12) write route tests that call bare
//! `get(path)` / `post(path, body)` and expect JSON back. The plan never defines these
//! (Task 3 ruling D1); they live here, once, so every later task's tests compile as
//! written.
//!
//! **Why in-process.** Both helpers drive `lineageq_api::app` directly with
//! `tower::ServiceExt::oneshot` — no `TcpListener::bind`, no port at all. The machine
//! this runs on has long-running servers on 5173, 5174, 5175, 8000, 8042 and 8043; a test
//! that bound a port could collide with one of those or, worse, silently read its
//! response instead of the router's. Each call opens a fresh `test_state()` store, so
//! tests never share state through the filesystem either.
//!
//! **`closed_addr` and `get_raw_with_oracle_a` (Ruling 5 fix round 2, 2026-09-09).** The
//! router itself never binds a port, but `routes::forward::fallback` makes a *real*
//! outbound HTTP call to `oracle_a` — and `8000` is a real, meaningful address here
//! (Ruling 1's oracle usually lives there), not a made-up default. A test asserting what
//! happens when the fallback's forward fails must not depend on that port happening to be
//! empty on whichever machine runs the suite; `closed_addr()` hands out an address
//! guaranteed refused (bind an ephemeral port, read it, drop the listener immediately —
//! nothing is listening on it a moment later) and `get_raw_with_oracle_a` drives the
//! router with that address as `oracle_a` instead of the real default.

use axum::body::Body;
use axum::http::Request;
use http_body_util::BodyExt;
use serde_json::Value;
use tower::ServiceExt;

pub async fn get(path: &str) -> Value {
    let req = Request::builder()
        .method("GET")
        .uri(path)
        .body(Body::empty())
        .expect("build GET request");
    send(req).await
}

/// Like `get`, but against a store seeded from `corpus/fixtures` — the exp_42 receipt file
/// the in-file questions (`file`, `blocks`, `tablegraph`, `story`) are checked against.
/// Task 9's own store, for the reason `lineageq_api::test_state_fixtures` gives: the
/// fixture cannot go into `test_state()` without changing what `/api/files` counts.
pub async fn get_fixtures(path: &str) -> Value {
    let req = Request::builder()
        .method("GET")
        .uri(path)
        .body(Body::empty())
        .expect("build GET request");
    send_with_state(lineageq_api::test_state_fixtures(), req).await
}

/// `get_raw`, against the fixtures store.
pub async fn get_raw_fixtures(path: &str) -> RawRes {
    get_raw_with_state(lineageq_api::test_state_fixtures(), path).await
}

pub async fn post(path: &str, body: Value) -> Value {
    let req = Request::builder()
        .method("POST")
        .uri(path)
        .header("content-type", "application/json")
        .body(Body::from(
            serde_json::to_vec(&body).expect("serialize request body"),
        ))
        .expect("build POST request");
    send(req).await
}

pub struct RawRes {
    pub status: u16,
    pub content_type: String,
    pub location: Option<String>,
    pub body: String,
}

/// Like `get`, but keeps the bytes and the content type instead of parsing JSON — the
/// Bench page is HTML, not an answer.
pub async fn get_raw(path: &str) -> RawRes {
    get_raw_with_state(lineageq_api::test_state(), path).await
}

/// Like `get_raw`, but drives the router with `oracle_a` overridden — for a test that
/// needs the `/api/*` fallback's forward attempt to fail deterministically. Pass
/// `closed_addr()` for "guaranteed connection-refused, on any machine".
pub async fn get_raw_with_oracle_a(oracle_a: &str, path: &str) -> RawRes {
    get_raw_with_state(lineageq_api::test_state_with_oracle_a(oracle_a.to_string()), path).await
}

async fn get_raw_with_state(state: lineageq_api::AppState, path: &str) -> RawRes {
    let req = Request::builder()
        .method("GET")
        .uri(path)
        .body(Body::empty())
        .expect("build GET request");
    let app = lineageq_api::app(state);
    let res = app.oneshot(req).await.expect("router call");
    let status = res.status().as_u16();
    let content_type = res
        .headers()
        .get(axum::http::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_string();
    let location = res
        .headers()
        .get(axum::http::header::LOCATION)
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_string());
    let bytes = res
        .into_body()
        .collect()
        .await
        .expect("read response body")
        .to_bytes();
    RawRes {
        status,
        content_type,
        location,
        body: String::from_utf8_lossy(&bytes).to_string(),
    }
}

/// An address nothing is listening on, on any machine: bind an ephemeral port (the OS
/// picks one that is currently free), read it back, then drop the listener — freeing the
/// port again immediately, before anything can be sent to it. A test that forwards here
/// gets a deterministic connection-refused, unlike a fixed port that might genuinely be
/// serving something real on a given dev machine (see this module's doc comment).
pub fn closed_addr() -> String {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("bind an ephemeral port");
    let port = listener.local_addr().expect("read the assigned port").port();
    drop(listener);
    format!("http://127.0.0.1:{port}")
}

async fn send(req: Request<Body>) -> Value {
    send_with_state(lineageq_api::test_state(), req).await
}

async fn send_with_state(state: lineageq_api::AppState, req: Request<Body>) -> Value {
    let app = lineageq_api::app(state);
    let res = app.oneshot(req).await.expect("router call");
    let status = res.status();
    let bytes = res
        .into_body()
        .collect()
        .await
        .expect("read response body")
        .to_bytes();
    if bytes.is_empty() {
        return serde_json::json!({ "_status": status.as_u16() });
    }
    serde_json::from_slice(&bytes).unwrap_or_else(|_| {
        serde_json::json!({
            "_status": status.as_u16(),
            "_raw": String::from_utf8_lossy(&bytes).to_string(),
        })
    })
}
