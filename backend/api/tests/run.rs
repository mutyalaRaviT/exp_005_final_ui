//! Task 12's end-to-end test: one block, both sides, a real verdict.
//!
//! **Why one block and not eleven here.** Each block costs a cold Spark JVM (~4.5 s
//! measured), so the whole file is a minute — that belongs in the pass-mark curl loop
//! (task-12-brief step 5), not in `cargo test`, which route tasks run on every change.
//! `b_003` is the brief's own choice: `sales.total_sales`, a PROC SQL aggregate over one
//! generated input, the smallest block that is not trivially empty.
//!
//! **What the two timing assertions are for.** They are not performance targets; they are
//! how this test knows *both* engines really ran. A left side that quietly returned a
//! cached answer would come back in ~0 ms, and a right side that never started Spark
//! cannot take a second — a JVM start is the one thing that cannot be faked cheaply. Both
//! bounds are the brief's, unedited (Ruling D13).

mod support;
use serde_json::json;
use support::post_fixtures;

#[tokio::test]
async fn one_block_runs_both_ways_and_matches() {
    let r = post_fixtures(
        "/api/run",
        json!({"fileid":"test_vishnu_testdata_fixed.sas", "block_id":"b_003", "engine":"rust"}),
    )
    .await;
    assert_eq!(r["match"], "match", "b_003 verdict (full answer: {r})");
    assert!(
        r["left_ms"].as_f64().unwrap() < 100.0,
        "rust interp should be ~8 ms, got {}",
        r["left_ms"]
    );
    assert!(
        r["right_ms"].as_f64().unwrap() > 1000.0,
        "spark carries a JVM start, got {}",
        r["right_ms"]
    );
}

/// A block that creates no table is a normal answer, not an error and not a 500 — the
/// `never 500, never hang` half of the brief. `b_001` is the fixture's LIBNAME.
#[tokio::test]
async fn a_block_that_creates_nothing_answers_rather_than_failing() {
    let r = post_fixtures(
        "/api/run",
        json!({"fileid":"test_vishnu_testdata_fixed.sas", "block_id":"b_001", "engine":"rust"}),
    )
    .await;
    assert_eq!(r["match"], "no inputs", "full answer: {r}");
    assert!(r["tables"].as_array().unwrap().is_empty());
}

/// An engine name nobody implements is rejected at the door, with the two that exist
/// named — not silently defaulted to `rust`, which would let a UI3 sweep believe it had an
/// independent left side when it had Rust checking its own homework (gold §5, Decision D6).
#[tokio::test]
async fn an_unknown_engine_is_a_bad_request() {
    let r = post_fixtures(
        "/api/run",
        json!({"fileid":"test_vishnu_testdata_fixed.sas", "block_id":"b_003", "engine":"julia"}),
    )
    .await;
    assert_eq!(r["_status"], 400, "full answer: {r}");
}

/// A fileid the store never converted is a 404, not a panic on `None`.
#[tokio::test]
async fn an_unknown_fileid_is_not_found() {
    let r = post_fixtures(
        "/api/run",
        json!({"fileid":"nope.sas", "block_id":"b_003", "engine":"rust"}),
    )
    .await;
    assert_eq!(r["_status"], 404, "full answer: {r}");
}
