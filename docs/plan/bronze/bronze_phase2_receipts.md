---
tags: [plan, bronze, phase2, receipts]
---
# bronze_phase2_receipts — the seven pass marks, measured in one sitting

**Why this file exists.** Phase 2's claim is one sentence: *two windows run on one Rust binary
over one DuckDB store, and no Python process is involved in any answer.* A claim like that is
worth exactly as much as the numbers behind it, so this page is the numbers — every pass mark with
the command that produced it, every accepted divergence with its root cause, and a section saying
what the numbers do **not** prove. Nothing here is carried forward from an earlier task's notes:
Task 14 re-measured all seven in one sitting on 2026-09-10.

**Inputs → outputs.** `tools/shot_ui1.mjs`, `tools/shot_bench.mjs`, `tools/shot_bench_cells.mjs`,
`tools/diff_route.py`, `curl` against `lineageq_api`, `cargo test`, `npx vitest run` → this page +
`docs/plan/bronze/evidence_2026-09-10/*.png`.

---

## "No Python alive" — the evidence

Every mark below except mark 3 was measured with **no Python process from this repo running**.
`pgrep -fl "app.py|convert_api.py"` at measurement time returned exactly one line:

```
97158 …/Python server/convert_api.py
```

and that pid's working directory is
`/Users/mutyala/Desktop/lineageQ/lineageQ_aug_experiments/exp_42_test_vishnu` — the **foreign**
`:8042` Bench belonging to another checkout (finding F8). It was never used, never pointed at, and
never killed. This repo's own Python servers — `:8000` (`raw/lineage_server/server/app.py`) and
`:8043`, `:8044`, `:8142` (`raw/bench_stack/server/convert_api.py`) — were stopped **by pid, after
reading each pid's cwd**, not with a blanket `pkill`, precisely so the foreign one survived.

What *was* running: `lineageq_api` (Rust) on `:8110` over `backend/lineageq.duckdb`, and Vite on
`:5199` serving UI1's dev build. Marks 6 and 3 started three more short-lived Rust instances
(`:8111`, `:8112`, `:8113`) over their own stores; those are Rust, not Python.

---

## The seven pass marks

### 1 — `11_branch_rollup` draws 6 files / 7 edges

```
BASE=http://localhost:5199 OUT=docs/plan/bronze/evidence_2026-09-10 node tools/shot_ui1.mjs
```

```
passmark_11_branch_rollup: files=6 edges=7 edgeRows=23 edgesCount=23 / 23 humanGold=1
```

**6 / 7. Met.**

### 2 — `07_enrich_fx` draws 4 files / 3 edges

Same run:

```
passmark_07_enrich_fx: files=4 edges=3 edgeRows=7 edgesCount=7 / 7 humanGold=1
baseline_18_dashboard_mart: files=7 edges=6 edgeRows=25 edgesCount=25 / 25 humanGold=1
no console errors
```

**4 / 3. Met.** The third line is the owner's other baseline: `18_dashboard_mart`, 25 / 25 edge
rows with exactly one `HUMAN_GOLD` row. No console errors with Python dead.

### 3 — every diffable route clean against its oracle

The oracles were restarted **for this check only** and stopped again immediately after:
`:8000` (`raw/lineage_server`) and this repo's Bench on `:8342` (never `:8042`).

| arm | oracle | Rust under test | routes | result |
|---|---|---|---|---|
| ankitha | `:8000` | `:8113`, a **team_finance-only** store | files, search, neighborhood, blocklinks, edges | all clean |
| exp42 | Bench `:8342` | `:8112`, a `corpus/fixtures` store (finding H2) | source, file, blocks, tablegraph | all clean |

```
raw/lineage_server/.venv/bin/python tools/diff_route.py <q> --corpus ankitha \
    --rust-base http://127.0.0.1:8113
raw/lineage_server/.venv/bin/python tools/diff_route.py <q> --corpus exp42 \
    --rust-base http://127.0.0.1:8112 --oracle-b http://127.0.0.1:8342
```

```
files:        clean —  1 call  checked, 0 diffs
search:       clean —  1 call  checked, 0 diffs
neighborhood: clean — 25 files checked, 0 diffs
blocklinks:   clean —  1 call  checked, 0 diffs
edges:        clean —  1 call  checked, 0 diffs
source:       clean —  1 file  checked, 0 diffs
file:         clean —  1 file  checked, 0 diffs
blocks:       clean —  1 file  checked, 0 diffs
tablegraph:   clean —  1 file  checked, 0 diffs
```

**Nine of nine clean. Met.** `convert`, `story` and `run` are `no_oracle` by their own briefs
(Tasks 6b, 10, 12; finding K4 corrected the count from eleven to nine).

