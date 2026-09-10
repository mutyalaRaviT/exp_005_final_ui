//! `spawn` — the one place this API starts an external process (phase 2, Task 12).
//!
//! **Why this exists.** `POST /api/run` is the only route that cannot be answered from
//! the store: three of its four steps are other programs — the Z3 row generator
//! (`raw/bench_stack/loops/gen_block_testdata.py`, Decision D1: shelled out, not ported),
//! the engine binary (`lineageq_sas block-programs` / `interp`, or `swipl
//! codegen/sas_interp.pl` when the left side is Prolog, Decision D6) and one PySpark
//! program on local Spark (Decision D4). All four need the same three things right, and
//! getting any of them wrong fails in a way that is hard to read from a stack trace:
//!
//! * **cwd `raw/bench_stack`** — every one of those programs resolves its own paths
//!   (`out/spec/sas.json`, `codegen/…`, `.venv/…`) relative to that directory, exactly as
//!   `server/bench_api.py::sh` does with `cwd=ROOT`.
//! * **`JAVA_HOME`** — pyspark 4.2.0 needs Java 17; the machine's default JDK is not it
//!   (repo `CLAUDE.md`).
//! * **`LINEAGEQ_OUT`** — the generated PySpark writes its tables to whatever directory
//!   this names. Without it, the right-hand side of the comparison lands somewhere the
//!   comparison never looks and every table reads as `missing`.
//!
//! **And a timeout.** A route that hangs is worse than a route that fails: axum has no
//! per-request deadline, so a wedged Spark JVM would hold the request forever and the
//! caller would learn nothing. Every child here is killed at `timeout`, and a killed
//! child is reported as a normal, structured failure (`Out::timed_out`), never a panic.
//!
//! **Inputs → outputs.** a program, its arguments and an optional `LINEAGEQ_OUT` → the
//! child's exit code, stdout and stderr, its wall time in ms, and whether it was killed.

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};

/// Java 17, as the repo `CLAUDE.md` and `bench_api.py` both pin it. `JAVA_HOME_17` in the
/// environment overrides, which is how `bench_api` lets a machine with a different layout
/// run the same code.
pub fn java_home() -> String {
    std::env::var("JAVA_HOME_17")
        .unwrap_or_else(|_| "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home".to_string())
}

/// `raw/bench_stack` — the working directory every shelled-out program expects.
/// `LINEAGEQ_BENCH_ROOT` overrides it (a test on a copied tree, a future move out of
/// `raw/`); otherwise it is resolved from this crate's own location, so the API answers
/// the same wherever it is started from.
pub fn bench_root() -> PathBuf {
    if let Ok(p) = std::env::var("LINEAGEQ_BENCH_ROOT") {
        return PathBuf::from(p);
    }
    PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack"))
}

/// The Python that has z3 and pyspark in it. Not the system `python3`, which has neither.
pub fn bench_python() -> PathBuf {
    bench_root().join(".venv/bin/python")
}

/// This repo's own engine binary — `rust_rules_converter`, with M3a's five fixes in it —
/// not `raw/bench_stack/rust_engine`'s exp_42 copy.
pub fn engine_bin() -> PathBuf {
    if let Ok(p) = std::env::var("LINEAGEQ_SAS") {
        return PathBuf::from(p);
    }
    PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../target/release/lineageq_sas"))
}

/// What one child process left behind.
#[derive(Debug, Clone)]
pub struct Out {
    pub code: i32,
    pub stdout: String,
    pub stderr: String,
    pub ms: f64,
    /// True when the child was killed at the deadline rather than exiting on its own.
    pub timed_out: bool,
}

impl Out {
    pub fn ok(&self) -> bool {
        self.code == 0 && !self.timed_out
    }

    /// A short, readable reason a step failed — the last few lines of whatever the child
    /// said, with Spark's log noise dropped. This is what ends up in the route's
    /// `message`, so it has to be a sentence a person can act on, not 400 lines of log4j.
    pub fn why(&self, what: &str) -> String {
        if self.timed_out {
            return format!("{what}: timed out after {:.0} ms", self.ms);
        }
        let noise = |l: &&str| {
            let l = *l;
            l.contains("WARN") || l.contains("setLogLevel") || l.contains("log4j") || l.starts_with("[Stage ")
        };
        let tail: Vec<&str> = self
            .stderr
            .lines()
            .chain(self.stdout.lines())
            .filter(|l| !l.trim().is_empty() && !noise(l))
            .collect();
        let n = tail.len().saturating_sub(6);
        format!("{what}: exit {} — {}", self.code, tail[n..].join(" | "))
    }
}

/// Run one program under `raw/bench_stack` and wait for it, with a deadline.
///
/// `out_dir` becomes `LINEAGEQ_OUT` when given — the directory the generated PySpark
/// writes its CSVs to. The parent environment is inherited (the venv's Python needs it),
/// with `JAVA_HOME` forced to 17.
pub async fn run(
    program: &Path,
    args: &[String],
    out_dir: Option<&Path>,
    timeout: Duration,
) -> std::io::Result<Out> {
    let mut cmd = tokio::process::Command::new(program);
    cmd.args(args)
        .current_dir(bench_root())
        .env("JAVA_HOME", java_home())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        // The children outlive a dropped future only long enough to be killed; without
        // this a cancelled request would leak a Spark JVM per call.
        .kill_on_drop(true);
    if let Some(d) = out_dir {
        cmd.env("LINEAGEQ_OUT", d);
    }
    let t0 = Instant::now();
    let child = cmd.spawn()?;
    match tokio::time::timeout(timeout, child.wait_with_output()).await {
        Ok(res) => {
            let o = res?;
            Ok(Out {
                code: o.status.code().unwrap_or(-1),
                stdout: String::from_utf8_lossy(&o.stdout).to_string(),
                stderr: String::from_utf8_lossy(&o.stderr).to_string(),
                ms: t0.elapsed().as_secs_f64() * 1000.0,
                timed_out: false,
            })
        }
        // `wait_with_output` owns the child, so the timeout branch cannot call `kill()` on
        // it by name — `kill_on_drop(true)` above is what actually stops it when the
        // future is dropped here.
        Err(_) => Ok(Out {
            code: -1,
            stdout: String::new(),
            stderr: String::new(),
            ms: t0.elapsed().as_secs_f64() * 1000.0,
            timed_out: true,
        }),
    }
}
