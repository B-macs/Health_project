/// <reference lib="webworker" />
// The service worker (rebuild Phase 4; vite-plugin-pwa, injectManifest):
// - the app shell precached, so the app opens in airplane mode;
// - /api NEVER cached: there is no route for it, so it goes straight to the network and
//   the phone's database owns the data (lib/cache.ts, lib/outbox.ts);
// - it takes over the open app on its first install (clientsClaim), but a NEW version
//   waits: the app asks it to take over at a safe moment (lib/updates.ts), never during a
//   training session.
import { clientsClaim } from 'workbox-core'
import { type PrecacheEntry, cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<PrecacheEntry | string> }

clientsClaim()
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// Every page load is "/" (the app routes with #hashes), answered with the precached shell.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }))

self.addEventListener('message', (event) => {
  if ((event.data as { type?: string } | null)?.type === 'SKIP_WAITING') void self.skipWaiting()
})
