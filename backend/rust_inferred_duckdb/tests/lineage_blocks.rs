use inferred_duckdb::lineage_blocks::{edges_per_block, Edge};
use rules_converter::{fold_file, spec};

// 2026-09-09, Task 5 (team-finance-corpus): the fixture used to live at
// `raw/bench_stack/testdata/test_vishnu_testdata_fixed.sas`, but that whole directory
// (and its twin under `raw/bench_stack/corpus/sas/`) is deleted in this task so no
// competing corpus survives. Copied byte-for-byte into tests/fixtures/ so this
// regression (block b_007's PROC SQL edge) keeps its exact assertions.

fn spec_() -> spec::Spec {
    let p = concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/out/spec/sas.json");
    serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap()
}

#[test]
fn every_edge_names_the_block_that_made_it() {
    let src = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/test_vishnu_testdata_fixed.sas");
    let text = std::fs::read_to_string(src).unwrap();
    let (_stmts, terms, ids) = fold_file(&spec_(), &text);
    let edges = edges_per_block(&ids, &terms);

    assert!(!edges.is_empty(), "no edges at all");
    let blank: Vec<&Edge> = edges.iter().filter(|e| e.block_id.is_empty()).collect();
    assert!(blank.is_empty(), "{} edges have no block_id, e.g. {:?}", blank.len(), blank.first());

    // sales.q1_avg_sales is written by the PROC SQL at L111-121, which is block b_007
    let e = edges.iter().find(|e| e.dst == "sales.q1_avg_sales")
        .expect("no edge writes sales.q1_avg_sales");
    assert_eq!(e.src, "sales.q1_sales");
    assert_eq!(e.block_id, "b_007");
}
