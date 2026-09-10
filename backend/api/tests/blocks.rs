//! Task 9's `blocks()` — the windowed read that `file()` deliberately does not do.
//!
//! Pass mark from the brief: `blocks(fileid, 0, 40)` returns SAS **and** PySpark text. The
//! window is half-open on the store's own 0-based `n` (`inferred_duckdb::blocks`), so
//! `from=0&to=40` over a 23-block file returns all 23.

mod support;
use support::{get_fixtures as get, get_raw_fixtures as get_raw};

#[tokio::test]
async fn blocks_zero_to_forty_returns_sas_and_pyspark_text() {
    let r = get("/api/blocks?fileid=test_vishnu_testdata_fixed.sas&from=0&to=40").await;
    let bs = r.as_array().expect("blocks() returns a bare list");
    assert_eq!(bs.len(), 23, "0..40 covers the whole 23-block file");

    // b_002 is the DATA step that builds sales.sales_data — it has both halves.
    let b = bs.iter().find(|b| b["id"] == "b_002").expect("b_002 is in the window");
    assert!(b["sas"].as_str().unwrap().contains("sales.sales_data"), "SAS text: {}", b["sas"]);
    assert!(!b["py"].as_str().unwrap().is_empty(), "PySpark text must not be empty");
    assert!(!b["py_pretty"].as_str().unwrap().is_empty(), "pretty PySpark must not be empty");
    assert!(!b["terms"].as_array().unwrap().is_empty(), "the node/4 terms of the block");
}

#[tokio::test]
async fn the_window_is_half_open_on_n() {
    let r = get("/api/blocks?fileid=test_vishnu_testdata_fixed.sas&from=0&to=3").await;
    let bs = r.as_array().unwrap();
    assert_eq!(bs.len(), 3);
    assert_eq!(bs[0]["n"], 0);
    assert_eq!(bs[2]["n"], 2);
}

#[tokio::test]
async fn a_missing_fileid_is_a_400() {
    let res = get_raw("/api/blocks?from=0&to=40").await;
    assert_eq!(res.status, 400, "body was: {}", res.body);
}
