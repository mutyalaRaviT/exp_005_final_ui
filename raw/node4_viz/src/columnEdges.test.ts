import { describe, expect, it } from 'vitest'
import { columnEdges } from './columnEdges'
import { openTables } from './openTables'
import { graph2Elements } from './graph2'
import type { FileDetail, Neighborhood } from './api'
import detail14 from './__fixtures__/team_finance/file/sas__raw__14_large_txn_report.sas.json'

const d14 = detail14 as unknown as FileDetail
const F = d14.fileid, B = d14.blocks[0].id
const hood: Neighborhood = { nodes: [{ id: F, label: d14.name, folder: d14.folder, score: 1, cyclic: false }], edges: [], story: [], order: {} }
const details = new Map([[F, d14]])
const base = graph2Elements(hood, new Set([F]), details, [])

describe('columnEdges', () => {
  it('nothing when fewer than two tables are open', () => {
    const els = openTables(base, new Set([`${F}::${B}:t_3`]), details)
    expect(columnEdges(els, details)).toBe(els)
  })
  it('one edge per column flow, landing on column handles; carried has no label, the why rides along', () => {
    const els = openTables(base, new Set([`${F}::${B}:t_1`, `${F}::${B}:t_3`]), details)
    const ce = columnEdges(els, details).filter((e) => e.data.column)
    expect(ce).toHaveLength(4)
    expect(ce[0].data).toMatchObject({ source: `${F}::${B}:t_1`, target: `${F}::${B}:t_3`, sourceHandle: 'col:acct_id', targetHandle: 'col:acct_id', why: 'carried' })
    expect(ce[0].data.label).toBeUndefined()
  })
  it('the table-level edge of a pair with column edges is dropped; other table edges stay', () => {
    const els = openTables(base, new Set([`${F}::${B}:t_1`, `${F}::${B}:t_3`]), details)
    const out = columnEdges(els, details)
    const tableEdges = out.filter((e) => e.data.source && !e.data.column)
    expect(tableEdges.map((e) => e.data.source)).toEqual([`${F}::${B}:t_2`])
  })
})
