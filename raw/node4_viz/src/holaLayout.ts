// Tier 5: HOLA (libdialect, Adaptagrams) through the pyhola sidecar in
// scripts/hola_server. ELK still lays out the inside of every file box; HOLA
// then places the TOP-LEVEL boxes and routes the edges between them
// orthogonally around those boxes. Edges that start or end on a pill inside a
// box get HOLA's box-to-box route stitched to the pill with two short legs.
import type { LaidOut, LaidOutEdge, LaidOutNode, Point } from './elkLayout'

export const HOLA_CMD =
  'cd /Users/mutyala/Desktop/lineageQ/lineageQ_sep_experiments/exp_003_lineageq_slides/node4_viz/scripts/hola_server && .venv/bin/uvicorn server:app --port 8765'

export interface HolaRequest {
  nodes: { id: string; width: number; height: number }[]
  /** one per LaidOut edge, lifted to the top-level ancestors of its endpoints */
  edges: { id: string; source: string; target: string }[]
  opts?: Record<string, number | boolean>
}
export interface HolaResponse {
  nodes: { id: string; x: number; y: number; width: number; height: number }[]
  /** centre-to-centre orthogonal polyline per input edge id; empty when HOLA had no route */
  edges: { id: string; points: Point[] }[]
  ms?: number
  components?: number
  warnings?: string[]
}

/** The top-level ancestor of every node (itself when it has no parent). */
export function topOf(nodes: LaidOutNode[]): Map<string, string> {
  const parent = new Map(nodes.map((n) => [n.id, n.parent]))
  const top = new Map<string, string>()
  const resolve = (id: string): string => {
    const hit = top.get(id)
    if (hit) return hit
    const p = parent.get(id)
    const t = p ? resolve(p) : id
    top.set(id, t)
    return t
  }
  for (const n of nodes) resolve(n.id)
  return top
}

/** What HOLA sees: the top-level boxes with their ELK sizes, and every edge lifted to those boxes. */
export function topLevelGraph(laid: LaidOut): HolaRequest {
  const top = topOf(laid.nodes)
  return {
    nodes: laid.nodes.filter((n) => !n.parent).map((n) => ({ id: n.id, width: n.width, height: n.height })),
    edges: laid.edges.map((e) => ({ id: e.id, source: top.get(e.source)!, target: top.get(e.target)!, })),
  }
}

type Rect = { x: number; y: number; width: number; height: number }
const inside = (p: Point, r: Rect) => p.x >= r.x && p.x <= r.x + r.width && p.y >= r.y && p.y <= r.y + r.height

/** Where the segment a→b (a inside r, b outside) crosses r's border. Axis-aligned segments only, else b. */
function borderCrossing(a: Point, b: Point, r: Rect): Point {
  if (a.y === b.y) return { x: b.x > a.x ? r.x + r.width : r.x, y: a.y }
  if (a.x === b.x) return { x: a.x, y: b.y > a.y ? r.y + r.height : r.y }
  return b
}

/** Drop the part of a centre-to-centre route that lies inside the start box; first point becomes the border crossing. */
export function clipStart(points: Point[], r: Rect): Point[] {
  let i = 0
  while (i < points.length - 1 && inside(points[i + 1], r)) i++
  if (i >= points.length - 1) return points.slice(-1)
  return [borderCrossing(points[i], points[i + 1], r), ...points.slice(i + 1)]
}
export function clipEnd(points: Point[], r: Rect): Point[] {
  return clipStart([...points].reverse(), r).reverse()
}

/** Remove repeated points and points on a straight run. */
export function tidy(points: Point[]): Point[] {
  const out: Point[] = []
  for (const p of points) {
    const a = out[out.length - 1]
    if (a && a.x === p.x && a.y === p.y) continue
    const b = out[out.length - 2]
    if (a && b && ((a.x === b.x && a.x === p.x) || (a.y === b.y && a.y === p.y))) out.pop()
    out.push(p)
  }
  return out
}

/**
 * Move every top-level subtree to HOLA's position and rebuild the edges:
 * box-to-box routes from HOLA (clipped to the borders), stitched to pills with
 * an L-shaped leg on each end; edges inside one box keep their ELK route.
 */
export function applyHola(laid: LaidOut, res: HolaResponse): LaidOut {
  const top = topOf(laid.nodes)
  const delta = new Map<string, Point>()
  for (const n of laid.nodes) {
    if (n.parent) continue
    const h = res.nodes.find((r) => r.id === n.id)
    if (h) delta.set(n.id, { x: h.x - n.x, y: h.y - n.y })
  }
  const nodes = laid.nodes.map((n) => {
    const d = delta.get(top.get(n.id)!)
    return d ? { ...n, x: n.x + d.x, y: n.y + d.y } : n
  })
  const rect = new Map(nodes.map((n) => [n.id, n]))
  const route = new Map(res.edges.map((e) => [e.id, e.points]))

  const edges: LaidOutEdge[] = laid.edges.map((e) => {
    const sTop = top.get(e.source)!
    const tTop = top.get(e.target)!
    const s = rect.get(e.source)!
    const t = rect.get(e.target)!
    const outPort: Point = { x: s.x + s.width, y: s.y + s.height / 2 }
    const inPort: Point = { x: t.x, y: t.y + t.height / 2 }
    if (sTop === tTop) {
      const d = delta.get(sTop) ?? { x: 0, y: 0 }
      return { ...e, points: e.points.map((p) => ({ x: p.x + d.x, y: p.y + d.y })), labelAt: undefined }
    }
    const r = route.get(e.id)
    if (!r || r.length < 2) return { ...e, points: [outPort, inPort], labelAt: undefined }
    let pts = clipEnd(clipStart(r, rect.get(sTop)!), rect.get(tTop)!)
    if (e.source !== sTop) pts = [outPort, { x: pts[0].x, y: outPort.y }, ...pts]
    if (e.target !== tTop) pts = [...pts, { x: pts[pts.length - 1].x, y: inPort.y }, inPort]
    return { ...e, points: tidy(pts), labelAt: undefined }
  })
  return { nodes, edges }
}

/** Ask the sidecar, then apply. Throws with a readable message when it is not running. */
export async function holaLayout(laid: LaidOut, fetchImpl: typeof fetch = fetch): Promise<{ laid: LaidOut; warnings: string[] }> {
  if (laid.nodes.length === 0) return { laid, warnings: [] }
  const req = topLevelGraph(laid)
  let res: Response
  try {
    res = await fetchImpl('/hola/layout', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(req) })
  } catch (e) {
    throw new Error(`sidecar not reachable (${e instanceof Error ? e.message : String(e)})`)
  }
  if (!res.ok) throw new Error(`sidecar ${res.status}: ${(await res.text()).slice(0, 200)}`)
  const body = (await res.json()) as HolaResponse
  return { laid: applyHola(laid, body), warnings: body.warnings ?? [] }
}
