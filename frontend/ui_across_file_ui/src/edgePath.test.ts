import { describe, expect, it } from 'vitest'
import { pointsToPath } from './edgePath'

describe('pointsToPath', () => {
  it('draws a straight line for two points', () => {
    expect(pointsToPath([{ x: 0, y: 0 }, { x: 100, y: 0 }])).toBe('M 0 0 L 100 0')
  })
  it('rounds every interior corner with a quadratic curve', () => {
    const d = pointsToPath([{ x: 0, y: 0 }, { x: 50, y: 0 }, { x: 50, y: 40 }], 8)
    expect(d).toBe('M 0 0 L 42 0 Q 50 0 50 8 L 50 40')
  })
  it('clamps the radius to half the shorter neighbouring segment', () => {
    const d = pointsToPath([{ x: 0, y: 0 }, { x: 6, y: 0 }, { x: 6, y: 40 }], 8)
    expect(d).toBe('M 0 0 L 3 0 Q 6 0 6 3 L 6 40')
  })
  it('returns an empty string for fewer than two points', () => {
    expect(pointsToPath([{ x: 1, y: 1 }])).toBe('')
  })
})
