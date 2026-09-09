// Pure adapter: Graph2Element[] -> ELK layered layout -> absolute boxes and
// edge polylines. Same option family as the 5173 canvas (GRAPH2_LAYOUT), so
// the React Flow picture matches the cytoscape one. `LayoutSettings` switch on
// the tier-1..3 refinements (merged edges, side ports, ELK labels, semi-
// interactive re-layout, model order).
import ELK, { type ElkNode, type ElkExtendedEdge, type ElkPort, type ElkLabel } from 'elkjs/lib/elk.bundled.js'
import type { Graph2Element } from './graph2'
import { DEFAULT_SETTINGS, type LayoutSettings } from './layoutSettings'

export type Graph2Kind = 'file' | 'fileCluster' | 'blockCluster' | 'macro' | 'occurrence'

export interface Point { x: number; y: number }
export interface LaidOutNode {
  id: string
  kind: Graph2Kind
  label: string
  parent?: string
  x: number
  y: number
  width: number
  height: number
  fileid?: string
  blockId?: string
  cyclic?: boolean
  collapsed?: boolean
}
export interface LaidOutEdge {
  id: string
  source: string
  target: string
  label?: string
  fact?: boolean
  points: Point[]
  /** label centre chosen by ELK (only when settings.elkLabels) */
  labelAt?: Point
}
export interface LaidOut { nodes: LaidOutNode[]; edges: LaidOutEdge[] }

export interface LayoutInput {
  settings?: LayoutSettings
  /** absolute positions of nodes as the user left them — used when settings.keepArrangement */
  positions?: Map<string, Point>
  /** run order per top-level node id — used when settings.followRunOrder */
  order?: Map<string, number>
}

const CHAR_W = 7
export function estimateSize(kind: Graph2Kind, label: string): { width: number; height: number } {
  const firstLine = label.split('\n')[0] ?? ''
  if (kind === 'file') return { width: Math.max(140, CHAR_W * firstLine.length + 40), height: 44 }
  if (kind === 'occurrence') return { width: CHAR_W * firstLine.length + 24, height: 26 }
  if (kind === 'blockCluster') return { width: Math.max(150, CHAR_W * firstLine.length + 56), height: 34 }
  // containers: a minimum so a title always fits; ELK grows them to their children
  return { width: Math.max(160, CHAR_W * firstLine.length + 60), height: 60 }
}

export const inPort = (id: string) => `${id}::in`
export const outPort = (id: string) => `${id}::out`

/** The ELK root options for a settings object — exported so tests can assert on them. */
export function rootOptions(s: LayoutSettings): Record<string, string> {
  const o: Record<string, string> = {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.edgeRouting': 'ORTHOGONAL',
    'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
    'elk.layered.spacing.nodeNodeBetweenLayers': '90',
    'elk.spacing.nodeNode': '26',
    'elk.spacing.componentComponent': '40',
    'elk.layered.nodePlacement.strategy': s.nodePlacement,
    'elk.layered.layering.strategy': s.layering,
    'elk.layered.thoroughness': String(s.thoroughness),
  }
  if (s.greedySwitch) o['elk.layered.crossingMinimization.greedySwitch.type'] = 'TWO_SIDED'
  if (s.nodePromotion) o['elk.layered.layering.nodePromotion.strategy'] = 'NIKOLOV_IMPROVED'
  if (s.compaction) o['elk.layered.compaction.postCompaction.strategy'] = 'EDGE_LENGTH'
  if (s.mergeEdges) {
    o['elk.layered.mergeEdges'] = 'true'
    o['elk.layered.mergeHierarchyEdges'] = 'true'
  }
  if (s.straighten) {
    o['elk.layered.unnecessaryBendpoints'] = 'true'
    o['elk.layered.nodePlacement.favorStraightEdges'] = 'true'
    o['elk.spacing.edgeEdge'] = '12'
    o['elk.layered.spacing.edgeEdgeBetweenLayers'] = '12'
    o['elk.spacing.edgeNode'] = '18'
    o['elk.layered.spacing.edgeNodeBetweenLayers'] = '24'
  }
  if (s.elkLabels) {
    o['elk.edgeLabels.placement'] = 'CENTER'
    o['elk.spacing.edgeLabel'] = '4'
  }
  if (s.keepArrangement) {
    o['elk.layered.cycleBreaking.strategy'] = 'INTERACTIVE'
    o['elk.layered.layering.strategy'] = 'INTERACTIVE' // wins over the placement group's layering
    o['elk.layered.crossingMinimization.semiInteractive'] = 'true'
  }
  if (s.followRunOrder) {
    o['elk.layered.considerModelOrder.strategy'] = 'NODES_AND_EDGES'
  }
  if (s.stableOrder) {
    // the children order IS the order: sorted by file name in elkLayout, and ELK must not reorder them
    o['elk.layered.considerModelOrder.strategy'] = 'NODES_AND_EDGES'
    o['elk.layered.crossingMinimization.forceNodeModelOrder'] = 'true'
  }
  return o
}

