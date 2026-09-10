//! Task 6b (M4a): `POST /api/convert` — the twelfth question, and the only one that
//! writes.
//!
//! **Why these tests drive one router twice by hand.** `support::post` opens a fresh
//! `test_state()` store per call, which is right for every read route and useless here:
//! idempotence is a statement about *the same store* seeing the same folder twice. So
//! these build one `AppState`, clone the router around it, and send two requests through
//! it — the second one's answer is the whole point.

mod support;
use axum::body::Body;
use axum::http::Request;
use http_body_util::BodyExt;
use serde_json::{json, Value};
use tower::ServiceExt;

/// One request against a router built from `state`, parsed as JSON. `Router` is `Clone`
/// and `oneshot` consumes a clone, so the state — and therefore the store — survives.
async fn post_to(state: &lineageq_api::AppState, path: &str, body: Value) -> (u16, Value) {
    let req = Request::builder()
        .method("POST")
        .uri(path)
        .header("content-type", "application/json")
        .body(Body::from(serde_json::to_vec(&body).expect("serialize body")))
        .expect("build POST");
    let res = lineageq_api::app(state.clone()).oneshot(req).await.expect("router call");
    let status = res.status().as_u16();
    let bytes = res.into_body().collect().await.expect("collect body").to_bytes();
    let v: Value = serde_json::from_slice(&bytes)
        .unwrap_or_else(|_| json!({ "raw": String::from_utf8_lossy(&bytes) }));
    (status, v)
}

/// A throwaway folder with `n` tiny SAS files in it, unique per test.
fn tmp_corpus(name: &str, n: usize) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("m4a_convert_{name}_{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("create tmp corpus");
    for i in 0..n {
        std::fs::write(
            dir.join(format!("t{i}.sas")),
            format!("data work.a{i};\n  set work.b{i};\nrun;\n"),
        )
        .expect("write tmp sas");
    }
    dir
}

/// The plan's own test (silver plan, Task 6b step 1), word for word in intent: a second
/// convert of an unchanged folder must write nothing. This needs `files.hash` to be
/// honoured; a `convert` that rewrote unconditionally would throw away the `runs` history
/// and, later, the human edits pinned to a `block_hash` (M7), for no reason at all.
#[tokio::test]
async fn convert_is_idempotent_over_http() {
    let dir = tmp_corpus("idem", 1);
    let state = lineageq_api::test_state();

    let (s1, r1) = post_to(&state, "/api/convert", json!({ "folder": dir.to_string_lossy() })).await;
    assert_eq!(s1, 200, "first convert: {r1}");
    assert_eq!(r1["ok"], 1);
    assert!(r1["blocks"].as_i64().unwrap() > 0, "first convert must write blocks: {r1}");

    let (s2, r2) = post_to(&state, "/api/convert", json!({ "folder": dir.to_string_lossy() })).await;
    assert_eq!(s2, 200, "second convert: {r2}");
    assert_eq!(r2["blocks"], 0, "second convert of an unchanged folder must write nothing");
    assert_eq!(r2["ok"], 1, "the file is still ok, it was simply skipped");

    let _ = std::fs::remove_dir_all(&dir);
}

/// A changed file must come back, or the store answers yesterday's questions forever.
/// This is the guard on the idempotence test above: without it, "writes 0 blocks" could be
/// met by a `convert` that never writes anything at all.
#[tokio::test]
async fn a_changed_file_is_reconverted() {
    let dir = tmp_corpus("changed", 1);
    let state = lineageq_api::test_state();
    let (_, r1) = post_to(&state, "/api/convert", json!({ "folder": dir.to_string_lossy() })).await;
    assert!(r1["blocks"].as_i64().unwrap() > 0);

    std::fs::write(dir.join("t0.sas"), "data work.z;\n  set work.y;\nrun;\n").unwrap();
    let (_, r2) = post_to(&state, "/api/convert", json!({ "folder": dir.to_string_lossy() })).await;
    assert!(
        r2["blocks"].as_i64().unwrap() > 0,
        "a file whose bytes changed must be folded again, not skipped: {r2}"
    );
    let _ = std::fs::remove_dir_all(&dir);
}

/// `{file}` is the other half of the shape the plan names, and it must reach the same
/// call — `collect_sas` already accepts a file as well as a directory.
#[tokio::test]
async fn a_single_file_converts_too() {
    let dir = tmp_corpus("single", 2);
    let state = lineageq_api::test_state();
    let (s, r) = post_to(
        &state,
        "/api/convert",
        json!({ "file": dir.join("t0.sas").to_string_lossy() }),
    )
    .await;
    assert_eq!(s, 200, "{r}");
    assert_eq!(r["files"], 1, "only the named file, not its neighbour: {r}");
    assert!(r["blocks"].as_i64().unwrap() > 0);
    let _ = std::fs::remove_dir_all(&dir);
}

/// The report is the `ConvertReport` shape the plan's interface line names, and it carries
/// `lock_ms` — how long every read waited on the store mutex, reported rather than hidden.
#[tokio::test]
async fn the_report_has_every_field_the_plan_names() {
    let dir = tmp_corpus("shape", 1);
    let state = lineageq_api::test_state();
    let (_, r) = post_to(&state, "/api/convert", json!({ "folder": dir.to_string_lossy() })).await;
    for k in ["files", "ok", "failed", "blocks", "node4", "edges", "fold_ms", "store_ms", "total_ms", "lock_ms"] {
        assert!(r.get(k).is_some(), "the report must carry {k}: {r}");
    }
    assert!(r["lock_ms"].as_f64().unwrap() >= r["total_ms"].as_f64().unwrap() - 1.0,
        "lock_ms covers the whole convert, so it cannot be shorter than total_ms: {r}");
    let _ = std::fs::remove_dir_all(&dir);
}

/// Bad input is a 400 with a sentence, not a 500 and not a silent no-op.
#[tokio::test]
async fn a_request_with_no_target_is_a_400() {
    let state = lineageq_api::test_state();
    let (s, _) = post_to(&state, "/api/convert", json!({})).await;
    assert_eq!(s, 400);
    let (s, _) = post_to(&state, "/api/convert", json!({ "folder": "  " })).await;
    assert_eq!(s, 400, "whitespace is not a folder");
    let (s, _) = post_to(&state, "/api/convert", json!({ "folder": "a", "file": "b" })).await;
    assert_eq!(s, 400, "folder and file together is a caller mistake, not a guess to make");
}

/// A path that is not there is a 404, not a 500 — the caller mistyped, the server is fine.
#[tokio::test]
async fn a_missing_path_is_a_404() {
    let state = lineageq_api::test_state();
    let (s, _) = post_to(
        &state,
        "/api/convert",
        json!({ "folder": "/no/such/folder/m4a" }),
    )
    .await;
    assert_eq!(s, 404);
}

/// Landing means the router serves it, not only that `LANDED` says so.
#[tokio::test]
async fn convert_is_landed_and_no_longer_forwarded() {
    assert!(lineageq_api::LANDED.contains(&"convert"));
    assert_eq!(
        lineageq_api::LANDED.len(),
        lineageq_api::ALL_ROUTES.len(),
        "Task 6b is the last route: all twelve questions are answered from the store"
    );
    let _ = support::closed_addr(); // keep the helper referenced; see support's doc comment
}
