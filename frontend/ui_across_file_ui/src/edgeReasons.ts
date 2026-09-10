// Pure post-pass (after openTables): every intra-block edge — a table a block
// reads → the table it writes — gets a label that says why they are joined,
// read off the block's code by tableColumns.reasonOf. Cross-file edges keep
// their table label; graph2.ts stays untouched.
import type { FileDetail } from './api'
import type { Graph2Element } from './graph2'
import { reasonOf } from './tableColumns'

export function edgeReasons(elements: Graph2Element[], details: Map<string, FileDetail>): Graph2Element[] {
  if (details.size === 0) return elements
  const byId = new Map(elements.map((e) => [e.data.id, e]))
  const occOf = (d: Graph2Element['data']) => {
    if (d.kind !== 'occurrence' || !d.fileid || !d.blockId) return null
    const detail = details.get(d.fileid)
    const block = detail?.blocks.find((b) => b.id === d.blockId)
    const occ = block?.occurrences.find((o) => `${d.fileid}::${o.id}` === d.id)
    return detail && block && occ ? { detail, block, occ } : null
  }
  // an open table shows its rows, so "· N cols" says nothing new
  const isOpen = (d: Graph2Element['data']) => (d as { columns?: string[] }).columns !== undefined
  const trimCols = (why: string, open: boolean) => (open ? why.replace(/ · \d+ cols?$/, '') : why)
  return elements.map((el) => {
    if (!el.data.source) return el
    const s = byId.get(el.data.source)?.data, t = byId.get(el.data.target!)?.data
    if (!s || !t) return el
    if (el.data.id.startsWith('ie:') && !el.data.label) {
      // inside one block: read table → written table, why
      const a = occOf(s), b = occOf(t)
      if (!a || !b || a.block !== b.block) return el
      const label = trimCols(reasonOf(a.detail.code, a.block, a.occ, b.occ), isOpen(s))
      return label ? { data: { ...el.data, label } } : el
    }
    if (el.data.id.startsWith('xe:') && el.data.label) {
      // across files into an open block: the arrow lands on the table's own box, so only the why is said
      const b = occOf(t)
      if (b) {
        const w = b.block.occurrences.find((o) => o.role === 'write') ?? b.occ
        const why = trimCols(reasonOf(b.detail.code, b.block, b.occ, w), isOpen(t))
        return why ? { data: { ...el.data, label: why } } : el
      }
      // into a closed file the arrow already says who reads it: the table name is the whole label
      return el
    }
    return el
  })
}
