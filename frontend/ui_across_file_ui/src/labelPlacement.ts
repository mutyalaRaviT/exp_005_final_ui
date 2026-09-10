import type { Edge } from '@xyflow/react'
import { computeEdgeLabelPlacements, type EdgeLabelInput } from './edgeLabels'
import type { FlowEdgeData } from './toFlow'

/** Run the copied collision-avoiding placer over the routed polylines and
 *  write the chosen box centre into each edge's data.labelAt. */
export function placeLabels(edges: Edge<FlowEdgeData>[]): Edge<FlowEdgeData>[] {
  const inputs: EdgeLabelInput[] = edges
    .filter((e) => e.data?.label && e.data.points.length >= 2 && !e.data.labelAt)
    .map((e) => {
      const pts = e.data!.points
      return { id: e.id, label: e.data!.label!, sx: pts[0].x, sy: pts[0].y, tx: pts[pts.length - 1].x, ty: pts[pts.length - 1].y, path: pts }
    })
  const byId = new Map(computeEdgeLabelPlacements(inputs, { charW: 7, lineH: 14, gap: 6 }).map((p) => [p.id, p]))
  return edges.map((e) => {
    const p = byId.get(e.id)
    if (!p || !e.data) return e
    return { ...e, data: { ...e.data, labelAt: { x: (p.box.x1 + p.box.x2) / 2, y: (p.box.y1 + p.box.y2) / 2 } } }
  })
}
