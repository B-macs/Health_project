// Settings (slate; rebuild Phase 4). What the app knows about itself, most useful first:
// whether the engine answers (read cache-first: the last answer shows at once), the saves
// still waiting to send, the daily data check, the access key, the phone's storage, the
// appearance, a switch that acts as if the engine is down, the debug log kept across
// reloads, and the version line (seven taps open the console).
import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useMemo, useState } from 'react'
import { getSetting, KEYS, setSetting, type HealthDB } from '../db/schema'
import { debugLines, openConsole, tapCounter } from '../debug/console'
import type { ThemePref } from '../design/theme'
import type { components } from '../generated/api'
import { alertSupport, disableAlerts, enableAlerts, sendTestAlert, type EnableResult } from '../lib/alerts'
import { ApiError, api } from '../lib/api'
import { cacheKey, useCached, type Ctx } from '../lib/cache'
import { drain, retry, wake } from '../lib/outbox'
import { formatBytes, storageInfo, type StorageInfo } from '../lib/storage'
import { updateWaiting } from '../lib/updates'
import { S } from '../strings'
import { DataLink } from './DataTables'
import { Freshness } from '../ui/Freshness'
import { versionLine } from '../version'
import { KeyForm } from './Welcome'

type Health = components['schemas']['HealthOut']
type DataCheck = components['schemas']['DataCheckOut']

export const THEMES: ThemePref[] = ['auto', 'light', 'dark']

const LAST_CHECK = '/api/data/check/last'

