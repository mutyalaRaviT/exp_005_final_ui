import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchBlockLinks, fetchFileDetail, fetchNeighborhood } from './api'

function mockFetch(body: unknown, ok = true) {
  const fn = vi.fn(async (_url: string) => ({ ok, status: ok ? 200 : 500, statusText: ok ? 'OK' : 'ERR', json: async () => body }))
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('fetchNeighborhood builds file/up/down query', async () => {
    const fn = mockFetch({ nodes: [], edges: [], story: [], order: {} })
    await fetchNeighborhood({ file: 'ankitha_1/04_build_accounts.sas', up: 1, down: 2 })
    expect(fn.mock.calls[0][0]).toBe('/api/neighborhood?file=ankitha_1%2F04_build_accounts.sas&up=1&down=2')
  })
  it('fetchBlockLinks unwraps links and skips the call for no files', async () => {
    const fn = mockFetch({ links: [{ table: 'work.t' }] })
    expect(await fetchBlockLinks([])).toEqual([])
    expect(fn).not.toHaveBeenCalled()
    expect(await fetchBlockLinks(['a', 'b'])).toEqual([{ table: 'work.t' }])
    expect(fn.mock.calls[0][0]).toBe('/api/blocklinks?files=a%2Cb')
  })
  it('fetchFileDetail keeps the slash in the fileid path', async () => {
    const fn = mockFetch({ fileid: 'x' })
    await fetchFileDetail('ankitha_1/04_build_accounts.sas')
    expect(fn.mock.calls[0][0]).toBe('/api/file/ankitha_1/04_build_accounts.sas')
  })
  it('throws on a non-ok response', async () => {
    mockFetch({}, false)
    await expect(fetchFileDetail('a')).rejects.toThrow('500')
  })
})
