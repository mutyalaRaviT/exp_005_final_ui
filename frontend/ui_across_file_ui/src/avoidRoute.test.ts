import { describe, expect, it } from 'vitest'
import { obstacles, routingGraph } from './avoidRoute'
import type { LaidOut } from './elkLayout'

const laid: LaidOut = {
  nodes: [
    { id: 'a.sas', kind: 'fileCluster', label: 'a.sas', x: 0, y: 0, width: 300, height: 200 },
    { id: 'a.sas::b1', kind: 'blockCluster', label: 'data · b1', parent: 'a.sas', x: 20, y: 40, width: 200, height: 100 },
    { id: 'a.sas::b1:t1', kind: 'occurrence', label: 'work.t', parent: 'a.sas::b1', x: 40, y: 80, width: 66, height: 26 },
    { id: 'b.sas', kind: 'file', label: 'b.sas', x: 400, y: 0, width: 140, height: 44 },
  ],
  edges: [
    { id: 'e1', source: 'a.sas::b1:t1', target: 'b.sas', label: 'work.t', points: [{ x: 106, y: 93 }, { x: 400, y: 22 }] },
    { id: 'e2', source: 'a.sas', target: 'b.sas', points: [{ x: 300, y: 100 }, { x: 400, y: 22 }] },
  ],
}

describe('avoidRoute (pure parts)', () => {
  it('treats only leaf boxes as obstacles', () => {
    expect(obstacles(laid.nodes).map((n) => n.id)).toEqual(['a.sas::b1:t1', 'b.sas'])
  })
  it('builds a flat absolute graph and drops edges that end on a container', () => {
    const g = routingGraph(laid.nodes, laid.edges)
    expect(g.children.map((c) => c.id)).toEqual(['a.sas::b1:t1', 'b.sas'])
    expect(g.children[0]).toEqual({ id: 'a.sas::b1:t1', x: 40, y: 80, width: 66, height: 26 })
    expect(g.edges.map((e) => e.id)).toEqual(['e1'])
  })
})
