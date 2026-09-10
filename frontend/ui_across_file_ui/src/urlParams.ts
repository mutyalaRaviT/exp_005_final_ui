export interface Params { file?: string; table?: string; block?: string; up: number; down: number; mock?: boolean }

const clamp = (v: string | null, d = 1) => {
  const n = v === null || v === '' ? d : Number(v)
  if (!Number.isFinite(n)) return d
  return Math.max(0, Math.min(3, Math.trunc(n)))
}

export function readParams(search: string): Params {
  const q = new URLSearchParams(search)
  const p: Params = { up: clamp(q.get('up')), down: clamp(q.get('down')) }
  const file = q.get('file')
  const table = q.get('table')
  if (file) p.file = file
  else if (table) p.table = table
  const block = q.get('block')
  if (block) p.block = block
  if (q.has('mock')) p.mock = true   // no-backend mode rides along on every URL rewrite
  return p
}

export function writeParams(p: Params): string {
  const q = new URLSearchParams()
  if (p.file) q.set('file', p.file)
  else if (p.table) q.set('table', p.table)
  q.set('up', String(p.up))
  q.set('down', String(p.down))
  if (p.block) q.set('block', p.block)
  if (p.mock) q.set('mock', '1')
  return `?${q}`
}
