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

/** The whole seconds shown: remaining for a countdown (rounded up, so 0.2 s left reads 1),
 *  elapsed for the stopwatch (rounded down). */
export function shownSeconds(t: Timer, now: number): number {
  return t.kind === 'stopwatch' ? Math.floor(elapsedMs(t, now) / 1000) : Math.ceil(remainingMs(t, now) / 1000)
}

/** The 3-2-1 ticks crossed between two readings: each whole second of the last three that
 *  the countdown passed. A tick a hidden app missed is not played late. */
export function ticksCrossed(t: Timer, before: number, after: number): number[] {
  if (t.kind === 'stopwatch') return []
  const a = Math.ceil(remainingMs(t, before) / 1000)
  const b = Math.ceil(remainingMs(t, after) / 1000)
  const out: number[] = []
  for (let s = a - 1; s >= b && s >= 1; s--) if (s <= 3) out.push(s)
  return after - before > 1500 ? [] : out
}
