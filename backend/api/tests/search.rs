mod support;
use support::get;

fn hit<'a>(hits: &'a [serde_json::Value], kind: &str, value: &str) -> Option<&'a serde_json::Value> {
    hits.iter().find(|h| h["kind"] == kind && h["value"] == value)
}

#[tokio::test]
async fn empty_query_is_no_hits() {
    let res = get("/api/search?q=").await;
    assert_eq!(res["hits"].as_array().unwrap().len(), 0);
}

#[tokio::test]
async fn a_table_hit_lists_every_file_it_appears_in() {
    // work.fx_rates is written by 06_seed_fx_rates.sas and read by 07_enrich_fx.sas (Task
    // 5 brief, "confirmed live"). Task 5b (2026-09-09) closed the parser gap this test used
    // to document: 07_enrich_fx.sas's `PROC SQL CREATE TABLE AS SELECT` (a single LEFT JOIN,
    // multi-condition ON, an alias, coalesce()) now folds, so `edges` carries the reader row
    // too and this hit's `files` grows to both writer and reader — the growth the old
    // comment on this test predicted.
    let res = get("/api/search?q=fx_rates").await;
    let hits = res["hits"].as_array().unwrap();
    let h = hit(hits, "table", "work.fx_rates").expect("work.fx_rates hit");
    let files: Vec<&str> = h["files"].as_array().unwrap().iter().map(|f| f.as_str().unwrap()).collect();
    assert_eq!(files, vec!["ankitha_1/06_seed_fx_rates.sas", "ankitha_1/07_enrich_fx.sas"]);
}

#[tokio::test]
async fn a_table_hit_unions_edges_and_first_writer() {
    // work.accounts's writer, 04_build_accounts.sas's second block (`select a.*, c.segment,
    // p.prod_type from work.accounts_raw a inner join ...`), needed qualified-star support
    // (`a.*`) to fold — task 5d (root cause A). Before that it was absent from `tables`
    // entirely; its only trace was as `src_table` in the edges its readers record. Task 5b's
    // LEFT/INNER JOIN support (capped at one JOIN per statement) got four of those readers
    // folding (08_daily_balances.sas, 09_customer_summary.sas, 10_product_metrics.sas,
    // 14_large_txn_report.sas). Task 5c lifted that cap to zero-or-more JOINs per statement,
    // which folded four more (11_branch_rollup.sas, phase 2's pass mark 1, plus
    // 15_join_risk_txn.sas, 22_marketing_list.sas, 24_ops_alerts.sas). Task 5d's qualified
    // star adds the writer itself, 04_build_accounts.sas, sorted first alphabetically — nine
    // files total. `first_writer_fileid` alone (the original brief's warning) would still
    // have missed the eight readers; this remains the case that proves `edges` is
    // load-bearing here, not `tables` alone.
    let res = get("/api/search?q=work.accounts").await;
    let hits = res["hits"].as_array().unwrap();
    let h = hit(hits, "table", "work.accounts").expect("work.accounts hit via edges");
    let files: Vec<&str> = h["files"].as_array().unwrap().iter().map(|f| f.as_str().unwrap()).collect();
    assert_eq!(files, vec![
        "ankitha_1/04_build_accounts.sas",
        "ankitha_1/08_daily_balances.sas",
        "ankitha_1/09_customer_summary.sas",
        "ankitha_1/10_product_metrics.sas",
        "ankitha_1/11_branch_rollup.sas",
        "ankitha_1/14_large_txn_report.sas",
        "ankitha_1/15_join_risk_txn.sas",
        "ankitha_1/22_marketing_list.sas",
        "ankitha_1/24_ops_alerts.sas",
    ]);
}

#[tokio::test]
async fn a_file_hit_is_shaped_right() {
    let res = get("/api/search?q=fx_rates").await;
    let hits = res["hits"].as_array().unwrap();
    let h = hit(hits, "file", "06_seed_fx_rates.sas").expect("file hit");
    assert_eq!(h["files"], serde_json::json!(["ankitha_1/06_seed_fx_rates.sas"]));
}

#[tokio::test]
async fn exact_match_ranks_above_a_longer_prefix_match() {
    let res = get("/api/search?q=work.fx_rates").await;
    let hits = res["hits"].as_array().unwrap();
    assert!(!hits.is_empty());
    assert_eq!(hits[0]["kind"], "table");
    assert_eq!(hits[0]["value"], "work.fx_rates");
}

#[tokio::test]
async fn no_hits_for_a_query_nothing_matches() {
    let res = get("/api/search?q=zzz_does_not_exist").await;
    assert_eq!(res["hits"].as_array().unwrap().len(), 0);
}
