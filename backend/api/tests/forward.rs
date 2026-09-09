//! Ruling 5 (2026-09-09, Task 5 fix round 1): a non-landed `/api/*` path must be routed
//! to `routes::forward::fallback`, not answered by axum's own 404 — that 404 was the
//! actual regression (UI1 losing its edges drawer, block-links and code pane once Task 4
//! pointed its dev proxy at this API). `tests/landed.rs` already exercises every name in
//! `ALL_ROUTES` this way; this test exists separately so the fallback's wiring has its
//! own name and doesn't only prove itself as a side effect of the landed/not-landed
//! table.
//!
//! No oracle runs in this test process (`support`'s own doc comment: in-process only, no
//! `TcpListener::bind`), so the fallback's forward to `oracle_a` (`127.0.0.1:8000`) is
//! expected to fail with connection-refused — that failure, translated to `502 Bad
//! Gateway` by `oracle::forward`, is exactly the proof this test wants: not a 404 (the
//! bug), and specifically the fallback's own unreachable-oracle status (not some other
//! failure shape), which only a request that actually reached the fallback can produce.

mod support;
use support::get_raw;

#[tokio::test]
async fn a_non_landed_api_path_is_forwarded_not_404() {
    // "edges" is in `ALL_ROUTES`, not in `LANDED`, and has no `.route()` in `app()` —
    // the exact shape of route Ruling 5 fixes.
    assert!(!lineageq_api::LANDED.contains(&"edges"));

    let res = get_raw("/api/edges?files=sas%2Fraw%2F11_branch_rollup.sas").await;

    assert_ne!(res.status, 404, "a non-landed /api/* path must not 404 — the fallback should have caught it");
    assert_eq!(res.status, 502, "no oracle runs in tests, so the fallback's forward() must report it unreachable");
    assert!(
        res.body.contains("oracle unreachable"),
        "the fallback's failure body should say so in a short, generic way, not leak a URL or path: {}",
        res.body
    );
}

#[tokio::test]
async fn an_unrelated_unmatched_path_still_gets_a_real_404() {
    // The fallback is confined to `/api/` by hand (axum's own `.fallback()` is otherwise
    // router-wide) — a typo'd or unrelated path must stay a genuine 404, not get
    // forwarded to an oracle that has no idea what it is.
    let res = get_raw("/not-an-api-path").await;
    assert_eq!(res.status, 404);
}
