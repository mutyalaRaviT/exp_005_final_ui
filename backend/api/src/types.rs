//! `types` — the shapes every handler shares.
//!
//! **Why this exists.** `AppState` is the one thing every route needs: the store
//! connection, and where to forward a question whose route has not landed yet. It is
//! built once — against the real store in `main`, against a throwaway one in
//! `test_state()` — and threaded through `axum::Router::with_state`. As routes land,
//! this module also grows the canonical JSON wire shapes mirroring UI1's `src/api.ts`
//! (plan §6). Task 5 is the first to need one: `FileRow` (`api.ts:74`) and `SearchHit`
//! (`api.ts:73`).

use duckdb::Connection;
use serde::Serialize;
use std::sync::{Arc, Mutex};

/// State shared by every handler. `db` is behind a `Mutex` because `duckdb::Connection`
/// is `!Sync`; every handler that touches the store takes the lock for the length of one
/// query. `oracle_a` / `oracle_b` are the two Python servers being replaced (UI1's
/// backend, default `http://127.0.0.1:8000`; the Bench, default `http://127.0.0.1:8042`)
/// — a route not yet landed forwards to whichever of the two answers its question.
#[derive(Clone)]
pub struct AppState {
    pub db: Arc<Mutex<Connection>>,
    pub oracle_a: String,
    pub oracle_b: String,
}

/// One row of `GET /api/files` — matches UI1's `FileRow` (`raw/node4_viz/src/api.ts:74`)
/// exactly: `id` is the fileid, `label` its basename, `folder` its dirname.
#[derive(Debug, Clone, Serialize)]
pub struct FileRow {
    pub id: String,
    pub label: String,
    pub folder: String,
}

/// One row of `GET /api/search` — matches UI1's `SearchHit` (`api.ts:73`). `files` lists
/// every file `value` appears in, not just where it was first written.
#[derive(Debug, Clone, Serialize)]
pub struct SearchHit {
    pub kind: &'static str, // "table" | "file"
    pub value: String,
    pub files: Vec<String>,
}