**Why the ankitha arm uses `:8113` and not the dev store on `:8110`.** The dev store serves both
windows, and UI2's pass mark needs the exp_42 fixture in it, so `/api/files` there answers **26**.
The oracle's corpus is the 25 `team_finance` files; comparing 26 against 25 is not a divergence,
it is a different question. `:8113` holds exactly what the oracle holds, so the comparison is
like-for-like. `backend/api/tests/files.rs` still pins 25 and stays green — its `test_state()`
seeds `corpus/team_finance` alone, which is the test state, not the dev store (Ruling D13: the
assertion is not edited to match anything).

### 4 — UI2: 23 blocks, 80/80, no Prolog

```
BASE=http://localhost:8110 OUT=docs/plan/bronze/evidence_2026-09-10 node tools/shot_bench.mjs
BASE=http://localhost:8110 OUT=docs/plan/bronze/evidence_2026-09-10 node tools/shot_bench_cells.mjs
grep -ci prolog frontend/ui_file_ide/bench.html
```

```
cells: 46
pills: ["folded 80/80","round trip 80/80","ran 0/23"]
header: lineageQ Bench sas · test_vishnu_testdata_fixed.sas · 23 blocks · 80 statements
        folded 80/80  round trip 80/80  ran 0/23
edges: 12
no console errors

cells: 46  sasCells: 23
no console errors

grep -ci prolog … = 0
```

**23 blocks · 80 statements · folded 80/80 · round trip 80/80, no `prolog == rust` pill, 12 edges,
grep 0. Met.**

### 5 — `run()`: 11 / 11 blocks match

`POST /api/run` on the fixture, `b_002` … `b_012`, `engine: "rust"`, `JAVA_HOME` = Java 17:

| block | verdict | left (node/4 interp) | right (Spark) |
|---|---|---:|---:|
| b_002 | match | 4.1 ms | 4576 ms |
| b_003 | match | 1.2 ms | 4465 ms |
| b_004 | match | 1.5 ms | 4458 ms |
| b_005 | match | 1.6 ms | 4407 ms |
| b_006 | match | 1.6 ms | 4424 ms |
| b_007 | match | 1.5 ms | 4445 ms |
| b_008 | match | 1.6 ms | 4462 ms |
| b_009 | match | 1.7 ms | 4528 ms |
| b_010 | match | 1.7 ms | 4725 ms |
| b_011 | match | 1.5 ms | 4700 ms |
| b_012 | match | 1.8 ms | 4551 ms |

**11 / 11. Met.** The ~4.5 s on the right is a cold Spark JVM per block, not the comparison.

### 6 — `file()` and `blocks(0,40)` under 20 ms over HTTP

A `corpus/perf` store behind `lineageq_api` on `:8111`; `curl -w %{time_total}`, three times each,
on `big_1000.sas` (1000 blocks, receipts 3303 / 3303 / 3303):

| call | run 1 | run 2 | run 3 | mark |
|---|---:|---:|---:|---|
| `file()` | 8.7 ms | 4.4 ms | 3.6 ms | < 20 ms |
| `blocks(0,40)` | 4.4 ms | 4.0 ms | 4.1 ms | < 20 ms |

**Met**, with margin. For scale: the exp_42 Bench's whole-file open of the same file took 63.4 s
(`bronze_perf_receipts_exp42.md`). That number is why this track exists.

### 7 — screenshots against both owner baselines

Five PNGs in `docs/plan/bronze/evidence_2026-09-10/`, taken headless at 2000 × 1200 with
Playwright, with no Python from this repo alive. Every difference from the 2026-09-09 baselines is
listed below.

---

## Every difference from the 2026-09-09 baselines

### UI2 — `bench.png` and `bench_cells.png`

**Deliberately removed (gold §7 C6 and Decision D17).** These are the differences the owner's
resolution of 2026-09-08 predicted: *"strip them, and the port's screenshots will differ from the
baseline in exactly those places, listed explicitly when the port is delivered."*

| # | in the baseline | now | why |
|---|---|---|---|
| 1 | `prolog == rust` pill in the receipt row | gone | C6 |
| 2 | the `Rust` / `Prolog` engine toggle, top right | gone | C6 |
| 3 | status bar `Rust engine · 13 ms` was a toggle read-out | fixed text, same wording | C6 — `S.engine` is pinned |
| 4 | help card row *"Switch engine: Rust ⇄ Prolog"* and the `r` key | gone | C6 |
| 5 | open log line `… prolog == rust: true` | `… round trip 80/80` | C6 |
| 6 | session chip `local` + *"paste a Jupyter link"* box | gone | D17, Jupyter attach dropped |
| 7 | Console rail button (`p`) and its panel | gone | D17 — it existed only to call `/api/exec` and `/api/term` |
| 8 | bottom strip opened on **Terminal** with `run_all run_loops convert fold diff compare ls` chips and a `bench ›` command input | opens on **Log**; the Terminal tab says *"Jupyter attach returns in M5"*; no command input | D17 |
| 9 | DataMatch tab had a *"paste listing"* box | one line saying the comparison needs the Bench's `out/pyspark_ravi` CSVs | D17 |
| 10 | left dock listed similar programs with Jaccard scores | one line saying similarity is the Bench's Python signature index | D17 |

