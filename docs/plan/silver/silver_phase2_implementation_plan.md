---
tags: [plan, silver, phase2, implementation_plan]
---
# Phase 2 Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One Rust API serves both shipping UIs from one DuckDB store, and every answer it gives is proved identical to the Python implementation it replaces.

**Architecture:** A single `axum` binary on `:8100` exposes plan §6's twelve questions. Each handler either answers from the DuckDB store (landed) or forwards to the Python oracle and translates the reply into canonical shape (not yet landed). Routes land one at a time; a route lands only when `tools/diff_route.py` finds no unexplained difference between the two arms across the corpus. The UIs are repointed once, at the start, and never break.

**Tech Stack:** Rust 2021 (`axum` 0.7, `tokio`, `duckdb` 1.1 bundled, `serde`), the existing `rules_converter` and `inferred_duckdb` crates, Python 3.11 for the oracle and the diff tool, Vite 6 + React 19 for UI1, vanilla JS for UI2.

**Spec:** `docs/plan/silver/silver_phase2_vertical_slice_design.md`

> **Plan location note.** The writing-plans skill defaults to
> `docs/superpowers/plans/`. This repo's `CLAUDE.md` requires everything under `docs/` to
> follow the medallion vault, so the plan lives in `docs/plan/silver/` instead. Repo
> convention wins.

## Global Constraints

- **Prolog is the reference, Rust mirrors it** (owner rule, exp_42). Never change node/4 semantics to make Rust convenient.
- **Copy, do not re-derive.** Anything lifted from `raw/` names its source path in the commit that adds it.
- **No Prolog in UI1 or UI2.** Gold §7 C6. `swipl` may still be *called* by `run(engine=prolog)`, but nothing in either UI mentions it.
- Java 17 for Spark: `export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home`
- Commit messages: first line what changed, body why + pass mark hit or missed. End with:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- `git notes add` on every task's final commit carrying its measured numbers.
- Ports: Rust API `:8100`, UI1 `:5199`, UI2 `:8142`. **`:5173`, `:5174`, `:5175`, `:8000`, `:8042`, `:8043` are already held by the owner's own long-running servers — never bind them, and never take a reading from them believing it is ours.**
- Every timing claim is measured 3× and reported as a range, never estimated.

## Environment (assume nothing is running)

```bash
export R=~/Desktop/lineageQ/lineageQ_sep_experiments/exp_005_final_ui_v3
# oracle A — UI1's backend
cd $R/raw/lineage_server/server && SAS_ROOTS=../inputs SAS_DB=../output/explorer.duckdb \
  PYTHONPATH=../exp_2:. ../.venv/bin/python app.py &
# oracle B — the Bench
cd $R/raw/bench_stack && .venv/bin/python server/convert_api.py --port 8042 &
```

If a venv is missing, rebuild it — `raw/lineage_server/server/requirements.txt` is **incomplete**; the full set is `fastapi uvicorn pyarrow dulwich pyahocorasick duckdb openpyxl sqlglot pyyaml parse pytest httpx`.

## File Structure

| file | responsibility |
|---|---|
| `backend/rust_inferred_duckdb/src/lineage_blocks.rs` | **create** — run lineage per block so every edge knows its block |
| `backend/rust_inferred_duckdb/src/schema.rs` | modify — `node4.b0/b1`, `files.source`, `blocks.block_hash`, `runs`/`run_tables`/`run_samples`, `meta` |
| `backend/rust_inferred_duckdb/src/lib.rs` | modify — write the new columns; reconvert key gains the spec hash |
| `backend/rust_inferred_duckdb/src/datamatch.rs` | **create** — the row comparison, ported from Python |
| `backend/api/src/main.rs` | **create** — axum wiring, `:8100` |
| `backend/api/src/oracle.rs` | **create** — forward to Python + translate; deleted route by route |
| `backend/api/src/routes/*.rs` | **create** — one file per question |
| `backend/api/src/types.rs` | **create** — the canonical JSON shapes, mirroring UI1's `src/api.ts` |
| `tools/diff_route.py` | **create** — the differential oracle |
| `frontend/ui_across_file_ui/` | **create** — extracted from `raw/node4_viz` |
| `frontend/ui_file_ide/` | **create** — extracted from `raw/bench_stack/server/bench.html` |
| `docs/plan/bronze/bronze_phase2_route_ledger.md` | **create** — which routes landed, and every accepted divergence |

Routes get one file each because they land one at a time and are reviewed one at a time.

---

### Task 1: Lineage per block, so every edge knows where it lives

Today `convert` runs lineage over the whole file, so all 1204 edge rows carry `block_id = ''`. Three of the twelve questions are unanswerable until this is fixed. This is the task the whole slice is blocked on.

**Files:**
- Create: `backend/rust_inferred_duckdb/src/lineage_blocks.rs`
- Modify: `backend/rust_inferred_duckdb/src/lib.rs` (the `// file-level edges` block, ~line 300)
- Test: `backend/rust_inferred_duckdb/tests/lineage_blocks.rs`

**Interfaces:**
- Consumes: `rules_converter::lineage::sas::run(&[(String, &Term)]) -> Facts`, `Facts::text() -> String`
- Produces: `pub fn edges_per_block(ids: &[String], terms: &[Option<Term>]) -> Vec<Edge>` where
  `pub struct Edge { pub src: String, pub dst: String, pub kind: String, pub block_id: String }`

- [ ] **Step 1: Write the failing test**

