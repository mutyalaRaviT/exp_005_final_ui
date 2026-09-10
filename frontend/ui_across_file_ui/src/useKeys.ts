// The bench's single-letter keys. A key never fires while the caret is in an
// input, textarea or contenteditable — typing a table name must not toggle a drawer.
import { useEffect } from 'react'

function typing(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null
  if (!el || !el.tagName) return false
  const tag = el.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable
}

/** `map` is keyed by the literal key ('b', 'g', '?'); 'mod+j' means ⌘/Ctrl+J. */
export function useKeys(map: Record<string, () => void>): void {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (typing(e.target)) return
      const mod = e.metaKey || e.ctrlKey
      const name = mod ? `mod+${e.key.toLowerCase()}` : e.key
      const fn = map[name]
      if (!fn) return
      if (!mod && (e.altKey || e.metaKey || e.ctrlKey)) return
      e.preventDefault()
      fn()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [map])
}
