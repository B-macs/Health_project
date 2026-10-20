// Every request carries the phone's day and the key, and every failure becomes one
// ApiError the screens can word (rebuild Phase 4).
import { describe, expect, it, vi } from 'vitest'
import { ApiError, api, localDay } from './api'

function answer(status: number, body: unknown) {
  return vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
    new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }))
}

async function kindOf(promise: Promise<unknown>): Promise<string> {
  try {
    await promise
    return 'ok'
  } catch (err) {
    return err instanceof ApiError ? err.kind : 'not an ApiError'
  }
}

describe('the request', () => {
  it("sends the phone's own day as X-Local-Date and the key as a bearer token", async () => {
    const fetchImpl = answer(200, { status: 'ok' })
    await api('/api/health', { key: 'k1', day: '2026-10-20', fetchImpl })
    const [path, init] = fetchImpl.mock.calls[0]
    const headers = new Headers(init?.headers)
    expect(path).toBe('/api/health')
    expect(headers.get('x-local-date')).toBe('2026-10-20')
    expect(headers.get('authorization')).toBe('Bearer k1')
    expect(init?.cache).toBe('no-store')
  })

  it('takes the day from the phone clock when none is given', async () => {
    const fetchImpl = answer(200, {})
    await api('/api/health', { key: 'k', fetchImpl })
    expect(new Headers(fetchImpl.mock.calls[0][1]?.headers).get('x-local-date')).toBe(localDay())
  })

  it("reads the day in the phone's own time zone, never UTC", () => {
    // 00:30 on 20 October in the phone's zone is the 20th, whatever UTC says.
    expect(localDay(new Date(2026, 9, 20, 0, 30))).toBe('2026-10-20')
    expect(localDay(new Date(2026, 9, 19, 23, 59))).toBe('2026-10-19')
  })

  it('sends a body as JSON', async () => {
    const fetchImpl = answer(200, { saved: true })
    await api('/api/checkin', { method: 'PUT', body: { a: 1 }, key: 'k', fetchImpl })
    const init = fetchImpl.mock.calls[0][1]
    expect(init?.method).toBe('PUT')
    expect(init?.body).toBe('{"a":1}')
    expect(new Headers(init?.headers).get('content-type')).toBe('application/json')
  })
})

describe('the failures', () => {
  it.each([
    [401, { error: 'unauthorized' }, 'unauthorized'],
    [400, { error: 'unauthorized' }, 'unauthorized'],
    [503, { error: 'engine_unavailable' }, 'engine_unavailable'],
    [504, { error: 'engine_timeout' }, 'engine_unavailable'],
    [503, { error: 'not_configured' }, 'engine_unavailable'],
    [500, { error: 'internal_error' }, 'server'],
    [409, { error: 'not_the_writer' }, 'rejected'],
    [422, { error: 'invalid_request' }, 'rejected'],
  ])('%i %j is %s', async (status, body, kind) => {
    expect(await kindOf(api('/api/x', { key: 'k', fetchImpl: answer(status, body) }))).toBe(kind)
  })

  it('no network is offline', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    expect(await kindOf(api('/api/x', { key: 'k', fetchImpl }))).toBe('offline')
  })

  it('the "engine is down" switch answers at once and sends nothing', async () => {
    const fetchImpl = answer(200, {})
    expect(await kindOf(api('/api/x', { key: 'k', engineDown: true, fetchImpl }))).toBe('engine_unavailable')
    expect(fetchImpl).not.toHaveBeenCalled()
  })
})
