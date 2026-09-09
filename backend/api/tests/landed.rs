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
//! `routes::forward::fallback`, which forwards to `oracle_a` and returns whatever that
//! gives back — `502 Bad Gateway` (`oracle::forward`'s own signal) only when the forward
//! itself fails to reach anything.
//!
//! **Fix round 2 (2026-09-09): why `oracle_a` is forced to `support::closed_addr()`.**
//! Round 1's version of this test left `oracle_a` at its real default, `127.0.0.1:8000` —
//! reasoning "no oracle runs in tests". That is false on any machine actually living
//! under Ruling 1, where this track's own oracle usually *does* listen there. With a real
//! oracle up, a forwarded non-landed name could come back `200`, its own `404`, `422`, or
//! anything else that server chooses to answer with — none of that is `502`, so
//! `via_fallback` would read `false` for a name that in fact went through the fallback,
//! and the assertion below would fail for exactly the routes it exists to check. Forcing
//! `oracle_a` to a deliberately closed port makes the forward attempt fail the same way
//! on every machine, so `502` is a reliable "went through the fallback" signal regardless
//! of what else is running.

mod support;
use support::{closed_addr, get_raw_with_oracle_a};

#[tokio::test]
async fn landed_names_are_wired_and_only_landed_names_are_wired() {
    assert!(lineageq_api::LANDED.iter().all(|l| lineageq_api::ALL_ROUTES.contains(l)));
    let oracle_a = closed_addr();
    for name in lineageq_api::ALL_ROUTES {
        let res = get_raw_with_oracle_a(&oracle_a, &format!("/api/{name}")).await;
        // 502 is `oracle::forward`'s own unreachable-oracle signal, deterministic here
        // because `oracle_a` is a port nothing is listening on — a landed name is
        // answered by its own handler and must never produce it; every other name has no
        // handler of its own, so it always falls through to the fallback and always does.
        let via_fallback = res.status == 502;
        let should_be_landed = lineageq_api::LANDED.contains(name);
        assert_eq!(
            !via_fallback, should_be_landed,
            "{name}: LANDED says {should_be_landed} but via_fallback={via_fallback} (status {})",
            res.status
        );
    }
}
