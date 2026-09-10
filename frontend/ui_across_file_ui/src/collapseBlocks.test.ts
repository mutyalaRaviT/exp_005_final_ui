import { describe, expect, it } from 'vitest'
import { graph2Elements } from './graph2'
import { collapseBlocks } from './collapseBlocks'
import { hood3, detailLoader, detailBuilder, links3, LB1, BB1 } from './__fixtures__/graph2Data'
import type { FileDetail } from './api'

const details = new Map<string, FileDetail>([
  ['loader.sas', detailLoader],
  ['builder.sas', detailBuilder],
])
const expanded = new Set(['loader.sas', 'builder.sas'])
const loaderBlock = `loader.sas::${LB1}`
const builderBlock = `builder.sas::${BB1}`

describe('collapseBlocks', () => {
  const base = graph2Elements(hood3, expanded, details, links3)

  it('is the identity when nothing is collapsed', () => {
    expect(collapseBlocks(base, new Set())).toBe(base)
  })

  it('hides the occurrences of a collapsed block and marks the block', () => {
    const out = collapseBlocks(base, new Set([loaderBlock]))
    expect(out.some((e) => e.data.kind === 'occurrence' && e.data.parent === loaderBlock)).toBe(false)
    expect(out.find((e) => e.data.id === loaderBlock)?.data.collapsed).toBe(true)
    // other blocks keep their occurrences
    expect(out.some((e) => e.data.kind === 'occurrence' && e.data.parent === builderBlock)).toBe(true)
  })

  it('re-points cross-file edges to the collapsed block and drops the folded intra-block edge', () => {
    const out = collapseBlocks(base, new Set([loaderBlock]))
    const edges = out.filter((e) => e.data.source)
    const ids = new Set(out.filter((e) => !e.data.source).map((e) => e.data.id))
    for (const e of edges) {
      expect(ids.has(e.data.source!)).toBe(true)
      expect(ids.has(e.data.target!)).toBe(true)
    }
    const fromBlock = edges.filter((e) => e.data.source === loaderBlock)
    expect(fromBlock.length).toBeGreaterThan(0)
    expect(fromBlock[0].data.label).toContain('stage.accounts')
    // the loader's own raw.accounts -> stage.accounts edge folds into the block
    expect(edges.some((e) => e.data.source === loaderBlock && e.data.target === loaderBlock)).toBe(false)
  })

  it('merges edges that land on the same pair after folding', () => {
    const out = collapseBlocks(base, new Set([loaderBlock, builderBlock]))
    const edges = out.filter((e) => e.data.source)
    const pairs = edges.map((e) => `${e.data.source}->${e.data.target}`)
    expect(new Set(pairs).size).toBe(pairs.length)
  })
})
