# team_finance Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up one local corpus, `corpus/team_finance/{sas,hive}`, staged
`raw -> auto_convert -> work -> final_match`, and point both UIs at one backend door so they
show the same data.

**Architecture:** The store (`lineageq_store convert <spec> <folder> <db>`) indexes any
folder recursively, taking each file's path relative to the seeded root as its `fileid`, and
collects `.sas` only. Seeding at `corpus/team_finance/` therefore produces fileids like
`sas/raw/09_customer_summary.sas`, skips the `.hql` files and skips the `.py` in the later
stages — the four-stage layout falls out of the existing walker with no code change. Both
UIs then talk only to the Rust API on `:8110`, which forwards not-yet-landed routes to the
two Python oracles.

**Tech Stack:** Rust (axum + duckdb), the `lineageq_sas` engine binary, Vite/React (UI1),
one static HTML page (UI2), zsh.

**Spec:** `docs/superpowers/specs/2026-09-09-team-finance-corpus-design.md`

## Global Constraints

- All paths relative to `exp_005_final_ui_v3/` unless they begin with `raw/`.
- `auto_convert/` is **never** hand-edited; it is regenerated on every run.
- `work/` is seeded once from `auto_convert/` and is the only stage a human edits.
- The engine spec is `raw/bench_stack/out/spec/sas.json`; the preamble is
  `raw/bench_stack/codegen/sas_runtime_preamble.py`.
- The three worked sample stems are exactly: `09_customer_summary`, `15_join_risk_txn`,
  `18_dashboard_mart`.
- Rust API default port is `8110`; oracles are `:8000` (a) and `:8042` (b).
- Do not land any new API route in this plan beyond serving the Bench page. Routes are
  phase C.
- Every commit message ends with the two attribution lines used on this branch.

## Facts established before planning (do not re-derive)

- `lineageq_store convert` over the 25 ankitha files: **25 files, 26 blocks, 126 node4,
  41 edges, 109 ms**. The store does not need `explorer.duckdb` or any tooling from
  `~/Desktop/sas2py_projects/`. The spec's headline risk is closed.
- 24 of 25 files round-trip. `13_risk_flags.sas` exits 1 with
  `rebuild mismatch: source "0.40" printed "0.4"`.
- `collect_sas` (`backend/rust_inferred_duckdb/src/lib.rs:129`) recurses and filters to
  `.sas`; `fileid` is `path.strip_prefix(folder)`.
- `split_fileid` (`backend/api/src/routes/files.rs:34`) splits on the **last** `/`, so
  `sas/raw/09_customer_summary.sas` yields folder `sas/raw`.
- The engine emits PySpark only when given argv[4]/argv[5]:
  `lineageq_sas <spec> <file> <out_dir> <preamble> <pretty_preamble>` writes
  `<stem>_ravi_rust.py` and `<stem>_pretty_rust.py`.
- `LANDED` is `["files", "search", "neighborhood"]`; `tests/landed.rs` fails if `LANDED` and
  the router disagree.

---

### Task 1: Build the corpus tree

**Files:**
- Create: `corpus/team_finance/sas/{raw,auto_convert,work,final_match}/.gitkeep`
- Create: `corpus/team_finance/hive/{raw,auto_convert,work,final_match}/.gitkeep`
- Create: `corpus/perf/` (moved files)
- Create: `tools/check_corpus.sh`

**Interfaces:**
- Produces: the corpus root `corpus/team_finance/`, seeded by every later task; and
  `tools/check_corpus.sh`, the structure check Task 5 re-runs after the deletions.

- [ ] **Step 1: Write the failing structure check**

```bash
cat > tools/check_corpus.sh <<'EOS'
#!/bin/zsh
# tools/check_corpus.sh — the corpus contract of the 2026-09-09 team_finance spec.
# Why: the four-stage layout is load-bearing (the store's fileids come from it) and is
# easy to break by hand. Exits non-zero with the first thing that is wrong.
set -u
root="${0:A:h}/../corpus/team_finance"
fail=0
for lang in sas hive; do
  for stage in raw auto_convert work final_match; do
    [[ -d "$root/$lang/$stage" ]] || { echo "MISSING $lang/$stage"; fail=1 }
  done
done
n_sas=$(ls "$root/sas/raw"/*.sas 2>/dev/null | wc -l | tr -d ' ')
n_hql=$(ls "$root/hive/raw"/*.hql 2>/dev/null | wc -l | tr -d ' ')
[[ "$n_sas" == 25 ]] || { echo "sas/raw: expected 25 .sas, found $n_sas"; fail=1 }
[[ "$n_hql" == 6  ]] || { echo "hive/raw: expected 6 .hql, found $n_hql"; fail=1 }
(( fail )) && { echo "corpus check FAILED"; exit 1 }
echo "corpus check ok: 25 sas, 6 hql, 8 stage folders"
EOS
chmod +x tools/check_corpus.sh
```

