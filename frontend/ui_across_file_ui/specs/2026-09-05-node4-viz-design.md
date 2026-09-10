# node4_viz — React Flow file/block lineage canvas for exp_003

Date: 2026-09-05. Owner decisions taken in the brainstorming session are marked **DECIDED**.

## 1. Why

The owner wants the graph shown at
`http://localhost:5173/?file=ankitha_1%2F04_build_accounts.sas&up=1&down=1`
(the SAS Table-Lineage Explorer in `sas2py_projects/file_dependencies_regex/web`)
redrawn in **React Flow** inside `exp_003_lineageq_slides`, as the node/4 visualiser,
with the nested look of the Python block graph in
`lineageQ_aug_experiments/docs1/Lineage Q Exp Season 3.md` (image `Pasted image 20260902230319.png`):
a file opens in place into a container of blocks and tables, and cross-file edges re-point
to the table inside.

The 5173 app draws with cytoscape + ELK. The exp_004 UI spec fixes React Flow + ELK layered
as the product canvas and the node/4 block id as the one id. This app is the first React Flow
build of that canvas on real lineage data.

## 2. Decisions

- **DECIDED** Data comes live from the FastAPI server on `:8000` (same ankitha_1 corpus). No snapshot.
- **DECIDED** Graph shape: files, each expandable in place to blocks and the tables they read/write.
- **DECIDED** Page scope: canvas + toolbar only. No explorer tree, code pane or edges grid.
- **DECIDED** Approach: React Flow + elkjs, ELK also routes the edges; a custom edge draws ELK's sections.
- Location: `exp_003_lineageq_slides/node4_viz/`. Dev port **5174**. Vite proxies `/api` → `http://localhost:8000`.
- Wiki: after the build, one bronze run page under `exp_003_lineageq_slides/docs/capabilities/bronze/`.
  This spec lives outside `docs/` on purpose (the medallion rule applies only under `docs/`).

## 3. Reused code (copied, not linked)

From `/Users/mutyala/Desktop/sas2py_projects/file_dependencies_regex/web/src/`:

| Source | Copied as | Change |
|---|---|---|
| `api.ts` (types `NodeOut`, `EdgeOut`, `Neighborhood`, `FileDetail`, `BlockInfo`, `Occurrence`, `MacroCallOut`, `BlockLink`) | `src/api.ts` | keep types; keep only three fetchers: neighborhood, blocklinks, file detail |
| `graph2.ts` + `graph2.test.ts` + `components/__fixtures__/graph2Data.ts` | `src/graph2.ts`, `src/graph2.test.ts`, `src/__fixtures__/graph2Data.ts` | verbatim |
| `edgeLabels.ts` — `computeEdgeLabelPlacements` and its types only | `src/edgeLabels.ts` | drop the cytoscape `applySmartEdgeLabels` / `clearSmartEdgeLabels` half; unit tests for the pure part come along |

Colours and legend follow the 5173 canvas: focus blue `#4f93c9` with dark ring, upstream tan, downstream green,
run order shown as `#N` under the file name.

## 4. Architecture

```
URL (?file|table, up, down)
  → fetchNeighborhood → fetchBlockLinks(all hood files)
  → on "+": fetchFileDetail(fileid) → details cache
  → graph2Elements(hood, expanded, details, links)          (pure, copied)
  → elkLayout(elements)                                     (pure adapter, async)
  → toFlow(layout)                                          (pure mapper)
  → <ReactFlow nodes edges nodeTypes edgeTypes/>
```

### 4.1 `src/elkLayout.ts`
Input: `Graph2Element[]`. Output:

```ts
interface LaidOut {
  nodes: Array<{ id: string; kind: Graph2Kind; label: string; parent?: string;
                 x: number; y: number; width: number; height: number;   // absolute
                 fileid?: string; blockId?: string; cyclic?: boolean }>
  edges: Array<{ id: string; source: string; target: string; label?: string; fact?: boolean;
                 points: Array<{ x: number; y: number }> }>              // absolute polyline
}
```

ELK options (same family as the 5173 `GRAPH2_LAYOUT`): `algorithm=layered`, `elk.direction=RIGHT`,
`elk.edgeRouting=ORTHOGONAL`, `elk.hierarchyHandling=INCLUDE_CHILDREN`,
`nodeNodeBetweenLayers=90`, `nodeNode=26`, `componentComponent=40`,
`elk.padding=[top=36,left=18,bottom=18,right=18]` on containers (room for the title and the ± button).

