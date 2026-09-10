import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Drawer from './Drawer'

const base = { side: 'left' as const, title: 'Files', hotkey: 'b', width: 270, onWidth: vi.fn(), onToggle: vi.fn() }

describe('Drawer', () => {
  it('carries its width as --w and only wears .open when open', () => {
    const { rerender, container } = render(<Drawer {...base} open><p>body</p></Drawer>)
    const el = container.querySelector('#left')!
    expect(el.className).toContain('open')
    expect(el.getAttribute('style')).toContain('--w: 270px')
    rerender(<Drawer {...base} open={false}><p>body</p></Drawer>)
    expect(container.querySelector('#left')!.className).not.toContain('open')
  })
  it('the header key shuts it', () => {
    const onToggle = vi.fn()
    render(<Drawer {...base} open onToggle={onToggle}><p>body</p></Drawer>)
    fireEvent.click(screen.getByText('b'))
    expect(onToggle).toHaveBeenCalled()
  })
  it('dragging the grip reports the pixel delta, sign-corrected per side', () => {
    const onWidth = vi.fn()
    const { rerender } = render(<Drawer {...base} open onWidth={onWidth}><p>b</p></Drawer>)
    fireEvent.mouseDown(screen.getByTestId('grip-left'), { clientX: 100 })
    fireEvent.mouseMove(window, { clientX: 130 })
    fireEvent.mouseUp(window)
    expect(onWidth).toHaveBeenLastCalledWith(30)

    // a right drawer grows when the mouse moves left, so the same gesture flips sign
    rerender(<Drawer {...base} side="right" open onWidth={onWidth}><p>b</p></Drawer>)
    fireEvent.mouseDown(screen.getByTestId('grip-right'), { clientX: 100 })
    fireEvent.mouseMove(window, { clientX: 130 })
    fireEvent.mouseUp(window)
    expect(onWidth).toHaveBeenLastCalledWith(-30)
  })
})
