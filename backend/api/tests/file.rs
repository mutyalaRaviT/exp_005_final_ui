//! Task 9's `file()` (`.superpowers/sdd/silver_phase2_implementation_plan/task-9-brief.md`).
//!
//! The pass mark, from the brief: `file()` on `test_vishnu_testdata_fixed.sas` returns 23
//! blocks, `receipts.statements == 80`, `folded == 80`, `roundtrip == 80`, and **no block
//! carries a `sas` key**. That last one is the point of the whole route: opening a file must
//! not ship the file's text, so a 1000-block file opens in milliseconds instead of the 63.4 s
//! the Bench takes (`docs/plan/bronze/bronze_perf_receipts_exp42.md`). `blocks()` is the
//! route that ships text, one window at a time.

mod support;
use support::{get_fixtures as get, get_raw_fixtures as get_raw};

#[tokio::test]
async fn file_on_the_exp42_fixture_has_twenty_three_blocks_and_eighty_eighty_eighty() {
    let r = get("/api/file?fileid=test_vishnu_testdata_fixed.sas").await;

    assert_eq!(r["stem"], "test_vishnu_testdata_fixed");
    assert_eq!(r["ok"], true);
    assert_eq!(r["errors"].as_array().unwrap().len(), 0);

    let blocks = r["blocks"].as_array().expect("blocks is a list");
    assert_eq!(blocks.len(), 23, "the exp_42 receipt file folds to 23 blocks");

    assert_eq!(r["receipts"]["statements"], 80);
    assert_eq!(r["receipts"]["folded"], 80);
    assert_eq!(r["receipts"]["roundtrip"], 80);
}

#[tokio::test]
async fn no_block_in_file_carries_its_text() {
    let r = get("/api/file?fileid=test_vishnu_testdata_fixed.sas").await;
    for b in r["blocks"].as_array().unwrap() {
        let o = b.as_object().unwrap();
        assert!(!o.contains_key("sas"), "file() must not ship block text: {b}");
        assert!(!o.contains_key("py"), "file() must not ship block text: {b}");
        assert!(!o.contains_key("py_pretty"), "file() must not ship block text: {b}");
        assert!(!o.contains_key("terms"), "file() ships heads only, not node/4 terms: {b}");
        // the head fields the brief does specify
        for k in ["id", "n", "kind", "name", "lines", "warn", "reads", "writes"] {
            assert!(o.contains_key(k), "file() block is missing {k}: {b}");
        }
    }
}

#[tokio::test]
async fn an_unknown_fileid_is_a_404() {
    let res = get_raw("/api/file?fileid=not_a_file.sas").await;
    assert_eq!(res.status, 404, "body was: {}", res.body);
}

#[tokio::test]
async fn a_missing_fileid_is_a_400() {
    let res = get_raw("/api/file").await;
    assert_eq!(res.status, 400, "body was: {}", res.body);
}

/// UI1's own `/api/file/<fileid>` — a different answer on a different path (see
/// `routes::file`'s doc comment). Finding G7: with `:8000` dead, UI1 showed `could not load
/// blocks for <fileid>` because nothing in Rust served this. These two use the team_finance
/// store, the corpus UI1 actually draws, not the exp42 fixture the rest of this file uses.
#[tokio::test]
async fn ui1_file_detail_has_code_blocks_and_block_edges() {
    let r = support::get_team_finance("/api/file/sas/raw/11_branch_rollup.sas").await;
    assert_eq!(r["fileid"], "sas/raw/11_branch_rollup.sas");
    assert_eq!(r["name"], "11_branch_rollup.sas");
    assert_eq!(r["folder"], "sas/raw");
    assert!(r["code"].as_str().unwrap().contains("branch_rollup"), "the file's own text");

    let blocks = r["blocks"].as_array().unwrap();
    assert!(!blocks.is_empty());
    let b = &blocks[0];
    assert_eq!(b["status"], "PARSED");
    assert!(b["line_start"].as_i64().unwrap() > 0);
    // every occurrence ref is `<block_id>:<table>` — the same ref `blocklinks` emits, which
    // is what `graph2.ts::ownerOf` matches a link against.
    for occ in b["occurrences"].as_array().unwrap() {
        let id = occ["id"].as_str().unwrap();
        assert!(id.starts_with(b["id"].as_str().unwrap()), "occurrence ref {id}");
        assert!(occ["role"] == "read" || occ["role"] == "write");
    }
    assert_eq!(
        b["reads"].as_u64().unwrap() + b["writes"].as_u64().unwrap(),
        b["occurrences"].as_array().unwrap().len() as u64
    );

    // the fields UI1 reads unconditionally: absent ones would crash graph2.ts, not degrade
    for k in ["block_edges", "file_edges", "macro_calls", "includes", "missing_includes"] {
        assert!(r[k].is_array(), "{k} must be a list");
    }
}

#[tokio::test]
async fn ui1_file_detail_404s_for_a_file_the_store_never_saw() {
    let res = support::get_raw_team_finance("/api/file/sas/raw/not_a_file.sas").await;
    assert_eq!(res.status, 404, "body was: {}", res.body);
}
