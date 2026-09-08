import type { Edge, Node } from '@xyflow/react'
import { MarkerType } from '@xyflow/react'
import type { NodeRole } from './api'
import type { Graph2Kind, LaidOut, LaidOutNode, Point } from './elkLayout'
import { EDGE_FACT, EDGE_INFERRED } from './palette'

export interface FlowNodeData extends Record<string, unknown> {
  kind: Graph2Kind
  label: string
  fileid?: string
  blockId?: string
  role?: NodeRole
  score?: number
  cyclic?: boolean
  occRole?: 'read' | 'write'
  expanded?: boolean
  /** a blockCluster folded to a single box */
  collapsed?: boolean
}
export interface FlowEdgeData extends Record<string, unknown> {
  points: Point[]
  label?: string
  fact?: boolean
  labelAt?: Point
  /** drawn thick in the accent colour (a drawer row was clicked) */
  highlight?: boolean
  /** an imagined flow the canvas does not have: dashed */
  ghost?: boolean
  /** where the handles sit for the laid-out boxes — ElkEdge falls back to a live path once a node drifts from these */
  anchors?: { sx: number; sy: number; tx: number; ty: number }
}
export interface FlowContext {
  roles: Map<string, NodeRole>
  scores: Map<string, number>
  occRoles: Map<string, 'read' | 'write'>
  expanded: Set<string>
}

const TYPE_BY_KIND: Record<Graph2Kind, 'file' | 'cluster' | 'occurrence'> = {
  file: 'file',
  fileCluster: 'cluster',
  blockCluster: 'cluster',
  macro: 'cluster',
  occurrence: 'occurrence',
}

/**
 * Where React Flow's handles will sit for this edge (right-middle of the source box,
 * left-middle of the target box). ElkEdge compares the live handles against these to
 * tell a dragged node from a routed edge; the route's own endpoints may legitimately
 * leave through the top or bottom of a box (libavoid, HOLA), so they are not the anchors.
 */
export function anchorsOf(s: LaidOutNode | undefined, t: LaidOutNode | undefined, points: Point[]): FlowEdgeData['anchors'] {
  const first = points[0]
  const last = points[points.length - 1]
  return {
    sx: s ? s.x + s.width : first.x,
    sy: s ? s.y + s.height / 2 : first.y,
    tx: t ? t.x : last.x,
    ty: t ? t.y + t.height / 2 : last.y,
  }
}

export function toFlow(laid: LaidOut, ctx: FlowContext): { nodes: Node<FlowNodeData>[]; edges: Edge<FlowEdgeData>[] } {
  const abs = new Map(laid.nodes.map((n) => [n.id, n]))
  const nodes: Node<FlowNodeData>[] = laid.nodes.map((n) => {
    const p = n.parent ? abs.get(n.parent) : undefined
    const label = n.label.split('\n')[0]
    const fileKey = n.fileid ?? n.id
    return {
      id: n.id,
      type: TYPE_BY_KIND[n.kind],
      parentId: n.parent,
      // children stay inside their container when dragged
      extent: n.parent ? 'parent' : undefined,
      position: { x: n.x - (p?.x ?? 0), y: n.y - (p?.y ?? 0) },
      style: { width: n.width, height: n.height },
      // React Flow hides a node until it has a size; ELK's size is known up front, so hand it over
      // and the node is visible from its first frame (measuring still refines handles)
      initialWidth: n.width,
      initialHeight: n.height,
      draggable: true,
      data: {
        kind: n.kind,
        label,
        fileid: n.fileid,
        blockId: n.blockId,
        role: ctx.roles.get(fileKey),
        score: ctx.scores.get(fileKey),
        cyclic: n.cyclic,
        occRole: ctx.occRoles.get(n.id),
        expanded: n.kind === 'fileCluster' ? true : n.kind === 'file' ? ctx.expanded.has(n.id) : undefined,
        collapsed: n.collapsed,
      },
    }
  })
  const edges: Edge<FlowEdgeData>[] = laid.edges.map((e) => ({
    id: e.id,
    type: 'elk',
    source: e.source,
    target: e.target,
    markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: e.fact === false ? EDGE_INFERRED : EDGE_FACT },
    data: {
      points: e.points,
      label: e.label,
      fact: e.fact,
      labelAt: e.labelAt,
      anchors: anchorsOf(abs.get(e.source), abs.get(e.target), e.points),
    },
  }))
  return { nodes, edges }
}
