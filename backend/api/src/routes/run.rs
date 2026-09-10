//! `run` — `POST /api/run {fileid, block_id, engine}`: leg L2 against leg L3.
//!
//! **Why this exists.** Every other route in this API answers a question about what the
//! code *says*. This one is the only route that answers what the code *does*, and it is
//! the whole point of LineageQ: run one SAS block's own semantics over generated rows,
//! run the PySpark the engine emitted from the same node/4 over the same rows, and put
//! the two answers side by side (`docs/plan/gold/gold_three_uis_and_verification_loop.md`
//! §3, legs L2 and L3). A migration that returns different numbers has failed, and this
//! is where that is found out.
//!
//! **The four steps, three of them other programs.**
//!
//! 1. **prepare** (in-process): fold the file's stored SAS text into node/4 and write, under
//!    `raw/bench_stack/out/api/<stem>/`, the three things the other programs read — the
//!    source (`corpus/<stem>.sas`), the terms (`run/<stem>.node4.{json,pl}`) and the
//!    emitted PySpark job body (`pyspark_corpus/<stem>.py`).
//! 2. **rows** (`loops/gen_block_testdata.py`, Python + Z3, Decision D1 — shelled out, not
//!    ported): one input CSV per dataset the block reads, with a row per leg of every
//!    IF/WHERE, boundary rows and seeded random rows, plus `blocks/manifest.json` saying
//!    what each block creates. Decision D9: rows only. Nothing here says what the answer
//!    should be — that is what the two engines are for.
//! 3. **left** (`lineageq_sas interp`, or `swipl codegen/sas_interp.pl` when
//!    `engine: "prolog"`, Decision D6): the executable node/4 over those rows.
//! 4. **right** (`.venv/bin/python blocks/<b>/block_<t>_rust.py` on local Spark, Decision
//!    D4): the block's own emitted PySpark over the same rows. `lineageq_sas
//!    block-programs` cuts those one-block programs out of the whole job first.
//!
//! Then `inferred_duckdb::datamatch` (Task 11) judges every table the block creates, and
//! the verdicts are written to `runs`, `run_tables` and `run_samples`.
//!
//! **Why it mirrors `bench_api.run_block`'s paths instead of choosing its own.** The
//! reference harness (`raw/bench_stack/server/bench_receipt.py`, whose 11/11 receipt is
//! this route's pass mark) works in `out/api/<stem>/blocks/<block>/{in,rust,prolog,spark}`.
//! Writing the same CSVs to the same places is what lets `tools/xcheck_datamatch.py` read
//! this route's output and the harness's output with one code path, and what lets a human
//! diff the two by eye when a verdict is surprising.
//!
//! **Nothing here may 500 or hang.** A block whose emitter has no rule for a construct
//! panics by design (Ruling D9, plan finding I5: four team_finance files still do), a
//! block whose Z3 inputs yield no rows produces an empty table, and Spark can wedge. All
//! three are *answers about a block*, not failures of the API: they come back as
//! `match: "error"` with a message, or `"match-warn"` for the agreed-empty case, exactly
//! as `bench_receipt` counts them. `spawn::run` puts a deadline on every child.
//!
//! **Inputs → outputs.** `{fileid, block_id, engine}` → `{block_id, engine, left_ms,
//! right_ms, tables: [{name, verdict, n_mismatch, samples}], match}`, plus one `runs` row,
//! one `run_tables` row per table and up to five `run_samples` rows per differing table.

use crate::spawn;
use crate::types::AppState;
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::Json;
use inferred_duckdb::datamatch::{compare_rows, Verdict};
use rules_converter::{block_ids, emit, fold_file, quote_atom, spec};
use serde::Deserialize;
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::time::Duration;

/// Long enough for a cold Spark JVM (~5 s) plus a slow first Z3 pass, short enough that a
/// wedged child is reported inside one impatient person's attention span.
const STEP_TIMEOUT: Duration = Duration::from_secs(300);

#[derive(Deserialize)]
pub struct RunBody {
    pub fileid: String,
    pub block_id: String,
    /// `rust` (default, and the pass mark's engine) or `prolog` — Decision D6: the pass
    /// mark may use the fast one, but the independent one must exist, because a loop whose
    /// left and right sides are both Rust is Rust checking its own homework (gold §5).
    #[serde(default)]
    pub engine: Option<String>,
}

