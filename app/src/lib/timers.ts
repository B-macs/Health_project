// The session's timers (rebuild Phase 6): a hold countdown, a rest countdown, an activity
// countdown and a count-up stopwatch, all on TIMESTAMPS, never on a counting interval. A
// timer is the moment it last started, the time it had run before that, and its length;
// what it shows is worked out from the clock whenever it is drawn. So a reload, an app
// kill, a locked phone or a hidden app cannot make it drift: on return it shows the right
// time, and a timer that ended while hidden says when it ended.
export type TimerKind = 'hold' | 'rest' | 'duration' | 'stopwatch'

export interface Timer {
  kind: TimerKind
  /** Total length in ms (0 for the stopwatch, which counts up). */
  lengthMs: number
  /** The clock (epoch ms) at the last start or resume; null while paused. */
  runningSince: number | null
  /** The time it ran before the last start or resume. */
  ranMs: number
}

export function startTimer(kind: TimerKind, lengthMs: number, now: number): Timer {
  return { kind, lengthMs, runningSince: now, ranMs: 0 }
}

export function elapsedMs(t: Timer, now: number): number {
  return t.ranMs + (t.runningSince != null ? Math.max(0, now - t.runningSince) : 0)
}

export function remainingMs(t: Timer, now: number): number {
  return Math.max(0, t.lengthMs - elapsedMs(t, now))
}

export function isRunning(t: Timer): boolean {
  return t.runningSince != null
}

/** A countdown that has run its length. A stopwatch never ends by itself. */
export function hasEnded(t: Timer, now: number): boolean {
  return t.kind !== 'stopwatch' && remainingMs(t, now) === 0
}

/** The clock at which a running countdown ends (or ended); null for a paused one or a
 *  stopwatch. */
export function endsAt(t: Timer): number | null {
  if (t.kind === 'stopwatch' || t.runningSince == null) return null
  return t.runningSince + (t.lengthMs - t.ranMs)
}

export function pauseTimer(t: Timer, now: number): Timer {
  if (t.runningSince == null) return t
  return { ...t, ranMs: elapsedMs(t, now), runningSince: null }
}

export function resumeTimer(t: Timer, now: number): Timer {
  if (t.runningSince != null) return t
  return { ...t, runningSince: now }
}

/** Add time to a countdown (the rest's +15 s). */
export function extendTimer(t: Timer, ms: number): Timer {
  return { ...t, lengthMs: t.lengthMs + ms }
}

/** A hold timer's length: the slow start the engine sends (`lead_in_seconds`, the daily
 *  tendon session, WP-40) and the hold, run as one timer, so the bell, the alert and the
 *  automatic move all keep working unchanged. */
export function holdLengthMs(ex: { hold_seconds?: number | null; lead_in_seconds?: number | null }): number {
  return ((ex.hold_seconds ?? 0) + (ex.lead_in_seconds ?? 0)) * 1000
}

/** The slow start still to run on a hold timer whose first `leadMs` are the lead-in: 0 once
 *  the hold itself runs. */
export function leadInLeftMs(t: Timer, leadMs: number, now: number): number {
  return t.kind === 'hold' && leadMs > 0 ? Math.max(0, leadMs - elapsedMs(t, now)) : 0
}

/** The whole seconds shown: remaining for a countdown (rounded up, so 0.2 s left reads 1),
 *  elapsed for the stopwatch (rounded down). */
export function shownSeconds(t: Timer, now: number): number {
  return t.kind === 'stopwatch' ? Math.floor(elapsedMs(t, now) / 1000) : Math.ceil(remainingMs(t, now) / 1000)
}

/** The 3-2-1 tick crossed between two readings: the whole second of the last three that
 *  the countdown just reached. When the clock skipped a second, only the second just
 *  reached, so two beeps never sound as one (his report, 2026-11-25). A tick a hidden app
 *  missed is not played late. */
export function ticksCrossed(t: Timer, before: number, after: number): number[] {
  if (t.kind === 'stopwatch') return []
  const a = Math.ceil(remainingMs(t, before) / 1000)
  const b = Math.ceil(remainingMs(t, after) / 1000)
  const out: number[] = []
  for (let s = a - 1; s >= b && s >= 1; s--) if (s <= 3) out.push(s)
  return after - before > 1500 ? [] : out.slice(-1)
}

/** The time from `now` to the next beep or bell a running countdown plays: the slow
 *  start's end, each of the last three seconds, and the end. Null for a stopwatch, a
 *  paused timer or one that has ended. The session screen wakes the sound this long ahead
 *  (sounds.wakeAhead). */
export function nextSoundInMs(t: Timer, leadMs: number, now: number): number | null {
  if (t.kind === 'stopwatch' || !isRunning(t)) return null
  const left = remainingMs(t, now)
  if (left === 0) return null
  const due = [leadInLeftMs(t, leadMs, now), left - 3000, left - 2000, left - 1000, left].filter((ms) => ms > 0)
  return Math.min(...due)
}
