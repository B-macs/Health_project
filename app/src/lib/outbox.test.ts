// The outbox contract (rebuild Phase 4): every write gets a ULID minted on the phone,
// goes out in the order it was written, is tried again with a growing wait, and leaves
// the outbox only on the engine's yes. Nothing is lost: not offline, not with the
// engine down, not across an app restart.
import { describe, expect, it, vi } from 'vitest'
import { HealthDB } from '../db/schema'
import { BACKOFF_MS, backoff, drain, enqueue, nextTry, retry, wake } from './outbox'
import { ULID, ulidTime } from './ulid'

let n = 0
const dbName = () => `outbox-test-${++n}-${Date.now()}`
const T0 = new Date('2026-10-20T07:00:00Z')

type Call = { path: string; body: unknown; day: string | null }

/** An engine that answers each call with the next status in the list (then 200). */
function engine(statuses: (number | 'offline')[] = []) {
  const calls: Call[] = []
  const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const status = statuses.shift() ?? 200
    if (status === 'offline') throw new TypeError('Failed to fetch')
    calls.push({ path: String(input), body: JSON.parse(String(init?.body ?? 'null')), day: new Headers(init?.headers).get('x-local-date') })
    const error = status === 503 ? 'engine_unavailable' : status === 401 ? 'unauthorized' : 'refused'
    return new Response(JSON.stringify(status === 200 ? { saved: true } : { error }), {
      status,
      headers: { 'content-type': 'application/json' },
    })
  })
  return { calls, fetchImpl }
}

const write = (i: number) => ({ kind: 'test', method: 'POST' as const, path: `/api/x/${i}`, body: { i }, day: '2026-10-20' })

describe('the ids', () => {
  it('every write gets a ULID minted on the phone, in time order', async () => {
    const store = new HealthDB(dbName())
    const a = await enqueue(store, write(1), T0)
    const b = await enqueue(store, write(2), new Date(T0.getTime() + 1))
    expect(a).toMatch(ULID)
    expect(b).toMatch(ULID)
    expect(a < b).toBe(true)
    expect(ulidTime(a)).toBe(T0.getTime())
  })
})

