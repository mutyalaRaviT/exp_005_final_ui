//! `GET /bench` — UI2's page, served from this origin — and the five `/api/bench/*`
//! questions that only UI2 asks.
//!
//! **Why this module changed shape (Decision D17, M4b, 2026-09-10).** Ruling 6
//! (2026-09-09) made `/bench` a 302 to `oracle_b`, because one origin could not answer
//! both UI1's `/api/files` and the Bench's differently-shaped one, and because nothing
//! here answered the Bench's other twelve calls. D17 takes Ruling 6's *other* branch —
//! "rename them under a prefix" — and closes both halves of that blocker:
//!
//! - the four Bench routes that are really lineage questions (`open`, `run_block`,
//!   `lineage`, `file?path=`) are repointed in the page itself at `file()` + `blocks()`,
//!   `run()`, `tablegraph()` and `source()`;
//! - the five that are Bench-only corpus-contract questions land here under
//!   `/api/bench/<name>`, so they can never collide with UI1's names;
//! - the four Jupyter-attach routes (`sessions`, `session`, `exec`, `term`) are dropped
//!   from UI2 in this slice — no forwarder survives for them, and the page's Terminal tab
//!   says so in one line.
//!
//! With no Bench call left unanswered, `/bench` serves the page's bytes again. It is
//! `frontend/ui_file_ide/bench.html`, compiled in with `include_str!` so the released
//! binary carries the window inside it (plan §8 phase 6) and so `tests/bench.rs` asserts
//! against exactly the bytes that ship. `LINEAGEQ_BENCH_HTML` overrides the path at run
//! time for dev iteration only; it is never set by `main`.
//!
//! **Inputs → outputs.**
//! - `GET /bench` → the page, `text/html`.
//! - `GET /api/bench/files` → the store's fileids as the Bench's file tree
//!   (`{groups:[{dir,items:[{name,path,kind}]}],recent:[]}`).
//! - `GET /api/bench/folder?dir=` → one folder's files with block/edge counts, plus the
//!   flow links between them (the folder page and the file graph).
//! - `GET /api/bench/similar?stem=` → `{similar:[],note:…}` — see `similar` below.
//! - `GET /api/bench/listing?stem=` → `{loaded:false,tables:{},note:…}` — see `listing`.
//! - `POST /api/bench/save {path,text}` → writes one file under `corpus/*/…/work/`, and
//!   refuses every path outside it.

use crate::routes::blocklinks::{block_facts, links_from_facts};
use crate::types::AppState;
use axum::extract::{Query, State};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Json};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Component, PathBuf};

/// The page as it ships. Not read from disk at request time: the release binary has no
/// `frontend/` beside it.
const BENCH_HTML: &str = include_str!("../../../../frontend/ui_file_ide/bench.html");

/// `GET /bench`.
pub async fn bench() -> impl IntoResponse {
    let body = match std::env::var("LINEAGEQ_BENCH_HTML") {
        Ok(p) if !p.is_empty() => std::fs::read_to_string(&p).unwrap_or_else(|_| BENCH_HTML.to_string()),
        _ => BENCH_HTML.to_string(),
    };
    (StatusCode::OK, [(header::CONTENT_TYPE, "text/html; charset=utf-8")], body)
}

fn ise(e: String) -> (StatusCode, String) {
    (StatusCode::INTERNAL_SERVER_ERROR, e)
}

/// `fileid` -> `(folder, name)`. A fileid with no slash — the exp42 fixture, converted as
/// its own root — sits in the folder `.`, which is a real, openable dir in the page.
fn split(fileid: &str) -> (String, String) {
    match fileid.rsplit_once('/') {
        Some((d, n)) => (d.to_string(), n.to_string()),
        None => (".".to_string(), fileid.to_string()),
    }
}