**Consequences of reading the store instead of the Bench** — not chrome, and each already an
accepted row in `bronze_phase2_route_ledger.md`:

| # | in the baseline | now | root cause |
|---|---|---|---|
| 11 | file name `testdata/test_vishnu_testdata_fixed.sas` | `test_vishnu_testdata_fixed.sas` | C4 — a fileid, not a path under `raw/bench_stack/` |
| 12 | block numbers 1-based (`sales_data … block 2`) | 0-based (`sales_data … block 1`) | C1 — the store's `blocks.n` is the index `blocks(from,to)` windows on |
| 13 | kinds `DATA step`, `PROC SQL`, `PROC_PRINT` | `data`, `proc_sql`, `proc_print` | C2 — the parser's head functor, not the Bench's display value |
| 14 | a block that writes nothing is named `proc_print` | its name is blank | C3 |
| 15 | graph nodes ordered as the Bench's `ds_lineage` list | ordered by block, then table | the store returns `tablegraph` sorted; same 12 edges, same 4 layers, same SOURCE → STEP 3 |
| 16 | 4 dashed `ctl` edges drawn from `col_lineage` ∪ `ctl_lineage` | the same 4 edges dashed, decided by `ctl` alone | the store has no `col_lineage` column yet, so an edge that `ctl` names is dashed without checking whether a column also flows along it. Same count, same shape; the column-lineage panel under the graph is therefore always the "click a table" placeholder |
| 17 | a matching block showed its output table under both cells | the badge says `match`, the table area is empty | `POST /api/run` returns verdicts, not rows (see "What this does not prove") |

### UI1 — `passmark_11_branch_rollup.png`, `passmark_07_enrich_fx.png`, `baseline_18_dashboard_mart.png`

| # | in the baseline | now | why |
|---|---|---|---|
| 18 | explorer `ALL FILES 25` | `ALL FILES 26`, with `test_vishnu_testdata_fixed.sas` at the top | the dev store on `:8110` now serves **both** windows, so it holds `corpus/team_finance` + `corpus/fixtures`. UI1's own counts are unchanged: 6/7, 4/3, 7/6 with 25 / 25 edge rows |

Everything else in the three UI1 shots is byte-for-byte the same story as 2026-09-09: same node
colours, same ELK routing, same edge labels, same drawer, same one `HUMAN_GOLD` row.

---

## Accepted divergences, by root cause

The full table is `bronze_phase2_route_ledger.md`; this is the roll-up. **309 accepted rows are
live** — blocklinks 80, edges 84, `file` 64, `blocks` 81 — and **292 more have been retired**
(neighborhood 288 when Task 5d closed three fold gaps, tablegraph 4 when M3a landed `ctl_lineage`).
Every live row is a naming or shaping difference; none is a difference about what the SAS means.

| cause | question(s) | rows | one line |
|---|---|---:|---|
| B1 | blocklinks | 80 | `:8000` names blocks `b_<n>_<hash8>`, the store names them `b_<nnn>`; membership identical |
| B2 | edges | 84 | one oracle-only `FILE_FLOW` self-row (`work.accounts_raw → work.accounts_raw`) |
| C1 | file, blocks | — | `blocks.n` is 0-based here, 1-based in the Bench; the ids are identical |
| C2 | file, blocks | — | `kind` is the parser's head functor, not the Bench's display string |
| C3 | file, blocks | — | `name` is empty when a block writes no table |
| C4 | file, blocks | — | fileid vs a `raw/bench_stack/`-relative path |
| C5 | file | — | `node4_same` / `pyspark_same` are the Prolog proof's columns; NULL on this side |
| C6 | blocks | — | `py` is the block's own runnable program, not a slice of the whole-file pretty print |
| (Task 6) | neighborhood | 288 | three `rust_rules_converter` fold gaps, all closed in Task 5d — rows retired |
| C7 | tablegraph | 4 | retired in M3a when `ctl_lineage` facts reached the engine |

New in M4b, recorded here because `/api/bench/*` has no oracle at all:

