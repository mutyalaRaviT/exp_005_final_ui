# CLAUDE.md — exp_005_final_ui_v3

September 2026 track: the third and final UI, built as a product shape. Rust backend, TypeScript
frontend, DuckDB store, rules packs. Two graphs: **across files** (the exp_003 `node4_viz` canvas)
and **inside a file** (the exp_42 Bench). Opened 2026-09-08 on the owner's brief (quoted in the plan).

## Read before doing anything

1. `docs/wiki_root.md` — the hub.
2. `docs/plan/gold/gold_draft_exp_005_plan.md` — the plan: why, shape, phases, pass marks, decisions.
3. `docs/plan/raw/raw_sources_to_copy.md` — every file that is copied in, and from where.
4. `docs/plan/bronze/bronze_perf_receipts_exp42.md` — the numbers that drove the design.

## Layout (planned; a folder exists once its README says what is in it)

| Path | What it is |
|---|---|
| `backend/` | Rust. `rust_rules_converter/` (tokenise, fold, node/4, PySpark, lineage), `prolog_rules_converter/` (drives swipl for the proof, in the background), `rust_inferred_duckdb/` (the store and the query API), `testdata_rules/engine/` (Z3 test data from node/4 branches), `api/` (HTTP + Tauri commands). |
| `frontend/` | TypeScript. `ui_across_file_ui/` (files, blocks, tables across a folder; from `node4_viz`), `ui_file_ide/` (one file: SAS ⇄ PySpark cells, table graph, strip; from the Bench), `shared/` (design tokens, URL state, API client). |
| `rules/` | `sas_pack/`, `py_pyspark_pack/`, and `*/test_data_gen/`: pyDSL spec, its JSON, the generated `.pl`, the node/4 schema, interfaces, generators. Only what the engines read. |
| `build_bin/tauri_builder/` | Desktop build: one binary with the backend inside and the two UIs as windows. |
| `docs/` | Obsidian medallion vault. One dimension: `plan/`. Later dimensions: `backend/`, `frontend/`, `rules/`. |
| `tools/` | `wiki_from_git.py` (planned): doc comments, commit messages and git notes → bronze pages. |

## Rules

- Follow the `medallion-wiki-obsidian` skill for any page under `docs/`. Gold is owner-only; agents write `gold_draft_*`.
- The wiki grows from the code: every module carries a doc comment that says why it exists and its inputs → outputs; every commit message says what changed and why; `git notes` carry the receipts (timings, counts). Pages are generated from those, then curated.
- Prolog is the reference, Rust mirrors it (owner rule, exp_42). Here the UI opens with Rust and the Prolog proof runs in the background; the receipt bar says when they agree.
- Copy, do not re-derive: the engine, the rules and the two UIs are copied from the tracks named in `raw_sources_to_copy.md`, then documented and trimmed. Name the source path in the first commit of every copied file.
- Java 17 for Spark runs: `export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home`.
