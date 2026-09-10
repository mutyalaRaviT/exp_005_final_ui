// Left sidebar file tree, VS Code style — folder-grouped, collapsible, with a
// filter box at the top.
//
// It has TWO layers, because a search is only useful if what it found stays
// put:
//
//   CURRENT     the working set — the files of the active (or pinned)
//               neighborhood. Only shown while there IS one.
//   ALL FILES   every indexed file (api.files()), always available, so the
//               explorer is never a dead end when a neighborhood is narrow.
//
// One filter box narrows both layers at once, and each layer (and each folder
// inside it) collapses on its own.
import { useMemo, useState, type RefObject } from 'react'

export interface TreeFile {
  id: string
  label: string
  folder: string
}

type LayerName = 'current' | 'all'

interface ExplorerTreeProps {
  /** the active/pinned neighborhood's files — empty when there is none */
  current: TreeFile[]
  /** every indexed file */
  all: TreeFile[]
  onPick: (fileid: string) => void
  filter: string
  onFilterChange: (v: string) => void
  filterInputRef?: RefObject<HTMLInputElement | null>
  selected?: string | null
  showCid?: boolean
}

/** Files matching the filter, grouped by folder, both sorted by name. */
function groupFiles(files: TreeFile[], filter: string): [string, TreeFile[]][] {
  const q = filter.trim().toLowerCase()
  const matched = q
    ? files.filter(
        (f) => f.label.toLowerCase().includes(q) || f.folder.toLowerCase().includes(q),
      )
    : files
  const byFolder = new Map<string, TreeFile[]>()
  for (const f of [...matched].sort((a, b) => a.label.localeCompare(b.label))) {
    const list = byFolder.get(f.folder) ?? []
    list.push(f)
    byFolder.set(f.folder, list)
  }
  return [...byFolder.entries()].sort(([a], [b]) => a.localeCompare(b))
}

export default function ExplorerTree({
  current,
  all,
  onPick,
  filter,
  onFilterChange,
  filterInputRef,
  selected,
  showCid,
}: ExplorerTreeProps) {
  // folder keys are namespaced by layer, so collapsing `ankitha_1` under
  // CURRENT never also collapses it under ALL FILES
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set())
  const [collapsedLayers, setCollapsedLayers] = useState<Set<LayerName>>(new Set())

  const currentGroups = useMemo(() => groupFiles(current, filter), [current, filter])
  const allGroups = useMemo(() => groupFiles(all, filter), [all, filter])

  function toggleFolder(key: string) {
    setCollapsedFolders((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function toggleLayer(layer: LayerName) {
    setCollapsedLayers((prev) => {
      const next = new Set(prev)
      if (next.has(layer)) next.delete(layer)
      else next.add(layer)
      return next
    })
  }

  function renderLayer(
    layer: LayerName,
    title: string,
    groups: [string, TreeFile[]][],
    count: number,
    emptyNote: string,
  ) {
    const layerCollapsed = collapsedLayers.has(layer)
    return (
      <div className="explorer-layer" data-cid={`explorer-layer-${layer}`}>
        <div
          className="explorer-layer-header"
          data-cid={`layer-toggle-${layer}`}
          onClick={() => toggleLayer(layer)}
        >
          <span className={`chevron${layerCollapsed ? ' collapsed' : ''}`}>▾</span>
          <span className="explorer-layer-name">{title}</span>
          <span className="explorer-layer-count">{count}</span>
        </div>
        {!layerCollapsed && (
          <div className="explorer-groups" data-cid={`explorer-groups-${layer}`}>
            {groups.length === 0 && <div className="empty-note">{emptyNote}</div>}
            {groups.map(([folder, items]) => {
              const key = `${layer}:${folder}`
              const folderCollapsed = collapsedFolders.has(key)
              return (
                <div
                  key={key}
                  className="explorer-group"
                  data-cid={`explorer-folder-${layer}-${folder}`}
                >
                  <div
                    className="explorer-folder"
                    data-cid={`folder-toggle-${layer}-${folder}`}
                    onClick={() => toggleFolder(key)}
                  >
                    <span className={`chevron${folderCollapsed ? ' collapsed' : ''}`}>▾</span>
                    <span className="folder-name">{folder}</span>
                  </div>
                  {!folderCollapsed &&
                    items.map((f) => (
                      <div
                        key={f.id}
                        className={`explorer-file${selected === f.id ? ' active' : ''}`}
                        data-cid={`explorer-file-${layer}-${f.id}`}
                        onClick={() => onPick(f.id)}
                      >
                        {f.label}
                      </div>
                    ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="explorer-tree" data-cid="explorer">
      {showCid && <span className="cid-badge">7</span>}
      <div className="section-label">Explorer</div>
      <input
        type="text"
        className="explorer-filter"
        data-cid="explorer-filter"
        placeholder="filter files..."
        value={filter}
        ref={filterInputRef}
        onChange={(e) => onFilterChange(e.target.value)}
      />
      {/* ALL FILES above, CURRENT below, split at the golden ratio; each layer
          scrolls on its own so a long index never pushes the working set away */}
      <div className={`explorer-layers${current.length > 0 ? ' split' : ''}`} data-cid="explorer-layers">
        {renderLayer('all', 'All Files', allGroups, all.length, 'no files indexed yet')}
        {current.length > 0 &&
          renderLayer(
            'current',
            'Current',
            currentGroups,
            current.length,
            'no file in the working set matches',
          )}
      </div>
    </div>
  )
}
