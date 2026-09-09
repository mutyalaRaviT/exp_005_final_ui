mod support;

/// The Bench page must come from the same door as the API it calls. bench.html asks for
/// relative `/api/...`, so whichever origin serves the page decides which backend it
/// talks to; serving it from :8110 is what puts UI2 behind the Rust API without editing
/// the 1,300-line page.
#[tokio::test]
async fn bench_page_is_served_and_is_the_real_page() {
    let res = support::get_raw("/bench").await;
    assert_eq!(res.status, 200);
    assert_eq!(res.content_type, "text/html; charset=utf-8");
    assert!(res.body.contains("<title>lineageQ Bench</title>"), "not the Bench page");
}
