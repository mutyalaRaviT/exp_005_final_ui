import { describe, expect, it } from 'vitest'
import { isMock, mockJson } from './mockApi'

const F14 = 'sas/raw/14_large_txn_report.sas'

describe('mockApi — the no-backend server', () => {
  it('is on only with ?mock', () => {
    expect(isMock('?file=x&mock=1')).toBe(true)
    expect(isMock('?file=x')).toBe(false)
  })
  it('answers the seed page: neighbourhood, files, file detail', () => {
    const nb = mockJson(`/api/neighborhood?file=${encodeURIComponent(F14)}&up=1&down=3`) as { nodes: { id: string }[]; edges: unknown[] }
    expect(nb.nodes.map((n) => n.id)).toContain(F14)
    expect(nb.nodes).toHaveLength(6)
    expect((mockJson('/api/files') as { files: unknown[] }).files).toHaveLength(25)
    const d = mockJson('/api/file/sas/raw/14_large_txn_report.sas') as { blocks: unknown[]; code: string }
    expect(d.blocks).toHaveLength(1)
    expect(d.code).toContain('proc sql')
  })
  it('filters block links to the files asked for, both ends', () => {
    const all = (mockJson('/api/blocklinks?files=' + encodeURIComponent(['sas/raw/12_txn_agg.sas', F14].join(','))) as { links: { src_file: string; dst_file: string }[] }).links
    expect(all.length).toBeGreaterThan(0)
    for (const l of all) expect([l.src_file, l.dst_file]).toContain(F14)
    expect((mockJson('/api/blocklinks?files=') as { links: unknown[] }).links).toHaveLength(0)
  })
  it('filters and pages edges like the server', () => {
    const one = mockJson(`/api/edges?files=${encodeURIComponent(F14)}`) as { total: number; rows: { level: string }[] }
    expect(one.total).toBe(one.rows.length)
    const blk = mockJson(`/api/edges?files=${encodeURIComponent(F14)}&level=block`) as { rows: { level: string }[] }
    for (const r of blk.rows) expect(r.level).toBe('block')
    const page = mockJson('/api/edges?limit=5&offset=5') as { total: number; rows: unknown[] }
    expect(page.rows).toHaveLength(5)
    expect(page.total).toBe(83)
  })
  it('says what it cannot answer', () => {
    expect(() => mockJson('/api/neighborhood?file=nope.sas&up=1&down=1')).toThrow(/404 mock/)
    expect(() => mockJson('/api/other')).toThrow(/no fixture/)
  })
})
