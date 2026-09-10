# frontend/ui_file_ide/mockups — static screens before code

**Why this folder exists.** The owner wants to see how the old g6 `lineage_ux/code_view` pages
(copied to `raw/B_tripane.html`, `raw/blocks_view.html`) fold into UI2 before any TypeScript is
written. Each mock is one self-contained HTML file in the Bench's frame and tokens, no backend,
no G6. Press `n` in a mock for the numbered notes (what came from where, what was dropped), `t`
for dark.

**Inputs → outputs.** `raw/B_tripane.html`, `raw/blocks_view.html`, `raw/bench_stack/server/bench.html`
(frame), `corpus/team_finance/sas/raw/*.sas` (real content) → one mock each, plus a screenshot.

| file | shows | status |
|---|---|---|
| `ui2_column_lineage_mock.html` (+ `.png`, `_tables.png`, `_notes.png`) | html1, the safe bet: Bench frame, column-grain lineage in the drawer, labels on every traced link (carried / renamed / computed / join key), `k` flips to Tables grain and the focused column rides along as a chip, flow strip, linkable code tokens with lines into both cells, `Column` tab on the strip | 2026-09-09, for review |
| `ui2_task_flow_mapping_mock.html` (+ `.png`) | html2: same frame as html1; clicking CODE FLOW flips the Lineage drawer to Flow — IDMC-style task flow (one task per block) on top, the selected task's mapping (SRC → JNR → EXP → TGT with ports) below. `04_build_accounts.sas`, the only 2-block file | 2026-09-09, for review (replaces the dropped blocks_view hybrid) |
| `ui2_ui1_bet_mock.html` (+ `.png`) | html3, the UI1 bet: the canvas is the centre, drawn UI1's way (file ▸ block ▸ table groups, +/− per node, edge labels), hops ◀ ▶ grow into neighbour files on the same canvas, code is UI1's right pane with a PySpark tab, Edges drawer on the strip. Notes card has the safe-vs-bet table | 2026-09-09, for review |

**Next (owner's brief, 2026-09-09).** After review of html1 + html2 and the owner's comments:
html3 = across-files + in-file designs together, in a new `../exp_007_static_ui12_ide/`; these
files move there. Only useful features, not many.

View locally: `python3 -m http.server 8711` in this folder (Playwright blocks `file://`).
