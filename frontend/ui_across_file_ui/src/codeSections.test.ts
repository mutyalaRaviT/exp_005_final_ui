import { describe, expect, it } from 'vitest'
import type { FileDetail } from './api'
import { foldRows, matchLines, matchSections, sectionAtLine, sectionTitle, sectionsOf } from './codeSections'

const detail: FileDetail = {
  fileid: 'f.sas', name: 'f.sas', folder: 'x',
  code: ['/* header */', '', 'data work.raw;', '  set src.a;', 'run;', '', 'proc sql;', '  create table work.out as select * from work.raw;', 'quit;', '/* trailer */'].join('\n'),
  blocks: [
    { id: 'b_2', status: 'PARSED', kind: 'proc sql', reads: 1, writes: 1, line_start: 7, line_end: 9,
      occurrences: [{ id: 'b_2:t_1', name: 'work.raw', role: 'read' }, { id: 'b_2:t_2', name: 'work.out', role: 'write' }] },
    { id: 'b_1', status: 'PARSED', kind: 'data', reads: 1, writes: 1, line_start: 3, line_end: 5,
      occurrences: [{ id: 'b_1:t_1', name: 'src.a', role: 'read' }, { id: 'b_1:t_2', name: 'work.raw', role: 'write' }] },
  ],
  block_edges: [], file_edges: [], macro_calls: [], includes: [], missing_includes: [],
}
const lines = detail.code.split('\n')

describe('sectionsOf', () => {
  it('orders blocks by line and converts to 0-based ranges with reads/writes', () => {
    const s = sectionsOf(detail)
    expect(s.map((x) => x.id)).toEqual(['b_1', 'b_2'])
    expect(s[0]).toMatchObject({ index: 1, kind: 'data', lineStart: 2, lineEnd: 4, writes: ['work.raw'], reads: ['src.a'] })
    expect(sectionTitle(s[1])).toBe('#2 proc sql → work.out')
  })
  it('is empty without a detail', () => expect(sectionsOf(null)).toEqual([]))
})

describe('matchSections', () => {
  const s = sectionsOf(detail)
  it('keeps everything on an empty query', () => expect(matchSections(s, lines, '  ')).toEqual(new Set(['b_1', 'b_2'])))
  it('matches by table name, kind, and code text, case-insensitively', () => {
    expect(matchSections(s, lines, 'WORK.OUT')).toEqual(new Set(['b_2']))
    expect(matchSections(s, lines, 'data')).toEqual(new Set(['b_1']))
    expect(matchSections(s, lines, 'set src')).toEqual(new Set(['b_1']))
    expect(matchSections(s, lines, 'work.raw')).toEqual(new Set(['b_1', 'b_2']))
  })
  it('ANDs several terms', () => expect(matchSections(s, lines, 'work.raw sql')).toEqual(new Set(['b_2'])))
  it('matchLines finds the lines that carry the terms', () => expect(matchLines(lines, 'work.raw')).toEqual(new Set([2, 7])))
})

describe('foldRows', () => {
  const s = sectionsOf(detail)
  it('shows kept sections and folds the runs between them', () => {
    const rows = foldRows({ lineCount: lines.length, sections: s, keep: new Set(['b_2']) })
    expect(rows).toEqual([
      { type: 'fold', from: 0, to: 5, key: '0-5' },
      { type: 'line', line: 6 }, { type: 'line', line: 7 }, { type: 'line', line: 8 },
      { type: 'fold', from: 9, to: 9, key: '9-9' },
    ])
  })
  it('keeps single text-hit lines and opens folds the reader unfolded', () => {
    const rows = foldRows({ lineCount: lines.length, sections: s, keep: new Set(), keepLines: new Set([3]), unfolded: new Set(['4-9']) })
    expect(rows[0]).toEqual({ type: 'fold', from: 0, to: 2, key: '0-2' })
    expect(rows[1]).toEqual({ type: 'line', line: 3 })
    expect(rows.slice(2).every((r) => r.type === 'line')).toBe(true)
    expect(rows).toHaveLength(2 + 6)
  })
  it('sectionAtLine finds the covering section', () => {
    expect(sectionAtLine(s, 7)?.id).toBe('b_2')
    expect(sectionAtLine(s, 0)).toBeUndefined()
  })
})
