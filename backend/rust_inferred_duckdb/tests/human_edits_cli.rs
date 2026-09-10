//! M2/G3 (2026-09-10): `lineageq_store human-edit <db> <json-file>` — the store-side half is
//! `inferred_duckdb::load_human_edits`, and this is its proof.
//!
//! Why it matters: before this, nothing in the repo could put a customer edit into a store,
//! so `edges()`'s merged view (the owner's "25 / 25 with one HUMAN_GOLD row" pass mark) could
//! only be reproduced by re-running a throwaway Python snippet nobody had kept. The fixture
//! read here is the very file the API's test store seeds from, so the two stores can never
//! drift apart.

use std::path::Path;

#[test]
fn human_edit_loads_the_api_fixture_and_is_idempotent() {
    let db = std::env::temp_dir().join(format!("human_edit_cli_{}.duckdb", std::process::id()));
    let _ = std::fs::remove_file(&db);
    let conn = inferred_duckdb::open(&db).unwrap();

    let fixture = Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../api/tests/fixtures/human_edits.json"
    ));
    let n = inferred_duckdb::load_human_edits(&conn, fixture).unwrap();
    assert_eq!(n, 1, "the fixture holds exactly one edit");

    let rows = inferred_duckdb::human_edits(&conn).unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].action, "correct");
    assert_eq!(rows[0].table_name, "work.cust_summary");
    assert_eq!(rows[0].level, "project");
    assert!(!rows[0].requires_check);

    // Running it twice must not double the merged view — `insert_human_edit` is keyed on
    // `edit_id`, and a dev store is rebuilt by re-running the same two commands.
    inferred_duckdb::load_human_edits(&conn, fixture).unwrap();
    assert_eq!(inferred_duckdb::human_edits(&conn).unwrap().len(), 1);
}
