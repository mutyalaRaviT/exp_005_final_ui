//! Ruling D6 (`.superpowers/sdd/silver_phase2_implementation_plan/progress.md`):
//! `LANDED` is only a reporting list — landing a route also needs a handler file and an
//! `app()` route-table edit, and nothing else keeps the three in sync. This asserts every
//! name in `LANDED` resolves to a route the router actually serves, and that no served
//! route is missing from `ALL_ROUTES`, so a route that is half-landed (in `LANDED` but not
//! wired, or wired but never added to `LANDED`) fails a test instead of `/api/health`
//! silently lying about it.
//!
//! **Ruling 5 (2026-09-09, Task 5 fix round 1) changed the discriminator.** Before the
//! `/api/*` fallback existed, a name with no route got axum's own 404 and a landed name
//! got anything else — a clean signal. Now every `/api/{name}` matches *something*: a
//! landed name hits its own handler, and every other name falls through to
//! `routes::forward::fallback`, which (no oracle running in tests) always comes back
//! `502 Bad Gateway` — see `oracle::forward`. So the new signal is "did the fallback
//! answer this", not "was this 404" — `get_raw` (not `get`) is used here because that
//! signal lives in the real HTTP status, and the fallback's body is valid JSON (unlike
//! axum's old empty-bodied 404), so `support::get`'s `_status`-on-empty-body trick no
//! longer fires for it.

mod support;
use support::get_raw;

#[tokio::test]
async fn landed_names_are_wired_and_only_landed_names_are_wired() {
    assert!(lineageq_api::LANDED.iter().all(|l| lineageq_api::ALL_ROUTES.contains(l)));
    for name in lineageq_api::ALL_ROUTES {
        let res = get_raw(&format!("/api/{name}")).await;
        // 502 is `oracle::forward`'s own unreachable-oracle signal (no oracle runs in
        // tests) — a landed name is answered by its own handler and must never produce
        // it; every other name has no handler of its own, so it always falls through to
        // the fallback and always does.
        let via_fallback = res.status == 502;
        let should_be_landed = lineageq_api::LANDED.contains(name);
        assert_eq!(
            !via_fallback, should_be_landed,
            "{name}: LANDED says {should_be_landed} but via_fallback={via_fallback} (status {})",
            res.status
        );
    }
}
