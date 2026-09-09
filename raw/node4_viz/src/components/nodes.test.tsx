import { fireEvent, render, screen } from '@testing-library/react'
import { ReactFlowProvider, type NodeProps, type Node } from '@xyflow/react'
import { describe, expect, it, vi } from 'vitest'
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
  it('shows label, run order and a + toggle that emits node4:toggle', () => {
    const spy = vi.fn()
    window.addEventListener('node4:toggle', spy as EventListener, { once: true })
    render(<ReactFlowProvider><FileNode {...props({ kind: 'file', label: '04_build_accounts.sas', fileid: 'ankitha_1/04_build_accounts.sas', role: 'seed', score: 1 })} /></ReactFlowProvider>)
    expect(screen.getByText('04_build_accounts.sas')).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '+' }))
    expect((spy.mock.calls[0][0] as CustomEvent).detail).toEqual({ fileid: 'ankitha_1/04_build_accounts.sas' })
  })
})

describe('GroupNode', () => {
  it('shows a − toggle only for fileCluster', () => {
    render(<ReactFlowProvider><GroupNode {...props({ kind: 'fileCluster', label: 'a.sas', fileid: 'a.sas', expanded: true })} /></ReactFlowProvider>)
    expect(screen.getByRole('button', { name: '−' })).toBeInTheDocument()
  })
  it('splits a block title into kind and id and offers a − toggle that emits node4:toggleBlock', () => {
    const spy = vi.fn()
    window.addEventListener('node4:toggleBlock', spy as EventListener, { once: true })
    render(<ReactFlowProvider><GroupNode {...props({ kind: 'blockCluster', label: 'proc sql · b_2', fileid: 'a.sas' }, 'a.sas::b_2')} /></ReactFlowProvider>)
    expect(screen.getByText('proc sql')).toBeInTheDocument()
    expect(screen.getByText('b_2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '−' }))
    expect((spy.mock.calls[0][0] as CustomEvent).detail).toEqual({ id: 'a.sas::b_2' })
  })
  it('shows + on a collapsed block', () => {
    render(<ReactFlowProvider><GroupNode {...props({ kind: 'blockCluster', label: 'data · b_1', fileid: 'a.sas', collapsed: true })} /></ReactFlowProvider>)
    expect(screen.getByRole('button', { name: '+' })).toBeInTheDocument()
    expect(document.querySelector('.rf-group.collapsed')).not.toBeNull()
  })
})

describe('OccurrenceNode', () => {
  it('renders the table name with the occurrence role class', () => {
    const { container } = render(<ReactFlowProvider><OccurrenceNode {...props({ kind: 'occurrence', label: 'work.accounts', occRole: 'write' })} /></ReactFlowProvider>)
    expect(screen.getByText('work.accounts')).toBeInTheDocument()
    expect(container.querySelector('.rf-occ.write')).not.toBeNull()
  })
})
