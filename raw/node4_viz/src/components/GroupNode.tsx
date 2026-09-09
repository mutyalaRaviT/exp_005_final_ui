import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { FlowNodeData } from '../toFlow'
import { emitToggle } from './FileNode'

export function emitToggleBlock(id: string) {
  window.dispatchEvent(new CustomEvent('node4:toggleBlock', { detail: { id } }))
}

/** File containers, macro wrappers and block clusters. Files collapse back to
 *  a file node (−); blocks fold their tables into one box (−) and unfold (+). */
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
      {isFile && (
        <button
          type="button"
          className="rf-toggle nodrag"
          aria-label="−"
          title="collapse back to a file"
          onClick={(e) => {
            e.stopPropagation()
            emitToggle(data.fileid ?? data.label)
          }}
        >
          −
        </button>
      )}
      {isBlock && (
        <button
          type="button"
          className="rf-toggle nodrag"
          aria-label={collapsed ? '+' : '−'}
          title={collapsed ? 'show the tables in this block' : 'fold the tables into the block'}
          onClick={(e) => {
            e.stopPropagation()
            emitToggleBlock(id)
          }}
        >
          {collapsed ? '+' : '−'}
        </button>
      )}
      <Handle type="source" position={Position.Right} className="rf-handle" />
    </div>
  )
}
