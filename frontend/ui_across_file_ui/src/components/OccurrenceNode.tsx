import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { FlowNodeData } from '../toFlow'

/** A table inside a block. A click opens it — one row per column the code
 *  names (tableColumns.ts) — and a click again folds it (App.onNodeClick). */
export default function OccurrenceNode({ data }: NodeProps<Node<FlowNodeData>>) {
  const open = data.columns !== undefined
  const cols = data.columns ?? []
  return (
    <div
      className={`rf-occ ${data.occRole ?? ''}${open ? ' open' : ''}`}
      title={open ? 'click to fold the columns · double click to show what it connects to' : `${data.occRole ? `${data.occRole}: ` : ''}${data.label} — click for its columns`}
    >
      <Handle type="target" position={Position.Left} className="rf-handle" />
      <div className="rf-occ-hd"><span>{data.label}</span></div>
      {open && (
        <div className="rf-occ-cols">
          {cols.length === 0 && <div className="rf-col none">no columns known</div>}
          {cols.map((c) => (
            <div key={c} className="rf-col" data-col={c}>
              <Handle type="target" id={`col:${c}`} position={Position.Left} className="rf-handle rf-col-handle" />
              {c}
              <Handle type="source" id={`col:${c}`} position={Position.Right} className="rf-handle rf-col-handle" />
            </div>
          ))}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="rf-handle" />
    </div>
  )
}
