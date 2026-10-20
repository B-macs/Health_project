// The browser tests' handle on the outbox (rebuild Phase 4). Installed ONLY in the mock
// build (`vite build --mode mock`, the build the Playwright tests run): main.tsx imports
// this file behind `import.meta.env.MODE === 'mock'`, so a real build never contains it.
// Phase 4 has no screen that writes yet; the tests write through this instead.
import { db } from '../db/schema'
import { enqueue, type Write } from '../lib/outbox'
import { sessionActive } from '../lib/session'

declare global {
  interface Window {
    __health?: {
      enqueue: (write: Write) => Promise<string>
      outbox: () => Promise<unknown[]>
      sessionActive: () => boolean
    }
  }
}

export function installTestHooks(): void {
  window.__health = {
    enqueue: (write) => enqueue(db, write),
    outbox: () => db.outbox.orderBy('seq').toArray(),
    sessionActive,
  }
}
