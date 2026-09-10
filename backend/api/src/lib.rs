//! `lineageq_api` — one HTTP API over the exp_005 store, fully serving UI1 and pointing
//! UI2 (the Bench) at its own origin.
//!
//! **Why this exists.** Phase 2 replaced two Python backends — `app.py` (UI1's server)
//! and `convert_api.py` (the Bench) — with one Rust API reading a single DuckDB store
//! (`docs/plan/silver/silver_phase2_implementation_plan.md`). Routes landed one at a
//! time, forwarding to whichever Python oracle answered them until they did. Task 14
//! (M4b) closed that: all twelve questions are answered from the store, `oracle.rs` and
//! the `/api/*` fallback are deleted, and no Python process is involved in any answer.
//! `GET /api/health` still reports the twelve, with nothing forwarded.
//!
//! **One door, for both windows (Decision D17, M4b).** UI1 and the Bench both define
//! `/api/files` with different shapes, which is why Ruling 6 (2026-09-09) made `/bench` a
//! 302 rather than serving the page. D17 took the other branch: UI2's five Bench-only
//! questions live under `/api/bench/`, where the names cannot collide, so `/bench` serves
//! the extracted page from this origin again — see `routes::bench`.
//!
//! **Shape.** `app(state)` builds the router from an `AppState` alone — no globals, no
//! listener — so `main` can serve it over TCP while a test drives the very same router
//! in-process with `tower::ServiceExt::oneshot` (`tests/support/mod.rs`). `test_state()`
//! gives a test a throwaway store instead of the real one.
//!
//! **On `lib.rs` and the test helpers existing at all.** The plan
//! (`docs/plan/silver/silver_phase2_implementation_plan.md`, Task 3) gives the `api`
//! crate a `main.rs` only. Eight later tasks (5–12) each write integration tests calling
//! `get(path)` / `post(path, body)`, and Task 3's own test calls `lineageq_api::app(...)`
//! and `lineageq_api::test_state()` — none of which a binary-only crate can expose, since
//! an integration test cannot link against a binary. This module and
//! `tests/support/mod.rs` exist to make that possible; see the Task 3 report for the
//! ruling this was made under.

pub mod spawn;
pub mod routes;
pub mod types;

pub use types::AppState;

use axum::{routing::get, Router};

/// Every question the API answers — plan §6's ten plus the two the route tasks split
/// out of it (`files`, the listing that `search` and `neighborhood` build on; `source`,
/// the raw-text read `file()` deliberately excludes). Grows only by the route tasks
/// (5, 6, 6b, 7, 8, 9, 10, 12) moving a name from here into `LANDED` — never by adding a
/// name that has no route.
pub const ALL_ROUTES: &[&str] = &[
    "files",
    "search",
    "neighborhood",
    "convert",
    "blocklinks",
    "edges",
    "source",
    "file",
    "blocks",
    "tablegraph",
    "story",
    "run",
];

/// Questions answered from the store. Task 5 landed `files`/`search`; each later route
/// task appended to this list as part of landing its route, Task 6b (M4a) closed it, and
/// Task 14 (M4b) deleted the forwarder that used to answer the rest. `LANDED` and
/// `ALL_ROUTES` hold the same names and always will. `tests/landed.rs` (Ruling D6) fails
/// loudly if this list and the router in `app()` ever disagree about which routes are
/// actually wired up.
pub const LANDED: &[&str] =
&[
    "files", "search", "neighborhood", "convert", "blocklinks", "edges", "source", "file",
    "blocks", "tablegraph", "story", "run",
];

