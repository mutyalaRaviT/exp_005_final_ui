// The SAS code pane: a section navigator beside the code.
//
// A big file is read by section, not by scrolling. The rail on the left lists
// every parsed block as `#n kind → tables it writes`; the filter box narrows
// the rail to the sections whose kind, tables or code contain the terms, and
// (with "only matching" on) folds every other line of the code behind a
// "⋯ N lines" row the reader can open. Picking a section — in the rail, the
// chip above its code, or with ↑/↓ — highlights its lines, scrolls to it and
// reports the block up so the canvas rings the matching cluster.
//
// `rangeBlocks` (verify mode) marks the slider's in-range lines.
import { Fragment, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import type { FileDetail } from '../api'
import { foldRows, matchLines, matchSections, queryTerms, sectionTitle, sectionsOf, type Section } from '../codeSections'

interface CodePaneProps {
  detail: FileDetail | null
  highlightBlock: string | null
  rangeBlocks?: Set<string> | null
  onChipClick?: (blockId: string) => void
  codeViewRef: RefObject<HTMLPreElement | null>
}

/** The line with every query term wrapped in <mark>, so the reader sees why a line was kept. */
function markTerms(line: string, terms: string[]): React.ReactNode {
  if (terms.length === 0 || !line) return line
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'ig')
  const parts = line.split(re)
  if (parts.length === 1) return line
  return parts.map((p, i) => (i % 2 === 1 ? <mark key={i}>{p}</mark> : p))
}

