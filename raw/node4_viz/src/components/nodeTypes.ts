import type { EdgeTypes, NodeTypes } from '@xyflow/react'
import FileNode from './FileNode'
import GroupNode from './GroupNode'
import OccurrenceNode from './OccurrenceNode'
import ElkEdge from './ElkEdge'

export const nodeTypes: NodeTypes = { file: FileNode, cluster: GroupNode, occurrence: OccurrenceNode }
export const edgeTypes: EdgeTypes = { elk: ElkEdge }
