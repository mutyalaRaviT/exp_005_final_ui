import { describe, expect, it } from 'vitest'
import type { Edge, Node } from '@xyflow/react'
import { applyHighlight, matchingEdgeIds } from './edgeHighlight'
import type { FlowEdgeData, FlowNodeData } from './toFlow'

const node = (id: string, data: Partial<FlowNodeData>): Node<FlowNodeData> => ({ id, position: { x: 0, y: 0 }, data: { kind: 'file', label: id, ...data } })
const edge = (id: string, source: string, target: string, label?: string): Edge<FlowEdgeData> => ({ id, source, target, data: { points: [], label } })

const nodes = [
  node('a.sas', { kind: 'file', fileid: 'a.sas', label: 'a.sas' }),
  node('b.sas::b1', { kind: 'blockCluster', fileid: 'b.sas', label: 'data · b1' }),
  node('b.sas::b1:t1', { kind: 'occurrence', fileid: 'b.sas', label: 'work.t', blockId: 'b1' }),
  node('b.sas::b1:t2', { kind: 'occurrence', fileid: 'b.sas', label: 'work.u', blockId: 'b1' }),
  node('c.sas', { kind: 'file', fileid: 'c.sas', label: 'c.sas' }),
]
const edges = [
  edge('xe:a->t1', 'a.sas', 'b.sas::b1:t1', 'work.t'),
  edge('ie:b:0', 'b.sas::b1:t1', 'b.sas::b1:t2'),
  edge('xe:t2->c', 'b.sas::b1:t2', 'c.sas', 'work.u'),
]

describe('matchingEdgeIds', () => {
  it('matches a block row by table names', () => {
    expect([...matchingEdgeIds(nodes, edges, { src: 'work.t', dst: 'work.u', fileid: 'b.sas', level: 'block' })]).toEqual(['ie:b:0'])
  })
  it('matches a project row by file ids, including an edge that lands on a pill inside the destination file', () => {
    expect([...matchingEdgeIds(nodes, edges, { src: 'a.sas', dst: 'b.sas', fileid: 'a.sas', level: 'project' })]).toEqual(['xe:a->t1'])
    const collapsed = [node('a.sas', { fileid: 'a.sas' }), node('b.sas', { fileid: 'b.sas' })]
    expect([...matchingEdgeIds(collapsed, [edge('xe:a->b', 'a.sas', 'b.sas', 'work.t')], { src: 'a.sas', dst: 'b.sas', fileid: 'a.sas', level: 'project' })]).toEqual(['xe:a->b'])
  })
  it('falls back to the cross-file edge carrying the table when the file is collapsed', () => {
    const collapsed = [node('a.sas', { fileid: 'a.sas' }), node('b.sas', { fileid: 'b.sas' })]
    const es = [edge('xe:a->b', 'a.sas', 'b.sas', 'work.t')]
    expect([...matchingEdgeIds(collapsed, es, { src: 'raw.x', dst: 'work.t', fileid: 'b.sas', level: 'block' })]).toEqual(['xe:a->b'])
  })
})

describe('applyHighlight', () => {
  it('sets highlight on hits and clears it elsewhere, keeping untouched edges by identity', () => {
    const first = applyHighlight(edges, new Set(['ie:b:0']))
    expect(first[1].data?.highlight).toBe(true)
    expect(first[1].zIndex).toBe(1000)
    expect(first[0]).toBe(edges[0])
    const cleared = applyHighlight(first, new Set())
    expect(cleared[1].data?.highlight).toBe(false)
  })
})

import { GHOST_EDGE_ID, ghostForRow, withoutGhosts } from './edgeHighlight'

describe('ghostForRow', () => {
  const canvas = [
    { ...node('a.sas', { fileid: 'a.sas' }), style: { width: 140, height: 44 }, position: { x: 100, y: 200 } },
  ]
  it('adds a ghost node for a missing destination to the right of the source and a dashed edge', () => {
    const g = ghostForRow(canvas, { src: 'a.sas', dst: 'z.sas', fileid: 'a.sas', level: 'project', tables: ['work.t'] })!
    expect(g.nodes).toHaveLength(1)
    expect(g.nodes[0].id).toBe('ghost:z.sas')
    expect(g.nodes[0].position.x).toBeGreaterThan(240)
    expect(g.nodes[0].className).toBe('rf-ghost')
    expect(g.edge.id).toBe(GHOST_EDGE_ID)
    expect(g.edge.source).toBe('a.sas')
    expect(g.edge.target).toBe('ghost:z.sas')
    expect(g.edge.data?.ghost).toBe(true)
    expect(g.edge.data?.label).toBe('work.t')
    expect(g.edge.data?.points[0]).toEqual({ x: 240, y: 222 })
  })
  it('adds a ghost source to the left when the source is missing', () => {
    const g = ghostForRow(canvas, { src: 'y.sas', dst: 'a.sas', fileid: 'a.sas', level: 'project', tables: [] })!
    expect(g.nodes[0].id).toBe('ghost:y.sas')
    expect(g.nodes[0].position.x).toBeLessThan(100)
  })
  it('draws only an edge when both ends are on the canvas, and nothing when neither is', () => {
    const both = [...canvas, { ...node('b.sas', { fileid: 'b.sas' }), position: { x: 500, y: 200 } }]
    const g = ghostForRow(both, { src: 'a.sas', dst: 'b.sas', fileid: 'a.sas', level: 'project', tables: ['work.t'] })!
    expect(g.nodes).toHaveLength(0)
    expect(g.edge.target).toBe('b.sas')
    expect(ghostForRow(canvas, { src: 'p.sas', dst: 'q.sas', fileid: 'p.sas', level: 'project', tables: [] })).toBeNull()
  })
  it('withoutGhosts strips ghost ids', () => {
    expect(withoutGhosts([{ id: 'a' }, { id: 'ghost:x' }, { id: GHOST_EDGE_ID }])).toEqual([{ id: 'a' }])
  })
})

describe('ghostForRow with neither table drawn', () => {
  const canvas = [
    node('a.sas', { kind: 'file', fileid: 'a.sas', label: 'a.sas' }),
    node('b.sas::b1', { kind: 'blockCluster', fileid: 'b.sas', label: 'data · b1' }),
  ]
  it('anchors two ghost tables around the row\'s block cluster when it is drawn', () => {
    const g = ghostForRow(canvas, { src: 'raw.x', dst: 'work.t', fileid: 'b.sas', block_id: 'b1', level: 'block', tables: ['work.t'] })!
    expect(g.nodes.map((n) => n.id)).toEqual(['ghost:raw.x', 'ghost:work.t'])
    expect(g.nodes[0].position.x).toBeLessThan(0)
    expect(g.nodes[1].position.x).toBeGreaterThan(0)
    expect(g.edge.source).toBe('ghost:raw.x')
    expect(g.edge.target).toBe('ghost:work.t')
    expect(g.edge.data?.ghost).toBe(true)
  })
  it('falls back to the row\'s file when the block is not drawn', () => {
    const g = ghostForRow(canvas, { src: 'raw.x', dst: 'work.t', fileid: 'a.sas', block_id: 'zz', level: 'file', tables: [] })!
    expect(g.nodes.map((n) => n.id)).toEqual(['ghost:raw.x', 'ghost:work.t'])
  })
  it('is null when neither the tables nor the file are on the canvas', () => {
    expect(ghostForRow(canvas, { src: 'raw.x', dst: 'work.t', fileid: 'q.sas', block_id: null, level: 'file', tables: [] })).toBeNull()
  })
})
