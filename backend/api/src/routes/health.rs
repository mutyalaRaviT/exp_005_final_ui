//! `health` — `GET /api/health`.
//!
//! **Why this exists.** Every later task lands one of plan §6's twelve questions and
//! appends its name to `crate::LANDED`. This route reports the split — landed vs still
//! forwarded to a Python oracle — from `crate::ALL_ROUTES` and `crate::LANDED` alone, so
//! it needs neither the store nor an oracle to answer and is never blocked on either
//! being up.

use axum::response::Json;
use serde_json::{json, Value};

pub async fn health() -> Json<Value> {
    let forwarded: Vec<&str> = crate::ALL_ROUTES
        .iter()
        .copied()
        .filter(|r| !crate::LANDED.contains(r))
        .collect();
    Json(json!({
        "ok": true,
        "landed": crate::LANDED,
        "forwarded": forwarded,
    }))
}
