//! Regression test — fix round 1 (2026-09-09, tasks 5b/5c).
//!
//! `pipeline/specs/sas.py`'s `select_stmt` ORDER BY used to build its direction field
//! with `choice("dir", {"ASC": "asc", "DESC": "desc"}, default="asc")`. Choice's print
//! (`pipeline/gen_prolog.py`'s `Choice` case in `compile_parts_print`) always emits the
//! literal keyword for whatever value the field resolved to — and the zero-token default
//! branch resolves to the SAME atom (`asc`) an explicit `ASC` keyword would, so print
//! could not tell "the source wrote ASC" from "the source wrote nothing". A bare
//! `ORDER BY key` (no ASC/DESC) folded fine but printed back with an `asc` injected,
//! breaking the source-rebuild law. No file in this project's regression corpus (neither
//! `test_vishnu_testdata_fixed.sas`/`big_1000.sas`, nor the ankitha corpus's only ORDER BY,
//! `14_large_txn_report.sas`, which always writes `DESC` explicitly) exercised a bare
//! `ORDER BY`, so this went uncaught until reviewed directly.
//!
//! Fixed by dropping Choice's own `default=` and wrapping it in `opt(...)` instead —
//! `orderby`'s direction field is `none|some(asc)|some(desc)` now, which genuinely
//! preserves presence. This test folds a bare `ORDER BY key` statement, prints it back,
//! and requires the source-rebuild law to hold, so this specific regression cannot
//! silently return.
use rules_converter::{parser, rebuild_source, spec, tokenise};

fn load_spec() -> spec::Spec {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/out/spec/sas.json");
    let text = std::fs::read_to_string(path).unwrap_or_else(|e| panic!("read {}: {}", path, e));
    serde_json::from_str(&text).expect("spec json")
}

/// Folds `text` as a whole SAS program, prints every statement back, and returns the
/// rebuilt source plus any per-token mismatches — the same law `lineageq_sas`'s own CLI
/// checks (source == rebuilt byte for byte).
fn fold_print_rebuild(spec: &spec::Spec, text: &str) -> (String, Vec<(String, String)>) {
    let toks = tokenise::tokenise(spec, text);
    let stmts = tokenise::split_statements(&toks);
    let printer = parser::Printer { spec };
    let mut printed_texts: Vec<Option<Vec<String>>> = Vec::new();
    for st in &stmts {
        let t = parser::Parser::new(spec, &st.toks)
            .fold()
            .unwrap_or_else(|| panic!("fold failed: {:?}", st.toks.iter().map(|t| &t.text).collect::<Vec<_>>()));
        let texts = printer.print_stmt(&t).expect("print failed");
        printed_texts.push(Some(texts));
    }
    rebuild_source(&toks, &printed_texts)
}

#[test]
fn bare_order_by_round_trips() {
    let spec = load_spec();
    let text = "proc sql;\ncreate table work.t as select a from work.s order by a;\nquit;\n";
    let (rebuilt, mismatches) = fold_print_rebuild(&spec, text);
    assert!(mismatches.is_empty(), "rebuild mismatches: {:?}", mismatches);
    assert_eq!(rebuilt, text, "a bare ORDER BY (no ASC/DESC) must round-trip byte for byte");
}

#[test]
fn explicit_asc_still_round_trips() {
    let spec = load_spec();
    let text = "proc sql;\ncreate table work.t as select a from work.s order by a asc;\nquit;\n";
    let (rebuilt, mismatches) = fold_print_rebuild(&spec, text);
    assert!(mismatches.is_empty(), "rebuild mismatches: {:?}", mismatches);
    assert_eq!(rebuilt, text, "an explicit ASC must still round-trip byte for byte");
}

#[test]
fn explicit_desc_still_round_trips() {
    let spec = load_spec();
    let text = "proc sql;\ncreate table work.t as select a from work.s order by a desc;\nquit;\n";
    let (rebuilt, mismatches) = fold_print_rebuild(&spec, text);
    assert!(mismatches.is_empty(), "rebuild mismatches: {:?}", mismatches);
    assert_eq!(rebuilt, text, "an explicit DESC must still round-trip byte for byte");
}
