// The first open (rebuild Phase 4). In the browser it first shows how to put the app on
// the Home Screen: iOS keeps the Home Screen app's data apart from Safari's, so the key
// is pasted in the app that will use it. Then the access key, pasted once and kept in
// the phone's database (never in a URL). The key is checked against the engine's
// /api/health through the Worker: only a "not right" answer stops it. With no connection,
// or the engine starting, the key is kept and checked at the next request.
import { useState } from 'react'
import { KEYS, setSetting, type HealthDB } from '../db/schema'
import { ApiError, api } from '../lib/api'
import { askToKeep } from '../lib/storage'
import { S } from '../strings'

type Outcome = 'saved' | 'wrong' | 'offline' | 'engine_down'

/** Check a pasted key and keep it unless the Worker says it is not right. */
export async function saveKey(store: HealthDB, raw: string, fetchImpl?: typeof fetch): Promise<Outcome | 'empty'> {
  const key = raw.trim()
  if (!key) return 'empty'
  let outcome: Outcome = 'saved'
  try {
    await api('/api/health', { key, fetchImpl })
  } catch (err) {
    const kind = err instanceof ApiError ? err.kind : 'server'
    if (kind === 'unauthorized') return 'wrong'
    outcome = kind === 'offline' ? 'offline' : 'engine_down'
  }
  await setSetting(store, KEYS.accessKey, key)
  return outcome
}

export function KeyForm(p: { store: HealthDB; onSaved?: () => void }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const submit = async () => {
    setBusy(true)
    setMessage(S.welcome.keyChecking)
    const outcome = await saveKey(p.store, value)
    setBusy(false)
    const text = {
      empty: S.welcome.keyEmpty,
      wrong: S.welcome.keyWrong,
      offline: S.welcome.keyOffline,
      engine_down: S.welcome.keyEngineDown,
      saved: null,
    }[outcome]
    setMessage(text)
    if (outcome === 'empty' || outcome === 'wrong') return
    setValue('')
    void askToKeep()
    p.onSaved?.()
  }
  return (
    <form className="group" onSubmit={(e) => {
      e.preventDefault()
      if (!busy) void submit()
    }}>
      <label className="eyebrow" htmlFor="access-key">{S.welcome.keyLabel}</label>
      <input id="access-key" className="field" type="password" value={value}
        autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false}
        onChange={(e) => setValue(e.target.value)} />
      <button className="btn btn--primary btn--wide" type="submit" disabled={busy}>{S.welcome.keySave}</button>
      {message && <p className="caption" role="status">{message}</p>}
    </form>
  )
}

export function Welcome(p: { store: HealthDB; standalone: boolean; installSkipped: boolean }) {
  const install = !p.standalone && !p.installSkipped
  return (
    <div className="screen">
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.welcome.title}</h1>
      </header>
      {install ? (
        <section className="card group" aria-labelledby="install-title">
          <h2 id="install-title" className="eyebrow">{S.welcome.installTitle}</h2>
          <ol className="steps">
            {S.welcome.installSteps.map((step) => <li key={step}>{step}</li>)}
          </ol>
          <p className="caption">{S.welcome.installWhy}</p>
          <p className="caption">{S.welcome.installKeyAfter}</p>
          <button className="btn btn--glass btn--wide"
            onClick={() => void setSetting(p.store, KEYS.installSkipped, true)}>
            {S.welcome.installSkip}
          </button>
        </section>
      ) : (
        <section className="card group" aria-labelledby="key-title">
          <h2 id="key-title" className="eyebrow">{S.welcome.keyTitle}</h2>
          <p className="caption">{S.welcome.keyHelp}</p>
          <KeyForm store={p.store} />
        </section>
      )}
    </div>
  )
}