- [ ] **Step 2: Run it to verify it fails**

Run: `tools/check_corpus.sh`
Expected: FAIL — `MISSING sas/raw` first, exit 1.

- [ ] **Step 3: Create the tree and copy the sources in**

```bash
mkdir -p corpus/team_finance/{sas,hive}/{raw,auto_convert,work,final_match} corpus/perf
for d in corpus/team_finance/{sas,hive}/{raw,auto_convert,work,final_match}; do touch "$d/.gitkeep"; done
cp raw/lineage_server/inputs/ankitha_1/*.sas corpus/team_finance/sas/raw/
cp ~/Desktop/lineageQ/lineageQ_aug_experiments/exp_014_vertical_slice_hadoop/corpus/hive/small/*.hql \
   corpus/team_finance/hive/raw/
git mv raw/bench_stack/corpus/sas/big_100.sas  corpus/perf/ 2>/dev/null || mv raw/bench_stack/corpus/sas/big_100.sas  corpus/perf/
git mv raw/bench_stack/corpus/sas/big_1000.sas corpus/perf/ 2>/dev/null || mv raw/bench_stack/corpus/sas/big_1000.sas corpus/perf/
git mv raw/bench_stack/corpus/sas/big_2000.sas corpus/perf/ 2>/dev/null || mv raw/bench_stack/corpus/sas/big_2000.sas corpus/perf/
```

- [ ] **Step 4: Run the check to verify it passes**

Run: `tools/check_corpus.sh`
Expected: PASS — `corpus check ok: 25 sas, 6 hql, 8 stage folders`.

- [ ] **Step 5: Verify the store indexes it, and only the raw stage**

Run:
```bash
backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json \
  corpus/team_finance /tmp/tf_probe.duckdb
```
Expected: `convert: 25 files, 26 blocks, 126 node4, 41 edges` — 25, not more: the `.hql`
files and the empty later stages contribute nothing. If the count is not 25, stop: the
walker is picking up something it should not.

- [ ] **Step 6: Record the round-trip baseline**

Run:
```bash
eng=raw/bench_stack/rust_engine/target/release/lineageq_sas
ok=0; bad=""
for f in corpus/team_finance/sas/raw/*.sas; do
  if $eng raw/bench_stack/out/spec/sas.json "$f" /tmp/tf_rt >/dev/null 2>&1; then
    ok=$((ok+1)); else bad="$bad $(basename $f)"; fi
done
echo "round-trip $ok/25  failed:$bad"
```
Expected: exactly `round-trip 24/25  failed: 13_risk_flags.sas`. Any other number means the
corpus copied in wrong. Do not fix `13_risk_flags.sas` here — the `0.40` -> `0.4` printer
bug is out of scope and is recorded in `corpus/README.md` in Task 5.

- [ ] **Step 7: Commit**

```bash
git add corpus tools/check_corpus.sh
git commit -m "Task 1: team_finance corpus tree, 25 SAS + 6 Hive, big_*.sas to corpus/perf

Source: SAS from raw/lineage_server/inputs/ankitha_1; Hive from
lineageQ_aug_experiments/exp_014_vertical_slice_hadoop/corpus/hive/small.
big_*.sas moved rather than deleted: backend/api/src/lib.rs names big_2000.sas
as a fixture for route tasks 8-10.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01J8C4ENAFXp5S7YxRAgDBJw"
```

---

### Task 2: Carry the three samples through the stages

**Files:**
- Create: `tools/build_stages.sh`
- Create: `corpus/team_finance/sas/auto_convert/<stem>.py` (3 files)
- Create: `corpus/team_finance/sas/work/<stem>.py` (3 files)
- Create: `corpus/team_finance/sas/final_match/<stem>.py` + `<stem>.verdict.json` (6 files)

