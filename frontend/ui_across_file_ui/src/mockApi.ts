// No-backend mode. With `?mock=1` in the URL (or VITE_MOCK=1) every /api call is
// answered from src/__fixtures__/team_finance/ — a snapshot of what :8000 said for
// the team_finance corpus on 2026-09-09 (25 files, up/down 0..3 each, all block
// links, all 83 edge rows). The page then works with nothing running but Vite,
// which is what the design rounds need: change the UI, reload, no servers.
//
// url → JSON. Neighborhood and file detail are looked up; block links, edges and
// search are filtered in memory the way the server would filter them.
const NB = import.meta.glob('./__fixtures__/team_finance/neighborhood/*.json', { eager: true, import: 'default' }) as Record<string, unknown>
const FILE = import.meta.glob('./__fixtures__/team_finance/file/*.json', { eager: true, import: 'default' }) as Record<string, unknown>
import filesJson from './__fixtures__/team_finance/files.json'
import blocklinksJson from './__fixtures__/team_finance/blocklinks_all.json'
import edgesJson from './__fixtures__/team_finance/edges_all.json'

type Row = Record<string, unknown>
const FILES = (filesJson as { files: { id: string; label: string; folder: string }[] }).files
const LINKS = (blocklinksJson as { links: Row[] }).links
const EDGES = (edgesJson as { rows: Row[] }).rows

export function isMock(search = typeof location === 'undefined' ? '' : location.search): boolean {
  if (new URLSearchParams(search).has('mock')) return true
  return Boolean(import.meta.env?.VITE_MOCK)
}

const key = (fileid: string) => fileid.replace(/\//g, '__')
const pick = (map: Record<string, unknown>, name: string) => Object.entries(map).find(([p]) => p.endsWith('/' + name))?.[1]

/** The in-memory server. Exported so the filters can be tested without a DOM. */
export function mockJson(url: string): unknown {
  const u = new URL(url, 'http://mock')
  const q = u.searchParams
  const path = u.pathname
  if (path === '/api/files') return { files: FILES }
  if (path === '/api/neighborhood') {
    const file = q.get('file') ?? ''
    const table = q.get('table')
    const up = q.get('up') ?? '1', down = q.get('down') ?? '1'
    if (table && !file) throw new Error(`mock: neighbourhood by table is not snapshotted (${table})`)
    const hit = pick(NB, `${key(file)}__u${up}_d${down}.json`)
    if (!hit) throw new Error(`404 mock: no neighbourhood for ${file} up=${up} down=${down}`)
    return hit
  }
  if (path.startsWith('/api/file/')) {
    const fileid = decodeURIComponent(path.slice('/api/file/'.length))
    const hit = pick(FILE, `${key(fileid)}.json`)
    if (!hit) throw new Error(`404 mock: no file detail for ${fileid}`)
    return hit
  }
  if (path === '/api/blocklinks') {
    const files = new Set((q.get('files') ?? '').split(',').filter(Boolean))
    return { links: LINKS.filter((l) => files.has(String(l.src_file)) && files.has(String(l.dst_file))) }
  }
  if (path === '/api/edges') {
    const files = new Set((q.get('files') ?? '').split(',').filter(Boolean))
    const filter = (q.get('filter') ?? '').toLowerCase()
    const level = q.get('level') ?? ''
    let rows = EDGES
    if (files.size) rows = rows.filter((r) => files.has(String(r.fileid)) || files.has(String(r.src)) || files.has(String(r.dst)))
    if (level) rows = rows.filter((r) => r.level === level)
    if (filter) rows = rows.filter((r) => JSON.stringify([r.src, r.dst, r.tables]).toLowerCase().includes(filter))
    const offset = Number(q.get('offset') ?? 0), limit = Number(q.get('limit') ?? rows.length)
    return { total: rows.length, rows: rows.slice(offset, offset + limit) }
  }
  if (path === '/api/search') {
    const s = (q.get('q') ?? '').toLowerCase()
    const hits = FILES.filter((f) => f.label.toLowerCase().includes(s)).map((f) => ({ kind: 'file', value: f.id, files: [f.id] }))
    return { hits }
  }
  throw new Error(`mock: no fixture for ${url}`)
}