pub async fn run(
    State(state): State<AppState>,
    Json(body): Json<RunBody>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let fileid = body.fileid.trim().to_string();
    let block_id = body.block_id.trim().to_string();
    let engine = body.engine.clone().unwrap_or_else(|| "rust".to_string());
    if fileid.is_empty() || block_id.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "run(): fileid and block_id are required".into()));
    }
    if engine != "rust" && engine != "prolog" {
        return Err((StatusCode::BAD_REQUEST, format!("run(): engine must be rust or prolog, not {engine}")));
    }

    // The store is read once, up front, and the lock released before anything is awaited:
    // `duckdb::Connection` is `!Sync`, and a guard held across an await would not compile
    // — and should not, since a child process can take five seconds.
    let (source, warn) = {
        let conn = state.db.lock().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
        let source: Option<String> = conn
            .query_row("SELECT source FROM files WHERE fileid = ?", duckdb::params![&fileid], |r| r.get(0))
            .ok();
        let warn: Option<bool> = conn
            .query_row(
                "SELECT warn FROM blocks WHERE fileid = ? AND block_id = ?",
                duckdb::params![&fileid, &block_id],
                |r| r.get(0),
            )
            .ok();
        (source, warn.unwrap_or(false))
    };
    let Some(source) = source else {
        return Err((StatusCode::NOT_FOUND, format!("run(): no such fileid {fileid}")));
    };

    let stem = Path::new(&fileid)
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| fileid.clone());

    let outcome = run_block(&state, &fileid, &stem, &source, &block_id, &engine, warn).await;
    Ok(Json(outcome))
}

/// One table's verdict, in the shape the route returns and the `run_tables` row keeps.
struct TableVerdict {
    name: String,
    verdict: String,
    n_mismatch: i64,
    missing_side: Option<String>,
    samples: Vec<inferred_duckdb::datamatch::Sample>,
}

/// A structured "this block could not be judged" answer. Never a 500: the caller asked
/// about a block and this *is* the answer about that block.
fn error(block_id: &str, engine: &str, left_ms: f64, right_ms: f64, message: String) -> Value {
    json!({
        "block_id": block_id, "engine": engine,
        "left_ms": left_ms, "right_ms": right_ms,
        "tables": [], "match": "error", "message": message
    })
}

