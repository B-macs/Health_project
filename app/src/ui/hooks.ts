// The screen wake lock, the rings' grow-in, and the timer's clock text. The session's
// timers themselves run on timestamps (lib/timers.ts).
import { useEffect, useRef, useState, type TouchEvent } from 'react'
import { holdScreen, type WakeLockHost } from '../lib/wakelock'

/** Keeps the screen on while `active` (lib/wakelock.ts); true while the iPhone holds the lock. */
export function useWakeLock(active: boolean): boolean {
  const [held, setHeld] = useState(false)
  useEffect(() => (active ? holdScreen(navigator as WakeLockHost, document, setHeld) : undefined), [active])
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

/** A sideways swipe of at least 60 px: right for the earlier one, left for the later one. A
 *  null side does nothing (the first or last day or week the engine allows). */
export function useSwipe(onPrev: (() => void) | null, onNext: (() => void) | null) {
  const start = useRef<number | null>(null)
  return {
    onTouchStart: (e: TouchEvent) => {
      start.current = e.touches[0]?.clientX ?? null
    },
    onTouchEnd: (e: TouchEvent) => {
      const from = start.current
      const to = e.changedTouches[0]?.clientX
      start.current = null
      if (from == null || to == null || Math.abs(to - from) < 60) return
      if (to > from) onPrev?.()
      if (to < from) onNext?.()
    },
  }
}

/** The last answer a screen showed, kept while another view of the same screen loads (another
 *  series or period): the parts that do not depend on the choice stay on screen meanwhile. */
export function useKept<T>(data: T | undefined): T | undefined {
  const [kept, setKept] = useState<T | undefined>(data)
  useEffect(() => {
    if (data !== undefined) setKept(data)
  }, [data])
  return data ?? kept
}

export function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
