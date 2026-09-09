//! Ruling D6 (`.superpowers/sdd/silver_phase2_implementation_plan/progress.md`):
//! `LANDED` is only a reporting list — landing a route also needs a handler file and an
//! `app()` route-table edit, and nothing else keeps the three in sync. This asserts every
//! name in `LANDED` resolves to a route the router actually serves, and that no served
//! route is missing from `ALL_ROUTES`, so a route that is half-landed (in `LANDED` but not
//! wired, or wired but never added to `LANDED`) fails a test instead of `/api/health`
//! silently lying about it.

mod support;
use support::get;

#[tokio::test]
async fn landed_names_are_wired_and_only_landed_names_are_wired() {
    assert!(lineageq_api::LANDED.iter().all(|l| lineageq_api::ALL_ROUTES.contains(l)));
    for name in lineageq_api::ALL_ROUTES {
        let res = get(&format!("/api/{name}")).await;
        // Not wired into `app()` at all -> axum's own 404. Wired (whatever method it
        // really wants) -> anything else, a real handler answering or rejecting the GET.
        let wired = res.get("_status").and_then(|s| s.as_u64()) != Some(404);
        let should_be_wired = lineageq_api::LANDED.contains(name);
        assert_eq!(wired, should_be_wired, "{name}: LANDED says {should_be_wired} but router wired={wired}");
    }
}
