---
tags: [plan, bronze, performance, receipts]
---
# bronze_perf_receipts_exp42 — the numbers behind the design

**Why this file exists.** The plan's shape is forced by measurements. They live here with how they
were taken, so nobody has to trust the plan's summary.

**Inputs → outputs.** exp_42 perf worktree `perf-1000-blocks` (2026-09-08): `testdata/gen_big.py`
made `big_100 / big_1000 / big_2000.sas`; `testdata/perf_open.py` timed `/api/open`;
`testdata/perf_steps.py` and `perf_swipl.sh` timed each pipeline step; `testdata/perf_ui.js` timed
UI actions in Chromium (Playwright MCP, 1500×900) → the tables below. Full write-up:
`exp_42_test_vishnu/reports/bench_perf_1000_blocks.md` (worktree, uncommitted at the time of writing).

## Server: opening a file (Bench, whole-file)

| file | open | blocks | statements | ds edges | JSON |
|---|---|---|---|---|---|
| big_100 | 5.7 s | 100 | 331 | 119 | 123 KB |
| big_1000 | 63.4 s | 1000 | 3303 | 1204 | 1.1 MB |
| big_2000 | 140.0 s | 2000 | 6606 | 2405 | 2.2 MB |

## Where the 65 s goes (big_1000, steps in isolation)

| step | time | engine |
|---|---|---|
| tokenise | 0.2 s | Python |
| fold → node/4 | 30 s | Prolog DCG, ~9 ms per statement |
| print back + re-fold (round trip) | 32 s | Prolog DCG |
| PySpark codegen | 0.1 s | Prolog |
| fold + unfold + node/4 + PySpark + pretty | 0.6 s | Rust |
| pretty PySpark | 7.6 s | Prolog |
| lineage | 0.0 s | Rust |

Caveat: the swipl passes were timed while another open of the same file ran on the same machine.
The shape holds: two Prolog parses of about thirty seconds each.

## Browser: one key press (Bench, Chromium)

| action | 100 blocks | 1000 blocks |
|---|---|---|
| full cell rebuild | 35 ms | 912 ms |
| ↓ focus next (p50) | 19 ms | 623 ms |
| esc | 18 ms | 707 ms |
| graph open (layout + SVG) | 4 ms | 45 ms |
| graph node click | 19 ms | 320 ms |
| IDE open | 26 ms (495 lines) | 211 ms (4610 lines) |
| IDE line move | 8 ms | 68 ms |
| DOM elements | 6.7 k | 351 k |
| JS heap | 3 MB | 63 MB |

In the user's Chrome with the feel pass applied, 1000 blocks: rebuild 1681 ms, ↓ 1250 ms, graph
open 42 ms, IDE open 400 ms. Same shape, slower machine state.

## Across files (`node4_viz` on the `:8000` API, ankitha_1, 25 files)

| call | time | size |
|---|---|---|
| `/api/neighborhood?file=ankitha_1/11_branch_rollup.sas&up=1&down=1` | 10 ms | 4 KB, 6 nodes, 7 edges |
| `/api/file/ankitha_1/11_branch_rollup.sas` | 4 ms | 2 KB |

That instance reported `scanner: rg, synced_at: null`: it answered from the ripgrep scan, not the
synced DuckDB store.

## Also found

- At 1000 blocks, 42 subquery PROC SQL blocks (from block 659) show no PySpark: the pretty file has
  them, but its SAS echo drifts a few characters there, so the section's line range no longer
  overlaps the block. 345 blocks at 2000. Pretty-printer trace drift at scale.
- `pyspark_pretty_same` is false for all three big files while node/4 and raw PySpark match.
- The 1000-table graph lays out in 45 ms but is 14,256 px wide with 70 layers; at the 30 % fit floor a
  third of it fits and labels are unreadable.

## Decisions
- **PROVEN ∎** — every number above has a run behind it in the perf worktree (`out/bench_perf_open_*.json`, the tool outputs quoted in the report).
- **OPEN** — the 2000-block browser measurement did not finish (the Playwright tab lost focus and its animation frames stopped); rerun with the tab in front.
