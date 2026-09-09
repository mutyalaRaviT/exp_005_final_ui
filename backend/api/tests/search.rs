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
    // 5 brief, "confirmed live"). Today's fold only sees the writer side for this table —
    // 07_enrich_fx.sas's `PROC SQL CREATE TABLE AS SELECT` fails to fold (a pre-existing
    // rust_rules_converter gap, out of scope here; see the Task 5 report) — so `edges`
    // carries no row for it and this hit's `files` is `first_writer_fileid` alone. The
    // assertion is written to the code, not the aspiration: once that parser gap closes,
    // `edges` will carry the missing row and this test must grow the second file with it.
    let res = get("/api/search?q=fx_rates").await;
    let hits = res["hits"].as_array().unwrap();
    let h = hit(hits, "table", "work.fx_rates").expect("work.fx_rates hit");
    let files: Vec<&str> = h["files"].as_array().unwrap().iter().map(|f| f.as_str().unwrap()).collect();
    assert_eq!(files, vec!["ankitha_1/06_seed_fx_rates.sas"]);
}

#[tokio::test]
async fn a_table_hit_unions_edges_and_first_writer() {
    // work.accounts is never the target of a successfully-folded CREATE TABLE AS in this
    // corpus (04_build_accounts.sas's second block also hits the same parser gap), so it
    // is absent from `tables` entirely — its only trace is as `src_table` in the edge
    // 08_daily_balances.sas records. `first_writer_fileid` alone (the brief's warning)
    // would have missed it completely; this is the case that proves `edges` is load-
    // bearing here, not `tables` alone.
    let res = get("/api/search?q=work.accounts").await;
    let hits = res["hits"].as_array().unwrap();
    let h = hit(hits, "table", "work.accounts").expect("work.accounts hit via edges");
    let files: Vec<&str> = h["files"].as_array().unwrap().iter().map(|f| f.as_str().unwrap()).collect();
    assert_eq!(files, vec!["ankitha_1/08_daily_balances.sas"]);
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
