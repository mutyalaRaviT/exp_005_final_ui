// Pure post-pass over graph2Elements: a collapsed block hides its table
// occurrences and every edge that touched one of them re-points to the block
// itself (same rule graph2 uses for files that are not expanded). graph2.ts is
// a verbatim copy and knows nothing about this; it stays untouched.
import type { Graph2Element } from './graph2'

export type Element = Graph2Element & { data: Graph2Element['data'] & { collapsed?: boolean } }

/** Up to 2 labels, then an overflow count: "work.a, work.b +3" — mirrors graph2's mergeLabel. */
function mergeLabels(labels: string[]): string | undefined {
  const uniq = [...new Set(labels.filter(Boolean))]
  if (uniq.length === 0) return undefined
  const shown = uniq.slice(0, 2).join(', ')
  return uniq.length > 2 ? `${shown} +${uniq.length - 2}` : shown
}

export function collapseBlocks(elements: Graph2Element[], collapsed: Set<string>): Element[] {
  if (collapsed.size === 0) return elements as Element[]
  // occurrence id -> its collapsed block id
  const hidden = new Map<string, string>()
  for (const el of elements) {
    if (el.data.kind === 'occurrence' && el.data.parent && collapsed.has(el.data.parent)) hidden.set(el.data.id, el.data.parent)
  }
  const out: Element[] = []
  const merged = new Map<string, Element & { labels: string[] }>()
  for (const el of elements) {
    if (!el.data.source) {
      if (hidden.has(el.data.id)) continue
      if (collapsed.has(el.data.id)) out.push({ data: { ...el.data, collapsed: true } })
      else out.push(el as Element)
      continue
    }
    const source = hidden.get(el.data.source) ?? el.data.source
    const target = hidden.get(el.data.target!) ?? el.data.target!
    if (source === target) continue // an intra-block edge folded into the block
    if (source === el.data.source && target === el.data.target) {
      out.push(el as Element)
      continue
    }
    const key = `${source}->${target}`
    const prev = merged.get(key)
    if (prev) {
      if (el.data.label) prev.labels.push(el.data.label)
      // a fact edge folded together with an inferred one stays a fact edge
      if (el.data.fact !== false) prev.data.fact = el.data.fact
    } else {
      merged.set(key, { data: { ...el.data, id: `ce:${key}`, source, target }, labels: el.data.label ? [el.data.label] : [] })
    }
  }
  for (const m of merged.values()) out.push({ data: { ...m.data, label: mergeLabels(m.labels) } })
  return out
}
