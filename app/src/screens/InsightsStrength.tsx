// Insights › Strength (rebuild Phase 8, inventory I5-I15): the overall strength score and
// whether it is still calibrating, the progress of one series (the score's weekly level, or a
// body sector's tonnage) with this week against last, the work without load, the body-part
// split with each region's card, and the muscle-balance findings.
//
// What a figure may claim is the engine's rule (services/strength.py): calibration holds a
// region's index until its confidence clears, core has no kilogram scale, and the strength
// score and the tonnage are separate metrics that are never added. Every number here is the
// engine's; the screen lays them out. Until the owner's 2025 reference is in the store the
// engine refuses the screen, and the screen says why.
import { useState } from 'react'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { longDate } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { useKept } from '../ui/hooks'
import { InsightsHead } from '../ui/InsightsHead'
import { WeekBars, WeekLine } from '../ui/InsightsCharts'
import { Contributor } from '../ui/parts'

type Schemas = components['schemas']
export type StrengthAnswer = Schemas['StrengthOut']

export const STRENGTH = '/api/insights/strength'
export const REFERENCE_MISSING = 'strength_reference_missing'

/** One series' readout (I8): this week, last week and the change, as the engine reads them. */
function Readout({ r }: { r: Schemas['StrengthReadout'] }) {
  const dp = r.points ? 1 : 0
  const show = (v: number | null) => (v == null ? S.ins.none : r.points ? `${v.toFixed(1)} ${r.unit}` : S.ins.kg(v))
  return (
    <div className="figures figures--three" data-testid="readout">
      <div className="figure">
        <span className="eyebrow">{S.ins.thisWeek(r.labels[0] ?? '')}</span>
        <span className="num figure__value">{show(r.current)}</span>
      </div>
      <div className="figure">
        <span className="eyebrow">{S.ins.lastWeek(r.labels[1] ?? '')}</span>
        <span className="num figure__value">{show(r.previous)}</span>
      </div>
      <div className="figure" data-tone={r.tone ?? 'none'}>
        <span className="eyebrow">{S.ins.change}</span>
        <span className="num figure__value">
          {r.delta == null ? S.ins.none : `${S.ins.signed(r.delta, dp)}${r.points ? ` ${r.unit}` : ' kg'}`}
        </span>
        <span className="caption">
          {r.delta == null ? S.ins.noPrevious : r.pct == null ? S.ins.noPct : S.ins.pctWeek(r.pct)}
        </span>
      </div>
    </div>
  )
}

/** The chosen series' chart (I9, I10): the score's level by week, or a sector's tonnage. */
function Progress({ d }: { d: StrengthAnswer }) {
  const chosen = d.metrics.find((m) => m.label === d.metric)
  if (chosen?.key === 'score') {
    return (
      <WeekLine level={d.score_series.map((p) => (p.level as number | null) ?? null)}
        measured={d.score_series.map((p) => (p.measured as number | null) ?? null)}
        axis={{ lo: d.axis.lo, hi: d.axis.hi }} labels={d.week_labels} label={S.ins.scoreChart}
        measuredWord={S.ins.chartMeasured} emptyWord={S.ins.noProgress} />
    )
  }
  const key = (chosen?.key ?? 'overall') as 'overall' | 'upper_body' | 'core' | 'lower_body'
  return (
    <WeekBars values={d.tonnage.map((w) => w[key].kg)} hi={d.axis.hi} labels={d.week_labels}
      label={S.ins.tonnageChart(d.metric)} />
  )
}

/** The body-part split (I12) and each region's card (I13): points, share, the index or "—",
 *  and the confidence the calibration reads. */
function BodyParts({ d, reduced }: { d: StrengthAnswer; reduced: boolean }) {
  return (
    <section className="card group" aria-label={S.ins.bodyParts} data-testid="body-parts">
      <h2 className="eyebrow">{S.ins.bodyParts}</h2>
      <div className="share" aria-hidden="true">
        {d.split.map((p) => (
          <span key={p.region} className={`share__part share__part--${p.region}`} style={{ width: `${p.pct}%` }} />
        ))}
      </div>
      {d.regions.map((r) => (
        <div key={r.region} className={r.off ? 'contrib--off' : undefined} data-region={r.region} data-band={r.band}>
          <Contributor name={S.ins.region[r.region] ?? r.region} value={`${r.index_label} ${r.index_text}`}
            fraction={r.confidence} reduced={reduced}
            note={`${S.ins.regionShare(r.points, r.pct)} · ${r.band}${r.index_label === 'Index' ? ` · ${S.ins.confidence(r.confidence)}` : ''}`} />
        </div>
      ))}
      {d.unmapped.length > 0 && <p className="caption">{S.ins.unmapped(d.unmapped.join(', '))}</p>}
    </section>
  )
}

