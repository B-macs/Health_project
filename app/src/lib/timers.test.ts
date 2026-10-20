// The timers run on timestamps (rebuild Phase 6): a hidden app, a locked phone or a reload
// cannot make them drift. The gate's timer_drift counter reads this file's results: any
// error over one second after a simulated background is a failure here.
import { describe, expect, it } from 'vitest'
import {
  elapsedMs, endsAt, extendTimer, hasEnded, pauseTimer, remainingMs, resumeTimer, shownSeconds, startTimer,
  ticksCrossed,
} from './timers'

const T0 = 1_760_000_000_000

describe('a countdown', () => {
  it('after a long background shows the right time, with no drift', () => {
    const rest = startTimer('rest', 90_000, T0)
    // The phone was locked for 61.4 s: no interval ran, the clock says where it is.
    expect(remainingMs(rest, T0 + 61_400)).toBe(28_600)
    expect(shownSeconds(rest, T0 + 61_400)).toBe(29)
    expect(Math.abs(remainingMs(rest, T0 + 61_400) - (90_000 - 61_400))).toBeLessThan(1000)
  })

  it('that ended while hidden says when it ended', () => {
    const hold = startTimer('hold', 30_000, T0)
    expect(hasEnded(hold, T0 + 300_000)).toBe(true)
    expect(endsAt(hold)).toBe(T0 + 30_000)
    expect(shownSeconds(hold, T0 + 300_000)).toBe(0)
  })

  it('pauses and resumes without losing or gaining time', () => {
    let t = startTimer('hold', 20_000, T0)
    t = pauseTimer(t, T0 + 5_000)
    expect(remainingMs(t, T0 + 60_000)).toBe(15_000)
    t = resumeTimer(t, T0 + 60_000)
    expect(remainingMs(t, T0 + 70_000)).toBe(5_000)
    expect(endsAt(t)).toBe(T0 + 75_000)
  })

  it('the rest can be made longer (+15 s)', () => {
    const t = extendTimer(startTimer('rest', 60_000, T0), 15_000)
    expect(remainingMs(t, T0 + 60_000)).toBe(15_000)
  })

  it('reads 1 until the last moment and 0 only at the end', () => {
    const t = startTimer('hold', 3_000, T0)
    expect(shownSeconds(t, T0 + 2_800)).toBe(1)
    expect(shownSeconds(t, T0 + 3_000)).toBe(0)
  })
})

describe('the stopwatch', () => {
  it('counts up, never ends by itself, and survives a background', () => {
    const w = startTimer('stopwatch', 0, T0)
    expect(shownSeconds(w, T0 + 95_900)).toBe(95)
    expect(hasEnded(w, T0 + 10 * 60_000)).toBe(false)
    expect(endsAt(w)).toBeNull()
    expect(elapsedMs(pauseTimer(w, T0 + 41_000), T0 + 999_999)).toBe(41_000)
  })
})

describe('the 3-2-1 ticks', () => {
  it('ring as the last three seconds pass', () => {
    const t = startTimer('rest', 10_000, T0)
    expect(ticksCrossed(t, T0 + 6_900, T0 + 7_100)).toEqual([3])
    expect(ticksCrossed(t, T0 + 7_900, T0 + 8_100)).toEqual([2])
    expect(ticksCrossed(t, T0 + 5_000, T0 + 5_500)).toEqual([])
  })

  it('a tick a hidden app missed is not played late', () => {
    const t = startTimer('rest', 10_000, T0)
    expect(ticksCrossed(t, T0 + 1_000, T0 + 9_500)).toEqual([])
  })
})
