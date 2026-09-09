//! `types` — the shapes every handler shares.
//!
//! **Why this exists.** `AppState` is the one thing every route needs: the store
//! connection, and where to forward a question whose route has not landed yet. It is
//! built once — against the real store in `main`, against a throwaway one in
//! `test_state()` — and threaded through `axum::Router::with_state`. As routes land,
//! this module also grows the canonical JSON wire shapes mirroring UI1's `src/api.ts`
//! (plan §6); nothing needs one yet, so it holds only `AppState` today.

use duckdb::Connection;
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
