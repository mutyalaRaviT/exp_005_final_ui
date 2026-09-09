import { describe, expect, it } from 'vitest'
import type { Edge } from '@xyflow/react'
import { placeLabels } from './labelPlacement'
import type { FlowEdgeData } from './toFlow'

function e(id: string, y: number): Edge<FlowEdgeData> {
  return { id, source: 's', target: 't', type: 'elk', data: { label: 'work.accounts', points: [{ x: 0, y }, { x: 200, y }, { x: 200, y: y + 60 }, { x: 400, y: y + 60 }] } }
}

describe('placeLabels', () => {
  it('gives every labelled edge a labelAt and no two label boxes overlap', () => {
    const out = placeLabels(Array.from({ length: 12 }, (_, i) => e(`x${i}`, i * 8)))
    const boxes = out.map((edge) => {
      const at = edge.data!.labelAt!
      const halfW = ('work.accounts'.length * 7) / 2
      return { x1: at.x - halfW, x2: at.x + halfW, y1: at.y - 7, y2: at.y + 7 }
    })
    for (let i = 0; i < boxes.length; i++)
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j]
        const overlap = a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2
        expect(overlap, `${i} vs ${j}`).toBe(false)
      }
  })
  it('leaves unlabelled edges untouched', () => {
    const edge: Edge<FlowEdgeData> = { id: 'u', source: 's', target: 't', data: { points: [{ x: 0, y: 0 }, { x: 10, y: 0 }] } }
    expect(placeLabels([edge])[0].data?.labelAt).toBeUndefined()
  })
})
