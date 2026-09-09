import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Toolbar from './Toolbar'

const base = { params: { file: 'a.sas', up: 1, down: 1 }, onParams: vi.fn(), onExpandAll: vi.fn(), onCollapseAll: vi.fn(), onFit: vi.fn(), onRelayout: vi.fn(), disabled: false }

describe('Toolbar', () => {
  it('steps up and down within 0..3', () => {
    const onParams = vi.fn()
    render(<Toolbar {...base} onParams={onParams} />)
    fireEvent.click(screen.getByRole('button', { name: 'more upstream' }))
    expect(onParams).toHaveBeenLastCalledWith({ file: 'a.sas', up: 2, down: 1 })
    fireEvent.click(screen.getByRole('button', { name: 'less downstream' }))
    expect(onParams).toHaveBeenLastCalledWith({ file: 'a.sas', up: 1, down: 0 })
  })
  it('never steps below 0', () => {
    const onParams = vi.fn()
    render(<Toolbar {...base} params={{ file: 'a.sas', up: 0, down: 1 }} onParams={onParams} />)
    fireEvent.click(screen.getByRole('button', { name: 'less upstream' }))
    expect(onParams).toHaveBeenLastCalledWith({ file: 'a.sas', up: 0, down: 1 })
  })
  it('wires the four action buttons and disables them when asked', () => {
    const { rerender } = render(<Toolbar {...base} />)
    fireEvent.click(screen.getByRole('button', { name: 'fit' }))
    fireEvent.click(screen.getByRole('button', { name: 're-layout' }))
    fireEvent.click(screen.getByRole('button', { name: 'expand all' }))
    fireEvent.click(screen.getByRole('button', { name: 'collapse all' }))
    expect(base.onFit).toHaveBeenCalled()
    expect(base.onRelayout).toHaveBeenCalled()
    expect(base.onExpandAll).toHaveBeenCalled()
    expect(base.onCollapseAll).toHaveBeenCalled()
    rerender(<Toolbar {...base} disabled />)
    expect(screen.getByRole('button', { name: 'fit' })).toBeDisabled()
  })
})
