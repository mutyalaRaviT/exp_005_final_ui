import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Rail, { RAIL_ICONS } from './Rail'

describe('Rail', () => {
  it('prints each panel key and marks the on one pressed', () => {
    render(<Rail items={[
      { key: 'files', title: 'Files (b)', icon: RAIL_ICONS.files, on: true, onClick: vi.fn() },
      { key: 'log', title: 'Log (l)', icon: RAIL_ICONS.log, onClick: vi.fn() },
    ]} />)
    expect(screen.getByText('f')).toBeInTheDocument()
    expect(screen.getByText('l')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Files (b)' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Log (l)' })).toHaveAttribute('aria-pressed', 'false')
  })
  it('clicks through, and a disabled button does not', () => {
    const onClick = vi.fn()
    const dead = vi.fn()
    render(<Rail items={[
      { key: 'files', title: 'Files', icon: RAIL_ICONS.files, onClick },
      { key: 'graph', title: 'Graph', icon: RAIL_ICONS.graph, disabled: true, onClick: dead },
    ]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Files' }))
    fireEvent.click(screen.getByRole('button', { name: 'Graph' }))
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(dead).not.toHaveBeenCalled()
  })
})
