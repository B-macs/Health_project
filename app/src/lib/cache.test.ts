// Cache first, then the engine (rebuild Phase 4): a screen gets the saved answer at once
// and the engine's after it; when the engine does not answer, the saved answer stays on
// screen with the reason. Nothing ever renders blank once something was saved.
import { describe, expect, it, vi } from 'vitest'
import { HealthDB } from '../db/schema'
import { READ_TIMEOUT_MS, SAVED_MS, ageMinutes, cacheFirst, cacheKey, within, type View } from './cache'

let n = 0
const freshDb = () => new HealthDB(`cache-test-${++n}-${Date.now()}`)

function answer(status: number, body: unknown) {
  return vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }))
}

async function views<T>(store: HealthDB, fetchImpl: typeof fetch, day: string | null = '2026-10-20') {
  const seen: View<T>[] = []
  const now = () => new Date('2026-10-20T07:00:00Z')
  await cacheFirst<T>(store, '/api/today', day, { key: 'k', engineDown: false, fetchImpl, now }, (v) => seen.push(v))
  return seen
}

describe('the cache-first read', () => {
  it('with nothing saved: loading, then the engine answer, which is kept', async () => {
    const store = freshDb()
    const seen = await views<{ score: number }>(store, answer(200, { score: 71 }))
    expect(seen.map((v) => [v.state, v.data])).toEqual([['loading', undefined], ['fresh', { score: 71 }]])
    const row = await store.cache.get(cacheKey('/api/today', '2026-10-20'))
    expect(row?.body).toEqual({ score: 71 })
    expect(row?.fetched_at).toBe('2026-10-20T07:00:00.000Z')
  })

  it('with an answer saved: the saved one first, then the new one', async () => {
    const store = freshDb()
    await views(store, answer(200, { score: 60 }))
    const seen = await views<{ score: number }>(store, answer(200, { score: 71 }))
    expect(seen.map((v) => [v.state, v.data])).toEqual([['loading', { score: 60 }], ['fresh', { score: 71 }]])
  })

  it('with the engine down: the saved answer stays, with the reason, and is not replaced', async () => {
    const store = freshDb()
    await views(store, answer(200, { score: 60 }))
    const seen = await views<{ score: number }>(store, answer(503, { error: 'engine_unavailable' }))
    expect(seen.map((v) => [v.state, v.data])).toEqual([
      ['loading', { score: 60 }],
      ['engine_unavailable', { score: 60 }],
    ])
    expect(seen[1].fetchedAt).toBe('2026-10-20T07:00:00.000Z')
    expect((await store.cache.get(cacheKey('/api/today', '2026-10-20')))?.body).toEqual({ score: 60 })
  })

  it('offline with nothing saved says so (the screen shows why, not a blank)', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    const seen = await views(freshDb(), fetchImpl)
    expect(seen.map((v) => [v.state, v.data])).toEqual([['loading', undefined], ['offline', undefined]])
  })

  it('keeps one answer per day', async () => {
    const store = freshDb()
    await views(store, answer(200, { day: 19 }), '2026-10-19')
    await views(store, answer(200, { day: 20 }), '2026-10-20')
    expect((await store.cache.get(cacheKey('/api/today', '2026-10-19')))?.body).toEqual({ day: 19 })
    expect((await store.cache.get(cacheKey('/api/today', '2026-10-20')))?.body).toEqual({ day: 20 })
  })

  it('asks the engine for the day it shows', async () => {
    const fetchImpl = answer(200, {})
    await views(freshDb(), fetchImpl, '2026-10-18')
    const init = (fetchImpl.mock.calls[0] as unknown as [string, RequestInit])[1]
    expect(new Headers(init.headers).get('x-local-date')).toBe('2026-10-18')
  })
})

describe("a read that never finishes (the owner's iPhone, 2026-10-20)", () => {
  it('ends at the time limit with the saved answer and the reason, never waits for good', async () => {
    expect(READ_TIMEOUT_MS).toBeGreaterThan(10_000)
    const store = freshDb()
    await store.cache.put({ key: cacheKey('/api/today', '2026-10-20'), path: '/api/today', day: '2026-10-20',
      body: { score: 60 }, fetched_at: '2026-10-20T03:00:00.000Z' })
    // A request that never answers, as a stalled connection does; it ends only when aborted.
    const fetchImpl = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })) as unknown as typeof fetch
    const seen: View<{ score: number }>[] = []
    await cacheFirst<{ score: number }>(store, '/api/today', '2026-10-20',
      { key: 'k', engineDown: false, fetchImpl, readTimeoutMs: 60 }, (v) => seen.push(v))
    expect(seen.map((v) => [v.state, v.data])).toEqual([['loading', { score: 60 }], ['offline', { score: 60 }]])
    expect(seen[1]!.code).toBe('timeout')
  })

  it("shows the engine's answer even when the phone's database stalls on keeping it", async () => {
    expect(SAVED_MS).toBeGreaterThan(0)
    const store = freshDb()
    vi.spyOn(store.cache, 'put').mockReturnValue(new Promise(() => undefined) as never)
    const seen: View<{ score: number }>[] = []
    await cacheFirst<{ score: number }>(store, '/api/today', '2026-10-20',
      { key: 'k', engineDown: false, fetchImpl: answer(200, { score: 71 }), savedMs: 60 }, (v) => seen.push(v))
    expect(seen.at(-1)?.state).toBe('fresh')
    expect(seen.at(-1)?.data).toEqual({ score: 71 })
  })

  it('within: the value, or undefined after the limit or on a failure', async () => {
    expect(await within(Promise.resolve(3), 50)).toBe(3)
    expect(await within(Promise.reject(new Error('no')), 50)).toBeUndefined()
    expect(await within(new Promise(() => undefined), 30)).toBeUndefined()
  })
})

describe('how old the shown answer is', () => {
  it('counts whole minutes, never below zero', () => {
    const now = new Date('2026-10-20T07:10:30Z')
    expect(ageMinutes('2026-10-20T07:07:00Z', now)).toBe(3)
    expect(ageMinutes('2026-10-20T07:11:00Z', now)).toBe(0)
    expect(ageMinutes(null, now)).toBeNull()
  })
})
