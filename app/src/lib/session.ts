// The training session in progress (rebuild Phase 4; Phase 6 fills its data). It lives in
// the phone's database, so it survives a reload and an app kill. While it exists the app is
// not idle: an app update waits for it (lib/updates.ts). The flag is also kept in memory,
// because the update check must answer at once.
import type { HealthDB, SessionRow } from '../db/schema'

let active = false

export function sessionActive(): boolean {
  return active
}

/** Read the stored session at start (an app kill leaves it in the database). */
export async function loadSession(store: HealthDB): Promise<SessionRow | undefined> {
  const row = await store.session.get('current')
  active = row !== undefined
  return row
}

export async function startSession(store: HealthDB, data: unknown, now: Date = new Date()): Promise<void> {
  await store.session.put({ id: 'current', started_at: now.toISOString(), data })
  active = true
}

export async function endSession(store: HealthDB): Promise<void> {
  await store.session.delete('current')
  active = false
}
