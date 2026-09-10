// Typed client for the SAS Table-Lineage Explorer API on :8000 (proxied as /api).
// Data-flow notation everywhere: x -> y means data moves from x into y.
import { isMock, mockJson } from './mockApi'
export type EdgeLevel = 'block' | 'file' | 'project'
export type Provenance = 'fact' | 'inferred' | 'human_gold'
export type NodeRole = 'seed' | 'up' | 'down' | 'both'

export interface NodeOut {
  id: string
  label: string
  folder: string
  score: number
  cyclic: boolean
  /** absent on old fixtures; the seed is also listed in `Neighborhood.seeds` */
  role?: NodeRole
}

export interface EdgeOut {
  src: string
  dst: string
  tables: string[]
  level: EdgeLevel
  provenance: Provenance
  src_ref?: string
  dst_ref?: string
  block?: string
  freshness?: string
}

export interface Neighborhood {
  nodes: NodeOut[]
  edges: EdgeOut[]
  seeds?: string[]
  story: string[]
  order: Record<string, unknown>
}

export interface Occurrence { id: string; name: string; role: 'read' | 'write' }
export interface MacroCallOut { name: string; instance: number; block_ids: string[] }
export interface BlockInfo {
  id: string
  status: string
  kind?: string
  reads: number
  writes: number
  line_start: number
  line_end: number
  occurrences: Occurrence[]
}
export interface FileDetail {
  fileid: string
  name: string
  folder: string
  code: string
  blocks: BlockInfo[]
  block_edges: EdgeOut[]
  file_edges: EdgeOut[]
  macro_calls: MacroCallOut[]
  includes: string[]
  missing_includes: string[]
}
export interface BlockLink {
  src_file: string
  src_block: string
  src_ref: string
  dst_file: string
  dst_block: string
  dst_ref: string
  table: string
}

export interface NeighborhoodParams { table?: string; file?: string; up: number; down: number }

export interface SearchHit { kind: 'table' | 'file'; value: string; files: string[] }
export interface FileRow { id: string; label: string; folder: string }
/** one row of /api/edges — `fileid`/`block_id` say where the flow lives */
export interface EdgeRow {
  fileid: string
  block_id: string | null
  src: string
  dst: string
  tables: string[]
  level: EdgeLevel
  provenance: Provenance
  freshness?: string
}
export interface EdgesResult { total: number; rows: EdgeRow[] }
export interface EdgesParams { files: string[]; filter?: string; level?: EdgeLevel | ''; offset?: number; limit?: number }

async function getJson<T>(url: string): Promise<T> {
  if (isMock()) return mockJson(url) as T   // ?mock=1: answer from the fixtures, no server
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${url}`)
  return (await res.json()) as T
}

export function fetchNeighborhood(p: NeighborhoodParams): Promise<Neighborhood> {
  const q = new URLSearchParams()
  if (p.table) q.set('table', p.table)
  if (p.file) q.set('file', p.file)
  q.set('up', String(p.up))
  q.set('down', String(p.down))
  return getJson(`/api/neighborhood?${q}`)
}

export async function fetchBlockLinks(files: string[]): Promise<BlockLink[]> {
  if (files.length === 0) return []
  const q = new URLSearchParams({ files: files.join(',') })
  const body = await getJson<{ links: BlockLink[] }>(`/api/blocklinks?${q}`)
  return body.links
}

export function fetchFileDetail(fileid: string): Promise<FileDetail> {
  return getJson(`/api/file/${fileid.split('/').map(encodeURIComponent).join('/')}`)
}

export async function searchHits(q: string): Promise<SearchHit[]> {
  if (!q.trim()) return []
  const body = await getJson<{ hits: SearchHit[] }>(`/api/search?${new URLSearchParams({ q })}`)
  return body.hits
}

export async function fetchFiles(): Promise<FileRow[]> {
  const body = await getJson<{ files: FileRow[] }>('/api/files')
  return body.files
}

export function fetchEdges(p: EdgesParams): Promise<EdgesResult> {
  const q = new URLSearchParams()
  if (p.files.length) q.set('files', p.files.join(','))
  if (p.filter) q.set('filter', p.filter)
  if (p.level) q.set('level', p.level)
  if (p.offset) q.set('offset', String(p.offset))
  if (p.limit) q.set('limit', String(p.limit))
  return getJson(`/api/edges?${q}`)
}
