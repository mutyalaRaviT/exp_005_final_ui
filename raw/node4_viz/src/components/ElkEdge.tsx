import { BaseEdge, EdgeLabelRenderer, Position, getBezierPath, getSmoothStepPath, type EdgeProps, type Edge } from '@xyflow/react'
import { LABEL_MAX } from '../readability'
import type { FlowEdgeData } from '../toFlow'
import { pointsToPath } from '../edgePath'
import { EDGE_FACT, EDGE_HIGHLIGHT, EDGE_INFERRED } from '../palette'

/** px a handle may drift from its ELK anchor before the edge stops following the routed polyline */
const DRIFT_PX = 2

/** true when either endpoint's node has been dragged away from where ELK placed it */
export function hasMoved(
  anchors: FlowEdgeData['anchors'],
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
): boolean {
  if (!anchors) return false
  return (
    Math.abs(anchors.sx - sourceX) > DRIFT_PX ||
    Math.abs(anchors.sy - sourceY) > DRIFT_PX ||
    Math.abs(anchors.tx - targetX) > DRIFT_PX ||
    Math.abs(anchors.ty - targetY) > DRIFT_PX
  )
}

export default function ElkEdge({ id, data, markerEnd, sourceX, sourceY, targetX, targetY }: EdgeProps<Edge<FlowEdgeData>>) {
  const routed = data?.points && data.points.length >= 2 && !data.column ? data.points : undefined
  const moved = hasMoved(data?.anchors, sourceX, sourceY, targetX, targetY)
  let path: string
  let at: { x: number; y: number }
  if (routed && !moved) {
    path = pointsToPath(routed, 8)
    at = data?.labelAt ?? routed[Math.floor(routed.length / 2)]
  } else if (data?.column) {
    // a column edge: its own curve from row to row, so ten of them do not share one channel
    const [d, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition: Position.Right, targetPosition: Position.Left, curvature: 0.35 })
    path = d
    at = { x: labelX, y: labelY }
  } else {
    // a node was dragged (or ELK gave no route): follow the live handles
    const [d, labelX, labelY] = getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      borderRadius: 8,
    })
    path = d
    at = { x: labelX, y: labelY }
  }
  const inferred = data?.fact === false
  const hi = Boolean(data?.highlight)
  const ghost = Boolean(data?.ghost)
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={hi
          ? { stroke: EDGE_HIGHLIGHT, strokeWidth: ghost ? 2.5 : 3, strokeDasharray: ghost ? '8 6' : undefined, opacity: ghost ? 0.85 : 1, filter: 'drop-shadow(0 0 3px rgba(34,114,180,.45))' }
          : { stroke: inferred ? EDGE_INFERRED : EDGE_FACT, strokeWidth: data?.column ? 1 : inferred ? 1.2 : 1.5, strokeDasharray: inferred ? '5 4' : undefined, opacity: data?.column ? 0.75 : 1 }}
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div className={`${hi ? 'rf-edge-label rf-edge-label-hi' : 'rf-edge-label'}${data?.column ? ' rf-edge-label-col' : ''}`} style={{ transform: `translate(-50%, -50%) translate(${at.x}px, ${at.y}px)` }} title={data.why ?? data.label}>
            {data.label.length > LABEL_MAX ? data.label.slice(0, LABEL_MAX - 1) + '…' : data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