| route | divergence | why it is accepted |
|---|---|---|
| `/api/bench/folder` | `links` carries the Bench's `flow` kind only; `subset` and `derived` are missing | `subset` compares two files' whole lineage rule sets and `derived` matches a non-SAS file's name against a SAS stem; this store holds only converted SAS files. The `flow` links come from the same `block_facts` that answer UI1's `blocklinks`, so the two windows cannot disagree |
| `/api/bench/folder` | no `bench` column (`n/m blocks match`) and no `rows` for CSVs | both read files under `out/bench/` that the store does not index |
| `/api/bench/similar` | always `[]` | the score is a Jaccard over the Bench's Python signature index (`out/bench/sig`); returns in M5 |
| `/api/bench/listing` | always `{loaded:false}` | a pasted PROC PRINT is compared against `out/pyspark_ravi` CSVs, which the store does not hold; returns in M5 |
| `/api/bench/save` | writes `corpus/*/…/work/<file>`, not `out/bench/buffers/<mangled path>` | `corpus/README.md` makes `work/` the one stage a person edits by hand; D17 confines the route to it |

---

## What this does not prove

- **UI2 is still vanilla JavaScript and still unwindowed.** Decision D2 chose the extraction now
  and the TypeScript port in M5. `loadProgram` asks `blocks()` for the *whole* file and puts every
  cell in the DOM, exactly as the Bench did. The pass mark is a 23-block file; nothing here says
  anything about `big_1000.sas` in this window. M5's marks — open to first cell < 1 s, ↓ key
  < 16 ms, DOM < 25 k elements — are unmeasured.
- **Jupyter attach is gone, not ported.** Four Bench routes (`sessions`, `session`, `exec`,
  `term`) were dropped, not reimplemented. The Console panel and the gated terminal went with
  them. Nothing in this slice proves they can be brought back cheaply.
- **`run()` returns verdicts, not data.** DataMatch runs inside the Rust API and only samples of a
  *differing* table come back. So "11/11 match" is a real receipt, but UI2 cannot show you the
  rows behind a match — the cell's table area is empty and the DataMatch tab counts what it can
  see. Being able to look at the data is a UI3 concern (gold §7 C3) and a shape change to `run()`.
- **L4 has not run.** The verification loop's fourth leg — `lineage_left == lineage_right` — does
  not exist yet (M6). A migration that produces the right numbers with the wrong lineage would
  still pass everything on this page, and gold §3 is explicit that such a migration has failed.
- **Nothing writes a verdict.** `corpus/team_finance/sas/final_match/*.verdict.json` still says
  `"accepted": false` with zeroed counts everywhere. No gate computes acceptance; the "verified"
  idea is painted, not derived. M6 owns it.
- **`human_edits` still has no writer.** The one `HUMAN_GOLD` row in UI1's drawer comes from a
  fixture loaded by `lineageq_store human-edit`. No UI writes one, and the stored row still names
  pre-Task-5 `ankitha_1/…` fileids on both sides (finding G9).
- **The corpus sweep is one file wide.** Marks 4, 5 and 6 all measure a single file each — the
  exp_42 fixture and `big_1000.sas`. `neighborhood` is the only mark that walks all 25 files.
- **Four team_finance files still panic the emitter** (`coalesce` ×2, `today`,
  `orderby(...) not a list`), caught by `catch_emit` (finding I5). They convert, they appear in
  UI1, and their PySpark is missing.
- **UI3 does not exist**, so the claim in gold §5 — that Prolog and Rust are two independently
  written engines checking each other — is proved today only by `POST /api/run`'s `engine: prolog`
  arm on eleven blocks of one file (M3b), never over a corpus.

---

## Decisions

- **PROVEN ∎** — the seven numbers above, each re-measured on 2026-09-10 with this repo's Python
  stopped by verified pid, commands and outputs as quoted. `cargo test --workspace --release`: 84
  passed, 0 failed. `npx vitest run` in `frontend/ui_across_file_ui` after `npm ci`: 174 passed,
  33 files.
- **PROVEN ∎** — no forwarder survives: `oracle.rs`, `routes/forward.rs` and the router's
  `.fallback()` are deleted, an unknown `/api/` path is a 404, and `/api/health` reports twelve
  landed and nothing forwarded.
- **ASSUMED** — that the foreign `:8042` process played no part. It was running throughout and
  was never dialled: nothing in `frontend/`, `tools/shot_*.mjs` or the Rust binary contains that
  port any more, and the Rust binary no longer has an `--oracle-b` flag to point at it. Not proved
  by packet capture.
- **OPEN** — whether `run()` should return the rows behind a match, and if so whether that belongs
  to `run()` or to a separate `run_tables()` read. It blocks UI2 showing data (difference 17).
- **OPEN** — `/api/bench/folder`'s missing `subset` and `derived` link kinds. They were the
  Bench's way of grouping a SAS file with its PySpark twin, and D7 (SAS-only through M4) has kept
  the question shut so far.