**Interfaces:**
- Consumes: `corpus/team_finance/sas/raw/` from Task 1.
- Produces: `tools/build_stages.sh`, re-runnable; it regenerates `auto_convert/` only and
  never overwrites `work/`.

- [ ] **Step 1: Write the failing stage check**

Append to `tools/check_corpus.sh`, before the final `echo`:

```bash
for stem in 09_customer_summary 15_join_risk_txn 18_dashboard_mart; do
  for stage in auto_convert work final_match; do
    [[ -f "$root/sas/$stage/$stem.py" ]] || { echo "MISSING sas/$stage/$stem.py"; fail=1 }
  done
  v="$root/sas/final_match/$stem.verdict.json"
  [[ -f "$v" ]] || { echo "MISSING $v"; fail=1 }
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$v" 2>/dev/null || { echo "BAD JSON $v"; fail=1 }
done
```

- [ ] **Step 2: Run it to verify it fails**

Run: `tools/check_corpus.sh`
Expected: FAIL — `MISSING sas/auto_convert/09_customer_summary.py`, exit 1.

- [ ] **Step 3: Write the stage builder**

```bash
cat > tools/build_stages.sh <<'EOS'
#!/bin/zsh
# tools/build_stages.sh — regenerate auto_convert/ and, on first run only, seed work/
# and final_match/ for the three worked sample stems of the 2026-09-09 spec.
# Why: auto_convert is machine output and must be reproducible; work is the human's and
# must never be clobbered by a rerun.
set -eu
here="${0:A:h}/.."
tf="$here/corpus/team_finance/sas"
eng="$here/raw/bench_stack/rust_engine/target/release/lineageq_sas"
spec="$here/raw/bench_stack/out/spec/sas.json"
pre="$here/raw/bench_stack/codegen/sas_runtime_preamble.py"
tmp=$(mktemp -d)
for stem in 09_customer_summary 15_join_risk_txn 18_dashboard_mart; do
  "$eng" "$spec" "$tf/raw/$stem.sas" "$tmp" "$pre" "$pre" >/dev/null
  cp "$tmp/${stem}_pretty_rust.py" "$tf/auto_convert/$stem.py"
  [[ -f "$tf/work/$stem.py" ]] || cp "$tf/auto_convert/$stem.py" "$tf/work/$stem.py"
  if [[ ! -f "$tf/final_match/$stem.py" ]]; then
    cp "$tf/work/$stem.py" "$tf/final_match/$stem.py"
    rows=$(grep -c . "$tf/raw/$stem.sas")
    cat > "$tf/final_match/$stem.verdict.json" <<EOJ
{
  "stem": "$stem",
  "accepted": false,
  "left_engine": "rust",
  "rows_compared": 0,
  "rows_matched": 0,
  "note": "seeded by tools/build_stages.sh; no DataMatch run yet (source lines: $rows)"
}
EOJ
  fi
  echo "staged $stem"
done
rm -rf "$tmp"
EOS
chmod +x tools/build_stages.sh
tools/build_stages.sh
```

Note `"accepted": false` and zeroed counts: no DataMatch has been run, and a verdict that
claimed a match it never made would be a lie in the corpus. Phase C fills these in.

- [ ] **Step 4: Run the check to verify it passes**

Run: `tools/check_corpus.sh`
Expected: PASS, including all nine stage files and three parsing verdicts.

- [ ] **Step 5: Verify a rerun does not clobber `work/`**

Run:
```bash
echo "# hand edit" >> corpus/team_finance/sas/work/09_customer_summary.py
tools/build_stages.sh
tail -1 corpus/team_finance/sas/work/09_customer_summary.py
```
Expected: `# hand edit` still there. Then remove it again with
`git checkout corpus/team_finance/sas/work/09_customer_summary.py` if it was committed, or
delete the line by hand.

- [ ] **Step 6: Commit**

```bash
git add corpus tools/build_stages.sh tools/check_corpus.sh
git commit -m "Task 2: three worked samples through auto_convert -> work -> final_match

Why these three: 09_customer_summary is the simplest complete conversion,
15_join_risk_txn depends on two upstream files, 18_dashboard_mart is a deep
downstream chain. Verdicts are seeded accepted:false with zeroed counts —
no DataMatch has run, and a verdict claiming an unmeasured match would be
false data in the corpus.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01J8C4ENAFXp5S7YxRAgDBJw"
```

