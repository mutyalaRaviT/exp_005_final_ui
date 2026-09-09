// Pure builder for the block graph v2: a Neighborhood plus whichever
// FileDetails have been expanded -> cytoscape element definitions, with the
// visible-ancestor edge re-pointing rule (a cross-file edge whose endpoint
// sits inside an expanded file re-points to the finest node visible there —
// an occurrence, else its block, else the file itself). No cytoscape import
// — plain data, so this file unit-tests without a canvas.
import type { BlockLink, EdgeOut, FileDetail, Neighborhood } from './api'

export type { BlockLink }

export interface Graph2Element {
  data: {
    id: string
    kind?: 'file' | 'fileCluster' | 'blockCluster' | 'macro' | 'occurrence'
    label?: string
    parent?: string
    source?: string
    target?: string
    fact?: boolean
    cyclic?: boolean
    fileid?: string
    blockId?: string
  }
}

/** Namespace an inner (block/occurrence/macro) id to its file. Block ids are
 *  content-hashed and only unique within a file — two files can share one —
 *  so every inner id used as a cytoscape element id goes through here. */
export function innerId(fileid: string, id: string): string {
  return `${fileid}::${id}`
}

function isVisible(
  fileid: string,
  expanded: Set<string>,
  details: Map<string, FileDetail>,
): boolean {
  return expanded.has(fileid) && details.has(fileid)
}

/** Which block (if any) owns an occurrence ref, within one file's detail. */
function blockOfRef(detail: FileDetail, ref: string): string | undefined {
  for (const block of detail.blocks) {
    if (block.occurrences.some((occ) => occ.id === ref)) return block.id
  }
  return undefined
}

/** Resolve a (file, block, ref) endpoint to the finest node currently
 *  visible: the occurrence if the file is expanded and the ref is one of
 *  its emitted occurrences, else that file's block node, else the file
 *  node — which is the same id whether the file is collapsed or expanded. */
function resolveEndpoint(
  fileid: string,
  block: string,
  ref: string,
  expanded: Set<string>,
  details: Map<string, FileDetail>,
): string {
  if (!isVisible(fileid, expanded, details)) return fileid
  const detail = details.get(fileid)!
  if (blockOfRef(detail, ref) !== undefined) return innerId(fileid, ref)
  if (detail.blocks.some((b) => b.id === block)) return innerId(fileid, block)
  return fileid
}

/** Up to 2 table names, then an overflow count: "work.a, work.b +3". */
function mergeLabel(tables: string[]): string {
  const shown = tables.slice(0, 2).join(', ')
  return tables.length > 2 ? `${shown} +${tables.length - 2}` : shown
}

