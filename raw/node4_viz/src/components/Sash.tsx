// A 4px draggable divider, VS Code style: `vertical` resizes something to
// its left/right (tracks clientX), `horizontal` resizes something above/
// below (tracks clientY). Reports the pixel delta since the last move so
// the parent can add it straight onto its own px size state. Double-click
// resets to the caller's default.
import { useCallback, useRef } from 'react'

interface SashProps {
  orientation: 'vertical' | 'horizontal'
  onDrag: (deltaPx: number) => void
  onReset?: () => void
  dataCid: string
}

export default function Sash({ orientation, onDrag, onReset, dataCid }: SashProps) {
  const lastPos = useRef(0)

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      lastPos.current = orientation === 'vertical' ? e.clientX : e.clientY

      function onMouseMove(ev: MouseEvent) {
        const pos = orientation === 'vertical' ? ev.clientX : ev.clientY
        const delta = pos - lastPos.current
        lastPos.current = pos
        if (delta !== 0) onDrag(delta)
      }
      function onMouseUp() {
        window.removeEventListener('mousemove', onMouseMove)
        window.removeEventListener('mouseup', onMouseUp)
      }
      window.addEventListener('mousemove', onMouseMove)
      window.addEventListener('mouseup', onMouseUp)
    },
    [orientation, onDrag],
  )

  return (
    <div
      className={`sash sash-${orientation}`}
      data-cid={dataCid}
      data-testid={dataCid}
      onMouseDown={onMouseDown}
      onDoubleClick={() => onReset?.()}
    />
  )
}
