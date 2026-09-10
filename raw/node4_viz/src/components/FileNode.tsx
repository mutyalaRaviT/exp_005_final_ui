import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { FlowNodeData } from '../toFlow'
import { ROLE_FILL } from '../palette'

// No DOM onClick here: a mouse-up that ends a drag would fire it. App opens the
// file through React Flow's onNodeClick, which ignores drags; double click shows
// the connected ones.
export default function FileNode({ data }: NodeProps<Node<FlowNodeData>>) {
  const fileid = data.fileid ?? data.label
  const fill = ROLE_FILL[data.role ?? 'down']
  return (
    <div className={`rf-file role-${data.role ?? 'down'}`} style={{ background: fill }} data-cid={`file:${fileid}`}>
      <Handle type="target" position={Position.Left} className="rf-handle" />
      <div className="rf-file-label">{data.label}</div>
      {data.score !== undefined && <div className="rf-file-score">#{data.score}</div>}
      {data.cyclic && <span className="rf-cyclic" title="in a cycle" />}
      <Handle type="source" position={Position.Right} className="rf-handle" />
    </div>
  )
}
