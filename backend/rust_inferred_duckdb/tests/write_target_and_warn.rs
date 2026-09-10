//! Two regression tests for `fold_one` (`rust_inferred_duckdb/src/lib.rs`):
//!
//! - `block_write_target` fallback (Task 5 brief, "genuine bug fix"): a DATA step seeded
//!   only from `datalines` (no SET/MERGE) never fires `ds_lineage` because that fact only
//!   fires when a block also *reads* another table — before the fix `blocks.name` and
//!   `tables` both silently dropped it.
//! - Ruling D9: an unmapped SAS function (`emit::sas_fn`/`emit_pretty::sas_fn` panic on
//!   anything not in their table, e.g. `today()`) must not take `convert` down. The block
//!   should land with `warn = true` and empty `py_text`/`py_pretty`, not abort the process.

use duckdb::Connection;

fn convert_text(dir_name: &str, sas: &str) -> Connection {
    let dir = std::env::temp_dir().join(dir_name);
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("t.sas"), sas).unwrap();

    let spec = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/out/spec/sas.json"));
    let db = dir.join("s.duckdb");
    let mut c = inferred_duckdb::open(&db).unwrap();
    inferred_duckdb::convert(&mut c, spec, &dir).unwrap();
    c
}

#[test]
fn a_datalines_only_data_step_still_names_its_table() {
    let c = convert_text(
        "phase2_write_target",
        "data work.seed;\n  input id name $;\n  datalines;\n1 A\n2 B\n;\nrun;\n",
    );

    let name: String = c
        .query_row("SELECT name FROM blocks WHERE fileid = 't.sas'", [], |r| r.get(0))
        .unwrap();
    assert_eq!(name, "work.seed", "a datalines-only DATA step must still name its own output");

    let in_tables: i64 = c
        .query_row("SELECT count(*) FROM tables WHERE name = 'work.seed'", [], |r| r.get(0))
        .unwrap();
    assert_eq!(in_tables, 1, "a seed table must reach the tables table (and therefore search())");
}

#[test]
fn an_unmapped_sas_function_warns_instead_of_panicking() {
    // today() has no PySpark mapping in emit.rs/emit_pretty.rs (Ruling D9 — Prolog has
    // none either, so Rust must not add one). Converting this must not panic the process.
    let c = convert_text(
        "phase2_warn_block",
        "data work.src;\n  input id;\n  datalines;\n1\n;\nrun;\n\nproc sql;\n  create table work.t as select id, today() as d from work.src;\nquit;\n",
    );

    let (warn, py_text, py_pretty): (bool, String, String) = c
        .query_row(
            "SELECT warn, py_text, py_pretty FROM blocks WHERE fileid = 't.sas' AND kind = 'proc_sql'",
            [],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
        )
        .unwrap();
    assert!(warn, "an unmapped SAS function must set warn = true, not panic convert()");
    assert!(py_text.is_empty(), "py_text must be empty when emit failed");
    assert!(py_pretty.is_empty(), "py_pretty must be empty when emit_pretty failed");

    // and the rest of the file still converted fine: the DATA step block is unaffected.
    let seed_warn: bool = c
        .query_row("SELECT warn FROM blocks WHERE fileid = 't.sas' AND kind = 'data'", [], |r| r.get(0))
        .unwrap();
    assert!(!seed_warn, "a block with no mapping gap must not be marked warn");
}
