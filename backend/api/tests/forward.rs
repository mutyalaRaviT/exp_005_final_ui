//! Ruling 5 (2026-09-09, Task 5 fix round 1): a non-landed `/api/*` path must be routed
//! to `routes::forward::fallback`, not answered by axum's own 404 — that 404 was the
//! actual regression (UI1 losing its edges drawer, block-links and code pane once Task 4
//! pointed its dev proxy at this API). `tests/landed.rs` already exercises every name in
//! `ALL_ROUTES` this way; this test exists separately so the fallback's wiring has its
//! own name and doesn't only prove itself as a side effect of the landed/not-landed
//! table.
//!
//! **Fix round 2 (2026-09-09): why `oracle_a` is forced to `support::closed_addr()`, not
//! left at the real default.** `127.0.0.1:8000` is a real, meaningful address here —
//! Ruling 1 exists precisely so this track's own oracle usually *does* listen there,
//! serving UI1's edges/blocklinks/file until phase C lands them. Round 1's version of this
//! test asserted `status == 502` against the *default* `oracle_a`, which only holds while
//! nothing answers on `8000` — the everyday, intended state (oracle up) made it fail. A
//! request the fallback forwards to a live server that answers with anything at all
//! (200, its own 404, whatever) is still proof the fallback was reached, but `502`
//! specifically is `oracle::forward`'s *unreachable* signal, so proving "the fallback was
//! reached" this way requires a forward that is guaranteed to fail — hence a deliberately
//! closed address, not whatever the machine happens to have open on `8000` right now.

mod support;
use support::{closed_addr, get_raw, get_raw_with_oracle_a};

#[tokio::test]
async fn a_non_landed_api_path_is_forwarded_not_404() {
    // "edges" is in `ALL_ROUTES`, not in `LANDED`, and has no `.route()` in `app()` —
    // the exact shape of route Ruling 5 fixes.
    assert!(!lineageq_api::LANDED.contains(&"edges"));

    let res = get_raw_with_oracle_a(&closed_addr(), "/api/edges?files=sas%2Fraw%2F11_branch_rollup.sas").await;

    assert_ne!(res.status, 404, "a non-landed /api/* path must not 404 — the fallback should have caught it");
    assert_eq!(res.status, 502, "oracle_a is a deliberately closed port, so the fallback's forward() must report it unreachable");
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
    // forwarded to an oracle that has no idea what it is. Doesn't touch oracle_a at all
    // (the fallback rejects it before ever calling `oracle::forward`), so the default
    // `test_state()` is fine here — nothing about this assertion depends on what, if
    // anything, is listening on `8000`.
    let res = get_raw("/not-an-api-path").await;
    assert_eq!(res.status, 404);
}
