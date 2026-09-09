// Read-only edges drawer for the bottom panel: a filter box and a level
// dropdown drive server-side fetches against /api/edges (the server does the
// filtering, so a big estate never lands in the browser). Rows are data flows,
// `src -> dst`, with level and provenance chips; clicking a row opens the
// file (and block) the flow lives in.
import { useEffect, useState } from 'react'
import { fetchEdges, type EdgeLevel, type EdgeRow } from '../api'

const PAGE_SIZE = 200
const DEBOUNCE_MS = 200

/** What the canvas click pointed at: the drawer narrows to flows touching it. */
export interface EdgeFocus {
  kind: 'file' | 'block' | 'table'
  /** fileid for file, block id for block, table name for table */
  value: string
  fileid?: string
}

interface EdgesPanelProps {
  fileids: string[]
  onOpenBlock: (fileid: string, blockId: string | null, row: EdgeRow) => void
  focus?: EdgeFocus | null
  onClearFocus?: () => void
}

/** inflow = data arrives at the focused thing, outflow = leaves it, self = lives inside it */
export function flowSide(e: EdgeRow, f: EdgeFocus | null | undefined): 'inflow' | 'outflow' | 'self' | null {
  if (!f) return null
  if (f.kind === 'table') {
    if (e.dst === f.value && e.src !== f.value) return 'inflow'
    if (e.src === f.value) return 'outflow'
    // a file -> file row carrying the table: the table flows out of its writer into the reader
    if (e.tables.includes(f.value)) return e.level === 'project' ? 'outflow' : 'self'
    return null
  }
  if (f.kind === 'block') return e.block_id === f.value && e.fileid === f.fileid ? 'self' : null
  // file: project rows name files as src/dst; block/file rows belong to the file
  if (e.dst === f.value && e.src !== f.value) return 'inflow'
  if (e.src === f.value) return 'outflow'
  return e.fileid === f.value ? 'self' : null
}

export default function EdgesPanel({ fileids, onOpenBlock, focus = null, onClearFocus }: EdgesPanelProps) {
  const [filter, setFilter] = useState('')
  const [level, setLevel] = useState<EdgeLevel | ''>('')
  const [rows, setRows] = useState<EdgeRow[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const scope = [...fileids].sort().join(',')
  const serverFilter = filter || (focus?.kind === 'table' ? focus.value : '')

  useEffect(() => {
    if (!scope) {
      setRows([])
      setTotal(0)
      return
    }
    let cancelled = false
    const timer = setTimeout(() => {
      setLoading(true)
      fetchEdges({ files: scope.split(','), filter: serverFilter || undefined, level, offset: 0, limit: PAGE_SIZE })
        .then((res) => {
          if (cancelled) return
          setRows(res.rows)
          setTotal(res.total)
        })
        .catch(() => {
          if (cancelled) return
          setRows([])
          setTotal(0)
        })
        .finally(() => !cancelled && setLoading(false))
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [scope, serverFilter, level])

  async function loadMore() {
    if (loading || rows.length >= total) return
    setLoading(true)
    try {
      const res = await fetchEdges({ files: scope.split(','), filter: serverFilter || undefined, level, offset: rows.length, limit: PAGE_SIZE })
      setRows((prev) => [...prev, ...res.rows])
      setTotal(res.total)
    } catch {
      // best effort: a failed page leaves the list as it is
    } finally {
      setLoading(false)
    }
  }

  const shown = focus ? rows.map((e) => [e, flowSide(e, focus)] as const).filter(([, side]) => side) : rows.map((e) => [e, null] as const)
  const focusLabel = focus ? (focus.kind === 'file' ? focus.value.split('/').pop() : focus.value) : null

  return (
    <div className="edges-table-panel" data-cid="edges-table">
      <div className="edges-toolbar" data-cid="edges-toolbar">
        <input
          type="text"
          className="edges-filter"
          data-cid="edges-filter"
          placeholder="filter edges..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <select data-cid="edges-level" aria-label="level" value={level} onChange={(e) => setLevel(e.target.value as EdgeLevel | '')}>
          <option value="">all levels</option>
          <option value="block">block</option>
          <option value="file">file</option>
          <option value="project">project</option>
        </select>
        {focus && (
          <span className={`edges-focus kind-${focus.kind}`} data-cid="edges-focus" title="the drawer shows only flows touching this; click the canvas background to clear">
            {focus.kind} · {focusLabel}
            <button type="button" aria-label="clear focus" onClick={onClearFocus}>×</button>
          </span>
        )}
        {focus && (
          <span className="edges-legend">
            <i className="inflow" /> in <i className="outflow" /> out <i className="self" /> inside
          </span>
        )}
        <span className="edges-count" data-cid="edges-count">
          {focus ? `${shown.length} of ` : ''}{rows.length} / {total}
        </span>
      </div>
      <div className="edges-head" data-cid="edges-head">
        <span className="edges-head-cell">flow (src -&gt; dst)</span>
        <span className="edges-head-cell">tables</span>
        <span className="edges-head-cell">level</span>
        <span className="edges-head-cell">provenance</span>
      </div>
      <div className="edges-virtual-viewport" data-cid="edges-viewport">
        {shown.length === 0 && <div className="empty-note">{scope ? (focus ? `no flows touch ${focusLabel}` : 'no edges match') : 'pick a file to list its edges'}</div>}
        {shown.map(([e, side], i) => (
          <div
            key={`${e.fileid}|${e.block_id ?? ''}|${e.src}|${e.dst}|${i}`}
            className={`edges-row${side ? ` ${side}` : ''}`}
            data-cid={`edge-row-${i + 1}`}
            title={`${e.fileid}${e.block_id ? ` · ${e.block_id}` : ''}`}
            onClick={() => onOpenBlock(e.fileid, e.block_id, e)}
          >
            <span className="edge-flow">
              {e.src} -&gt; {e.dst}
            </span>
            <span className="edge-tables">{e.tables.join(', ')}</span>
            <span className={`chip chip-level-${e.level}`}>{e.level}</span>
            <span className={`chip chip-${e.provenance}`}>{e.provenance}</span>
          </div>
        ))}
        {rows.length < total && (
          <button type="button" className="edges-more" disabled={loading} onClick={loadMore}>
            load more ({total - rows.length} left)
          </button>
        )}
      </div>
    </div>
  )
}
