//! Task 7's two headline pass marks (`.superpowers/sdd/silver_phase2_implementation_plan/task-7-brief.md`).
//!
//! The brief's `blocklinks_name_both_blocks` was written with `ankitha_1/…` fileids; Task 5
//! rebuilt the store on `sas/raw/…` (M0.3 measured it against `:8000` on 2026-09-10), so
//! the URL here says `sas%2Fraw%2F…`. Only the stale token changed — every assertion is the
//! brief's, unedited.

mod support;
use support::get;

#[tokio::test]
async fn dashboard_mart_has_twenty_five_edges() {
    // the "25 / 25" in the owner's baseline screenshot
    let files = "sas/raw/09_customer_summary.sas,sas/raw/10_product_metrics.sas,\
sas/raw/11_branch_rollup.sas,sas/raw/14_large_txn_report.sas,\
sas/raw/18_dashboard_mart.sas,sas/raw/19_export_dashboard.sas,sas/raw/25_final_pack.sas";
    let r = get(&format!("/api/edges?files={}", urlencoding::encode(files))).await;
    assert_eq!(r["total"], 25);
    let rows = r["rows"].as_array().unwrap();
    assert!(
        rows.iter().any(|e| e["provenance"] == "human_gold"),
        "the baseline shows one HUMAN_GOLD row; human_edits must overlay the inferred edges"
    );
    assert!(rows.iter().any(|e| e["level"] == "block" && e["provenance"] == "fact"));
}

#[tokio::test]
async fn blocklinks_name_both_blocks() {
    let r = get("/api/blocklinks?files=sas%2Fraw%2F11_branch_rollup.sas,sas%2Fraw%2F18_dashboard_mart.sas").await;
    let links = r["links"].as_array().unwrap();
    assert!(!links.is_empty());
    for l in links {
        assert!(!l["src_block"].as_str().unwrap().is_empty(), "src_block empty — Task 1 did not take");
        assert!(!l["dst_block"].as_str().unwrap().is_empty(), "dst_block empty");
    }
    assert!(links.iter().any(|l| l["table"] == "work.branch_rollup"));
}
