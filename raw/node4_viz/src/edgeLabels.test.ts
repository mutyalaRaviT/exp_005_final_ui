// The smart edge-label placer: a pure stand-in for ELK's edge-label
// placement (cytoscape-elk never hands labels to ELK). Each label gets a
// stable pseudo-random spot 50-80% along its edge, is pushed to a side of
// the line (above/below for horizontal-ish edges, left/right for
// vertical-ish), and placements greedily avoid the boxes already placed.
import { describe, expect, it } from 'vitest'
import { computeEdgeLabelPlacements, type EdgeLabelInput } from './edgeLabels'

function horizontalEdge(id: string, y = 100): EdgeLabelInput {
  return { id, label: 'work.accounts', sx: 0, sy: y, tx: 400, ty: y }
}

describe('computeEdgeLabelPlacements', () => {
  it('places every label between 50% and 80% along its edge', () => {
    const edges = Array.from({ length: 20 }, (_, i) =>
      horizontalEdge(`e${i}`, i * 40),
    )
    const placements = computeEdgeLabelPlacements(edges)
    expect(placements).toHaveLength(edges.length)
    for (const p of placements) {
      expect(p.t).toBeGreaterThanOrEqual(0.5)
      expect(p.t).toBeLessThanOrEqual(0.8)
      expect(p.offset).toBeCloseTo(p.t * 400, 5)
    }
  })

  it('is deterministic: the same edges always get the same placements', () => {
    const edges = [horizontalEdge('e1'), horizontalEdge('e2', 50)]
    const first = computeEdgeLabelPlacements(edges)
    expect(first).toHaveLength(2)
    expect(computeEdgeLabelPlacements(edges)).toEqual(first)
  })

  it('pushes labels above or below a horizontal edge', () => {
    const [p] = computeEdgeLabelPlacements([horizontalEdge('e1')])
    expect(['above', 'below']).toContain(p.side)
    expect(p.marginX).toBe(0)
    expect(p.marginY).not.toBe(0)
  })

  it('pushes labels beside a vertical edge', () => {
    const [p] = computeEdgeLabelPlacements([
      { id: 'v1', label: 'work.accounts', sx: 100, sy: 0, tx: 100, ty: 400 },
    ])
    expect(['left', 'right']).toContain(p.side)
    expect(p.marginY).toBe(0)
    expect(p.marginX).not.toBe(0)
  })

  it('keeps identical stacked edges from overlapping label boxes', () => {
    // three edges with the SAME geometry and label — the worst case from
    // the live graph (stacked work.accounts labels)
    const edges = ['a', 'b', 'c'].map((id) => horizontalEdge(id))
    const boxes = computeEdgeLabelPlacements(edges).map((p) => p.box)
    expect(boxes).toHaveLength(3)
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i]
        const b = boxes[j]
        const overlaps =
          a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2
        expect(overlaps, `boxes ${i} and ${j} overlap`).toBe(false)
      }
    }
  })

  it('measures the offset along a taxi polyline, not the straight line', () => {
    // right 40, down 200, right 360 — path length 600 vs straight ~447
    const path = [
      { x: 0, y: 0 },
      { x: 40, y: 0 },
      { x: 40, y: 200 },
      { x: 400, y: 200 },
    ]
    const [p] = computeEdgeLabelPlacements([
      { id: 't1', label: 'work.accounts', sx: 0, sy: 0, tx: 400, ty: 200, path },
    ])
    expect(p.offset).toBeCloseTo(p.t * 600, 5)
  })

  it('sides with the local segment: a label on a vertical run goes beside it', () => {
    // the long middle drop guarantees every t in [0.5, 0.8] lands on it
    const path = [
      { x: 0, y: 0 },
      { x: 40, y: 0 },
      { x: 40, y: 2000 },
      { x: 100, y: 2000 },
    ]
    const [p] = computeEdgeLabelPlacements([
      { id: 'v9', label: 'work.accounts', sx: 0, sy: 0, tx: 100, ty: 2000, path },
    ])
    expect(['left', 'right']).toContain(p.side)
    // the box hangs off the true path point: x pinned beside the run at
    // x=40, y exactly at the distance the offset walked down the drop
    const d = p.t * 2100
    expect((p.box.y1 + p.box.y2) / 2).toBeCloseTo(d - 40, 5)
  })

  it('prefers a spot on a horizontal run over the shared vertical trunk', () => {
    // t in [0.5, 0.8] spans the trunk (d 40-440) AND the final horizontal
    // approach (d 440-800) — an uncrowded label should take the horizontal
    const path = [
      { x: 0, y: 0 },
      { x: 40, y: 0 },
      { x: 40, y: 400 },
      { x: 400, y: 400 },
    ]
    // these ids seed a t whose first candidate lands ON the vertical trunk
    // (hash % 1024 < ~0.16*1024) — only a horizontal preference moves them
    for (const id of ['e2', 'e7', 'e13']) {
      const placed = computeEdgeLabelPlacements([
        { id, label: 'work.accounts', sx: 0, sy: 0, tx: 400, ty: 400, path },
      ])
      expect(['above', 'below']).toContain(placed[0].side)
    }
  })

  it('returns nothing for edges without a label', () => {
    expect(
      computeEdgeLabelPlacements([
        { id: 'e1', label: '', sx: 0, sy: 0, tx: 100, ty: 0 },
      ]),
    ).toEqual([])
  })
})
