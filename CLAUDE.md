# CLAUDE.md — exp_005_final_ui_v3

September 2026 track: the third and final UI, built as a product shape. Rust backend, TypeScript
frontend, DuckDB store, rules packs. **Three** windows, two of which ship: **across files** (UI1,
the exp_003 `node4_viz` canvas), **inside a file** (UI2, the exp_42 Bench) and the **verification
workbench** (UI3, the owner's alone), which is a third window in the same app behind a build flag
that keeps it out of the release binary. Opened 2026-09-08 on the owner's brief (quoted in the
plan); the three-UI shape and the four-leg verification loop are
`docs/plan/gold/gold_three_uis_and_verification_loop.md`, owner gold, which wins on conflict.
Corrections C1–C7 from its §7 were applied here and to the plan on 2026-09-10 (Task 14, M4b).

## Read before doing anything

1. `docs/wiki_root.md` — the hub.
2. `docs/plan/gold/gold_draft_exp_005_plan.md` — the plan: why, shape, phases, pass marks, decisions.
3. `docs/plan/raw/raw_sources_to_copy.md` — every file that is copied in, and from where.
4. `docs/plan/bronze/bronze_perf_receipts_exp42.md` — the numbers that drove the design.

## Layout (planned; a folder exists once its README says what is in it)

| Path | What it is |
|---|---|
| `backend/` | Rust. `rust_rules_converter/` (tokenise, fold, node/4, PySpark, lineage), `prolog_rules_converter/` (drives swipl as the **independent second engine**: it computes `output_left` for UI3's loop — not a background proof service, and never on a UI1 or UI2 path), `rust_inferred_duckdb/` (the store and the query API), `testdata_rules/engine/` (Z3 test data from node/4 branches), `api/` (HTTP + Tauri commands). |
| `frontend/` | TypeScript. `ui_across_file_ui/` (UI1 — files, blocks, tables across a folder; extracted from `node4_viz`, which was deleted from `raw/` on 2026-09-10, D11), `ui_file_ide/` (UI2 — one file: SAS ⇄ PySpark cells, table graph, strip; `bench.html` extracted from the Bench on 2026-09-10, vanilla JS until the M5 TypeScript port), `shared/` (design tokens, URL state, API client). Later: UI3, behind the build flag. |
| `rules/` | `sas_pack/`, `py_pyspark_pack/`, and `*/test_data_gen/`: pyDSL spec, its JSON, the generated `.pl`, the node/4 schema, interfaces, generators. Only what the engines read. |
| `build_bin/tauri_builder/` | Desktop build: one binary with the backend inside and the **two shipping** UIs as windows. The build flag that excludes UI3 from the release bundle is part of this folder's pass mark (C4): grepping the bundle must find no UI3 code. |
| `corpus/` | `team_finance/{sas,hive}/{raw,auto_convert,work,final_match}` — the one corpus both UIs read; `perf/` for the big fixtures. See `corpus/README.md`. |
| `docs/` | Obsidian medallion vault. One dimension: `plan/`. Later dimensions: `backend/`, `frontend/`, `rules/`. |
| `tools/` | `wiki_from_git.py` (planned): doc comments, commit messages and git notes → bronze pages. |

## Rules

- Follow the `medallion-wiki-obsidian` skill for any page under `docs/`. Gold is owner-only; agents write `gold_draft_*`.
- The wiki grows from the code: every module carries a doc comment that says why it exists and its inputs → outputs; every commit message says what changed and why; `git notes` carry the receipts (timings, counts). Pages are generated from those, then curated.
- Prolog is the reference, Rust mirrors it (owner rule, exp_42). **Corrected by gold §5 (C2, C6):** there is no background proof and no receipt bar. Prolog is the *independent second engine* — it computes `output_left` inside UI3, so the loop is not Rust checking its own homework — and it appears nowhere in UI1 or UI2. Neither shipping window names it: `grep -ci prolog frontend/ui_file_ide/bench.html` is 0, and stays 0.
- Copy, do not re-derive: the engine, the rules and the two UIs are copied from the tracks named in `raw_sources_to_copy.md`, then documented and trimmed. Name the source path in the first commit of every copied file.
- Java 17 for Spark runs: `export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home`.
