# node4_viz — React Flow lineage canvas (exp_003)

Redraws the `:5173` SAS Table-Lineage Explorer file graph in React Flow, with files that
expand in place into blocks and tables and ELK-routed orthogonal edges.

## Run

    # 1. API (from sas2py_projects/file_dependencies_regex)
    cd server && SAS_ROOTS=../inputs SAS_DB=../output/explorer.duckdb PYTHONPATH=../exp_2:. ../.venv/bin/python app.py
    # 2. this app
    npm install && npm run dev      # http://localhost:5174

Deep link: `http://localhost:5174/?file=ankitha_1%2F04_build_accounts.sas&up=1&down=1`

`VITE_PROXY` points `/api` at a different API base (default `http://localhost:8000`) — set it
before `npm run dev` if the SAS Table-Lineage Explorer API is running elsewhere.

## Test

    npx vitest run     # pure pipeline + components
    npm run smoke      # playwright, needs dev server + API; writes two screenshots into ../plots/

## Layout of the code

URL → `api.ts` → `graph2.ts` (copied from the 5173 app, verbatim) → `elkLayout.ts` → `toFlow.ts` → React Flow.
`edgeLabels.ts` (copied, pure half) places labels without overlap. Spec: `specs/`, plan: `plans/`.

## The shell (added 2026-09-07)

One VS Code-style window: explorer (current set + all files) | canvas | a resizable bottom
panel with the SAS code (block-id chips) and a read-only edges drawer. Search is a typeahead
over `/api/search`; **Pin** stops file clicks from re-centering the graph. Nodes drag freely:
a moved node's edges follow it as smooth-step lines until the next re-layout, and a block or table
stays inside its file container. `+`/`−` on a file expands it into blocks; `−`/`+` on a block folds its
tables into one box and unfolds them again.

## Interaction

