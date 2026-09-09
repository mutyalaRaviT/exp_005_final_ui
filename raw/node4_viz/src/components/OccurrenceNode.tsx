import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { FlowNodeData } from '../toFlow'

export default function OccurrenceNode({ data }: NodeProps<Node<FlowNodeData>>) {
  return (
    <div className={`rf-occ ${data.occRole ?? ''}`} title={data.occRole ? `${data.occRole}: ${data.label}` : data.label}>
      <Handle type="target" position={Position.Left} className="rf-handle" />
      <span>{data.label}</span>
      <Handle type="source" position={Position.Right} className="rf-handle" />
    </div>
  )
}
