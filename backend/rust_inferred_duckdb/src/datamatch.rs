//! `datamatch` — the row comparison, in Rust (phase 2, Task 11).
//!
//! **Why this exists.** The verification loop's whole claim rests on one sentence:
//! `output_left == output_right`. Everything else in the slice is plumbing that can only
//! fail loudly; this is the one module where being *too generous* is silent — a
//! comparison that shrugs at a lost duplicate row, or that calls `"5"` and `"5.0"`
//! different, hands back a verdict nobody can trust. `POST /api/run` (Task 12) calls it
//! for every table a block creates.
//!
//! **Inputs → outputs.** two row sets, each a `Vec<Vec<String>>` of CSV cells *without*
//! the header line → `(Verdict, n_mismatch, samples)`, where `n_mismatch` counts row
//! *instances* (duplicates included) that one side has and the other does not, and
//! `samples` names at most `max_samples` of them with each side's count.
//!
//! **Two references, and which one wins.** `raw/bench_stack/pipeline/datamatch.py:158`
//! (Python, the reference for `tools/xcheck_datamatch.py`: if Rust and Python disagree on
//! a real block, Rust is wrong) and `raw/bench_stack/server/datamatch.ts:21` (the Bench's
//! browser copy). They agree everywhere except on the SAS missing value `"."`, which
//! Python passes through unchanged and TypeScript folds into `""`. Task 11's own test
//! asserts `normalize_value(".") == ""`, i.e. the TypeScript law, and a pass mark is
//! never edited to match an implementation (Ruling D13) — so `"."` and `""` are one value
//! here. The only way that could ever diverge from Python on real data is a table where
//! one engine writes `.` for a cell the other leaves empty; the 11-block cross-check
//! shows it does not happen (both write `""`).

use std::collections::BTreeMap;

/// Decimal places every numeric cell is rounded to before comparison — `FLOAT_DP` in both
/// references. Two engines that computed the same value by different routes must not
/// differ on the seventeenth digit.
pub const FLOAT_DP: usize = 6;

/// Cells are joined with a unit separator to key the multiset, exactly as the Python and
/// TypeScript do: no real cell contains `\u{1f}`, so two different rows can never collide
/// into one key.
const SEP: char = '\u{1f}';

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    Pass,
    Fail,
}

impl Verdict {
    /// The wire spelling both references print: `PASS` / `FAIL`.
    pub fn as_str(self) -> &'static str {
        match self {
            Verdict::Pass => "PASS",
            Verdict::Fail => "FAIL",
        }
    }
}

/// One differing row and how many times each side has it. `n_left` / `n_right` are
/// `ref_count` / `conv_count` in the Python.
#[derive(Debug, Clone, serde::Serialize)]
pub struct Sample {
    pub row: Vec<String>,
    pub n_left: i64,
    pub n_right: i64,
}

/// One field → its canonical comparable string.
///
/// Whitespace stripped; the SAS missing value (`.`) and the empty cell are the same
/// value; a numeric string is rounded to `FLOAT_DP` places with integers and whole floats
/// unified (`5` == `5.0` == `5.000000`) and `-0` collapsed to `0`; non-finite numerics
/// collapse to `nan` / `inf` / `-inf` **before** rounding, so that a spelling difference
/// between the engines (`NaN` vs `nan`, `Infinity` vs `inf`) is not read as a data
/// difference while NaN, +Inf and -Inf stay distinct from each other and from every real
/// number; anything else passes through stripped and otherwise untouched.
pub fn normalize_value(s: &str) -> String {
    let s = s.trim();
    if s.is_empty() || s == "." {
        return String::new();
    }
    // Python's `float()` accepts a trailing bare dot ("5."), Rust's parser does not; the
    // two must agree or a SAS-written "5." would compare unequal to Spark's "5.0".
    let parsed = s
        .parse::<f64>()
        .or_else(|_| if s.ends_with('.') { format!("{s}0").parse::<f64>() } else { Err("".parse::<f64>().unwrap_err()) });
    let Ok(f) = parsed else { return s.to_string() };
    if f.is_nan() {
        return "nan".to_string();
    }
    if f.is_infinite() {
        return if f > 0.0 { "inf".into() } else { "-inf".into() };
    }
    // `{:.6}` is a correctly rounded decimal expansion of the double, which is what
    // `format(round(f, 6), ".6f")` produces in Python — including for values far larger
    // than i64, where converting to an integer type first would overflow.
    let t = format!("{f:.FLOAT_DP$}");
    let (int_part, frac) = t.split_once('.').unwrap_or((t.as_str(), ""));
    if frac.bytes().all(|b| b == b'0') {
        // whole after rounding -> the integer spelling; "-0" is 0.
        return if int_part.bytes().all(|b| b == b'0' || b == b'-') { "0".to_string() } else { int_part.to_string() };
    }
    t.trim_end_matches('0').trim_end_matches('.').to_string()
}

fn key(row: &[String]) -> String {
    row.iter().map(|c| normalize_value(c)).collect::<Vec<_>>().join(&SEP.to_string())
}

fn counts(rows: &[Vec<String>]) -> BTreeMap<String, i64> {
    let mut m: BTreeMap<String, i64> = BTreeMap::new();
    for r in rows {
        *m.entry(key(r)).or_insert(0) += 1;
    }
    m
}

fn unkey(k: &str) -> Vec<String> {
    k.split(SEP).map(|s| s.to_string()).collect()
}

/// Multiset row comparison — duplicates count, order does not.
///
/// Returns `(verdict, n_mismatch, samples)`: `n_mismatch` is the total number of row
/// *instances* the two sides disagree about (rows the left has too many of, plus rows the
/// right has too many of), and `samples` is at most `max_samples` of them, missing-side
/// rows first, exactly as `pipeline/datamatch.py:158` orders them.
///
/// A `BTreeMap` rather than the brief's `HashMap`: the counts are identical either way,
/// but ordered keys make the sample list deterministic run to run, which matters because
/// those samples are written into `run_samples` and read back by a human.
pub fn compare_rows(
    left: &[Vec<String>],
    right: &[Vec<String>],
    max_samples: usize,
) -> (Verdict, i64, Vec<Sample>) {
    let l = counts(left);
    let r = counts(right);
    if l == r {
        return (Verdict::Pass, 0, Vec::new());
    }
    let mut n_mismatch = 0i64;
    let mut missing = Vec::new(); // left has more instances
    let mut extra = Vec::new(); // right has more instances
    for (k, &nl) in &l {
        let nr = *r.get(k).unwrap_or(&0);
        if nl > nr {
            n_mismatch += nl - nr;
            missing.push((k.clone(), nl, nr));
        }
    }
    for (k, &nr) in &r {
        let nl = *l.get(k).unwrap_or(&0);
        if nr > nl {
            n_mismatch += nr - nl;
            extra.push((k.clone(), nl, nr));
        }
    }
    let samples = missing
        .into_iter()
        .chain(extra)
        .take(max_samples)
        .map(|(k, n_left, n_right)| Sample { row: unkey(&k), n_left, n_right })
        .collect();
    (Verdict::Fail, n_mismatch, samples)
}