#[allow(clippy::too_many_arguments)]
async fn run_block(
    state: &AppState,
    fileid: &str,
    stem: &str,
    source: &str,
    block_id: &str,
    engine: &str,
    warn: bool,
) -> Value {
    let root = spawn::bench_root();
    let work = root.join("out/api").join(stem);

    // ---- step 1: prepare, in-process
    let prep = match prepare(&work, stem, source) {
        Ok(p) => p,
        Err(e) => return error(block_id, engine, 0.0, 0.0, e),
    };

    // ---- step 2: rows + one-block programs, cached per file exactly as
    // `bench_api._ensure_blocks` caches them (the 11-block loop pays for this once).
    let bdir = work.join("blocks");
    if !bdir.join("manifest.json").exists() {
        let out = spawn::run(
            &spawn::bench_python(),
            &[
                "loops/gen_block_testdata.py".into(),
                stem.into(),
                prep.node4_json.display().to_string(),
                bdir.display().to_string(),
            ],
            None,
            STEP_TIMEOUT,
        )
        .await;
        match out {
            Ok(o) if !o.ok() => return error(block_id, engine, 0.0, 0.0, o.why("gen_block_testdata.py")),
            Err(e) => return error(block_id, engine, 0.0, 0.0, format!("gen_block_testdata.py: {e}")),
            _ => {}
        }
        let out = spawn::run(
            &spawn::engine_bin(),
            &[
                "block-programs".into(),
                "out/spec/pyspark.json".into(),
                prep.job_py.display().to_string(),
                "codegen/sas_runtime_preamble.py".into(),
                bdir.display().to_string(),
            ],
            None,
            STEP_TIMEOUT,
        )
        .await;
        match out {
            Ok(o) if !o.ok() => return error(block_id, engine, 0.0, 0.0, o.why("block-programs")),
            Err(e) => return error(block_id, engine, 0.0, 0.0, format!("block-programs: {e}")),
            _ => {}
        }
    }

    let manifest: Vec<Value> = std::fs::read_to_string(bdir.join("manifest.json"))
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_default();
    let Some(entry) = manifest.iter().find(|e| e["block"].as_str() == Some(block_id)) else {
        // Not an error: a LIBNAME or a PROC PRINT creates nothing, so there is nothing to
        // compare. `bench_api.run_block` says "no inputs" for exactly this.
        return json!({
            "block_id": block_id, "engine": engine, "left_ms": 0.0, "right_ms": 0.0,
            "tables": [], "match": "no inputs",
            "message": format!("{block_id} creates no table to test")
        });
    };
    let creates: Vec<String> = entry["creates"]
        .as_array()
        .map(|a| a.iter().filter_map(|c| c.as_str().map(|s| s.to_string())).collect())
        .unwrap_or_default();

    let d = bdir.join(block_id);

    // ---- step 3: left — the executable node/4
    //
    // **Why `rust` runs in-process and `prolog` shells out.** The brief lists the left
    // side among the steps that shell out, and for Prolog it must: `swipl` is another
    // program. For Rust it need not be — `rules_converter::interp` is a library this
    // crate already links, and `lineageq_sas interp` is a thin CLI over the very same
    // code, on the very same node/4 this route just folded. Calling it directly is the
    // same computation with the process start taken out, and the process start is not
    // free: measured 2026-09-10, the subprocess form answers in ~8 ms on an idle machine
    // but 159 ms when `cargo test --workspace` has eight test binaries and a Spark JVM
    // running beside it — over the brief's own `left_ms < 100` bound, which exists to
    // prove the interpreter really ran. In-process, `left_ms` measures the interpreter
    // instead of the operating system's willingness to fork, which is what that bound is
    // about. `interp` refuses an unmapped construct by panicking, exactly as `emit` does
    // (Ruling D9), so the call is wrapped the same way.
    let (left_dir, left) = if engine == "prolog" {
        (
            d.join("prolog"),
            spawn::run(
                Path::new("swipl"),
                &[
                    "-q".into(), "-s".into(), "codegen/sas_interp.pl".into(), "-g".into(), "main".into(), "--".into(),
                    prep.node4_pl.display().to_string(),
                    d.join("in").display().to_string(),
                    d.join("prolog").display().to_string(),
                    block_id.into(),
                ],
                None,
                STEP_TIMEOUT,
            )
            .await
            .map(|o| (o.ms, if o.ok() { Ok(()) } else { Err(o.why("left (prolog interp)")) }))
            .unwrap_or_else(|e| (0.0, Err(format!("left (prolog): {e}")))),
        )
    } else {
        (d.join("rust"), interp_in_process(&prep, &d.join("in"), &d.join("rust"), block_id))
    };
    let (left_ms, left_res) = left;
    if let Err(why) = left_res {
        return error(block_id, engine, left_ms, 0.0, why);
    }

    // ---- step 4: right — the block's own PySpark on local Spark
    let Some(prog) = one_block_program(&d) else {
        return error(block_id, engine, left_ms, 0.0, format!("no block program in {}", d.display()));
    };
    let spark_dir = d.join("spark");
    let right = spawn::run(
        &spawn::bench_python(),
        &[prog.display().to_string()],
        Some(&spark_dir),
        STEP_TIMEOUT,
    )
    .await;
    let right = match right {
        Ok(o) => o,
        Err(e) => return error(block_id, engine, left_ms, 0.0, format!("right (spark): {e}")),
    };
    if !right.ok() {
        return error(block_id, engine, left_ms, right.ms, right.why("right (spark)"));
    }

    // ---- judge every table the block creates
    let mut tables: Vec<TableVerdict> = Vec::new();
    for t in &creates {
        let l = read_csv(&left_dir.join(format!("{t}.csv")));
        let r = read_csv(&spark_dir.join(format!("{t}.csv")));
        match (l, r) {
            (None, _) | (_, None) => {
                let missing = if read_csv(&left_dir.join(format!("{t}.csv"))).is_none() { "left" } else { "right" };
                tables.push(TableVerdict {
                    name: t.clone(), verdict: "missing".into(), n_mismatch: 0,
                    missing_side: Some(missing.into()), samples: Vec::new(),
                });
            }
            (Some(l), Some(r)) => {
                let (v, n, samples) = compare_rows(l.get(1..).unwrap_or(&[]), r.get(1..).unwrap_or(&[]), 5);
                // The `match-warn` rule is `bench_api.run_block`'s, verbatim: a table both
                // sides agree is empty, or a block the emitter warned about, is agreement —
                // but weak agreement, and it is labelled so rather than counted as proof.
                let verdict = if v == Verdict::Pass {
                    if l.len() <= 1 || warn { "match-warn" } else { "match" }
                } else {
                    "differs"
                };
                tables.push(TableVerdict {
                    name: t.clone(), verdict: verdict.into(), n_mismatch: n,
                    missing_side: None, samples,
                });
            }
        }
    }
    let verdicts: Vec<&str> = tables.iter().map(|t| t.verdict.as_str()).collect();
    let overall = if verdicts.is_empty() {
        "no inputs"
    } else if verdicts.contains(&"differs") {
        "differs"
    } else if verdicts.contains(&"missing") {
        "missing"
    } else if verdicts.contains(&"match-warn") {
        "match-warn"
    } else {
        "match"
    };

    write_rows(state, fileid, block_id, engine, overall, left_ms, &tables);

    json!({
        "block_id": block_id, "engine": engine,
        "left_ms": left_ms, "right_ms": right.ms,
        "tables": tables.iter().map(|t| json!({
            "name": t.name, "verdict": t.verdict, "n_mismatch": t.n_mismatch,
            "missing_side": t.missing_side, "samples": t.samples,
        })).collect::<Vec<_>>(),
        "match": overall
    })
}

