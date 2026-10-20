// The shell's small rules (rebuild Phase 4): when an update may take over, the training
// session kept across a restart, the settings read before the first paint, the bytes
// shown in Settings, the freshness line, the debug log and its seven taps, and the key
// check on the first open.
import { describe, expect, it, vi } from 'vitest'
import { HealthDB, KEYS, setSetting } from '../db/schema'
import { debugLines, debugLog, loadLog, tapCounter } from '../debug/console'
import { saveKey } from '../screens/Welcome'
import { S } from '../strings'
import { freshnessText } from '../ui/Freshness'
import { endSession, loadSession, sessionActive, startSession } from './session'
import { DEFAULT_SETTINGS, readSettings } from './settings'
import { formatBytes } from './storage'
import { mayTakeUpdate } from './updates'

let n = 0
const freshDb = () => new HealthDB(`shell-test-${++n}-${Date.now()}`)

describe('an app update', () => {
  const idle = { waiting: true, controlled: true, idle: true, reloading: false }

  it('takes over only when one waits, the page is controlled, and nothing runs', () => {
    expect(mayTakeUpdate(idle)).toBe(true)
    expect(mayTakeUpdate({ ...idle, idle: false })).toBe(false)
    expect(mayTakeUpdate({ ...idle, waiting: false })).toBe(false)
    expect(mayTakeUpdate({ ...idle, controlled: false })).toBe(false)
    expect(mayTakeUpdate({ ...idle, reloading: true })).toBe(false)
  })
})

describe('the training session', () => {
  it('survives a restart, and only its end clears it', async () => {
    const name = `session-test-${Date.now()}`
    const store = new HealthDB(name)
    await startSession(store, { kind: 'frame' }, new Date('2026-10-20T07:00:00Z'))
    expect(sessionActive()).toBe(true)
    store.close()
    const again = new HealthDB(name)
    const row = await loadSession(again)
    expect(row?.started_at).toBe('2026-10-20T07:00:00.000Z')
    expect(sessionActive()).toBe(true)
    await endSession(again)
    expect(sessionActive()).toBe(false)
    expect(await loadSession(again)).toBeUndefined()
  })
})

describe('the settings', () => {
  it('fall back to the defaults, then read what was saved', async () => {
    const store = freshDb()
    expect(await readSettings(store)).toEqual(DEFAULT_SETTINGS)
    await setSetting(store, KEYS.accessKey, 'k1')
    await setSetting(store, KEYS.theme, 'dark')
    await setSetting(store, KEYS.engineDown, true)
    expect(await readSettings(store)).toEqual({ key: 'k1', theme: 'dark', engineDown: true, installSkipped: false })
  })

  it('ignore an appearance they do not know', async () => {
    const store = freshDb()
    await setSetting(store, KEYS.theme, 'neon')
    expect((await readSettings(store)).theme).toBe('auto')
  })
})

describe('bytes', () => {
  it('read as iOS Settings shows them', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1_234_567)).toBe('1.2 MB')
    expect(formatBytes(64_000_000_000)).toBe('64 GB')
    expect(formatBytes(null)).toBe('—')
  })
})

describe('the freshness line', () => {
  const now = new Date('2026-10-20T07:10:00Z')

  it('is quiet when the engine answered', () => {
    expect(freshnessText({ data: {}, fetchedAt: '2026-10-20T07:10:00Z', state: 'fresh' }, now)).toBe(S.fresh.justNow)
    expect(freshnessText({ data: {}, fetchedAt: '2026-10-20T07:07:00Z', state: 'fresh' }, now)).toBe(S.fresh.ago(3))
  })

  it('says it shows saved data, and why, when the engine did not answer', () => {
    const text = freshnessText({ data: {}, fetchedAt: '2026-10-20T07:07:00Z', state: 'engine_unavailable' }, now)
    expect(text).toContain(S.fresh.saved)
    expect(text).toContain(S.fresh.ago(3))
    expect(text).toContain(S.fresh.why.engine_unavailable)
  })

  it('says why when nothing is saved yet', () => {
    const text = freshnessText({ data: undefined, fetchedAt: null, state: 'offline' }, now)
    expect(text).toBe(`${S.fresh.nothingSaved} ${S.fresh.why.offline}`)
  })

  it('counts hours and days past an hour', () => {
    expect(S.fresh.ago(90)).toBe('Updated 1 h ago')
    expect(S.fresh.ago(3000)).toBe('Updated 2 d ago')
  })
})

describe('the debug log', () => {
  it('is kept across a restart', async () => {
    const store = freshDb()
    debugLog('test: kept', { n: 1 }, store)
    await vi.waitFor(async () => expect(await store.debuglog.count()).toBe(1))
    await loadLog(store)
    expect(debugLines().some((line) => line.includes('test: kept'))).toBe(true)
  })

  it('opens the console on the seventh quick tap, not on slow ones', () => {
    let t = 0
    const tap = tapCounter(() => t)
    for (let i = 0; i < 6; i++) {
      expect(tap()).toBe(false)
      t += 300
    }
    expect(tap()).toBe(true)
    const slow = tapCounter(() => t)
    for (let i = 0; i < 7; i++) {
      expect(slow()).toBe(false)
      t += 5_000
    }
  })
})

describe('the key on the first open', () => {
  const answer = (status: number, body: unknown) =>
    vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } }))

  it('is kept when the engine answers, trimmed', async () => {
    const store = freshDb()
    expect(await saveKey(store, '  k1 \n', answer(200, { status: 'ok' }))).toBe('saved')
    expect((await readSettings(store)).key).toBe('k1')
  })

  it('is not kept when the Worker says it is not right', async () => {
    const store = freshDb()
    expect(await saveKey(store, 'wrong', answer(401, { error: 'unauthorized' }))).toBe('wrong')
    expect((await readSettings(store)).key).toBeNull()
  })

  it('is kept when the engine is starting: the Worker already checked the key', async () => {
    const store = freshDb()
    expect(await saveKey(store, 'k1', answer(503, { error: 'engine_unavailable' }))).toBe('engine_down')
    expect((await readSettings(store)).key).toBe('k1')
  })

  it('is kept with no connection, to be checked at the next request', async () => {
    const store = freshDb()
    const offline = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    expect(await saveKey(store, 'k1', offline)).toBe('offline')
    expect((await readSettings(store)).key).toBe('k1')
  })

  it('an empty paste is refused', async () => {
    const store = freshDb()
    const fetchImpl = answer(200, {})
    expect(await saveKey(store, '   ', fetchImpl)).toBe('empty')
    expect(fetchImpl).not.toHaveBeenCalled()
  })
})