/** The muscle-balance findings (I15): the count and the two groups, each heading a state. */
function Imbalances({ d }: { d: StrengthAnswer }) {
  const groups = d.imbalances as { overactive_tight?: string[]; underactive_weak?: string[] }
  const over = groups.overactive_tight ?? []
  const under = groups.underactive_weak ?? []
  return (
    <section className="card group" aria-label={S.ins.imbalances} data-testid="imbalances">
      <div className="kv">
        <h2 className="eyebrow">{S.ins.imbalances}</h2>
        <span className="num figure__value">{S.ins.imbalanceCount(d.imbalance_count)}</span>
      </div>
      {over.length > 0 && (
        <div className="group">
          <span className="caption">{S.ins.holdTension}</span>
          <ul className="list">{over.map((name) => <li key={name}>{name}</li>)}</ul>
        </div>
      )}
      {under.length > 0 && (
        <div className="group">
          <span className="caption">{S.ins.workTooLittle}</span>
          <ul className="list">{under.map((name) => <li key={name}>{name}</li>)}</ul>
        </div>
      )}
    </section>
  )
}

/** The screen drawn from one read (cache-first): the tests draw it in each state. */
export function StrengthBody({ view, reduced, onMetric }: {
  view: View<StrengthAnswer>; reduced: boolean; onMetric: (label: string) => void
}) {
  const d = view.data
  return (
    <div className="screen insights" data-testid="strength">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.strength} />
      <Freshness view={view} />
      {!d && view.code === REFERENCE_MISSING && <p className="notice" data-testid="reference-missing">{S.ins.referenceMissing}</p>}
      {d && (
        <>
          <section className="card group" aria-label={S.ins.overall}>
            <span className="eyebrow">{S.ins.overall}</span>
            <div className="kv">
              <span className="num tile__value" data-testid="overall">{d.overall == null ? S.ins.none : d.overall.toFixed(1)}</span>
              {d.calibrating && <span className="badge" data-testid="calibrating">{S.ins.calibrating}</span>}
            </div>
            <span className="caption">{S.ins.points} · {S.ins.scale}</span>
            <span className="caption">{S.ins.updated(longDate(d.today))}</span>
          </section>
          {d.load_error && <p className="alert" data-testid="load-error">{S.ins.loadError(d.load_error)}</p>}
          <section className="card group" aria-label={S.ins.progress}>
            <h2 className="eyebrow">{S.ins.progress}</h2>
            <div className="segmented segmented--wrap" role="radiogroup" aria-label={S.ins.progress}>
              {d.metrics.map((m) => (
                <button key={m.label} role="radio" aria-checked={d.metric === m.label}
                  className={`segmented__item${d.metric === m.label ? ' segmented__item--on' : ''}`}
                  onClick={() => onMetric(m.label)}>{m.label}</button>
              ))}
            </div>
            <Readout r={d.readout} />
            <Progress d={d} />
            {d.unloaded.length > 0 && (
              <div className="group" data-testid="unloaded">
                <span className="caption">{S.ins.workWithoutLoad}</span>
                {d.unloaded.map((u) => <span key={u.label} className="kv"><span>{u.label}</span><span>{u.text}</span></span>)}
              </div>
            )}
          </section>
          <BodyParts d={d} reduced={reduced} />
          <Imbalances d={d} />
        </>
      )}
    </div>
  )
}

export function StrengthScreen() {
  const { store, ctx, reduced } = useApp()
  const [metric, setMetric] = useState<string | null>(null)
  const view = useCached<StrengthAnswer>(store, metric ? `${STRENGTH}?metric=${encodeURIComponent(metric)}` : STRENGTH, null, ctx)
  // While another series loads, the last answer stays on screen rather than a blank page.
  const kept = useKept(view.data)
  return <StrengthBody view={view.data ? view : { ...view, data: kept }} reduced={reduced} onMetric={setMetric} />
}