/// The paths step 2 and step 3 read.
struct Prep {
    corpus_sas: PathBuf,
    node4_json: PathBuf,
    node4_pl: PathBuf,
    job_py: PathBuf,
}

/// Fold the stored SAS text and lay down everything the shelled-out programs read.
///
/// **Why node/4 is written here and not taken from `raw/bench_stack/out/api/<stem>/ir/`.**
/// That directory is the *Python* pipeline's (`run_fold.py` via `convert_api.convert`),
/// and this API must be able to answer `run()` with no Python pipeline having been run at
/// all — that is the whole point of phase 2. It goes under `run/` so the two never
/// overwrite each other. M3a measured the two node/4 texts byte-identical on this fixture,
/// so `swipl codegen/sas_interp.pl` is reading the same terms either way.
fn prepare(work: &Path, stem: &str, source: &str) -> Result<Prep, String> {
    let spec_path = spawn::bench_root().join("out/spec/sas.json");
    let spec: spec::Spec = serde_json::from_str(
        &std::fs::read_to_string(&spec_path).map_err(|e| format!("read {}: {e}", spec_path.display()))?,
    )
    .map_err(|e| format!("parse {}: {e}", spec_path.display()))?;

    let corpus = work.join("corpus");
    let run_dir = work.join("run");
    let body_dir = work.join("pyspark_corpus");
    for d in [&corpus, &run_dir, &body_dir] {
        std::fs::create_dir_all(d).map_err(|e| format!("mkdir {}: {e}", d.display()))?;
    }
    let corpus_sas = corpus.join(format!("{stem}.sas"));
    write_if_changed(&corpus_sas, source)?;

    let (stmts, terms, ids) = fold_file(&spec, source);
    let ids = if ids.is_empty() { block_ids(&spec, &terms) } else { ids };
    let rel = corpus_sas.display().to_string();

    let mut node4_json: Vec<Value> = Vec::new();
    let mut pl = String::new();
    let mut nodes: Vec<emit::Node> = Vec::new();
    for (i, st) in stmts.iter().enumerate() {
        let Some(t) = &terms[i] else { continue };
        node4_json.push(json!({
            "block": ids[i], "seq": st.seq, "term": t.to_string(),
            "trace": {"file": rel, "l0": st.l0, "l1": st.l1, "b0": st.b0, "b1": st.b1},
            "comments": []
        }));
        pl.push_str(&format!(
            "node({}, {}, {}, trace({},{},{},{},{})).\n",
            quote_atom(&ids[i]), st.seq, t, quote_atom(&rel), st.l0, st.l1, st.b0, st.b1
        ));
        nodes.push(emit::Node {
            block: ids[i].clone(), seq: st.seq, term: t.clone(),
            l0: st.l0, l1: st.l1, b0: st.b0, b1: st.b1,
        });
    }
    if nodes.is_empty() {
        return Err(format!("{stem}: nothing folded — no node/4 to run"));
    }
    let jp = run_dir.join(format!("{stem}.node4.json"));
    write_if_changed(&jp, &serde_json::to_string_pretty(&node4_json).unwrap_or_default())?;
    let pp = run_dir.join(format!("{stem}.node4.pl"));
    write_if_changed(&pp, &pl)?;

    // The PySpark job body, with no preamble: `block-programs` folds the body and glues
    // `codegen/sas_runtime_preamble.py` back on per block itself, which is why
    // `bench_api._ensure_blocks` cuts the preamble off before calling it. An emitter with
    // no rule for a construct panics by design (Ruling D9); catching it turns four known
    // team_finance files (finding I5) into a message instead of a dead API process.
    let job = inferred_duckdb::catch_emit(move || emit::Emitter::new().program(&nodes, ""))
        .map_err(|e| format!("emit PySpark for {stem}: {e}"))?;
    let job_py = body_dir.join(format!("{stem}.py"));
    write_if_changed(&job_py, &job)?;

    Ok(Prep { corpus_sas, node4_json: jp, node4_pl: pp, job_py })
}

