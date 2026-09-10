import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EdgesPanel, { flowSide } from './EdgesPanel'
import { fetchEdges, type EdgeRow } from '../api'

vi.mock('../api', () => ({ fetchEdges: vi.fn() }))

const rows: EdgeRow[] = [
  { fileid: 'a.sas', block_id: 'b_1', src: 'raw.x', dst: 'work.t', tables: ['work.t'], level: 'block', provenance: 'fact' },
  { fileid: 'a.sas', block_id: null, src: 'a.sas', dst: 'b.sas', tables: ['work.t'], level: 'project', provenance: 'inferred' },
]

beforeEach(() => {
  vi.mocked(fetchEdges).mockReset()
  vi.mocked(fetchEdges).mockResolvedValue({ total: 2, rows })
})

describe('EdgesPanel', () => {
  it('lists the flows for the scoped files with level and provenance chips', async () => {
    render(<EdgesPanel fileids={['b.sas', 'a.sas']} onOpenBlock={vi.fn()} />)
    expect(await screen.findByText('raw.x -> work.t')).toBeInTheDocument()
    expect(screen.getByText('2 / 2')).toBeInTheDocument()
    expect(document.querySelector('.chip-fact')).not.toBeNull()
    expect(document.querySelector('.chip-level-project')).not.toBeNull()
    // scope is sorted so the same set of files is one server query
    expect(vi.mocked(fetchEdges).mock.calls[0][0].files).toEqual(['a.sas', 'b.sas'])
  })
  it('clicking a row opens its file and block', async () => {
    const onOpenBlock = vi.fn()
    render(<EdgesPanel fileids={['a.sas']} onOpenBlock={onOpenBlock} />)
    fireEvent.click(await screen.findByText('raw.x -> work.t'))
    expect(onOpenBlock).toHaveBeenCalledWith('a.sas', 'b_1', rows[0])
  })
  it('re-queries with the level filter', async () => {
    render(<EdgesPanel fileids={['a.sas']} onOpenBlock={vi.fn()} />)
    await screen.findByText('raw.x -> work.t')
    fireEvent.change(screen.getByLabelText('level'), { target: { value: 'block' } })
    await waitFor(() => expect(vi.mocked(fetchEdges).mock.calls.at(-1)?.[0].level).toBe('block'))
  })
  it('shows a hint and skips the fetch with no files', () => {
    render(<EdgesPanel fileids={[]} onOpenBlock={vi.fn()} />)
    expect(screen.getByText(/pick a file/i)).toBeInTheDocument()
    expect(fetchEdges).not.toHaveBeenCalled()
  })
  it('narrows to the focused file and tints inflow/outflow', async () => {
    vi.mocked(fetchEdges).mockResolvedValue({ total: 3, rows: [
      ...rows,
      { fileid: 'c.sas', block_id: null, src: 'c.sas', dst: 'a.sas', tables: ['work.x'], level: 'project', provenance: 'inferred' },
    ] })
    render(<EdgesPanel fileids={['a.sas', 'b.sas', 'c.sas']} onOpenBlock={vi.fn()} focus={{ kind: 'file', value: 'a.sas' }} onClearFocus={vi.fn()} />)
    await screen.findByText('raw.x -> work.t')
    expect(document.querySelector('.edges-row.self')).not.toBeNull()      // block row inside a.sas
    expect(document.querySelector('.edges-row.outflow')).not.toBeNull()   // a.sas -> b.sas
    expect(document.querySelector('.edges-row.inflow')).not.toBeNull()    // c.sas -> a.sas
    expect(screen.getByText(/3 of 3/)).toBeInTheDocument()
    expect(screen.getByText('file · a.sas')).toBeInTheDocument()
  })
  it('a table focus asks the server for that table and classifies sides', () => {
    expect(flowSide({ fileid: 'a', block_id: 'b', src: 'raw.x', dst: 'work.t', tables: ['work.t'], level: 'block', provenance: 'fact' }, { kind: 'table', value: 'work.t' })).toBe('inflow')
    expect(flowSide({ fileid: 'a', block_id: 'b', src: 'work.t', dst: 'work.u', tables: ['work.t'], level: 'block', provenance: 'fact' }, { kind: 'table', value: 'work.t' })).toBe('outflow')
    expect(flowSide({ fileid: 'a', block_id: 'b', src: 'x', dst: 'y', tables: ['z'], level: 'block', provenance: 'fact' }, { kind: 'table', value: 'work.t' })).toBeNull()
    expect(flowSide({ fileid: 'a', block_id: null, src: 'a.sas', dst: 'b.sas', tables: ['work.t'], level: 'project', provenance: 'inferred' }, { kind: 'table', value: 'work.t' })).toBe('outflow')
    expect(flowSide({ fileid: 'a', block_id: 'b_1', src: 'x', dst: 'y', tables: ['z'], level: 'block', provenance: 'fact' }, { kind: 'block', value: 'b_1', fileid: 'a' })).toBe('self')
  })
})
