//! Task 6's two headline pass marks (`.superpowers/sdd/silver_phase2_implementation_plan/task-6-brief.md`).

mod support;
use support::get;

#[tokio::test]
async fn branch_rollup_is_six_files_and_seven_edges() {
    let r = get("/api/neighborhood?file=ankitha_1%2F11_branch_rollup.sas&up=1&down=1").await;
    assert_eq!(r["nodes"].as_array().unwrap().len(), 6);
    assert_eq!(r["edges"].as_array().unwrap().len(), 7);
}

#[tokio::test]
async fn enrich_fx_is_four_files_and_three_edges() {
    let r = get("/api/neighborhood?file=ankitha_1%2F07_enrich_fx.sas&up=1&down=1").await;
    assert_eq!(r["nodes"].as_array().unwrap().len(), 4);
    assert_eq!(r["edges"].as_array().unwrap().len(), 3);
    let roles: Vec<&str> = r["nodes"].as_array().unwrap().iter().map(|n| n["role"].as_str().unwrap()).collect();
    assert_eq!(roles.iter().filter(|x| **x == "seed").count(), 1);
    assert_eq!(roles.iter().filter(|x| **x == "up").count(), 2); // 05_seed_transactions, 06_seed_fx_rates
    assert_eq!(roles.iter().filter(|x| **x == "down").count(), 1); // 12_txn_agg
}
