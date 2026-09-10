// Sections of a file's code, for the code pane's navigator: each parsed block
// becomes a section with a human title (`#2 proc sql → work.accounts`), and a
// text filter narrows the sections to the ones a reader wants. With the fold
// on, the code view hides every line outside the matching sections behind a
// "⋯ N lines" row, so a 3,000-line file collapses to the few sections that
// matter and the reader gets to the code without scrolling.
import type { FileDetail } from './api'

export interface Section {
  id: string
  /** 1-based position in the file, what the title shows */
  index: number
  kind: string
  /** 0-based inclusive code line range */
  lineStart: number
  lineEnd: number
  writes: string[]
  reads: string[]
}

export type CodeRow =
  | { type: 'line'; line: number }
  | { type: 'fold'; from: number; to: number; key: string }

const uniq = (xs: string[]) => [...new Set(xs)]

/** The file's blocks as sections, in line order. */
export function sectionsOf(detail: FileDetail | null): Section[] {
  if (!detail) return []
  const blocks = [...detail.blocks].sort((a, b) => (a.line_start ?? 1) - (b.line_start ?? 1))
  return blocks.map((b, i) => {
    const lineStart = Math.max(0, (b.line_start ?? 1) - 1)
    return {
      id: b.id,
      index: i + 1,
      kind: b.kind ?? 'block',
      lineStart,
      lineEnd: Math.max(lineStart, (b.line_end ?? b.line_start ?? 1) - 1),
      writes: uniq(b.occurrences.filter((o) => o.role === 'write').map((o) => o.name)),
      reads: uniq(b.occurrences.filter((o) => o.role === 'read').map((o) => o.name)),
    }
  })
}

/** `#2 proc sql → work.accounts` — the section's name in the rail and in the chip above its code. */
export function sectionTitle(s: Section): string {
  const out = s.writes.length ? ` → ${s.writes.join(', ')}` : ''
  return `#${s.index} ${s.kind}${out}`
}

/** Query terms: every whitespace-separated term must match (AND), case-insensitive. */
export function queryTerms(query: string): string[] {
  return query.toLowerCase().split(/\s+/).filter(Boolean)
}

/** Sections whose kind, id, tables or code lines contain every query term. Empty query → all. */
export function matchSections(sections: Section[], lines: string[], query: string): Set<string> {
  const terms = queryTerms(query)
  if (terms.length === 0) return new Set(sections.map((s) => s.id))
  const hits = new Set<string>()
  for (const s of sections) {
    const meta = [s.kind, s.id, `#${s.index}`, ...s.writes, ...s.reads].join(' ').toLowerCase()
    const body = lines.slice(s.lineStart, s.lineEnd + 1).join('\n').toLowerCase()
    if (terms.every((t) => meta.includes(t) || body.includes(t))) hits.add(s.id)
  }
  return hits
}

/** Lines that themselves contain every query term (highlighted in the code, kept when folded). */
export function matchLines(lines: string[], query: string): Set<number> {
  const terms = queryTerms(query)
  const hits = new Set<number>()
  if (terms.length === 0) return hits
  lines.forEach((l, i) => {
    const low = l.toLowerCase()
    if (terms.every((t) => low.includes(t))) hits.add(i)
  })
  return hits
}

export interface FoldOptions {
  lineCount: number
  sections: Section[]
  /** sections to keep; everything else folds */
  keep: Set<string>
  /** single lines to keep even outside a kept section (text hits) */
  keepLines?: Set<number>
  /** fold keys the reader has opened by hand */
  unfolded?: Set<string>
}

/** The rows the code view draws: visible lines, and one fold row per hidden run. */
export function foldRows({ lineCount, sections, keep, keepLines, unfolded }: FoldOptions): CodeRow[] {
  const visible = new Array<boolean>(lineCount).fill(false)
  for (const s of sections) {
    if (!keep.has(s.id)) continue
    for (let l = s.lineStart; l <= Math.min(s.lineEnd, lineCount - 1); l++) visible[l] = true
  }
  for (const l of keepLines ?? []) if (l >= 0 && l < lineCount) visible[l] = true
  const rows: CodeRow[] = []
  let i = 0
  while (i < lineCount) {
    if (visible[i]) { rows.push({ type: 'line', line: i }); i++; continue }
    let j = i
    while (j < lineCount && !visible[j]) j++
    const key = `${i}-${j - 1}`
    if (unfolded?.has(key)) for (let l = i; l < j; l++) rows.push({ type: 'line', line: l })
    else rows.push({ type: 'fold', from: i, to: j - 1, key })
    i = j
  }
  return rows
}

/** The section that covers a code line, if any. */
export function sectionAtLine(sections: Section[], line: number): Section | undefined {
  return sections.find((s) => line >= s.lineStart && line <= s.lineEnd)
}
