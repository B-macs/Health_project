// Insights › Engine data (rebuild Phase 8, inventory I52-I61): what the engine read today.
// The directive in Home's words (the shared verdict, fault F4) with its ACWR note, the stage
// progression, the biometric traffic light with its four cards and the baseline drift, the
// workload (ACWR, its two windows, the stage ceiling and its status, the 28-day AU chart),
// and the weekly volume load. Every figure, word and chart top is the engine's.
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { shortDate } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { WeekBars } from '../ui/InsightsCharts'
import { InsightsHead } from '../ui/InsightsHead'
import { Marked } from '../ui/Marked'
import { Contributor, Spinner } from '../ui/parts'

type Engine = components['schemas']['EngineDataOut']

export const ENGINE = '/api/insights/engine'

type Directive = { words: string; banner_kind: string; banner_text: string; engine_label: string; acwr_advisory: string }
type Stage = {
  stage_label: string; message: string; progress_days?: string; days_progress_pct?: number
  progress_tightness?: string; tight_progress_pct?: number
}
type Card = { key: string; label: string; value: string; comparison: string; change: string; signal: string; missing_source: string | null }
type Light = {
  status: string; overall: string | null; message: string; no_reading: boolean; cards: Card[]
  drift: { drifted: boolean; severity: string; message: string; applied: boolean; lines: string[] }
}
type Workload = {
  value: number | null; acute_avg: number | null; chronic_avg: number | null; chronic_label: string
  chronic_help: string; ceiling: number | null; status: { kind: string; text: string } | null
  chart: { dates: string[]; au: number[]; windows: string[]; hi: number }
}

/** A note in the engine's own kind: a warning or an error as an alert, information plainly. */
function Kind({ kind, text, testId }: { kind: string; text: string; testId?: string }) {
  return <p className={kind === 'info' ? 'notice' : 'alert'} data-testid={testId}>{text}</p>
}

function DirectiveCard({ d }: { d: Directive }) {
  return (
    <section className="card group card--hi" data-testid="directive" data-kind={d.banner_kind}>
      <span className="eyebrow">{S.eng.directive}</span>
      <span className="answer">{d.words}</span>
      {d.banner_text && <p className="caption">{d.banner_text}</p>}
      {d.engine_label && <p className="caption">{S.eng.engineLabel(d.engine_label)}</p>}
    </section>
  )
}

function StageCard({ s, reduced }: { s: Stage; reduced: boolean }) {
  const shown = (v?: string) => v && v !== '—'
  return (
    <section className="card group" data-testid="stage">
      <h2 className="eyebrow">{S.eng.stage}</h2>
      <p><b>{s.stage_label}</b></p>
      <p className="caption">{s.message}</p>
      {shown(s.progress_days) && (
        <Contributor name={S.eng.painFree} value={S.eng.pct(s.days_progress_pct ?? 0)} fraction={s.days_progress_pct ?? 0}
          note={s.progress_days ?? ''} reduced={reduced} />
      )}
      {shown(s.progress_tightness) && (
        <Contributor name={S.eng.tightness} value={S.eng.pct(s.tight_progress_pct ?? 0)} fraction={s.tight_progress_pct ?? 0}
          note={s.progress_tightness ?? ''} reduced={reduced} />
      )}
    </section>
  )
}

