// The browser tests' handle on the outbox (rebuild Phase 4). Installed ONLY in the mock
// build (`vite build --mode mock`, the build the Playwright tests run): main.tsx imports
// this file behind `import.meta.env.MODE === 'mock'`, so a real build never contains it.
// Phase 4 had no screen that writes; the tests write through this. `session` reads the
// stored training session (Phase 6), so a test can wait until a tap is stored.
import { db, setSetting } from '../db/schema'
import { enqueue, type Write } from '../lib/outbox'
import { sessionActive } from '../lib/session'

declare global {
  interface Window {
    __health?: {
      enqueue: (write: Write) => Promise<string>
      outbox: () => Promise<unknown[]>
      sessionActive: () => boolean
      session: () => Promise<unknown>
      setSetting: (key: string, value: unknown) => Promise<void>
    }
  }
}

export function installTestHooks(): void {
  window.__health = {
    enqueue: (write) => enqueue(db, write),
    outbox: () => db.outbox.orderBy('seq').toArray(),
    sessionActive,
    session: async () => (await db.session.get('current'))?.data ?? null,
    setSetting: (key, value) => setSetting(db, key, value),
  }
}
