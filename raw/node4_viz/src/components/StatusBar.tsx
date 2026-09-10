// The bench's 26px status line: mode, what is focused, which engine drew it,
// then the key hints. Reading order matches bench.html's #status exactly.
interface StatusBarProps {
  focusInfo: string
  engineInfo: string
  keys: { k: string; label: string }[]
  /** 0–100, from readability.ts; the title says what cost points */
  readability?: { score: number; labelOnBox: number; labelOnLabel: number; crossings: number; longLabels: number } | null
}

export default function StatusBar({ focusInfo, engineInfo, keys, readability }: StatusBarProps) {
  return (
    <div id="status" data-cid="status-bar">
      <span className="mode" data-cid="status-mode">GRAPH</span>
      <span className="mono" data-cid="status-focus">{focusInfo}</span>
      <span className="mono" data-cid="status-engine">{engineInfo}</span>
      {readability && (
        <span className="mono" data-cid="status-readability" title={`labels on boxes ${readability.labelOnBox} · labels on labels ${readability.labelOnLabel} · crossings ${readability.crossings} · long labels ${readability.longLabels}`}>
          readability {readability.score}
        </span>
      )}
      <div className="keys">
        {keys.map((h) => (
          <span key={h.k}><kbd>{h.k}</kbd> {h.label}</span>
        ))}
      </div>
    </div>
  )
}
