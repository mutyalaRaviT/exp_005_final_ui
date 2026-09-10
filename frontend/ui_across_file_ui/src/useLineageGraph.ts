import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Edge, Node } from '@xyflow/react'
import { fetchBlockLinks, fetchFileDetail, fetchNeighborhood, type BlockLink, type FileDetail, type Neighborhood, type NodeRole } from './api'
import { graph2Elements, type Graph2Element } from './graph2'
import { openTables } from './openTables'
import { edgeReasons } from './edgeReasons'
import { columnEdges } from './columnEdges'
import { collapseBlocks } from './collapseBlocks'
import { elkLayout, type LaidOut, type Point } from './elkLayout'
import { routeWithAvoid } from './avoidRoute'
import { holaLayout } from './holaLayout'
import { DEFAULT_SETTINGS, type LayoutSettings } from './layoutSettings'
import { toFlow, type FlowEdgeData, type FlowNodeData } from './toFlow'
import { placeLabels } from './labelPlacement'
import type { Params } from './urlParams'

// Task 8 (2026-09-10): this used to name a Python server in ~/Desktop/sas2py_projects,
// a machine-specific path from the August track that no longer exists here. The API this
// window talks to is the Rust one on :8110 (vite.config.ts proxies /api to it).
export const START_CMD =
  'cd backend && cargo run --release -p lineageq_api -- --db lineageq.duckdb --port 8110'

type Status = 'idle' | 'loading' | 'ready' | 'error'

/** Fallback when ELK throws: files in a row, no nesting, straight edges. */
function gridLayout(elements: Graph2Element[]): LaidOut {
  const files = elements.filter((e) => !e.data.source && !e.data.parent)
  const nodes = files.map((e, i) => ({
    id: e.data.id, kind: 'file' as const, label: e.data.label ?? e.data.id, x: i * 200, y: 0, width: 160, height: 44, fileid: e.data.fileid, cyclic: e.data.cyclic,
  }))
  const pos = new Map(nodes.map((n) => [n.id, n]))
  const edges = elements
    .filter((e) => e.data.source && pos.has(e.data.source) && pos.has(e.data.target!))
    .map((e) => {
      const s = pos.get(e.data.source!)!
      const t = pos.get(e.data.target!)!
      return { id: e.data.id, source: s.id, target: t.id, label: e.data.label, fact: e.data.fact, points: [{ x: s.x + s.width, y: s.y + 22 }, { x: t.x, y: t.y + 22 }] }
    })
  return { nodes, edges }
}

/** `alsoDetail` is a file whose FileDetail the shell wants (the code pane) even when it is not expanded on the canvas. */
export interface LineageGraphOptions {
  settings?: LayoutSettings
  /** current absolute node positions (from React Flow) — read when keepArrangement is on or when re-routing after a drag */
  getPositions?: () => Map<string, Point>
}

