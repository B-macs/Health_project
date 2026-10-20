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
  /** The tests' shorter limits (READ_TIMEOUT_MS, SAVED_MS). */
  readTimeoutMs?: number
  savedMs?: number
}

export function cacheKey(path: string, day: string | null): string {
  return day ? `${path}|${day}` : path
}

/** How long a screen waits for the engine before it shows its saved answer with the reason
 *  (2026-10-20: on the owner's iPhone, reads that never finished left every screen on its
 *  saved copy with no word of why, and the Strength buttons seemed dead). The Worker gives
 *  up at 60 s; an engine starting from sleep answers in about 10 s. */
export const READ_TIMEOUT_MS = 30_000
/** How long the phone's own database may take to read or keep an answer. IndexedDB can stall
 *  on iOS after the app comes back from the background; the engine is asked regardless. */
export const SAVED_MS = 3_000

/** `promise`'s value, or undefined when it fails or takes longer than `ms`. */
export function within<T>(promise: Promise<T>, ms: number): Promise<T | undefined> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(undefined), ms)
    promise.then(
      (value) => {
        clearTimeout(timer)
        resolve(value)
      },
      () => {
        clearTimeout(timer)
        resolve(undefined)
      },
    )
  })
}

function ask<T>(path: string, day: string | null, ctx: Ctx): Promise<T> {
  return api<T>(path, {
    key: ctx.key,
    day: day ?? localDay(ctx.now?.()),
    engineDown: ctx.engineDown,
    fetchImpl: ctx.fetchImpl,
    timeoutMs: ctx.readTimeoutMs ?? READ_TIMEOUT_MS,
  })
}

/** Ask the engine and keep its answer. Throws an ApiError; the saved row stays. */
export async function refresh<T>(store: HealthDB, path: string, day: string | null, ctx: Ctx): Promise<T> {
  const body = await ask<T>(path, day, ctx)
  const fetchedAt = (ctx.now?.() ?? new Date()).toISOString()
  await within(store.cache.put({ key: cacheKey(path, day), path, day, body, fetched_at: fetchedAt }),
    ctx.savedMs ?? SAVED_MS)
  return body
}

/** Keep the screen a write answered with (the engine answers some writes with the whole
 *  screen), so the screen shows it at once rather than the answer from before the write. */
export async function keepAnswer(store: HealthDB, path: string, day: string | null, body: unknown,
  now: Date = new Date()): Promise<void> {
  await store.cache.put({ key: cacheKey(path, day), path, day, body, fetched_at: now.toISOString() })
}

/** The cache-first read: `show` gets the saved answer at once, then the engine's answer, or
 *  the saved answer again with why the engine did not answer. The engine's answer is shown
 *  before it is kept, so a stalled database never holds it back, and a read that takes
 *  longer than READ_TIMEOUT_MS ends as "no connection" with the code "timeout". */
export async function cacheFirst<T>(store: HealthDB, path: string, day: string | null, ctx: Ctx,
  show: (view: View<T>) => void): Promise<void> {
  const savedMs = ctx.savedMs ?? SAVED_MS
  const saved = await within(store.cache.get(cacheKey(path, day)), savedMs)
  const kept: View<T> = { data: saved?.body as T | undefined, fetchedAt: saved?.fetched_at ?? null, state: 'loading' }
  show(kept)
  let body: T
  try {
    body = await ask<T>(path, day, ctx)
  } catch (err) {
    show({ ...kept, state: err instanceof ApiError ? err.kind : 'server', code: err instanceof ApiError ? err.code : undefined })
    return
  }
  const fetchedAt = (ctx.now?.() ?? new Date()).toISOString()
  show({ data: body, fetchedAt, state: 'fresh' })
  await within(store.cache.put({ key: cacheKey(path, day), path, day, body, fetched_at: fetchedAt }), savedMs)
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
