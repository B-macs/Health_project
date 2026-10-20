// The service worker and app updates (rebuild Phase 4, Lauscher's lesson). A new version
// installs in the background and then WAITS; it takes over only when the app starts or
// comes back to the front with no training session in progress. iOS does not always fire
// controllerchange, so a timer reloads as well.
import { debugLog } from '../debug/console'

export interface UpdateState {
  waiting: boolean
  controlled: boolean
  idle: boolean
  reloading: boolean
}

/** Take the waiting version now? Only when one waits, this page is controlled (not the
 *  first install), nothing is in progress, and no reload has started. */
export function mayTakeUpdate(s: UpdateState): boolean {
  return s.waiting && s.controlled && s.idle && !s.reloading
}

export function registerServiceWorker(idle: () => boolean): void {
  if (!('serviceWorker' in navigator) || !import.meta.env.PROD) return
  let reloading = false
  const apply = (registration: ServiceWorkerRegistration) => {
    const waiting = registration.waiting
    const take = mayTakeUpdate({
      waiting: Boolean(waiting),
      controlled: Boolean(navigator.serviceWorker.controller),
      idle: idle(),
      reloading,
    })
    if (!take || !waiting) {
      if (waiting && !idle()) debugLog('update: waiting for the session to end')
      return
    }
    reloading = true
    debugLog('update: the new version takes over, reloading')
    const reload = () => window.location.reload()
    navigator.serviceWorker.addEventListener('controllerchange', reload, { once: true })
    setTimeout(reload, 3000)
    waiting.postMessage({ type: 'SKIP_WAITING' })
  }
  navigator.serviceWorker
    .register('/sw.js', { scope: '/', updateViaCache: 'none' })
    .then((registration) => {
      apply(registration)
      registration.addEventListener('updatefound', () => {
        registration.installing?.addEventListener('statechange', () => apply(registration))
      })
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState !== 'visible') return
        apply(registration)
        registration.update().catch(() => undefined)
      })
    })
    .catch((err) => debugLog('service worker: not registered', { error: String(err) }))
}

/** A new version installed and waiting (Settings can offer to load it). */
export async function updateWaiting(): Promise<boolean> {
  if (!('serviceWorker' in navigator)) return false
  return Boolean((await navigator.serviceWorker.getRegistration())?.waiting)
}
