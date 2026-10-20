// The outbox (rebuild Phase 4). Every write — a check-in, a session save, a swap, a carry,
// a redo, yoga, outdoor — goes here first, with an id the phone mints (a ULID). The items
// are sent strictly in the order they were written; one that cannot be sent now (offline,
// the engine starting or down, a server error) is tried again later with a growing wait,
// and nothing after it overtakes it. An item leaves the outbox ONLY when the engine
// confirms it. The engine's saves are idempotent on the ids (rebuild rule 4), so sending an
// item again after a lost answer stores it once. A refused item (4xx: retrying cannot help)
// stays, marked, with the engine's reason, until the owner sends it again from Settings.
import { useEffect } from 'react'
import { type HealthDB, type OutboxRow } from '../db/schema'
import { ApiError, api, localDay } from './api'
import { ulid } from './ulid'

export interface Write {
  kind: string
  method: OutboxRow['method']
  path: string
  body: unknown
  day?: string
}

/** The waits after the 1st, 2nd, ... failed try; the last repeats. */
export const BACKOFF_MS = [5_000, 15_000, 60_000, 5 * 60_000, 15 * 60_000] as const

export function backoff(attempts: number): number {
  return BACKOFF_MS[Math.min(Math.max(attempts, 1), BACKOFF_MS.length) - 1]
}

/** The event that wakes the outbox loop when something is written. */
export const OUTBOX_EVENT = 'health-outbox'

function notify(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(OUTBOX_EVENT))
}

export async function enqueue(store: HealthDB, write: Write, now: Date = new Date()): Promise<string> {
  const id = ulid(now.getTime())
  await store.outbox.add({
    id,
    kind: write.kind,
    method: write.method,
    path: write.path,
    body: write.body,
    day: write.day ?? localDay(now),
    created_at: now.toISOString(),
    attempts: 0,
    next_at: now.toISOString(),
    state: 'waiting',
  })
  notify()
  return id
}

export type DrainResult = 'done' | 'later' | 'offline' | 'unauthorized' | 'busy'

export interface DrainCtx {
  key: string | null
  engineDown: boolean
  fetchImpl?: typeof fetch
  now?: () => Date
}

async function first(store: HealthDB): Promise<OutboxRow | undefined> {
  const waiting = await store.outbox.where('state').equals('waiting').toArray()
  return waiting.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))[0]
}

/** Send what can be sent now, in order. One drain at a time (Web Locks where they exist). */
export async function drain(store: HealthDB, ctx: DrainCtx): Promise<DrainResult> {
  const now = () => ctx.now?.() ?? new Date()
  const run = async (): Promise<DrainResult> => {
    if (!ctx.key) return 'unauthorized'
    for (;;) {
      const item = await first(store)
      if (!item) return 'done'
      if (new Date(item.next_at) > now()) return 'later'
      try {
        await api(item.path, {
          method: item.method,
          body: item.body,
          key: ctx.key,
          day: item.day,
          engineDown: ctx.engineDown,
          fetchImpl: ctx.fetchImpl,
        })
        await store.outbox.delete(item.seq!)
      } catch (err) {
        const e = err instanceof ApiError ? err : new ApiError('server', null, 'unknown')
        const attempts = item.attempts + 1
        if (e.kind === 'unauthorized') {
          await store.outbox.update(item.seq!, { last_error: e.code })
          return 'unauthorized'
        }
        if (e.kind === 'rejected') {
          await store.outbox.update(item.seq!, { state: 'failed', attempts, last_error: e.code })
          continue
        }
        const next = new Date(now().getTime() + backoff(attempts)).toISOString()
        await store.outbox.update(item.seq!, { attempts, next_at: next, last_error: e.code })
        return 'offline'
      }
    }
  }
  const locks = typeof navigator === 'undefined' ? undefined : navigator.locks
  if (!locks) return run()
  return locks.request('health-outbox', { ifAvailable: true }, async (lock) => (lock ? run() : 'busy'))
}

/** Send a refused item again (Settings): it joins the queue in its old place. */
export async function retry(store: HealthDB, seq: number, now: Date = new Date()): Promise<void> {
  await store.outbox.update(seq, { state: 'waiting', next_at: now.toISOString() })
  notify()
}

/** The network is back: every waiting item may be tried at once, not after its wait. */
export async function wake(store: HealthDB, now: Date = new Date()): Promise<void> {
  await store.outbox.where('state').equals('waiting').modify({ next_at: now.toISOString() })
}

/** When the first waiting item may be tried (null when nothing waits). */
export async function nextTry(store: HealthDB): Promise<Date | null> {
  const item = await first(store)
  return item ? new Date(item.next_at) : null
}

/** Drains while the app is open: at the start, after every new write, when the phone is
 *  back online, when the app comes to the front, and when the first item's wait ends. */
export function useOutboxLoop(store: HealthDB, ctx: DrainCtx): void {
  useEffect(() => {
    if (!ctx.key) return
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false
    const go = async () => {
      clearTimeout(timer)
      if (stopped || document.visibilityState !== 'visible') return
      // A wrong key cannot get better by itself: wait until the key changes.
      if ((await drain(store, ctx)) === 'unauthorized') return
      const next = await nextTry(store)
      if (stopped || !next) return
      timer = setTimeout(() => void go(), Math.max(next.getTime() - Date.now(), 1_000))
    }
    const online = () => void wake(store).then(go)
    const visible = () => void go()
    void go()
    window.addEventListener(OUTBOX_EVENT, visible)
    window.addEventListener('online', online)
    document.addEventListener('visibilitychange', visible)
    return () => {
      stopped = true
      clearTimeout(timer)
      window.removeEventListener(OUTBOX_EVENT, visible)
      window.removeEventListener('online', online)
      document.removeEventListener('visibilitychange', visible)
    }
    // ctx is rebuilt on every render; its two values are the real inputs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store, ctx.key, ctx.engineDown])
}