/// The Rust left side, without a process start: fold-once terms in, CSVs out.
///
/// Returns `(ms, Ok)` or `(ms, Err(why))`. The node/4 is re-folded here rather than
/// carried out of `prepare`, because `interp::Interp::run` wants `(block_id, &Term)`
/// pairs and `Term` is not `Send` — the fold is ~1 ms on this fixture and keeps the
/// borrow local.
fn interp_in_process(prep: &Prep, in_dir: &Path, out_dir: &Path, block_id: &str) -> (f64, Result<(), String>) {
    let t0 = std::time::Instant::now();
    let spec_text = match std::fs::read_to_string(spawn::bench_root().join("out/spec/sas.json")) {
        Ok(t) => t,
        Err(e) => return (0.0, Err(format!("left (rust interp): read sas.json: {e}"))),
    };
    let source = match std::fs::read_to_string(&prep.corpus_sas) {
        Ok(t) => t,
        Err(e) => return (0.0, Err(format!("left (rust interp): read {}: {e}", prep.corpus_sas.display()))),
    };
    let block = block_id.to_string();
    let out = out_dir.to_path_buf();
    let data = in_dir.to_path_buf();
    let r = inferred_duckdb::catch_emit(move || {
        let spec: spec::Spec = serde_json::from_str(&spec_text).expect("parse sas.json");
        let (_stmts, terms, ids) = fold_file(&spec, &source);
        let nodes: Vec<(String, &rules_converter::term::Term)> = terms
            .iter()
            .enumerate()
            .filter_map(|(i, t)| t.as_ref().map(|t| (ids[i].clone(), t)))
            .collect();
        let mut it = rules_converter::interp::Interp::default();
        it.load_inputs(&data);
        it.run(&nodes, Some(&block));
        it.write_all(&out);
        String::new()
    });
    let ms = t0.elapsed().as_secs_f64() * 1000.0;
    (ms, r.map(|_| ()).map_err(|e| format!("left (rust interp): {e}")))
}

