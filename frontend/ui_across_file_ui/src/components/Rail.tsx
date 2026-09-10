// The bench's 44px icon rail: one button per panel, its key printed in the corner.
// Icons are the bench's own 24x24 stroked paths (raw/bench_stack/server/bench.html).
import type { ReactNode } from 'react'

export interface RailItem {
  key: string
  title: string
  icon: ReactNode
  on?: boolean
  disabled?: boolean
  onClick?: () => void
  /** push this button (and the ones after it) to the bottom of the rail */
  spacer?: boolean
}

export const RAIL_ICONS: Record<string, ReactNode> = {
  project: (<svg viewBox="0 0 24 24"><rect x="3" y="4" width="7" height="6" rx="1" /><rect x="14" y="14" width="7" height="6" rx="1" /><rect x="3" y="14" width="7" height="6" rx="1" /><path d="M10 7h4a3 3 0 0 1 3 3v4" /></svg>),
  graph: (<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="12" r="2.5" /><circle cx="6" cy="18" r="2.5" /><path d="M8 7l8 4M8 17l8-4" /></svg>),
  files: (<svg viewBox="0 0 24 24"><path d="M3 6h6l2 2h10v11H3z" /></svg>),
  settings: (<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" /></svg>),
  code: (<svg viewBox="0 0 24 24"><path d="M9 8l-4 4 4 4M15 8l4 4-4 4" /></svg>),
  edges: (<svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="8" cy="6" r="1.6" /><circle cx="16" cy="12" r="1.6" /><circle cx="8" cy="18" r="1.6" /></svg>),
  log: (<svg viewBox="0 0 24 24"><path d="M4 5h16v14H4zM7 9l3 3-3 3M12 15h5" /></svg>),
  help: (<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01" /></svg>),
}

export default function Rail({ items }: { items: RailItem[] }) {
  return (
    <nav id="rail" aria-label="panels" data-cid="rail">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          data-panel={it.key}
          data-cid={`rail-${it.key}`}
          className={`${it.on ? 'on' : ''}${it.spacer ? ' spacer' : ''}`.trim() || undefined}
          title={it.title}
          aria-label={it.title}
          aria-pressed={it.on ?? false}
          disabled={it.disabled}
          onClick={it.onClick}
        >
          {it.icon}
          <kbd>{it.key === 'help' ? '?' : it.key[0]}</kbd>
        </button>
      ))}
    </nav>
  )
}
