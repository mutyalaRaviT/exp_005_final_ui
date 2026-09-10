import { describe, expect, it } from 'vitest'
import { columnsOf } from './tableColumns'
import type { BlockInfo } from './api'
import detail14 from './__fixtures__/team_finance/file/sas__raw__14_large_txn_report.sas.json'
import detail04 from './__fixtures__/team_finance/file/sas__raw__04_build_accounts.sas.json'
import type { FileDetail } from './api'

const d14 = detail14 as unknown as FileDetail
const d04 = detail04 as unknown as FileDetail
const occ = (b: BlockInfo, name: string) => b.occurrences.find((o) => o.name === name)!

describe('columnsOf — columns a BA can see in the code', () => {
  const b = d14.blocks[0]
  it('proc sql: the written table gets the select list, in order', () => {
    expect(columnsOf(d14.code, b, occ(b, 'work.large_txn_report'))).toEqual(['acct_id', 'cust_id', 'prod_id', 'branch_id', 'txn_type', 'txn_cnt', 'amt_usd_sum'])
  })
  it('proc sql: a read table gets the alias.col mentions that resolve to it (select, on, where, order)', () => {
    expect(columnsOf(d14.code, b, occ(b, 'work.txn_agg'))).toEqual(['acct_id', 'txn_type', 'txn_cnt', 'amt_usd_sum'])
    expect(columnsOf(d14.code, b, occ(b, 'work.accounts'))).toEqual(['cust_id', 'prod_id', 'branch_id', 'acct_id'])
  })
  it('proc sql: `a.*` and `x as y` land as * and y', () => {
    const sql = d04.blocks.find((x) => x.kind === 'proc sql')!
    expect(columnsOf(d04.code, sql, occ(sql, 'work.accounts'))).toEqual(['*', 'segment', 'prod_type'])
    expect(columnsOf(d04.code, sql, occ(sql, 'work.accounts_raw'))).toEqual(['*', 'cust_id', 'prod_id'])
  })
  it('data step: the INPUT / LENGTH names for the written table; nothing for a read', () => {
    const ds = d04.blocks.find((x) => x.kind === 'data')!
    expect(columnsOf(d04.code, ds, occ(ds, 'work.accounts_raw'))).toEqual(['acct_id', 'cust_id', 'prod_id', 'branch_id', 'status', 'open_bal'])
  })
  it('says nothing rather than guessing for other kinds', () => {
    const blk: BlockInfo = { ...b, kind: 'proc sort' }
    expect(columnsOf(d14.code, blk, occ(b, 'work.txn_agg'))).toEqual([])
  })
})

import { columnFlows } from './tableColumns'
import detail18 from './__fixtures__/team_finance/file/sas__raw__18_dashboard_mart.sas.json'
import detail12 from './__fixtures__/team_finance/file/sas__raw__12_txn_agg.sas.json'
const d18 = detail18 as unknown as FileDetail
const d12 = detail12 as unknown as FileDetail

describe('columnFlows — column → column, and why', () => {
  it('a plain select carries every column by name', () => {
    const b = d14.blocks[0]
    expect(columnFlows(d14.code, b, occ(b, 'work.txn_agg'), occ(b, 'work.large_txn_report'))).toEqual([
      { from: 'acct_id', to: 'acct_id', why: 'carried' }, { from: 'txn_type', to: 'txn_type', why: 'carried' },
      { from: 'txn_cnt', to: 'txn_cnt', why: 'carried' }, { from: 'amt_usd_sum', to: 'amt_usd_sum', why: 'carried' }])
  })
  it('`x as y` is renamed, an expression is computed, a literal has no source', () => {
    const b = d18.blocks[0]
    const flows = columnFlows(d18.code, b, occ(b, 'work.branch_rollup'), occ(b, 'work.dashboard_mart'))
    expect(flows).toEqual([{ from: 'branch_id', to: 'key_id', why: 'renamed branch_id' }, { from: 'branch_name', to: 'key_name', why: 'renamed branch_name' }, { from: 'total_ledger_bal', to: 'metric_val', why: 'renamed total_ledger_bal' }])
  })
  it('later union branches map by position onto the first branch names', () => {
    const b = d18.blocks[0]
    expect(columnFlows(d18.code, b, occ(b, 'work.prod_metrics'), occ(b, 'work.dashboard_mart'))).toEqual([{ from: 'prod_id', to: 'key_id', why: 'renamed prod_id' }, { from: 'prod_name', to: 'key_name', why: 'renamed prod_name' }, { from: 'book_bal', to: 'metric_val', why: 'renamed book_bal' }])
    expect(columnsOf(d18.code, b, occ(b, 'work.dashboard_mart'))).toEqual(['metric_type', 'key_id', 'key_name', 'metric_val'])
  })
  it('an aggregate is computed from its inputs', () => {
    const b = d12.blocks[0]
    const flows = columnFlows(d12.code, b, b.occurrences.find((o) => o.role === 'read')!, occ(b, 'work.txn_agg'))
    expect(flows.some((f) => f.why.startsWith('computed') && f.to === 'amt_usd_sum')).toBe(true)
  })
  it('`a.*` carries the known columns', () => {
    const b = d04.blocks.find((x) => x.kind === 'proc sql')!
    const flows = columnFlows(d04.code, b, occ(b, 'work.accounts_raw'), occ(b, 'work.accounts'))
    expect(flows.map((f) => f.to)).toEqual(['cust_id', 'prod_id'])
  })
})