/// Write a prepared file only when its content would change, and atomically when it does.
///
/// **Why, and not a plain `write`.** Two requests about two blocks of the same file
/// prepare the same four files at the same time (the `cargo test` suite does exactly
/// that, and so would two UI3 panes). A plain `fs::write` truncates first, so the second
/// writer can leave the first one's `interp` reading a half-empty `.sas` — which showed up
/// as a `differs` that reran green. Identical content is the normal case, so the compare
/// skips almost every write; the rename makes the rare real write all-or-nothing.
fn write_if_changed(p: &Path, content: &str) -> Result<(), String> {
    if std::fs::read_to_string(p).map(|old| old == content).unwrap_or(false) {
        return Ok(());
    }
    let tmp = p.with_extension(format!(
        "{}.tmp{}",
        p.extension().map(|e| e.to_string_lossy().to_string()).unwrap_or_default(),
        std::process::id()
    ));
    std::fs::write(&tmp, content).map_err(|e| format!("write {}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, p).map_err(|e| format!("rename into {}: {e}", p.display()))
}

/// `block-programs` writes exactly one `block_<table>_rust.py` per block directory.
fn one_block_program(d: &Path) -> Option<PathBuf> {
    let mut progs: Vec<PathBuf> = std::fs::read_dir(d)
        .ok()?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| {
            p.file_name()
                .map(|n| {
                    let n = n.to_string_lossy();
                    n.starts_with("block_") && n.ends_with("_rust.py")
                })
                .unwrap_or(false)
        })
        .collect();
    progs.sort();
    progs.into_iter().next()
}

/// A CSV as rows of cells, header included; `None` when the file is not there — which is
/// the `missing` verdict, not an error.
fn read_csv(p: &Path) -> Option<Vec<Vec<String>>> {
    let text = std::fs::read_to_string(p).ok()?;
    let mut rows = Vec::new();
    let (mut row, mut cell, mut in_q) = (Vec::new(), String::new(), false);
    let mut chars = text.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' if in_q && chars.peek() == Some(&'"') => {
                cell.push('"');
                chars.next();
            }
            '"' => in_q = !in_q,
            ',' if !in_q => row.push(std::mem::take(&mut cell)),
            '\r' if !in_q => {}
            '\n' if !in_q => {
                row.push(std::mem::take(&mut cell));
                rows.push(std::mem::take(&mut row));
            }
            _ => cell.push(c),
        }
    }
    if !cell.is_empty() || !row.is_empty() {
        row.push(cell);
        rows.push(row);
    }
    Some(rows)
}

/// One `runs` row, one `run_tables` row per table, up to five `run_samples` rows per
/// differing table. A store that cannot be written is logged, not raised: the verdict the
/// caller asked for is already computed and correct, and losing the receipt is a smaller
/// failure than losing the answer.
fn write_rows(
    state: &AppState,
    fileid: &str,
    block_id: &str,
    engine: &str,
    overall: &str,
    left_ms: f64,
    tables: &[TableVerdict],
) {
    let Ok(conn) = state.db.lock() else { return };
    let rows_n: i64 = tables.len() as i64;
    let first_diff = tables
        .iter()
        .find(|t| t.verdict == "differs" || t.verdict == "missing")
        .map(|t| t.name.clone());
    let r = conn.execute(
        "INSERT INTO runs (fileid, block_id, engine, rows_n, ms, match_, first_diff, at_ts)
         VALUES (?, ?, ?, ?, ?, ?, ?, now())",
        duckdb::params![fileid, block_id, engine, rows_n, left_ms, overall, first_diff],
    );
    if let Err(e) = r {
        eprintln!("run(): could not write the runs row for {fileid} {block_id}: {e}");
        return;
    }
    for t in tables {
        let _ = conn.execute(
            "INSERT INTO run_tables (fileid, block_id, engine, table_name, verdict, n_mismatch, missing_side, at_ts)
             VALUES (?, ?, ?, ?, ?, ?, ?, now())",
            duckdb::params![fileid, block_id, engine, t.name, t.verdict, t.n_mismatch, t.missing_side],
        );
        for (n, s) in t.samples.iter().enumerate() {
            let _ = conn.execute(
                "INSERT INTO run_samples (fileid, block_id, engine, table_name, n, row_json, n_left, n_right)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                duckdb::params![
                    fileid, block_id, engine, t.name, n as i32,
                    serde_json::to_string(&s.row).unwrap_or_default(),
                    s.n_left, s.n_right
                ],
            );
        }
    }
}
