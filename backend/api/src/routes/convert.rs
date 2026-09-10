//! `convert` — `POST /api/convert {folder}` or `{file}`: the twelfth question, and the
//! only one that writes.
//!
//! **Why this exists.** Every other route reads rows somebody else put in the store. This
//! is where they come from: fold a folder of SAS once, write the eight tables, and from
//! then on every question the two UIs ask is a keyed read (`inferred_duckdb`'s own doc
//! comment; exp_42 folded a file on every open — 63.4 s for `big_1000.sas`). Until today
//! the only way to fill the store was the `lineageq_store` binary on a terminal, so a
//! desktop build had no way to point at a folder.
//!
//! **Synchronous, and no stream.** Plan §6 says `convert()` "streams `block ready`
//! events". Nothing in this slice consumes them — the spec's own OPEN item — so this
//! returns the `ConvertReport` when the work is done rather than inventing an SSE channel
//! that no client reads (Task 6b, step 3). When a UI wants progress, the shape to build is
//! decided by that UI, not guessed here.
//!
//! **A convert blocks reads, on purpose.** The handler takes the store mutex for the whole
//! call, which is the sharp end of the spec's OPEN question about one connection versus
//! one per thread. It is the honest behaviour: a convert deletes and rewrites a file's rows
//! inside a transaction, and a `file()` served from the middle of that would be answering
//! from a half-rewritten store. Measured over HTTP on this machine (release build, an
//! empty store, `GET /api/files` polled every 20 ms throughout): `corpus/team_finance`
//! (25 files, 26 blocks) held the lock **106.5 ms** and the worst concurrent read waited
//! 81.3 ms; `corpus/perf/big_2000.sas` (one file, 2000 blocks) held it **2353.1 ms** and
//! the worst read waited 2328.4 ms. A second convert of either, unchanged, holds it for
//! 5.2 ms and 1.3 ms. No read failed in any of the four; they wait, they do not error.
//! Two and a half seconds of blocked reads on a 2000-block file is the honest cost of one
//! connection, and the number a later slice would have to beat to justify a pool.
//!
//! **Idempotent.** `inferred_duckdb::convert` skips a file whose `files.hash` and the
//! store's `spec_hash` are both unchanged, so converting the same folder twice writes zero
//! blocks the second time. `tests/convert.rs` asserts exactly that, because a reconvert
//! that rewrote everything would throw away the `runs` history and the human edits pinned
//! to a `block_hash` (M7) for no reason.
//!
//! **No oracle.** `:8042 /api/convert` is a different question with a different shape (the
//! Bench converts one open file for its own editor), and `:8000` has no such route at all.
//! This is new surface, not a replacement, so it lands undiffed — the one honest reason a
//! route may (plan Task 6b step 5), recorded as `no oracle — new surface` in
//! `docs/plan/bronze/bronze_phase2_route_ledger.md`.
//!
//! **Inputs → outputs.** `{folder}` or `{file}` (a path, absolute or relative to the repo
//! root) → `{files, ok, failed, blocks, node4, edges, fold_ms, store_ms, total_ms}`, the
//! `ConvertReport` `inferred_duckdb` already returns, plus `lock_ms`: how long the store
//! was held, which is how long reads waited.

use crate::spawn;
use crate::types::AppState;
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::path::PathBuf;

#[derive(Deserialize)]
pub struct ConvertBody {
    /// A folder to walk for `.sas` files. Mutually exclusive with `file`.
    #[serde(default)]
    pub folder: Option<String>,
    /// A single `.sas` file. `inferred_duckdb::collect_sas` accepts a file as well as a
    /// directory, so the two arrive at the same call.
    #[serde(default)]
    pub file: Option<String>,
}

pub async fn convert(
    State(state): State<AppState>,
    Json(body): Json<ConvertBody>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let target = match (
        body.folder.as_deref().map(str::trim).filter(|s| !s.is_empty()),
        body.file.as_deref().map(str::trim).filter(|s| !s.is_empty()),
    ) {
        (Some(_), Some(_)) => {
            return Err((StatusCode::BAD_REQUEST, "convert(): give folder or file, not both".into()))
        }
        (Some(f), None) | (None, Some(f)) => f.to_string(),
        (None, None) => {
            return Err((StatusCode::BAD_REQUEST, "convert(): folder or file is required".into()))
        }
    };

    let path = resolve(&target);
    if !path.exists() {
        return Err((StatusCode::NOT_FOUND, format!("convert(): no such path {target}")));
    }
    let spec_path = spawn::bench_root().join("out/spec/sas.json");
    if !spec_path.exists() {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("convert(): the SAS spec is missing at {}", spec_path.display()),
        ));
    }

    // The lock is taken here and held until the report is built: see the module comment.
    let t_lock = std::time::Instant::now();
    let mut conn = state
        .db
        .lock()
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let rep = inferred_duckdb::convert(&mut conn, &spec_path, &path)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("convert(): {e}")))?;
    let lock_ms = t_lock.elapsed().as_secs_f64() * 1000.0;
    drop(conn);

    Ok(Json(json!({
        "files": rep.files,
        "ok": rep.ok,
        "failed": rep.failed,
        "blocks": rep.blocks,
        "node4": rep.node4,
        "edges": rep.edges,
        "fold_ms": rep.fold_ms,
        "store_ms": rep.store_ms,
        "total_ms": rep.total_ms,
        // How long every other route waited on the store mutex. Reported rather than
        // hidden: it is the number the spec's one-connection question turns on.
        "lock_ms": lock_ms,
    })))
}

/// A relative path is read from the repo root, not from whatever directory the binary was
/// started in — `main` is routinely run from `backend/`, and a caller asking for
/// `corpus/team_finance` means the one in the repo either way.
fn resolve(target: &str) -> PathBuf {
    let p = PathBuf::from(target);
    if p.is_absolute() {
        return p;
    }
    let root = PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."));
    let from_root = root.join(&p);
    if from_root.exists() {
        from_root
    } else {
        p
    }
}
