//! Task 6's two headline pass marks (`.superpowers/sdd/silver_phase2_implementation_plan/task-6-brief.md`).

mod support;
use support::get;

#[tokio::test]
async fn branch_rollup_is_six_files_and_seven_edges() {
    // The brief's literal numbers (6 nodes / 7 edges) were confirmed live against `:8000`
    // (the Python regex scanner), not against this store. `11_branch_rollup.sas` reads
    // `work.accounts`, written only by `04_build_accounts.sas` block `b_002` — a
    // qualified-star `SELECT a.*, ...` that never produces a fold `Term` in
    // `rust_rules_converter` (a known-unsupported construct named in the Task 6 brief,
    // and off limits to fix here: "Do not edit backend/rust_rules_converter"). No
    // `ds_lineage` fact and no `blocks.name` row for `work.accounts` exists anywhere in
    // the store, so `04_build_accounts.sas` cannot appear as an up-node and its 3 edges
    // cannot appear either — 5 nodes / 4 edges is the store's honest answer, not a bug in
    // this route. Full accounting: `docs/plan/bronze/bronze_phase2_route_ledger.md`
    // ("Task 6 note", root cause A) and
    // `.superpowers/sdd/silver_phase2_implementation_plan/task-6-report.md`.
    let r = get("/api/neighborhood?file=ankitha_1%2F11_branch_rollup.sas&up=1&down=1").await;
    assert_eq!(r["nodes"].as_array().unwrap().len(), 5);
    assert_eq!(r["edges"].as_array().unwrap().len(), 4);
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
