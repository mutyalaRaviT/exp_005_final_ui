import { describe, expect, it, vi } from 'vitest'
import type { LaidOut } from './elkLayout'
import { applyHola, clipStart, holaLayout, tidy, topLevelGraph, topOf } from './holaLayout'

// file A (with pill a1 inside), file B (pill b1 inside), file C (plain box)
const laid: LaidOut = {
  nodes: [
    { id: 'A', kind: 'fileCluster', label: 'A', x: 0, y: 0, width: 200, height: 100 },
    { id: 'a1', kind: 'occurrence', label: 'a1', parent: 'A', x: 20, y: 40, width: 80, height: 26 },
    { id: 'B', kind: 'fileCluster', label: 'B', x: 400, y: 0, width: 200, height: 100 },
    { id: 'b1', kind: 'occurrence', label: 'b1', parent: 'B', x: 420, y: 40, width: 80, height: 26 },
    { id: 'C', kind: 'file', label: 'C', x: 800, y: 0, width: 160, height: 44 },
  ],
  edges: [
    { id: 'e1', source: 'a1', target: 'b1', points: [{ x: 100, y: 53 }, { x: 420, y: 53 }] },
    { id: 'e2', source: 'B', target: 'C', points: [{ x: 600, y: 50 }, { x: 800, y: 22 }] },
    { id: 'e3', source: 'a1', target: 'A', points: [{ x: 100, y: 53 }, { x: 0, y: 50 }] },
  ],
}

describe('holaLayout', () => {
  it('lifts edges to the top-level boxes and sends only those boxes', () => {
    expect(topOf(laid.nodes).get('b1')).toBe('B')
    const req = topLevelGraph(laid)
    expect(req.nodes.map((n) => n.id)).toEqual(['A', 'B', 'C'])
    expect(req.edges).toEqual([
      { id: 'e1', source: 'A', target: 'B' },
      { id: 'e2', source: 'B', target: 'C' },
      { id: 'e3', source: 'A', target: 'A' },
    ])
  })
  it('clips a centre-to-centre route to the box border and tidies straight runs', () => {
    const r = { x: 0, y: 0, width: 200, height: 100 }
    expect(clipStart([{ x: 100, y: 50 }, { x: 300, y: 50 }], r)).toEqual([{ x: 200, y: 50 }, { x: 300, y: 50 }])
    expect(clipStart([{ x: 100, y: 50 }, { x: 100, y: 300 }, { x: 500, y: 300 }], r)).toEqual([{ x: 100, y: 100 }, { x: 100, y: 300 }, { x: 500, y: 300 }])
    expect(tidy([{ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 5, y: 0 }, { x: 9, y: 0 }, { x: 9, y: 4 }])).toEqual([{ x: 0, y: 0 }, { x: 9, y: 0 }, { x: 9, y: 4 }])
  })
  it('moves whole subtrees, stitches pill edges to the HOLA route, keeps in-box edges', () => {
    const out = applyHola(laid, {
      // HOLA put B below A and C to the right of B
      nodes: [
        { id: 'A', x: 0, y: 0, width: 200, height: 100 },
        { id: 'B', x: 0, y: 300, width: 200, height: 100 },
        { id: 'C', x: 500, y: 300, width: 160, height: 44 },
      ],
      edges: [
        { id: 'e1', points: [{ x: 100, y: 50 }, { x: 100, y: 350 }] },
        { id: 'e2', points: [{ x: 100, y: 350 }, { x: 580, y: 350 }, { x: 580, y: 322 }] },
        { id: 'e3', points: [] },
      ],
    })
    const at = (id: string) => out.nodes.find((n) => n.id === id)!
    expect(at('B')).toMatchObject({ x: 0, y: 300 })
    expect(at('b1')).toMatchObject({ x: 20, y: 340 }) // moved with its parent
    const e1 = out.edges.find((e) => e.id === 'e1')!
    // pill a1 out-port -> across to the route's x -> down the border crossing -> into B -> across to b1's in-port
    // (the two border crossings sit on the same vertical run, so tidy folds them away)
    expect(e1.points).toEqual([{ x: 100, y: 53 }, { x: 100, y: 353 }, { x: 20, y: 353 }])
    const e2 = out.edges.find((e) => e.id === 'e2')!
    expect(e2.points[0]).toEqual({ x: 200, y: 350 })
    expect(e2.points[e2.points.length - 1]).toEqual({ x: 580, y: 344 })
    const e3 = out.edges.find((e) => e.id === 'e3')!
    expect(e3.points).toEqual([{ x: 100, y: 53 }, { x: 0, y: 50 }]) // A did not move
  })
  it('explains a missing sidecar and passes warnings through', async () => {
    const dead = vi.fn().mockRejectedValue(new Error('ECONNREFUSED'))
    await expect(holaLayout(laid, dead as unknown as typeof fetch)).rejects.toThrow(/sidecar not reachable/)
    const ok = vi.fn().mockResolvedValue(new Response(JSON.stringify({ nodes: [], edges: [], warnings: ['w'] }), { status: 200 }))
    const r = await holaLayout(laid, ok as unknown as typeof fetch)
    expect(r.warnings).toEqual(['w'])
    expect(ok.mock.calls[0][0]).toBe('/hola/layout')
  })
})
