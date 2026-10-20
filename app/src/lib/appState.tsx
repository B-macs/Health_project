// What every screen needs from the shell (rebuild Phase 5): the phone's database, the
// request context (the key and the "engine down" switch), and the day shown with a way
// to pick another. One React context, so a screen does not take five props.
import { createContext, useContext, type ReactNode } from 'react'
import type { HealthDB } from '../db/schema'
import type { Ctx } from './cache'
import type { Pick } from './day'

export interface AppState {
  store: HealthDB
  ctx: Ctx
  reduced: boolean
  pick: Pick | null
  /** Show a day: null (or today) for today. */
  showDay: (day: string | null) => void
  /** Open an address in the app (hash routes), from the top of the page. */
  go: (path: string) => void
}

const State = createContext<AppState | null>(null)

export function AppStateProvider({ value, children }: { value: AppState; children: ReactNode }) {
  return <State.Provider value={value}>{children}</State.Provider>
}

export function useApp(): AppState {
  const state = useContext(State)
  if (!state) throw new Error('useApp outside AppStateProvider')
  return state
}