export function useLineageGraph(params: Params, alsoDetail: string | null = null, opts: LineageGraphOptions = {}) {
  const settings = opts.settings ?? DEFAULT_SETTINGS
  const getPositions = opts.getPositions
  const [hood, setHood] = useState<Neighborhood | null>(null)
  const [links, setLinks] = useState<BlockLink[]>([])
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | undefined>()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [collapsedBlocks, setCollapsedBlocks] = useState<Set<string>>(new Set())
  const [openedTables, setOpenedTables] = useState<Set<string>>(new Set())
  const [failed, setFailed] = useState<Set<string>>(new Set())
  const [details, setDetails] = useState<Map<string, FileDetail>>(new Map())
  const [flow, setFlow] = useState<{ nodes: Node<FlowNodeData>[]; edges: Edge<FlowEdgeData>[] } | null>(null)
  const [layoutError, setLayoutError] = useState<string | undefined>()
  const [layoutTick, setLayoutTick] = useState(0)
  const [routeError, setRouteError] = useState<string | undefined>()
  const [holaError, setHolaError] = useState<string | undefined>()
  const [holaWarnings, setHolaWarnings] = useState<string[]>([])
  const lastLaid = useRef<LaidOut | null>(null)
  const seq = useRef(0)

  // 1. seed -> neighborhood + block links
  useEffect(() => {
    if (!params.file && !params.table) {
      ++seq.current
      setHood(null); setStatus('idle'); setFlow(null)
      return
    }
    const my = ++seq.current
    setStatus('loading'); setError(undefined)
    ;(async () => {
      try {
        const h = await fetchNeighborhood(params)
        const l = await fetchBlockLinks(h.nodes.map((n) => n.id))
        if (my !== seq.current) return
        setHood(h); setLinks(l); setExpanded(new Set()); setStatus('ready')
      } catch (e) {
        if (my !== seq.current) return
        setError(e instanceof Error ? e.message : String(e)); setStatus('error'); setHood(null); setFlow(null)
      }
    })()
  }, [params.file, params.table, params.up, params.down])

  // 2. expanded files need their detail
  useEffect(() => {
    const wanted = new Set(expanded)
    if (alsoDetail) wanted.add(alsoDetail)
    const missing = [...wanted].filter((f) => !details.has(f) && !failed.has(f))
    if (missing.length === 0) return
    let cancelled = false
    ;(async () => {
      const got = await Promise.all(missing.map(async (f) => [f, await fetchFileDetail(f).catch(() => null)] as const))
      if (cancelled) return
      setDetails((prev) => {
        const next = new Map(prev)
        for (const [f, d] of got) if (d) next.set(f, d)
        return next
      })
      const failedIds = got.filter(([, d]) => !d).map(([f]) => f)
      if (failedIds.length) {
        setExpanded((prev) => { const n = new Set(prev); failedIds.forEach((f) => n.delete(f)); return n })
        setFailed((prev) => { const n = new Set(prev); failedIds.forEach((f) => n.add(f)); return n })
      }
    })()
    return () => { cancelled = true }
  }, [expanded, details, alsoDetail, failed])

  const elements = useMemo(
    () => (hood ? columnEdges(edgeReasons(openTables(collapseBlocks(graph2Elements(hood, expanded, details, links), collapsedBlocks), openedTables, details), details), details) : []),
    [hood, expanded, details, links, collapsedBlocks, openedTables],
  )

  const ctx = useMemo(() => {
    const roles = new Map<string, NodeRole>()
    const scores = new Map<string, number>()
    const occRoles = new Map<string, 'read' | 'write'>()
    for (const n of hood?.nodes ?? []) {
      roles.set(n.id, n.role ?? (hood?.seeds?.includes(n.id) ? 'seed' : 'down'))
      scores.set(n.id, n.score)
    }
    for (const [fileid, d] of details) for (const b of d.blocks) for (const o of b.occurrences) occRoles.set(`${fileid}::${o.id}`, o.role)
    return { roles, scores, occRoles, expanded }
  }, [hood, details, expanded])

  const order = useMemo(() => new Map((hood?.nodes ?? []).map((n) => [n.id, n.score])), [hood])

  // 3. elements -> ELK (+ HOLA) (+ libavoid) -> React Flow
  useEffect(() => {
    if (!hood) return
    let cancelled = false
    ;(async () => {
      let laid: LaidOut
      try {
        const positions = settings.keepArrangement ? getPositions?.() : undefined
        laid = await elkLayout(elements, { settings, positions, order })
        if (!cancelled) setLayoutError(undefined)
      } catch (e) {
        if (!cancelled) console.error('ELK layout failed, using grid fallback', e)
        laid = gridLayout(elements)
        if (!cancelled) setLayoutError(e instanceof Error ? e.message : String(e))
      }
      if (cancelled) return
      if (settings.holaLayout) {
        try {
          const h = await holaLayout(laid)
          laid = h.laid
          if (!cancelled) { setHolaError(undefined); setHolaWarnings(h.warnings) }
        } catch (e) {
          if (!cancelled) { setHolaError(e instanceof Error ? e.message : String(e)); setHolaWarnings([]) }
        }
        if (cancelled) return
      } else {
        setHolaError(undefined); setHolaWarnings([])
      }
      if (settings.avoidRouting) {
        try {
          laid = { ...laid, edges: await routeWithAvoid(laid) }
          if (!cancelled) setRouteError(undefined)
        } catch (e) {
          if (!cancelled) setRouteError(e instanceof Error ? e.message : String(e))
        }
        if (cancelled) return
      } else {
        setRouteError(undefined)
      }
      lastLaid.current = laid
      const f = toFlow(laid, ctx)
      setFlow({ nodes: f.nodes, edges: placeLabels(f.edges) })
    })()
    return () => { cancelled = true }
    // getPositions is a ref-like getter; reading it inside the effect is intended
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hood, elements, ctx, layoutTick, settings, order])

  /** After a drag with avoidRouting on: re-route edges around the boxes where they are now. */
  const reroute = useCallback(async (positions: Map<string, Point>): Promise<Edge<FlowEdgeData>[] | null> => {
    const laid = lastLaid.current
    if (!laid || !settings.avoidRouting) return null
    const moved: LaidOut = { ...laid, nodes: laid.nodes.map((n) => { const p = positions.get(n.id); return p ? { ...n, x: p.x, y: p.y } : n }) }
    try {
      const edges = await routeWithAvoid(moved)
      const f = toFlow({ ...moved, edges }, ctx)
      return placeLabels(f.edges)
    } catch (e) {
      setRouteError(e instanceof Error ? e.message : String(e))
      return null
    }
  }, [settings.avoidRouting, ctx])

  const toggle = useCallback((fileid: string) => {
    setExpanded((prev) => { const n = new Set(prev); n.has(fileid) ? n.delete(fileid) : n.add(fileid); return n })
    setFailed((prev) => { if (!prev.has(fileid)) return prev; const n = new Set(prev); n.delete(fileid); return n })
  }, [])
  const toggleBlock = useCallback((id: string) => {
    setCollapsedBlocks((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  }, [])
  const toggleTable = useCallback((id: string) => {
    setOpenedTables((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })
  }, [])
  const openTable = useCallback((id: string) => {
    setOpenedTables((prev) => (prev.has(id) ? prev : new Set(prev).add(id)))
  }, [])
  const expand = useCallback((fileid: string) => {
    setExpanded((prev) => (prev.has(fileid) ? prev : new Set(prev).add(fileid)))
  }, [])
  const expandAll = useCallback(() => setExpanded(new Set(hood?.nodes.map((n) => n.id) ?? [])), [hood])
  const collapseAll = useCallback(() => setExpanded(new Set()), [])
  const relayout = useCallback(() => setLayoutTick((t) => t + 1), [])

  return { hood, status, error, expanded, failed, details, collapsedBlocks, openedTables, toggle, toggleBlock, toggleTable, openTable, expand, expandAll, collapseAll, flow, layoutError, routeError, holaError, holaWarnings, relayout, reroute }
}
