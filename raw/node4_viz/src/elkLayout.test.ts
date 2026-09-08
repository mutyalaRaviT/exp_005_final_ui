import { describe, expect, it } from 'vitest'
import { graph2Elements } from './graph2'
import { elkLayout, estimateSize, rootOptions } from './elkLayout'
import { DEFAULT_SETTINGS } from './layoutSettings'
import { hood3, detailLoader, detailBuilder, links3 } from './__fixtures__/graph2Data'
import type { FileDetail } from './api'

const details = new Map<string, FileDetail>([
  ['loader.sas', detailLoader],
  ['builder.sas', detailBuilder],
])

describe('estimateSize', () => {
  it('sizes a file node by its label with a floor of 140', () => {
    expect(estimateSize('file', 'a.sas')).toEqual({ width: 140, height: 44 })
    expect(estimateSize('file', '04_build_accounts.sas')).toEqual({ width: 7 * 21 + 40, height: 44 })
    expect(estimateSize('occurrence', 'work.t')).toEqual({ width: 7 * 6 + 24, height: 26 })
  })
})

describe('elkLayout', () => {
  it('lays out collapsed files left to right with routed edges', async () => {
    const out = await elkLayout(graph2Elements(hood3, new Set(), details, links3))
    expect(out.nodes.map((n) => n.id).sort()).toEqual(['builder.sas', 'loader.sas', 'report.sas'])
    const byId = new Map(out.nodes.map((n) => [n.id, n]))
    expect(byId.get('loader.sas')!.x).toBeLessThan(byId.get('builder.sas')!.x)
    expect(byId.get('builder.sas')!.x).toBeLessThan(byId.get('report.sas')!.x)
    expect(out.edges).toHaveLength(2)
    for (const e of out.edges) expect(e.points.length).toBeGreaterThanOrEqual(2)
  })

  it('keeps every child inside its parent box and parents before children', async () => {
    const expanded = new Set(['loader.sas', 'builder.sas'])
    const out = await elkLayout(graph2Elements(hood3, expanded, details, links3))
    const byId = new Map(out.nodes.map((n) => [n.id, n]))
    const seen = new Set<string>()
    for (const n of out.nodes) {
      if (n.parent) {
        expect(seen.has(n.parent)).toBe(true)
        const p = byId.get(n.parent)!
        expect(n.x).toBeGreaterThanOrEqual(p.x)
        expect(n.y).toBeGreaterThanOrEqual(p.y)
        expect(n.x + n.width).toBeLessThanOrEqual(p.x + p.width + 0.01)
        expect(n.y + n.height).toBeLessThanOrEqual(p.y + p.height + 0.01)
      }
      seen.add(n.id)
    }
    expect(out.nodes.some((n) => n.kind === 'occurrence')).toBe(true)
    expect(out.nodes.some((n) => n.kind === 'macro')).toBe(true)
  })

  it('routes cross-file edges to the occurrence endpoints and keeps labels', async () => {
    const expanded = new Set(['loader.sas', 'builder.sas'])
    const out = await elkLayout(graph2Elements(hood3, expanded, details, links3))
    const byId = new Map(out.nodes.map((n) => [n.id, n]))
    const cross = out.edges.find((e) => e.id.startsWith('xe:'))!
    expect(byId.get(cross.source)!.kind).toBe('occurrence')
    // links3 has two loader->builder rows on the same (src_ref, dst_ref) pair
    // (stage.accounts, stage.audit); graph2.ts's mergeLabel joins them with
    // ", " once both files are expanded — see links3's own comment.
    expect(cross.label).toBe('stage.accounts, stage.audit')
    // the first point starts at the source box's right edge (within ELK rounding)
    const s = byId.get(cross.source)!
    expect(Math.abs(cross.points[0].x - (s.x + s.width))).toBeLessThan(2)
  })

  it('returns an empty layout for no elements', async () => {
    expect(await elkLayout([])).toEqual({ nodes: [], edges: [] })
  })

  it('honours the layout settings in the ELK root options', () => {
    const on = rootOptions({ ...DEFAULT_SETTINGS, mergeEdges: true, straighten: true, elkLabels: true, keepArrangement: true, followRunOrder: true, thoroughness: 12 })
    expect(on['elk.layered.mergeEdges']).toBe('true')
    expect(on['elk.layered.unnecessaryBendpoints']).toBe('true')
    expect(on['elk.edgeLabels.placement']).toBe('CENTER')
    expect(on['elk.layered.crossingMinimization.semiInteractive']).toBe('true')
    expect(on['elk.layered.considerModelOrder.strategy']).toBe('NODES_AND_EDGES')
    expect(on['elk.layered.thoroughness']).toBe('12')
    const off = rootOptions({ ...DEFAULT_SETTINGS, mergeEdges: false, straighten: false, elkLabels: false, keepArrangement: false, followRunOrder: false, stableOrder: false })
    for (const k of ['elk.layered.mergeEdges', 'elk.layered.unnecessaryBendpoints', 'elk.edgeLabels.placement', 'elk.layered.crossingMinimization.semiInteractive', 'elk.layered.considerModelOrder.strategy'])
      expect(off[k]).toBeUndefined()
  })

  it('with side ports every edge still starts on its source box and ends on its target box', async () => {
    const out = await elkLayout(graph2Elements(hood3, new Set(), details, links3), { settings: { ...DEFAULT_SETTINGS, sidePorts: true, mergeEdges: true } })
    const byId = new Map(out.nodes.map((n) => [n.id, n]))
    for (const e of out.edges) {
      const s = byId.get(e.source)!, t = byId.get(e.target)!
      expect(Math.abs(e.points[0].x - (s.x + s.width))).toBeLessThan(2)
      expect(Math.abs(e.points[e.points.length - 1].x - t.x)).toBeLessThan(2)
    }
  })

  it('ELK places labels when asked', async () => {
    const out = await elkLayout(graph2Elements(hood3, new Set(), details, links3), { settings: { ...DEFAULT_SETTINGS, elkLabels: true } })
    const labelled = out.edges.filter((e) => e.label)
    expect(labelled.length).toBeGreaterThan(0)
    for (const e of labelled) expect(e.labelAt).toBeDefined()
  })

  it('follows the run order when asked and keeps a dragged order when asked', async () => {
    const elements = graph2Elements(hood3, new Set(), details, links3)
    const order = new Map([['loader.sas', 0], ['builder.sas', 1], ['report.sas', 2]])
    const a = await elkLayout(elements, { settings: { ...DEFAULT_SETTINGS, stableOrder: false, followRunOrder: true }, order })
    expect(a.nodes.map((n) => n.id)).toEqual(['loader.sas', 'builder.sas', 'report.sas'])
    // semi-interactive: the user dragged report above loader in the same layer set; layout must not throw and keeps all nodes
    const positions = new Map(a.nodes.map((n) => [n.id, { x: n.x, y: n.id === 'report.sas' ? -200 : n.y }]))
    const b = await elkLayout(elements, { settings: { ...DEFAULT_SETTINGS, keepArrangement: true }, positions })
    expect(b.nodes).toHaveLength(3)
    expect(b.edges).toHaveLength(2)
  })

  it('maps the placement group onto ELK options', () => {
    const o = rootOptions({ ...DEFAULT_SETTINGS, layering: 'COFFMAN_GRAHAM', nodePlacement: 'BRANDES_KOEPF', greedySwitch: true, nodePromotion: true, compaction: true })
    expect(o['elk.layered.layering.strategy']).toBe('COFFMAN_GRAHAM')
    expect(o['elk.layered.nodePlacement.strategy']).toBe('BRANDES_KOEPF')
    expect(o['elk.layered.crossingMinimization.greedySwitch.type']).toBe('TWO_SIDED')
    expect(o['elk.layered.layering.nodePromotion.strategy']).toBe('NIKOLOV_IMPROVED')
    expect(o['elk.layered.compaction.postCompaction.strategy']).toBe('EDGE_LENGTH')
  })

  it('every layering x placement pair lays out the fixture without throwing', async () => {
    const elements = graph2Elements(hood3, new Set(['builder.sas']), details, links3)
    for (const layering of ['NETWORK_SIMPLEX', 'LONGEST_PATH', 'COFFMAN_GRAHAM', 'MIN_WIDTH'] as const)
      for (const nodePlacement of ['NETWORK_SIMPLEX', 'BRANDES_KOEPF', 'LINEAR_SEGMENTS', 'SIMPLE'] as const) {
        const out = await elkLayout(elements, { settings: { ...DEFAULT_SETTINGS, layering, nodePlacement, greedySwitch: true, compaction: true } })
        expect(out.nodes.length).toBeGreaterThan(3)
        for (const e of out.edges) expect(e.points.length).toBeGreaterThanOrEqual(2)
      }
  })

  it('stable order keeps files in file-name order whether or not one is expanded', async () => {
    const settings = { ...DEFAULT_SETTINGS, stableOrder: true, followRunOrder: false }
    const collapsed = await elkLayout(graph2Elements(hood3, new Set(), details, links3), { settings })
    const expanded = await elkLayout(graph2Elements(hood3, new Set(['builder.sas']), details, links3), { settings })
    const top = (out: Awaited<ReturnType<typeof elkLayout>>) => out.nodes.filter((n) => !n.parent).map((n) => n.id)
    expect(top(collapsed)).toEqual(['builder.sas', 'loader.sas', 'report.sas'])
    expect(top(expanded)).toEqual(['builder.sas', 'loader.sas', 'report.sas'])
    const o = rootOptions(settings)
    expect(o['elk.layered.crossingMinimization.forceNodeModelOrder']).toBe('true')
  })
})
