mod support;
use support::get;

#[tokio::test]
async fn health_reports_which_routes_have_landed() {
    let res = get("/api/health").await;
    assert_eq!(res["ok"], true);
    assert!(res["landed"].is_array());
    assert!(res["forwarded"].is_array());
    // Task 5 landed `files`/`search`; Task 6 `neighborhood`; Task 7 `blocklinks`/`edges`;
    // Task 8 `source`; Task 9 `file`/`blocks`; Task 10 `tablegraph`/`story`: ten of the
    // twelve questions read the store now, two (`convert` and `run`, both POST-shaped and
    // both Task 11/12's) are still forwarded. The last route task deletes this pair along
    // with the fallback itself.
    assert_eq!(res["landed"].as_array().unwrap().len(), 10);
    assert_eq!(res["forwarded"].as_array().unwrap().len(), 2);
}
