import { describe, expect, it } from 'vitest'
import { graph2Elements, innerId, type BlockLink } from './graph2'
import type { FileDetail, Neighborhood } from './api'
import {
  hood3, detailLoader, detailBuilder, links3, LB1, BB1, BB2,
} from './__fixtures__/graph2Data'

const hood: Neighborhood = {
  nodes: [
    { id: 'a.sas', label: 'a.sas', folder: 'f', score: 0, cyclic: false },
    { id: 'b.sas', label: 'b.sas', folder: 'f', score: 1, cyclic: false },
  ],
  edges: [{ src: 'a.sas', dst: 'b.sas', tables: ['work.t', 'work.u'], level: 'project', provenance: 'inferred' }],
  story: [], order: {},
}
const B1 = 'b_1_aaaa1111'
const detailA: FileDetail = {
  fileid: 'a.sas', name: 'a.sas', folder: 'f', code: '',
  blocks: [{ id: B1, status: 'PARSED', reads: 1, writes: 1, line_start: 1, line_end: 1,
    occurrences: [
      { id: `${B1}:t_1`, name: 'raw.x', role: 'read' },
      { id: `${B1}:t_2`, name: 'work.t', role: 'write' },
    ] }],
  block_edges: [{ src: 'raw.x', dst: 'work.t', tables: ['work.t'], level: 'block',
    provenance: 'fact', src_ref: `${B1}:t_1`, dst_ref: `${B1}:t_2`, block: B1 }],
  file_edges: [], macro_calls: [], includes: [], missing_includes: [],
}
const links: BlockLink[] = [
  { src_file: 'a.sas', src_block: B1, src_ref: `${B1}:t_2`,
    dst_file: 'b.sas', dst_block: B1, dst_ref: `${B1}:t_1`, table: 'work.t' },
  { src_file: 'a.sas', src_block: B1, src_ref: `${B1}:t_2`,
    dst_file: 'b.sas', dst_block: B1, dst_ref: `${B1}:t_1`, table: 'work.u' },
]

describe('graph2Elements', () => {
  it('collapsed everywhere == v1 file graph', () => {
    const els = graph2Elements(hood, new Set(), new Map(), links)
    const nodes = els.filter((e) => !e.data.source)
    expect(nodes.map((n) => n.data.id).sort()).toEqual(['a.sas', 'b.sas'])
    const edges = els.filter((e) => e.data.source)
    expect(edges).toHaveLength(1)
    expect(edges[0].data.source).toBe('a.sas')
    expect(edges[0].data.label).toBe('work.t')
  })

  it('an expanded file becomes a namespaced cluster with blocks and tables', () => {
    const els = graph2Elements(hood, new Set(['a.sas']), new Map([['a.sas', detailA]]), links)
    const ids = els.filter((e) => !e.data.source).map((e) => e.data.id)
    expect(ids).toContain('a.sas')                        // now a fileCluster
    expect(ids).toContain(innerId('a.sas', B1))
    expect(ids).toContain(innerId('a.sas', `${B1}:t_2`))
    const cluster = els.find((e) => e.data.id === 'a.sas')!
    expect(cluster.data.kind).toBe('fileCluster')
    const block = els.find((e) => e.data.id === innerId('a.sas', B1))!
    expect(block.data.parent).toBe('a.sas')
  })

  it('cross-file edges re-point to the finest visible end and merge labels', () => {
    const els = graph2Elements(hood, new Set(['a.sas']), new Map([['a.sas', detailA]]), links)
    const cross = els.filter((e) => e.data.source && e.data.target === 'b.sas')
    expect(cross).toHaveLength(1)                          // two links merged
    expect(cross[0].data.source).toBe(innerId('a.sas', `${B1}:t_2`))
    expect(cross[0].data.label).toBe('work.t, work.u')
  })

  it('same block id in two expanded files never collides', () => {
    const detailB: FileDetail = { ...detailA, fileid: 'b.sas', name: 'b.sas' }
    const els = graph2Elements(hood, new Set(['a.sas', 'b.sas']),
      new Map([['a.sas', detailA], ['b.sas', detailB]]), links)
    const blockIds = els.filter((e) => e.data.kind === 'blockCluster').map((e) => e.data.id)
    expect(new Set(blockIds).size).toBe(blockIds.length)
    expect(blockIds).toContain(innerId('a.sas', B1))
    expect(blockIds).toContain(innerId('b.sas', B1))
  })

  it('intra-file fact edges render inside an expanded file', () => {
    const els = graph2Elements(hood, new Set(['a.sas']), new Map([['a.sas', detailA]]), links)
    const intra = els.find((e) => e.data.source === innerId('a.sas', `${B1}:t_1`))
    expect(intra?.data.target).toBe(innerId('a.sas', `${B1}:t_2`))
    expect(intra?.data.fact).toBe(true)
  })
})

// The V2-6 story fixture (loader -> builder -> report): confirms the parts
// the stories themselves can't observe through the real browser's canvas —
// the macro cluster wraps only its block, and two same-pair links merge
// into one labeled cross edge — using the exact data the stories render.
describe('graph2Elements with the V2-6 story fixture (loader -> builder -> report)', () => {
  it('report.sas has no detail, so it stays a plain collapsed file node', () => {
    const els = graph2Elements(hood3, new Set(['loader.sas', 'builder.sas']),
      new Map([['loader.sas', detailLoader], ['builder.sas', detailBuilder]]), links3)
    const report = els.find((e) => e.data.id === 'report.sas')!
    expect(report.data.kind).toBe('file')
  })

  it('%load_dims wraps only BB1; BB2 stays a direct child of the fileCluster', () => {
    const els = graph2Elements(hood3, new Set(['builder.sas']),
      new Map([['builder.sas', detailBuilder]]), links3)
    const macro = els.find((e) => e.data.kind === 'macro')!
    expect(macro.data.label).toBe('%load_dims #1')
    expect(macro.data.parent).toBe('builder.sas')
    const bb1 = els.find((e) => e.data.id === innerId('builder.sas', BB1))!
    expect(bb1.data.parent).toBe(macro.data.id)
    const bb2 = els.find((e) => e.data.id === innerId('builder.sas', BB2))!
    expect(bb2.data.parent).toBe('builder.sas')
  })

  it('two same-pair links merge into one block-to-block edge once both files expand', () => {
    const els = graph2Elements(hood3, new Set(['loader.sas', 'builder.sas']),
      new Map([['loader.sas', detailLoader], ['builder.sas', detailBuilder]]), links3)
    const cross = els.filter((e) =>
      e.data.source === innerId('loader.sas', `${LB1}:t_2`) &&
      e.data.target === innerId('builder.sas', `${BB1}:t_1`))
    expect(cross).toHaveLength(1)
    expect(cross[0].data.label).toBe('stage.accounts, stage.audit')
  })

  it('the builder -> report link stays a separate, unmerged file-level edge', () => {
    const els = graph2Elements(hood3, new Set(['builder.sas']),
      new Map([['builder.sas', detailBuilder]]), links3)
    const toReport = els.find((e) => e.data.target === 'report.sas')!
    expect(toReport.data.source).toBe(innerId('builder.sas', `${BB2}:t_2`))
    expect(toReport.data.label).toBe('work.report_base')
  })
})
