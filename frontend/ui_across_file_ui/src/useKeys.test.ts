import { renderHook } from '@testing-library/react'
import { fireEvent } from '@testing-library/dom'
import { describe, expect, it, vi } from 'vitest'
import { useKeys } from './useKeys'

describe('useKeys', () => {
  it('fires the mapped key', () => {
    const b = vi.fn()
    renderHook(() => useKeys({ b }))
    fireEvent.keyDown(window, { key: 'b' })
    expect(b).toHaveBeenCalledTimes(1)
  })
  it('stays silent while the caret is in an input', () => {
    const b = vi.fn()
    renderHook(() => useKeys({ b }))
    const input = document.createElement('input')
    document.body.appendChild(input)
    fireEvent.keyDown(input, { key: 'b' })
    expect(b).not.toHaveBeenCalled()
    input.remove()
  })
  it('matches mod+j on either ⌘ or Ctrl, and a bare j is not mod+j', () => {
    const j = vi.fn()
    renderHook(() => useKeys({ 'mod+j': j }))
    fireEvent.keyDown(window, { key: 'j' })
    expect(j).not.toHaveBeenCalled()
    fireEvent.keyDown(window, { key: 'j', metaKey: true })
    fireEvent.keyDown(window, { key: 'j', ctrlKey: true })
    expect(j).toHaveBeenCalledTimes(2)
  })
  it('ignores an unmapped key', () => {
    const b = vi.fn()
    renderHook(() => useKeys({ b }))
    fireEvent.keyDown(window, { key: 'z' })
    expect(b).not.toHaveBeenCalled()
  })
})
