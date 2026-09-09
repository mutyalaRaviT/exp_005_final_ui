//! `lineageq_api` — one HTTP API over the exp_005 store, serving both shipping UIs.
//!
//! **Why this exists.** Phase 2 replaces two Python backends — `app.py` (UI1's server)
//! and `convert_api.py` (the Bench) — with one Rust API reading a single DuckDB store
//! (`docs/plan/silver/silver_phase2_implementation_plan.md`). Routes land one at a time;
//! until a route lands, its handler forwards the question to whichever Python oracle
//! answers it today and translates the reply into canonical shape (`oracle::forward`).
//! `GET /api/health` reports which of the twelve questions in plan §6 are landed and
//! which are still forwarded.
//!
//! **Shape.** `app(state)` builds the router from an `AppState` alone — no globals, no
//! listener — so `main` can serve it over TCP while a test drives the very same router
//! in-process with `tower::ServiceExt::oneshot` (`tests/support/mod.rs`). `test_state()`
//! gives a test a throwaway store instead of the real one, and default oracle addresses
//! that are never dialled unless a test explicitly calls `oracle::forward`.
//!
//! **On `lib.rs` and the test helpers existing at all.** The plan
//! (`docs/plan/silver/silver_phase2_implementation_plan.md`, Task 3) gives the `api`
//! crate a `main.rs` only. Eight later tasks (5–12) each write integration tests calling
//! `get(path)` / `post(path, body)`, and Task 3's own test calls `lineageq_api::app(...)`
//! and `lineageq_api::test_state()` — none of which a binary-only crate can expose, since
//! an integration test cannot link against a binary. This module and
//! `tests/support/mod.rs` exist to make that possible; see the Task 3 report for the
//! ruling this was made under.

pub mod oracle;
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

/// Questions answered from the store today. Task 5 lands `files`/`search`; each later
/// route task appends to this list as part of landing its route. `tests/landed.rs`
/// (Ruling D6) fails loudly if this list and the router in `app()` ever disagree about
/// which routes are actually wired up.
pub const LANDED: &[&str] = &["files", "search", "neighborhood"];

/// Build the router from state alone. Called with a real store + real oracle addresses
/// by `main`, and with `test_state()` by every integration test — same router, same
/// handlers, either way.
pub fn app(state: AppState) -> Router {
    Router::new()
        .route("/api/health", get(routes::health::health))
        .route("/api/files", get(routes::files::files))
        .route("/api/search", get(routes::search::search))
        .route("/api/neighborhood", get(routes::neighborhood::neighborhood))
        .route("/bench", get(routes::bench::bench))
        // Ruling 5 (2026-09-09, Task 5 fix round 1): every other `/api/*` path forwards
        // to oracle_a instead of 404ing — see `routes::forward` for why a fallback and
        // not nine more named routes. Landing a route for real still means moving its
        // name into `LANDED` and adding its own `.route()` above, same as always.
        .fallback(routes::forward::fallback)
        .with_state(state)
}

/// A throwaway store for tests: a fresh DuckDB file under the OS temp dir, unique per
/// call so parallel test binaries never collide, opened with the same DDL `main` runs
/// against the real store, and seeded from `corpus/team_finance/` — the corpus root, not
/// a single language subfolder. `inferred_duckdb::convert` sets each file's `fileid` to
/// its path relative to the seeded folder, so seeding the root yields fileids of the form
/// `sas/raw/<name>.sas`, and `collect_sas`'s `.sas`-only filter skips the `.hql` files
/// under `hive/raw` and every `.py` under the later `auto_convert`/`work`/`final_match`
/// stages — the store still ends up with exactly the 25 raw SAS files. Oracle addresses
/// are the same defaults `main` uses; nothing landed so far dials them, and a test that
/// needs `oracle::forward` is free to point elsewhere.
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

    let mut conn = inferred_duckdb::open(&db).expect("open throwaway test store");
    let spec = std::path::Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../raw/bench_stack/out/spec/sas.json"
    ));
    let folder = std::path::Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../corpus/team_finance"
    ));
    inferred_duckdb::convert(&mut conn, spec, folder)
        .expect("seed the team_finance corpus into the test store");

    AppState {
        db: std::sync::Arc::new(std::sync::Mutex::new(conn)),
        oracle_a: "http://127.0.0.1:8000".to_string(),
        oracle_b: "http://127.0.0.1:8042".to_string(),
    }
}