fn all_files(conn: &duckdb::Connection) -> Result<Vec<(String, i64, String)>, duckdb::Error> {
    let mut st = conn.prepare(
        "SELECT fileid, length(source), COALESCE(CAST(converted_at AS VARCHAR), '')
         FROM files ORDER BY fileid",
    )?;
    let mut rows = st.query([])?;
    let mut out = Vec::new();
    while let Some(r) = rows.next()? {
        out.push((r.get(0)?, r.get::<_, Option<i64>>(1)?.unwrap_or(0), r.get(2)?));
    }
    Ok(out)
}

// ---------------------------------------------------------------- files

/// The Bench's own file tree, from the store instead of a hard-coded directory list.
///
/// The Bench's `list_files()` walks eight fixed directories under `raw/bench_stack` and
/// keys everything by on-disk path; this keys everything by **fileid**, so every path the
/// page then hands back to `file()`, `blocks()`, `run()` or `source()` is already the key
/// those routes take. That is the whole reason this route is Bench-shaped rather than
/// UI1-shaped: the page reads `groups[].items[].path`.
pub async fn files(State(state): State<AppState>) -> Result<Json<Value>, (StatusCode, String)> {
    let conn = state.db.lock().map_err(|e| ise(e.to_string()))?;
    let files = all_files(&conn).map_err(|e| ise(e.to_string()))?;
    drop(conn);

    let mut groups: BTreeMap<String, Vec<Value>> = BTreeMap::new();
    for (fileid, _, _) in &files {
        let (dir, name) = split(fileid);
        groups.entry(dir).or_default().push(json!({
            "name": name, "path": fileid, "kind": kind_of(&name),
        }));
    }
    let groups: Vec<Value> = groups
        .into_iter()
        .map(|(dir, items)| json!({ "dir": dir, "items": items }))
        .collect();
    // The Bench keeps a `recent.json` beside its outputs; this store has no such notion,
    // and the page keeps its own recent list in `localStorage` either way.
    Ok(Json(json!({ "groups": groups, "recent": [] })))
}

fn kind_of(name: &str) -> &'static str {
    if name.ends_with(".sas") {
        "sas"
    } else if name.ends_with(".py") {
        "py"
    } else {
        "ir"
    }
}

// ---------------------------------------------------------------- folder

#[derive(Deserialize)]
pub struct FolderParams {
    #[serde(default)]
    dir: String,
}

