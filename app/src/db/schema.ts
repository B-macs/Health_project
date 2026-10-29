// The phone's database (Dexie 4 over IndexedDB), schema v1 (rebuild Phase 4).
//
// - cache: the last answer of every GET, keyed by path and day, with the time it came.
//   A screen renders from here FIRST, then asks the engine, then renders again; it never
//   shows a blank screen (lib/cache.ts).
// - outbox: every write, with an id the phone mints (a ULID), sent in order and retried
//   until the engine confirms it (lib/outbox.ts). An item leaves only on the engine's yes.
// - session: the training session in progress (Phase 6 fills it). It survives a reload and
//   an app kill; while it exists, an app update waits (lib/updates.ts).
// - settings: the access key (never in a URL), the appearance, the debug switches.
// - debuglog: what the app did, kept across reloads (debug/console.ts).
//
// Migration plan (Lauscher's rules):
// - A version only adds stores or indexes. The outbox and the session are never renamed or
//   dropped while they can hold something the engine has not received.
// - The cache can be cleared and rebuilt from the engine at any time: an upgrade that
//   changes its shape clears it in `upgrade()`.
// - When a newer version opens elsewhere, `versionchange` closes this connection and the
//   app asks to reload.
// - Every new version gets a fake-indexeddb test that upgrades a v(n-1) database with data.
import Dexie, { type Table } from 'dexie'

export const DB_NAME = 'health'

export interface CacheRow {
  key: string
  path: string
  day: string | null
  body: unknown
  fetched_at: string
}

export type OutboxState = 'waiting' | 'failed'

export interface OutboxRow {
  seq?: number
  id: string
  kind: string
  method: 'POST' | 'PUT' | 'DELETE'
  path: string
  body: unknown
  day: string
  created_at: string
  attempts: number
  next_at: string
  state: OutboxState
  last_error?: string
}

export interface SessionRow {
  id: 'current'
  started_at: string
  data: unknown
}

export interface SettingRow {
  key: string
  value: unknown
}

export interface LogRow {
  id?: number
  at: string
  line: string
}

export class HealthDB extends Dexie {
  cache!: Table<CacheRow, string>
  outbox!: Table<OutboxRow, number>
  session!: Table<SessionRow, string>
  settings!: Table<SettingRow, string>
  debuglog!: Table<LogRow, number>

  constructor(name: string = DB_NAME) {
    super(name)
    this.version(1).stores({
      cache: 'key, fetched_at',
      outbox: '++seq, &id, state, next_at',
      session: 'id',
      settings: 'key',
      debuglog: '++id, at',
    })
    this.on('versionchange', () => {
      this.close()
      return false
    })
  }
}

export const db = new HealthDB()

export async function getSetting<T>(store: HealthDB, key: string, fallback: T): Promise<T> {
  const row = await store.settings.get(key)
  return row === undefined ? fallback : (row.value as T)
}

export async function setSetting(store: HealthDB, key: string, value: unknown): Promise<void> {
  await store.settings.put({ key, value })
}

/** The settings keys, in one place. */
export const KEYS = {
  accessKey: 'access_key',
  theme: 'theme',
  engineDown: 'debug_engine_down',
  installSkipped: 'install_skipped',
  /** The timer alerts are on (lib/alerts.ts). */
  alerts: 'timer_alerts',
  /** The session's bells and beeps; absent counts as on (lib/sounds.ts, 2026-10-29). */
  bells: 'bells',
  /** The Worker's push key the phone subscribed with: a new key means subscribing again. */
  pushKey: 'push_key',
  /** The day a plan session was saved on this phone (WP-32): Training shows that day as
   *  trained before the engine's answer says so, and never offers Start again. */
  trainedOn: 'trained_on',
} as const
