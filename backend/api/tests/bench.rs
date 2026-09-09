mod support;

/// Ruling 6 (2026-09-09, final review fix wave): `GET /bench` no longer serves the
/// Bench's HTML from :8110 — it redirects to wherever `oracle_b` (the Bench's own
/// server) actually serves `/bench`, using the address already in `AppState` rather than
/// a hardcoded `:8042`. `test_state()` defaults `oracle_b` to `http://127.0.0.1:8042`
/// (see `lib.rs`), so that is what the Location header must point at here.
#[tokio::test]
async fn bench_redirects_to_oracle_b() {
    let res = support::get_raw("/bench").await;
    assert!(
        (300..400).contains(&res.status),
        "expected a redirect, got {}",
        res.status
    );
    assert_eq!(
        res.location.as_deref(),
        Some("http://127.0.0.1:8042/bench"),
        "Location must point at oracle_b's own /bench, not a served page"
    );
}
