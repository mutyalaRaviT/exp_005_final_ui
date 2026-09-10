import { describe, expect, it } from 'vitest'
import { edgeReasons } from './edgeReasons'
import { reasonOf } from './tableColumns'
import { graph2Elements } from './graph2'
import type { FileDetail, Neighborhood } from './api'
import detail14 from './__fixtures__/team_finance/file/sas__raw__14_large_txn_report.sas.json'
import detail04 from './__fixtures__/team_finance/file/sas__raw__04_build_accounts.sas.json'
import detail18 from './__fixtures__/team_finance/file/sas__raw__18_dashboard_mart.sas.json'

const d14 = detail14 as unknown as FileDetail
const d04 = detail04 as unknown as FileDetail
const d18 = detail18 as unknown as FileDetail
const occ = (d: FileDetail, kind: string, name: string) => { const b = d.blocks.find((x) => x.kind === kind)!; return [b, b.occurrences.find((o) => o.name === name)!] as const }

describe('reasonOf — why a read table flows into the written one', () => {
  it('the from table, with its filter and column count', () => {
    const [b, t] = occ(d14, 'proc sql', 'work.txn_agg'); const [, w] = occ(d14, 'proc sql', 'work.large_txn_report')
    expect(reasonOf(d14.code, b, t, w)).toBe('from · filter amt_usd_sum >= 1000 · 4 cols')
  })
  it('a joined table, with the join kind and key', () => {
    const [b, a] = occ(d14, 'proc sql', 'work.accounts'); const [, w] = occ(d14, 'proc sql', 'work.large_txn_report')
    expect(reasonOf(d14.code, b, a, w)).toBe('inner join on acct_id · 4 cols')
  })
  it('a union all reads as union', () => {
    const [b, l] = occ(d18, 'proc sql', 'work.large_txn_report'); const [, w] = occ(d18, 'proc sql', 'work.dashboard_mart')
    expect(reasonOf(d18.code, b, l, w)).toBe('union · 3 cols')
  })
  it('two joins in one query each get their own key', () => {
    const [b, c] = occ(d04, 'proc sql', 'work.customers'); const [, w] = occ(d04, 'proc sql', 'work.accounts')
    expect(reasonOf(d04.code, b, c, w)).toBe('inner join on cust_id · 2 cols')
    const [, p] = occ(d04, 'proc sql', 'work.products')
    expect(reasonOf(d04.code, b, p, w)).toBe('inner join on prod_id · 2 cols')
  })
})

describe('edgeReasons post-pass', () => {
  it('labels the intra-block edges of an expanded file and nothing else', () => {
    const hood: Neighborhood = { nodes: [{ id: d14.fileid, label: d14.name, folder: d14.folder, score: 1, cyclic: false }], edges: [], story: [], order: {} }
    const details = new Map([[d14.fileid, d14]])
    const out = edgeReasons(graph2Elements(hood, new Set([d14.fileid]), details, []), details)
    const labels = out.filter((e) => e.data.source).map((e) => e.data.label).sort()
    expect(labels).toEqual(['from · filter amt_usd_sum >= 1000 · 4 cols', 'inner join on acct_id · 4 cols'])
  })
  it('is the identity with no details', () => {
    const els = [{ data: { id: 'ie:x:0', source: 'a', target: 'b' } }]
    expect(edgeReasons(els, new Map())).toBe(els)
  })
})

describe('edgeReasons on cross-file edges', () => {
  it('a file → read table edge says only how the block uses it (the box names the table); a written table → closed file edge keeps just the table (the arrow says who reads it)', () => {
    const d14 = detail14 as unknown as FileDetail
    const up = 'sas/raw/04_build_accounts.sas', down = 'sas/raw/18_dashboard_mart.sas'
    const hood: Neighborhood = {
      nodes: [{ id: up, label: '04', folder: 'sas/raw', score: 0, cyclic: false }, { id: d14.fileid, label: d14.name, folder: d14.folder, score: 1, cyclic: false }, { id: down, label: '18', folder: 'sas/raw', score: 2, cyclic: false }],
      edges: [{ src: up, dst: d14.fileid, tables: ['work.accounts'], level: 'project', provenance: 'inferred' }, { src: d14.fileid, dst: down, tables: ['work.large_txn_report'], level: 'project', provenance: 'inferred' }],
      story: [], order: {},
    }
    const b = d14.blocks[0].id
    const links = [
      { src_file: up, src_block: 'x', src_ref: 'x:t_1', dst_file: d14.fileid, dst_block: b, dst_ref: `${b}:t_2`, table: 'work.accounts' },
      { src_file: d14.fileid, src_block: b, src_ref: `${b}:t_3`, dst_file: down, dst_block: 'y', dst_ref: 'y:t_1', table: 'work.large_txn_report' },
    ]
    const details = new Map([[d14.fileid, d14]])
    const out = edgeReasons(graph2Elements(hood, new Set([d14.fileid]), details, links), details)
    const labels = out.filter((e) => e.data.id.startsWith('xe:')).map((e) => e.data.label).sort()
    expect(labels).toEqual(['inner join on acct_id · 4 cols', 'work.large_txn_report'])
  })
})
