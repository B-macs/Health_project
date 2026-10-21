// Settings › Data (rebuild Phase 8, inventory I62-I63, I78-I93): the engineering checks the
// old app's Sync tab held. What waits for the keyword parse (notes are parsed when they are
// saved), the session checks, the three data tables with their date range, what wiring
// sleep fusion into the engine would change, and the device syncs. The sync buttons stay off
// until the switch-over: one background writer at a time (rebuild rule 2), and until Phase 9
// that is the old app. Every row, count and word about the data is the engine's.
import { useState } from 'react'
import type { components } from '../generated/api'
import { ApiError, api } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { SYNC_TIMEOUT_MS } from '../lib/sync'
import { yearDate } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { InsightsHead } from '../ui/InsightsHead'
import { failure } from './FlexibilityShared'
import { SLEEP_ARCH } from './InsightsSleep'

/** The keyword parse of typed notes (its queue and the run on demand). */
export const QUEUE = '/api/insights/queue'

type Schemas = components['schemas']

export const DATA_PAGE = '/settings/data'
export const TABLES = ['engine_view', 'blend_history', 'metrics_history'] as const
const RANGED = new Set<string>(['blend_history', 'metrics_history'])

/** What waits for the keyword parse (I62), and parsing it now (I63). */
export function ParseQueueCard({ data, busy, result, error, onProcess }: {
  data: Schemas['QueueOut'] | undefined; busy: boolean; result: Schemas['ProcessOut'] | null; error: string | null
  onProcess: () => void
}) {
  const waiting = data ? data.pending_notes + data.pending_readiness : 0
  return (
    <section className="card group" data-testid="parse-queue">
      <h2 className="eyebrow">{S.data.queue}</h2>
      {data && (
        <div className="figures">
          <div className="figure">
            <span className="eyebrow">{S.data.queueNotes}</span>
            <span className="num figure__value">{data.pending_notes}</span>
          </div>
          <div className="figure">
            <span className="eyebrow">{S.data.queueCheckins}</span>
            <span className="num figure__value">{data.pending_readiness}</span>
          </div>
        </div>
      )}
      {data && waiting === 0 && <p className="caption">{S.data.queueNone}</p>}
      {waiting > 0 && <button className="btn btn--primary" disabled={busy} onClick={onProcess}>{S.data.process}</button>}
      {result && <p className="caption">{S.data.processed(result.total)}</p>}
      {result && result.errors.length > 0 && (
        <div className="alert group">
          <span>{S.data.processErrors(result.errors.length)}</span>
          {result.errors.map((e) => <span key={e}>{e}</span>)}
        </div>
      )}
      {error && <p className="alert" role="alert">{error}</p>}
    </section>
  )
}

function ParseQueue() {
  const { store, ctx } = useApp()
  const view = useCached<Schemas['QueueOut']>(store, QUEUE, null, ctx)
  const [result, setResult] = useState<Schemas['ProcessOut'] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function process() {
    setBusy(true)
    setError(null)
    try {
      setResult(await api<Schemas['ProcessOut']>(`${QUEUE}/process`, {
        method: 'POST', key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl,
      }))
      view.again()
    } catch (err) {
      setError(failure(err))
    } finally {
      setBusy(false)
    }
  }
  return <ParseQueueCard data={view.data} busy={busy} result={result} error={error} onProcess={() => void process()} />
}

/** Two sessions on one date, a day's load far over every other day's (I86). */
export function ChecksCard({ data }: { data: Schemas['SessionChecksOut'] | undefined }) {
  const warnings = data?.warnings ?? []
  return (
    <section className="card group" data-testid="session-checks">
      <h2 className="eyebrow">{S.data.checks}</h2>
      {data && warnings.length === 0 && <p className="caption">{S.data.checksNone}</p>}
      {warnings.map((w) => <p key={w} className="alert">{w}</p>)}
    </section>
  )
}

const cell = (v: unknown) => (v == null || v === '' ? S.ins.none : typeof v === 'object' ? JSON.stringify(v) : String(v))