/// One folder as a page: its files with what each one is worth (blocks, edges), the
/// folders under it, and how its files are linked.
///
/// `links` here are the Bench's `flow` links only — B reads a table A writes — computed
/// from the same `block_facts`/`links_from_facts` that answer UI1's `blocklinks`, so the
/// two windows cannot disagree about which file feeds which. The Bench's other two link
/// kinds are not reproduced: `subset` compares two files' whole lineage rule sets and
/// `derived` matches a non-SAS file's name against a SAS stem, and this store holds only
/// converted SAS files. Recorded as an accepted divergence in the ledger.
pub async fn folder(
    State(state): State<AppState>,
    Query(params): Query<FolderParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let dir = params.dir.trim().trim_end_matches('/').to_string();
    let dir = if dir.is_empty() { ".".to_string() } else { dir };

    let conn = state.db.lock().map_err(|e| ise(e.to_string()))?;
    let files = all_files(&conn).map_err(|e| ise(e.to_string()))?;

    let mut here: Vec<(String, String, i64, String)> = Vec::new(); // fileid, name, size, modified
    let mut subdirs: BTreeSet<String> = BTreeSet::new();
    for (fileid, size, modified) in &files {
        let (d, name) = split(fileid);
        if d == dir {
            here.push((fileid.clone(), name, *size, modified.clone()));
        } else if dir == "." {
            if let Some(top) = d.split('/').next() {
                if d != "." {
                    subdirs.insert(top.to_string());
                }
            }
        } else if let Some(rest) = d.strip_prefix(&format!("{dir}/")) {
            if let Some(top) = rest.split('/').next() {
                subdirs.insert(top.to_string());
            }
        }
    }

    let scope: Vec<String> = here.iter().map(|(f, _, _, _)| f.clone()).collect();
    let mut blocks: BTreeMap<String, i64> = BTreeMap::new();
    let mut edges: BTreeMap<String, i64> = BTreeMap::new();
    {
        let mut st = conn.prepare("SELECT fileid, COUNT(*) FROM blocks GROUP BY fileid").map_err(|e| ise(e.to_string()))?;
        let mut rows = st.query([]).map_err(|e| ise(e.to_string()))?;
        while let Some(r) = rows.next().map_err(|e| ise(e.to_string()))? {
            blocks.insert(r.get(0).map_err(|e| ise(e.to_string()))?, r.get(1).map_err(|e| ise(e.to_string()))?);
        }
    }
    {
        let mut st = conn.prepare("SELECT fileid, COUNT(*) FROM edges GROUP BY fileid").map_err(|e| ise(e.to_string()))?;
        let mut rows = st.query([]).map_err(|e| ise(e.to_string()))?;
        while let Some(r) = rows.next().map_err(|e| ise(e.to_string()))? {
            edges.insert(r.get(0).map_err(|e| ise(e.to_string()))?, r.get(1).map_err(|e| ise(e.to_string()))?);
        }
    }
    let facts = block_facts(&conn, &scope).map_err(|e| ise(e.to_string()))?;
    drop(conn);

    let name_of: BTreeMap<String, String> =
        here.iter().map(|(f, n, _, _)| (f.clone(), n.clone())).collect();
    let mut via: BTreeMap<(String, String), BTreeSet<String>> = BTreeMap::new();
    for l in links_from_facts(&facts) {
        if l.src_file == l.dst_file {
            continue;
        }
        via.entry((l.src_file.clone(), l.dst_file.clone())).or_default().insert(l.table);
    }
    let links: Vec<Value> = via
        .into_iter()
        .filter_map(|((from, to), tables)| {
            Some(json!({
                "from": name_of.get(&from)?, "to": name_of.get(&to)?,
                "kind": "flow", "via": tables.into_iter().collect::<Vec<_>>(),
            }))
        })
        .collect();

    let rows: Vec<Value> = here
        .iter()
        .map(|(fileid, name, size, modified)| {
            json!({
                "name": name, "path": fileid, "kind": kind_of(name),
                "size": size, "modified": modified,
                "shapes": blocks.get(fileid).copied().unwrap_or(0),
                "edges": edges.get(fileid).copied().unwrap_or(0),
            })
        })
        .collect();

    Ok(Json(json!({
        "dir": dir,
        "files": rows,
        "subdirs": subdirs.into_iter().collect::<Vec<_>>(),
        "total_bytes": here.iter().map(|(_, _, s, _)| *s).sum::<i64>(),
        "links": links,
    })))
}

// ---------------------------------------------------------------- similar

#[derive(Deserialize)]
pub struct StemParams {
    #[serde(default)]
    #[allow(dead_code)]
    stem: String,
}

/// **Empty by design, with the reason attached (D17).** The Bench's `similar()` is a
/// Jaccard score over a *signature index* — `out/bench/sig/*`, block shapes ∪ lineage
/// edges, written by folding every SAS file with the Python loop and cached on disk. That
/// index is a Python artefact this store does not hold and this milestone does not port;
/// inventing a different score here would put a number in the page that no oracle agrees
/// with. So the route exists, answers `[]`, and says why, and the page prints the note
/// where the list would be.
pub async fn similar(Query(_p): Query<StemParams>) -> Json<Value> {
    Json(json!({
        "similar": [],
        "note": "similarity scoring is the Bench's Python signature index (out/bench/sig); \
                 it is not in the Rust store. Returns in M5.",
    }))
}

// ---------------------------------------------------------------- listing

/// **Empty by design, with the reason attached.** A "listing" is a PROC PRINT output
/// pasted from SAS OnDemand, compared against the file-level Spark CSVs under
/// `out/pyspark_ravi/`. Neither the pasted text nor those CSVs are in this store, and the
/// comparison is `bench_api.parse_listing`/`listing_verdicts`, Python this milestone does
/// not port. The route answers the empty shape the page already handles (`loaded:false`).
pub async fn listing(Query(_p): Query<StemParams>) -> Json<Value> {
    Json(json!({
        "loaded": false,
        "tables": {},
        "note": "pasting a SAS listing compares against the Bench's file-level Spark CSVs \
                 (out/pyspark_ravi), which are not in the Rust store. Returns in M5.",
    }))
}