```rust
// backend/rust_inferred_duckdb/tests/lineage_blocks.rs
use inferred_duckdb::lineage_blocks::{edges_per_block, Edge};
use rules_converter::{fold_file, spec};

fn spec_() -> spec::Spec {
    let p = concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/out/spec/sas.json");
    serde_json::from_str(&std::fs::read_to_string(p).unwrap()).unwrap()
}

#[test]
fn every_edge_names_the_block_that_made_it() {
    let src = concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/testdata/test_vishnu_testdata_fixed.sas");
    let text = std::fs::read_to_string(src).unwrap();
    let (_stmts, terms, ids) = fold_file(&spec_(), &text);
    let edges = edges_per_block(&ids, &terms);

    assert!(!edges.is_empty(), "no edges at all");
    let blank: Vec<&Edge> = edges.iter().filter(|e| e.block_id.is_empty()).collect();
    assert!(blank.is_empty(), "{} edges have no block_id, e.g. {:?}", blank.len(), blank.first());

    // sales.q1_avg_sales is written by the PROC SQL at L111-121, which is block b_007
    let e = edges.iter().find(|e| e.dst == "sales.q1_avg_sales")
        .expect("no edge writes sales.q1_avg_sales");
    assert_eq!(e.src, "sales.q1_sales");
    assert_eq!(e.block_id, "b_007");
}
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd $R/backend && cargo test -p inferred_duckdb --test lineage_blocks`
Expected: FAIL — `unresolved import inferred_duckdb::lineage_blocks`

- [ ] **Step 3: Write the module**

```rust
//! `lineage_blocks` — lineage facts, attributed to the block that produced them.
//!
//! **Why this exists.** `convert` used to run `lineage::sas::run` once over a whole
//! file's terms. That yields correct edges with no idea which block made them, so
//! `blocklinks`, `tablegraph` and `story` cannot be answered. Running lineage once per
//! block instead costs one pass per block and attributes every fact.
//!
//! **Inputs → outputs.** block ids + folded terms → one `Edge` per `ds_lineage/2` fact,
//! each naming its block.

use rules_converter::{lineage, term::Term};

#[derive(Debug, Clone, PartialEq)]
pub struct Edge { pub src: String, pub dst: String, pub kind: String, pub block_id: String }

/// `ds_lineage('OUT','IN').` — note the argument order: the fact names the output first,
/// so the edge runs IN -> OUT.
fn parse_ds_lineage(line: &str) -> Option<(String, String)> {
    let rest = line.strip_prefix("ds_lineage(")?;
    let mut q = rest.split('\'').skip(1).step_by(2);
    let out = q.next()?.to_string();
    let inp = q.next()?.to_string();
    Some((inp, out))
}

pub fn edges_per_block(ids: &[String], terms: &[Option<Term>]) -> Vec<Edge> {
    let mut order: Vec<&String> = Vec::new();
    for id in ids { if !order.contains(&id) { order.push(id); } }

    let mut out = Vec::new();
    for bid in order {
        let nodes: Vec<(String, &Term)> = ids.iter().enumerate()
            .filter(|(_, x)| *x == bid)
            .filter_map(|(i, _)| terms[i].as_ref().map(|t| (bid.clone(), t)))
            .collect();
        if nodes.is_empty() { continue; }
        for line in lineage::sas::run(&nodes).text().lines() {
            if let Some((src, dst)) = parse_ds_lineage(line) {
                out.push(Edge { src, dst, kind: "ds".into(), block_id: bid.clone() });
            }
        }
    }
    out
}
```

Add `pub mod lineage_blocks;` to `src/lib.rs`.

- [ ] **Step 4: Run the test**

Run: `cargo test -p inferred_duckdb --test lineage_blocks`
Expected: PASS. If `b_007` is wrong, print the edges and fix the *assertion* to the real block — do not fix the code to match a guess.

- [ ] **Step 5: Use it in `convert`**

In `lib.rs::fold_one`, delete the `// file-level edges, from ds_lineage(OUT, IN)` block and its `let facts = lineage::sas::run(&all);` and replace with:

```rust
    let edges: Vec<(String, String, String, String)> =
        crate::lineage_blocks::edges_per_block(&ids, &terms)
            .into_iter()
            .map(|e| (e.src, e.dst, e.kind, e.block_id))
            .collect();
```

`write_edges` already writes the 4th tuple element into `block_id`; it was always receiving `String::new()`.

- [ ] **Step 6: Prove it on the real store**

```bash
cd $R/backend && cargo build --release
rm -f /tmp/p2.duckdb
./target/release/lineageq_store convert $R/raw/bench_stack/out/spec/sas.json /tmp/bigcorpus /tmp/p2.duckdb
$R/raw/lineage_server/.venv/bin/python -c "
import duckdb; c=duckdb.connect('/tmp/p2.duckdb', read_only=True)
print('edges', c.execute('select count(*) from edges').fetchone()[0])
print('blank', c.execute(\"select count(*) from edges where block_id=''\").fetchone()[0])
"
```
Expected: `blank 0`. Record the edge count — **if it is no longer 1204, stop and explain why before continuing.** A changed count means the per-block split changed what lineage sees.

- [ ] **Step 7: Commit**

```bash
git add backend/rust_inferred_duckdb/src/lineage_blocks.rs backend/rust_inferred_duckdb/src/lib.rs backend/rust_inferred_duckdb/tests/lineage_blocks.rs
git commit -m "Phase 2: attribute every lineage edge to its block

Why: convert ran lineage once over a whole file, so all 1204 edge rows had
block_id = ''. blocklinks, tablegraph and story are unanswerable without it, and
they are three of the twelve questions the slice must serve.

What: lineage_blocks::edges_per_block runs lineage::sas::run once per block.
Edge count before/after: <N> / <M>.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: The remaining store columns

**Files:**
- Modify: `backend/rust_inferred_duckdb/src/schema.rs`, `src/lib.rs`
- Test: `backend/rust_inferred_duckdb/tests/store_columns.rs`

**Interfaces:**
- Produces: `files.source TEXT`, `node4.trace_b0/trace_b1 INTEGER`, `blocks.block_hash VARCHAR`, tables `runs`, `run_tables`, `run_samples`, `meta(key,value)`; `convert` skips a file only when **both** the file hash and the spec hash are unchanged.

- [ ] **Step 1: Write the failing test**

```rust
// backend/rust_inferred_duckdb/tests/store_columns.rs
use duckdb::Connection;

