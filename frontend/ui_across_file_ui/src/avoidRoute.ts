// Tier 4: obstacle-avoiding orthogonal edge routing with libavoid (Adaptagrams),
// via @mr_mint/elkjs-libavoid's WASM wrapper. ELK still places the nodes; this
// re-routes every edge around every LEAF box (files, table pills, folded
// blocks). Containers are visual frames, not obstacles, so an edge may cross a
// container border to reach a pill inside it.
//
// Loaded lazily: the wasm is only fetched when the setting is on, and unit
// tests never touch it.
import type { LaidOut, LaidOutEdge, LaidOutNode, Point } from './elkLayout'

export interface AvoidOptions {
  shapeBufferDistance?: number
  idealNudgingDistance?: number
  segmentPenalty?: number
  crossingPenalty?: number
}

const DEFAULTS: Required<AvoidOptions> = { shapeBufferDistance: 10, idealNudgingDistance: 8, segmentPenalty: 10, crossingPenalty: 4 }

let ready: Promise<typeof import('@mr_mint/elkjs-libavoid')> | null = null
function lib() {
  if (!ready) {
    ready = import('@mr_mint/elkjs-libavoid').then(async (m) => {
      await m.init(`${import.meta.env.BASE_URL}libavoid.wasm`)
      return m
    })
  }
  return ready
}

/** Leaf boxes only: anything that has no children is an obstacle. */
export function obstacles(nodes: LaidOutNode[]): LaidOutNode[] {
  const parents = new Set(nodes.map((n) => n.parent).filter(Boolean))
  return nodes.filter((n) => !parents.has(n.id))
}

/** Flat routing graph (absolute coordinates) for the wrapper. */
export function routingGraph(nodes: LaidOutNode[], edges: LaidOutEdge[]) {
  const leaves = obstacles(nodes)
  const ids = new Set(leaves.map((n) => n.id))
  return {
    id: 'root',
    children: leaves.map((n) => ({ id: n.id, x: n.x, y: n.y, width: n.width, height: n.height })),
    edges: edges.filter((e) => ids.has(e.source) && ids.has(e.target)).map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  }
}

/** Route `laid.edges` around `laid.nodes`; edges whose endpoint is a container keep their ELK route. */
export async function routeWithAvoid(laid: LaidOut, opts: AvoidOptions = {}): Promise<LaidOutEdge[]> {
  const m = await lib()
  const graph = routingGraph(laid.nodes, laid.edges)
  if (graph.edges.length === 0) return laid.edges
  const o = { ...DEFAULTS, ...opts }
  const routes = await m.routeEdges(graph, {
    routingType: 'orthogonal',
    shapeBufferDistance: o.shapeBufferDistance,
    idealNudgingDistance: o.idealNudgingDistance,
    segmentPenalty: o.segmentPenalty,
    crossingPenalty: o.crossingPenalty,
    nudgeOrthogonalSegmentsConnectedToShapes: true,
    nudgeSharedPathsWithCommonEndPoint: true,
  })
  return laid.edges.map((e) => {
    const r = routes.get(e.id)
    if (!r) return e
    const points: Point[] = [r.sourcePoint, ...r.bendPoints, r.targetPoint].map((p) => ({ x: p.x, y: p.y }))
    return { ...e, points, labelAt: undefined }
  })
}
