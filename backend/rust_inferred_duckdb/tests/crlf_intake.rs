//! Decision D13 (plan Part I finding I4, M4a): CRLF is normalised **on intake**.
//!
//! **Why this exists.** The Python tokeniser reads with universal newlines, so on a CRLF
//! file Prolog's node/4 trace offsets run one byte short per line while Rust's count the
//! `\r`. Measured on `corpus/team_finance`'s 25 CRLF files: node/4 `prolog == rust` 0/25
//! before, 25/25 after; plain PySpark 13/25 -> 21/25 (the four left are the pre-existing
//! emitter panics, not line endings). These tests pin the two halves of the decision — the
//! engine sees LF, and the store still hands back the bytes that arrived — so neither can
//! be undone without a red test.

use duckdb::params;

fn store_with(name: &str, body: &str) -> (std::path::PathBuf, duckdb::Connection) {
    let dir = std::env::temp_dir().join(format!("m4a_crlf_{name}"));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("t.sas"), body).unwrap();
    let spec = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/out/spec/sas.json"));
    let db = dir.join("s.duckdb");
    let mut c = inferred_duckdb::open(&db).unwrap();
    inferred_duckdb::convert(&mut c, spec, &dir).unwrap();
    (dir, c)
}

const LF: &str = "data work.a;\n  set work.b;\nrun;\n";
const CRLF: &str = "data work.a;\r\n  set work.b;\r\nrun;\r\n";

#[test]
fn a_crlf_file_and_its_lf_twin_fold_to_the_same_node4() {
    let (_d1, lf) = store_with("lf", LF);
    let (_d2, crlf) = store_with("crlf", CRLF);
    let terms = |c: &duckdb::Connection| -> Vec<(String, i32, i32)> {
        let mut s = c
            .prepare("SELECT term, trace_b0, trace_b1 FROM node4 ORDER BY block_id, seq")
            .unwrap();
        s.query_map([], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))
            .unwrap()
            .map(|x| x.unwrap())
            .collect()
    };
    let a = terms(&lf);
    assert!(!a.is_empty(), "the LF file must fold to something to compare against");
    assert_eq!(a, terms(&crlf), "CRLF must not move a single node/4 byte offset");
}

#[test]
fn the_store_keeps_the_bytes_that_arrived_and_says_it_normalised() {
    let (_d, c) = store_with("source", CRLF);
    let (src, flag): (String, bool) = c
        .query_row("SELECT source, crlf_normalised FROM files WHERE fileid = 't.sas'", params![], |r| {
            Ok((r.get(0)?, r.get(1)?))
        })
        .unwrap();
    // `/api/source` reads this column verbatim: UI1's code pane must see the file as it is
    // on disk, not a rewritten copy. `raw/` is never touched either.
    assert_eq!(src, CRLF, "files.source must hold the bytes as received, CRLF intact");
    assert!(flag, "files.crlf_normalised must record that the engine was fed LF");

    let (_d2, c2) = store_with("source_lf", LF);
    let flag2: bool = c2
        .query_row("SELECT crlf_normalised FROM files WHERE fileid = 't.sas'", params![], |r| r.get(0))
        .unwrap();
    assert!(!flag2, "an LF file was not normalised and must not claim it was");
}

#[test]
fn block_line_numbers_still_slice_the_stored_source() {
    // The code pane slices `files.source` by `blocks.l0/l1`. Normalising for the engine
    // must not shift those, or every highlight in UI1 moves by a line.
    let (_d, c) = store_with("lines", CRLF);
    let (l0, l1, sas): (i32, i32, String) = c
        .query_row("SELECT l0, l1, sas_text FROM blocks ORDER BY n LIMIT 1", params![], |r| {
            Ok((r.get(0)?, r.get(1)?, r.get(2)?))
        })
        .unwrap();
    let src: String = c
        .query_row("SELECT source FROM files WHERE fileid = 't.sas'", params![], |r| r.get(0))
        .unwrap();
    let lines: Vec<&str> = src.lines().collect();
    let slice: Vec<String> = lines[(l0 as usize - 1)..(l1 as usize)]
        .iter()
        .map(|l| l.trim_end_matches('\r').to_string())
        .collect();
    assert_eq!(
        slice.join("\n").trim_end(),
        sas.trim_end(),
        "blocks.l0/l1 must still address the same lines of files.source"
    );
}
