// Pure post-pass over graph2Elements (after collapseBlocks): an opened table
// occurrence carries its column names, read from the block's code by
// tableColumns.ts. graph2.ts stays untouched, as with collapseBlocks.
import type { FileDetail } from './api'
import type { Graph2Element } from './graph2'
import { columnsOf } from './tableColumns'

export type ElementWithColumns = Graph2Element & { data: Graph2Element['data'] & { columns?: string[]; collapsed?: boolean } }

export function openTables(elements: Graph2Element[], open: Set<string>, details: Map<string, FileDetail>): ElementWithColumns[] {
  if (open.size === 0) return elements as ElementWithColumns[]
  return elements.map((el) => {
    if (el.data.kind !== 'occurrence' || !open.has(el.data.id) || !el.data.fileid || !el.data.blockId) return el as ElementWithColumns
    const detail = details.get(el.data.fileid)
    const block = detail?.blocks.find((b) => b.id === el.data.blockId)
    const occ = block?.occurrences.find((o) => `${el.data.fileid}::${o.id}` === el.data.id)
    if (!detail || !block || !occ) return el as ElementWithColumns
    return { data: { ...el.data, columns: columnsOf(detail.code, block, occ) } }
  })
}