---

### Task 3: Re-seed the API tests from team_finance

**Files:**
- Modify: `backend/api/src/lib.rs:100-120` (`test_state`, and its doc comment above it)
- Modify: `backend/api/tests/files.rs`
- Modify: `backend/api/tests/neighborhood.rs`
- Modify: `backend/api/tests/search.rs`

**Interfaces:**
- Consumes: `corpus/team_finance/` from Task 1.
- Produces: a `test_state()` whose fileids are `sas/raw/<name>.sas`. Every later route task
  (phase C) writes its assertions against that prefix.

- [ ] **Step 1: See the tests pass on the old corpus first**

Run: `cd backend && cargo test -p lineageq_api`
Expected: PASS. This is the baseline — if it is already red, fix that before changing the
seed, or you cannot tell what this task broke.

- [ ] **Step 2: Re-point the seed**

In `backend/api/src/lib.rs`, replace the `folder` binding in `test_state()`:

```rust
    let folder = std::path::Path::new(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../corpus/team_finance"
    ));
    inferred_duckdb::convert(&mut conn, spec, folder)
        .expect("seed the team_finance corpus into the test store");
```

Also update the doc comment above `test_state()`: it currently says "seeded with the 25-file
`ankitha` corpus" and "Only `ankitha`". Say instead that it is seeded from
`corpus/team_finance/`, that fileids are `sas/raw/<name>.sas` because `convert` takes the
path relative to the seeded root, and that the `.hql` files under `hive/raw` and the `.py`
under the later stages are skipped by `collect_sas`'s `.sas` filter.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && cargo test -p lineageq_api`
Expected: FAIL in `files.rs` and `neighborhood.rs` — the fileids are now
`sas/raw/06_seed_fx_rates.sas`, not `ankitha_1/06_seed_fx_rates.sas`.

- [ ] **Step 4: Update the assertions**

In `backend/api/tests/files.rs`, rename the test and fix the ids:

```rust
async fn returns_all_25_team_finance_files_with_exactly_id_label_folder() {
```
```rust
        .find(|f| f["id"] == "sas/raw/06_seed_fx_rates.sas")
        .expect("06_seed_fx_rates.sas is in the team_finance corpus");
```
```rust
    assert_eq!(hit["folder"], "sas/raw");
```

In `backend/api/tests/neighborhood.rs` and `backend/api/tests/search.rs`, replace every
`ankitha_1%2F` with `sas%2Fraw%2F` and every bare `ankitha_1/` with `sas/raw/`. Find them
with:

```bash
grep -rn "ankitha" backend/api/tests backend/api/src
```

Expected after fixing: that grep returns nothing.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && cargo test -p lineageq_api`
Expected: PASS, all suites including `landed.rs`. The file count assertion still expects 25
— Task 1 already proved the walker finds exactly 25.

- [ ] **Step 6: Commit**

```bash
git add backend/api
git commit -m "Task 3: seed the API tests from corpus/team_finance

fileids become sas/raw/<name>.sas: convert() takes each path relative to the
seeded root, so seeding the corpus root rather than one language folder keeps
both languages addressable and groups them in UI1's explorer. The .hql files
and the .py in the later stages are skipped by collect_sas's .sas filter, so
the store still holds exactly the 25 raw SAS files.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01J8C4ENAFXp5S7YxRAgDBJw"
```

---

### Task 4: One door — both UIs on :8110

**Files:**
- Create: `backend/api/src/routes/bench.rs`
- Modify: `backend/api/src/routes/mod.rs`
- Modify: `backend/api/src/lib.rs` (the router in `app()`)
- Create: `backend/api/tests/bench.rs`
- Modify: `raw/node4_viz/vite.config.ts:11`

**Interfaces:**
- Consumes: `app(state)` from `lib.rs`.
- Produces: `GET /bench` on `:8110`, serving `raw/bench_stack/server/bench.html` verbatim.
  This is a page route, not an API route: it is deliberately **not** added to `ALL_ROUTES`
  or `LANDED`, which track API questions only, and `tests/landed.rs` must stay green.

- [ ] **Step 1: Write the failing test**

```rust
// backend/api/tests/bench.rs
mod support;