export default function CodePane({ detail, highlightBlock, rangeBlocks, onChipClick, codeViewRef }: CodePaneProps) {
  const [query, setQuery] = useState('')
  const [foldOn, setFoldOn] = useState(true)
  const [unfolded, setUnfolded] = useState<Set<string>>(new Set())
  const filterRef = useRef<HTMLInputElement | null>(null)

  const lines = useMemo(() => (detail ? detail.code.split('\n') : []), [detail])
  const sections = useMemo(() => sectionsOf(detail), [detail])
  const terms = useMemo(() => queryTerms(query), [query])
  const matched = useMemo(() => matchSections(sections, lines, query), [sections, lines, query])
  const hitLines = useMemo(() => matchLines(lines, query), [lines, query])
  const shownSections = useMemo(() => sections.filter((s) => matched.has(s.id)), [sections, matched])
  const filtering = terms.length > 0

  // hand-opened folds belong to one query on one file
  useEffect(() => { setUnfolded(new Set()) }, [query, detail])

  const rows = useMemo(() => {
    if (!filtering || !foldOn) return lines.map((_, i) => ({ type: 'line' as const, line: i }))
    const keep = new Set(matched)
    if (highlightBlock) keep.add(highlightBlock)
    return foldRows({ lineCount: lines.length, sections, keep, keepLines: hitLines, unfolded })
  }, [filtering, foldOn, lines, matched, highlightBlock, sections, hitLines, unfolded])

  const chipsByLine = useMemo(() => {
    const m = new Map<number, Section[]>()
    for (const s of sections) m.set(s.lineStart, [...(m.get(s.lineStart) ?? []), s])
    return m
  }, [sections])

  const activeLines = useMemo(() => {
    const s = sections.find((x) => x.id === highlightBlock)
    const set = new Set<number>()
    if (s) for (let l = s.lineStart; l <= s.lineEnd; l++) set.add(l)
    return set
  }, [sections, highlightBlock])

  const inRangeLines = useMemo(() => {
    if (!rangeBlocks) return null
    const set = new Set<number>()
    for (const s of sections) if (rangeBlocks.has(s.id)) for (let l = s.lineStart; l <= s.lineEnd; l++) set.add(l)
    return set
  }, [sections, rangeBlocks])

  // ↑ / ↓ / Enter walk the matching sections; Enter with nothing picked goes to the first
  const activeIdx = shownSections.findIndex((s) => s.id === highlightBlock)
  const step = (delta: number) => {
    if (shownSections.length === 0 || !onChipClick) return
    const next = activeIdx < 0 ? (delta > 0 ? 0 : shownSections.length - 1) : (activeIdx + delta + shownSections.length) % shownSections.length
    onChipClick(shownSections[next].id)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Cmd/Ctrl+Shift+F: jump to the section filter from anywhere
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'f') { e.preventDefault(); filterRef.current?.focus(); filterRef.current?.select() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (!detail) return <div className="empty-note">select a file to see its code</div>

  const gutter = String(lines.length).length

  return (
    <div className="code-pane" data-cid="code-pane">
      <div className="code-toolbar" data-cid="code-toolbar">
        <input
          ref={filterRef}
          type="text"
          className="code-filter"
          data-cid="code-filter"
          placeholder="filter sections: table, proc, or code text…"
          title="every word must match a section's kind, tables, or code (⌘⇧F)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); step(e.shiftKey ? -1 : 1) }
            else if (e.key === 'Escape') { setQuery('') }
          }}
        />
        {query && <button type="button" className="code-clear" aria-label="clear filter" onClick={() => setQuery('')}>×</button>}
        <label className={`code-fold-toggle${filtering ? '' : ' muted'}`} title="hide the code outside the matching sections">
          <input type="checkbox" data-cid="code-fold" checked={foldOn} disabled={!filtering} onChange={(e) => setFoldOn(e.target.checked)} /> only matching
        </label>
        <span className="code-step">
          <button type="button" aria-label="previous section" title="previous section (⇧Enter)" disabled={shownSections.length === 0} onClick={() => step(-1)}>↑</button>
          <button type="button" aria-label="next section" title="next section (Enter)" disabled={shownSections.length === 0} onClick={() => step(1)}>↓</button>
        </span>
        <span className="code-count" data-cid="code-count">
          {filtering ? `${shownSections.length} of ${sections.length}` : sections.length} section{sections.length === 1 ? '' : 's'} · {lines.length} lines
        </span>
      </div>
      <div className="code-body">
        <div className="code-sections" data-cid="code-sections">
          {sections.length === 0 && <div className="empty-note">no parsed sections in this file</div>}
          {sections.length > 0 && shownSections.length === 0 && (
            <div className="empty-note">no section matches “{query.trim()}”</div>
          )}
          {shownSections.map((s) => (
            <div
              key={s.id}
              className={`code-section${s.id === highlightBlock ? ' active' : ''}`}
              data-cid={`section-${s.id}`}
              title={`${s.id} · lines ${s.lineStart + 1}–${s.lineEnd + 1}`}
              onClick={onChipClick ? () => onChipClick(s.id) : undefined}
            >
              <div className="code-section-title">
                <span className="code-section-index">#{s.index}</span>
                <span className="code-section-kind">{s.kind}</span>
                <span className="code-section-lines">L{s.lineStart + 1}–{s.lineEnd + 1}</span>
              </div>
              {s.writes.length > 0 && <div className="code-section-tables write">→ {s.writes.join(', ')}</div>}
              {s.reads.length > 0 && <div className="code-section-tables read">← {s.reads.join(', ')}</div>}
            </div>
          ))}
        </div>
        <pre className="code-view" data-cid="code-view" ref={codeViewRef}>
          {rows.map((r) => {
            if (r.type === 'fold') {
              const n = r.to - r.from + 1
              return (
                <div key={r.key} className="code-fold" data-cid={`fold-${r.key}`} onClick={() => setUnfolded((prev) => new Set(prev).add(r.key))} title="show these lines">
                  <span className="ln">⋯</span> {n} line{n === 1 ? '' : 's'} hidden · click to show
                </div>
              )
            }
            const i = r.line
            const cls = [
              activeLines.has(i) ? 'line-active' : '',
              hitLines.has(i) ? 'line-hit' : '',
              inRangeLines?.has(i) ? 'in-range' : '',
            ].filter(Boolean).join(' ')
            return (
              <Fragment key={i}>
                {(chipsByLine.get(i) ?? []).map((s) => (
                  <div
                    key={s.id}
                    className={s.id === highlightBlock ? 'block-header active' : 'block-header'}
                    data-cid={`block-chip-${s.id}`}
                    data-block={s.id}
                    title={`${s.id} · click to select this section`}
                    onClick={onChipClick ? () => onChipClick(s.id) : undefined}
                  >
                    <span className="ln" />
                    <span className="block-chip">{sectionTitle(s)}</span>
                  </div>
                ))}
                <div data-line={i} className={cls || undefined}>
                  <span className="ln">{String(i + 1).padStart(gutter)}</span>
                  {markTerms(lines[i], terms)}
                </div>
              </Fragment>
            )
          })}
        </pre>
      </div>
    </div>
  )
}
