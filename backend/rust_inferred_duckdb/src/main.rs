//! `lineageq_store` — the command line over the store.
//!
//! **Why this exists.** Phase 1's pass mark is measured, not asserted: this binary is how
//! `convert`, `file` and `blocks` get timed on `big_1000.sas`.
//!
//! **Inputs → outputs.**
//!   lineageq_store convert <spec.json> <folder> <db>
//!   lineageq_store file    <db> <fileid>
//!   lineageq_store blocks  <db> <fileid> <from> <to>
//!   lineageq_store search  <db> <query>
//!   lineageq_store human-edit <db> <json-file>
//!   lineageq_store counts  <db>
//! Each read prints JSON and its own wall time in ms on the last line.

use inferred_duckdb as store;
use std::path::Path;
use std::time::Instant;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if a.len() < 3 { eprintln!("{}", USAGE); std::process::exit(2); }
    if let Err(e) = run(&a) { eprintln!("error: {}", e); std::process::exit(1); }
}

const USAGE: &str = "lineageq_store convert <spec.json> <folder> <db> | file <db> <fileid> | blocks <db> <fileid> <from> <to> | search <db> <q> | counts <db> | human-edit <db> <json-file>";

fn run(a: &[String]) -> store::Res<()> {
    match a[1].as_str() {
        "convert" => {
            let mut conn = store::open(Path::new(&a[4]))?;
            let rep = store::convert(&mut conn, Path::new(&a[2]), Path::new(&a[3]))?;
            println!("{}", serde_json::to_string_pretty(&rep)?);
            eprintln!("convert: {} files, {} blocks, {} node4, {} edges  fold {:.0} ms  store {:.0} ms  total {:.0} ms",
                rep.files, rep.blocks, rep.node4, rep.edges, rep.fold_ms, rep.store_ms, rep.total_ms);
        }
        "file" => {
            let conn = store::open(Path::new(&a[2]))?;
            let t = Instant::now();
            let ans = store::file(&conn, &a[3])?;
            let ms = t.elapsed().as_secs_f64() * 1000.0;
            println!("{}", serde_json::to_string(&ans)?);
            eprintln!("file({}): {} blocks in {:.2} ms", a[3], ans.blocks.len(), ms);
        }
        "blocks" => {
            let conn = store::open(Path::new(&a[2]))?;
            let (from, to): (i64, i64) = (a[4].parse()?, a[5].parse()?);
            let t = Instant::now();
            let bs = store::blocks(&conn, &a[3], from, to)?;
            let ms = t.elapsed().as_secs_f64() * 1000.0;
            let bytes: usize = bs.iter().map(|b| b.sas_text.len() + b.py_pretty.len()).sum();
            println!("{}", serde_json::to_string(&bs)?);
            eprintln!("blocks({}, {}, {}): {} blocks, {} bytes of text in {:.2} ms", a[3], from, to, bs.len(), bytes, ms);
        }
        "search" => {
            let conn = store::open(Path::new(&a[2]))?;
            let t = Instant::now();
            let hits = store::search(&conn, &a[3])?;
            eprintln!("search({}): {} hits in {:.2} ms", a[3], hits.len(), t.elapsed().as_secs_f64() * 1000.0);
            println!("{}", serde_json::to_string(&hits)?);
        }
        // M2/G3 (2026-09-10): the only way to get a customer edit into a store used to be a
        // throwaway Python call (plan Part G, finding G3), so the dev store could not be
        // rebuilt from the repo alone. The JSON is the same array shape
        // `backend/api/tests/fixtures/human_edits.json` holds, so one file seeds both the
        // test store and the dev store. Idempotent on `edit_id`.
        "human-edit" => {
            if a.len() < 4 { eprintln!("{}", USAGE); std::process::exit(2); }
            let conn = store::open(Path::new(&a[2]))?;
            let n = store::load_human_edits(&conn, Path::new(&a[3]))?;
            eprintln!("human-edit: {} row(s) written from {}", n, a[3]);
            println!("{}", serde_json::to_string(&serde_json::json!({ "written": n }))?);
        }
        "counts" => {
            let conn = store::open(Path::new(&a[2]))?;
            for (t, n) in store::counts(&conn)? { println!("{:>10}  {}", t, n); }
        }
        _ => { eprintln!("{}", USAGE); std::process::exit(2); }
    }
    Ok(())
}
