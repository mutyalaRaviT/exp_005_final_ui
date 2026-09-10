import { describe, expect, it } from 'vitest'
import { openTables } from './openTables'
import type { FileDetail } from './api'
import type { Graph2Element } from './graph2'
import detail14 from './__fixtures__/team_finance/file/sas__raw__14_large_txn_report.sas.json'

const d14 = detail14 as unknown as FileDetail
const F = d14.fileid
const B = d14.blocks[0].id
const occId = `${F}::${B}:t_3`
const els: Graph2Element[] = [
  { data: { id: F, kind: 'fileCluster', label: F } },
  { data: { id: `${F}::${B}`, kind: 'blockCluster', parent: F, fileid: F } },
  { data: { id: occId, kind: 'occurrence', label: 'work.large_txn_report', parent: `${F}::${B}`, fileid: F, blockId: B } },
]
const details = new Map([[F, d14]])

describe('openTables', () => {
  it('is the identity when nothing is open', () => {
    expect(openTables(els, new Set(), details)).toBe(els)
  })
  it('gives an opened occurrence its columns and leaves the rest alone', () => {
    const out = openTables(els, new Set([occId]), details)
    expect(out.find((e) => e.data.id === occId)?.data.columns).toEqual(['acct_id', 'cust_id', 'prod_id', 'branch_id', 'txn_type', 'txn_cnt', 'amt_usd_sum'])
    expect(out.find((e) => e.data.id === F)?.data).not.toHaveProperty('columns')
  })
  it('an open id with no detail yet stays a plain occurrence', () => {
    const out = openTables(els, new Set([occId]), new Map())
    expect(out.find((e) => e.data.id === occId)?.data).not.toHaveProperty('columns')
  })
})
