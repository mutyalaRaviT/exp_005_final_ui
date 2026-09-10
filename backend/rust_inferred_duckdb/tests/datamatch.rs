//! Task 11's three tests, verbatim from `.superpowers/sdd/silver_phase2_implementation_plan/task-11-brief.md`.
//!
//! **Why these three and not more.** `datamatch` is the one place in the slice where a
//! *wrong* answer is silent: a comparison that is too generous returns `match` over a bad
//! migration and the whole verification loop reports green. The three failure modes that
//! would do that are normalisation (`"5"` vs `"5.0"` vs `"5.000000"`), set-instead-of-
//! multiset (a lost duplicate row), and an accidental order dependency. One test each.
//! The real coverage is `tools/xcheck_datamatch.py`, which runs both this and
//! `pipeline/datamatch.py` over the 11 blocks' real CSVs and requires identical verdicts.

use inferred_duckdb::datamatch::{compare_rows, normalize_value, Verdict};

#[test]
fn normalisation_matches_python() {
    assert_eq!(normalize_value(" 1.0 "), "1"); // whole float -> integer
    assert_eq!(normalize_value("."), ""); // SAS missing
    assert_eq!(normalize_value(""), "");
    assert_eq!(normalize_value("-0"), "0");
    assert_eq!(normalize_value("1.2345678"), "1.234568"); // 6 dp
    assert_eq!(normalize_value("nan"), "nan");
    assert_eq!(normalize_value("Fred"), "Fred"); // non-numeric passes through
}

#[test]
fn duplicates_are_counted() {
    let a = vec![vec!["x".into()], vec!["x".into()]];
    let b = vec![vec!["x".into()]];
    let (v, n, _) = compare_rows(&a, &b, 5);
    assert!(matches!(v, Verdict::Fail));
    assert_eq!(n, 1, "a multiset comparison must notice the missing duplicate");
}

#[test]
fn row_order_does_not_matter() {
    let a = vec![vec!["p".into()], vec!["q".into()]];
    let b = vec![vec!["q".into()], vec!["p".into()]];
    assert!(matches!(compare_rows(&a, &b, 5).0, Verdict::Pass));
}