const CONTAINER_OPTIONS: Record<string, string> = {
  'elk.padding': '[top=36,left=18,bottom=18,right=18]',
  'elk.direction': 'RIGHT',
  'elk.spacing.nodeNode': '18',
  'elk.layered.spacing.nodeNodeBetweenLayers': '50',
}

const elk = new ELK()

export async function elkLayout(elements: Graph2Element[], input: LayoutInput = {}): Promise<LaidOut> {
  const s = input.settings ?? DEFAULT_SETTINGS
  const nodeEls = elements.filter((e) => !e.data.source)
  const edgeEls = elements.filter((e) => e.data.source && e.data.target)
  if (nodeEls.length === 0) return { nodes: [], edges: [] }

  const parentOf = new Map(nodeEls.map((e) => [e.data.id, e.data.parent]))
  const absOfInput = (id: string): Point | undefined => input.positions?.get(id)
  /** ELK wants `elk.position` relative to the parent's origin */
  const relPosition = (id: string): string | undefined => {
    const p = absOfInput(id)
    if (!p) return undefined
    const parent = parentOf.get(id)
    const pp = parent ? absOfInput(parent) : undefined
    return `(${p.x - (pp?.x ?? 0)},${p.y - (pp?.y ?? 0)})`
  }

  // build the ELK tree
  const elkById = new Map<string, ElkNode>()
  for (const el of nodeEls) {
    const kind = (el.data.kind ?? 'file') as Graph2Kind
    const size = estimateSize(kind, el.data.label ?? el.data.id)
    const hasChildren = nodeEls.some((c) => c.data.parent === el.data.id)
    const isContainer = (kind === 'fileCluster' || kind === 'blockCluster' || kind === 'macro') && hasChildren
    const layoutOptions: Record<string, string> = { ...(isContainer ? CONTAINER_OPTIONS : {}) }
    if (s.sidePorts) layoutOptions['elk.portConstraints'] = 'FIXED_SIDE'
    if (s.keepArrangement) {
      const pos = relPosition(el.data.id)
      if (pos) layoutOptions['elk.position'] = pos
    }
    const ports: ElkPort[] | undefined = s.sidePorts
      ? [
          { id: inPort(el.data.id), width: 1, height: 1, layoutOptions: { 'elk.port.side': 'WEST' } },
          { id: outPort(el.data.id), width: 1, height: 1, layoutOptions: { 'elk.port.side': 'EAST' } },
        ]
      : undefined
    elkById.set(el.data.id, {
      id: el.data.id,
      width: size.width,
      height: size.height,
      children: [],
      ports,
      layoutOptions: Object.keys(layoutOptions).length ? layoutOptions : undefined,
    })
  }
  const root: ElkNode = { id: 'root', layoutOptions: rootOptions(s), children: [], edges: [] }
  for (const el of nodeEls) {
    const node = elkById.get(el.data.id)!
    const parent = el.data.parent ? elkById.get(el.data.parent) : undefined
    ;(parent ?? root).children!.push(node)
  }
  // model order: top-level nodes by run order, then id; ELK reads children order
  if (s.stableOrder) {
    // by file name (the label), so the same files sit in the same vertical order whatever is expanded
    const label = new Map(nodeEls.map((e) => [e.data.id, (e.data.label ?? e.data.id).split('\n')[0]]))
    root.children!.sort((a, b) => label.get(a.id)!.localeCompare(label.get(b.id)!) || a.id.localeCompare(b.id))
  } else if (s.followRunOrder && input.order) {
    const ord = input.order
    root.children!.sort((a, b) => (ord.get(a.id) ?? 1e9) - (ord.get(b.id) ?? 1e9) || a.id.localeCompare(b.id))
  }
  const idSet = new Set(elkById.keys())
  root.edges = edgeEls
    .filter((e) => idSet.has(e.data.source!) && idSet.has(e.data.target!))
    .map<ElkExtendedEdge>((e) => {
      const edge: ElkExtendedEdge = {
        id: e.data.id,
        sources: [s.sidePorts ? outPort(e.data.source!) : e.data.source!],
        targets: [s.sidePorts ? inPort(e.data.target!) : e.data.target!],
      }
      if (s.elkLabels && e.data.label) {
        const label: ElkLabel = { id: `${e.data.id}::label`, text: e.data.label, width: CHAR_W * e.data.label.length, height: 12 }
        edge.labels = [label]
      }
      return edge
    })

  const laid = await elk.layout(root)

  // absolute positions by walking the tree; ELK child coords are parent-relative
  const abs = new Map<string, Point>()
  const outNodes: LaidOutNode[] = []
  const elByIdData = new Map(nodeEls.map((e) => [e.data.id, e.data]))
  const walk = (n: ElkNode, ox: number, oy: number, parent?: string) => {
    for (const c of n.children ?? []) {
      const x = ox + (c.x ?? 0)
      const y = oy + (c.y ?? 0)
      abs.set(c.id, { x, y })
      const d = elByIdData.get(c.id)!
      outNodes.push({
        id: c.id,
        kind: (d.kind ?? 'file') as Graph2Kind,
        label: d.label ?? c.id,
        parent,
        x,
        y,
        width: c.width ?? 0,
        height: c.height ?? 0,
        fileid: d.fileid,
        blockId: d.blockId,
        cyclic: d.cyclic,
        collapsed: (d as { collapsed?: boolean }).collapsed,
      })
      walk(c, x, y, c.id)
    }
  }
  abs.set('root', { x: 0, y: 0 })
  walk(laid, 0, 0)

  // edge sections are relative to the edge's container node (root when absent)
  const edgeData = new Map(edgeEls.map((e) => [e.data.id, e.data]))
  const outEdges: LaidOutEdge[] = []
  for (const e of laid.edges ?? []) {
    const d = edgeData.get(e.id)
    if (!d) continue
    const container = (e as ElkExtendedEdge & { container?: string }).container ?? 'root'
    const o = abs.get(container) ?? { x: 0, y: 0 }
    const points: Point[] = []
    for (const sec of e.sections ?? []) {
      points.push({ x: sec.startPoint.x + o.x, y: sec.startPoint.y + o.y })
      for (const b of sec.bendPoints ?? []) points.push({ x: b.x + o.x, y: b.y + o.y })
      points.push({ x: sec.endPoint.x + o.x, y: sec.endPoint.y + o.y })
    }
    if (points.length < 2) {
      // no section (should not happen with layered) — straight centre to centre
      const sn = outNodes.find((n) => n.id === d.source)!
      const tn = outNodes.find((n) => n.id === d.target)!
      points.push({ x: sn.x + sn.width, y: sn.y + sn.height / 2 }, { x: tn.x, y: tn.y + tn.height / 2 })
    }
    let labelAt: Point | undefined
    const lab = e.labels?.[0]
    if (s.elkLabels && lab && lab.x !== undefined && lab.y !== undefined) {
      labelAt = { x: lab.x + o.x + (lab.width ?? 0) / 2, y: lab.y + o.y + (lab.height ?? 0) / 2 }
    }
    outEdges.push({ id: e.id, source: d.source!, target: d.target!, label: d.label, fact: d.fact, points, labelAt })
  }
  return { nodes: outNodes, edges: outEdges }
}
