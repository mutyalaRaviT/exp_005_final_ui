import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { FlowNodeData } from '../toFlow'
import { ROLE_FILL } from '../palette'

export function emitToggle(fileid: string) {
  window.dispatchEvent(new CustomEvent('node4:toggle', { detail: { fileid } }))
}

// Picking a file (re-seeding on it) is NOT a DOM onClick here: a mouse-up
// that ends a drag would fire it and snap the graph back to a fresh layout.
// App handles picks through React Flow's onNodeClick, which ignores drags.
export default function FileNode({ data }: NodeProps<Node<FlowNodeData>>) {
  const fileid = data.fileid ?? data.label
  const fill = ROLE_FILL[data.role ?? 'down']
  return (
    <div className={`rf-file role-${data.role ?? 'down'}`} style={{ background: fill }} data-cid={`file:${fileid}`}>
      <Handle type="target" position={Position.Left} className="rf-handle" />
      <div className="rf-file-label">{data.label}</div>
      {data.score !== undefined && <div className="rf-file-score">#{data.score}</div>}
      {data.cyclic && <span className="rf-cyclic" title="in a cycle" />}
      <button
        type="button"
        className="rf-toggle nodrag"
        aria-label="+"
        title="expand into blocks and tables"
        onClick={(e) => {
          e.stopPropagation()
          emitToggle(fileid)
        }}
      >
        +
      </button>
      <Handle type="source" position={Position.Right} className="rf-handle" />
    </div>
  )
}