/// Build the router from state alone. Called with the real store by `main`, and with
/// `test_state()` by every integration test — same router, same handlers, either way.
pub fn app(state: AppState) -> Router {
    Router::new()
        .route("/api/health", get(routes::health::health))
        .route("/api/files", get(routes::files::files))
        .route("/api/search", get(routes::search::search))
        .route("/api/neighborhood", get(routes::neighborhood::neighborhood))
        .route("/api/blocklinks", get(routes::blocklinks::blocklinks))
        .route("/api/edges", get(routes::edges::edges))
        .route("/api/source", get(routes::source::source))
        .route("/api/file", get(routes::file::file))
        // UI1 has always asked for `/api/file/<fileid>` — a different answer on a different
        // path, not `file()` with a path parameter. See `routes::file`'s doc comment; it is
        // finding G7 (UI1's `could not load blocks` banner with the Python oracle dead).
        .route("/api/file/*fileid", get(routes::file::file_detail))
        .route("/api/blocks", get(routes::blocks::blocks))
        .route("/api/tablegraph", get(routes::tablegraph::tablegraph))
        .route("/api/story", get(routes::story::story))
        // Task 12: the only POST among the twelve, and the only route that runs other
        // programs rather than reading the store — see `routes::run`.
        .route("/api/run", axum::routing::post(routes::run::run))
        // Task 6b (M4a): the twelfth question and the only one that writes. POST, like
        // `run`, and it takes the store mutex for the whole call — see `routes::convert`.
        .route("/api/convert", axum::routing::post(routes::convert::convert))
        // Decision D17 (M4b): `/bench` serves the extracted page again, and the five
        // Bench-only questions land beside it under `/api/bench/` where they cannot
        // collide with UI1's names — see `routes::bench`.
        .route("/bench", get(routes::bench::bench))
        .route("/api/bench/files", get(routes::bench::files))
        .route("/api/bench/folder", get(routes::bench::folder))
        .route("/api/bench/similar", get(routes::bench::similar))
        .route("/api/bench/listing", get(routes::bench::listing))
        .route("/api/bench/save", axum::routing::post(routes::bench::save))
        .with_state(state)
}

/// A throwaway store for tests: a fresh DuckDB file under the OS temp dir, unique per
/// call so parallel test binaries never collide, opened with the same DDL `main` runs
/// against the real store, and seeded from `corpus/team_finance/` — the corpus root, not
/// a single language subfolder. `inferred_duckdb::convert` sets each file's `fileid` to
/// its path relative to the seeded folder, so seeding the root yields fileids of the form
/// `sas/raw/<name>.sas`, and `collect_sas`'s `.sas`-only filter skips the `.hql` files
/// under `hive/raw` and every `.py` under the later `auto_convert`/`work`/`final_match`
/// stages — the store still ends up with exactly the 25 raw SAS files.
///
/// **Why seeded, not empty.** `support::get`/`post` (`tests/support/mod.rs`) each call
/// this function fresh and drive the router they build from it — there is no way for a
/// test to reach into that router's state and convert a corpus into it first. Task 6's
/// own brief writes `get("/api/neighborhood?file=sas%2Fraw%2F11_branch_rollup.sas&up=1
/// &down=1")` with no setup step of its own and expects real data back, so the seeding has
/// to live here for every route task from this one on to have anything to answer with.
/// Only `team_finance`: it is what `files`/`search`/`neighborhood`/`blocklinks`/`edges`
/// (Tasks 5–7) are checked against, and it converts in well under 100 ms. The `exp42`
/// corpus routes need (Tasks 8–10) include `big_2000.sas`; converting that on every single
/// `get()`/`post()` call — one per assertion, not per test file — would make every later
/// test suite slow for no benefit to this one. Whichever of those tasks needs `exp42` data
/// seeds it the same way, here, when it lands.
pub fn test_state() -> AppState {
    let (mut conn, spec) = fresh_store();
    let folder = std::path::Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../corpus/team_finance"
    ));
    inferred_duckdb::convert(&mut conn, spec, folder)
        .expect("seed the team_finance corpus into the test store");
    seed_human_edits(&conn);
    AppState { db: std::sync::Arc::new(std::sync::Mutex::new(conn)) }
}

