import { describe, expect, it } from 'vitest'
import { crossings, readability } from './readability'

const box = (x: number, y: number, w = 100, h = 30) => ({ x, y, w, h })
describe('readability', () => {
  it('a clean scene scores 100', () => {
    const s = readability({ nodes: [box(0, 0), box(300, 0)], labels: [{ rect: box(120, 40, 60, 12), text: 'carried' }], edges: [{ points: [{ x: 100, y: 15 }, { x: 300, y: 15 }] }] })
    expect(s).toEqual({ score: 100, labelOnBox: 0, labelOnLabel: 0, crossings: 0, longLabels: 0 })
  })
  it('a label on a box costs 4, on another label 3, a crossing 1, a long label 1', () => {
    const s = readability({
      nodes: [box(0, 0)],
      labels: [{ rect: box(10, 10, 60, 12), text: 'on the box' }, { rect: box(200, 100, 60, 12), text: 'a' }, { rect: box(230, 105, 60, 12), text: 'a label that is far too long to scan quickly' }],
      edges: [{ points: [{ x: 0, y: 0 }, { x: 100, y: 100 }] }, { points: [{ x: 0, y: 100 }, { x: 100, y: 0 }] }],
    })
    expect(s).toEqual({ score: 100 - 4 - 3 - 1 - 1, labelOnBox: 1, labelOnLabel: 1, crossings: 1, longLabels: 1 })
  })
  it('two column edges crossing count half; a column edge crossing a table edge counts whole', () => {
    const x = [{ x: 0, y: 0 }, { x: 100, y: 100 }], y = [{ x: 0, y: 100 }, { x: 100, y: 0 }]
    expect(crossings([{ points: x, column: true }, { points: y, column: true }])).toBe(0.5)
    expect(crossings([{ points: x, column: true }, { points: y }])).toBe(1)
  })
  it('crossings are capped so one busy canvas cannot go below zero on that alone', () => {
    const edges = Array.from({ length: 12 }, (_, i) => ({ points: [{ x: 0, y: i * 10 }, { x: 100, y: 110 - i * 10 }] }))
    expect(crossings(edges)).toBeGreaterThan(30)
    expect(readability({ nodes: [], labels: [], edges }).score).toBe(70)
  })
})
