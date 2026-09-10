import type { Point } from './elkLayout'

/** Polyline -> SVG path with rounded corners (quadratic curve at each bend). */
export function pointsToPath(points: Point[], radius = 8): string {
  if (points.length < 2) return ''
  const f = (n: number) => String(Math.round(n * 100) / 100)
  let d = `M ${f(points[0].x)} ${f(points[0].y)}`
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1]
    const cur = points[i]
    const next = points[i + 1]
    const inLen = Math.hypot(cur.x - prev.x, cur.y - prev.y)
    const outLen = Math.hypot(next.x - cur.x, next.y - cur.y)
    const r = Math.min(radius, inLen / 2, outLen / 2)
    if (r <= 0) {
      d += ` L ${f(cur.x)} ${f(cur.y)}`
      continue
    }
    const a = { x: cur.x - ((cur.x - prev.x) / inLen) * r, y: cur.y - ((cur.y - prev.y) / inLen) * r }
    const b = { x: cur.x + ((next.x - cur.x) / outLen) * r, y: cur.y + ((next.y - cur.y) / outLen) * r }
    d += ` L ${f(a.x)} ${f(a.y)} Q ${f(cur.x)} ${f(cur.y)} ${f(b.x)} ${f(b.y)}`
  }
  const last = points[points.length - 1]
  d += ` L ${f(last.x)} ${f(last.y)}`
  return d
}
