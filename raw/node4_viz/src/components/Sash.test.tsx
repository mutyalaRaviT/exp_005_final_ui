import { describe, expect, it, vi } from 'vitest'
import { render, fireEvent, screen } from '@testing-library/react'
import Sash from './Sash'

describe('Sash', () => {
  it('dragging horizontally reports the pixel delta via onDrag', () => {
    const onDrag = vi.fn()
    render(<Sash orientation="vertical" onDrag={onDrag} dataCid="sash-explorer" />)
    const sash = screen.getByTestId('sash-explorer')

    fireEvent.mouseDown(sash, { clientX: 100 })
    fireEvent.mouseMove(window, { clientX: 130 })
    expect(onDrag).toHaveBeenCalledWith(30)

    fireEvent.mouseMove(window, { clientX: 150 })
    expect(onDrag).toHaveBeenCalledWith(20)

    fireEvent.mouseUp(window)
    fireEvent.mouseMove(window, { clientX: 999 })
    expect(onDrag).toHaveBeenCalledTimes(2)
  })

  it('double-click calls onReset', () => {
    const onReset = vi.fn()
    render(<Sash orientation="horizontal" onDrag={vi.fn()} onReset={onReset} dataCid="sash-panel" />)
    fireEvent.doubleClick(screen.getByTestId('sash-panel'))
    expect(onReset).toHaveBeenCalledTimes(1)
  })
})
