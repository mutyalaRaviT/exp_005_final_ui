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

/// The 500 path must not leak this machine's filesystem layout to whoever hit the URL.
/// The handler reads a fixed `const` path, so there is no clean way to make the real
/// `GET /bench` request fail through the router — instead this drives the extracted
/// `unreadable_response` directly with a synthetic `io::Error` and checks its body for
/// exactly the kind of fragment the leaked message used to contain (an absolute path, the
/// repo-relative `corpus`-adjacent segments, and `CARGO_MANIFEST_DIR` itself).
#[test]
fn unreadable_response_body_has_no_filesystem_path() {
    let e = std::io::Error::new(std::io::ErrorKind::NotFound, "no such file or directory");
    let (status, body) = lineageq_api::routes::bench::unreadable_response(&e);

    assert_eq!(status, axum::http::StatusCode::INTERNAL_SERVER_ERROR);
    assert!(!body.contains("/Users"), "leaked an absolute path: {body}");
    assert!(!body.contains("corpus"), "leaked a repo-relative path: {body}");
    assert!(
        !body.contains(env!("CARGO_MANIFEST_DIR")),
        "leaked the manifest dir: {body}"
    );
    assert!(!body.is_empty(), "body should still say something useful");
}