describe('sending', () => {
  it('sends in the order written, with each write\'s own day, and empties on yes', async () => {
    const store = new HealthDB(dbName())
    for (const i of [1, 2, 3]) await enqueue(store, { ...write(i), day: `2026-10-1${i}` }, T0)
    const { calls, fetchImpl } = engine()
    expect(await drain(store, { key: 'k', engineDown: false, fetchImpl, now: () => T0 })).toBe('done')
    expect(calls.map((c) => [c.path, c.day])).toEqual([
      ['/api/x/1', '2026-10-11'],
      ['/api/x/2', '2026-10-12'],
      ['/api/x/3', '2026-10-13'],
    ])
    expect(await store.outbox.count()).toBe(0)
  })

  it('a write that cannot go now waits with a growing wait, and nothing overtakes it', async () => {
    const store = new HealthDB(dbName())
    for (const i of [1, 2]) await enqueue(store, write(i), T0)
    const { calls, fetchImpl } = engine(['offline'])
    expect(await drain(store, { key: 'k', engineDown: false, fetchImpl, now: () => T0 })).toBe('offline')
    expect(calls).toEqual([])
    const [first] = await store.outbox.orderBy('seq').toArray()
    expect(first.attempts).toBe(1)
    expect(new Date(first.next_at).getTime() - T0.getTime()).toBe(BACKOFF_MS[0])
    // Before its wait ends, nothing is sent: not it, and not the one behind it.
    expect(await drain(store, { key: 'k', engineDown: false, fetchImpl, now: () => T0 })).toBe('later')
    expect(calls).toEqual([])
    expect(await store.outbox.count()).toBe(2)
  })

  it('with the engine down, every write stays until it answers; then all go, in order', async () => {
    const store = new HealthDB(dbName())
    for (const i of [1, 2, 3]) await enqueue(store, write(i), T0)
    const down = engine([503, 503])
    let now = T0
    const ctx = { key: 'k', engineDown: false, fetchImpl: down.fetchImpl, now: () => now }
    expect(await drain(store, ctx)).toBe('offline')
    now = new Date(now.getTime() + BACKOFF_MS[0])
    expect(await drain(store, ctx)).toBe('offline')
    expect(await store.outbox.count()).toBe(3)
    now = new Date(now.getTime() + BACKOFF_MS[1])
    expect(await drain(store, ctx)).toBe('done')
    expect(down.calls.map((c) => c.path)).toEqual(['/api/x/1', '/api/x/1', '/api/x/1', '/api/x/2', '/api/x/3'])
    expect(await store.outbox.count()).toBe(0)
  })

  it('the "engine is down" switch keeps every write', async () => {
    const store = new HealthDB(dbName())
    await enqueue(store, write(1), T0)
    const { calls, fetchImpl } = engine()
    expect(await drain(store, { key: 'k', engineDown: true, fetchImpl, now: () => T0 })).toBe('offline')
    expect(calls).toEqual([])
    expect(await store.outbox.count()).toBe(1)
  })

  it('a refused write is kept, marked, and the ones after it still go', async () => {
    const store = new HealthDB(dbName())
    for (const i of [1, 2]) await enqueue(store, write(i), T0)
    const { calls, fetchImpl } = engine([422])
    expect(await drain(store, { key: 'k', engineDown: false, fetchImpl, now: () => T0 })).toBe('done')
    expect(calls.map((c) => c.path)).toEqual(['/api/x/1', '/api/x/2'])
    const left = await store.outbox.toArray()
    expect(left.map((r) => [r.path, r.state, r.last_error])).toEqual([['/api/x/1', 'failed', 'refused']])
    // Sent again from Settings, it goes.
    await retry(store, left[0].seq!, T0)
    expect(await drain(store, { key: 'k', engineDown: false, fetchImpl, now: () => T0 })).toBe('done')
    expect(await store.outbox.count()).toBe(0)
  })

  it('a wrong key stops the queue and keeps every write', async () => {
    const store = new HealthDB(dbName())
    for (const i of [1, 2]) await enqueue(store, write(i), T0)
    const { fetchImpl } = engine([401])
    expect(await drain(store, { key: 'wrong', engineDown: false, fetchImpl, now: () => T0 })).toBe('unauthorized')
    expect(await store.outbox.count()).toBe(2)
    expect(await drain(store, { key: null, engineDown: false, fetchImpl, now: () => T0 })).toBe('unauthorized')
  })

  it('nothing is lost across a restart: a new connection finds every write', async () => {
    const name = dbName()
    const before = new HealthDB(name)
    for (const i of [1, 2]) await enqueue(before, write(i), T0)
    before.close()
    const after = new HealthDB(name)
    const { calls, fetchImpl } = engine()
    expect(await drain(after, { key: 'k', engineDown: false, fetchImpl, now: () => T0 })).toBe('done')
    expect(calls.map((c) => c.body)).toEqual([{ i: 1 }, { i: 2 }])
  })

  it('back online, every waiting write may go at once', async () => {
    const store = new HealthDB(dbName())
    await enqueue(store, write(1), T0)
    const { fetchImpl } = engine(['offline'])
    await drain(store, { key: 'k', engineDown: false, fetchImpl, now: () => T0 })
    expect((await nextTry(store))!.getTime()).toBe(T0.getTime() + BACKOFF_MS[0])
    await wake(store, T0)
    expect((await nextTry(store))!.getTime()).toBe(T0.getTime())
  })
})

describe('the wait', () => {
  it('grows 5 s, 15 s, 1 min, 5 min, then 15 min each time', () => {
    expect([1, 2, 3, 4, 5, 6, 9].map(backoff)).toEqual([5_000, 15_000, 60_000, 300_000, 900_000, 900_000, 900_000])
  })
})
