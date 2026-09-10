mod support;
use support::get;

#[tokio::test]
async fn health_reports_which_routes_have_landed() {
    let res = get("/api/health").await;
    assert_eq!(res["ok"], true);
    assert!(res["landed"].is_array());
    assert!(res["forwarded"].is_array());
    // Task 5 landed `files`/`search`; Task 6 `neighborhood`; Task 7 `blocklinks`/`edges`;
    // Task 8 `source`; Task 9 `file`/`blocks`; Task 10 `tablegraph`/`story`; Task 12
    // `run`: eleven of the twelve questions are answered here now, and only `convert`
    // still forwards. Landing that one deletes this line along with the fallback itself.
    assert_eq!(res["landed"].as_array().unwrap().len(), 11);
    assert_eq!(res["forwarded"].as_array().unwrap().len(), 1);
}
