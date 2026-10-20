// The screen wake lock, the rings' grow-in, and the timer's clock text. The session's
// timers themselves run on timestamps (lib/timers.ts).
import { useCallback, useEffect, useState } from 'react'

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
