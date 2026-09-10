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

/// One cross-file block-to-block link — matches UI1's `BlockLink`
/// (`raw/node4_viz/src/api.ts:62`) field for field. `src_ref`/`dst_ref` identify the table
/// occurrence inside each block; see `routes::blocklinks` for why this store's refs are
/// `"<block_id>:<table>"` and not `:8000`'s `t_<n>` token numbering.
#[derive(Debug, Clone, Serialize)]
pub struct BlockLink {
    pub src_file: String,
    pub src_block: String,
    pub src_ref: String,
    pub dst_file: String,
    pub dst_block: String,
    pub dst_ref: String,
    pub table: String,
}

/// One row of `GET /api/edges` — matches UI1's `EdgeRow` (`api.ts:76`). `block_id` is
/// `None` for a row that has no single block behind it (a project-level roll-up, or a
/// human edit made at file/project level), which is what UI1 reads as `null`.
#[derive(Debug, Clone, Serialize)]
pub struct EdgeRow {
    pub fileid: String,
    pub block_id: Option<String>,
    pub src: String,
    pub dst: String,
    pub tables: Vec<String>,
    pub level: String,
    pub provenance: String,
    pub freshness: String,
}
