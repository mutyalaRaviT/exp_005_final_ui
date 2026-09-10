import { render, screen } from '@testing-library/react'
import { ReactFlowProvider, type NodeProps, type Node } from '@xyflow/react'
import { describe, expect, it } from 'vitest'
import FileNode from './FileNode'
import GroupNode from './GroupNode'
import OccurrenceNode from './OccurrenceNode'
import type { FlowNodeData } from '../toFlow'

// React Flow's NodeProps carry many fields; we only pass what the components read.
function props(data: FlowNodeData, id = 'n1'): NodeProps<Node<FlowNodeData>> {
  return { id, data, selected: false, type: 'x', dragging: false, zIndex: 0, isConnectable: false,
    positionAbsoluteX: 0, positionAbsoluteY: 0, width: 100, height: 40, draggable: true, selectable: true, deletable: false } as never
}

describe('FileNode', () => {
  it('shows label and run order, and no +/− button — the box itself is the toggle (App.onNodeClick)', () => {
    render(<ReactFlowProvider><FileNode {...props({ kind: 'file', label: '04_build_accounts.sas', fileid: 'ankitha_1/04_build_accounts.sas', role: 'seed', score: 1 })} /></ReactFlowProvider>)
    expect(screen.getByText('04_build_accounts.sas')).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('GroupNode', () => {
  it('a file cluster shows its title and no button', () => {
    render(<ReactFlowProvider><GroupNode {...props({ kind: 'fileCluster', label: 'a.sas', fileid: 'a.sas', expanded: true })} /></ReactFlowProvider>)
    expect(screen.getByText('a.sas')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })
  it('splits a block title into kind and id', () => {
    render(<ReactFlowProvider><GroupNode {...props({ kind: 'blockCluster', label: 'proc sql · b_2', fileid: 'a.sas' }, 'a.sas::b_2')} /></ReactFlowProvider>)
    expect(screen.getByText('proc sql')).toBeInTheDocument()
    expect(screen.getByText('b_2')).toBeInTheDocument()
  })
  it('marks a collapsed block', () => {
    render(<ReactFlowProvider><GroupNode {...props({ kind: 'blockCluster', label: 'data · b_1', fileid: 'a.sas', collapsed: true })} /></ReactFlowProvider>)
    expect(document.querySelector('.rf-group.collapsed')).not.toBeNull()
  })
})

describe('OccurrenceNode', () => {
  it('renders the table name with the occurrence role class', () => {
    const { container } = render(<ReactFlowProvider><OccurrenceNode {...props({ kind: 'occurrence', label: 'work.accounts', occRole: 'write' })} /></ReactFlowProvider>)
    expect(screen.getByText('work.accounts')).toBeInTheDocument()
    expect(container.querySelector('.rf-occ.write')).not.toBeNull()
  })
  it('opens to one row per column when columns are known', () => {
    const { container } = render(<ReactFlowProvider><OccurrenceNode {...props({ kind: 'occurrence', label: 'work.t', occRole: 'read', columns: ['a', 'b'] })} /></ReactFlowProvider>)
    expect(container.querySelector('.rf-occ.open')).not.toBeNull()
    expect([...container.querySelectorAll('.rf-col')].map((c) => c.textContent)).toEqual(['a', 'b'])
  })
})
