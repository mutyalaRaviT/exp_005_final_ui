use duckdb::Connection;

fn cols(c: &Connection, t: &str) -> Vec<String> {
    let mut s = c.prepare("SELECT column_name FROM information_schema.columns WHERE table_name = ?").unwrap();
    s.query_map([t], |r| r.get::<_, String>(0)).unwrap().map(|x| x.unwrap()).collect()
}

#[test]
fn schema_has_what_phase2_needs() {
    let db = std::env::temp_dir().join("phase2_cols.duckdb");
    let _ = std::fs::remove_file(&db);
    let c = inferred_duckdb::open(&db).unwrap();
    assert!(cols(&c, "files").contains(&"source".to_string()));
    for x in ["trace_b0", "trace_b1"] { assert!(cols(&c, "node4").contains(&x.to_string()), "node4.{}", x); }
    assert!(cols(&c, "blocks").contains(&"block_hash".to_string()));
    for t in ["runs", "run_tables", "run_samples", "meta"] {
        assert!(!cols(&c, t).is_empty(), "table {} missing", t);
    }
}

#[test]
fn a_spec_change_forces_a_reconvert() {
    let dir = std::env::temp_dir().join("phase2_specchange");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("t.sas"), "data work.a; set work.b; run;\n").unwrap();

    let spec_a = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/out/spec/sas.json"));
    // a byte-identical copy with one extra space: same grammar, different hash
    let spec_b = dir.join("sas_copy.json");
    std::fs::write(&spec_b, std::fs::read_to_string(spec_a).unwrap() + " ").unwrap();

    let db = dir.join("s.duckdb");
    let mut c = inferred_duckdb::open(&db).unwrap();
    let r1 = inferred_duckdb::convert(&mut c, spec_a, &dir).unwrap();
    assert_eq!(r1.ok, 1);

    // same spec: the file is skipped, so no blocks are rewritten
    let r2 = inferred_duckdb::convert(&mut c, spec_a, &dir).unwrap();
    assert_eq!(r2.blocks, 0, "unchanged file + unchanged spec must be skipped");

    // different spec hash: it must be reconverted even though the file is identical
    let r3 = inferred_duckdb::convert(&mut c, &spec_b, &dir).unwrap();
    assert!(r3.blocks > 0, "a spec change must force a reconvert; stale rows are wrong answers");
}