- **Single click** a node: selects it — the code pane and edges drawer follow, nothing moves.
- **Double click** a node: re-seeds the graph on it. Files already on screen stay, new ones join, and
  (with *Animate layout changes* on) everything glides to its new place with a d3 tween
  (`src/animateLayout.ts`, d3-interpolate / d3-ease / d3-timer driving React Flow's `setNodes`).
- **Explorer**: All Files above, Current below, split at the golden ratio; each list scrolls on its own.
- **Edges focus**: a single click on a file, block or table narrows the edges drawer to flows touching it —
  inflow tinted tan, outflow green, flows inside it blue. Click the canvas background or the × chip to clear.
- **Edge row click**: clicking a row in the edges drawer highlights that edge on the canvas (thick blue), rings
  its block, expands the file if needed and zooms to the block. A file → file row also matches an edge that
  lands on a table pill inside the destination file. If the flow is not drawn at all, a dashed blue **ghost
  edge** appears between the two ends; an end that is off-canvas gets a translucent ghost node beside the
  other end. Click the canvas background to clear.
- **Code pane sections** (`src/codeSections.ts`, `src/components/CodePane.tsx`): a rail beside the code lists
  every parsed block as `#n kind → tables it writes / ← tables it reads / L10–24`. The filter box narrows the
  rail to the sections whose kind, tables or code contain every typed word (⌘⇧F focuses it); with *only
  matching* on, the code outside those sections folds into `⋯ N lines hidden` rows that open on click, and
  the matching words are marked in the code. Enter / ⇧Enter (or ↑ ↓) step through the matching sections.
  Picking a section highlights its lines, scrolls to it, rings its block on the canvas (expanding the file if
  needed), zooms to it and narrows the edges drawer to that block.
- **Sort by file name** (on by default) pins files in file-name order via ELK model order, so `+`/`−`
  never shuffles them; neighbours move aside instead.

## Layout settings (⚙ Layout in the command bar)

Pick a profile first; the toggles below it show what the profile set, and changing one by hand turns the profile into **Custom**.

| Profile | What it is |
|---|---|
| Simple | plain ELK, thoroughness 7, every edge on its own line; fastest |
| Medium | merged trunks, straight runs, side ports, thoroughness 19 (the default; the owner's pick) |
| Best | Medium with thoroughness 30; slower on big graphs |

The other four toggles (ELK labels, keep arrangement, run order, libavoid) live under **Advanced**; the
owner judged them not helpful on the ankitha corpus (2026-09-07), so no profile turns them on.


| Tier | Toggle | What it does |
|---|---|---|
| 1 | Merge fan-out edges | ELK `mergeEdges` + `mergeHierarchyEdges`: one trunk per table, split near the targets |
| 1 | Straighten edges | `unnecessaryBendpoints`, `favorStraightEdges`, wider edge spacing |
| 1 | Side ports | `FIXED_SIDE` ports: edges leave on the right, enter on the left |
| 1 | ELK places labels | ELK reserves room for edge labels instead of the post-pass placer |
| 1 | Thoroughness | `elk.layered.thoroughness` (ELK default 7) |
| 2 | Keep my arrangement | semi-interactive re-layout: `cycleBreaking`/`layering` INTERACTIVE + `semiInteractive` crossing minimisation, fed the positions you dragged to |
| 3 | Follow run order | `considerModelOrder` with files ordered by run order, blocks in source order |
| 4 | Obstacle-avoiding edges | libavoid (Adaptagrams) via `@mr_mint/elkjs-libavoid` WASM routes every edge around every leaf box after ELK; re-routes on drag stop |
| 5 | HOLA placement (pyhola) | HOLA (libdialect) places the top-level file boxes and routes the box-to-box edges; ELK keeps laying out the inside of each box and the app stitches HOLA's routes to the pills. Needs `scripts/hola_server` (Python sidecar on :8765, proxied as `/hola`) |

Settings persist in `localStorage` under `node4_viz.layout`. The WASM lives in `public/libavoid.wasm`
(copied from `node_modules/@mr_mint/elkjs-libavoid/dist/`; LGPL-2.1 for libavoid itself).

Tier 5, HOLA / libdialect ("human-like" orthogonal layout): no Rust or WASM port exists as of
2026-09-07, so it runs as a Python sidecar (`scripts/hola_server/README.md`; the throwaway
comparison that preceded it is `scripts/hola_compare/`). HOLA ignores left-to-right flow and
cannot nest, hence the hybrid: HOLA for the file boxes, ELK inside them. libdialect aborts on
some graph shapes (a bare triangle, an isolated node); the sidecar runs each connected component
in a subprocess and lays a component that crashed out in a row, with a banner saying so.

Advanced also holds a **Placement** group: ELK layering strategy, node placement strategy, greedy
crossing switch, node promotion and post-compaction.

## Known limits

- Cross-file edges are always drawn solid, regardless of provenance; only intra-file inferred
  edges are drawn dashed.
- Dragging a node leaves its edges on the old ELK route until the next re-layout.
- A file whose blocks fail to load stays collapsed, and a banner reports which fileids failed.

## 2026-09-09 — no-backend mode (`?mock=1`)

Add `&mock=1` to any URL and every `/api` call is answered from
`src/__fixtures__/team_finance/` — a snapshot of `:8000`'s answers for the team_finance corpus
(25 files × up/down 0..3 neighbourhoods, 25 file details, all block links, all 83 edge rows;
2.4 MB). `src/mockApi.ts` looks up neighbourhood and file detail, and filters block links, edges
and search in memory the way the server does. `src/mockApi.test.ts` proves the filters.
`mock` survives every URL rewrite (`urlParams.ts`). Neighbourhood by `?table=` is not snapshotted.

Why: the design rounds on the UI (edge labels, column grain, hops) need the page to work with
nothing running but Vite. Proof: `VITE_PROXY=http://localhost:1 npx vite --port 5181` (dead
proxy) draws `?file=sas/raw/14_large_txn_report.sas&up=1&down=3&mock=1` in full.
Re-snapshot: the loop in this commit's message (curl over `/api/files` ids).
