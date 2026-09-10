# frontend/ui_across_file_ui — the across-files window

**Why this folder exists.** This is UI1: the explorer tree, the React Flow + ELK canvas of
files (expandable into blocks and table pills), the code pane and the edges drawer. It is
`raw/node4_viz` extracted (Task 8, 2026-09-10) — copied, not re-derived, per the track's
own rule — now that every question it asks is answered by the Rust API on `:8110` instead
of the Python server on `:8000`.

**Source path.** `raw/node4_viz/` (the exp_003 `node4_viz` track, listed in
`docs/plan/raw/raw_sources_to_copy.md`), minus `node_modules/`, `dist/` and
`scripts/hola_compare/` — the HOLA comparison harness, which no exp_005 pass mark uses.
`raw/node4_viz` is left in place: it is the copied-in source of record, and `raw/` is only
edited where a brief names the line.

**Inputs → outputs.** `GET /api/files`, `/api/search`, `/api/neighborhood`,
`/api/blocklinks`, `/api/edges` (all landed in Rust, Tasks 5–7) and `/api/file/<fileid>`
(**still forwarded** to `:8000` until Task 9 lands `file()`) → the canvas, the drawer and
the code pane.

## Running it

```bash
cd backend && cargo build --release && cd ..
backend/target/release/lineageq_api --db backend/lineageq.duckdb --port 8110 &
cd frontend/ui_across_file_ui && npx vite --port 5199   # 5173-5175 are taken on this laptop
```

`vite.config.ts` proxies `/api` to `:8110` (override with `VITE_PROXY`). `?mock=1` answers
from `src/__fixtures__/` with no server at all.

`node_modules` is not committed and not vendored here: this folder's dev tools resolve
through a symlink to `raw/node4_viz/node_modules` (`npm install` here would work too, and
would replace the symlink with a real tree).

| command | what it does |
|---|---|
| `npx vitest run` | the unit suite — **174 passed** (2026-09-10). They stub `fetch`, so they pass with no backend at all; that is the point, they prove the extraction did not break the app. |
| `node scripts/smoke.mjs` | headless smoke against a running dev server. `SMOKE_URL`, `SMOKE_FILES` (default 11) and `SMOKE_OUT` (default `../plots`) are parameters as of Task 8; they used to be hard-coded. |
| `BASE=http://localhost:5199 OUT=docs/plan/bronze/evidence_<date> node ../../tools/shot_ui1.mjs` | the three pass-mark screenshots, run from the repo root. |

## Pass marks (Task 8, measured 2026-09-10 with `:8000` stopped)

| deep link | files | edges | edges drawer | HUMAN_GOLD rows |
|---|---|---|---|---|
| `?file=sas%2Fraw%2F11_branch_rollup.sas&up=1&down=1` | **6** | **7** | 23 / 23 | 1 |
| `?file=sas%2Fraw%2F07_enrich_fx.sas&up=1&down=1` | **4** | **3** | 7 / 7 | 1 |
| `?file=sas%2Fraw%2F18_dashboard_mart.sas&up=1&down=1` | 7 | 6 | **25 / 25** | 1 |

The drawer's 23 where the 2026-09-09 Python baseline said 24 is the one `FILE_FLOW`-shaped
row this store states as two block rows instead — traced in the ledger's Task 7 note
(cause B2), not a lost flow.

## What still needs Python

Nothing on the canvas. The **code pane** does: it calls `/api/file/<fileid>`, which the
Ruling 5 fallback forwards to `:8000`, so with Python stopped the banner reads
`could not load blocks for <fileid>` and the console carries one 502 per open file. Task 9
(milestone M2) lands `file()` and that goes away. It is the only request in the window that
still leaves the store.