/// Load `tests/fixtures/human_edits.json` into a freshly seeded test store.
///
/// **Why this exists (Task 7, 2026-09-10).** `edges()` answers the merged view — inferred
/// rows with un-flagged customer edits applied — and its pass mark
/// (`tests/edges.rs::dashboard_mart_has_twenty_five_edges`, the owner's 2026-09-09 "25 / 25
/// with one HUMAN_GOLD row" screenshot) can only be met if a customer edit exists to merge.
/// `convert` never writes one: a human edit is not something folding a folder can infer.
/// The fixture is the `human_edits` table of the oracle store this corpus's answers are
/// checked against (`raw/lineage_server/output/explorer.duckdb`, exported verbatim,
/// **1 row** — an `action='correct'` project-level assertion that
/// `09_customer_summary.sas` feeds `18_dashboard_mart.sas` through `work.cust_summary`),
/// so both engines merge exactly the same assertions and `diff_route.py edges` compares
/// like with like. Its `src`/`dst` still carry the pre-Task-5 `ankitha_1/` fileids: that is
/// what the row says on both sides, and rewriting it here would make the two answers differ
/// for no reason but tidiness.
///
/// A missing or unparseable fixture is a panic, not a silent skip: a test store quietly
/// without its edits would fail the pass mark with a number nobody could explain.
fn seed_human_edits(conn: &duckdb::Connection) {
    let path = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures/human_edits.json"));
    let text = std::fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("read {}: {e}", path.display()));
    let edits: Vec<inferred_duckdb::HumanEdit> =
        serde_json::from_str(&text).unwrap_or_else(|e| panic!("parse {}: {e}", path.display()));
    for e in &edits {
        inferred_duckdb::insert_human_edit(conn, e).expect("seed one human edit");
    }
}

/// Like `test_state()`, but seeded from `corpus/fixtures` instead of `corpus/team_finance`.
///
/// **Why a second state and not one more `convert` into the first (Task 9, 2026-09-10).**
/// `convert` does append — it clears and rewrites only the fileids under the folder it is
/// given — so seeding both corpora into one connection works, and was tried first. It
/// breaks `tests/files.rs::returns_all_25_team_finance_files_with_exactly_id_label_folder`,
/// which counts what `/api/files` returns: 26 rows, not 25. That count is Task 5's stated
/// answer for this corpus, and Ruling D13 says a pass mark is never edited to match an
/// implementation, so the fixture gets its own store instead. The two corpora also answer
/// two different oracles while those existed (`:8000` for team_finance, the Bench for the
/// fixture); keeping them in separate stores keeps that separation visible.
///
/// The fixture's fileid here is the bare `test_vishnu_testdata_fixed.sas` — `convert` takes
/// a fileid from the path relative to the folder it is pointed at, and `corpus/fixtures` is
/// converted as its own root, exactly as `tools/diff_route.py`'s `exp42_files()` documents.
/// `corpus/perf`'s `big_*.sas` are deliberately not seeded: the perf pass marks are measured
/// over HTTP against a store built for them, not in this suite.
pub fn test_state_fixtures() -> AppState {
    let (mut conn, spec) = fresh_store();
    let folder = std::path::Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../corpus/fixtures"
    ));
    inferred_duckdb::convert(&mut conn, spec, folder)
        .expect("seed the exp42 fixture into the test store");
    AppState { db: std::sync::Arc::new(std::sync::Mutex::new(conn)) }
}

/// A fresh, empty store under the OS temp dir plus the spec path both seeders convert with.
/// Shared by `test_state` and `test_state_fixtures` so the two can never drift
/// apart on DDL, spec, or naming.
fn fresh_store() -> (duckdb::Connection, &'static std::path::Path) {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);

    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    let pid = std::process::id();
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let db = std::env::temp_dir().join(format!("lineageq_api_test_{pid}_{nanos}_{n}.duckdb"));
    let _ = std::fs::remove_file(&db);
    let conn = inferred_duckdb::open(&db).expect("open throwaway test store");
    let spec = std::path::Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../raw/bench_stack/out/spec/sas.json"
    ));
    (conn, spec)
}

