---
tags: [root, hub]
---
# wiki_root — exp_005_final_ui_v3

**Why this file exists.** The one page to open first. It says what the track is, where every page sits, and what happened in order.

**Inputs → outputs.** The owner's brief of 2026-09-08 and the exp_42 perf spike → this vault.

## Status (2026-09-08)

Planning. No code copied yet. The plan is a `gold_draft`; the owner promotes it.

## Map

| Dimension | Hub | What it holds |
|---|---|---|
| plan | [[plan]] | the plan, the copy list, the perf receipts |

Later dimensions, opened when their first page exists: `backend`, `frontend`, `rules`.

## Ledger

- 2026-09-08 — track opened. Pages: [[gold_draft_exp_005_plan]], [[raw_sources_to_copy]], [[bronze_perf_receipts_exp42]].
- 2026-09-09 — one local corpus. The two UIs read two different corpora through two
  different backends until today; see `corpus/README.md` and the plan/spec at
  `docs/superpowers/plans/2026-09-09-team-finance-corpus.md` /
  `docs/superpowers/specs/2026-09-09-team-finance-corpus-design.md`.
- 2026-09-10 — M0 re-baseline: briefs 7–14 corrected, corpus/fixtures/ registered. Plan: docs/superpowers/plans/2026-09-10-milestone-plan.md.
- 2026-09-10 — M1: UI1 without Python. `blocklinks`, `edges` and `source` land in Rust (Tasks 7–8); UI1 extracted from `raw/node4_viz` to `frontend/ui_across_file_ui/`; pass marks 6/7, 4/3 and 25/25 re-measured with `:8000` stopped. Evidence: `docs/plan/bronze/evidence_2026-09-10/`.
- 2026-09-10 — M3b: `run()` lands (Tasks 11–12). `POST /api/run` executes one SAS block two ways — the node/4 interpreter on the left (Rust in-process, or Prolog with `engine: prolog`), the emitted PySpark on local Spark on the right — over Z3-generated rows, and judges them with `datamatch.rs`, the row comparison ported from `pipeline/datamatch.py` and cross-checked against it 11/11 on real CSVs. Pass mark 5 met: 11 blocks `b_002`…`b_012` all `match` with `engine: rust`, and all 11 `match` again with `engine: prolog`; `LANDED` reaches eleven of twelve, only `convert` still forwards. The Z3 generator's staleness behind that receipt is written up in `docs/plan/bronze/bronze_phase2_route_ledger.md` (Task 12 note).
- 2026-09-10 — M2: the in-file questions. `file`, `blocks`, `tablegraph` and `story` land in Rust (Tasks 9–10), plus UI1's own `/api/file/<fileid>` detail; `LANDED` reaches ten of twelve, only the two POST-shaped questions (`convert`, `run`) still forward. Pass marks: 23 blocks and 80/80/80 on the exp_42 fixture, 12 `tablegraph` edges with `sales.q1_avg_sales` made by `b_007`, and `file`/`blocks` over HTTP on `big_1000.sas` at 4.9–9.8 ms and 4.4–5.6 ms against a 20 ms mark. 149 accepted divergences in seven root causes: `docs/plan/bronze/bronze_phase2_route_ledger.md` (Task 9 and Task 10 notes).
- 2026-09-10 — M3a: five engine defects closed, Prolog first then Rust — `0.40` round-trips (team_finance L1 goes 24/25 → 25/25), UNION ALL PySpark renders every branch, CASE WHEN and a lone `.` get px/pe rules, the `ctl` lineage label reaches the store (root cause C7 retired, 12 `ds` + 4 `ctl` on the fixture), and the Prolog pretty printer slices the source by bytes. Ledger: `docs/plan/bronze/bronze_phase2_route_ledger.md`.

## Story

The Bench (exp_42) proved SAS → PySpark by rules, with a page that shows one file well. The
across-files canvas (exp_003 `node4_viz`) proved that asking a store for a neighbourhood keeps a
graph fast at any size. Measured at 1000 blocks, the Bench's whole-file open and whole-page redraw
break down. This track joins the two: convert once into a store with Rust, ask small questions from
TypeScript, and draw only what is on screen.
- 2026-09-09 — store design. Page: [[silver_duckdb_store_design]] (silver; the owner promotes). The strawman already meets phase 1's pass mark (1.09 s convert, 1.7 ms `file()`, 1.05 ms `blocks(0,40)` on `big_1000.sas`); the page corrects what it stores.
