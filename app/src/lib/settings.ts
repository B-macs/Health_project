// The phone's settings as React state (rebuild Phase 4). The access key, the appearance
// and the debug switches live in the phone's database (db/schema.ts), never in a URL.
// main.tsx reads them once before the first paint, so the app never flashes the wrong
// appearance; after that the screens follow every change live.
import { useLiveQuery } from 'dexie-react-hooks'
import type { ThemePref } from '../design/theme'
import { KEYS, type HealthDB } from '../db/schema'

export interface AppSettings {
  key: string | null
  theme: ThemePref
  engineDown: boolean
  installSkipped: boolean
  /** The timer alerts are on (lib/alerts.ts). */
  alerts: boolean
  /** The session's bells and beeps are on (lib/sounds.ts); on unless switched off. */
  bells: boolean
}

export const DEFAULT_SETTINGS: AppSettings = {
  key: null,
  theme: 'auto',
  engineDown: false,
  installSkipped: false,
  alerts: false,
  bells: true,
}

const THEMES: readonly ThemePref[] = ['auto', 'light', 'dark']

export async function readSettings(store: HealthDB): Promise<AppSettings> {
  const rows = await store.settings.toArray()
  const value = (key: string) => rows.find((row) => row.key === key)?.value
  const key = value(KEYS.accessKey)
  const theme = value(KEYS.theme)
  return {
    key: typeof key === 'string' && key ? key : null,
    theme: THEMES.includes(theme as ThemePref) ? (theme as ThemePref) : 'auto',
    engineDown: value(KEYS.engineDown) === true,
    installSkipped: value(KEYS.installSkipped) === true,
    alerts: value(KEYS.alerts) === true,
    bells: value(KEYS.bells) !== false,
  }
}

export function useAppSettings(store: HealthDB, initial: AppSettings): AppSettings {
  return useLiveQuery(() => readSettings(store), [store], initial)
}
