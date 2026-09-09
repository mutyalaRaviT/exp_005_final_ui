// The bench's 26px status line: mode, what is focused, which engine drew it,
// then the key hints. Reading order matches bench.html's #status exactly.
interface StatusBarProps {
  focusInfo: string
  engineInfo: string
  keys: { k: string; label: string }[]
}

export default function StatusBar({ focusInfo, engineInfo, keys }: StatusBarProps) {
  return (
    <div id="status" data-cid="status-bar">
      <span className="mode" data-cid="status-mode">GRAPH</span>
      <span className="mono" data-cid="status-focus">{focusInfo}</span>
      <span className="mono" data-cid="status-engine">{engineInfo}</span>
      <div className="keys">
        {keys.map((h) => (
          <span key={h.k}><kbd>{h.k}</kbd> {h.label}</span>
        ))}
      </div>
    </div>
  )
}
