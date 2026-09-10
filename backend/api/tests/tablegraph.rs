//! Task 10's `tablegraph()` and `story()`
//! (`.superpowers/sdd/silver_phase2_implementation_plan/task-10-brief.md`).
//!
//! The pass mark is the owner's own Bench screenshot of this fixture: **12 edges** across
//! SOURCE -> STEP 1 -> STEP 2 -> STEP 3, `sales.sales_data` at the source and
//! `sales.final_summary` at the end, and `sales.q1_avg_sales` made by `b_007`. `story()`'s
//! is smaller and just as sharp: the makers of a table come back in the order they run, not
//! the order the rows happen to sit in.

mod support;
use support::{get_fixtures as get, get_raw_fixtures as get_raw};

#[tokio::test]
async fn tablegraph_matches_the_bench_screenshot() {
    let r = get("/api/tablegraph?fileid=test_vishnu_testdata_fixed.sas").await;
    assert_eq!(r["edges"].as_array().unwrap().len(), 12, "the baseline says '12 edges'");
    let t: Vec<&str> = r["tables"].as_array().unwrap().iter()
        .map(|x| x["name"].as_str().unwrap()).collect();
    for want in ["sales.sales_data", "sales.q1_avg_sales", "sales.final_summary"] {
        assert!(t.contains(&want), "missing {}", want);
    }
    let e = r["edges"].as_array().unwrap().iter()
        .find(|e| e["dst"] == "sales.q1_avg_sales").unwrap();
    assert_eq!(e["block_id"], "b_007");
}

#[tokio::test]
async fn story_lists_makers_in_run_order() {
    let r = get("/api/story?table=sales.final_summary").await;
    let m = r["makers"].as_array().unwrap();
    assert!(!m.is_empty());
    let ns: Vec<i64> = m.iter().map(|x| x["n"].as_i64().unwrap()).collect();
    let mut sorted = ns.clone(); sorted.sort();
    assert_eq!(ns, sorted, "makers must come back in run order, not insertion order");
}

#[tokio::test]
async fn a_story_maker_names_its_file_and_block() {
    let r = get("/api/story?table=sales.final_summary").await;
    let m = &r["makers"].as_array().unwrap()[0];
    assert_eq!(m["fileid"], "test_vishnu_testdata_fixed.sas");
    assert_eq!(m["block_id"], "b_012", "b_012 is the DATA step that makes sales.final_summary");
}

#[tokio::test]
async fn a_table_nobody_makes_has_an_empty_story_not_an_error() {
    let r = get("/api/story?table=sales.sales_data").await;
    // sales.sales_data is built from datalines: it is a source, so no edge makes it.
    assert!(r["makers"].as_array().unwrap().is_empty());
}

#[tokio::test]
async fn missing_parameters_are_400s() {
    assert_eq!(get_raw("/api/tablegraph").await.status, 400);
    assert_eq!(get_raw("/api/story").await.status, 400);
}
