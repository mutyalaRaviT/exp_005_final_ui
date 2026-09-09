mod support;
use support::get;

#[tokio::test]
async fn health_reports_which_routes_have_landed() {
    let res = get("/api/health").await;
    assert_eq!(res["ok"], true);
    assert!(res["landed"].is_array());
    assert!(res["forwarded"].is_array());
    // Nothing has landed yet: every one of the twelve questions is still forwarded.
    assert_eq!(res["landed"].as_array().unwrap().len(), 0);
    assert_eq!(res["forwarded"].as_array().unwrap().len(), 12);
}
