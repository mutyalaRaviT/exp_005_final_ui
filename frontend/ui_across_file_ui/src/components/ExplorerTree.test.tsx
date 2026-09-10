import { describe, expect, it, vi } from 'vitest'
import { render, fireEvent, within } from '@testing-library/react'
import ExplorerTree from './ExplorerTree'

const all = [
  { id: 'ankitha_1/a.sas#111', label: 'a.sas', folder: 'ankitha_1' },
  { id: 'ankitha_1/b.sas#222', label: 'b.sas', folder: 'ankitha_1' },
  { id: 'other/c.sas#333', label: 'c.sas', folder: 'other' },
]

// the working set a search produced: a subset of everything indexed
const current = [all[0], all[2]]

function layer(name: 'current' | 'all'): HTMLElement {
  return document.querySelector(`[data-cid="explorer-layer-${name}"]`) as HTMLElement
}

describe('ExplorerTree', () => {
  it('groups files by folder and calls onPick when a file is clicked', () => {
    const onPick = vi.fn()
    render(
      <ExplorerTree current={[]} all={all} onPick={onPick} filter="" onFilterChange={vi.fn()} />,
    )

    expect(within(layer('all')).getByText('ankitha_1')).toBeTruthy()
    expect(within(layer('all')).getByText('other')).toBeTruthy()
    fireEvent.click(within(layer('all')).getByText('a.sas'))
    expect(onPick).toHaveBeenCalledWith('ankitha_1/a.sas#111')
  })

  it('shows the working set under CURRENT and everything under ALL FILES', () => {
    render(
      <ExplorerTree
        current={current}
        all={all}
        onPick={vi.fn()}
        filter=""
        onFilterChange={vi.fn()}
      />,
    )

    expect(within(layer('current')).getByText('a.sas')).toBeTruthy()
    expect(within(layer('current')).getByText('c.sas')).toBeTruthy()
    expect(within(layer('current')).queryByText('b.sas')).toBeNull()

    expect(within(layer('all')).getByText('a.sas')).toBeTruthy()
    expect(within(layer('all')).getByText('b.sas')).toBeTruthy()
    expect(within(layer('all')).getByText('c.sas')).toBeTruthy()
  })

  it('hides CURRENT while there is no neighborhood, keeps ALL FILES', () => {
    render(
      <ExplorerTree current={[]} all={all} onPick={vi.fn()} filter="" onFilterChange={vi.fn()} />,
    )
    expect(document.querySelector('[data-cid="explorer-layer-current"]')).toBeNull()
    expect(document.querySelector('[data-cid="explorer-layer-all"]')).toBeTruthy()
  })

  it('the filter box narrows both layers at once', () => {
    render(
      <ExplorerTree
        current={current}
        all={all}
        onPick={vi.fn()}
        filter="c.sas"
        onFilterChange={vi.fn()}
      />,
    )

    expect(within(layer('current')).getByText('c.sas')).toBeTruthy()
    expect(within(layer('current')).queryByText('a.sas')).toBeNull()
    expect(within(layer('all')).getByText('c.sas')).toBeTruthy()
    expect(within(layer('all')).queryByText('a.sas')).toBeNull()
    expect(within(layer('all')).queryByText('b.sas')).toBeNull()
  })

  it('each layer collapses on its own', () => {
    render(
      <ExplorerTree
        current={current}
        all={all}
        onPick={vi.fn()}
        filter=""
        onFilterChange={vi.fn()}
      />,
    )

    fireEvent.click(document.querySelector('[data-cid="layer-toggle-current"]')!)

    expect(within(layer('current')).queryByText('a.sas')).toBeNull()
    expect(within(layer('all')).getByText('a.sas')).toBeTruthy()
  })

  it('clicking a folder header collapses its files in that layer only', () => {
    render(
      <ExplorerTree
        current={current}
        all={all}
        onPick={vi.fn()}
        filter=""
        onFilterChange={vi.fn()}
      />,
    )

    fireEvent.click(within(layer('all')).getByText('ankitha_1'))

    expect(within(layer('all')).queryByText('a.sas')).toBeNull()
    expect(within(layer('current')).getByText('a.sas')).toBeTruthy()
  })
})
