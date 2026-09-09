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

/// Questions answered from the store today. Empty until Task 5 lands `files`/`search`;
/// each later route task appends to this list as part of landing its route.
pub const LANDED: &[&str] = &[];

/// Build the router from state alone. Called with a real store + real oracle addresses
/// by `main`, and with `test_state()` by every integration test — same router, same
/// handlers, either way.
pub fn app(state: AppState) -> Router {
    Router::new()
        .route("/api/health", get(routes::health::health))
        .with_state(state)
}

/// A throwaway store for tests: a fresh DuckDB file under the OS temp dir, unique per
/// call so parallel test binaries never collide, opened with the same DDL `main` runs
/// against the real store. Oracle addresses are the same defaults `main` uses; nothing
/// in a route landed so far dials them, and a test that needs `oracle::forward` is free
/// to point elsewhere.
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

    let conn = inferred_duckdb::open(&db).expect("open throwaway test store");
    AppState {
        db: std::sync::Arc::new(std::sync::Mutex::new(conn)),
        oracle_a: "http://127.0.0.1:8000".to_string(),
        oracle_b: "http://127.0.0.1:8042".to_string(),
    }
}