/** One table's rows, as the engine sends them: its span, its count, and the rows. */
export function TableRows({ table, data }: { table: string; data: Schemas['DataTableOut'] | undefined }) {
  const columns = data && data.rows.length > 0 ? Object.keys(data.rows[0]!) : []
  return (
    <>
      {table === 'engine_view' && <p className="caption">{S.data.blendWhy}</p>}
      {data?.earliest && data.latest && <p className="caption">{S.data.span(yearDate(data.earliest), yearDate(data.latest))}</p>}
      {data && <p className="caption">{data.rows.length ? S.data.rows(data.rows.length) : S.data.noRows}</p>}
      {columns.length > 0 && (
        <div className="dtable">
          <table>
            <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {data!.rows.map((row, i) => (
                <tr key={i}>{columns.map((c) => <td key={c}>{cell(row[c])}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

/** One data table (I82, I83, I85), with a date range for the two history tables. */
function Table({ table }: { table: string }) {
  const { store, ctx } = useApp()
  const [range, setRange] = useState<{ start: string; end: string } | null>(null)
  const [draft, setDraft] = useState<{ start: string; end: string }>({ start: '', end: '' })
  const path = `/api/data/tables/${table}${range ? `?start=${range.start}&end=${range.end}` : ''}`
  const view = useCached<Schemas['DataTableOut']>(store, path, null, ctx)
  const d = view.data
  return (
    <div className="group" data-testid={`table-${table}`}>
      <Freshness view={view} />
      {RANGED.has(table) && (
        <>
          <div className="pair">
            <label className="group">
              <span className="caption">{S.data.from}</span>
              <input className="field" type="date" value={draft.start || d?.earliest || ''}
                onChange={(e) => setDraft({ ...draft, start: e.target.value })} />
            </label>
            <label className="group">
              <span className="caption">{S.data.to}</span>
              <input className="field" type="date" value={draft.end || d?.latest || ''}
                onChange={(e) => setDraft({ ...draft, end: e.target.value })} />
            </label>
          </div>
          <button className="btn btn--glass" onClick={() => setRange({
            start: draft.start || d?.earliest || '', end: draft.end || d?.latest || '',
          })}>{S.data.show}</button>
        </>
      )}
      <TableRows table={table} data={d} />
    </div>
  )
}

/** The tables, each read only when opened. */
function Tables() {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  return (
    <section className="group" data-testid="data-tables">
      <h2 className="eyebrow">{S.data.tables}</h2>
      {TABLES.map((t) => (
        <details key={t} className="card guide" onToggle={(e) => setOpen({ ...open, [t]: (e.target as HTMLDetailsElement).open })}>
          <summary className="tapline">{S.data.table[t]}</summary>
          {open[t] && <Table table={t} />}
        </details>
      ))}
    </section>
  )
}

export type Shadow = {
  nights_compared: number; readiness_median_delta: number | null; readiness_max_delta: number | null
  sleep_debt_now: number | null; sleep_debt_fused: number | null
  traffic_light_now: string | null; traffic_light_fused: string | null
  traffic_light_would_flip: boolean; rest_trigger_now: boolean; rest_trigger_fused: boolean
}

/** What wiring sleep fusion into the engine would change (I78). */
export function ShadowCard({ shadow: s }: { shadow: Shadow | null | undefined }) {
  const num = (v: number | null) => (v == null ? S.ins.none : v.toFixed(2))
  return (
    <section className="card group" data-testid="shadow">
      <h2 className="eyebrow">{S.data.shadow}</h2>
      <p className="caption">{S.data.shadowWhy}</p>
      {s && (
        <>
          <p>{S.data.shadowNights(s.nights_compared)}</p>
          <p>{S.data.shadowReadiness(num(s.readiness_median_delta), num(s.readiness_max_delta))}</p>
          <p>{S.data.shadowDebt(num(s.sleep_debt_now), num(s.sleep_debt_fused))}</p>
          <p>{S.data.shadowLight(s.traffic_light_now ?? S.ins.none, s.traffic_light_fused ?? S.ins.none)}</p>
          {s.traffic_light_would_flip && <p className="alert">{S.data.shadowFlip}</p>}
          {s.rest_trigger_now !== s.rest_trigger_fused && <p className="alert">{S.data.shadowRest}</p>}
        </>
      )}
    </section>
  )
}

/** The device syncs (I84, I87-I93): set up or not, and one button per sync the engine
 *  names (Settings' manual_syncs), on only while the engine runs the syncs (rebuild Phase 9).
 *  `results` holds each sync's last line: done, running, or why it was refused. */
export function SyncsCard({ settings: d, results = {}, onRun }: {
  settings: Schemas['SettingsOut'] | undefined
  results?: Record<string, string>
  onRun?: (kind: string) => void
}) {
  const engine = d?.writer === 'engine'
  const busy = Object.values(results).includes(S.data.syncRunning)
  return (
    <section className="card group" data-testid="syncs" data-writer={d?.writer ?? ''}>
      <h2 className="eyebrow">{S.data.syncs}</h2>
      {!engine && <p className="notice">{S.data.syncsWait}</p>}
      <p className="caption">{engine ? S.data.autoEngine : S.data.auto}</p>
      {d && <p>{d.garmin_configured ? S.data.garminOn : S.data.garminOff}</p>}
      {d && <p>{d.oura_configured ? S.data.ouraOn : S.data.ouraOff}</p>}
      {(d?.manual_syncs ?? []).map((kind) => (
        <div key={kind} className="group">
          <button className="btn btn--glass" disabled={!engine || busy} title={engine ? undefined : S.data.syncsWait}
            onClick={() => onRun?.(kind)}>{S.data.syncButtons[kind] ?? kind}</button>
          {results[kind] && <p className="caption" role="status" data-sync={kind}>{results[kind]}</p>}
        </div>
      ))}
    </section>
  )
}

/** The syncs card with its buttons wired to the engine (POST /api/data/sync/{kind}). */
function Syncs({ settings }: { settings: Schemas['SettingsOut'] | undefined }) {
  const { ctx } = useApp()
  const [results, setResults] = useState<Record<string, string>>({})
  async function run(kind: string) {
    setResults((r) => ({ ...r, [kind]: S.data.syncRunning }))
    try {
      await api<Schemas['ManualSyncOut']>(`/api/data/sync/${encodeURIComponent(kind)}`, {
        method: 'POST', key: ctx.key, engineDown: ctx.engineDown, fetchImpl: ctx.fetchImpl, timeoutMs: SYNC_TIMEOUT_MS,
      })
      setResults((r) => ({ ...r, [kind]: S.data.syncDone }))
    } catch (err) {
      const code = err instanceof ApiError ? err.code : ''
      setResults((r) => ({ ...r, [kind]: S.data.syncRefused[code] ?? S.data.syncFailed }))
    }
  }
  return <SyncsCard settings={settings} results={results} onRun={(kind) => void run(kind)} />
}

export function DataScreen() {
  const { store, ctx } = useApp()
  const checks = useCached<Schemas['SessionChecksOut']>(store, '/api/data/session-checks', null, ctx)
  const arch = useCached<Schemas['SleepArchitectureOut']>(store, SLEEP_ARCH, null, ctx)
  const settings = useCached<Schemas['SettingsOut']>(store, '/api/settings', null, ctx)
  return (
    <div className="screen settings" data-testid="data">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.data.title} back="/settings" backLabel={S.settings.title} />
      <p className="caption">{S.data.store}</p>
      <ParseQueue />
      <ChecksCard data={checks.data} />
      <Tables />
      <ShadowCard shadow={arch.data?.shadow as Shadow | null | undefined} />
      <Syncs settings={settings.data} />
    </div>
  )
}

/** The way in from Settings. */
export function DataLink() {
  const { go } = useApp()
  return (
    <section className="card group">
      <button className="tapline kv" onClick={() => go(DATA_PAGE)}>
        <span>{S.data.open}</span>
        <span className="caption">{S.ins.open}</span>
      </button>
    </section>
  )
}
