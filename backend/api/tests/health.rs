mod support;
use support::get;

#[tokio::test]
async fn health_reports_which_routes_have_landed() {
    let res = get("/api/health").await;
    assert_eq!(res["ok"], true);
    assert!(res["landed"].is_array());
    assert!(res["forwarded"].is_array());
    // Task 5 landed `files`/`search`: two of the twelve questions read the store now, ten
    // are still forwarded.
    assert_eq!(res["landed"].as_array().unwrap().len(), 2);
    assert_eq!(res["forwarded"].as_array().unwrap().len(), 10);
}
