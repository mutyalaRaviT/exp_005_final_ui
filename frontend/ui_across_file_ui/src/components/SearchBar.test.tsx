// SearchBar dropdown discipline: picking a hit must not re-open the list
// (the box's new value is a result, not a query), Escape and outside clicks
// close it, and ArrowDown/Enter pick without the mouse.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SearchBar from './SearchBar'
import { searchHits, type SearchHit } from '../api'

vi.mock('../api', () => ({
  searchHits: vi.fn(),
}))

const hits: SearchHit[] = [
  { kind: 'table', value: 'work.cust_summary', files: ['a.sas'] },
  { kind: 'table', value: 'work.customers', files: ['a.sas', 'b.sas'] },
]

beforeEach(() => {
  vi.mocked(searchHits).mockResolvedValue(hits)
})

function type(value: string) {
  fireEvent.change(screen.getByPlaceholderText(/search table or file/i), {
    target: { value },
  })
}

describe('SearchBar', () => {
  it('picking a suggestion closes the dropdown and keeps it closed', async () => {
    const onSelect = vi.fn()
    render(<SearchBar onSelect={onSelect} />)
    type('cust')
    fireEvent.click(await screen.findByText('work.cust_summary'))
    expect(onSelect).toHaveBeenCalledWith(hits[0])
    // the pick rewrote the box to the hit's value — that text must not
    // trigger a new search that re-opens the dropdown over the graph
    await new Promise((r) => setTimeout(r, 400))
    expect(screen.queryByText('work.customers')).toBeNull()
  })

  it('Escape closes the dropdown', async () => {
    render(<SearchBar onSelect={vi.fn()} />)
    type('cust')
    await screen.findByText('work.cust_summary')
    fireEvent.keyDown(screen.getByPlaceholderText(/search table or file/i), {
      key: 'Escape',
    })
    expect(screen.queryByText('work.cust_summary')).toBeNull()
  })

  it('a click outside closes the dropdown', async () => {
    render(
      <div>
        <SearchBar onSelect={vi.fn()} />
        <button type="button">elsewhere</button>
      </div>,
    )
    type('cust')
    await screen.findByText('work.cust_summary')
    fireEvent.mouseDown(screen.getByText('elsewhere'))
    await waitFor(() =>
      expect(screen.queryByText('work.cust_summary')).toBeNull())
  })

  it('ArrowDown + Enter picks without the mouse', async () => {
    const onSelect = vi.fn()
    render(<SearchBar onSelect={onSelect} />)
    const input = screen.getByPlaceholderText(/search table or file/i)
    type('cust')
    await screen.findByText('work.cust_summary')
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledWith(hits[1])
  })
})
