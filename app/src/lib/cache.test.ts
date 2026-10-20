// Cache first, then the engine (rebuild Phase 4): a screen gets the saved answer at once
// and the engine's after it; when the engine does not answer, the saved answer stays on
// screen with the reason. Nothing ever renders blank once something was saved.
import { describe, expect, it, vi } from 'vitest'
import { HealthDB } from '../db/schema'
import { ageMinutes, cacheFirst, cacheKey, type View } from './cache'

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

describe('how old the shown answer is', () => {
  it('counts whole minutes, never below zero', () => {
    const now = new Date('2026-10-20T07:10:30Z')
    expect(ageMinutes('2026-10-20T07:07:00Z', now)).toBe(3)
    expect(ageMinutes('2026-10-20T07:11:00Z', now)).toBe(0)
    expect(ageMinutes(null, now)).toBeNull()
  })
})