function LightCard({ l }: { l: Light }) {
  return (
    <section className="card group" data-testid="traffic-light">
      <h2 className="eyebrow">{S.eng.light}</h2>
      {l.no_reading ? <p className="notice">{l.message}</p> : (
        <>
          <p data-signal={l.overall ?? 'grey'}><Marked text={S.eng.overall(l.overall ?? '', l.message)} /></p>
          <div className="mcards">
            {l.cards.map((c) => (
              <div key={c.key} className="card mcard" data-signal={c.signal}>
                <span className="eyebrow">{c.label}</span>
                <span className="num figure__value">{c.value}</span>
                <span className="caption">{c.comparison}</span>
                <span className="caption mcard__source">{c.change}</span>
                {c.missing_source && <span className="caption">{S.eng.pending(c.missing_source)}</span>}
              </div>
            ))}
          </div>
          {l.drift.drifted && (
            <div className="alert group" data-testid="drift">
              <b>{S.eng.drift(l.drift.severity)}</b>
              <span>{l.drift.message}</span>
              {l.drift.applied && <span>{S.eng.driftApplied}</span>}
              {l.drift.lines.length > 0 && (
                <details className="guide">
                  <summary className="tapline">{S.eng.driftDetail}</summary>
                  {l.drift.lines.map((line) => <p key={line} className="caption">{line}</p>)}
                </details>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function WorkloadCard({ w }: { w: Workload }) {
  const acute = w.chart.windows.findIndex((x) => x.startsWith('Acute'))
  const value = (v: number | null) => (v == null ? S.ins.none : String(v))
  return (
    <section className="card group" data-testid="workload">
      <h2 className="eyebrow">{S.eng.workload}</h2>
      <div className="figures">
        <div className="figure">
          <span className="eyebrow">{S.eng.acwr}</span>
          <span className="num figure__value">{w.value ? w.value.toFixed(3) : S.ins.none}</span>
        </div>
        <div className="figure">
          <span className="eyebrow">{S.eng.ceiling}</span>
          <span className="num figure__value">{value(w.ceiling)}</span>
        </div>
        <div className="figure">
          <span className="eyebrow">{S.eng.acute}</span>
          <span className="num figure__value">{value(w.acute_avg)}</span>
        </div>
        <div className="figure">
          <span className="eyebrow">{w.chronic_label}</span>
          <span className="num figure__value">{value(w.chronic_avg)}</span>
          {w.chronic_help && <span className="caption">{w.chronic_help}</span>}
        </div>
      </div>
      {w.status && <Kind kind={w.status.kind} text={w.status.text} testId="acwr-status" />}
      <WeekBars values={w.chart.au} hi={w.chart.hi} labels={[]} label={S.eng.auChart}
        strongFrom={acute >= 0 ? acute : undefined} />
      <p className="caption">{S.eng.auChart}</p>
    </section>
  )
}

function VolumeCard({ weeks, hi }: { weeks: { week_start: string; kg: number }[]; hi: number }) {
  const any = weeks.some((w) => w.kg > 0)
  return (
    <section className="card group" data-testid="volume">
      <h2 className="eyebrow">{S.eng.volume}</h2>
      <p className="caption">{S.eng.volumeWhy}</p>
      {any ? (
        <WeekBars values={weeks.map((w) => w.kg)} hi={hi} labels={weeks.map((w) => shortDate(w.week_start))}
          label={S.eng.volumeChart} />
      ) : <p className="notice">{S.eng.noVolume}</p>}
    </section>
  )
}

/** The screen drawn from one read: the tests draw it in each state. */
export function EngineBody({ view, reduced, onRefresh }: { view: View<Engine>; reduced: boolean; onRefresh: () => void }) {
  const d = view.data
  const directive = d?.directive as unknown as Directive | null | undefined
  return (
    <div className="screen insights" data-testid="engine">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.engine} />
      <Freshness view={view} />
      {/* While the engine is asked again the button turns and waits (the owner, 2026-10-21). */}
      <button className="btn btn--glass pill" onClick={onRefresh} disabled={view.state === 'loading'}
        aria-busy={view.state === 'loading'} data-testid="engine-refresh">
        {view.state === 'loading' ? <><Spinner />{S.fresh.reading}</> : S.eng.refresh}
      </button>
      {d?.load_error && <p className="alert" role="alert" data-testid="engine-unreadable">{S.eng.unreadable(d.load_error)}</p>}
      {d && !d.load_error && (
        <>
          {directive && <DirectiveCard d={directive} />}
          {directive?.acwr_advisory && <p className="caption" data-testid="acwr-advisory">{directive.acwr_advisory}</p>}
          {d.stage && <StageCard s={d.stage as unknown as Stage} reduced={reduced} />}
          {d.traffic_light && <LightCard l={d.traffic_light as unknown as Light} />}
          {d.acwr && <WorkloadCard w={d.acwr as unknown as Workload} />}
          <VolumeCard weeks={(d.volume ?? []) as { week_start: string; kg: number }[]} hi={d.volume_hi ?? 0} />
        </>
      )}
    </div>
  )
}

export function EngineScreen() {
  const { store, ctx, reduced } = useApp()
  const view = useCached<Engine>(store, ENGINE, null, ctx)
  return <EngineBody view={view} reduced={reduced} onRefresh={view.again} />
}
