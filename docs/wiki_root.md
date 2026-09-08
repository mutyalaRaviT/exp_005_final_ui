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

## Story

The Bench (exp_42) proved SAS → PySpark by rules, with a page that shows one file well. The
across-files canvas (exp_003 `node4_viz`) proved that asking a store for a neighbourhood keeps a
graph fast at any size. Measured at 1000 blocks, the Bench's whole-file open and whole-page redraw
break down. This track joins the two: convert once into a store with Rust, ask small questions from
TypeScript, and draw only what is on screen.
