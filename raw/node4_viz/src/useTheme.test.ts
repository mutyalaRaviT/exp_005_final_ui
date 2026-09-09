import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute('data-theme') })
  afterEach(() => { localStorage.clear() })

  it('starts on system: no attribute, nothing stored', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('system')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })
  it('cycles system -> light -> dark -> system, stamping the attribute', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.cycle())
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    act(() => result.current.cycle())
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(localStorage.getItem('node4.theme')).toBe('dark')
    act(() => result.current.cycle())
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
    expect(localStorage.getItem('node4.theme')).toBe(null)
  })
  it('reads a remembered theme back on mount', () => {
    localStorage.setItem('node4.theme', 'dark')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})
