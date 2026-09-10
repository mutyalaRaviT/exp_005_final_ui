import { describe, expect, it } from 'vitest'
import { toFlow, type FlowContext } from './toFlow'
import type { LaidOut } from './elkLayout'

const laid: LaidOut = {
  nodes: [
    { id: 'a.sas', kind: 'fileCluster', label: 'a.sas', x: 10, y: 20, width: 300, height: 200, fileid: 'a.sas' },
    { id: 'a.sas::b_1', kind: 'blockCluster', label: 'data · b_1', parent: 'a.sas', x: 30, y: 60, width: 200, height: 100, fileid: 'a.sas' },
    { id: 'a.sas::b_1:t_1', kind: 'occurrence', label: 'work.t', parent: 'a.sas::b_1', x: 50, y: 100, width: 66, height: 26, fileid: 'a.sas', blockId: 'b_1' },
    { id: 'b.sas', kind: 'file', label: 'b.sas\n#2', x: 400, y: 20, width: 140, height: 44, fileid: 'b.sas' },
  ],
  edges: [
    { id: 'xe:a.sas::b_1:t_1->b.sas', source: 'a.sas::b_1:t_1', target: 'b.sas', label: 'work.t', points: [{ x: 116, y: 113 }, { x: 400, y: 42 }] },
  ],
}
const ctx: FlowContext = {
  roles: new Map([['a.sas', 'up'], ['b.sas', 'seed']]),
  scores: new Map([['a.sas', 0], ['b.sas', 2]]),
  occRoles: new Map([['a.sas::b_1:t_1', 'write']]),
  expanded: new Set(['a.sas']),
}

describe('toFlow', () => {
  const { nodes, edges } = toFlow(laid, ctx)
  it('keeps parents before children and sets parentId', () => {
    expect(nodes.map((n) => n.id)).toEqual(['a.sas', 'a.sas::b_1', 'a.sas::b_1:t_1', 'b.sas'])
    expect(nodes[1].parentId).toBe('a.sas')
    expect(nodes[2].parentId).toBe('a.sas::b_1')
    expect(nodes[3].parentId).toBeUndefined()
  })
  it('positions children relative to their parent', () => {
    expect(nodes[0].position).toEqual({ x: 10, y: 20 })
    expect(nodes[1].position).toEqual({ x: 20, y: 40 })
    expect(nodes[2].position).toEqual({ x: 20, y: 40 })
  })
  it('maps kinds to node types and carries sizes, roles and scores', () => {
    expect(nodes.map((n) => n.type)).toEqual(['cluster', 'cluster', 'occurrence', 'file'])
    expect(nodes[1].extent).toBe('parent')
    expect(nodes[0].extent).toBeUndefined()
    expect(nodes[0].style).toEqual({ width: 300, height: 200 })
    expect(nodes[3].data.role).toBe('seed')
    expect(nodes[3].data.score).toBe(2)
    expect(nodes[3].data.label).toBe('b.sas')
    expect(nodes[2].data.occRole).toBe('write')
    expect(nodes[0].data.expanded).toBe(true)
  })
  it('emits elk edges with points and label', () => {
    expect(edges).toHaveLength(1)
    expect(edges[0].type).toBe('elk')
    expect(edges[0].source).toBe('a.sas::b_1:t_1')
    expect(edges[0].data?.points).toHaveLength(2)
    expect(edges[0].data?.label).toBe('work.t')
  })
})

import { anchorsOf } from './toFlow'

describe('anchorsOf', () => {
  it('uses the boxes, not the route ends, so a top-exit route is not mistaken for a drag', () => {
    const s = { id: 's', kind: 'occurrence' as const, label: 's', x: 100, y: 200, width: 120, height: 26 }
    const t = { id: 't', kind: 'occurrence' as const, label: 't', x: 500, y: 40, width: 120, height: 26 }
    const route = [{ x: 160, y: 200 }, { x: 160, y: 53 }, { x: 500, y: 53 }] // leaves through s's top
    expect(anchorsOf(s, t, route)).toEqual({ sx: 220, sy: 213, tx: 500, ty: 53 })
    expect(anchorsOf(undefined, undefined, route)).toEqual({ sx: 160, sy: 200, tx: 500, ty: 53 })
  })
})
