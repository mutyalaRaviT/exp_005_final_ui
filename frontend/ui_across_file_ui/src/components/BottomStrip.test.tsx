import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import BottomStrip from './BottomStrip'

const tabs = [
  { key: 'code', label: 'Code', content: <p>the code</p> },
  { key: 'log', label: 'Log', content: <p>the log</p> },
]
const base = { tabs, open: true, min: false, height: 220, onToggleMin: vi.fn(), onClose: vi.fn(), onActive: vi.fn() }

describe('BottomStrip', () => {
  it('shows only the active tab body and marks its button pressed', () => {
    render(<BottomStrip {...base} active="log" />)
    expect(screen.getByText('the log')).toBeInTheDocument()
    expect(screen.queryByText('the code')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log' })).toHaveAttribute('aria-pressed', 'true')
  })
  it('reports a tab click', () => {
    const onActive = vi.fn()
    render(<BottomStrip {...base} active="code" onActive={onActive} />)
    fireEvent.click(screen.getByRole('button', { name: 'Log' }))
    expect(onActive).toHaveBeenCalledWith('log')
  })
  it('collapsed keeps the tabs but drops the height and the body', () => {
    const { container } = render(<BottomStrip {...base} active="code" min />)
    const el = container.querySelector('#bottom')!
    expect(el.className).toContain('min')
    expect(el.getAttribute('style') ?? '').not.toContain('height')
    expect(screen.getByRole('button', { name: 'Code' })).toBeInTheDocument()
  })
  it('shut renders without .open, so the frame row collapses', () => {
    const { container } = render(<BottomStrip {...base} active="code" open={false} />)
    expect(container.querySelector('#bottom')!.className).not.toContain('open')
  })
})
