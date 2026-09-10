import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { FlowNodeData } from '../toFlow'

/** File containers, macro wrappers and block clusters. A click on the title folds
 *  a file back to a file node or a block back to one box (App.onNodeClick). */
export default function GroupNode({ id, data }: NodeProps<Node<FlowNodeData>>) {
  const isFile = data.kind === 'fileCluster'
  const isBlock = data.kind === 'blockCluster'
  const collapsed = Boolean(data.collapsed)
  const [kindLabel, ...rest] = isBlock ? data.label.split(' · ') : ['', data.label]
  return (
    <div className={`rf-group kind-${data.kind}${collapsed ? ' collapsed' : ''}`} data-cid={`group:${data.kind}:${data.label}`}>
      <Handle type="target" position={Position.Left} className="rf-handle" />
      <div className="rf-group-title">
        {isBlock && kindLabel && <span className="rf-group-kind">{kindLabel}</span>}
        <span className="rf-group-name">{isBlock ? rest.join(' · ') : data.label}</span>
      </div>
      <Handle type="source" position={Position.Right} className="rf-handle" />
    </div>
  )
}
