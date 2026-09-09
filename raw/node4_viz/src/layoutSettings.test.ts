import { describe, expect, it } from 'vitest'
import { DEFAULT_SETTINGS, STORAGE_KEY, loadSettings, saveSettings } from './layoutSettings'

function memStorage(initial: Record<string, string> = {}) {
  const m = new Map(Object.entries(initial))
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), dump: () => m }
}

describe('layoutSettings', () => {
  it('returns defaults with no store or a garbled store', () => {
    expect(loadSettings(null)).toEqual(DEFAULT_SETTINGS)
    expect(loadSettings(memStorage({ [STORAGE_KEY]: '{not json' }))).toEqual(DEFAULT_SETTINGS)
  })
  it('round-trips and ignores unknown or wrongly typed keys', () => {
    const s = memStorage()
    saveSettings({ ...DEFAULT_SETTINGS, avoidRouting: true, thoroughness: 15 }, s)
    expect(loadSettings(s)).toEqual({ ...DEFAULT_SETTINGS, avoidRouting: true, thoroughness: 15 })
    s.setItem(STORAGE_KEY, JSON.stringify({ mergeEdges: 'yes', bogus: 1, thoroughness: 99 }))
    const loaded = loadSettings(s)
    expect(loaded.mergeEdges).toBe(DEFAULT_SETTINGS.mergeEdges)
    expect(loaded.thoroughness).toBe(30)
    expect('bogus' in loaded).toBe(false)
    s.setItem(STORAGE_KEY, JSON.stringify({ layering: 'NOPE', nodePlacement: 'BRANDES_KOEPF' }))
    expect(loadSettings(s).layering).toBe('NETWORK_SIMPLEX')
    expect(loadSettings(s).nodePlacement).toBe('BRANDES_KOEPF')
  })
})

import { PROFILES, profileOf, profileSettings } from './layoutSettings'

describe('profiles', () => {
  it('every profile round-trips through profileOf', () => {
    for (const p of PROFILES) expect(profileOf(profileSettings(p.id))).toBe(p.id)
  })
  it('the defaults are the Medium profile and a hand edit becomes custom', () => {
    expect(profileOf(DEFAULT_SETTINGS)).toBe('medium')
    expect(profileOf({ ...DEFAULT_SETTINGS, thoroughness: 11 })).toBe('custom')
  })
  it('profiles get progressively more thorough and none turns on the advanced toggles', () => {
    const t = (id: 'simple' | 'medium' | 'best') => profileSettings(id).thoroughness
    expect(t('simple')).toBeLessThan(t('medium'))
    expect(t('medium')).toBeLessThan(t('best'))
    for (const p of PROFILES) {
      expect(p.settings.avoidRouting).toBe(false)
      expect(p.settings.holaLayout).toBe(false)
      expect(p.settings.keepArrangement).toBe(false)
      expect(p.settings.elkLabels).toBe(false)
    }
  })
})
