import { describe, expect, it } from 'vitest'
import type { Node } from '@xyflow/react'
import { interpolateNodes, tweenNodes } from './animateLayout'

const n = (id: string, x: number, y: number, parentId?: string): Node => ({ id, position: { x, y }, data: {}, parentId })

describe('interpolateNodes', () => {
  const prev = [n('a', 0, 0), n('b', 100, 100)]
  const next = [n('a', 200, 0), n('b', 100, 100), n('c', 50, 50)]
  it('starts at the old positions and ends at the new ones', () => {
    const start = interpolateNodes(prev, next, 0)
    expect(start.find((x) => x.id === 'a')!.position).toEqual({ x: 0, y: 0 })
    const end = interpolateNodes(prev, next, 1)
    expect(end.find((x) => x.id === 'a')!.position).toEqual({ x: 200, y: 0 })
    expect(end.find((x) => x.id === 'c')!.style?.opacity).toBeUndefined()
  })
  it('moves monotonically and fades new nodes in', () => {
    const mid = interpolateNodes(prev, next, 0.5)
    const a = mid.find((x) => x.id === 'a')!.position.x
    expect(a).toBeGreaterThan(0)
    expect(a).toBeLessThan(200)
    expect(mid.find((x) => x.id === 'c')!.style?.opacity).toBeCloseTo(0.5, 5)
    // an unmoved node is returned as-is
    expect(mid.find((x) => x.id === 'b')).toBe(next[1])
  })
  it('re-parented nodes appear rather than glide across containers', () => {
    const moved = interpolateNodes([n('x', 0, 0)], [n('x', 10, 10, 'p')], 0.5)
    expect(moved[0].position).toEqual({ x: 10, y: 10 })
    expect(moved[0].style?.opacity).toBeCloseTo(0.5, 5)
  })
})

describe('tweenNodes', () => {
  it('applies the target immediately with no duration or no previous nodes', () => {
    const seen: Node[][] = []
    tweenNodes([], [n('a', 1, 1)], (x) => seen.push(x), { duration: 400 })
    tweenNodes([n('a', 0, 0)], [n('a', 1, 1)], (x) => seen.push(x), { duration: 0 })
    expect(seen).toHaveLength(2)
    expect(seen[0][0].position).toEqual({ x: 1, y: 1 })
  })
  it('ends exactly on the target after the duration', async () => {
    const seen: Node[][] = []
    tweenNodes([n('a', 0, 0)], [n('a', 100, 0)], (x) => seen.push(x), { duration: 60 })
    await new Promise((r) => setTimeout(r, 200))
    expect(seen.length).toBeGreaterThan(1)
    expect(seen[seen.length - 1][0].position).toEqual({ x: 100, y: 0 })
  })
})

import { keepMeasured } from './animateLayout'

describe('keepMeasured', () => {
  it('copies React Flow measured sizes onto fresh node objects, by id, without overriding ones that have them', () => {
    const cur = [
      { id: 'a', position: { x: 0, y: 0 }, data: {}, measured: { width: 100, height: 40 } },
      { id: 'b', position: { x: 0, y: 0 }, data: {} },
    ]
    const next = [
      { id: 'a', position: { x: 5, y: 5 }, data: {} },
      { id: 'b', position: { x: 6, y: 6 }, data: {} },
      { id: 'c', position: { x: 7, y: 7 }, data: {}, measured: { width: 1, height: 1 } },
    ]
    const out = keepMeasured(next, cur)
    expect(out[0].measured).toEqual({ width: 100, height: 40 })
    expect(out[0].position).toEqual({ x: 5, y: 5 })
    expect(out[1].measured).toBeUndefined()
    expect(out[2].measured).toEqual({ width: 1, height: 1 })
    expect(out[2]).toBe(next[2]) // untouched objects keep identity (React Flow's equality shortcut)
  })
})
