// Typeahead search box: debounces keystrokes into searchHits(q) and shows
// table/file suggestions. Picking a suggestion hands the hit up to the
// parent, which loads its neighborhood (table -> file, or file -> file).
// The dropdown closes on pick, Escape, and clicks outside — and picking a
// hit does NOT re-open it (the box's new value is the pick, not a query).
// ArrowUp/Down + Enter walk and choose without the mouse.
import { useEffect, useRef, useState, type RefObject } from 'react'
import { searchHits, type SearchHit } from '../api'

interface SearchBarProps {
  onSelect: (hit: SearchHit) => void
  inputRef?: RefObject<HTMLInputElement | null>
}

const DEBOUNCE_MS = 150

function cidEnabled(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return new URLSearchParams(window.location.search).get('cid') === '1'
  } catch {
    return false
  }
}

export default function SearchBar({ onSelect, inputRef }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const requestId = useRef(0)
  /** the value the last pick wrote into the box — that text is a result,
   *  not a query, so seeing it again must not re-open the dropdown */
  const pickedValue = useRef<string | null>(null)
  const rootRef = useRef<HTMLDivElement | null>(null)
  const showCid = cidEnabled()

  useEffect(() => {
    const q = query.trim()
    if (!q || q === pickedValue.current) {
      setHits([])
      setOpen(false)
      setActive(-1)
      return
    }
    const id = ++requestId.current
    const timer = setTimeout(() => {
      searchHits(q)
        .then((result) => {
          if (requestId.current !== id) return
          setHits(result)
          setOpen(true)
          setActive(-1)
        })
        .catch(() => {
          if (requestId.current !== id) return
          setHits([])
          setOpen(true)
        })
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query])

  // A click anywhere outside the search bar closes the dropdown.
  useEffect(() => {
    if (!open) return
    function onDocMouseDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [open])

  function pick(hit: SearchHit) {
    pickedValue.current = hit.value
    setOpen(false)
    setActive(-1)
    setQuery(hit.value)
    onSelect(hit)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      setOpen(false)
      setActive(-1)
      return
    }
    if (!open || hits.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => (a + 1) % hits.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => (a <= 0 ? hits.length - 1 : a - 1))
    } else if (e.key === 'Enter' && active >= 0 && active < hits.length) {
      e.preventDefault()
      pick(hits[active])
    }
  }

  return (
    <div className="search-bar" data-cid="search-bar" ref={rootRef}>
      {showCid && <span className="cid-badge">3</span>}
      <input
        type="text"
        className="search-input"
        placeholder="search table or file..."
        value={query}
        data-cid="search-input"
        ref={inputRef}
        onChange={(e) => {
          if (e.target.value.trim() !== pickedValue.current) {
            pickedValue.current = null
          }
          setQuery(e.target.value)
        }}
        onKeyDown={onKeyDown}
        onFocus={() => hits.length > 0 && setOpen(true)}
      />
      {open && hits.length > 0 && (
        <ul className="search-suggestions" data-cid="search-suggestions">
          {hits.map((hit, i) => (
            <li
              key={`${hit.kind}:${hit.value}`}
              className={i === active ? 'search-suggestion active' : 'search-suggestion'}
              data-cid={`suggestion-${i + 1}`}
              onClick={() => pick(hit)}
            >
              {showCid && <span className="cid-badge">{i + 1}</span>}
              <span className={`kind-chip kind-${hit.kind}`}>{hit.kind}</span>
              <span className="suggestion-value">{hit.value}</span>
              <span className="suggestion-count">{hit.files.length}</span>
            </li>
          ))}
        </ul>
      )}
      {open && hits.length === 0 && query.trim() !== '' && (
        <div className="search-empty" data-cid="search-empty">
          no matches
        </div>
      )}
    </div>
  )
}
