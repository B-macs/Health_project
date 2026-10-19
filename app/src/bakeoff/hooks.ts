// The bake-off's two behaviours: the mock hold timer and the screen wake lock.
// The timer walks the mock's steps (hold, hold, rest, ...) the way the real guided
// flow will walk the engine's: a hold waits for "Start", a rest runs by itself.
import { useCallback, useEffect, useState } from 'react'
import type { Step } from '../mock/generate'

export type TimerPhase = 'running' | 'paused' | 'ready' | 'finished'

export type HoldTimer = {
  index: number
  step: Step | undefined
  phase: TimerPhase
  remaining: number
  fraction: number
  pause: () => void
  resume: () => void
  start: () => void
  finishStep: () => void
  restart: () => void
  extend: (seconds: number) => void
}

export function useHoldTimer(steps: readonly Step[], startElapsedSeconds: number): HoldTimer {
  const [index, setIndex] = useState(0)
  const [phase, setPhase] = useState<TimerPhase>('running')
  const [base, setBase] = useState(startElapsedSeconds * 1000)
  const [runStart, setRunStart] = useState(() => performance.now())
  const [now, setNow] = useState(() => performance.now())
  const [extra, setExtra] = useState(0)

  useEffect(() => {
    if (phase !== 'running') return
    const id = window.setInterval(() => setNow(performance.now()), 200)
    return () => window.clearInterval(id)
  }, [phase])

  const step = steps[index]
  const total = step ? step.seconds * 1000 + extra : 0
  const elapsed = phase === 'running' ? base + Math.max(0, now - runStart) : base

  const run = useCallback(() => {
    const t = performance.now()
    setRunStart(t)
    setNow(t)
    setPhase('running')
  }, [])

  const advance = useCallback(() => {
    const next = index + 1
    setBase(0)
    setExtra(0)
    setIndex(next)
    if (next >= steps.length) setPhase('finished')
    else if (steps[next].kind === 'rest') run()
    else setPhase('ready')
  }, [index, steps, run])

  useEffect(() => {
    if (phase === 'running' && step && elapsed >= total) advance()
  }, [phase, step, elapsed, total, advance])

  return {
    index,
    step,
    phase,
    remaining: Math.max(0, Math.ceil((total - elapsed) / 1000)),
    fraction: total ? Math.min(1, elapsed / total) : 1,
    pause: () => {
      setBase(elapsed)
      setPhase('paused')
    },
    resume: run,
    start: () => {
      setBase(0)
      run()
    },
    finishStep: advance,
    restart: () => {
      setIndex(0)
      setBase(0)
      setExtra(0)
      run()
    },
    extend: (seconds: number) => setExtra((x) => x + seconds * 1000),
  }
}

/** Keeps the screen on while `active`; true while the iPhone holds the lock. */
export function useWakeLock(active: boolean): boolean {
  const [held, setHeld] = useState(false)
  useEffect(() => {
    if (!active || !('wakeLock' in navigator)) return
    let lock: WakeLockSentinel | null = null
    let stopped = false
    const request = async () => {
      try {
        const next = await navigator.wakeLock.request('screen')
        if (stopped) {
          await next.release()
          return
        }
        lock = next
        setHeld(true)
        next.addEventListener('release', () => setHeld(false))
      } catch {
        setHeld(false)
      }
    }
    void request()
    const onVisible = () => {
      if (document.visibilityState === 'visible') void request()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      stopped = true
      document.removeEventListener('visibilitychange', onVisible)
      void lock?.release().catch(() => undefined)
    }
  }, [active])
  return held
}

/**
 * A ring or bar that grows to its value once, when it first shows, unless the iPhone
 * asks for less motion. After that it follows its value at once (the stylesheet's
 * transition smooths it): waiting for an animation frame on every change left a ring
 * that changes five times a second stuck at zero when frames were slow.
 */
export function useGrow(target: number, reduced: boolean): number {
  const [grown, setGrown] = useState(reduced)
  useEffect(() => {
    if (grown) return
    const frame = window.requestAnimationFrame(() => setGrown(true))
    const fallback = window.setTimeout(() => setGrown(true), 60)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(fallback)
    }
  }, [grown])
  return grown ? target : 0
}

export function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
