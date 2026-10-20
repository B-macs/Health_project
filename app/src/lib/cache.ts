// Cache first, then the engine (rebuild Phase 4). A screen shows the last saved answer at
// once, asks the engine, and shows the new answer when it comes. The engine may be asleep
// (Cloud Run starts in seconds) or down, and the gym has a weak signal: the screen never
// waits blank. A saved answer is replaced only by a good one.
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import type { HealthDB } from '../db/schema'
import { ApiError, api, localDay, type ApiErrorKind } from './api'
import { currentEpoch, subscribe } from './refresh'

export type FetchState = 'loading' | 'fresh' | ApiErrorKind

export interface View<T> {
  data: T | undefined
  fetchedAt: string | null
  state: FetchState
  /** The engine's own word for a refusal (its JSON error), when it refused. */
  code?: string
}

export interface Ctx {
  key: string | null
  engineDown: boolean
  fetchImpl?: typeof fetch
  now?: () => Date
}

export function cacheKey(path: string, day: string | null): string {
  return day ? `${path}|${day}` : path
}

/** Ask the engine and keep its answer. Throws an ApiError; the saved row stays. */
export async function refresh<T>(store: HealthDB, path: string, day: string | null, ctx: Ctx): Promise<T> {
  const body = await api<T>(path, {
    key: ctx.key,
    day: day ?? localDay(ctx.now?.()),
    engineDown: ctx.engineDown,
    fetchImpl: ctx.fetchImpl,
  })
  const fetchedAt = (ctx.now?.() ?? new Date()).toISOString()
  await store.cache.put({ key: cacheKey(path, day), path, day, body, fetched_at: fetchedAt })
  return body
}

/** Keep the screen a write answered with (the engine answers some writes with the whole
 *  screen), so the screen shows it at once rather than the answer from before the write. */
export async function keepAnswer(store: HealthDB, path: string, day: string | null, body: unknown,
  now: Date = new Date()): Promise<void> {
  await store.cache.put({ key: cacheKey(path, day), path, day, body, fetched_at: now.toISOString() })
}

/** The cache-first read: `show` gets the saved answer at once, then the engine's answer, or
 *  the saved answer again with why the engine did not answer. */
export async function cacheFirst<T>(store: HealthDB, path: string, day: string | null, ctx: Ctx,
  show: (view: View<T>) => void): Promise<void> {
  const saved = await store.cache.get(cacheKey(path, day))
  const kept: View<T> = { data: saved?.body as T | undefined, fetchedAt: saved?.fetched_at ?? null, state: 'loading' }
  show(kept)
  try {
    const body = await refresh<T>(store, path, day, ctx)
    const row = await store.cache.get(cacheKey(path, day))
    show({ data: body, fetchedAt: row?.fetched_at ?? null, state: 'fresh' })
  } catch (err) {
    show({ ...kept, state: err instanceof ApiError ? err.kind : 'server', code: err instanceof ApiError ? err.code : undefined })
  }
}

/** The hook a screen uses. `again()` asks the engine once more, and so does every engine
 *  sync that ran (lib/refresh.ts). It answers only for its own address: when the address
 *  changes (another day), the previous address's answer is never shown under it, not even
 *  for one frame. */
export function useCached<T>(store: HealthDB, path: string, day: string | null, ctx: Ctx):
  View<T> & { again: () => void } {
  const key = cacheKey(path, day)
  const [view, setView] = useState<View<T> & { key: string }>({ key: '', data: undefined, fetchedAt: null, state: 'loading' })
  const [tick, setTick] = useState(0)
  const again = useCallback(() => setTick((t) => t + 1), [])
  const epoch = useSyncExternalStore(subscribe, currentEpoch, currentEpoch)
  useEffect(() => {
    let alive = true
    void cacheFirst<T>(store, path, day, ctx, (next) => {
      if (alive) setView({ ...next, key })
    })
    return () => {
      alive = false
    }
    // ctx is rebuilt on every render; its two values are the real inputs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store, path, day, ctx.key, ctx.engineDown, tick, epoch])
  if (view.key !== key) return { data: undefined, fetchedAt: null, state: 'loading', again }
  return { data: view.data, fetchedAt: view.fetchedAt, state: view.state, code: view.code, again }
}

/** How old the shown answer is, in whole minutes (null when nothing is saved). */
export function ageMinutes(fetchedAt: string | null, now: Date = new Date()): number | null {
  if (!fetchedAt) return null
  return Math.max(0, Math.floor((now.getTime() - new Date(fetchedAt).getTime()) / 60_000))
}