/// The Bench page must come from the same door as the API it calls. bench.html asks for
/// relative `/api/...`, so whichever origin serves the page decides which backend it
/// talks to; serving it from :8110 is what puts UI2 behind the Rust API without editing
/// the 1,300-line page.
#[tokio::test]
async fn bench_page_is_served_and_is_the_real_page() {
    let res = support::get_raw("/bench").await;
    assert_eq!(res.status, 200);
    assert_eq!(res.content_type, "text/html; charset=utf-8");
    assert!(res.body.contains("<title>lineageQ Bench</title>"), "not the Bench page");
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && cargo test -p lineageq_api --test bench`
Expected: FAIL to compile — `support::get_raw` does not exist yet.

- [ ] **Step 3: Add the raw-response helper**

`support::get` returns parsed JSON; a page is not JSON. In
`backend/api/tests/support/mod.rs` add, alongside `get`:

```rust
pub struct RawRes { pub status: u16, pub content_type: String, pub body: String }

/// Like `get`, but keeps the bytes and the content type instead of parsing JSON — the
/// Bench page is HTML, not an answer.
pub async fn get_raw(path: &str) -> RawRes {
    use tower::ServiceExt;
    let app = lineageq_api::app(lineageq_api::test_state());
    let req = axum::http::Request::builder().uri(path).body(axum::body::Body::empty()).unwrap();
    let res = app.oneshot(req).await.unwrap();
    let status = res.status().as_u16();
    let content_type = res.headers().get(axum::http::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok()).unwrap_or("").to_string();
    let bytes = axum::body::to_bytes(res.into_body(), usize::MAX).await.unwrap();
    RawRes { status, content_type, body: String::from_utf8_lossy(&bytes).to_string() }
}
```

If the existing `get` builds its request differently, mirror it rather than this sketch —
match the file you find.

- [ ] **Step 4: Write the route**

```rust
// backend/api/src/routes/bench.rs
//! `GET /bench` — UI2's page, served from the API's own origin.
//!
//! **Why here.** bench.html fetches relative `/api/...`. Served from :8042 those calls hit
//! the Python server; served from :8110 they hit this API, which answers what it has landed
//! and forwards the rest to the oracles. So this one route is what puts UI2 behind the same
//! door as UI1, with no change to the 1,300-line page itself.
//!
//! **Inputs → outputs.** no inputs → the bytes of raw/bench_stack/server/bench.html.
//!
//! Read at request time, not baked in with `include_str!`: the page is still being edited
//! in its own track, and a stale copy compiled into the binary would be a confusing lie.

use axum::http::{header, StatusCode};
use axum::response::IntoResponse;

const BENCH_HTML: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../raw/bench_stack/server/bench.html"
);

pub async fn bench() -> impl IntoResponse {
    match std::fs::read_to_string(BENCH_HTML) {
        Ok(body) => (
            StatusCode::OK,
            [
                (header::CONTENT_TYPE, "text/html; charset=utf-8"),
                (header::CACHE_CONTROL, "no-store"),
            ],
            body,
        )
            .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("bench.html unreadable at {BENCH_HTML}: {e}"),
        )
            .into_response(),
    }
}
```

Add `pub mod bench;` to `backend/api/src/routes/mod.rs`, and the route to `app()` in
`lib.rs`:

```rust
        .route("/bench", get(routes::bench::bench))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && cargo test -p lineageq_api`
Expected: PASS, `bench` included, and `landed.rs` still green — `/bench` is a page, not an
entry in `ALL_ROUTES`.

- [ ] **Step 6: Point UI1 at the same door**

In `raw/node4_viz/vite.config.ts`, change the proxy default:

```ts
      '/api': process.env.VITE_PROXY ?? 'http://localhost:8110',
```

Leave the `/hola` proxy alone — it is the layout sidecar, not a data backend.

- [ ] **Step 7: Prove both UIs work through :8110**

Run, in three terminals:
```bash
backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json \
  corpus/team_finance backend/lineageq.duckdb
