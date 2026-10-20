// The screen stays on during a session (rebuild Phase 6, inventory T88: a new phone
// requirement; the Streamlit page could not keep it on, and a locked phone stopped its
// timers). iOS lets go of the lock whenever the app leaves the front, so it is asked for
// again each time the app comes back. Without the Screen Wake Lock API nothing happens and
// the screen says nothing about it.
export interface WakeLockHost {
  wakeLock?: { request(type: 'screen'): Promise<WakeLockSentinel> }
}

type VisibilityHost = Pick<Document, 'visibilityState' | 'addEventListener' | 'removeEventListener'>

/** Hold the screen on; `onHeld` hears whether the lock is held. Returns the release. */
export function holdScreen(nav: WakeLockHost, doc: VisibilityHost, onHeld: (held: boolean) => void): () => void {
  const wakeLock = nav.wakeLock
  if (!wakeLock) return () => undefined
  let lock: WakeLockSentinel | null = null
  let stopped = false
  const request = async () => {
    try {
      const next = await wakeLock.request('screen')
      if (stopped) {
        await next.release()
        return
      }
      lock = next
      onHeld(true)
      next.addEventListener('release', () => onHeld(false))
    } catch {
      onHeld(false)
    }
  }
  void request()
  const onVisible = () => {
    if (doc.visibilityState === 'visible') void request()
  }
  doc.addEventListener('visibilitychange', onVisible)
  return () => {
    stopped = true
    doc.removeEventListener('visibilitychange', onVisible)
    void lock?.release().catch(() => undefined)
  }
}
