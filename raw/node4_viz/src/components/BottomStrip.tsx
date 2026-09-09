// The bench's third buffer: a full-width strip under the canvas with tabs, either
// open at a fixed height or collapsed to its 32px header line (⌘J). No drag —
// same rule as the Bench (exp_42 2026-09-08).
import type { ReactNode } from 'react'

export interface StripTab {
  key: string
  label: string
  content: ReactNode
}

interface BottomStripProps {
  tabs: StripTab[]
  active: string
  onActive: (key: string) => void
  open: boolean
  min: boolean
  height: number
  onToggleMin: () => void
  onClose: () => void
  status?: ReactNode
}

export default function BottomStrip({ tabs, active, onActive, open, min, height, onToggleMin, onClose, status }: BottomStripProps) {
  const current = tabs.find((t) => t.key === active) ?? tabs[0]
  return (
    <div
      id="bottom"
      data-cid="bottom-strip"
      className={`${open ? 'open' : ''}${min ? ' min' : ''}`.trim()}
      style={{ height: open && !min ? height : undefined }}
    >
      <div className="tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            data-tab={t.key}
            data-cid={`tab-${t.key}`}
            className={t.key === current?.key ? 'on' : undefined}
            aria-pressed={t.key === current?.key}
            onClick={() => onActive(t.key)}
          >
            {t.label}
          </button>
        ))}
        <div className="sp">
          {status}
          <kbd data-cid="strip-min" title="collapse to one line (⌘J)" onClick={onToggleMin}>{min ? '⌃' : '⌄'}</kbd>
          <kbd data-cid="strip-close" title="close" onClick={onClose}>×</kbd>
        </div>
      </div>
      <div className="body" data-cid="strip-body">{current?.content}</div>
    </div>
  )
}
