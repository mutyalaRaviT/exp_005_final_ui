// Pure post-pass (after openTables): when a read table and the written table of
// one block are both open, one edge per column flow between them, labelled why
// (carried / renamed x / computed expr) — tableColumns.columnFlows. Across files,
// an open written table and an open read table of the same name carry every
// column they share. Edges land on column rows through per-column handles
// (`col:<name>`), which OccurrenceNode renders. graph2.ts stays untouched.
import type { FileDetail } from './api'
import type { Graph2Element } from './graph2'
import { columnFlows } from './tableColumns'

export type ColumnEdgeData = Graph2Element['data'] & { columns?: string[]; sourceHandle?: string; targetHandle?: string; column?: boolean; why?: string }
export type ElementWithColumnEdges = { data: ColumnEdgeData }

export function columnEdges(elements: ElementWithColumnEdges[], details: Map<string, FileDetail>): ElementWithColumnEdges[] {
  const open = elements.filter((e) => e.data.kind === 'occurrence' && e.data.columns)
  if (open.length < 2) return elements
  const out: ElementWithColumnEdges[] = [...elements]
  const occOf = (d: ColumnEdgeData) => {
    const detail = d.fileid ? details.get(d.fileid) : undefined
    const block = detail?.blocks.find((b) => b.id === d.blockId)
    const occ = block?.occurrences.find((o) => `${d.fileid}::${o.id}` === d.id)
    return detail && block && occ ? { detail, block, occ } : null
  }
  const push = (s: ColumnEdgeData, t: ColumnEdgeData, from: string, to: string, why: string) => {
    if (!s.columns!.includes(from) || !t.columns!.includes(to)) return
    // carried / renamed / same table are visible from the two rows the line joins; only computed needs words
    const label = why.startsWith('computed') ? why.slice('computed '.length) : undefined
    out.push({ data: { id: `ce:${s.id}.${from}->${t.id}.${to}`, source: s.id, target: t.id, sourceHandle: `col:${from}`, targetHandle: `col:${to}`, label, why, fact: true, column: true } })
  }
  for (const t of open) {
    const b = occOf(t.data)
    if (!b || b.occ.role !== 'write') continue
    // inside the block: each open read table → this written table
    for (const s of open) {
      if (s === t || s.data.blockId !== t.data.blockId || s.data.fileid !== t.data.fileid) continue
      const a = occOf(s.data)
      if (!a || a.occ.role !== 'read') continue
      for (const f of columnFlows(a.detail.code, a.block, a.occ, b.occ)) push(s.data, t.data, f.from, f.to, f.why)
    }
    // across files: the same table, written here and read there
    for (const r of open) {
      const c = occOf(r.data)
      if (!c || c.occ.role !== 'read' || r.data.fileid === t.data.fileid || c.occ.name.toLowerCase() !== b.occ.name.toLowerCase()) continue
      for (const col of t.data.columns!) if (r.data.columns!.includes(col)) push(t.data, r.data, col, col, 'same table')
    }
  }
  // a pair that now has column edges drops its table-level edge: the columns say why, row by row
  const pairs = new Set(out.filter((e) => e.data.column).map((e) => `${e.data.source}->${e.data.target}`))
  return out.filter((e) => !(e.data.source && !e.data.column && pairs.has(`${e.data.source}->${e.data.target}`)))
}