fn cols(c: &Connection, t: &str) -> Vec<String> {
    let mut s = c.prepare("SELECT column_name FROM information_schema.columns WHERE table_name = ?").unwrap();
    s.query_map([t], |r| r.get::<_, String>(0)).unwrap().map(|x| x.unwrap()).collect()
}

#[test]
fn schema_has_what_phase2_needs() {
    let db = std::env::temp_dir().join("phase2_cols.duckdb");
    let _ = std::fs::remove_file(&db);
    let c = inferred_duckdb::open(&db).unwrap();
    assert!(cols(&c, "files").contains(&"source".to_string()));
    for x in ["trace_b0", "trace_b1"] { assert!(cols(&c, "node4").contains(&x.to_string()), "node4.{}", x); }
    assert!(cols(&c, "blocks").contains(&"block_hash".to_string()));
    for t in ["runs", "run_tables", "run_samples", "meta"] {
        assert!(!cols(&c, t).is_empty(), "table {} missing", t);
    }
}

#[test]
fn a_spec_change_forces_a_reconvert() {
    let dir = std::env::temp_dir().join("phase2_specchange");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(dir.join("t.sas"), "data work.a; set work.b; run;\n").unwrap();

    let spec_a = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../../raw/bench_stack/out/spec/sas.json"));
    // a byte-identical copy with one extra space: same grammar, different hash
    let spec_b = dir.join("sas_copy.json");
    std::fs::write(&spec_b, std::fs::read_to_string(spec_a).unwrap() + " ").unwrap();

    let db = dir.join("s.duckdb");
    let mut c = inferred_duckdb::open(&db).unwrap();
    let r1 = inferred_duckdb::convert(&mut c, spec_a, &dir).unwrap();
    assert_eq!(r1.ok, 1);

    // same spec: the file is skipped, so no blocks are rewritten
    let r2 = inferred_duckdb::convert(&mut c, spec_a, &dir).unwrap();
    assert_eq!(r2.blocks, 0, "unchanged file + unchanged spec must be skipped");

    // different spec hash: it must be reconverted even though the file is identical
    let r3 = inferred_duckdb::convert(&mut c, &spec_b, &dir).unwrap();
    assert!(r3.blocks > 0, "a spec change must force a reconvert; stale rows are wrong answers");
}
```

- [ ] **Step 2: Run and watch it fail**

Run: `cargo test -p inferred_duckdb --test store_columns`
Expected: FAIL on `files.source`.

- [ ] **Step 3: Extend the DDL**

In `schema.rs`, add to `files`: `source VARCHAR,`. Add to `node4`: `trace_b0 INTEGER, trace_b1 INTEGER`. Add to `blocks`: `block_hash VARCHAR`. Then append:

```sql
CREATE TABLE IF NOT EXISTS run_tables (
    fileid VARCHAR, block_id VARCHAR, engine VARCHAR, table_name VARCHAR,
    verdict VARCHAR,           -- match | match-warn | differs | missing
    n_mismatch BIGINT, missing_side VARCHAR, at_ts TIMESTAMP
);
CREATE TABLE IF NOT EXISTS run_samples (
    fileid VARCHAR, block_id VARCHAR, engine VARCHAR, table_name VARCHAR,
    n INTEGER,                 -- 0..4, at most five per table
    row_json VARCHAR, n_left BIGINT, n_right BIGINT
);
CREATE TABLE IF NOT EXISTS meta (key VARCHAR PRIMARY KEY, value VARCHAR);
```

- [ ] **Step 4: Write the new columns**

In `lib.rs`: `write_file` gains `text` into `source`; `write_node4` writes `b0`/`b1` (extend `Folded::node4` to a 7-tuple `(block, seq, term, l0, l1, b0, b1)` and carry `st.b0`/`st.b1` in `fold_one`); `write_blocks` writes `block_hash: hash_of(&b.sas_text)`.

The reconvert key becomes both hashes:

```rust
let spec_hash = hash_of(&std::fs::read_to_string(spec_path)?);
// ...
let seen: Option<(String, String)> = conn.query_row(
    "SELECT f.hash, coalesce(m.value,'') FROM files f LEFT JOIN meta m ON m.key='spec_hash'
     WHERE f.fileid = ?", params![&fileid], |r| Ok((r.get(0)?, r.get(1)?))).ok();
if seen.as_ref().map(|(h, s)| h == &hash && s == &spec_hash).unwrap_or(false) { rep.ok += 1; continue; }
```
and after the loop: `INSERT OR REPLACE INTO meta VALUES ('spec_hash', ?)`.

- [ ] **Step 5: Tests pass, pass mark still holds**

```bash
cargo test -p inferred_duckdb
rm -f /tmp/p2b.duckdb
for i in 1 2 3; do ./target/release/lineageq_store convert $R/raw/bench_stack/out/spec/sas.json /tmp/bigcorpus /tmp/p2b_$i.duckdb 2>&1 >/dev/null | grep ^convert; done
```
Expected: all tests pass; convert still **< 3 s** (it was 1.46–1.50 s; `files.source` adds one string per file, `node4` two ints per row).

- [ ] **Step 6: Commit** (with a `git notes` receipt carrying the three convert timings)

---

### Task 3: The API skeleton and the oracle forwarder

**Files:**
- Create: `backend/api/Cargo.toml`, `src/main.rs`, `src/types.rs`, `src/oracle.rs`, `src/routes/mod.rs`
- Modify: `backend/Cargo.toml` (add `"api"` to `members`)
- Test: `backend/api/tests/health.rs`

**Interfaces:**
- Produces: binary `lineageq_api`; `GET /api/health -> {"ok":true,"landed":[...],"forwarded":[...]}`; `oracle::forward(base: &str, path: &str) -> Result<serde_json::Value>`; `AppState { db: Arc<Mutex<Connection>>, oracle_a: String, oracle_b: String }`

- [ ] **Step 1: Write the failing test**

```rust
// backend/api/tests/health.rs
#[tokio::test]
async fn health_reports_which_routes_have_landed() {
    let app = lineageq_api::app(lineageq_api::test_state());
    let res = axum_test_helper(app, "/api/health").await;   // see helper in src/lib.rs
    assert_eq!(res["ok"], true);
    assert!(res["landed"].is_array());
    assert!(res["forwarded"].is_array());
}
```

- [ ] **Step 2: Run, watch it fail** — `cargo test -p lineageq_api` → crate does not exist.

- [ ] **Step 3: Create the crate**

`backend/api/Cargo.toml`:
```toml
[package]
name = "lineageq_api"
version = "0.1.0"
edition = "2021"
description = "One HTTP API over the exp_005 store, serving both shipping UIs."

[dependencies]
inferred_duckdb = { path = "../rust_inferred_duckdb" }
rules_converter = { path = "../rust_rules_converter" }
axum = "0.7"
tokio = { version = "1", features = ["rt-multi-thread", "macros", "process"] }
reqwest = { version = "0.12", features = ["json"] }
serde = { workspace = true }
serde_json = { workspace = true }
```

`src/oracle.rs`:
```rust
//! `oracle` — the scaffold, not the destination.
//!
//! **Why this exists.** A question is answered from the store only once its route has
//! landed. Until then this forwards it to the Python implementation being replaced and
//! translates the reply into canonical shape. The same translation is what
//! `tools/diff_route.py` compares against, so it is written once, here, and each arm is
//! deleted as its route lands. When this file is empty the slice is done.

pub async fn forward(base: &str, path_and_query: &str) -> anyhow::Result<serde_json::Value> {
    Ok(reqwest::get(format!("{base}{path_and_query}")).await?.json().await?)
}
```

`src/main.rs` wires axum, reads `--db`, `--oracle-a` (default `http://127.0.0.1:8000`), `--oracle-b` (default `http://127.0.0.1:8042`), `--port` (default `8100`), and serves `/api/health` listing landed vs forwarded routes from a single `const LANDED: &[&str]`.

- [ ] **Step 4: Test passes.** `cargo test -p lineageq_api`

- [ ] **Step 5: Prove it runs**

```bash
./target/release/lineageq_api --db /tmp/p2.duckdb & sleep 1
curl -s localhost:8100/api/health | python3 -m json.tool
```
Expected: `ok true`, `landed []`, `forwarded` listing all twelve.

- [ ] **Step 6: Commit**

---

### Task 4: `tools/diff_route.py` — the differential oracle

**Files:**
- Create: `tools/diff_route.py`, `docs/plan/bronze/bronze_phase2_route_ledger.md`
- Test: `tools/tests/test_diff_route.py`

**Interfaces:**
- Produces: `python3 tools/diff_route.py <question> [--corpus ankitha|exp42] [--json]`; exit 0 only when there is no unexplained difference; every accepted divergence read from the ledger's `## Accepted divergences` table, keyed `question | fileid | json_path`.

- [ ] **Step 1: Write the failing test**

```python
# tools/tests/test_diff_route.py
from tools.diff_route import diff_json, load_accepted

def test_identical_payloads_have_no_differences():
    assert diff_json({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 2]}) == []

def test_a_changed_leaf_is_reported_with_its_path():
    d = diff_json({"nodes": [{"id": "x", "role": "up"}]},
                  {"nodes": [{"id": "x", "role": "down"}]})
    assert d == [("nodes[0].role", "up", "down")]

def test_list_order_does_not_matter_for_edges():
    a = {"edges": [{"src": "p", "dst": "q"}, {"src": "r", "dst": "s"}]}
    b = {"edges": [{"src": "r", "dst": "s"}, {"src": "p", "dst": "q"}]}
    assert diff_json(a, b, unordered={"edges"}) == []

def test_an_accepted_divergence_is_not_a_failure():
    acc = load_accepted(_ledger_fixture())     # one row: neighborhood | f.sas | nodes[0].score
    d = [("nodes[0].score", 0, 3)]
    assert filter_accepted(d, acc, "neighborhood", "f.sas") == []
```

- [ ] **Step 2: Run, watch it fail** — `cd $R && python3 -m pytest tools/tests/test_diff_route.py -v`

- [ ] **Step 3: Implement** `diff_json(a, b, unordered=frozenset())` walking both trees and yielding `(json_path, left, right)`; `load_accepted(path) -> set[tuple[str,str,str]]` parsing the ledger's markdown table into `(question, fileid, json_path)`; and `filter_accepted(diffs, accepted, question, fileid) -> list` dropping exactly those. `unordered` exists because `:8000` returns edges in DuckDB's order and Rust returns them in fold order — that is a genuine non-difference, and pretending otherwise would bury the real ones.

- [ ] **Step 4: Tests pass.**

- [ ] **Step 5: Seed the ledger**

```markdown
# bronze_phase2_route_ledger — which routes have landed
| question | landed | corpus clean | accepted divergences |
|---|---|---|---|
| files | no | — | — |
(… all twelve …)

## Accepted divergences
| question | fileid | json_path | why the parser is right |
|---|---|---|---|
```

- [ ] **Step 6: Commit**

---

### Task 5: Land `files()` and `search()`

The two simplest questions. They exercise the whole path — store read, canonical shape, diff — with almost no logic, so failures here are plumbing failures.

**Files:** Create `backend/api/src/routes/files.rs`, `search.rs`; modify `routes/mod.rs`, `main.rs` (`LANDED`)
**Interfaces:**
- Produces: `GET /api/files -> {"files":[{"id","label","folder"}]}` (matches `FileRow` in UI1 `src/api.ts:74`); `GET /api/search?q= -> {"hits":[{"kind":"table"|"file","value","files":[...]}]}` (matches `SearchHit`, `api.ts:73`)

- [ ] **Step 1: Write the failing test** — a Rust integration test asserting `/api/files` returns 25 rows for the ankitha store and that each row has exactly the keys `id,label,folder`.
- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** both handlers over `inferred_duckdb`. `search` uses `table_refs`-style matching, not `ILIKE '%q%'` over two tables.
- [ ] **Step 4: Tests pass.**
- [ ] **Step 5: Land them**

```bash
python3 tools/diff_route.py files   --corpus ankitha
python3 tools/diff_route.py search  --corpus ankitha
```
Expected: exit 0. Add both to `LANDED`, tick the ledger.

- [ ] **Step 6: Commit**

---

### Task 6: Land `neighborhood()`

The hardest question and the one both pass marks depend on. `:8000` computes it from the `mentions` index plus an in-memory cache, **not** from its `lineage` table (Fable, `silver_duckdb_store_design.md` §1) — so do not copy its SQL; match its *answer*.

**Files:** Create `backend/api/src/routes/neighborhood.rs`; Test `backend/api/tests/neighborhood.rs`
**Interfaces:**
- Produces: `GET /api/neighborhood?file=&table=&up=&down= -> {nodes,edges,seeds,story,order}` exactly matching UI1's `Neighborhood` (`src/api.ts:29`), with `NodeOut{id,label,folder,score,cyclic,role}` and `EdgeOut{src,dst,tables,level,provenance,src_ref,dst_ref,block,freshness}`. `up`/`down` clamp to 0..3 (`urlParams.ts:3`).

- [ ] **Step 1: Write the failing tests** — the two the pass marks name:

```rust
#[tokio::test]
async fn branch_rollup_is_six_files_and_seven_edges() {
    let r = get("/api/neighborhood?file=ankitha_1%2F11_branch_rollup.sas&up=1&down=1").await;
    assert_eq!(r["nodes"].as_array().unwrap().len(), 6);
    assert_eq!(r["edges"].as_array().unwrap().len(), 7);
}

#[tokio::test]
async fn enrich_fx_is_four_files_and_three_edges() {
    let r = get("/api/neighborhood?file=ankitha_1%2F07_enrich_fx.sas&up=1&down=1").await;
    assert_eq!(r["nodes"].as_array().unwrap().len(), 4);
    assert_eq!(r["edges"].as_array().unwrap().len(), 3);
    let roles: Vec<&str> = r["nodes"].as_array().unwrap().iter().map(|n| n["role"].as_str().unwrap()).collect();
    assert_eq!(roles.iter().filter(|x| **x == "seed").count(), 1);
    assert_eq!(roles.iter().filter(|x| **x == "up").count(), 2);   // 05_seed_transactions, 06_seed_fx_rates
    assert_eq!(roles.iter().filter(|x| **x == "down").count(), 1); // 12_txn_agg
}
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** — a breadth-first walk over `edges` rolled up to file level, `up` hops upstream and `down` downstream from the seed, `role` from which side the node was reached (`both` when both), `score` and `cyclic` as `:8000` computes them. `provenance` is `fact` for block-level rows, `inferred` for file-level, `human_gold` where a `human_edits` row confirms it.
- [ ] **Step 4: Tests pass.**
- [ ] **Step 5: Land it** — `python3 tools/diff_route.py neighborhood --corpus ankitha` across all 25 files. **Expect differences here.** Classify each as a Rust bug or a written-down accepted divergence; the parser finding a flow the regex scanner missed is the likely shape.
- [ ] **Step 6: Commit** with the divergence count in the message and a `git notes` receipt.

---

### Task 6b: Land `convert()`

The twelfth question, and the only one that writes. `lineageq_store convert` already does
the work; this exposes it and streams progress.

**Files:** Create `backend/api/src/routes/convert.rs`
**Interfaces:**
- Produces: `POST /api/convert {folder}` or `{file}` → `{files,ok,failed,blocks,node4,edges,fold_ms,store_ms,total_ms}` — the `ConvertReport` `inferred_duckdb` already returns.
- Plan §6 says it "streams `block ready` events". **Nothing in this slice consumes them**
  (spec OPEN item), so this task returns the report synchronously and does not invent a
  stream. Say so in the commit rather than building an unused SSE channel.

- [ ] **Step 1: Write the failing test**

```rust
#[tokio::test]
async fn convert_is_idempotent_over_http() {
    let r1 = post("/api/convert", json!({"folder": "<tmp corpus>"})).await;
    assert_eq!(r1["ok"], 1);
    assert!(r1["blocks"].as_i64().unwrap() > 0);
    let r2 = post("/api/convert", json!({"folder": "<tmp corpus>"})).await;
    assert_eq!(r2["blocks"], 0, "second convert of an unchanged folder must write nothing");
}
```

- [ ] **Step 2: Run, fail.**
- [ ] **Step 3: Implement** — one handler calling `inferred_duckdb::convert`, taking the
  store mutex for the whole call. **A convert blocks reads**; that is the sharp end of the
  spec's OPEN question about one connection versus one per thread. Record the measured
  blocking duration in the commit.
- [ ] **Step 4: Test passes.**
- [ ] **Step 5: Land it** — no oracle diff: `:8042 /api/convert` returns a different shape
  and this is new surface, not a replacement. Note that in the ledger as
  `no oracle — new surface`, which is the only honest reason a route may land undiffed.
- [ ] **Step 6: Commit.**

---

### Task 7: Land `blocklinks()` and `edges()`

**Files:** Create `routes/blocklinks.rs`, `routes/edges.rs`
**Interfaces:**
- Produces: `GET /api/blocklinks?files=a,b -> {"links":[BlockLink]}` with `BlockLink{src_file,src_block,src_ref,dst_file,dst_block,dst_ref,table}` (`api.ts:61`); `GET /api/edges?files=&filter=&level=&offset=&limit= -> {"total":N,"rows":[EdgeRow]}` (`api.ts:85`).
- Depends on Task 1: both read `edges.block_id`.

- [ ] **Step 1: Write the failing tests**

```rust
#[tokio::test]
async fn dashboard_mart_has_twenty_five_edges() {
    // the "25 / 25" in the owner's baseline screenshot
    let files = "ankitha_1/09_customer_summary.sas,ankitha_1/10_product_metrics.sas,\
ankitha_1/11_branch_rollup.sas,ankitha_1/14_large_txn_report.sas,\
ankitha_1/18_dashboard_mart.sas,ankitha_1/19_export_dashboard.sas,ankitha_1/25_final_pack.sas";
    let r = get(&format!("/api/edges?files={}", urlencoding::encode(files))).await;
    assert_eq!(r["total"], 25);
    let rows = r["rows"].as_array().unwrap();
    assert!(rows.iter().any(|e| e["provenance"] == "human_gold"),
            "the baseline shows one HUMAN_GOLD row; human_edits must overlay the inferred edges");
    assert!(rows.iter().any(|e| e["level"] == "block" && e["provenance"] == "fact"));
}

#[tokio::test]
async fn blocklinks_name_both_blocks() {
    let r = get("/api/blocklinks?files=ankitha_1%2F11_branch_rollup.sas,ankitha_1%2F18_dashboard_mart.sas").await;
    let links = r["links"].as_array().unwrap();
    assert!(!links.is_empty());
    for l in links {
        assert!(!l["src_block"].as_str().unwrap().is_empty(), "src_block empty — Task 1 did not take");
        assert!(!l["dst_block"].as_str().unwrap().is_empty(), "dst_block empty");
    }
    assert!(links.iter().any(|l| l["table"] == "work.branch_rollup"));
}
```

- [ ] **Step 2: Run, watch both fail.**
- [ ] **Step 3: Implement** both handlers. `edges()` reads block rows and rolls up to file
  and project level; the `human_gold` provenance comes from overlaying `human_edits`, which
  `:8000` does in one CTE (`_merged_edges`) — copy that logic, changing only the join key.
- [ ] **Step 4: Both tests pass.**
- [ ] **Step 5: Land** — `python3 tools/diff_route.py blocklinks --corpus ankitha` and
  `… edges --corpus ankitha`. `edges` is the one most likely to diverge, because the
  parser sees flows the scanner misses; classify every difference.
- [ ] **Step 6: Commit.**

---

### Task 8: Land `source()`, extract UI1, and hit pass marks 1 and 2

**Files:**
- Create: `routes/source.rs`; `frontend/ui_across_file_ui/` (from `raw/node4_viz`, excluding `node_modules`, `scripts/hola_compare`)
- Modify: `frontend/ui_across_file_ui/src/api.ts` (six fetches → canonical names), `vite.config.ts:11` (`:8000` → `:8100`), `src/useLineageGraph.ts:15` and `src/holaLayout.ts:9` (stale absolute paths), `scripts/smoke.mjs` (parameterise the `!== 11` assertion and the screenshot dir)

- [ ] **Step 1: Extract and repoint.** Name the source path in the commit.
- [ ] **Step 2: Unit tests still pass** — `npm test` → **127 passed** (they stub `fetch`, so they pass regardless of backend; that is the point — they prove the extraction did not break the app).
- [ ] **Step 3: Run it against Rust with Python still up.**
- [ ] **Step 4: PASS MARK — stop both Python servers, then measure.**

```bash
kill $(lsof -ti:8000) $(lsof -ti:8042)
cd frontend/ui_across_file_ui && BASE=http://localhost:5199 OUT=$R/../run_evidence node ../../tools/shot_ui1.mjs
```
Expected: `passmark_11_branch_rollup: files=6 edges=7`, `enrich_fx: files=4 edges=3`, **no console errors**. This is the mark that only passes when Python is gone.

- [ ] **Step 5: Restart the oracles** (later tasks still need them).
- [ ] **Step 6: Commit** with both screenshots and a `git notes` receipt.

---

### Task 9: Land `file()` and `blocks()`

**Files:** Create `routes/file.rs`, `routes/blocks.rs`
**Interfaces:**
- Produces: `GET /api/file?fileid= -> {stem,path,ok,errors,blocks:[{id,n,kind,name,lines,warn,reads,writes}],receipts}` — **no `sas`, no `py`**, per plan §6; `GET /api/blocks?fileid=&from=&to= -> [{id,n,kind,name,lines,sas,py,py_pretty,terms}]`.
- The Bench's `/api/open` returns both halves in one payload (1.1 MB for `big_1000`); splitting them is what makes phase 3's windowing possible.

- [ ] **Step 1: Write the failing test** — `file()` on `test_vishnu_testdata_fixed.sas` returns 23 blocks, `receipts.statements == 80`, `folded == 80`, `roundtrip == 80`, and **no block carries a `sas` key**.
- [ ] **Step 2: Fail.** — [ ] **Step 3: Implement** over `inferred_duckdb::file` / `::blocks`. — [ ] **Step 4: Pass.**
- [ ] **Step 5: PASS MARK 6 — through HTTP this time**

```bash
for i in 1 2 3; do curl -s -o /dev/null -w "%{time_total}\n" "localhost:8100/api/file?fileid=big_1000.sas"; done
for i in 1 2 3; do curl -s -o /dev/null -w "%{time_total}\n" "localhost:8100/api/blocks?fileid=big_1000.sas&from=0&to=40"; done
```
Expected: both **< 20 ms**. In-process they were 1.1–4.3 ms and 0.7–1.3 ms; HTTP and JSON serialisation are the new cost. If `file()` exceeds 20 ms at 1000 blocks, say so — Fable flagged its 85 KB payload as an OPEN question about paging.

- [ ] **Step 6: Land via `diff_route.py --corpus exp42`, commit.**

---

### Task 10: Land `tablegraph()` and `story()`

**Files:** Create `routes/tablegraph.rs`, `routes/story.rs`
**Interfaces:**
- Produces: `GET /api/tablegraph?fileid= -> {tables:[{name,kind,block_id}],edges:[{src,dst,kind,block_id}]}`; `GET /api/story?table= -> {makers:[{fileid,block_id,n}]}` in run order.
- The owner's Bench screenshot is the fixture: `test_vishnu_testdata_fixed.sas` draws **12 edges** across SOURCE → STEP 1 → STEP 2 → STEP 3, with `sales_data` at SOURCE and `final_summary` at STEP 3.

- [ ] **Step 1: Write the failing tests**

```rust
#[tokio::test]
async fn tablegraph_matches_the_bench_screenshot() {
    let r = get("/api/tablegraph?fileid=test_vishnu_testdata_fixed.sas").await;
    assert_eq!(r["edges"].as_array().unwrap().len(), 12, "the baseline says '12 edges'");
    let t: Vec<&str> = r["tables"].as_array().unwrap().iter()
        .map(|x| x["name"].as_str().unwrap()).collect();
    for want in ["sales.sales_data", "sales.q1_avg_sales", "sales.final_summary"] {
        assert!(t.contains(&want), "missing {}", want);
    }
    let e = r["edges"].as_array().unwrap().iter()
        .find(|e| e["dst"] == "sales.q1_avg_sales").unwrap();
    assert_eq!(e["block_id"], "b_007");
}

#[tokio::test]
async fn story_lists_makers_in_run_order() {
    let r = get("/api/story?table=sales.final_summary").await;
    let m = r["makers"].as_array().unwrap();
    assert!(!m.is_empty());
    let ns: Vec<i64> = m.iter().map(|x| x["n"].as_i64().unwrap()).collect();
    let mut sorted = ns.clone(); sorted.sort();
    assert_eq!(ns, sorted, "makers must come back in run order, not insertion order");
}
```

- [ ] **Step 2: Run, watch both fail.**
- [ ] **Step 3: Implement.** `tablegraph` is `SELECT src_table, dst_table, kind, block_id
  FROM edges WHERE fileid = ?` plus the distinct table names. `story` walks `edges`
  backwards from the table, ordering makers by `blocks.n`.
- [ ] **Step 4: Both pass.**
- [ ] **Step 5: Land** via `diff_route.py --corpus exp42` against `:8042 /api/lineage`.
- [ ] **Step 6: Commit.**

---

### Task 11: Port the row comparison to Rust

The only genuinely new algorithm in the slice, and the one place a wrong "match" could come from. It has **two** reference implementations to check against: `pipeline/datamatch.py` and `server/datamatch.ts`.

**Files:** Create `backend/rust_inferred_duckdb/src/datamatch.rs`; Test `backend/rust_inferred_duckdb/tests/datamatch.rs`
**Interfaces:**
- Produces:
  ```rust
  pub enum Verdict { Pass, Fail }
  pub struct Sample { pub row: Vec<String>, pub n_left: i64, pub n_right: i64 }
  pub fn normalize_value(s: &str) -> String;
  pub fn compare_rows(left: &[Vec<String>], right: &[Vec<String>], max_samples: usize)
      -> (Verdict, i64, Vec<Sample>);
  ```
- Semantics copied from `pipeline/datamatch.py:158`: **multiset** comparison (duplicates count), `n_mismatch` is the total differing row-instances, at most five samples.

- [ ] **Step 1: Write the failing tests — normalisation first, because that is where a false match hides**

```rust
#[test] fn normalisation_matches_python() {
    assert_eq!(normalize_value(" 1.0 "), "1");       // whole float -> integer
    assert_eq!(normalize_value("."), "");            // SAS missing
    assert_eq!(normalize_value(""), "");
    assert_eq!(normalize_value("-0"), "0");
    assert_eq!(normalize_value("1.2345678"), "1.234568");  // 6 dp
    assert_eq!(normalize_value("nan"), "nan");
    assert_eq!(normalize_value("Fred"), "Fred");     // non-numeric passes through
}
#[test] fn duplicates_are_counted() {
    let a = vec![vec!["x".into()], vec!["x".into()]];
    let b = vec![vec!["x".into()]];
    let (v, n, _) = compare_rows(&a, &b, 5);
    assert!(matches!(v, Verdict::Fail));
    assert_eq!(n, 1, "a multiset comparison must notice the missing duplicate");
}
#[test] fn row_order_does_not_matter() {
    let a = vec![vec!["p".into()], vec!["q".into()]];
    let b = vec![vec!["q".into()], vec!["p".into()]];
    assert!(matches!(compare_rows(&a, &b, 5).0, Verdict::Pass));
}
```

- [ ] **Step 2: Fail.** — [ ] **Step 3: Implement** with a `HashMap<Vec<String>, i64>` multiset, joined on `\u{1f}` as the Python does.
- [ ] **Step 4: Pass.**
- [ ] **Step 5: Cross-check against Python on real CSVs**

```bash
# feed both implementations the same out/blocks/*/rust and */spark CSVs and require
# identical (verdict, n_mismatch) for all 11 blocks
python3 tools/xcheck_datamatch.py
```
Expected: 11/11 identical verdicts. **If Rust and Python disagree on any block, Rust is wrong** — Python is the reference here, exactly as Prolog is for the engine.

- [ ] **Step 6: Commit.**

---

### Task 12: Land `run()` — L2 against L3

**Files:** Create `backend/api/src/routes/run.rs`, `backend/api/src/spawn.rs`
**Interfaces:**
- Produces: `POST /api/run {fileid, block_id, engine} -> {block_id, engine, left_ms, right_ms, tables:[{name,verdict,n_mismatch,samples}], match}`; rows written to `runs`, `run_tables`, `run_samples`.
- Four steps, three of which shell out: `block-programs` (Rust, in-process), `loops/gen_block_testdata.py` (Python + Z3), Rust `interp` for `output_left` — or `swipl codegen/sas_interp.pl` when `engine == "prolog"` — and `python <block>.py` on Spark for `output_right`. Comparison is Task 11.

- [ ] **Step 1: Write the failing test** — one block end to end:

```rust
#[tokio::test]
async fn one_block_runs_both_ways_and_matches() {
    let r = post("/api/run", json!({"fileid":"test_vishnu_testdata_fixed.sas",
                                    "block_id":"b_003","engine":"rust"})).await;
    assert_eq!(r["match"], "match");
    assert!(r["left_ms"].as_f64().unwrap() < 100.0, "rust interp should be ~8 ms");
    assert!(r["right_ms"].as_f64().unwrap() > 1000.0, "spark carries a JVM start");
}
```

- [ ] **Step 2: Fail.** — [ ] **Step 3: Implement** `spawn.rs` (a `tokio::process::Command` wrapper carrying `JAVA_HOME` and `LINEAGEQ_OUT`), then the four steps.
- [ ] **Step 4: Pass** (~5 s: the Spark JVM dominates).
- [ ] **Step 5: PASS MARK 5 — the whole file**

```bash
for b in $(seq -f "b_%03g" 2 12); do
  curl -s -X POST localhost:8100/api/run -H 'Content-Type: application/json' \
    -d "{\"fileid\":\"test_vishnu_testdata_fixed.sas\",\"block_id\":\"$b\",\"engine\":\"rust\"}" \
    | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['block_id'],d['match'])"
