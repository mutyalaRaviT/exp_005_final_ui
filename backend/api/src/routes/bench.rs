//! `GET /bench` — redirects to UI2's own origin; it is not served from here.
//!
//! **Ruling 6 (2026-09-09, final review fix wave).** One door for UI2 is not achievable
//! in this plan: UI1 and the Bench both define `/api/files`, with different response
//! shapes, so one origin cannot answer both until the Bench's own routes land in Rust
//! (phase C) or are renamed under a prefix (editing the 1,300-line `bench.html`,
//! explicitly out of scope here). This route used to read and serve `bench.html`'s bytes
//! directly from :8110 (see git history for that version), which put the page behind this
//! origin while every one of its 13 distinct `/api/*` calls (`open`, `similar`,
//! `listing`, `files`, `sessions`, `save`, `run_block`, `file`, `folder`, `exec`, `term`,
//! `session` — several of them POSTs) still had nowhere to land here and nothing forwarded
//! them to `oracle_b`. That shipped a page whose data calls could not work — a false "one
//! door" claim. Redirecting instead keeps a single well-known entry point (`:8110/bench`
//! always gets you to the Bench) without pretending :8110 answers its questions.
//!
//! **Inputs → outputs.** no inputs → `302 Found` with `Location: {oracle_b}/bench`, where
//! `oracle_b` is `AppState::oracle_b` (default `http://127.0.0.1:8042`), never hardcoded.

use crate::types::AppState;
use axum::extract::State;
use axum::http::{header, StatusCode};
use axum::response::IntoResponse;

pub async fn bench(State(state): State<AppState>) -> impl IntoResponse {
    let location = format!("{}/bench", state.oracle_b);
    (StatusCode::FOUND, [(header::LOCATION, location)])
}
