// The bench's 38px top bar. Left to right: brand, the seed (SearchBar wearing the
// bench file-picker's clothes), the receipt pills, the P/G view switch, depth
// steppers, canvas actions, settings, pin, theme — the same reading order as
// bench.html's #top.
import type { ReactNode, RefObject } from 'react'
import SearchBar from './SearchBar'
import SettingsPanel from './SettingsPanel'
import type { LayoutSettings } from '../layoutSettings'
import type { SearchHit } from '../api'
import type { Params } from '../urlParams'

export type View = 'project' | 'file'

interface TopBarProps {
  seed: string | null
  onSelect: (hit: SearchHit) => void
  searchRef?: RefObject<HTMLInputElement | null>
  pills: ReactNode
  view: View
  onView: (v: View) => void
  params: Params
  onParams: (p: Params) => void
  onFit: () => void
  onRelayout: () => void
  disabled: boolean
  settings: LayoutSettings
  onSettings: (s: LayoutSettings) => void
  pinned: boolean
  onPin: () => void
  theme: string
  onTheme: () => void
}

const clamp = (n: number) => Math.max(0, Math.min(3, n))

export default function TopBar(p: TopBarProps) {
  const step = (side: 'up' | 'down', delta: number) =>
    p.onParams({ ...p.params, [side]: clamp(p.params[side] + delta) } as Params)

  return (
    <div id="top" data-cid="top-bar">
      <div className="brand">lineage<span>Q</span> Graph</div>
      <div className="file">
        <span className="tag sas">sas</span>
        <SearchBar onSelect={p.onSelect} inputRef={p.searchRef} />
      </div>
      <div className="receipts" data-cid="receipts">{p.pills}</div>

      <div className="engine" data-cid="view-switch" title="P: this project's files · G: inside one file (the Bench) — not merged yet">
        <button type="button" className={p.view === 'project' ? 'on' : undefined} aria-pressed={p.view === 'project'} data-cid="view-p" onClick={() => p.onView('project')}>
          P <kbd>p</kbd>
        </button>
        <button type="button" disabled data-cid="view-g" title="the file graph still lives in the Bench on :8042 — merge pending">
          G <kbd>g</kbd>
        </button>
      </div>

      <div className="engine" data-cid="depth-up" title="how many upstream hops to draw">
        <button type="button" aria-label="less upstream" onClick={() => step('up', -1)}>−</button>
        <button type="button" className="on" aria-label={`upstream ${p.params.up}`}>◀ {p.params.up}</button>
        <button type="button" aria-label="more upstream" onClick={() => step('up', 1)}>+</button>
      </div>
      <div className="engine" data-cid="depth-down" title="how many downstream hops to draw">
        <button type="button" aria-label="less downstream" onClick={() => step('down', -1)}>−</button>
        <button type="button" className="on" aria-label={`downstream ${p.params.down}`}>{p.params.down} ▶</button>
        <button type="button" aria-label="more downstream" onClick={() => step('down', 1)}>+</button>
      </div>
      <div className="engine" data-cid="canvas-actions">
        <button type="button" disabled={p.disabled} onClick={p.onFit}>fit</button>
        <button type="button" disabled={p.disabled} onClick={p.onRelayout}>re-layout</button>
      </div>

      <SettingsPanel settings={p.settings} onChange={p.onSettings} />
      <button
        type="button"
        className={p.pinned ? 'pin-toggle pinned' : 'pin-toggle'}
        data-cid="pin-toggle"
        aria-pressed={p.pinned}
        title={p.pinned ? 'pinned: clicking a file only changes the code below' : 'pin these results: clicking a file will stop re-centering'}
        onClick={p.onPin}
      >
        {p.pinned ? 'Pinned' : 'Pin'}
      </button>
      <button className="theme" data-cid="theme-btn" title={`Theme: ${p.theme} (t)`} aria-label={`Theme: ${p.theme}`} onClick={p.onTheme}>◐</button>
    </div>
  )
}
