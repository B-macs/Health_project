// The start (rebuild Phase 4): read the debug log, the session left open (if any) and the
// settings from the phone's database BEFORE the first paint, so the app opens in the
// right appearance and on the right screen; then register the service worker, which
// takes a new version only while no training session runs. If the database cannot open
// (a private window), the app still starts, with the defaults and nothing kept.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './ui/app.css'
import { App } from './App'
import { db } from './db/schema'
import { debugLog, loadLog } from './debug/console'
import { loadSession, sessionActive } from './lib/session'
import { DEFAULT_SETTINGS, readSettings, type AppSettings } from './lib/settings'
import { audioReport, declareMixing } from './lib/sounds'
import { isStandalone } from './lib/standalone'
import { registerServiceWorker } from './lib/updates'

async function start(): Promise<void> {
  await loadLog()
  let settings: AppSettings = DEFAULT_SETTINGS
  let resume = false
  try {
    settings = await readSettings(db)
    resume = (await loadSession(db)) !== undefined
  } catch (err) {
    debugLog('start: the phone database did not open', { error: String(err) })
  }
  debugLog('start', { commit: __APP_BUILD__.commit, standalone: isStandalone(), session: resume })
  declareMixing()
  debugLog('audio at start', audioReport())
  registerServiceWorker(() => !sessionActive())
  if (import.meta.env.MODE === 'mock') {
    const { installTestHooks } = await import('./debug/testHooks')
    installTestHooks()
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App store={db} initial={settings} resume={resume} />
    </StrictMode>,
  )
}

void start()
