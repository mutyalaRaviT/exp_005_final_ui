---
tags: [plan, silver, phase2, api, vertical_slice, design]
---
# silver_phase2_vertical_slice_design — one slice through every layer

**Why this file exists.** The plan builds exp_005 in layers: phase 1 the store, phase 2 the
API and UI1, phase 3 UI2. The owner changed that on 2026-09-09 — *"lets plan for phase 2:
start unified development of a vertical slice"*. A slice is cut through **every** layer at
once instead: Rust engine → DuckDB → one Rust API → both shipping UIs, with the block run
that compares the original against the migration. This page is the design that was agreed
in chat before any of it was built.

**Inputs → outputs.** the owner's four scoping answers of 2026-09-09 + what was measured
running the copies that day (`bronze_local_run_2026-09-09.md`) + Fable's store design
(`silver_duckdb_store_design.md`) → this design → an implementation plan → phase 2.

**Status.** Silver. The owner approved the design in chat and asked for one change (no
legacy path aliases), which is folded in below. Not yet promoted.

---

## 1. What the slice is, and what it is not

**In.** One Rust API binary serving **both** shipping UIs from **one** DuckDB store, with:

- UI1, across files, extracted from `raw/node4_viz`
- UI2, the Bench, `bench.html` repointed — **not** rewritten in TypeScript
- `run()`: a block executed both ways and the two results compared
- every route proved against the Python implementation it replaces

**Out, deliberately.**

| out | why |
|---|---|
| UI3, the verification workbench | owner scoped the slice to the two shipping UIs |
| UI2's TypeScript rewrite and cell windowing | that is phase 3, with its own pass mark (`big_1000` open < 1 s, DOM < 25 k). Rewriting the UI *and* moving its backend in one step means a failure has two possible causes. |
| the rest of Fable's 13-table design | `macros`, `testcases`, `librefs` wait for the features that need them |

**Why UI2 is repointed and not rewritten.** The slice's question is *"can one Rust API
carry both UIs?"*. Rewriting UI2 answers a different question at the same time and makes
the first one unanswerable.

---

## 2. Architecture

```
   UI1  frontend/ui_across_file_ui   (Vite, :5199)
                    │
                    ├────────►  lineageq_api   (Rust, axum, :8100)
                    │             ├─ answers from the store, for landed routes
   UI2  frontend/ui_file_ide       └─ forwards to the Python oracle, for the rest
        (bench.html, :8142)                       │
                    │                             ▼
                    └────────►          :8000 lineage_server   (dev only)
                                        :8042 convert_api      (dev only)
                                                  │
                              one DuckDB store ◄──┘ (Rust side only)
```

One binary. One store. The Python servers are **the oracle, not a dependency**: when the
slice is done they are stopped and both UIs still work. That is pass mark 1.

---

## 3. The API — one canonical surface

The routes are plan §6's questions. There are **no aliases** for the old Python paths: the
owner rejected them on 2026-09-09, and they were the wrong idea — they would have frozen a
regex scanner's wire shape into the product.

| question | who asks | replaces |
|---|---|---|
| `neighborhood(file\|table, up, down)` | UI1 | `:8000 /api/neighborhood` |
| `blocklinks(files)` | UI1 | `:8000 /api/blocklinks` |
| `edges(files, filter, level, offset, limit)` | UI1 | `:8000 /api/edges` |
| `files()` | UI1 | `:8000 /api/files` |
| `search(q)` | both | `:8000 /api/search` |
| `source(fileid)` | UI1 | `:8000 /api/file/{id}` |
| `file(fileid)` | both | `:8042 /api/open` (the header + block list half) |
| `blocks(fileid, from, to)` | UI2 | `:8042 /api/open` (the text half) |
| `tablegraph(fileid)` | UI2 | `:8042 /api/lineage` |
| `story(table)` | UI2 | `:8042 /api/lineage` |
| `run(fileid, block_id, engine)` | UI2 | `:8042 /api/run_block` |
| `convert(folder\|file)` | both | `:8042 /api/convert` |

That is **twelve** questions where plan §6 lists ten. The difference is deliberate and
comes from Fable's audit of the working backend:

- **added** `edges(files, filter, level, offset, limit)` — UI1's edges drawer calls it, and
  the plan simply missed it. It is the source of the `25 / 25` in the owner's screenshot.
- **added** `source(fileid)` — UI1's code pane needs whole-file text, and `file()` must not
  carry it.
