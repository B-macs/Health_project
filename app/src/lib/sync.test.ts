// The engine's sync, started by the phone (rebuild Phase 9, H57): asked at every open, run
// only when the engine says one is due, one at a time, at most one question a minute; a
// sync that ran makes every screen read again.
import { afterEach, describe, expect, it } from 'vitest'
import { currentEpoch } from './refresh'
import { ASK_GAP_MS, resetSyncState, syncIfDue } from './sync'

type Call = { path: string; method: string }

function engine(statusDue: string | null, syncStatus = 200) {
  const calls: Call[] = []
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input)
    calls.push({ path, method: init?.method ?? 'GET' })
    if (path === '/api/status') {
      return new Response(JSON.stringify({ writer: statusDue ? 'engine' : 'streamlit', offline: false, datastore_built_at: null,
        oura: null, last_sync: null, notices: [], sync_due: statusDue }), { status: 200, headers: { 'content-type': 'application/json' } })
    }
    if (syncStatus !== 200) return new Response(JSON.stringify({ error: 'not_the_writer' }), { status: syncStatus })
    return new Response(JSON.stringify({ ran: true, reason: statusDue, status: { day: '2026-10-20', at: '2026-10-20T05:00:00Z', results: {}, error: null } }),
      { status: 200, headers: { 'content-type': 'application/json' } })
  }) as typeof fetch
  return { calls, ctx: { key: 'k', engineDown: false, fetchImpl } }
}

afterEach(() => resetSyncState())

describe('the sync at an open', () => {
  it('asks the engine and starts nothing when no sync is due (the old app is the writer)', async () => {
    const { calls, ctx } = engine(null)
    expect(await syncIfDue(ctx)).toBe('not_due')
    expect(calls).toEqual([{ path: '/api/status', method: 'GET' }])
  })

  it('runs the sync the engine says is due, and every screen reads again', async () => {
    const { calls, ctx } = engine('first_open')
    const before = currentEpoch()
    expect(await syncIfDue(ctx)).toBe('ran')
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual(['GET /api/status', 'POST /api/sync'])
    expect(currentEpoch()).toBe(before + 1)
  })

  it('runs one sync for two opens at once, and asks at most once a minute', async () => {
    const { calls, ctx } = engine('first_open')
    let now = 1_000_000
    const [a, b] = await Promise.all([syncIfDue(ctx, () => now), syncIfDue(ctx, () => now)])
    expect([a, b]).toEqual(['ran', 'ran'])
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
    now += ASK_GAP_MS - 1
    expect(await syncIfDue(ctx, () => now)).toBe('skipped')
    now += 1
    expect(await syncIfDue(ctx, () => now)).toBe('ran')
  })

  it('asks nothing with no key or with the engine switched off in Settings', async () => {
    const { calls, ctx } = engine('first_open')
    expect(await syncIfDue({ ...ctx, key: null })).toBe('skipped')
    expect(await syncIfDue({ ...ctx, engineDown: true })).toBe('skipped')
    expect(calls).toEqual([])
  })

  it('says it failed when the engine refuses (no longer the writer), and changes nothing', async () => {
    const { ctx } = engine('first_open', 409)
    const before = currentEpoch()
    expect(await syncIfDue(ctx)).toBe('failed')
    expect(currentEpoch()).toBe(before)
  })
})
