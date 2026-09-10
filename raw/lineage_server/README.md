# raw/lineage_server — the backend UI1 actually needs

**Why this folder exists.** `raw/node4_viz/` (UI1) cannot run on its own. Every piece of
data it draws comes from `fetch('/api/...')` in `src/api.ts`, and `vite.config.ts` proxies
`/api` to `http://localhost:8000`. That server was never part of any exp_00x track — it
lives in `~/Desktop/sas2py_projects/file_dependencies_regex/`, a different project tree.
Without it UI1 renders its shell and an error banner, and nothing else. So it is copied
here, with its database and corpus, so the UI can be run and screenshotted anywhere,
including in the cloud.

**Inputs → outputs.** SAS files under `inputs/` + the pre-built `output/explorer.duckdb`
→ a FastAPI app on `:8000` → the six routes UI1 calls.

**Status (2026-09-09).** Copied in during phase 0. This is a **stand-in, not the
destination.** Plan phase 2 replaces it with the Rust API (`backend/api/`); this copy
exists so UI1 can be proven working before that API is written, and so the Rust API has a
reference implementation to match route-for-route.

## Provenance

Everything below from `~/Desktop/sas2py_projects/file_dependencies_regex/` on 2026-09-09.

| here | from | size | excluded |
|---|---|---|---|
| `server/` | `server/` | 224K | `__pycache__`, `.pytest_cache` |
| `exp_2/` | `exp_2/` | 2.3M | `__pycache__`, `exp_2/output/` |
| `output/explorer.duckdb` | `output/` | 3.6M | the HTML report dumps, `estate_history/`, the `.wal` |
| `inputs/` | `inputs/` (ankitha_1, 25 SAS files) | 108K | — |

`exp_2/sas_lineage/` is the package `server/app.py` imports as `sas_lineage.store` and
`sas_lineage.ui_export` — hence `PYTHONPATH=../exp_2:.`.

## How to run it

```
cd raw/lineage_server/server
pip install -r requirements.txt          # fastapi, uvicorn, pyarrow, dulwich
SAS_ROOTS=../inputs SAS_DB=../output/explorer.duckdb PYTHONPATH=../exp_2:. python app.py
```

Then, in `raw/node4_viz/`: `npm install && npm run dev` → `http://localhost:5174/`.

The DB is pre-built, so the server does not need to re-index the corpus to answer.

## The routes UI1 calls

All present in `server/app.py`, verified 2026-09-09:

| route | line | used by |
|---|---|---|
| `GET /api/files` | 117 | the explorer tree |
| `GET /api/search?q=` | 124 | the search typeahead |
| `GET /api/neighborhood?file=&up=&down=` | 128 | **the graph itself** |
| `GET /api/blocklinks?files=` | 138 | block-level edges |
| `GET /api/file/{fileid:path}` | 171 | the code pane, on expand |
| `GET /api/edges?files=&filter=&level=&offset=&limit=` | 193 | the edges drawer |

`app.py` exposes ten more routes (status, history, save, order, excel, arrow, edits, sync)
that UI1 does not call. The Rust API in phase 2 only needs the six above.

## Decisions
- **PROVEN ∎** — the six routes were located in `server/app.py` by line number on
  2026-09-09; the proxy target is `vite.config.ts:11`; the original start command is
  quoted in `raw/node4_viz/src/useLineageGraph.ts:15`.
- **ASSUMED** — that the checked-in `explorer.duckdb` is current enough to reproduce the
  owner's reference screenshot. Not yet verified by running it.
- **PROVEN ∎** — the `.wal` is not needed alongside the `.duckdb`. Opened a copy of
  `explorer.duckdb` on its own, read-only, with the `.wal` withheld (2026-09-10): all 11
  tables present and populated — 25 files, 26 blocks, 42 lineage rows, 375 events — and no
  `.wal` was regenerated. It is now untracked (`*.duckdb.wal` in `.gitignore`); DuckDB
  recreates it locally whenever the server writes, and it no longer churns every diff.
