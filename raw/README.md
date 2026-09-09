# raw — Untouched Source Copies

**Why this folder exists.** The plan copies, it does not rewrite (`CLAUDE.md`: "Copy, do
not re-derive"). These are the source trees as they stood on the laptop on 2026-09-08/09,
unmodified, so every later extraction into `backend/`, `frontend/` and `rules/` can be
diffed against its origin. Nothing here is edited in place; it is read from and extracted
out of. It is also what makes cloud work possible at all — none of this was in any git
repo before, so no agent off this laptop could see it.

**Inputs → outputs.** three source tracks on `~/Desktop/` → this folder → (later)
`backend/rust_rules_converter/`, `backend/prolog_rules_converter/`,
`frontend/ui_across_file_ui/`, `frontend/ui_file_ide/`, `rules/*`.

**Status (2026-09-09).** Copied in during phase 0. Extraction is phases 1–3.

## Layout — three self-contained stacks

`raw/` is not a flat dump. The Bench's code resolves everything from
`ROOT = Path(__file__).resolve().parent.parent` and expects `server/`, `pipeline/`,
`codegen/`, `rust_engine/`, `out/`, `loops/`, `corpus/`, `testdata/` to be **siblings** —
so the copy mirrors that layout exactly, or nothing resolves.

| stack | what it is | how it runs |
|---|---|---|
| `bench_stack/` | UI2 plus the whole engine, laid out as exp_42's ROOT | `python3 server/convert_api.py --port 8042` → `/bench` |
| `lineage_server/` | UI1's backend, FastAPI + DuckDB — see its own README | `:8000` |
| `node4_viz/` | UI1 itself, Vite + React Flow | `npm run dev` → `:5174` |
| `corpus_ankitha_1/` | the 25-file SAS corpus in the owner's UI1 screenshot | data |

## Provenance

All copied 2026-09-08/09 with `rsync -a`. Paths relative to `~/Desktop/lineageQ/` unless
stated.

| here | from | excluded |
|---|---|---|
| `node4_viz/` | `lineageQ_sep_experiments/exp_003_lineageq_slides/node4_viz/` | `node_modules` 141M, `dist/`, `scripts/hola_server` 44M |
| `bench_stack/server/` | `lineageQ_aug_experiments/exp_42_test_vishnu/server/` | `__pycache__` |
| `bench_stack/{pipeline,codegen,testdata,corpus,loops,raw}/`, `out/spec/`, `run_all.sh` | same track, same names | `__pycache__` |
| `bench_stack/rust_engine/` | same track | `target/` 68M |
| `corpus_ankitha_1/` | `lineageQ_aug_experiments/exp_014b_vertical_slice_sas_lineage/corpus/ankitha_1/` | — |
| `lineage_server/` | `~/Desktop/sas2py_projects/file_dependencies_regex/` | see `lineage_server/README.md` |

`node4_viz/README_from_node4_viz.md` is that repo's own README, renamed so it does not
collide with this track's folder READMEs.

**Deliberately not copied**, both rebuildable, 1.2 GB together:

- `rust_engine/target/` → `cargo build --release` produces `target/release/lineageq_sas`,
  the path `server/bench_api.py:40` hardcodes.
- the `.venv/` the servers expect at `ROOT/.venv/bin/python`
  (`server/bench_api.py:39`).

## What still has to be installed to run any of this

| need | why | where it is asserted |
|---|---|---|
| `swipl` | **not optional** — `pipeline/run_fold.py` is the only writer of `<stem>.node4.json`, and the Bench cannot list blocks without it | `pipeline/run_fold.py:289` |
| `cargo` | build `lineageq_sas` | `rust_engine/Cargo.toml` |
| Python venv | `fastapi uvicorn pyarrow dulwich` for UI1; `z3-solver`, `pyspark`, `requests`, `websocket-client` for the Bench | the two `requirements.txt` |
| JDK 17 | Spark runs in-process, no `spark-submit` | `server/bench_api.py:41`, override with `JAVA_HOME_17` |
| Node 18+ | UI1 only; `datamatch.js` is checked in compiled | `node4_viz/package.json` |

## Two corrections to the plan

1. **The ankitha_1 corpus is not in `exp_003_lineageq_slides`.** `docs/plan/raw/raw_sources_to_copy.md`
   says it is. It lives in `exp_014b_vertical_slice_sas_lineage/corpus/ankitha_1/` —
   verified by locating `18_dashboard_mart.sas`, the file in the owner's screenshot.
2. **`file_dependencies_regex` is not "ideas only".** The same page lists it as a pattern
   to read for the DuckDB store, "the code is Python". It is in fact a hard runtime
   dependency of UI1: without its FastAPI server on `:8000`, UI1 draws nothing. Hence
   `lineage_server/`.

## 2026-09-09 — the old corpora are gone; `bench_stack/run_all.sh` has nothing to run

Task 5 (team-finance-corpus) deletes every competing corpus so the two UIs cannot drift
apart again: `lineage_server/inputs/ankitha_1/`, `bench_stack/corpus/parts/`,
`bench_stack/testdata/`, and `bench_stack/corpus/sas/test_vishnu*.sas` — which was the
whole contents of `bench_stack/corpus/sas/`, so that folder is now empty. `bench_api.py`'s
`SAS_DIRS` is re-pointed at `corpus/team_finance/sas/raw` (the shared corpus, see
`corpus/README.md`), so the Bench oracle keeps serving files. `run_all.sh` was never
re-pointed — that is out of scope for Task 5 — so it still reads `corpus/sas/*.sas`
(lines 15, 24, 30) and `corpus/sas/test_vishnu_testdata.sas` (line 46), all now missing.
Running it will fail on step 1. It is retained as **reference only**: read it to see the
loop's shape (tokenise → fold → Rust → PySpark → DataMatch), do not run it. `explorer.duckdb`
(+ `.wal`) was NOT deleted, against the original task brief — it was rebuilt in place
instead (`server/scripts/sync_store.py` against `SAS_ROOTS=corpus/team_finance`) so its
fileids read `sas/raw/<name>.sas`, matching the Rust API, rather than going blind.

`tools/diff_route.py`'s `ankitha_files()` (lines 292-293) globs
`raw/lineage_server/inputs/ankitha_1/` for its `--corpus ankitha` mode; that directory is
also deleted, and `Path.glob` on a missing directory returns empty rather than raising, so
that mode now silently degrades to 0 files instead of failing loudly. Not fixed (out of
scope, same as `run_all.sh` above) — recorded here so it isn't a surprise later.

## Decisions

- **PROVEN ∎** — every source path above was copied on 2026-09-08/09; the sibling-layout
  requirement is `server/bench_api.py:35` (`ROOT = Path(__file__).resolve().parent.parent`);
  the sixteen files the Bench stack needs were checked present after the restructure.
- **OPEN** — whether `node4_viz/scripts/hola_server/` (44M, absent) is ever needed. The
  HOLA layout tier is off by default, so it only bites if that toggle is turned on.
