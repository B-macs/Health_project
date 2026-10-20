/// <reference lib="webworker" />
// The service worker (rebuild Phase 4; vite-plugin-pwa, injectManifest):
// - the app shell precached, so the app opens in airplane mode;
// - /api NEVER cached: there is no route for it, so it goes straight to the network and
//   the phone's database owns the data (lib/cache.ts, lib/outbox.ts);
// - it takes over the open app on its first install (clientsClaim), but a NEW version
//   waits: the app asks it to take over at a safe moment (lib/updates.ts), never during a
//   training session;
// - the timer alerts (rebuild Phase 6, lib/alerts.ts): every push shows a notification (iOS
//   takes the subscription away after pushes without one). The Worker sends a declarative
//   message iOS shows by itself (iOS 18.4+); elsewhere this worker shows it. A tap opens
//   Training.
import { clientsClaim } from 'workbox-core'
import { type PrecacheEntry, cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { S } from '../strings'

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<PrecacheEntry | string> }

clientsClaim()
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// Every page load is "/" (the app routes with #hashes), answered with the precached shell,
// except /api and /oura: Oura's login sends the phone to the Worker's /oura/callback, which
// must reach the network to finish the login (rebuild Phase 9).
export const NETWORK_ONLY_PAGES = [/^\/api\//, /^\/oura\//]
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: NETWORK_ONLY_PAGES }))

interface Alert {
  title: string
  body?: string
  lang?: string
  tag?: string
  navigate?: string
}

/** The proposed notification of a declarative push (iOS 18.4+), else the message's JSON. */
export function alertOf(event: PushEvent): Alert | null {
  const proposed = (event as PushEvent & { notification?: Notification & { navigate?: string } }).notification
  if (proposed) {
    return { title: proposed.title, body: proposed.body, lang: proposed.lang, tag: proposed.tag, navigate: proposed.navigate }
  }
  try {
    return (event.data?.json() as { notification?: Alert } | undefined)?.notification ?? null
  } catch {
    return null
  }
}

self.addEventListener('push', (event) => {
  const alert = alertOf(event) ?? { title: S.app }
  event.waitUntil(self.registration.showNotification(alert.title, {
    body: alert.body,
    lang: alert.lang,
    tag: alert.tag,
    data: { navigate: alert.navigate ?? '/#/training' },
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data as { navigate?: string } | null)?.navigate ?? '/#/training'
  event.waitUntil((async () => {
    const open = (await self.clients.matchAll({ type: 'window', includeUncontrolled: true }))[0]
    if (open) await open.focus()
    else await self.clients.openWindow(url)
  })())
})

self.addEventListener('message', (event) => {
  if ((event.data as { type?: string } | null)?.type === 'SKIP_WAITING') void self.skipWaiting()
})
