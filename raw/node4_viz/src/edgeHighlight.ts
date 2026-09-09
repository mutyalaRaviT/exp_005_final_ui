// Which canvas edges does a drawer row stand for? Rows name tables (block /
// file level) or file ids (project level); canvas edges connect node ids. An
// edge matches when its endpoints' keys — the table name for a pill, the file
// id for a file or file container — equal the row's src and dst. Pure.
import type { Edge, Node } from '@xyflow/react'
import type { EdgeRow } from './api'
import type { FlowEdgeData, FlowNodeData } from './toFlow'

/** the identity a node carries for matching: table name for pills, file id for everything else */
export function nodeKey(n: Node<FlowNodeData>): string | undefined {
  return n.data.kind === 'occurrence' ? n.data.label : n.data.fileid
}

export function matchingEdgeIds(nodes: Node<FlowNodeData>[], edges: Edge<FlowEdgeData>[], row: Pick<EdgeRow, 'src' | 'dst' | 'fileid' | 'level'>): Set<string> {
  const key = new Map(nodes.map((n) => [n.id, nodeKey(n)]))
  const file = new Map(nodes.map((n) => [n.id, n.data.fileid]))
  const hits = new Set<string>()
  for (const e of edges) {
    const s = key.get(e.source)
    const t = key.get(e.target)
    if (s === row.src && t === row.dst) hits.add(e.id)
    // a file -> file row is also satisfied by an edge between those files' pills or containers
    if (row.level === 'project' && file.get(e.source) === row.src && file.get(e.target) === row.dst && file.get(e.source) !== file.get(e.target)) hits.add(e.id)
  }
  if (hits.size > 0 || row.level === 'project') return hits
  // block/file row whose tables are not expanded on the canvas: fall back to the
  // cross-file edge that carries the same flow between the row's file and its neighbours
  for (const e of edges) {
    const sNode = nodes.find((n) => n.id === e.source)
    const tNode = nodes.find((n) => n.id === e.target)
    const label = e.data?.label ?? ''
    if ((sNode?.data.fileid === row.fileid || tNode?.data.fileid === row.fileid) && (label.includes(row.dst) || label.includes(row.src))) hits.add(e.id)
  }
  return hits
}

/** Copy of `edges` with `data.highlight` set for the ids in `hits` (and cleared elsewhere). */
export function applyHighlight(edges: Edge<FlowEdgeData>[], hits: Set<string>): Edge<FlowEdgeData>[] {
  return edges.map((e) => {
    const on = hits.has(e.id)
    if (Boolean(e.data?.highlight) === on) return e
    return { ...e, zIndex: on ? 1000 : undefined, data: { ...(e.data as FlowEdgeData), highlight: on } }
  })
}

// ---- ghost edges: a drawer row whose flow is not on the canvas -------------

export const GHOST_EDGE_ID = 'ghost:row'
export const ghostNodeId = (key: string) => `ghost:${key}`

function sizeOf(n: Node<FlowNodeData>): { w: number; h: number } {
  const w = Number(n.measured?.width ?? n.style?.width ?? 160)
  const h = Number(n.measured?.height ?? n.style?.height ?? 44)
  return { w, h }
}

/** absolute position of a node (children are stored parent-relative) */
function absPos(n: Node<FlowNodeData>, byId: Map<string, Node<FlowNodeData>>): { x: number; y: number } {
  let x = n.position.x, y = n.position.y, p = n.parentId ? byId.get(n.parentId) : undefined
  while (p) { x += p.position.x; y += p.position.y; p = p.parentId ? byId.get(p.parentId) : undefined }
  return { x, y }
}

/** Ghost elements for a row with no matching canvas edge: at most one ghost node
 *  (for an endpoint that is not on the canvas) and one dashed ghost edge. Returns
 *  null when neither endpoint is on the canvas — nothing to anchor to. */
export function ghostForRow(nodes: Node<FlowNodeData>[], row: Pick<EdgeRow, 'src' | 'dst' | 'fileid' | 'level' | 'tables'> & Partial<Pick<EdgeRow, 'block_id'>>): { nodes: Node<FlowNodeData>[]; edge: Edge<FlowEdgeData> } | null {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const find = (key: string) =>
    nodes.find((n) => n.data.kind === 'occurrence' && n.data.label === key) ??
    nodes.find((n) => (n.data.kind === 'file' || n.data.kind === 'fileCluster') && n.data.fileid === key)
  let src = find(row.src)
  let dst = find(row.dst)
  const ghosts: Node<FlowNodeData>[] = []
  const ghost = (key: string, at: { x: number; y: number }): Node<FlowNodeData> => ({
    id: ghostNodeId(key),
    type: 'file',
    position: at,
    style: { width: 160, height: 44 },
    className: 'rf-ghost',
    draggable: true,
    selectable: false,
    data: { kind: 'file', label: key.split('/').pop() ?? key, fileid: key.includes('.') && !key.includes('/') ? undefined : key },
  })
  if (!src && !dst) {
    // neither table is drawn (file collapsed, or a file-level row): hang two
    // ghost tables either side of the row's block, else its file, and join them
    const anchor = (row.block_id ? byId.get(`${row.fileid}::${row.block_id}`) : undefined) ??
      nodes.find((n) => (n.data.kind === 'file' || n.data.kind === 'fileCluster') && n.data.fileid === row.fileid)
    if (!anchor) return null
    const p = absPos(anchor, byId)
    const { w, h } = sizeOf(anchor)
    const y = p.y + Math.max(0, h / 2 - 22)
    src = ghost(row.src, { x: p.x - 160 - 140, y })
    dst = ghost(row.dst, { x: p.x + w + 140, y })
    ghosts.push(src, dst)
  }
  if (!src && dst) {
    const p = absPos(dst, byId)
    src = ghost(row.src, { x: p.x - 160 - 140, y: p.y })
    ghosts.push(src)
  } else if (src && !dst) {
    const p = absPos(src, byId)
    const { w } = sizeOf(src)
    dst = ghost(row.dst, { x: p.x + w + 140, y: p.y })
    ghosts.push(dst)
  }
  const s = src!, t = dst!
  const sp = ghosts.includes(s) ? s.position : absPos(s, byId)
  const tp = ghosts.includes(t) ? t.position : absPos(t, byId)
  const ss = sizeOf(s), ts = sizeOf(t)
  const edge: Edge<FlowEdgeData> = {
    id: GHOST_EDGE_ID,
    type: 'elk',
    source: s.id,
    target: t.id,
    zIndex: 1000,
    data: {
      points: [{ x: sp.x + ss.w, y: sp.y + ss.h / 2 }, { x: tp.x, y: tp.y + ts.h / 2 }],
      label: row.tables[0],
      highlight: true,
      ghost: true,
    },
  }
  return { nodes: ghosts, edge }
}

/** Strip any ghost elements from a React Flow node/edge state. */
export function withoutGhosts<T extends { id: string }>(items: T[]): T[] {
  return items.filter((i) => !i.id.startsWith('ghost:'))
}
