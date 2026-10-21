// Settings' sync card and the plan's first-run setup (rebuild Phase 9; inventory H57, T29).
// The sync card says which app syncs the devices, the last sync this app's engine ran with
// each step, the Oura login's state (never a token), and whether a sync is due: what the
// owner reads each day of the week after the switch-over. The plan setup shows only when no
// plan is stored (a first run) and starts the first block from the day he picks; the engine
// refuses it once a plan runs.
import { useState } from 'react'
import type { components } from '../generated/api'
import { ApiError, api, localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { S } from '../strings'

type Status = components['schemas']['StatusOut']
type SettingsAnswer = components['schemas']['SettingsOut']

const CLOCK = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
/** "Tue 20 Oct, 07:12" in the phone's own time zone. */
export const clockTime = (iso: string) => CLOCK.format(new Date(iso))

/** The sync card, drawn from the engine's status (GET /api/status). */
export function SyncCard({ status }: { status: Status | undefined }) {
  if (!status) return null
  const run = status.last_sync
  const steps = Object.entries((run?.results ?? {}) as Record<string, [boolean, string | null]>)
  return (
    <section className="card group" aria-labelledby="sync-title" data-testid="sync-card" data-writer={status.writer ?? ''}>
      <h2 className="eyebrow" id="sync-title">{S.settings.sync}</h2>
      <p>{status.writer ? (S.settings.writer[status.writer] ?? status.writer) : S.settings.writerUnknown}</p>
      <p className="caption">{run?.at ? S.settings.lastSync(clockTime(run.at)) : S.settings.noSync}</p>
      {steps.length > 0 && (
        <ul className="list" data-testid="sync-steps">
          {steps.map(([step, [ok, error]]) => (
            <li key={step} className="kv" data-ok={ok}>
              <span>{S.settings.steps[step] ?? step}</span>
              {/* A step that did nothing on purpose says why (Garmin paused after a refusal),
                  never "done" (2026-10-21: Garmin read "done" while it had refused). */}
              <span className="caption">{ok ? (error ?? S.settings.stepOk) : `${S.settings.stepFailed}${error ? `: ${error}` : ''}`}</span>
            </li>
          ))}
        </ul>
      )}
      {run?.error && <p className="alert">{S.settings.syncError(run.error)}</p>}
      {status.oura && (
        <p className="caption" data-testid="oura-login">
          {S.settings.oura(S.settings.ouraState[status.oura.state ?? ''] ?? (status.oura.state ?? ''),
            status.oura.expires_at ? clockTime(status.oura.expires_at) : null)}
        </p>
      )}
      {status.writer === 'engine' && (
        <p className="caption">{status.sync_due ? (S.settings.syncDue[status.sync_due] ?? status.sync_due) : S.settings.syncNotDue}</p>
      )}
    </section>
  )
}

/** The Oura login (rebuild Phase 9): a button that opens Oura's own login page, on only
 *  while the engine runs the syncs. Oura sends the owner back to /oura/callback, where the
 *  Worker finishes the login and opens the result page (screens/OuraDone.tsx). */
export function OuraLoginCard({ writer, busy, error, onLogin }: {
  writer: string | null | undefined; busy: boolean; error: string | null; onLogin: () => void
}) {
  const engine = writer === 'engine'
  return (
    <section className="card group" data-testid="oura-login-card">
      <h2 className="eyebrow">{S.settings.ouraLogin}</h2>
      <p className="caption">{engine ? S.settings.ouraLoginWhy : S.settings.ouraLoginLater}</p>
      {error && <p className="alert" role="alert">{error}</p>}
      <button className="btn btn--glass btn--wide" disabled={!engine || busy} onClick={onLogin}>{S.settings.ouraLoginStart}</button>
    </section>
  )
}

/** Where Oura sends the owner back: the Worker's page on this app's own address. */
export const ouraRedirect = (origin: string) => `${origin}/oura/callback`

export function OuraLogin() {
  const { store, ctx } = useApp()
  const status = useCached<Status>(store, '/api/status', null, ctx)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  async function login() {
    setBusy(true)
    setError(null)
    try {
      const answer = await api<components['schemas']['OuraLoginOut']>('/api/oura/login', {
        method: 'POST', key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl,
        body: { redirect_uri: ouraRedirect(window.location.origin) },
      })
      window.location.assign(answer.authorize_url)
    } catch (err) {
      const code = err instanceof ApiError ? err.code : ''
      setError(S.settings.ouraLoginRefused[code] ?? S.fresh.why[err instanceof ApiError ? err.kind : 'server'])
      setBusy(false)
    }
  }
  return <OuraLoginCard writer={status.data?.writer} busy={busy} error={error} onLogin={() => void login()} />
}

export function SyncStatus() {
  const { store, ctx } = useApp()
  const view = useCached<Status>(store, '/api/status', null, ctx)
  return <SyncCard status={view.data} />
}

/** The plan's start on a first run (T29): a day and one button; nothing once a plan runs. */
export function PlanStartCard({ settings, busy, done, error, onStart }: {
  settings: SettingsAnswer | undefined; busy: boolean; done: SettingsAnswer | null; error: string | null
  onStart: (day: string) => void
}) {
  const [day, setDay] = useState(localDay())
  if (done) return <p className="notice" data-testid="plan-started">{S.settings.planStarted(done.active_phase ?? null)}</p>
  if (!settings || settings.plan_running) return null
  return (
    <section className="card group" data-testid="plan-start">
      <h2 className="eyebrow">{S.settings.plan}</h2>
      <p className="caption">{S.settings.planWhy}</p>
      <input className="field" type="date" aria-label={S.settings.plan} value={day} onChange={(e) => setDay(e.target.value)} />
      {error && <p className="alert" role="alert">{error}</p>}
      <button className="btn btn--primary" disabled={busy || !day} onClick={() => onStart(day)}>{S.settings.planStart}</button>
    </section>
  )
}

export function PlanStart() {
  const { store, ctx } = useApp()
  const view = useCached<SettingsAnswer>(store, '/api/settings', null, ctx)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<SettingsAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)
  async function start(day: string) {
    setBusy(true)
    setError(null)
    try {
      setDone(await api<SettingsAnswer>('/api/settings/plan-start', {
        method: 'PUT', key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl, body: { start_date: day },
      }))
    } catch (err) {
      const code = err instanceof ApiError ? err.code : ''
      setError(S.settings.planRefused[code] ?? S.fresh.why[err instanceof ApiError ? err.kind : 'server'])
    } finally {
      setBusy(false)
    }
  }
  return <PlanStartCard settings={view.data} busy={busy} done={done} error={error} onStart={(day) => void start(day)} />
}
