//! `blocks` — `GET /api/blocks?fileid=&from=&to=`.
//!
//! **Why this exists.** The other half of the split `file()` describes: this is the route
//! that ships text, and it ships only the window asked for. `from`/`to` are a half-open
//! range over the store's own 0-based `blocks.n` (`inferred_duckdb::blocks`), the same `n`
//! `file()` prints, so a UI that has the header can ask for exactly the rows it is about to
//! draw. That is the whole mechanism behind phase 3's "open `big_1000.sas` to first cell in
//! under a second" pass mark.
//!
//! **Wire shape** (Task 9 brief): a bare list of
//! `{id,n,kind,name,lines,sas,py,py_pretty,warn,reads,writes,terms}`. The brief's interface
//! line names the first nine; `warn`, `reads` and `writes` are carried too because
//! `tools/diff_route.py`'s `blocks` branch compares them against the Bench and because a
//! consumer that reads one window should not have to re-fetch `file()` to learn whether the
//! block it is drawing warned.
//!
//! **`py` and `py_pretty` are two different things.** `py` is `emit()`'s output — the
//! PySpark the Bench also produces, and the only one there is an oracle for. `py_pretty` is
//! `emit_pretty()`'s, this phase's own rendering, which the Bench structurally cannot have;
//! `diff_route.py` projects it off both sides rather than reporting it missing on every
//! block of every file.
//!
//! **Inputs → outputs.** `blocks`, `node4`, `edges` + a fileid and a window → that window's
//! blocks with their text.

use crate::routes::file::block_reads;
use crate::types::AppState;
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

/// `blocks()` with no window is the whole file — the same default the Bench's own
/// whole-program `/api/open` has, so a caller that has not decided on a window yet is not
/// silently handed an empty list.
const DEFAULT_TO: i64 = i64::MAX;

#[derive(Deserialize)]
pub struct BlocksParams {
    #[serde(default)]
    fileid: String,
    #[serde(default)]
    from: Option<i64>,
    #[serde(default)]
    to: Option<i64>,
}

pub async fn blocks(
    State(state): State<AppState>,
    Query(params): Query<BlocksParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let fileid = params.fileid.trim().to_string();
    if fileid.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "blocks(): fileid is required".into()));
    }
    let ise = |e: String| (StatusCode::INTERNAL_SERVER_ERROR, e);
    let from = params.from.unwrap_or(0);
    let to = params.to.unwrap_or(DEFAULT_TO);

    let conn = state.db.lock().map_err(|e| ise(e.to_string()))?;
    let window = inferred_duckdb::blocks(&conn, &fileid, from, to).map_err(|e| ise(e.to_string()))?;

    // `reads`/`writes` are per block, computed the same way `file()` computes them (the
    // Bench's own rule) — over the *whole* file's heads, because a block that makes nothing
    // falls back to its node/4 terms and needs to know it makes nothing.
    let heads = match inferred_duckdb::file(&conn, &fileid) {
        Ok(a) => a.blocks,
        Err(e) if e.to_string().contains("no rows") || e.to_string().contains("NoRows") => {
            return Err((StatusCode::NOT_FOUND, format!("blocks(): no such fileid {fileid}")))
        }
        Err(e) => return Err(ise(e.to_string())),
    };
    let reads = block_reads(&conn, &fileid, &heads).map_err(|e| ise(e.to_string()))?;
    let terms = block_terms(&conn, &fileid).map_err(|e| ise(e.to_string()))?;
    let py = block_py(&conn, &fileid).map_err(|e| ise(e.to_string()))?;
    let warns = block_warn_flags(&conn, &fileid).map_err(|e| ise(e.to_string()))?;
    drop(conn);

    let out: Vec<Value> = window
        .iter()
        .map(|b| {
            let writes: Option<&str> = if b.name.is_empty() { None } else { Some(b.name.as_str()) };
            json!({
                "id": b.block_id,
                "n": b.n,
                "kind": b.kind,
                "name": b.name,
                "lines": format!("{}-{}", b.l0, b.l1),
                "sas": b.sas_text,
                "py": py.get(&b.block_id).cloned().unwrap_or_default(),
                "py_pretty": b.py_pretty,
                "warn": crate::routes::file::warn_text_pub(warns.get(&b.block_id).copied().unwrap_or(false)),
                "reads": reads.get(&b.block_id).cloned().unwrap_or_default(),
                "writes": writes,
                "terms": terms.get(&b.block_id).cloned().unwrap_or_default(),
            })
        })
        .collect();

    Ok(Json(Value::Array(out)))
}

/// The printed node/4 terms of every block of one file, in `seq` order — the Bench's
/// `blocks[].terms`, which is what its own `terms` list is built from.
fn block_terms(
    conn: &duckdb::Connection,
    fileid: &str,
) -> Result<BTreeMap<String, Vec<String>>, duckdb::Error> {
    let mut st = conn.prepare("SELECT block_id, term FROM node4 WHERE fileid = ? ORDER BY seq")?;
    let mut rows = st.query(duckdb::params![fileid])?;
    let mut out: BTreeMap<String, Vec<String>> = BTreeMap::new();
    while let Some(r) = rows.next()? {
        out.entry(r.get(0)?).or_default().push(r.get(1)?);
    }
    Ok(out)
}

/// `blocks.py_text` — `emit()`'s PySpark, the half that has an oracle. Not on
/// `inferred_duckdb::BlockFull` (which carries `py_pretty`), and adding it there would
/// change an existing struct, so it is read here.
fn block_py(
    conn: &duckdb::Connection,
    fileid: &str,
) -> Result<BTreeMap<String, String>, duckdb::Error> {
    let mut st = conn.prepare("SELECT block_id, py_text FROM blocks WHERE fileid = ?")?;
    let mut rows = st.query(duckdb::params![fileid])?;
    let mut out = BTreeMap::new();
    while let Some(r) = rows.next()? {
        out.insert(r.get(0)?, r.get::<_, Option<String>>(1)?.unwrap_or_default());
    }
    Ok(out)
}

fn block_warn_flags(
    conn: &duckdb::Connection,
    fileid: &str,
) -> Result<BTreeMap<String, bool>, duckdb::Error> {
    let mut st = conn.prepare("SELECT block_id, warn FROM blocks WHERE fileid = ?")?;
    let mut rows = st.query(duckdb::params![fileid])?;
    let mut out = BTreeMap::new();
    while let Some(r) = rows.next()? {
        out.insert(r.get(0)?, r.get::<_, Option<bool>>(1)?.unwrap_or(false));
    }
    Ok(out)
}