backend/target/release/lineageq_api --db backend/lineageq.duckdb --port 8110
(cd raw/bench_stack && .venv/bin/python server/convert_api.py --port 8042)
(cd raw/node4_viz && npm run dev)
```
Then check:
```bash
curl -s localhost:8110/api/files | head -c 200
curl -s -o /dev/null -w "%{http_code}\n" localhost:8110/bench
curl -s -o /dev/null -w "%{http_code}\n" localhost:5174/
```
Expected: the files list shows `sas/raw/...` ids; `/bench` and UI1 both return 200. Open
`http://localhost:5174/` and `http://localhost:8110/bench` and confirm both name the same
files. If the Bench errors on a route the API forwards, note which route and stop — that is
the oracle-fidelity risk the spec called out, and it belongs to phase C, not here.

- [ ] **Step 8: Commit**

```bash
git add backend/api raw/node4_viz/vite.config.ts
git commit -m "Task 4: serve the Bench from :8110 and point UI1 there too

bench.html fetches relative /api/..., so the origin that serves the page picks
its backend. Serving it from the Rust API puts UI2 behind the same door as UI1
without touching the 1,300-line page. Read at request time rather than
include_str! so an edit in the bench_stack track is never masked by a stale
compiled copy. /bench is a page, not an API question, so it stays out of
ALL_ROUTES and LANDED.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01J8C4ENAFXp5S7YxRAgDBJw"
```

---

### Task 5: Delete the old corpora and write it down

**Files:**
- Delete: `raw/lineage_server/inputs/ankitha_1/`, `raw/lineage_server/output/explorer.duckdb{,.wal}`
- Delete: `raw/bench_stack/corpus/sas/test_vishnu*.sas`, `raw/bench_stack/corpus/parts/`,
  `raw/bench_stack/testdata/`
- Create: `corpus/README.md`
- Modify: `CLAUDE.md` (the Layout table), `docs/wiki_root.md`

**Interfaces:**
- Consumes: everything above. This task is last because the deletions are only safe once
  Tasks 3 and 4 prove nothing still reads the old paths.

- [ ] **Step 1: Find every reference before deleting anything**

