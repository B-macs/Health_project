// Cache first, then the engine (rebuild Phase 4): a screen gets the saved answer at once
// and the engine's after it; when the engine does not answer, the saved answer stays on
// screen with the reason. Nothing ever renders blank once something was saved.
import { describe, expect, it, vi } from 'vitest'
import { HealthDB } from '../db/schema'
import { api } from './api'
import { READ_TIMEOUT_MS, SAVED_MS, ageMinutes, cacheFirst, cacheKey, readsOnTheWay, within, type Ctx, type View } from './cache'
import { bump } from './refresh'

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

// The first open of 2026-10-22 sent /api/training/day fifteen times in a minute (one for
// every tab change) and the engine computed every copy: a screen asking for an address
// already on its way now waits for that read.
describe('one read per address on its way', () => {
  const NOON = () => new Date('2026-10-20T12:00:00Z')

  /** A fetch that answers only when told, and counts the requests. */
  function held() {
    const waiting: { resolve: (r: Response) => void; reject: (e: unknown) => void }[] = []
    const fetchImpl = vi.fn(() => new Promise<Response>((resolve, reject) => waiting.push({ resolve, reject })))
    const answerAll = (body: unknown) => waiting.splice(0).forEach((w) =>
      w.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })))
    const failAll = () => waiting.splice(0).forEach((w) => w.reject(new TypeError('Failed to fetch')))
    return { fetchImpl: fetchImpl as unknown as typeof fetch, calls: () => fetchImpl.mock.calls.length, answerAll, failAll }
  }

  const ctxOf = (fetchImpl: typeof fetch): Ctx => ({ key: 'k', engineDown: false, fetchImpl, now: NOON })

  /** Start a read and wait until it is on its way (it shows its saved answer just before). */
  async function start<T>(store: HealthDB, path: string, day: string | null, ctx: Ctx) {
    const seen: View<T>[] = []
    const done = cacheFirst<T>(store, path, day, ctx, (v) => seen.push(v))
    await vi.waitFor(() => expect(seen.length).toBe(1))
    return { seen, done }
  }

  it('a second screen asking for the same address waits for the read on its way', async () => {
    const store = freshDb()
    const f = held()
    const a = await start<{ n: number }>(store, '/api/training/day', null, ctxOf(f.fetchImpl))
    const b = await start<{ n: number }>(store, '/api/training/day', null, ctxOf(f.fetchImpl))
    expect(f.calls()).toBe(1)
    expect(readsOnTheWay()).toBe(1)
    f.answerAll({ n: 1 })
    await Promise.all([a.done, b.done])
    expect(a.seen.at(-1)).toMatchObject({ state: 'fresh', data: { n: 1 } })
    expect(b.seen.at(-1)).toMatchObject({ state: 'fresh', data: { n: 1 } })
    expect(readsOnTheWay()).toBe(0)
  })

  it('a write that ended meanwhile: the next screen asks again', async () => {
    const store = freshDb()
    const f = held()
    const a = await start(store, '/api/checkin?date=2026-10-20', null, ctxOf(f.fetchImpl))
    await api('/api/checkin', { method: 'PUT', key: 'k', body: {}, fetchImpl: answer(200, {}) })
    const b = await start(store, '/api/checkin?date=2026-10-20', null, ctxOf(f.fetchImpl))
    expect(f.calls()).toBe(2)
    f.answerAll({})
    await Promise.all([a.done, b.done])
  })

  it('a sync that ran meanwhile: the next screen asks again', async () => {
    const store = freshDb()
    const f = held()
    const a = await start(store, '/api/today', null, ctxOf(f.fetchImpl))
    bump()
    const b = await start(store, '/api/today', null, ctxOf(f.fetchImpl))
    expect(f.calls()).toBe(2)
    f.answerAll({})
    await Promise.all([a.done, b.done])
  })

  it('another day, or another address, is another read', async () => {
    const store = freshDb()
    const f = held()
    const reads = [
      await start(store, '/api/today', '2026-10-19', ctxOf(f.fetchImpl)),
      await start(store, '/api/today', '2026-10-20', ctxOf(f.fetchImpl)),
      await start(store, '/api/today/week', '2026-10-20', ctxOf(f.fetchImpl)),
    ]
    expect(f.calls()).toBe(3)
    f.answerAll({})
    await Promise.all(reads.map((r) => r.done))
  })

  it('a failed read fails for every screen that waited, and the next one asks again', async () => {
    const store = freshDb()
    const f = held()
    const a = await start(store, '/api/training/session', null, ctxOf(f.fetchImpl))
    const b = await start(store, '/api/training/session', null, ctxOf(f.fetchImpl))
    f.failAll()
    await Promise.all([a.done, b.done])
    expect([a.seen.at(-1)?.state, b.seen.at(-1)?.state]).toEqual(['offline', 'offline'])
    const c = await start(store, '/api/training/session', null, ctxOf(f.fetchImpl))
    expect(f.calls()).toBe(2)
    f.answerAll({})
    await c.done
  })
})

// A today address: on the morning of 2026-10-22 Home showed the day before's "Rest day" under
// Thursday's date until the engine answered.
describe('an address that answers for today', () => {
  const at = (iso: string): Ctx => ({ key: 'k', engineDown: false, fetchImpl: answer(503, { error: 'engine_unavailable' }),
    now: () => new Date(iso) })

  async function keptOn(store: HealthDB, fetchedAt: string) {
    await store.cache.put({ key: cacheKey('/api/training/day', null), path: '/api/training/day', day: null,
      body: { date: fetchedAt.slice(0, 10) }, fetched_at: fetchedAt })
  }

  async function shown(store: HealthDB, ctx: Ctx, today: boolean | undefined) {
    const seen: View<{ date: string }>[] = []
    await cacheFirst<{ date: string }>(store, '/api/training/day', null, ctx, (v) => seen.push(v), { today })
    return seen.map((v) => [v.state, v.data])
  }

  it('does not show a copy kept on an earlier day: the screen loads instead', async () => {
    const store = freshDb()
    await keptOn(store, '2026-10-21T12:00:00.000Z')
    expect(await shown(store, at('2026-10-22T12:00:00Z'), true)).toEqual([
      ['loading', undefined], ['engine_unavailable', undefined]])
  })

  it('shows a copy kept earlier the same day (the gym with no signal)', async () => {
    const store = freshDb()
    await keptOn(store, '2026-10-22T06:00:00.000Z')
    expect(await shown(store, at('2026-10-22T12:00:00Z'), true)).toEqual([
      ['loading', { date: '2026-10-22' }], ['engine_unavailable', { date: '2026-10-22' }]])
  })

  it('an address with its own day in it shows its copy whenever it was kept', async () => {
    const store = freshDb()
    await keptOn(store, '2026-10-21T12:00:00.000Z')
    expect(await shown(store, at('2026-10-22T12:00:00Z'), undefined)).toEqual([
      ['loading', { date: '2026-10-21' }], ['engine_unavailable', { date: '2026-10-21' }]])
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
