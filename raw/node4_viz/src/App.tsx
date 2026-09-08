// The one workbench window: explorer | canvas over a code + edges panel.
// Same URL contract as the 5173 explorer (?file|table&up&down&block=).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Background, Controls, ReactFlow, ReactFlowProvider, useNodesState, useEdgesState, useReactFlow, useUpdateNodeInternals } from '@xyflow/react'
import type { Edge, Node, NodeMouseHandler, OnNodeDrag } from '@xyflow/react'
import SettingsPanel from './components/SettingsPanel'
import { loadSettings, saveSettings, type LayoutSettings } from './layoutSettings'
import type { Point } from './elkLayout'
import { keepMeasured, tweenNodes } from './animateLayout'
import { applyHighlight, ghostForRow, matchingEdgeIds, withoutGhosts } from './edgeHighlight'
import type { EdgeRow } from './api'
import Toolbar from './components/Toolbar'
import Banner from './components/Banner'
import SearchBar from './components/SearchBar'
import ExplorerTree, { type TreeFile } from './components/ExplorerTree'
import CodePane from './components/CodePane'
import EdgesPanel, { type EdgeFocus } from './components/EdgesPanel'
import Sash from './components/Sash'
import { edgeTypes, nodeTypes } from './components/nodeTypes'
import { readParams, writeParams, type Params } from './urlParams'
import { HOLA_CMD } from './holaLayout'
import { START_CMD, useLineageGraph } from './useLineageGraph'
import { fetchFiles, type SearchHit } from './api'
import type { FlowEdgeData, FlowNodeData } from './toFlow'

const DEFAULT_EXPLORER_WIDTH = 260
const MIN_EXPLORER_WIDTH = 160
const MAX_EXPLORER_WIDTH = 560
const MIN_PANEL_HEIGHT = 120
const MAX_PANEL_HEIGHT = 720
const MIN_SPLIT_PCT = 20
const MAX_SPLIT_PCT = 80

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/** Highlight the edges a drawer row stands for; if none is drawn, add a dashed ghost edge (and ghost node). */
function decorate(nodes: Node<FlowNodeData>[], edges: Edge<FlowEdgeData>[], row: EdgeRow | null): { nodes: Node<FlowNodeData>[]; edges: Edge<FlowEdgeData>[] } {
  const cleanNodes = withoutGhosts(nodes)
  const cleanEdges = withoutGhosts(edges)
  if (!row) return { nodes: cleanNodes, edges: applyHighlight(cleanEdges, new Set()) }
  const hits = matchingEdgeIds(cleanNodes, cleanEdges, row)
  if (hits.size > 0) return { nodes: cleanNodes, edges: applyHighlight(cleanEdges, hits) }
  const ghost = ghostForRow(cleanNodes, row)
  if (!ghost) return { nodes: cleanNodes, edges: applyHighlight(cleanEdges, new Set()) }
  return { nodes: [...cleanNodes, ...ghost.nodes], edges: [...applyHighlight(cleanEdges, new Set()), ghost.edge] }
}
const defaultPanelHeight = () => Math.round((typeof window !== 'undefined' ? window.innerHeight : 800) * 0.38)