// ---------------------------------------------------------------- save

#[derive(Deserialize)]
pub struct SaveBody {
    pub path: String,
    pub text: String,
}

/// Write one edited buffer into the corpus's `work/` stage.
///
/// **Why it refuses almost everything.** `corpus/README.md` makes `work/` the one stage a
/// person edits by hand ("you, in the Bench"); `raw/` is the bytes as received and
/// `auto_convert/` is regenerated every run. A save route that could write anywhere would
/// let the page overwrite the source it is meant to be migrating. So the path must be
/// relative, must start with `corpus/`, must have a `work` component, and must name a
/// single file directly inside it — `corpus/team_finance/sas/work/09_customer_summary.py`
/// and nothing else. `..`, absolute paths and symlink-shaped escapes are rejected before
/// anything is opened.
pub async fn save(Json(body): Json<SaveBody>) -> Result<Json<Value>, (StatusCode, String)> {
    let rel = check_work_path(&body.path)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("save(): {e}")))?;
    let root = PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."));
    let dest = root.join(&rel);
    let parent = dest.parent().expect("a checked work path always has a parent");
    if !parent.is_dir() {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("save(): {} is not a folder in this corpus", rel.parent().unwrap().display()),
        ));
    }
    std::fs::write(&dest, &body.text)
        .map_err(|e| ise(format!("save(): write {}: {e}", dest.display())))?;
    Ok(Json(json!({
        "path": body.path,
        "saved_as": rel.to_string_lossy(),
        "bytes": body.text.as_bytes().len(),
    })))
}

/// `corpus/<anything>/work/<one file>` or an error saying which rule it broke. Pure, so
/// `tests/bench.rs` can check the refusals without a filesystem.
pub fn check_work_path(path: &str) -> Result<PathBuf, String> {
    let p = PathBuf::from(path);
    let comps: Vec<&str> = p
        .components()
        .map(|c| match c {
            Component::Normal(s) => Ok(s.to_str().unwrap_or("")),
            _ => Err("path must be relative, with no `..` and no root".to_string()),
        })
        .collect::<Result<Vec<_>, _>>()?;
    if comps.len() < 3 || comps[0] != "corpus" {
        return Err(format!("{path} is not under corpus/"));
    }
    let Some(work) = comps.iter().position(|c| *c == "work") else {
        return Err(format!("{path} has no work/ stage; only corpus/*/work/ is writable"));
    };
    if work + 2 != comps.len() {
        return Err(format!("{path} must name one file directly inside its work/ folder"));
    }
    let name = comps[comps.len() - 1];
    if name.is_empty() || name.starts_with('.') {
        return Err(format!("{name:?} is not a file name this route will write"));
    }
    Ok(comps.iter().collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_work_stage_of_the_corpus_is_writable() {
        assert_eq!(
            check_work_path("corpus/team_finance/sas/work/09_customer_summary.py").unwrap(),
            PathBuf::from("corpus/team_finance/sas/work/09_customer_summary.py")
        );
    }

    #[test]
    fn everything_outside_a_work_stage_is_refused() {
        for bad in [
            "corpus/team_finance/sas/raw/09_customer_summary.sas",
            "corpus/team_finance/sas/work/nested/x.py",
            "backend/api/src/lib.rs",
            "/etc/passwd",
            "corpus/../backend/x.py",
            "corpus/team_finance/sas/work/",
        ] {
            assert!(check_work_path(bad).is_err(), "should refuse {bad}");
        }
    }

    #[test]
    fn a_fileid_with_no_folder_lands_in_the_root_folder() {
        assert_eq!(split("test_vishnu_testdata_fixed.sas"), (".".into(), "test_vishnu_testdata_fixed.sas".into()));
        assert_eq!(split("sas/raw/01_seed_customers.sas"), ("sas/raw".into(), "01_seed_customers.sas".into()));
    }
}
