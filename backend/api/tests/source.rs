//! Task 8's `source()` (`.superpowers/sdd/silver_phase2_implementation_plan/task-8-brief.md`).
//!
//! The brief names the route but states no wire shape and `tools/diff_route.py` has no
//! oracle for it (`ROUTES["source"].no_oracle`), so this file is the route's whole proof:
//! the text it returns is the file on disk, byte for byte, and a fileid the store has never
//! seen is a 404 rather than an empty string pretending to be a file.

mod support;
use support::{get, get_raw};

#[tokio::test]
async fn source_is_the_file_on_disk_byte_for_byte() {
    let r = get("/api/source?fileid=sas%2Fraw%2F11_branch_rollup.sas").await;
    let on_disk = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../corpus/team_finance/sas/raw/11_branch_rollup.sas"
    ))
    .expect("read the corpus file this store was seeded from");

    assert_eq!(r["fileid"], "sas/raw/11_branch_rollup.sas");
    assert_eq!(r["text"].as_str().unwrap(), on_disk);
    assert_eq!(r["size"].as_u64().unwrap(), on_disk.len() as u64);
}

#[tokio::test]
async fn an_unknown_fileid_is_a_404_not_an_empty_file() {
    let res = get_raw("/api/source?fileid=sas%2Fraw%2Fnot_a_file.sas").await;
    assert_eq!(res.status, 404, "body was: {}", res.body);
}

#[tokio::test]
async fn a_missing_fileid_is_a_400() {
    let res = get_raw("/api/source").await;
    assert_eq!(res.status, 400, "body was: {}", res.body);
}
