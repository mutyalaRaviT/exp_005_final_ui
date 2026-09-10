import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { hood3, detailLoader, detailBuilder, links3 } from './__fixtures__/graph2Data'
import * as elkLayoutModule from './elkLayout'

function mockApi(fail = false) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (fail) return { ok: false, status: 500, statusText: 'ERR', json: async () => ({}) }
    const body = url.startsWith('/api/neighborhood') ? hood3
      : url.startsWith('/api/blocklinks') ? { links: links3 }
      : url.includes('/api/file/loader.sas') ? detailLoader
      : url.includes('/api/file/builder.sas') ? detailBuilder
      : url.startsWith('/api/files') ? { files: [] }
      : url.startsWith('/api/edges') ? { total: 0, rows: [] }
      : { hits: [] }
    return { ok: true, status: 200, statusText: 'OK', json: async () => body }
  }))
}
describe('App', () => {
  afterEach(() => vi.unstubAllGlobals())
  afterEach(() => vi.restoreAllMocks())

  it('renders one file node per neighborhood file from the URL', async () => {
    window.history.replaceState(null, '', '/?file=builder.sas&up=1&down=1')
    mockApi()
    render(<App />)
    await waitFor(() => expect(document.querySelectorAll('.rf-file')).toHaveLength(3), { timeout: 8000 })
    expect(screen.getAllByText('loader.sas').length).toBeGreaterThan(0)
  })
  it('shows the start command when the API is down', async () => {
    window.history.replaceState(null, '', '/?file=builder.sas&up=1&down=1')
    mockApi(true)
    render(<App />)
    // Task 8 (2026-09-10): START_CMD used to name a Python server under
    // ~/Desktop/sas2py_projects; the API this window talks to is the Rust one on :8110.
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('lineageq_api'))
  })
  it('shows the hint when there is no seed', async () => {
    window.history.replaceState(null, '', '/')
    mockApi()
    render(<App />)
    expect(await screen.findByText(/search a table or file/i)).toBeInTheDocument()
  })
  it('discards an in-flight neighborhood response after the seed is cleared', async () => {
    window.history.replaceState(null, '', '/?file=builder.sas&up=1&down=1')
    let resolveNeighborhood!: (v: unknown) => void
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.startsWith('/api/neighborhood')) {
        const body = await new Promise((resolve) => { resolveNeighborhood = resolve })
        return { ok: true, status: 200, statusText: 'OK', json: async () => body }
      }
      const body = url.startsWith('/api/blocklinks') ? { links: links3 }
        : url.includes('/api/file/loader.sas') ? detailLoader
        : url.includes('/api/file/builder.sas') ? detailBuilder
        : url.startsWith('/api/files') ? { files: [] }
        : url.startsWith('/api/edges') ? { total: 0, rows: [] }
        : { hits: [] }
      return { ok: true, status: 200, statusText: 'OK', json: async () => body }
    }))
    // Stub out ELK layout with an instantly-resolving fake so this test's
    // timing doesn't depend on the real (worker-backed, unpredictably slow
    // in jsdom) ELK computation -- only on the seq.current discard logic.
    vi.spyOn(elkLayoutModule, 'elkLayout').mockResolvedValue({
      nodes: hood3.nodes.map((n, i) => ({ id: n.id, kind: 'file' as const, label: n.label, x: i * 200, y: 0, width: 160, height: 44, fileid: n.id })),
      edges: [],
    })

    render(<App />)
    await waitFor(() => expect(resolveNeighborhood).toBeDefined())

    window.history.replaceState(null, '', '/')
    act(() => { window.dispatchEvent(new PopStateEvent('popstate')) })
    await screen.findByText(/search a table or file/i)

    // let the stale neighborhood response (and everything it would trigger:
    // fetchBlockLinks, ELK layout, toFlow) fully settle before asserting
    await act(async () => {
      resolveNeighborhood(hood3)
      await new Promise((r) => setTimeout(r, 50))
    })
    expect(screen.getByText(/search a table or file/i)).toBeInTheDocument()
    expect(document.querySelectorAll('.rf-file')).toHaveLength(0)
  })

  it('shows a banner and stays collapsed when a file detail fetch fails', async () => {
    window.history.replaceState(null, '', '/?file=builder.sas&up=1&down=1')
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/file/loader.sas')) return { ok: false, status: 404, statusText: 'Not Found', json: async () => ({}) }
      const body = url.startsWith('/api/neighborhood') ? hood3
        : url.startsWith('/api/blocklinks') ? { links: links3 }
        : url.includes('/api/file/builder.sas') ? detailBuilder
        : url.startsWith('/api/files') ? { files: [] }
        : url.startsWith('/api/edges') ? { total: 0, rows: [] }
        : { hits: [] }
      return { ok: true, status: 200, statusText: 'OK', json: async () => body }
    }))
    render(<App />)
    await waitFor(() => expect(document.querySelectorAll('.rf-file')).toHaveLength(3), { timeout: 8000 })

    await act(async () => {
      window.dispatchEvent(new CustomEvent('node4:toggle', { detail: { fileid: 'loader.sas' } }))
      await new Promise((r) => setTimeout(r, 50))
    })

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('could not load blocks for loader.sas'))
    expect(document.querySelectorAll('.rf-file')).toHaveLength(3)
  })

  it('expands a file into blocks and tables on toggle', async () => {
    window.history.replaceState(null, '', '/?file=builder.sas&up=1&down=1')
    mockApi()
    render(<App />)
    await waitFor(() => expect(document.querySelectorAll('.rf-file')).toHaveLength(3), { timeout: 8000 })

    await act(async () => {
      window.dispatchEvent(new CustomEvent('node4:toggle', { detail: { fileid: 'builder.sas' } }))
    })

    await waitFor(() => {
      expect(document.querySelectorAll('.rf-group.kind-blockCluster').length).toBeGreaterThan(0)
      expect(document.querySelectorAll('.rf-occ').length).toBeGreaterThan(0)
    }, { timeout: 8000 })
    expect(document.querySelectorAll('.rf-file')).toHaveLength(2)
  })
})
