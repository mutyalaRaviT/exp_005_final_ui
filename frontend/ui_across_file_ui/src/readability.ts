// A readability score for what is on the canvas right now: 100 minus penalties
// for the things that make a lineage picture hard to read — a label sitting on
// a box, a label on another label, edges crossing, labels too long to scan.
// Pure geometry over screen rects and polylines; App collects them from the
// DOM after each layout and shows the number in the status bar, so every UX
// change can be judged against it. Not a proof of anything — a smell meter.
export interface Rect { x: number; y: number; w: number; h: number }
export interface Poly { points: { x: number; y: number }[]; /** a thin column → column edge: its crossings count half */ column?: boolean }
export interface Scene { nodes: Rect[]; labels: { rect: Rect; text: string }[]; edges: Poly[] }
export interface Score { score: number; labelOnBox: number; labelOnLabel: number; crossings: number; longLabels: number }

export const LABEL_MAX = 36
const P = { labelOnBox: 4, labelOnLabel: 3, crossing: 1, longLabel: 1, crossingCap: 30 }

const overlaps = (a: Rect, b: Rect) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
/** a label touching a box it does not belong beside counts once; a tiny overlap (< 4px) does not */
const overlapArea = (a: Rect, b: Rect) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y))

type Pt = { x: number; y: number }
const ccw = (a: Pt, b: Pt, c: Pt) => (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x)
const segCross = (a: Pt, b: Pt, c: Pt, d: Pt) => ccw(a, c, d) !== ccw(b, c, d) && ccw(a, b, c) !== ccw(a, b, d)

export function crossings(edges: Poly[]): number {
  let n = 0
  for (let i = 0; i < edges.length; i++) for (let j = i + 1; j < edges.length; j++) {
    const a = edges[i].points, b = edges[j].points
    const w = edges[i].column && edges[j].column ? 0.5 : 1
    for (let p = 0; p + 1 < a.length; p++) for (let q = 0; q + 1 < b.length; q++) if (segCross(a[p], a[p + 1], b[q], b[q + 1])) n += w
  }
  return n
}

export function readability(scene: Scene): Score {
  let labelOnBox = 0, labelOnLabel = 0, longLabels = 0
  for (const l of scene.labels) {
    if (scene.nodes.some((n) => overlaps(l.rect, n) && overlapArea(l.rect, n) >= 16)) labelOnBox++
    if (l.text.length > LABEL_MAX) longLabels++
  }
  for (let i = 0; i < scene.labels.length; i++) for (let j = i + 1; j < scene.labels.length; j++) if (overlaps(scene.labels[i].rect, scene.labels[j].rect)) labelOnLabel++
  const x = crossings(scene.edges)
  const penalty = labelOnBox * P.labelOnBox + labelOnLabel * P.labelOnLabel + Math.min(x, P.crossingCap) * P.crossing + longLabels * P.longLabel
  return { score: Math.round(Math.max(0, Math.min(100, 100 - penalty))), labelOnBox, labelOnLabel, crossings: x, longLabels }
}

/** Collect the scene from the live canvas: node boxes (leaf nodes only — groups are meant to contain labels), labels, and every edge path sampled to a polyline. */
export function sceneFromDom(root: ParentNode = document): Scene {
  const rect = (el: Element): Rect => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height } }
  const nodes = [...root.querySelectorAll('.rf-file, .rf-occ')].map(rect)
  const labels = [...root.querySelectorAll('.rf-edge-label')].map((el) => ({ rect: rect(el), text: el.textContent ?? '' }))
  const edges: Poly[] = []
  for (const p of root.querySelectorAll<SVGPathElement>('.react-flow__edge-path')) {
    const len = typeof p.getTotalLength === 'function' ? p.getTotalLength() : 0
    if (!len) continue
    const pts: Pt[] = []
    const steps = Math.max(2, Math.min(24, Math.round(len / 20)))
    for (let i = 0; i <= steps; i++) { const q = p.getPointAtLength((len * i) / steps); const m = p.getScreenCTM(); pts.push(m ? { x: q.x * m.a + q.y * m.c + m.e, y: q.x * m.b + q.y * m.d + m.f } : { x: q.x, y: q.y }) }
    edges.push({ points: pts, column: p.closest('.react-flow__edge')?.getAttribute('data-id')?.startsWith('ce:') ?? false })
  }
  return { nodes, labels, edges }
}