- **dropped** `proof(fileid)` — gold §7 C2 removed the background proof; verification is
  UI3's, later.

`file()` returns the block list **with no text**; `blocks()` is the windowed text.

### How a route is served while it is being built

Each handler is one of two things, and which one is a per-route fact recorded in the
progress table:

```rust
match landed(route) {
    true  => answer_from_store(&db, q),          // the destination
    false => translate(forward_to_python(q)?),   // the scaffold
}
```

The forward-and-translate arm is deleted route by route as each lands. It replaces the
separate proxy an earlier draft proposed: because the translation to canonical shape has
to be written anyway for the differential oracle, putting it in the handler means it is
written **once**, and the UIs are repointed **once**, at the start, and never break.

---

## 4. The differential oracle

The owner chose this over golden fixtures and over screenshots alone. It is the house rule
— *Prolog is the reference, Rust mirrors it* — applied to the API.

`tools/diff_route.py <question>` replays one question across the whole corpus (25 ankitha
files, plus the exp_42 SAS files for UI2's questions) against **both** arms of the handler
above, and diffs the canonical JSON. A route lands when the diff is empty, or every
remaining difference is written down and justified.

**The honest wrinkle, stated up front.** `:8000` is a regex scanner; exp_005 is a real
parser. On some files they *ought* to disagree, and the parser is the one that is right.
So a difference is not automatically a bug. Every difference must therefore be one of:

- **a Rust bug** → fix Rust
- **an accepted divergence** → recorded in the progress table with the file, the field, and
  one sentence saying why the parser is right

A tool that lets a difference be waved through silently is worse than no tool, because it
converts an unknown into a false reassurance. There is no third category and no `--force`.

---

## 5. Store changes this slice forces

From `silver_duckdb_store_design.md` §6, only what these routes need:

| change | forced by | evidence |
|---|---|---|
| populate `edges.block_id` | `blocklinks`, `tablegraph`, `story` | all 1204 edge rows have `block_id = ''` today; lineage is run over the whole file, so no edge knows its block |
| `node4` gains `b0`, `b1` | `run()`, UI2 cell offsets, Prolog `trace/5` | columns today stop at `trace_l1` |
| `files.source` | UI1's code pane | it needs whole-file text; `file()` must not carry it |
| `blocks.block_hash` | `human_edits` surviving an edit | `:8000` pins notes to `b_<n>_<hash8>`; positional `b_017` shifts when a block is inserted above |
| reconvert key includes the spec hash | correctness | today a grammar change leaves stale rows, because the key is the file hash alone |
| `runs`, `run_tables`, `run_samples` | `run()` | the five sample differing rows need somewhere to go |

`block_id` itself stays positional this slice. Making it content-addressed changes node/4
and therefore Prolog, and the owner's rule is that Prolog moves first.

---

## 6. `run()` — L2 against L3

Four steps. Three already exist; one is new.

| step | how | status |
|---|---|---|
| the block's PySpark program | Rust `block-programs` | exists |
| test rows for the block | shell to `loops/gen_block_testdata.py` | exists — Python + Z3, and Z3 has no good Rust binding. This is dev tooling, so shelling out is honest, not a compromise. |
| `output_left` | Rust `interp` over node/4 | exists |
| `output_right` | shell to python, running that program on local Spark | exists |
| compare | **port `pipeline/datamatch.py::compare_rows` to Rust** | **new**, ~100 lines |

The comparison is the only new code, and it has two reference implementations to be
checked against: `pipeline/datamatch.py` and `server/datamatch.ts`. Normalisation is the
part that matters — trim, `.` and `""` both empty, floats to 6 dp, `-0` → `0`, whole floats
to integers — and it is where a wrong "match" would come from.

Verdicts (`match`, `match-warn`, `differs`, `missing`) and up to five differing rows are
written to `runs` / `run_samples` so UI2 reads them back instead of recomputing.

**Under the gold doc, `engine=prolog` computes `output_left` via `swipl sas_interp.pl`.**
That path stays reachable from the API but is not surfaced in UI2 — it is UI3's, later.

---

## 7. What changes in the two UIs

**UI1** — `raw/node4_viz` extracted to `frontend/ui_across_file_ui`:

- `src/api.ts`: the six fetches move to canonical question names
- `vite.config.ts`: proxy target `:8000` → `:8100`
- `src/useLineageGraph.ts:15` and `src/holaLayout.ts:9`: two hardcoded
  `/Users/mutyala/...` paths, both stale, both fixed
- `scripts/smoke.mjs`: reused, with its hardcoded `!== 11` file-count assertion
  parameterised

**UI2** — `bench.html` to `frontend/ui_file_ide`, repointed, and the Prolog surface removed
per gold §7 C6:

| removed | where | note |
|---|---|---|
| `prolog == rust` pill | `bench.html:365, 521` | reads three booleans nothing else uses |
| Rust/Prolog engine toggle | `:371-373, 1032-1033, 1144, 1262` | `S.engine` pins to `"rust"`; ten ternaries collapse |
| `prolog == rust` receipt line | `:534` | one log row |
| help text naming both engines | `:452` | |
| `folded` / `round trip` pills | `:363-364, 519-520` | **kept**, but sourced from Rust's own counts, which `convert_api.py:91` already computes as `rust_summary` and throws away |

`statements` is load-bearing beyond the pill (`:517` header meta) and stays.

**This will make UI2 differ from the owner's baseline screenshot in exactly those places.**
That is intended and was decided on 2026-09-08; the differences get listed when the slice
is delivered.

---

## 8. Pass marks

1. `?file=ankitha_1/11_branch_rollup.sas&up=1&down=1` draws **6 files, 7 edges** — with
   both Python servers **stopped**
2. `?file=ankitha_1/07_enrich_fx.sas&up=1&down=1` draws **4 files, 3 edges**, likewise
3. every landed route: zero unexplained diffs across 25 files; every accepted divergence
   written down
4. UI2 opens `test_vishnu_testdata_fixed.sas` — 23 blocks, 80 statements, folded 80/80,
   round trip 80/80 — with **no Prolog visible anywhere**
5. `run()` on that file: **11/11 blocks match**, the receipt `bench_receipt.py` produced on
   2026-09-09
6. `file()` < 20 ms and `blocks(0,40)` < 20 ms still hold, through HTTP this time
7. screenshots against both owner baselines, with every difference listed

Marks 1, 2 and 5 are the real ones: 1 and 2 because they only pass when Python is gone,
5 because it is the only mark that proves the migration is *correct* and not merely fast.

---

## 9. Risks

| risk | mitigation |
|---|---|
| the parser and the scanner disagree, and telling improvement from regression is a judgement call each time | every divergence written down with a reason; no silent accept |
| `run()` drags Spark into the slice — ~4.5 s per block, 50 s for 11 | it is the last route to land, and its diff runs on one file, not the corpus |
| the store migration is bigger than §5 suggests once `block_id` is populated per block | lineage must run per block rather than per file; if that changes edge counts, mark 1 catches it immediately |
| repointing UI2 breaks something invisible in 1318 lines of vanilla JS | the Bench's own receipts (23 blocks, 80/80) are the tripwire |

---

## Decisions

- **PROVEN ∎** — `edges.block_id` is empty on all 1204 rows (queried 2026-09-09);
  `07_enrich_fx` is 4 nodes / 3 edges and `11_branch_rollup` 6 / 7 (both from `:8000`);
  `run()`'s four steps all exist except the comparison, and 11/11 blocks matched on
  2026-09-09; UI2's Prolog surface is at the line numbers listed.
- **PROVEN ∎** — dropping swipl from UI2 is a **serialization** task, not a semantics one:
  Rust already emits `block, seq, term, trace(file,l0,l1,b0,b1)`, comments are already in
  its token stream (that is how `rebuild_source` works), and `emit_pretty.rs` already
  produces the pretty PySpark that swipl generates. An earlier claim in this session that
  this was a large engine job was wrong.
- **ASSUMED** — that axum is the right HTTP crate. Nothing in the plan requires it; it is
  chosen for being unsurprising. Phase 6 needs Tauri commands over the same handlers, so
  handlers must not be axum-shaped internally.
- **ASSUMED** — that the exp_42 corpus is enough to land UI2's questions. It is 8 files.
- **OPEN** — whether `convert()` streams `block ready` events, as plan §6 says. Nothing in
  the slice consumes them yet.
- **OPEN** — whether one DuckDB connection is shared (as `:8000` does) or one per request
  thread. Fable's design left this open too, and `run()` makes it sharper, because a run
  writes while the UI reads.
- **OPEN** — what happens to `:8000`'s ten unused routes (history, save, order, excel,
  arrow, edits, sync). `edits` matters: it is how `human_edits` are created, and UI1 has an
  edges drawer that writes them.