Node sizes are estimated from label length (file: `max(140, 7*len+40)` × 44; occurrence: `7*len+24` × 26;
containers are sized by ELK from their children). ELK returns positions relative to the parent; the adapter
converts to absolute by walking the tree, and edge sections likewise (ELK gives section points relative to
the edge's containing node).

### 4.2 `src/toFlow.ts`
Maps `LaidOut` to React Flow. Nested nodes get `parentId` and `position` = absolute minus parent absolute,
`extent: 'parent'` is **not** set (dragging a child out is allowed and harmless until re-layout).
Containers get `style: { width, height }` and are rendered before their children (React Flow requires
parents earlier in the array). Edge `type: 'elk'`, `data: { points, label, fact }`,
`markerEnd: arrowclosed`.

Node types by kind: `file` → `FileNode`; `fileCluster`, `macro`, `blockCluster` → `GroupNode`;
`occurrence` → `OccurrenceNode`.

### 4.3 Components (`src/components/`)
- `FileNode` — name, `#score`, role colour from `hood.nodes[].role`; a `+` button top-right; a red dot if `cyclic`.
- `GroupNode` — title strip (file name, `%macro #n`, or `kind · block id`), light fill, dashed border for `macro`,
  `−` button top-right on `fileCluster` only (blocks and macros collapse with their file).
- `OccurrenceNode` — monospace pill with the table name; border green for write, orange for read
  (role from `FileDetail.blocks[].occurrences[].role`).
- `ElkEdge` — `<path>` through `data.points` with 8 px rounded corners; solid 1.5 px purple `#8f7fd0` for fact
  edges, dashed grey for file (inferred) edges; arrowhead at the end. Label uses
  `computeEdgeLabelPlacements` over all edges once per layout (in `App`), result passed down as
  `data.labelAt: {x,y}`; rendered with `EdgeLabelRenderer`.
- `Toolbar` — search input (calls `/api/search`, picks table or file), `up`/`down` steppers (0–3),
  expand all, collapse all, fit, re-layout, legend (focus / upstream / downstream / `#N = run order` /
  fact edge / inferred edge).
- `Banner` — server unreachable / empty result messages.

### 4.4 `src/App.tsx`
State: `params {file?, table?, up, down}` (from URL, written back with `history.replaceState`),
`hood`, `links`, `expanded: Set<string>`, `details: Map`, `laidOut`, `status: 'idle'|'loading'|'error'`.
Effects: params → fetch hood+links; (hood, expanded, details, links) → elements → layout.
Clicking a file node (not the ±) sets it as the seed. Node drags are kept in React Flow state until
re-layout or the next expand/collapse.

## 5. Error handling
- Any fetch fails → `Banner` with: `cd server && SAS_ROOTS=../inputs SAS_DB=../output/explorer.duckdb PYTHONPATH=../exp_2:. ../.venv/bin/python app.py`.
- Empty hood → hint "search a table or file to see its neighborhood".
- ELK throws → fallback layout: files in a row 200 px apart, no nesting, straight two-point edges; error logged with `console.error`.
- A file whose detail 404s stays collapsed and shows a `!` badge; no crash.

## 6. Testing
Vitest (jsdom):
- `graph2.test.ts` — copied, must pass unchanged.
- `edgeLabels.test.ts` — no two placed boxes overlap for the ankitha fixture.
- `elkLayout.test.ts` — runs real elkjs on the fixture: every child's box lies within its parent's box;
  every edge has ≥ 2 points; ids preserved.
- `toFlow.test.ts` — parents precede children; child positions are relative; edge data carries points.
- `App.test.tsx` — with a mocked fetch: renders 11 file nodes for the ankitha fixture; banner on fetch error.

Playwright smoke (manual script `scripts/smoke.mjs`, dev server + `:8000` required):
open `http://localhost:5174/?file=ankitha_1%2F04_build_accounts.sas&up=1&down=1`, expect 11 `.rf-file` nodes;
click `+` on the seed, expect ≥ 2 `.rf-group.kind-blockCluster`; click `−`, expect 11 files again.

## 7. Done means
- `npm run dev` on 5174 shows the ankitha graph from the URL above with the 5173 colours and run-order numbers.
- `+` on any file nests its blocks and tables in place; cross-file edges land on the inner table pill.
- Edges are orthogonal with rounded corners and non-overlapping labels.
- `npx vitest run` green; smoke script passes.
- Bronze run page written under `docs/capabilities/bronze/` with inputs → outputs and the numbers seen.

## 8. Out of scope
Explorer tree, code pane, edges grid, editing, Excel export, column-level edges, presets, uiDSL wire format.
