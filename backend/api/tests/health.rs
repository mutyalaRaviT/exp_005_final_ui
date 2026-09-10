mod support;
use support::get;

#[tokio::test]
async fn health_reports_which_routes_have_landed() {
    let res = get("/api/health").await;
    assert_eq!(res["ok"], true);
    assert!(res["landed"].is_array());
    assert!(res["forwarded"].is_array());
    // Task 5 landed `files`/`search`; Task 6 landed `neighborhood`; Task 7 landed
    // `blocklinks`/`edges` and Task 8 `source`: six of the twelve questions read the store
    // now, six are still forwarded. Each later route task bumps this pair by one as it lands.
    assert_eq!(res["landed"].as_array().unwrap().len(), 6);
    assert_eq!(res["forwarded"].as_array().unwrap().len(), 6);
}