done
```
Expected: **11 blocks, all `match`** — the receipt `bench_receipt.py` produced on 2026-09-09. Anything less is a regression against a known-good number, not a new unknown.

- [ ] **Step 6: Commit** with a `git notes` receipt of the 11 verdicts and both timings.

---

### Task 13: Extract UI2, repoint it, and remove Prolog from the interface

**Files:**
- Create: `frontend/ui_file_ide/` (from `raw/bench_stack/server/bench.html`, 1318 lines)
- Modify: the thirteen fetch sites; the Prolog surface below

- [ ] **Step 1: Extract and repoint** the thirteen `api("...")` calls (`/api/open` splits into `file()` + `blocks()`; `/api/run_block` → `run()`; `/api/lineage` → `tablegraph()`; `/api/files`, `/api/file`, `/api/similar`, `/api/folder`, `/api/save`, `/api/listing`, `/api/sessions`, `/api/session`, `/api/exec`, `/api/term` follow).
- [ ] **Step 2: Strip the Prolog surface** (gold §7 C6):

| remove | line |
|---|---|
| `<span class="pill idle" id="rSame">…prolog == rust</span>` | 365 |
| the `pill("#rSame", …)` call | 521 |
| the `<div class="engine">Rust\|Prolog</div>` toggle + its CSS | 371-373, 73-75 |
| its click handler and `setEngine` | 1032-1033 |
| the palette action and the `r` keybinding | 1144, 1262 |
| the `prolog == rust` term in the open log line | 534 |
| the help text naming both engines | 452 |

`S.engine` is pinned to `"rust"`; the ten ternaries reading it collapse to `"Rust"`. **Keep** the `folded` and `round trip` pills, sourced from Rust's own counts. **Keep** `statements` — line 517 uses it for the header meta.

- [ ] **Step 3: PASS MARK 4 — with both Python servers stopped**

```bash
kill $(lsof -ti:8000) $(lsof -ti:8042)
node tools/shot_bench.mjs   # BASE=http://localhost:8142
grep -ci prolog frontend/ui_file_ide/bench.html
```
Expected: header reads `23 blocks · 80 statements · folded 80/80 · round trip 80/80`, **no `prolog == rust` pill**, and the grep returns **0**.

- [ ] **Step 4: Commit** with the screenshot and a list of every difference from the owner's baseline.

---

### Task 14: Close the slice

- [ ] **Step 1: Delete `oracle.rs`** and the `forward` arm from every handler. If any route still needs it, the slice is not done — say which and stop.
- [ ] **Step 2: Full run with no Python at all**

```bash
pkill -f "app.py|convert_api.py"
./target/release/lineageq_api --db /tmp/p2.duckdb &
# UI1 :5199, UI2 :8142
node tools/shot_ui1.mjs && node tools/shot_bench.mjs && node tools/shot_bench_cells.mjs
```
All seven pass marks, re-measured in one sitting, none inherited from an earlier task:

| # | mark | how it is checked here |
|---|---|---|
| 1 | `11_branch_rollup` draws 6 files / 7 edges | `tools/shot_ui1.mjs`, Python dead |
| 2 | `07_enrich_fx` draws 4 files / 3 edges | same run |
| 3 | **every route clean against the oracle** | `for q in files search neighborhood blocklinks edges source file blocks tablegraph story run; do python3 tools/diff_route.py $q; done` — with the oracles restarted for this check only, then stopped again. Every non-empty diff must already be in the ledger's accepted table. |
| 4 | UI2: 23 blocks, 80/80, no Prolog | `tools/shot_bench.mjs` + `grep -ci prolog` returns 0 |
| 5 | `run()`: 11/11 blocks match | the loop from Task 12 |
| 6 | `file()` and `blocks(0,40)` < 20 ms over HTTP | `curl -w %{time_total}`, 3× each |
| 7 | **screenshots against both owner baselines** | `tools/shot_ui1.mjs`, `shot_bench.mjs`, `shot_bench_cells.mjs`; compare with `docs/plan/bronze/evidence_2026-09-09/*.png` and **list every difference**, including the Prolog elements deliberately removed |

A mark that cannot be re-measured here is not met. Do not carry forward a number from an
earlier task's notes.

- [ ] **Step 3: Write `docs/plan/bronze/bronze_phase2_receipts.md`** — every pass mark with its measured number, every accepted divergence, and a **What this does not prove** section (UI2 is still vanilla JS and unwindowed; UI3 does not exist; `human_edits` writing is untouched).
- [ ] **Step 4: Update the ledger** to twelve landed.
- [ ] **Step 5: Correct the plan** — apply gold §7 C1–C7 to `gold_draft_exp_005_plan.md`, which still says two UIs and a background Prolog proof.
- [ ] **Step 6: Final commit + PR.**

---

## Risks carried from the spec

| risk | first task that would reveal it |
|---|---|
| parser and scanner disagree; improvement vs regression is a judgement each time | Task 6 |
| per-block lineage changes edge counts | Task 1, Step 6 |
| `file()` at 1000 blocks is 85 KB and may exceed 20 ms over HTTP | Task 9, Step 5 |
| repointing 1318 lines of vanilla JS breaks something invisible | Task 13, Step 3 |
| Spark's ~4.5 s per block makes Task 12 slow to iterate | Task 12, Step 4 |