function Workbench({ params, setParams }: { params: Params; setParams: (p: Params) => void }) {
  const [selectedFile, setSelectedFile] = useState<string | null>(params.file ?? null)
  const [highlightBlock, setHighlightBlock] = useState<string | null>(params.block ?? null)
  const [pinned, setPinned] = useState(false)
  const [focus, setFocus] = useState<EdgeFocus | null>(null)
  /** the drawer row last clicked: its canvas edge is drawn thick and the view zooms to its block */
  const [pickedRow, setPickedRow] = useState<EdgeRow | null>(null)
  const zoomTarget = useRef<string | null>(null)
  const pickedRowRef = useRef<EdgeRow | null>(null)
  pickedRowRef.current = pickedRow
  const [allFiles, setAllFiles] = useState<TreeFile[]>([])
  const [explorerFilter, setExplorerFilter] = useState('')
  const [explorerWidth, setExplorerWidth] = useState(DEFAULT_EXPLORER_WIDTH)
  const [panelHeight, setPanelHeight] = useState(defaultPanelHeight)
  const [panelSplit, setPanelSplit] = useState(50)
  const codeViewRef = useRef<HTMLPreElement | null>(null)
  const [settings, setSettingsState] = useState<LayoutSettings>(() => loadSettings())
  const setSettings = useCallback((next: LayoutSettings) => { setSettingsState(next); saveSettings(next) }, [])

  const rf = useReactFlow()
  const updateNodeInternals = useUpdateNodeInternals()
  /** absolute positions of every node as React Flow has them now (children are stored parent-relative) */
  const getPositions = useCallback((): Map<string, Point> => {
    const nodes = rf.getNodes()
    const byId = new Map(nodes.map((n) => [n.id, n]))
    const abs = new Map<string, Point>()
    const resolve = (id: string): Point => {
      const cached = abs.get(id)
      if (cached) return cached
      const n = byId.get(id)!
      const p = n.parentId ? resolve(n.parentId) : { x: 0, y: 0 }
      const a = { x: p.x + n.position.x, y: p.y + n.position.y }
      abs.set(id, a)
      return a
    }
    for (const n of nodes) resolve(n.id)
    return abs
  }, [rf])

  const g = useLineageGraph(params, selectedFile, { settings, getPositions })

  // debugging hook: the live React Flow state, readable from the console as window.__node4
  useEffect(() => {
    ;(window as unknown as { __node4?: unknown }).__node4 = { nodes: () => rf.getNodes(), edges: () => rf.getEdges() }
  }, [rf])
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<FlowNodeData>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge<FlowEdgeData>>([])

  // every indexed file, for the explorer's ALL FILES layer
  useEffect(() => {
    let cancelled = false
    fetchFiles()
      .then((files) => !cancelled && setAllFiles(files))
      .catch(() => !cancelled && setAllFiles([]))
    return () => { cancelled = true }
  }, [])

  // a new seed becomes the selected file unless the shell is pinned
  useEffect(() => {
    if (params.file && !pinned) setSelectedFile(params.file)
  }, [params.file, pinned])

  // fresh layout -> fresh node/edge state (this is also what discards drags).
  // With `animate` on, nodes that already exist glide to their new spot; edges
  // are set at once and ElkEdge draws them smooth-step until the glide ends.
  const tweenStop = useRef<() => void>(() => {})
  const highlightIdRef = useRef<string | null>(null)
  /** the node ring for the highlighted block, applied on every tween frame so the glide never drops it */
  const withRing = useCallback((ns: Node<FlowNodeData>[]) => {
    const id = highlightIdRef.current
    return ns.map((n) => { const want = n.id === id ? 'rf-highlight' : undefined; return n.className === want ? n : { ...n, className: want } })
  }, [])
  // the highlighted block's group gets a ring on the canvas
  const highlightId = selectedFile && highlightBlock ? `${selectedFile}::${highlightBlock}` : null
  highlightIdRef.current = highlightId
  useEffect(() => {
    setNodes((prev) => withRing(prev))
  }, [highlightId, setNodes, withRing])

  useEffect(() => {
    tweenStop.current()
    if (!g.flow) { setNodes([]); setEdges([]); return }
    const row = pickedRowRef.current
    const { nodes: target, edges: decorated } = decorate(g.flow.nodes, g.flow.edges, row)
    setEdges(decorated)
    const prev = rf.getNodes() as Node<FlowNodeData>[]
    // a hidden tab freezes rAF-driven transitions (React Flow's fitView uses d3-zoom): animate only when visible
    const visible = typeof document === 'undefined' || document.visibilityState !== 'hidden'
    const dur = settings.animate && visible ? 450 : 0
    // functional update + keepMeasured: React Flow's size updates arrive through setNodes too, and a
    // tween frame must never overwrite them (a node without `measured` is invisible)
    tweenStop.current = tweenNodes(prev, target, (ns) => setNodes((cur) => withRing(keepMeasured(ns, cur))), { duration: dur })
    // a pending zoom (drawer row click) wins over the general fit; it waits for the glide to land
    const zoomId = zoomTarget.current && target.some((n) => n.id === zoomTarget.current) ? zoomTarget.current : null
    zoomTarget.current = null
    const t = setTimeout(() => {
      // the glide has landed: make React Flow re-measure every node. Under rapid +/- its own
      // measure step can be lost (a node then has a size but no handle bounds, and its edges are
      // never drawn); this explicit pass is idempotent and cheap for ≤ 30 nodes.
      updateNodeInternals(target.map((n) => n.id))
      if (zoomId) rf.fitView({ nodes: [{ id: zoomId }], padding: 0.6, maxZoom: 1.6, duration: dur ? 350 : 0 })
      else rf.fitView({ padding: 0.15, duration: dur ? 300 : 0 })
    }, dur + 50)
    return () => clearTimeout(t)
  }, [g.flow, rf, updateNodeInternals, setNodes, setEdges, settings.animate, withRing])

  // a newly picked drawer row re-tints the edges already on the canvas — or, when
  // the flow is not drawn, conjures a ghost edge (and a ghost node for an off-canvas end)
  useEffect(() => {
    const base = withoutGhosts(rf.getNodes() as Node<FlowNodeData>[])
    setEdges((prev) => decorate(base, withoutGhosts(prev), pickedRow).edges)
    setNodes((prev) => {
      const clean = withoutGhosts(prev)
      const extra = decorate(clean, [], pickedRow).nodes.filter((n) => n.id.startsWith('ghost:'))
      return extra.length ? [...clean, ...extra] : clean
    })
  }, [pickedRow, rf, setEdges, setNodes])


  useEffect(() => {
    const onToggle = (e: Event) => g.toggle((e as CustomEvent<{ fileid: string }>).detail.fileid)
    const onToggleBlock = (e: Event) => g.toggleBlock((e as CustomEvent<{ id: string }>).detail.id)
    window.addEventListener('node4:toggle', onToggle)
    window.addEventListener('node4:toggleBlock', onToggleBlock)
    return () => {
      window.removeEventListener('node4:toggle', onToggle)
      window.removeEventListener('node4:toggleBlock', onToggleBlock)
    }
  }, [g.toggle, g.toggleBlock])

  // scroll the code pane to the highlighted block once its code is there
  const detail = selectedFile ? g.details.get(selectedFile) ?? null : null
  useEffect(() => {
    if (!highlightBlock || !detail || !codeViewRef.current) return
    const chip = codeViewRef.current.querySelector<HTMLElement>(`[data-block="${highlightBlock}"]`)
    chip?.scrollIntoView({ block: 'center' })
  }, [highlightBlock, detail])

  const pickFile = useCallback((fileid: string) => {
    setSelectedFile(fileid)
    setHighlightBlock(null)
    if (!pinned) setParams({ file: fileid, up: params.up, down: params.down })
  }, [pinned, params.up, params.down, setParams])

  // single click: only select (code + edges below follow); double click: re-seed on it
  const onNodeClick: NodeMouseHandler<Node<FlowNodeData>> = useCallback((_, node) => {
    const d = node.data
    if (!d.fileid) return
    setSelectedFile(d.fileid)
    if (d.kind === 'occurrence') {
      setHighlightBlock(d.blockId ?? null)
      setFocus({ kind: 'table', value: d.label, fileid: d.fileid })
    } else if (d.kind === 'blockCluster') {
      const blockId = node.id.split('::').pop() ?? null
      setHighlightBlock(blockId)
      setFocus(blockId ? { kind: 'block', value: blockId, fileid: d.fileid } : null)
    } else {
      setHighlightBlock(null)
      setFocus({ kind: 'file', value: d.fileid })
    }
  }, [])
  const onNodeDoubleClick: NodeMouseHandler<Node<FlowNodeData>> = useCallback((_, node) => {
    if (node.data.fileid) pickFile(node.data.fileid)
  }, [pickFile])

  const onNodeDragStop: OnNodeDrag<Node<FlowNodeData>> = useCallback(async () => {
    const routed = await g.reroute(getPositions())
    if (routed) setEdges(routed)
  }, [g, getPositions, setEdges])

  const onSearchSelect = useCallback((hit: SearchHit) => {
    if (hit.kind === 'table') {
      setParams({ table: hit.value, up: params.up, down: params.down })
      setSelectedFile(hit.files[0] ?? null)
    } else {
      const fileid = hit.files[0] ?? hit.value
      setParams({ file: fileid, up: params.up, down: params.down })
      setSelectedFile(fileid)
    }
    setHighlightBlock(null)
  }, [params.up, params.down, setParams])


  const onOpenBlock = useCallback((fileid: string, blockId: string | null, row?: EdgeRow) => {
    setSelectedFile(fileid)
    setHighlightBlock(blockId)
    if (row) setPickedRow(row)
    const nodeId = blockId ? `${fileid}::${blockId}` : fileid
    if (blockId && !g.expanded.has(fileid)) {
      // the block appears with the next layout; zoom then
      zoomTarget.current = nodeId
      g.expand(fileid)
    } else {
      const now = rf.getNodes() as Node<FlowNodeData>[]
      const present = now.some((n) => n.id === nodeId)
      const ids: { id: string }[] = [{ id: present ? nodeId : fileid }]
      if (row && matchingEdgeIds(withoutGhosts(now), withoutGhosts(rf.getEdges() as Edge<FlowEdgeData>[]), row).size === 0) {
        const gh = ghostForRow(withoutGhosts(now), row)
        if (gh) ids.splice(0, ids.length, { id: gh.edge.source }, { id: gh.edge.target })
      }
      // the ghost node is added by the pickedRow effect right after this handler; fit once it exists
      setTimeout(() => rf.fitView({ nodes: ids, padding: 0.5, maxZoom: 1.6, duration: settings.animate && document.visibilityState !== 'hidden' ? 350 : 0 }), 30)
    }
  }, [g, rf, settings.animate])
  // picking a section in the code pane: ring its block on the canvas (expanding the file if needed) and zoom to it
  const onChipClick = useCallback((blockId: string) => {
    if (selectedFile) { onOpenBlock(selectedFile, blockId); setFocus({ kind: 'block', value: blockId, fileid: selectedFile }) }
    else setHighlightBlock(blockId)
  }, [selectedFile, onOpenBlock])
  // clicking the canvas background clears the drawer focus and the edge highlight
  const clearPicks = useCallback(() => { setFocus(null); setPickedRow(null) }, [])

  const currentFiles: TreeFile[] = useMemo(
    () => (g.hood?.nodes ?? []).map((n) => ({ id: n.id, label: n.label, folder: n.folder })).sort((a, b) => a.id.localeCompare(b.id)),
    [g.hood],
  )
  const hoodFileids = useMemo(() => (g.hood?.nodes ?? []).map((n) => n.id), [g.hood])

  const hasSeed = Boolean(params.file || params.table)
  const hint = !hasSeed ? 'search a table or file to see its neighborhood' : g.hood && g.hood.nodes.length === 0 ? 'nothing flows into or out of this seed' : undefined

  return (
    <div className="app-root" data-cid="app">
      <div className="vscode-shell" data-cid="vscode-shell" style={{ gridTemplateColumns: `${explorerWidth}px 4px 1fr` }}>
        <ExplorerTree
          current={currentFiles}
          all={allFiles}
          onPick={pickFile}
          filter={explorerFilter}
          onFilterChange={setExplorerFilter}
          selected={selectedFile}
        />
        <Sash
          orientation="vertical"
          dataCid="sash-explorer"
          onDrag={(d) => setExplorerWidth((w) => clamp(w + d, MIN_EXPLORER_WIDTH, MAX_EXPLORER_WIDTH))}
          onReset={() => setExplorerWidth(DEFAULT_EXPLORER_WIDTH)}
        />
        <div className="vscode-main" data-cid="vscode-main">
          <div className="command-bar" data-cid="command-bar">
            <SearchBar onSelect={onSearchSelect} />
            <button
              type="button"
              className={pinned ? 'pin-toggle pinned' : 'pin-toggle'}
              data-cid="pin-toggle"
              aria-pressed={pinned}
              title={pinned ? 'pinned: clicking a file only changes the code below' : 'pin these results: clicking a file will stop re-centering'}
              onClick={() => setPinned((v) => !v)}
            >
              {pinned ? 'Pinned' : 'Pin'}
            </button>
            <SettingsPanel settings={settings} onChange={setSettings} />
            <Toolbar
              params={params}
              onParams={setParams}
              onExpandAll={g.expandAll}
              onCollapseAll={g.collapseAll}
              onFit={() => rf.fitView({ padding: 0.15 })}
              onRelayout={g.relayout}
              disabled={!g.hood}
              hint={g.status === 'loading' ? 'loading…' : undefined}
            />
          </div>
          {g.status === 'error' && <Banner kind="error">{`API not reachable (${g.error}). Start it with:\n${START_CMD}`}</Banner>}
          {g.layoutError && <Banner kind="info">{`ELK layout failed (${g.layoutError}); showing a plain grid.`}</Banner>}
          {g.routeError && <Banner kind="info">{`libavoid routing failed (${g.routeError}); showing ELK's edges.`}</Banner>}
          {g.holaError && <Banner kind="info">{`HOLA placement failed (${g.holaError}); showing ELK's layout. Start the sidecar with:\n${HOLA_CMD}`}</Banner>}
          {g.holaWarnings.length > 0 && <Banner kind="info">{`HOLA fell back on ${g.holaWarnings.length} component(s): ${g.holaWarnings.join(' · ')}`}</Banner>}
          {g.failed.size > 0 && <Banner kind="info">{`could not load blocks for ${[...g.failed].join(', ')}`}</Banner>}
          {hint && g.status !== 'error' && <Banner kind="info">{hint}</Banner>}
          <div className="canvas" data-cid="canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              onNodeDoubleClick={onNodeDoubleClick}
              onPaneClick={clearPicks}
              onNodeDragStop={onNodeDragStop}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              minZoom={0.1}
              nodesConnectable={false}
              elementsSelectable
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={18} size={1} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <Sash
            orientation="horizontal"
            dataCid="sash-panel"
            onDrag={(d) => setPanelHeight((h) => clamp(h - d, MIN_PANEL_HEIGHT, MAX_PANEL_HEIGHT))}
            onReset={() => setPanelHeight(defaultPanelHeight())}
          />
          <div className="bottom-panel" data-cid="bottom-panel" style={{ height: panelHeight }}>
            <div className="panel-body" data-cid="panel-body" style={{ gridTemplateColumns: `${panelSplit}% 4px 1fr` }}>
              <div className="panel-half panel-code" data-cid="panel-code">
                <div className="panel-half-header">SAS Code{selectedFile ? ` — ${selectedFile}` : ''}</div>
                <CodePane detail={detail} highlightBlock={highlightBlock} onChipClick={onChipClick} codeViewRef={codeViewRef} />
              </div>
              <Sash
                orientation="vertical"
                dataCid="sash-panel-split"
                onDrag={(d) => setPanelSplit((pct) => clamp(pct + d / 8, MIN_SPLIT_PCT, MAX_SPLIT_PCT))}
                onReset={() => setPanelSplit(50)}
              />
              <div className="panel-half panel-edges" data-cid="panel-edges">
                <div className="panel-half-header">Edges</div>
                <EdgesPanel fileids={hoodFileids} onOpenBlock={onOpenBlock} focus={focus} onClearFocus={() => setFocus(null)} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [params, setParamsState] = useState<Params>(() => readParams(window.location.search))
  const setParams = useCallback((p: Params) => {
    setParamsState(p)
    window.history.replaceState(null, '', writeParams(p))
  }, [])
  useEffect(() => {
    const onPop = () => setParamsState(readParams(window.location.search))
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  return (
    <ReactFlowProvider>
      <Workbench params={params} setParams={setParams} />
    </ReactFlowProvider>
  )
}
