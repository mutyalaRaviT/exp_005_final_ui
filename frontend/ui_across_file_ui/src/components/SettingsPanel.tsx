import { useEffect, useRef, useState } from 'react'
import { LAYERINGS, NODE_PLACEMENTS, PROFILES, profileOf, profileSettings, type LayoutSettings } from '../layoutSettings'

interface SettingsPanelProps {
  settings: LayoutSettings
  onChange: (next: LayoutSettings) => void
}

interface Row { key: keyof LayoutSettings; label: string; tier: 1 | 2 | 3 | 4 | 5; help: string; advanced?: boolean }

const ROWS: Row[] = [
  { key: 'mergeEdges', tier: 1, label: 'Merge fan-out edges', help: 'One trunk leaves a table and splits near the targets (ELK mergeEdges).' },
  { key: 'straighten', tier: 1, label: 'Straighten edges', help: 'Drop needless bends, favour straight runs, wider edge spacing.' },
  { key: 'stableOrder', tier: 1, label: 'Sort by file name', help: 'Files keep file-name order; expanding or collapsing moves others aside instead of shuffling.' },
  { key: 'animate', tier: 1, label: 'Animate layout changes', help: 'Nodes glide to their new place (d3 tween on top of React Flow).' },
  { key: 'sidePorts', tier: 1, label: 'Side ports', help: 'Edges leave on the right and enter on the left of every box.' },
  { key: 'elkLabels', tier: 1, advanced: true, label: 'ELK places labels', help: 'Let the layout engine reserve room for edge labels.' },
  { key: 'keepArrangement', tier: 2, advanced: true, label: 'Keep my arrangement', help: 'Re-layout keeps the order you dragged nodes into (semi-interactive).' },
  { key: 'followRunOrder', tier: 3, advanced: true, label: 'Follow run order', help: 'Files in run order, blocks in source order (model order).' },
  { key: 'avoidRouting', tier: 4, advanced: true, label: 'Obstacle-avoiding edges', help: 'Route edges around every box with libavoid after ELK places the nodes.' },
  { key: 'holaLayout', tier: 5, advanced: true, label: 'HOLA placement (pyhola)', help: 'HOLA (libdialect) places the file boxes and routes the edges between them; ELK still lays out the inside of each box. Needs the hola_server sidecar on :8765.' },
]
/** placement group: how ELK chooses columns and positions */
const PLACEMENT_ROWS: Row[] = [
  { key: 'greedySwitch', tier: 1, label: 'Greedy crossing switch', help: 'Post-pass that swaps neighbouring nodes to remove leftover crossings.' },
  { key: 'nodePromotion', tier: 1, label: 'Node promotion', help: 'Pull nodes into earlier columns to shorten long edges.' },
  { key: 'compaction', tier: 1, label: 'Post-compaction', help: 'Squeeze the layout after placement to shorten edges.' },
]