export function graph2Elements(
  hood: Neighborhood,
  expanded: Set<string>,
  details: Map<string, FileDetail>,
  links: BlockLink[],
): Graph2Element[] {
  const elements: Graph2Element[] = []
  const nodes = [...hood.nodes].sort((a, b) => a.id.localeCompare(b.id))
  const hoodIds = new Set(nodes.map((n) => n.id))

  // 1. Nodes: an expanded+cached file becomes a fileCluster containing
  // macro parents, blockClusters, and occurrence leaves (macro-parent-first,
  // as in verify.ts's blockScopeElements); everything else is a plain file
  // node, same shape as v1. Track each expanded file's emitted occurrence
  // refs, for the intra-file edge guard below.
  const emittedOcc = new Map<string, Set<string>>()

  for (const n of nodes) {
    if (isVisible(n.id, expanded, details)) {
      const detail = details.get(n.id)!
      elements.push({ data: { id: n.id, kind: 'fileCluster', label: n.label, fileid: n.id } })

      const blockIds = new Set(detail.blocks.map((b) => b.id))
      const macroParentOf = new Map<string, string>()
      for (const call of detail.macro_calls) {
        const wrapped = call.block_ids.filter((id) => blockIds.has(id))
        if (wrapped.length === 0) continue
        const parentId = innerId(n.id, `macro#${call.name}#${call.instance}`)
        elements.push({
          data: {
            id: parentId,
            kind: 'macro',
            label: `%${call.name} #${call.instance}`,
            parent: n.id,
            fileid: n.id,
          },
        })
        for (const id of wrapped) macroParentOf.set(id, parentId)
      }

      const occSet = new Set<string>()
      for (const block of detail.blocks) {
        const blockElId = innerId(n.id, block.id)
        elements.push({
          data: {
            id: blockElId,
            kind: 'blockCluster',
            label: `${block.kind ? `${block.kind} · ` : ''}${block.id}`,
            parent: macroParentOf.get(block.id) ?? n.id,
            fileid: n.id,
          },
        })
        for (const occ of block.occurrences) {
          occSet.add(occ.id)
          elements.push({
            data: {
              id: innerId(n.id, occ.id),
              kind: 'occurrence',
              label: occ.name,
              parent: blockElId,
              fileid: n.id,
              blockId: block.id,
            },
          })
        }
      }
      emittedOcc.set(n.id, occSet)
    } else {
      elements.push({
        data: {
          id: n.id,
          kind: 'file',
          label: `${n.label}\n#${n.score}`,
          cyclic: n.cyclic,
          fileid: n.id,
        },
      })
    }
  }

  // 2. Intra-file edges: each expanded+cached file's own block_edges (fact)
  // and file_edges (dashed), namespaced, skipped unless both refs made it
  // into that file's emitted occurrences — mirrors verify.ts's pushEdge.
  for (const n of nodes) {
    if (!isVisible(n.id, expanded, details)) continue
    const detail = details.get(n.id)!
    const occSet = emittedOcc.get(n.id)!
    const pushIntra = (edge: EdgeOut, fact: boolean, i: number) => {
      if (!edge.src_ref || !edge.dst_ref) return
      if (!occSet.has(edge.src_ref) || !occSet.has(edge.dst_ref)) return
      elements.push({
        data: {
          id: `ie:${n.id}:${i}`,
          source: innerId(n.id, edge.src_ref),
          target: innerId(n.id, edge.dst_ref),
          fact,
        },
      })
    }
    detail.block_edges.forEach((e, i) => pushIntra(e, true, i))
    detail.file_edges.forEach((e, i) => pushIntra(e, false, i + detail.block_edges.length))
  }

  // 3. Cross-file edges: for any file pair with at least one expanded end,
  // re-point each `links` row's endpoints to the finest visible ancestor
  // and merge rows that land on the same (src, dst) after resolution. For
  // pairs where neither end is expanded, fall back to `hood.edges` verbatim
  // (label = tables[0]) — that half alone reproduces the v1 file graph.
  const crossEdges = new Map<string, { src: string; dst: string; tables: string[] }>()
  const addTable = (src: string, dst: string, table: string) => {
    const key = `${src}->${dst}`
    const entry = crossEdges.get(key)
    if (entry) {
      if (!entry.tables.includes(table)) entry.tables.push(table)
    } else {
      crossEdges.set(key, { src, dst, tables: [table] })
    }
  }

  for (const link of links) {
    if (!hoodIds.has(link.src_file) || !hoodIds.has(link.dst_file)) continue
    const srcVisible = isVisible(link.src_file, expanded, details)
    const dstVisible = isVisible(link.dst_file, expanded, details)
    if (!srcVisible && !dstVisible) continue
    const src = resolveEndpoint(link.src_file, link.src_block, link.src_ref, expanded, details)
    const dst = resolveEndpoint(link.dst_file, link.dst_block, link.dst_ref, expanded, details)
    addTable(src, dst, link.table)
  }

  for (const edge of hood.edges) {
    const srcVisible = isVisible(edge.src, expanded, details)
    const dstVisible = isVisible(edge.dst, expanded, details)
    if (srcVisible || dstVisible) continue
    addTable(edge.src, edge.dst, edge.tables[0] ?? '')
  }

  for (const [key, { src, dst, tables }] of crossEdges) {
    elements.push({ data: { id: `xe:${key}`, source: src, target: dst, label: mergeLabel(tables) } })
  }

  return elements
}
