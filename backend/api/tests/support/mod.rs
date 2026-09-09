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

async fn send(req: Request<Body>) -> Value {
    let app = lineageq_api::app(lineageq_api::test_state());
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
