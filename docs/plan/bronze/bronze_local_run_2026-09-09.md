---
tags: [plan, bronze, run, receipts, ui1, ui2]
---
# bronze_local_run_2026-09-09 — both UIs run from `raw/`, on this laptop

**Why this file exists.** `raw/` was copied in blind: the sources were moved into the repo
before anything proved they still worked from their new home. This is the receipt of the
first run out of `raw/`, with the numbers and the screenshots, so nobody has to take the
copy on trust.

**Inputs → outputs.** `raw/lineage_server` + `raw/node4_viz` + `raw/bench_stack` on
darwin 25.5.0, 2026-09-09 → two running UIs → four PNGs in `evidence_2026-09-09/` and the
tables below.

**Verdict: both UIs run. Phase 2's pass mark is met, ahead of phase 2.**

## What was built, and how long it took

| step | result |
|---|---|
| `cargo build --release` (rust_engine) | OK, **6.95 s**, 9 warnings → `target/release/lineageq_sas` |
| `npm install` (node4_viz) | OK |
| venv for `lineage_server` | OK, but `requirements.txt` is **incomplete** — see below |
| venv for `bench_stack` | OK (`z3-solver requests websocket-client pyspark`) |

Tooling already present: `swipl`, `cargo`, `node v24.14.0`, `python3 3.11`.

## Two things `raw/` was missing, found only by running it

1. **`server/requirements.txt` lists four packages; the app imports nine.** It names
   `fastapi uvicorn pyarrow dulwich`; `app.py` also needs `pyahocorasick`, `duckdb`,
   `openpyxl`, `sqlglot`, `pyyaml`, and `sas_lineage.data_step` needs `parse`. First run
   died at `indexer.py:35 import ahocorasick`.
2. **`out/grammar/` was not copied**, only `out/spec/`. The Bench opened with
   `fold produced no node/4: ERROR: grammar file not found: out/grammar/sas.pl` and zero
   blocks. `out/grammar/{sas,pyspark}.pl` (56K) is an **input** to the fold, not an output.

Both fixed. Nothing else was missing: the restructure into sibling layout held.

## UI1 — across files (`node4_viz` + `lineage_server`)

Backend on `:8000` from `raw/lineage_server/server` (cwd verified), UI on **`:5199`**.

> Ports 5173, 5174, 5175, 8042 and 8043 were already taken by **pre-existing servers on
> this laptop**. `:5174` answered correctly throughout, but it is the owner's exp_003
> instance, not this copy. Screenshotting it would have proved nothing, so every number
> below comes from `:5199` and `:8000`, whose working directories were checked with
> `lsof -d cwd` to confirm they are the copies under `raw/`.

Backend on startup: `state ready, 25/25 sources indexed, 87 tables known`.

| deep link | files | edges | edge rows | console errors |
|---|---|---|---|---|
| `?file=ankitha_1/18_dashboard_mart.sas&up=1&down=1` | 7 | 6 | **25 / 25** | none |
| `?file=ankitha_1/11_branch_rollup.sas&up=1&down=1` | **6** | **7** | 24 / 24 | none |

**Phase 2's pass mark, verbatim from the plan:** *"the deep link
`?file=ankitha_1/11_branch_rollup.sas&up=1&down=1` draws the same 6 files and 7 edges as
`:5174` today"*. Measured: **6 files, 7 edges.** Met — and met before phase 2 starts,
because it is still the Python API answering, not the Rust one.

Against the owner's reference screenshot of `18_dashboard_mart`: ALL FILES 25 ✓,
CURRENT 7 ✓, EDGES 25/25 ✓, provenance badges `PROJECT`/`BLOCK` × `HUMAN_GOLD`/
`INFERRED`/`FACT` ✓, code pane 1 section ✓. **Differences:** the reference has files
expanded to blocks and `Layout · Custom`; the fresh load is collapsed with `+` toggles and
`Layout · Medium`. That is view state, not data — the `+` controls are present and the
block edges are in the table.

## UI2 — the Bench (`bench_stack`)

Server on **`:8142`** (`:8042` was the owner's pre-existing Bench — its `/api/health`
answered `rust: true, swipl: true` and was **not** this copy; cwd of `:8142` verified as
`raw/bench_stack`).

`POST /api/open {"path":"testdata/test_vishnu_testdata_fixed.sas"}` → **1.58 s**:

| receipt | value | owner's screenshot |
|---|---|---|
| blocks | 23 | 23 ✓ |
| statements | 80 | 80 ✓ |
| folded | 80 | folded 80/80 ✓ |
| roundtrip | 80 | round trip 80/80 ✓ |
| source_match | true | ✓ |
| node4_same | true | `prolog == rust` green ✓ |
| pyspark_same | true | ✓ |
| pyspark_pretty_same | true | ✓ |
| rust_us | 26 325 (26 ms) | status bar said 16 ms |
| ran | 0/23 | ran 0/23 ✓ |

Header rendered: `lineageQ Bench · SAS · testdata/test_vishnu_testdata_fixed.sas ·
23 blocks · 80 statements · folded 80/80 · round trip 80/80 · prolog == rust · ran 0/23`.
Terminal receipt line and the `COMMAND | block 2 : sales.sales_data | Rust engine · 13 ms`
status bar both match. 46 cells in the DOM, 23 SAS cells. No console errors.

Two views captured: the table-lineage graph (12 edges, SOURCE → STEP 1 → STEP 2 → STEP 3)
and the CELLS pane, whose numbering, tree indentation and
`PROC SQL · L111-121 · reads q1_sales` line format match the reference exactly.

## Screenshots

`evidence_2026-09-09/` — `baseline_18_dashboard_mart.png`,
`passmark_11_branch_rollup.png`, `bench.png`, `bench_cells.png`. Taken headless with
Playwright at 2000×1200 by `tools/shot_ui1.mjs`, `tools/shot_bench.mjs`,
`tools/shot_bench_cells.mjs`.

## What this does NOT prove

- **Nothing was run.** `ran 0/23`. Legs L2 and L3 of the verification loop
  (`output_left` vs `output_right`) were never executed — no Spark job ran, no
  DataMatch verdict was produced. Only fold, round trip and codegen were exercised.
- **Prolog is confirmed load-bearing.** `swipl: true` on both servers, and the run
  succeeded only after `out/grammar/sas.pl` was in place — the grammar the Prolog fold
  loads. This is direct evidence for the exploration's finding that the Bench cannot list
  blocks without swipl, and therefore that
  `gold_three_uis_and_verification_loop.md` §7 C6 (strip Prolog from UI2) needs Rust to
  write `node4.json` first.
- **UI1 is still on the Python API**, not the Rust one. Phase 2's pass mark is met by the
  stand-in; it will have to be met again by `backend/api/`.

## Decisions

- **PROVEN ∎** — every number above was measured on 2026-09-09; the two servers' working
  directories were verified with `lsof -p <pid> -a -d cwd` to rule out the pre-existing
  instances on `:5174` and `:8042`.
- **OPEN** — why `rust_us` is 26 ms here and the reference screenshot says 16 ms. Same
  file, same block count. Probably cold cache; not investigated.
- **OPEN** — whether `requirements.txt` should be corrected in `raw/` (which is meant to
  be untouched) or only in the extracted copy. Left untouched; recorded here instead.
