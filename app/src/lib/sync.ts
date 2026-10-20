// The engine's device sync, started by the phone (rebuild Phase 9; inventory H57, T5, T6).
// The engine decides when a sync is due (the owner's rule, services/sync_policy.py: the
// first open of the day, then at most once an hour while last night is missing) and runs it
// only while it is the background writer (rebuild rule 2): until the switch-over the store
// names the Streamlit app, the engine never says a sync is due, and the phone starts nothing.
// The phone asks at every open and each time the app comes back to the front, whatever the
// screen, so the first screen opened starts it (the old app synced only when Home loaded to
// its end). When a sync has run, every screen reads again (lib/refresh.ts).
import type { components } from '../generated/api'
import { api } from './api'
import type { Ctx } from './cache'
import { bump } from './refresh'

type Status = components['schemas']['StatusOut']
type SyncOut = components['schemas']['SyncOut']

export type SyncOutcome = 'ran' | 'not_due' | 'skipped' | 'failed'

/** The quickest the phone asks again after an answer (a foreground and back is no new open). */
export const ASK_GAP_MS = 60_000
/** The question "is a sync due?" gives up after this long. */
export const STATUS_TIMEOUT_MS = 30_000
/** A sync runs the device calls inside one request: the phone waits for it. */
export const SYNC_TIMEOUT_MS = 300_000

let running: Promise<SyncOutcome> | null = null
let askedAt = 0

/** For the tests: forget the last question. */
export function resetSyncState(): void {
  running = null
  askedAt = 0
}

/** Ask the engine whether a sync is due and, when it is, run it; one at a time, and at most
 *  one question a minute. A sync that ran makes every screen read again. */
export function syncIfDue(ctx: Ctx, now: () => number = Date.now): Promise<SyncOutcome> {
  if (running) return running
  if (!ctx.key || ctx.engineDown || now() - askedAt < ASK_GAP_MS) return Promise.resolve('skipped')
  askedAt = now()
  const options = { key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl }
  running = (async (): Promise<SyncOutcome> => {
    try {
      // A status read that never answers would hold `running` for good: it gives up.
      const status = await api<Status>('/api/status', { ...options, timeoutMs: STATUS_TIMEOUT_MS })
      if (!status.sync_due) return 'not_due'
      const out = await api<SyncOut>('/api/sync', { ...options, method: 'POST', body: {}, timeoutMs: SYNC_TIMEOUT_MS })
      if (out.ran) bump()
      return out.ran ? 'ran' : 'not_due'
    } catch {
      // Not the writer any more, no connection, the engine down: the next open asks again.
      return 'failed'
    } finally {
      running = null
    }
  })()
  return running
}