function when(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function Engine({ store, ctx }: { store: HealthDB; ctx: Ctx }) {
  const view = useCached<Health>(store, '/api/health', null, ctx)
  const word = view.state === 'fresh' ? S.settings.engineUp : view.state === 'loading' ? '' : S.settings.engineDown
  return (
    <section className="card group" aria-labelledby="engine-title" data-testid="engine">
      <div className="kv">
        <h2 id="engine-title" className="eyebrow">{S.settings.engine}</h2>
        <span className="word">{word}</span>
      </div>
      {view.data && (
        <p className="caption">{S.settings.engineVersion(view.data.build.version, view.data.build.commit ?? '—')}</p>
      )}
      <Freshness view={view} />
    </section>
  )
}

function Outbox({ store, ctx }: { store: HealthDB; ctx: Ctx }) {
  const items = useLiveQuery(() => store.outbox.orderBy('seq').toArray(), [store], [])
  const waiting = items.filter((item) => item.state === 'waiting')
  const failed = items.filter((item) => item.state === 'failed')
  const next = waiting[0]?.next_at
  const sendNow = () => void wake(store).then(() => drain(store, ctx))
  return (
    <section className="card group" aria-labelledby="outbox-title" data-testid="outbox"
      data-waiting={waiting.length} data-failed={failed.length}>
      <h2 id="outbox-title" className="eyebrow">{S.settings.outbox}</h2>
      <p className="caption">
        {waiting.length === 0 && failed.length === 0 ? S.settings.outboxNone : S.settings.outboxWaiting(waiting.length)}
      </p>
      {next && <p className="caption">{S.settings.outboxNext(clockTime(next))}</p>}
      {failed.length > 0 && <p className="caption">{S.settings.outboxFailed(failed.length)}</p>}
      {failed.map((item) => (
        <div key={item.id} className="kv">
          <span className="caption">{`${S.settings.kinds[item.kind] ?? item.kind} · ${item.last_error ?? ''}`}</span>
          <button className="btn btn--glass" onClick={() => void retry(store, item.seq!)}>{S.settings.outboxAgain}</button>
        </div>
      ))}
      {waiting.length > 0 && (
        <button className="btn btn--glass btn--wide" onClick={sendNow}>{S.settings.outboxSend}</button>
      )}
    </section>
  )
}

function DataCheckCard({ store, ctx }: { store: HealthDB; ctx: Ctx }) {
  const view = useCached<DataCheck | null>(store, LAST_CHECK, null, ctx)
  const [running, setRunning] = useState(false)
  const [failed, setFailed] = useState<string | null>(null)
  const run = async () => {
    setRunning(true)
    setFailed(null)
    try {
      const body = await api<DataCheck>('/api/data/check/run', { method: 'POST', key: ctx.key, engineDown: ctx.engineDown })
      await store.cache.put({ key: cacheKey(LAST_CHECK, null), path: LAST_CHECK, day: null, body, fetched_at: new Date().toISOString() })
    } catch (err) {
      setFailed(`${S.settings.checkFailed} ${S.fresh.why[err instanceof ApiError ? err.kind : 'server']}`)
    } finally {
      setRunning(false)
      view.again()
    }
  }
  const c = view.data
  return (
    <section className="card group" aria-labelledby="check-title" data-testid="data-check">
      <h2 id="check-title" className="eyebrow">{S.settings.check}</h2>
      {c === null && <p className="caption">{S.settings.checkNone}</p>}
      {c && (
        <>
          <p className="caption">{S.settings.checkWhen(when(c.checked_at))}</p>
          <p className="caption">{c.missing_rows === 0 ? S.settings.checkClean : S.settings.checkMissing(c.missing_rows)}</p>
          {c.tables.filter((t) => t.missing > 0).map((t) => (
            <div key={t.table} className="kv">
              <span>{t.table}</span>
              <span className="num">{t.missing}</span>
            </div>
          ))}
          <p className="caption">{c.backup_day ? S.settings.checkBackup(c.backup_day) : S.settings.checkNoBackup}</p>
          {c.backup_stale && <p className="caption">{S.settings.checkStale}</p>}
        </>
      )}
      {failed && <p className="caption" role="status">{failed}</p>}
      <Freshness view={view} />
      <button className="btn btn--glass btn--wide" disabled={running} onClick={() => void run()}>
        {running ? S.settings.checkRunning : S.settings.checkNow}
      </button>
    </section>
  )
}

function AccessKey({ store }: { store: HealthDB }) {
  const [open, setOpen] = useState(false)
  return (
    <section className="card group" aria-labelledby="key-card-title">
      <h2 id="key-card-title" className="eyebrow">{S.settings.key}</h2>
      <p className="caption">{S.settings.keySaved}</p>
      {open ? (
        <KeyForm store={store} onSaved={() => setOpen(false)} />
      ) : (
        <button className="btn btn--glass btn--wide" onClick={() => setOpen(true)}>{S.settings.keyChange}</button>
      )}
    </section>
  )
}

function Storage() {
  const [info, setInfo] = useState<StorageInfo | null>(null)
  useEffect(() => {
    void storageInfo().then(setInfo)
  }, [])
  const kept = info?.persisted
  return (
    <section className="card group" aria-labelledby="storage-title">
      <h2 id="storage-title" className="eyebrow">{S.settings.storage}</h2>
      <p className="caption">
        {kept === true ? S.settings.storageKept : kept === false ? S.settings.storageNotKept : S.settings.storageUnknown}
      </p>
      {info && <p className="caption">{S.settings.storageUsed(formatBytes(info.usage), formatBytes(info.quota))}</p>}
    </section>
  )
}

function Choice<T extends string | boolean>(p: {
  label: string
  options: readonly T[]
  value: T
  name: (t: T) => string
  onChoose: (t: T) => void
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={p.label}>
      {p.options.map((option) => (
        <button key={String(option)} role="radio" aria-checked={option === p.value}
          className={`segmented__item${option === p.value ? ' segmented__item--on' : ''}`}
          onClick={() => p.onChoose(option)}>
          {p.name(option)}
        </button>
      ))}
    </div>
  )
}

/** The timer alerts (lib/alerts.ts): on from a tap, a test alert, off. */
function Alerts({ store, ctx, on }: { store: HealthDB; ctx: Ctx; on: boolean }) {
  const support = alertSupport()
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const run = (task: () => Promise<string | null>) => {
    setBusy(true)
    setNote(null)
    void task().then((text) => setNote(text)).finally(() => setBusy(false))
  }
  const words: Record<EnableResult, string | null> = {
    on: null, denied: S.settings.alertsDenied, 'not-configured': S.settings.alertsNotReady, failed: S.settings.alertsFailed,
  }
  return (
    <section className="card group" aria-labelledby="alerts-title" data-testid="alerts" data-state={on ? 'on' : support}>
      <h2 id="alerts-title" className="eyebrow">{S.settings.alerts}</h2>
      <p className="caption">{S.settings.alertsWhat}</p>
      {support === 'install-first' ? <p className="caption">{S.settings.alertsInstall}</p>
        : support === 'unsupported' ? <p className="caption">{S.settings.alertsUnsupported}</p>
          : support === 'denied' ? <p className="caption">{S.settings.alertsDenied}</p>
            : on ? (
              <>
                <p>{S.settings.alertsOn}</p>
                <div className="pair">
                  <button className="btn btn--glass" disabled={busy}
                    onClick={() => run(async () => ((await sendTestAlert(ctx)) ? S.settings.alertsTestSent : S.settings.alertsTestFailed))}>
                    {S.settings.alertsTest}
                  </button>
                  <button className="btn btn--glass" disabled={busy}
                    onClick={() => run(async () => { await disableAlerts(store, ctx); return null })}>
                    {S.settings.alertsOff}
                  </button>
                </div>
              </>
            ) : (
              <button className="btn btn--primary" disabled={busy}
                onClick={() => run(async () => words[await enableAlerts(store, ctx)])}>
                {S.settings.alertsTurnOn}
              </button>
            )}
      {note && <p className="caption" role="status">{note}</p>}
    </section>
  )
}

function Log() {
  const lines = debugLines().slice(-40).reverse()
  return (
    <section className="card group">
      <details>
        <summary className="tapline">{S.settings.log}</summary>
        <pre className="log">{lines.length ? lines.join('\n') : S.settings.logEmpty}</pre>
      </details>
    </section>
  )
}

function Version() {
  const tap = useMemo(() => tapCounter(), [])
  const [ready, setReady] = useState(false)
  useEffect(() => {
    void updateWaiting().then(setReady)
  }, [])
  return (
    <section className="card group" aria-labelledby="version-title">
      <h2 id="version-title" className="eyebrow">{S.settings.version}</h2>
      <button className="tapline" data-testid="version" onClick={() => {
        if (tap()) void openConsole()
      }}>
        {versionLine(__APP_BUILD__)}
      </button>
      <p className="caption">{S.settings.versionTap}</p>
      {ready && <p className="caption">{S.settings.updateReady}</p>}
    </section>
  )
}

const ON_OFF = [false, true] as const

export function Settings(p: { store: HealthDB; ctx: Ctx; theme: ThemePref; onTheme: (t: ThemePref) => void }) {
  const alertsOn = useLiveQuery(() => getSetting(p.store, KEYS.alerts, false), [p.store], false)
  return (
    <div className="screen settings">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.settings.title}</h1>
      </header>
      <Engine store={p.store} ctx={p.ctx} />
      <Outbox store={p.store} ctx={p.ctx} />
      <DataCheckCard store={p.store} ctx={p.ctx} />
      <DataLink />
      <Alerts store={p.store} ctx={p.ctx} on={alertsOn === true} />
      <AccessKey store={p.store} />
      <Storage />
      <section className="card group">
        <h2 className="eyebrow">{S.settings.appearance}</h2>
        <Choice label={S.settings.appearance} options={THEMES} value={p.theme}
          name={(t) => S.settings.themes[t]} onChoose={p.onTheme} />
      </section>
      <section className="card group">
        <h2 className="eyebrow">{S.settings.test}</h2>
        <div className="caption">{S.settings.engineDownTest}</div>
        <Choice<boolean> label={S.settings.engineDownTest} options={ON_OFF} value={p.ctx.engineDown}
          name={(on) => (on ? S.settings.on : S.settings.off)}
          onChoose={(on) => void setSetting(p.store, KEYS.engineDown, on)} />
      </section>
      <Log />
      <Version />
    </div>
  )
}

export function NotYet({ title }: { title: string }) {
  return (
    <div className="screen">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{title}</h1>
      </header>
      <p className="caption">{S.notYet}</p>
    </div>
  )
}
