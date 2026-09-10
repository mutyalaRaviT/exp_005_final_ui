// Layout settings the owner can toggle: tier 1 (ELK routing options), tier 2
// (keep the user's arrangement), tier 3 (follow the model order), tier 4
// (libavoid obstacle-avoiding routing), tier 5 (HOLA placement through the pyhola
// sidecar). Persisted per browser in localStorage.

export interface LayoutSettings {
  /** tier 1 — one trunk per source: elk.layered.mergeEdges + mergeHierarchyEdges */
  mergeEdges: boolean
  /** tier 1 — drop needless bends, favour straight edges, wider edge spacing */
  straighten: boolean
  /** tier 1 — every node gets a WEST in-port and an EAST out-port (FIXED_SIDE) */
  sidePorts: boolean
  /** tier 1 — ELK positions edge labels instead of our post-pass placer */
  elkLabels: boolean
  /** tier 1 — elk.layered.thoroughness (7 is ELK's default) */
  thoroughness: number
  /** tier 2 — semi-interactive: re-layout keeps the order the user dragged into */
  keepArrangement: boolean
  /** tier 3 — model order: files by run order, blocks in source order */
  followRunOrder: boolean
  /** tier 4 — route edges with libavoid around every box after ELK placement */
  avoidRouting: boolean
  /** tier 5 — HOLA (libdialect) places the top-level boxes and routes the edges between them; needs scripts/hola_server */
  holaLayout: boolean
  /** order — files sorted by name and pinned in that order, so +/− never shuffles them */
  stableOrder: boolean
  /** glide nodes to their new spot when the layout changes (d3 tween) */
  animate: boolean
  /** placement — how ELK assigns layers (columns) */
  layering: Layering
  /** placement — how ELK positions nodes inside a layer */
  nodePlacement: NodePlacement
  /** placement — a greedy post-pass that swaps neighbours to remove crossings */
  greedySwitch: boolean
  /** placement — pull nodes into earlier layers to shorten long edges */
  nodePromotion: boolean
  /** placement — post-compaction to shorten edges after placement */
  compaction: boolean
}

export type Layering = 'NETWORK_SIMPLEX' | 'LONGEST_PATH' | 'COFFMAN_GRAHAM' | 'MIN_WIDTH'
export type NodePlacement = 'NETWORK_SIMPLEX' | 'BRANDES_KOEPF' | 'LINEAR_SEGMENTS' | 'SIMPLE'
export const LAYERINGS: Layering[] = ['NETWORK_SIMPLEX', 'LONGEST_PATH', 'COFFMAN_GRAHAM', 'MIN_WIDTH']
export const NODE_PLACEMENTS: NodePlacement[] = ['NETWORK_SIMPLEX', 'BRANDES_KOEPF', 'LINEAR_SEGMENTS', 'SIMPLE']

// Owner's verdict (2026-09-07): merge + straighten + side ports + a high thoroughness are
// what helps; ELK labels, keep-arrangement, model order and libavoid did not earn their place.
export const DEFAULT_SETTINGS: LayoutSettings = {
  mergeEdges: true,
  straighten: true,
  sidePorts: true,
  elkLabels: false,
  thoroughness: 19,
  keepArrangement: false,
  followRunOrder: false,
  avoidRouting: false,
  holaLayout: false,
  stableOrder: true,
  animate: true,
  layering: 'NETWORK_SIMPLEX',
  nodePlacement: 'NETWORK_SIMPLEX',
  greedySwitch: false,
  nodePromotion: false,
  compaction: false,
}

export const STORAGE_KEY = 'node4_viz.layout'

/** Load persisted settings, tolerating a missing/garbled store and unknown keys. */
export function loadSettings(storage: Pick<Storage, 'getItem'> | null = safeStorage()): LayoutSettings {
  try {
    const raw = storage?.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    const parsed = JSON.parse(raw) as Partial<LayoutSettings>
    const out: LayoutSettings = { ...DEFAULT_SETTINGS }
    for (const k of Object.keys(DEFAULT_SETTINGS) as (keyof LayoutSettings)[]) {
      const v = parsed[k]
      if (typeof v === typeof DEFAULT_SETTINGS[k]) (out as unknown as Record<string, unknown>)[k] = v
    }
    out.thoroughness = Math.max(1, Math.min(30, Math.trunc(out.thoroughness)))
    if (!LAYERINGS.includes(out.layering)) out.layering = DEFAULT_SETTINGS.layering
    if (!NODE_PLACEMENTS.includes(out.nodePlacement)) out.nodePlacement = DEFAULT_SETTINGS.nodePlacement
    return out
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

export function saveSettings(s: LayoutSettings, storage: Pick<Storage, 'setItem'> | null = safeStorage()): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(s))
  } catch {
    // storage unavailable (private mode, quota): settings live for the session only
  }
}

function safeStorage(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

// ---- profiles: one click sets every toggle -------------------------------

export type ProfileId = 'simple' | 'medium' | 'best'

export interface Profile {
  id: ProfileId
  label: string
  /** one line shown under the segmented control */
  hint: string
  settings: LayoutSettings
}

export const PROFILES: Profile[] = [
  {
    id: 'simple',
    label: 'Simple',
    hint: 'Plain ELK, every edge on its own line. Fastest.',
    settings: { ...DEFAULT_SETTINGS, mergeEdges: false, straighten: false, sidePorts: false, thoroughness: 7 },
  },
  {
    id: 'medium',
    label: 'Medium',
    hint: 'Merged trunks, straight runs, side ports. The default.',
    settings: { ...DEFAULT_SETTINGS },
  },
  {
    id: 'best',
    label: 'Best',
    hint: 'Medium with the most thorough ELK pass. Slower on big graphs.',
    settings: { ...DEFAULT_SETTINGS, thoroughness: 30 },
  },
]

/** The profile whose settings match exactly, or 'custom'. */
export function profileOf(s: LayoutSettings): ProfileId | 'custom' {
  const keys = Object.keys(DEFAULT_SETTINGS) as (keyof LayoutSettings)[]
  const hit = PROFILES.find((p) => keys.every((k) => p.settings[k] === s[k]))
  return hit?.id ?? 'custom'
}

export function profileSettings(id: ProfileId): LayoutSettings {
  return { ...PROFILES.find((p) => p.id === id)!.settings }
}