/** Gear button + popover with the layout toggles. Closes on Escape or an outside click. */
export default function SettingsPanel({ settings, onChange }: SettingsPanelProps) {
  const [open, setOpen] = useState(false)
  const anyAdvancedOn = ROWS.some((r) => r.advanced && settings[r.key]) || PLACEMENT_ROWS.some((r) => settings[r.key]) || settings.layering !== 'NETWORK_SIMPLEX' || settings.nodePlacement !== 'NETWORK_SIMPLEX'
  const [showAdvanced, setShowAdvanced] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const set = <K extends keyof LayoutSettings>(key: K, value: LayoutSettings[K]) => onChange({ ...settings, [key]: value })
  const current = profileOf(settings)
  const currentLabel = current === 'custom' ? 'Custom' : PROFILES.find((p) => p.id === current)!.label
  const hint = current === 'custom' ? 'Hand-tuned toggles. Pick a profile to reset them.' : PROFILES.find((p) => p.id === current)!.hint

  return (
    <div className="settings" ref={rootRef} data-cid="settings">
      <button
        type="button"
        className={open ? 'settings-btn open' : 'settings-btn'}
        aria-label="layout settings"
        aria-expanded={open}
        title="layout settings"
        onClick={() => setOpen((v) => !v)}
      >
        ⚙ Layout · {currentLabel}
      </button>
      {open && (
        <div className="settings-pop" role="dialog" aria-label="layout settings" data-cid="settings-pop">
          <div className="settings-profiles" role="radiogroup" aria-label="layout profile">
            {PROFILES.map((p) => (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={current === p.id}
                className={current === p.id ? 'settings-profile on' : 'settings-profile'}
                title={p.hint}
                onClick={() => onChange(profileSettings(p.id))}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="settings-hint">{hint}</div>
          {ROWS.filter((r) => !r.advanced).map((r) => (
            <label key={r.key} className="settings-row" title={r.help}>
              <input type="checkbox" aria-label={r.label} checked={Boolean(settings[r.key])} onChange={(e) => set(r.key, e.target.checked as never)} />
              <span className="settings-tier">T{r.tier}</span>
              <span className="settings-label">{r.label}</span>
            </label>
          ))}
          <label className="settings-row settings-range" title="How hard ELK tries (7 is its default; higher is slower but cleaner).">
            <span className="settings-tier">T1</span>
            <span className="settings-label">Thoroughness</span>
            <input
              type="range"
              min={1}
              max={30}
              aria-label="thoroughness"
              value={settings.thoroughness}
              onChange={(e) => set('thoroughness', Number(e.target.value))}
            />
            <b>{settings.thoroughness}</b>
          </label>
          <button
            type="button"
            className="settings-advanced-toggle"
            aria-expanded={showAdvanced || anyAdvancedOn}
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced || anyAdvancedOn ? '▾' : '▸'} Advanced{anyAdvancedOn ? ' · on' : ''}
          </button>
          {(showAdvanced || anyAdvancedOn) && (
            <>
              <div className="settings-group">Placement</div>
              <label className="settings-row settings-select" title="How ELK assigns nodes to columns.">
                <span className="settings-tier">T1</span>
                <span className="settings-label">Layering</span>
                <select aria-label="layering" value={settings.layering} onChange={(e) => set('layering', e.target.value as LayoutSettings['layering'])}>
                  {LAYERINGS.map((v) => <option key={v} value={v}>{v.toLowerCase().replace('_', ' ')}</option>)}
                </select>
              </label>
              <label className="settings-row settings-select" title="How ELK positions nodes inside a column.">
                <span className="settings-tier">T1</span>
                <span className="settings-label">Node placement</span>
                <select aria-label="node placement" value={settings.nodePlacement} onChange={(e) => set('nodePlacement', e.target.value as LayoutSettings['nodePlacement'])}>
                  {NODE_PLACEMENTS.map((v) => <option key={v} value={v}>{v.toLowerCase().replace('_', ' ')}</option>)}
                </select>
              </label>
              {PLACEMENT_ROWS.map((r) => (
            <label key={r.key} className="settings-row" title={r.help}>
              <input type="checkbox" aria-label={r.label} checked={Boolean(settings[r.key])} onChange={(e) => set(r.key, e.target.checked as never)} />
              <span className="settings-tier">T{r.tier}</span>
              <span className="settings-label">{r.label}</span>
            </label>
              ))}
              <div className="settings-group">Routing extras</div>
            </>
          )}
          {(showAdvanced || anyAdvancedOn) && ROWS.filter((r) => r.advanced).map((r) => (
            <label key={r.key} className="settings-row" title={r.help}>
              <input type="checkbox" aria-label={r.label} checked={Boolean(settings[r.key])} onChange={(e) => set(r.key, e.target.checked as never)} />
              <span className="settings-tier">T{r.tier}</span>
              <span className="settings-label">{r.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
