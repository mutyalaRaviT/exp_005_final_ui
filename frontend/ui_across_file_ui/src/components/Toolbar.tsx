import type { Params } from '../urlParams'
import { EDGE_FACT, EDGE_INFERRED, ROLE_FILL } from '../palette'

export interface ToolbarProps {
  params: Params
  onParams: (p: Params) => void
  onExpandAll: () => void
  onCollapseAll: () => void
  disabled: boolean
}

const clamp = (n: number) => Math.max(0, Math.min(3, n))

/** The Layout drawer's body: depth steppers, the two bulk actions and the legend.
 *  Search, fit and re-layout sit in the top bar; this is what did not fit up there. */
export default function Toolbar({ params, onParams, onExpandAll, onCollapseAll, disabled }: ToolbarProps) {
  const step = (side: 'up' | 'down', delta: number) => onParams({ ...params, [side]: clamp(params[side] + delta) } as Params)
  return (
    <div className="toolbar" data-cid="toolbar">
      <span className="toolbar-group">
        <span className="toolbar-label">◀ LEFT</span>
        <button type="button" aria-label="less upstream" onClick={() => step('up', -1)}>−</button>
        <b>{params.up}</b>
        <button type="button" aria-label="more upstream" onClick={() => step('up', 1)}>+</button>
      </span>
      <span className="toolbar-group">
        <span className="toolbar-label">RIGHT ▶</span>
        <button type="button" aria-label="less downstream" onClick={() => step('down', -1)}>−</button>
        <b>{params.down}</b>
        <button type="button" aria-label="more downstream" onClick={() => step('down', 1)}>+</button>
      </span>
      <button type="button" disabled={disabled} onClick={onExpandAll}>expand all</button>
      <button type="button" disabled={disabled} onClick={onCollapseAll}>collapse all</button>
      <span className="legend">
        <i style={{ background: ROLE_FILL.seed }} /> focus
        <i style={{ background: ROLE_FILL.up }} /> upstream
        <i style={{ background: ROLE_FILL.down }} /> downstream
        <s style={{ borderColor: EDGE_FACT }} /> fact
        <s style={{ borderColor: EDGE_INFERRED, borderStyle: 'dashed' }} /> inferred
        <span>#N = run order</span>
      </span>
    </div>
  )
}