Run:
```bash
grep -rn "ankitha_1\|test_vishnu\|explorer.duckdb\|corpus/parts\|testdata/" \
  --exclude-dir=node_modules --exclude-dir=target --exclude-dir=.git \
  --exclude-dir=.venv backend frontend raw/node4_viz tools docs CLAUDE.md | grep -v "^docs/superpowers/"
```
Expected: hits only inside `raw/bench_stack/server/*.py` (the oracle's own defaults) and
`raw/lineage_server/`. **If anything under `backend/` or `raw/node4_viz/` still matches,
stop and fix that first** — Task 3 was supposed to clear it.

- [ ] **Step 2: Check what the oracles still need**

`raw/bench_stack/server/bench_api.py:421` sets
`SAS_DIRS = ["corpus/sas", "corpus/parts", "testdata"]`. Those are the Bench oracle's file
list. Deleting all three leaves the Bench dock empty for any route the Rust API forwards.
Point it at the new corpus instead:

```python
SAS_DIRS = ["../../corpus/team_finance/sas/raw"]   # 2026-09-09: one corpus, see docs/superpowers/specs/2026-09-09-team-finance-corpus-design.md
```

Then check line 67's dock list and line 612's `"corpus/sas/test_vishnu.sas"` default and
give them the same treatment: the default stem becomes `09_customer_summary`.

- [ ] **Step 3: Delete**

```bash
git rm -r --quiet raw/lineage_server/inputs/ankitha_1 raw/bench_stack/corpus/parts raw/bench_stack/testdata
git rm --quiet raw/bench_stack/corpus/sas/test_vishnu*.sas
git rm --quiet --ignore-unmatch raw/lineage_server/output/explorer.duckdb raw/lineage_server/output/explorer.duckdb.wal
```

- [ ] **Step 4: Re-run everything**

Run:
```bash
tools/check_corpus.sh
cd backend && cargo test -p lineageq_api && cd ..
backend/target/release/lineageq_store convert raw/bench_stack/out/spec/sas.json \
  corpus/team_finance /tmp/tf_after.duckdb
```
Expected: corpus check ok; all Rust tests pass; convert still reports 25 files, 41 edges.
Restart the two servers and re-check `localhost:8110/bench` and `localhost:5174/` return
200 and list the same files.

- [ ] **Step 5: Write the corpus README**

```bash
cat > corpus/README.md <<'EOS'
# corpus/ — the one local corpus

**Why this folder exists.** Until 2026-09-09 the two UIs read two different corpora through
two different backends, so they showed different data. This is the single corpus both now
read, through the Rust API on :8110.

**Inputs → outputs.** `team_finance/<lang>/raw/` is the source as received; the store
(`lineageq_store convert <spec> corpus/team_finance <db>`) indexes it into DuckDB and the
API answers from there.

## Stages

| stage | written by | hand-edited | regenerated |
|---|---|---|---|
| `raw/` | nobody — source as received | no | no |
| `auto_convert/` | `tools/build_stages.sh` | never | every run |
| `work/` | you, in the Bench | yes | no — seeded once from auto_convert |
| `final_match/` | the pipeline on acceptance | no | on acceptance |

`final_match/<stem>.verdict.json` carries the DataMatch result. Today every verdict says
`"accepted": false` with zeroed counts: no DataMatch has been run yet. Phase C fills them in.

## Contents

- `team_finance/sas/raw/` — 25 chained SAS files (customers, products, branches, accounts,
  transactions, FX, risk, compliance, dashboard). From
  `~/Desktop/sas2py_projects/file_dependencies_regex/inputs/ankitha_1`, via
  `raw/lineage_server/`. 24 of 25 round-trip; `13_risk_flags.sas` does not — `0.40` prints
  back as `0.4`, an engine bug in the printer.
- `team_finance/hive/raw/` — 6 HiveQL files, from
  `lineageQ_aug_experiments/exp_014_vertical_slice_hadoop/corpus/hive/small`. **Present but
  not converted:** the Hive tokeniser spec (`raw/bench_stack/pipeline/specs/hive.py`) has
  never been executed and there is no `out/spec/hive.json`. That is phase B.
- `perf/` — `big_100.sas`, `big_1000.sas`, `big_2000.sas`. Fixtures, not a corpus:
  `backend/api/src/lib.rs` names `big_2000.sas` for route tasks 8-10.

## Checks

- `tools/check_corpus.sh` — the structure contract.
- `tools/build_stages.sh` — regenerate `auto_convert/`, seed `work/` and `final_match/`.
EOS
```

- [ ] **Step 6: Update the two docs that describe the layout**

In `CLAUDE.md`, add a `corpus/` row to the Layout table:

```markdown
| `corpus/` | `team_finance/{sas,hive}/{raw,auto_convert,work,final_match}` — the one corpus both UIs read; `perf/` for the big fixtures. See `corpus/README.md`. |
```

In `docs/wiki_root.md`, add a line pointing at `corpus/README.md` and at this plan's spec.

- [ ] **Step 7: Commit**

```bash
git add -A corpus tools docs CLAUDE.md raw/bench_stack/server
git commit -m "Task 5: delete the old corpora, document the new one

Deleted: inputs/ankitha_1, explorer.duckdb, corpus/parts, testdata,
test_vishnu*.sas. The Bench oracle's SAS_DIRS is re-pointed at
corpus/team_finance/sas/raw so the forwarded routes still have files to list.
Recorded in corpus/README.md, including the two open defects: the 0.40 -> 0.4
printer bug, and that the Hive tokeniser has never been run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01J8C4ENAFXp5S7YxRAgDBJw"
```

---

## Pass marks (the spec's, restated as commands)

| # | Check | Command |
|---|---|---|
| 1 | 8 stage folders, 25 SAS, 6 Hive | `tools/check_corpus.sh` |
| 2 | 24/25 round-trip, `13_risk_flags` the known failure | the loop in Task 1 Step 6 |
| 3 | 3 samples staged, verdicts parse | `tools/check_corpus.sh` |
| 4 | landed routes green on the new seed | `cd backend && cargo test -p lineageq_api` |
| 5 | both UIs up, same files | `curl` checks in Task 4 Step 7 |

## Not in this plan

- Hive conversion (phase B): `out/spec/hive.json`, node/4 branches, the Prolog mirror.
- API routes 4-12 (phase C): `convert`, `blocklinks`, `edges`, `source`, `file`, `blocks`,
  `tablegraph`, `story`, `run`, and retiring the Python oracles.
- The `0.40` -> `0.4` printer bug.
