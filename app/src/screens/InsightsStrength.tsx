// Insights › Strength, redone (the owner, 2026-10-20: "Can you review that page and redo
// it"). One answer draws the whole page: the headline, the weekly trend, each body area, the
// training volume and the muscle-balance findings. No part of the page waits for a request
// of its own, so nothing on it can look dead on a weak signal (his five buttons each waited
// for one). Every number is the engine's (services/strength_screen.py); the page lays the
// numbers out and words their states.
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { longDate, shortDate } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { InsightsHead } from '../ui/InsightsHead'
import { StackedWeeks, WeekLine } from '../ui/InsightsCharts'
import { Contributor } from '../ui/parts'

type Schemas = components['schemas']
export type StrengthAnswer = Schemas['StrengthOut']

export const STRENGTH = '/api/insights/strength'
export const REFERENCE_MISSING = 'strength_reference_missing'

/** The body areas' order and their chart shades (the share bar's). */
const AREAS = ['upper_body', 'core', 'lower_body'] as const

/** The headline (I5, I6): his lifts as a % of 2025. */
function Headline({ d }: { d: StrengthAnswer }) {
  return (
    <section className="card group" aria-label={S.ins.overall}>
      <span className="eyebrow">{S.ins.overall}</span>
      <span className="num masthead__value" data-testid="overall">
        {d.overall == null ? S.ins.none : S.ins.pct(d.overall)}
      </span>
      <span className="caption">{S.ins.scale}</span>
      <span className="caption">{S.ins.updated(longDate(d.today))}</span>
    </section>
  )
}

/** The weekly trend (I9): each week's lifts against 2025, and the headline as it read. */
function Trend({ d }: { d: StrengthAnswer }) {
  const weeks = d.trend ?? []
  const axis = { lo: d.trend_axis?.lo ?? 0, hi: d.trend_axis?.hi ?? 100 }
  return (
    <section className="card group" aria-label={S.ins.trend} data-testid="trend">
      <h2 className="eyebrow">{S.ins.trend}</h2>
      <WeekLine level={weeks.map((w) => w.level)} measured={weeks.map((w) => w.measured)} axis={axis}
        labels={weeks.map((w) => w.label)} label={S.ins.trendChart} emptyWord={S.ins.noProgress}
        valueText={S.ins.pct} />
      <p className="caption">{S.ins.trendKey}</p>
    </section>
  )
}

function areaValue(a: Schemas['AreaRow']): string {
  if ((a.state === 'measured' || a.state === 'hold_time') && a.pct_of_2025 != null) return S.ins.pct(a.pct_of_2025)
  return a.state === 'too_few' ? S.ins.notYet : S.ins.none
}

function areaFraction(a: Schemas['AreaRow']): number | null {
  if (a.pct_of_2025 != null) return Math.min(1, a.pct_of_2025 / 100)
  return a.progress ?? null
}

function areaNote(a: Schemas['AreaRow']): string {
  if (a.state === 'measured') return S.ins.areaMeasured(a.lifts)
  if (a.state === 'too_few') return S.ins.areaTooFew
  if (a.state === 'hold_time') return S.ins.areaHold(a.hold_date ? shortDate(a.hold_date) : '')
  return a.region === 'core' ? S.ins.areaNoneCore : S.ins.areaNone
}

/** Each body area (I12, I13): a number only once the engine may show one. */
function Areas({ d, reduced }: { d: StrengthAnswer; reduced: boolean }) {
  return (
    <section className="card group" aria-label={S.ins.areas} data-testid="body-parts">
      <h2 className="eyebrow">{S.ins.areas}</h2>
      {(d.areas ?? []).map((a) => (
        <div key={a.region} data-region={a.region} data-state={a.state}
          className={a.state === 'none' ? 'contrib--off' : undefined}>
          <Contributor name={S.ins.region[a.region] ?? a.region} value={areaValue(a)}
            fraction={areaFraction(a)} note={areaNote(a)} reduced={reduced} />
        </div>
      ))}
    </section>
  )
}

/** The training volume (I8, I10, I11): the last full week against the one before, this
 *  week so far, the weeks by body area, and the work not counted in kilograms. */
function Volume({ v }: { v: Schemas['VolumeOut'] }) {
  const full = v.last_full
  const now = v.this_week
  return (
    <section className="card group" aria-label={S.ins.volume} data-testid="volume">
      <h2 className="eyebrow">{S.ins.volume}</h2>
      <div className="figures">
        <div className="figure" data-testid="last-full-week">
          <span className="eyebrow">{full ? S.ins.lastFullWeek(full.label) : S.ins.lastFullWeek('')}</span>
          <span className="num figure__value">{full ? S.ins.kg(full.kg) : S.ins.none}</span>
          <span className="caption">{full ? S.ins.vsWeekBefore(full.pct, full.delta) : S.ins.noFullWeek}</span>
        </div>
        <div className="figure" data-testid="this-week">
          <span className="eyebrow">{S.ins.thisWeekSoFar(now?.label ?? '')}</span>
          <span className="num figure__value">{now ? S.ins.kg(now.kg) : S.ins.none}</span>
          <span className="caption">{now ? S.ins.trainingDays(now.days) : ''}</span>
        </div>
      </div>
      <StackedWeeks label={S.ins.volumeChart} hi={v.hi}
        weeks={v.weeks.map((w) => ({ label: w.label, current: w.current,
          parts: AREAS.map((key) => ({ key, value: w[key] })) }))} />
      <ul className="areakey" aria-hidden="true">
        {AREAS.map((key) => (
          <li key={key} className="areakey__item">
            <span className={`areakey__chip areakey__chip--${key}`} />
            {S.ins.region[key]}
          </li>
        ))}
      </ul>
      {v.unloaded.length > 0 && (
        <div className="group" data-testid="unloaded">
          <span className="caption">{S.ins.notInKg}</span>
          {(['last_full', 'this_week'] as const).map((week) => {
            const lines = v.unloaded.filter((u) => u.week === week)
            if (lines.length === 0) return null
            return (
              <div key={week} className="group">
                <span className="eyebrow">{S.ins.weekWord[week]}</span>
                {lines.map((u) => (
                  <span key={`${week}-${u.area}`} className="kv">
                    <span>{S.ins.region[u.area] ?? u.area}</span>
                    <span>{u.text}</span>
                  </span>
                ))}
              </div>
            )
          })}
        </div>
      )}
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
export function StrengthBody({ view, reduced }: { view: View<StrengthAnswer>; reduced: boolean }) {
  const d = view.data
  return (
    <div className="screen insights" data-testid="strength">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.strength} />
      <Freshness view={view} />
      {!d && view.code === REFERENCE_MISSING && <p className="notice" data-testid="reference-missing">{S.ins.referenceMissing}</p>}
      {d && (
        <>
          <Headline d={d} />
          {d.load_error && <p className="alert" data-testid="load-error">{S.ins.loadError(d.load_error)}</p>}
          <Trend d={d} />
          <Areas d={d} reduced={reduced} />
          {d.volume && <Volume v={d.volume} />}
          <Imbalances d={d} />
        </>
      )}
    </div>
  )
}

export function StrengthScreen() {
  const { store, ctx, reduced } = useApp()
  const view = useCached<StrengthAnswer>(store, STRENGTH, null, ctx)
  return <StrengthBody view={view} reduced={reduced} />
}
