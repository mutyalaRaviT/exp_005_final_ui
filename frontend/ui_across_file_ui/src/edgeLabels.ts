// Smart edge-label placement: a pure stand-in for ELK's edge-label placer.
//
// Every label gets a stable pseudo-random spot along its edge — always
// within [minT, maxT] (default 50%-80%) so labels never crowd the node they
// leave — and is pushed off the line: above/below for horizontal-ish edges,
// left/right for vertical-ish ones. Placement is greedy: each label tries
// several spots x both sides and takes the first that does not collide with
// a box already placed, which is what keeps stacked same-name edges (the
// work.accounts pile-up) readable.

export interface EdgeLabelInput {
  id: string
  label: string
  /** rendered source and target endpoint positions */
  sx: number
  sy: number
  tx: number
  ty: number
  /** the rendered polyline (e.g. the taxi route). Offsets are measured
   *  along it — omitted, the straight source→target line is used. */
  path?: Array<{ x: number; y: number }>
}

export interface LabelBox {
  x1: number
  y1: number
  x2: number
  y2: number
}

export interface EdgeLabelPlacement {
  id: string
  /** fraction of the edge the label sits at, always within [minT, maxT] */
  t: number
  /** px along the edge from the source — feeds the renderer's text offset */
  offset: number
  side: 'above' | 'below' | 'left' | 'right'
  /** px push off the line — feeds the renderer's text margin x/y */
  marginX: number
  marginY: number
  /** the estimated label box, used for collision avoidance */
  box: LabelBox
}

export interface EdgeLabelOptions {
  minT?: number
  maxT?: number
  /** estimated px per label character (the graph uses a 9px font) */
  charW?: number
  /** estimated label height in px */
  lineH?: number
  /** px of clearance between the line and the label box */
  gap?: number
}

/** deterministic 32-bit hash (FNV-1a) so an edge keeps its spot forever */
function hash(id: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < id.length; i++) {
    h ^= id.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

function overlaps(a: LabelBox, b: LabelBox): boolean {
  return a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2
}

const T_STEPS = 8
/** golden-ratio stride spreads the candidate spots across [minT, maxT] */
const T_STRIDE = 0.618

export function computeEdgeLabelPlacements(
  edges: EdgeLabelInput[],
  options: EdgeLabelOptions = {},
): EdgeLabelPlacement[] {
  const { minT = 0.5, maxT = 0.8, charW = 7, lineH = 14, gap = 6 } = options
  const span = maxT - minT
  const placed: LabelBox[] = []
  const out: EdgeLabelPlacement[] = []

  for (const e of edges) {
    // the polyline the offset walks — the renderer's source-text-offset
    // follows the rendered path, so the collision model must too
    const pts =
      e.path && e.path.length >= 2
        ? e.path
        : [
            { x: e.sx, y: e.sy },
            { x: e.tx, y: e.ty },
          ]
    const segs: { x: number; y: number; dx: number; dy: number; len: number }[] = []
    let length = 0
    for (let i = 1; i < pts.length; i++) {
      const dx = pts[i].x - pts[i - 1].x
      const dy = pts[i].y - pts[i - 1].y
      const len = Math.hypot(dx, dy)
      if (len === 0) continue
      segs.push({ x: pts[i - 1].x, y: pts[i - 1].y, dx, dy, len })
      length += len
    }
    if (!e.label || length === 0) continue

    /** the point `d` px along the path, and whether that run is horizontal */
    const pointAt = (d: number) => {
      let rest = d
      for (const s of segs) {
        if (rest <= s.len) {
          const f = rest / s.len
          return {
            x: s.x + f * s.dx,
            y: s.y + f * s.dy,
            horizontal: Math.abs(s.dx) >= Math.abs(s.dy),
          }
        }
        rest -= s.len
      }
      const last = segs[segs.length - 1]
      return { x: last.x + last.dx, y: last.y + last.dy, horizontal: Math.abs(last.dx) >= Math.abs(last.dy) }
    }

    const h = hash(e.id)
    const t0 = minT + (span * (h % 1024)) / 1024
    const halfW = (e.label.length * charW) / 2
    const halfH = lineH / 2
    // a full row pushes the label one label-height (or -width) further out,
    // like ELK stacking label rows
    const rowStepX = halfW * 2 + 4
    const rowStepY = lineH + 2

    // which side to try first comes from the hash, so stacked edges
    // naturally alternate instead of all fighting for the same side
    const sidesFor = (horizontal: boolean): EdgeLabelPlacement['side'][] =>
      horizontal
        ? h & 1024
          ? ['above', 'below']
          : ['below', 'above']
        : h & 1024
          ? ['left', 'right']
          : ['right', 'left']

    const candidate = (t: number, side: EdgeLabelPlacement['side'], row: number) => {
      const pt = pointAt(t * length)
      const outX = gap + halfW + row * rowStepX
      const outY = gap + halfH + row * rowStepY
      const marginX = side === 'left' ? -outX : side === 'right' ? outX : 0
      const marginY = side === 'above' ? -outY : side === 'below' ? outY : 0
      const cx = pt.x + marginX
      const cy = pt.y + marginY
      const box: LabelBox = {
        x1: cx - halfW,
        y1: cy - halfH,
        x2: cx + halfW,
        y2: cy + halfH,
      }
      return { id: e.id, t, offset: t * length, side, marginX, marginY, box }
    }

    // candidate spots in stride order, but spots on horizontal runs first:
    // a label beside the shared vertical trunk is the cluttered case, so it
    // is only used once the horizontal approaches are taken
    const ts = Array.from(
      { length: T_STEPS },
      (_, i) => minT + ((t0 - minT + i * T_STRIDE * span) % span),
    )
    const orderedTs = [
      ...ts.filter((t) => pointAt(t * length).horizontal),
      ...ts.filter((t) => !pointAt(t * length).horizontal),
    ]

    let chosen: EdgeLabelPlacement | null = null
    for (let row = 0; row < 3 && !chosen; row++) {
      for (const t of orderedTs) {
        if (chosen) break
        for (const side of sidesFor(pointAt(t * length).horizontal)) {
          const c = candidate(t, side, row)
          if (!placed.some((b) => overlaps(b, c.box))) {
            chosen = c
            break
          }
        }
      }
    }
    // everything collides (a very dense pile): keep the seeded spot anyway
    chosen ??= candidate(t0, sidesFor(pointAt(t0 * length).horizontal)[0], 0)
    placed.push(chosen.box)
    out.push(chosen)
  }
  return out
}
