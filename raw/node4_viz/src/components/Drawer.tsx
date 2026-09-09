// A bench drawer: zero width when shut, `width` px when open, with a 6px grip on
// its inner edge. Same Sash drag maths as before — the grip is just where it lives now.
import type { ReactNode } from 'react'
import { useCallback, useRef } from 'react'

interface DrawerProps {
  side: 'left' | 'right'
  title: string
  hotkey: string
  open: boolean
  width: number
  onWidth: (px: number) => void
  onToggle: () => void
  children: ReactNode
}

export default function Drawer({ side, title, hotkey, open, width, onWidth, onToggle, children }: DrawerProps) {
  const last = useRef(0)
  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      last.current = e.clientX
      const onMove = (ev: MouseEvent) => {
        const d = ev.clientX - last.current
        last.current = ev.clientX
        if (d !== 0) onWidth(side === 'left' ? d : -d)
      }
      const onUp = () => {
        window.removeEventListener('mousemove', onMove)
        window.removeEventListener('mouseup', onUp)
      }
      window.addEventListener('mousemove', onMove)
      window.addEventListener('mouseup', onUp)
    },
    [onWidth, side],
  )

  return (
    <aside
      className={`drawer${side === 'right' ? ' right' : ''}${open ? ' open' : ''}`}
      id={side}
      data-cid={`drawer-${side}`}
      style={{ ['--w' as string]: `${width}px` }}
      aria-hidden={!open}
    >
      <div className="dh">
        <span>{title}</span>
        <kbd onClick={onToggle} title={`close ${title.toLowerCase()}`} data-cid={`drawer-${side}-key`}>{hotkey}</kbd>
      </div>
      <div className="db" data-cid={`drawer-${side}-body`}>{children}</div>
      <div className="grip" data-cid={`grip-${side}`} data-testid={`grip-${side}`} onMouseDown={onMouseDown} />
    </aside>
  )
}
