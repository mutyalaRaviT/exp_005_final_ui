import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SettingsPanel from './SettingsPanel'
import { DEFAULT_SETTINGS, profileSettings } from '../layoutSettings'

describe('SettingsPanel', () => {
  it('opens on the gear, toggles a setting and reports the whole object', () => {
    const onChange = vi.fn()
    render(<SettingsPanel settings={DEFAULT_SETTINGS} onChange={onChange} />)
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'layout settings' }))
    // advanced toggles are hidden until asked for
    expect(screen.queryByLabelText('Obstacle-avoiding edges')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /advanced/i }))
    fireEvent.click(screen.getByLabelText('Obstacle-avoiding edges'))
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_SETTINGS, avoidRouting: true })
    fireEvent.click(screen.getByLabelText('HOLA placement (pyhola)'))
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_SETTINGS, holaLayout: true })
  })
  it('changes thoroughness through the slider', () => {
    const onChange = vi.fn()
    render(<SettingsPanel settings={DEFAULT_SETTINGS} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'layout settings' }))
    fireEvent.change(screen.getByLabelText('thoroughness'), { target: { value: '20' } })
    expect(onChange).toHaveBeenCalledWith({ ...DEFAULT_SETTINGS, thoroughness: 20 })
  })
  it('closes on Escape', () => {
    render(<SettingsPanel settings={DEFAULT_SETTINGS} onChange={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'layout settings' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
  })
  it('shows the matching profile and applies a profile in one click', () => {
    const onChange = vi.fn()
    render(<SettingsPanel settings={DEFAULT_SETTINGS} onChange={onChange} />)
    expect(screen.getByRole('button', { name: 'layout settings' })).toHaveTextContent('Medium')
    fireEvent.click(screen.getByRole('button', { name: 'layout settings' }))
    expect(screen.getByRole('radio', { name: 'Medium' })).toHaveAttribute('aria-checked', 'true')
    fireEvent.click(screen.getByRole('radio', { name: 'Best' }))
    expect(onChange).toHaveBeenCalledWith(profileSettings('best'))
  })
  it('labels hand-tuned toggles as Custom', () => {
    render(<SettingsPanel settings={{ ...DEFAULT_SETTINGS, thoroughness: 11 }} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'layout settings' })).toHaveTextContent('Custom')
  })
  it('exposes the placement group under Advanced', () => {
    const onChange = vi.fn()
    render(<SettingsPanel settings={DEFAULT_SETTINGS} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'layout settings' }))
    fireEvent.click(screen.getByRole('button', { name: /advanced/i }))
    fireEvent.change(screen.getByLabelText('layering'), { target: { value: 'COFFMAN_GRAHAM' } })
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_SETTINGS, layering: 'COFFMAN_GRAHAM' })
    fireEvent.click(screen.getByLabelText('Post-compaction'))
    expect(onChange).toHaveBeenLastCalledWith({ ...DEFAULT_SETTINGS, compaction: true })
  })
})
