// exp_42 2026-09-08 — Bench UI timings for a big program. Evaluate this in the page after the program is loaded.
// Every number is the wall time of one synchronous UI action (ms), i.e. what the user waits after a key press.
async () => {
  const R = {};
  const ms = f => { const t = performance.now(); f(); return +(performance.now() - t).toFixed(1); };
  const avg = (k, f) => { const a = []; for (let i = 0; i < k; i++) a.push(ms(f)); a.sort((x, y) => x - y); return { p50: a[k >> 1], max: a[k - 1] }; };
  const frame = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  R.blocks = BLOCKS.length; R.edges = LINEAGE.length;
  R.dom_start = document.getElementsByTagName("*").length;
  // 1. full cell render (what happens on open and on every focus move today)
  R.renderCells_ms = ms(() => renderCells());
  R.dom_cells = document.getElementsByTagName("*").length;
  // 2. moving focus with ↓ / ↑ (each does renderCells + renderRight)
  R.next_ms = avg(10, () => act("next"));
  R.prev_ms = avg(10, () => act("prev"));
  // 3. the graph: open, then click a node (story), then esc
  S.right = null; renderRight();
  R.graph_open_ms = ms(() => panel("graph"));
  R.graph_svg_nodes = document.querySelectorAll("#graph .node").length;
  await frame();
  const node = document.querySelector("#graph .node[data-n]") || document.querySelector("#graph .node");
  R.graph_node_click_ms = node ? ms(() => node.dispatchEvent(new MouseEvent("click", { bubbles: true }))) : null;
  R.story_len = S.story ? S.story.length : (S.sel ? S.sel.blocks.length : null);
  R.esc_ms = ms(() => act("escape"));
  // 4. next with the graph open (both buffers redraw)
  R.next_with_graph_ms = avg(10, () => act("next"));
  // 5. text buffer toggles
  R.hide_text_ms = ms(() => act("view_jupyter"));
  R.show_text_ms = ms(() => act("view_jupyter"));
  // 6. IDE view: build + highlight the whole PySpark file, then move lines
  R.ide_open_ms = ms(() => act("view_ide"));
  R.ide_lines = $("#buf").value.split("\n").length;
  R.ide_move_ms = avg(10, () => ideMove(1));
  R.ide_back_ms = ms(() => act("view_jupyter"));
  // 7. cells dock (lineage tree) and console
  R.cells_dock_ms = ms(() => { S.right = "cells"; renderRight(); });
  R.console_ms = ms(() => { S.right = "console"; renderRight(); });
  S.right = "graph"; renderRight();
  // 8. bottom strip tabs
  S.bottom = true; S.bmin = false;
  R.tab_out_ms = ms(() => { S.tab = "out"; renderBottom(); });
  R.tab_log_ms = ms(() => { S.tab = "log"; renderBottom(); });
  R.tab_dm_ms = ms(() => { S.tab = "dm"; renderBottom(); });
  // 9. scrolling the cells: frame time while jumping through the list
  const c = $("#cells"); const ft = []; for (let i = 0; i < 20; i++) { c.scrollTop = (c.scrollHeight / 20) * i; const t = performance.now(); await frame(); ft.push(performance.now() - t); }
  ft.sort((a, b) => a - b); R.scroll_frame_ms = { p50: +ft[10].toFixed(1), max: +ft[19].toFixed(1) };
  R.heap_mb = performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(0) : null;
  R.dom_end = document.getElementsByTagName("*").length;
  return R;
}
