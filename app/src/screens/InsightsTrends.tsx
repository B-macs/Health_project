// Insights › Trends (rebuild Phase 8, inventory I65-I72): the check-ins over time, and the
// multi-week analysis once there is enough data. The body areas he selected most, the
// tightness and pain of every check-in (with the note's keyword reading where the note was
// read; the owner, 2026-10-20), the parsed entries by warning level, the data gate, the
// recovery direction with its slopes and notable correlations, and what they read as (worked
// out on load, from templates). Every figure, word and scale is the engine's.
import { useState } from 'react'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { DatedLines } from '../ui/InsightsCharts'
import { InsightsHead } from '../ui/InsightsHead'
import { Marked, plain } from '../ui/Marked'
import { Contributor } from '../ui/parts'

type Trends = components['schemas']['TrendsOut']

export const TRENDS = '/api/insights/trends'

type Region = { region: string; mentions: number; share: number }
type Point = { date: string; self_reported: number | null; parsed_severity: number | null; pain: number | null }
type Axis = { lo: number; hi: number; y_labels: string[]; x_labels: string[]; start: string; end: string }
type Entry = { date: string; tightness: number | null; pain: number | null; severity: number | null; parts: string; sensation: string }
type Gate = { bio_days: number; sessions: number; needed: number; enough: boolean }
type Analysis = {
  recovery_label: string
  slopes: Record<string, string>[]
  notable: { pair: string; lag_days: number; r: number; strength: string; direction: string }[]
  interpretation: {
    headline: string; recovery_label: string; load_management_note: string
    correlations: { variable_pair: string; lag_days: number; clinical_note: string }[]
    recommendations: string[]
  }
}

const SERIES = ['self_reported', 'parsed_severity', 'pain'] as const
const LEVELS = ['none', 'monitor', 'flag'] as const

const shown = (v: number | null | undefined) => (v == null ? S.ins.none : plain(v))

function Timeline({ points, axis }: { points: Point[]; axis: Axis }) {
  return (
    <section className="card group" data-testid="timeline">
      <h2 className="eyebrow">{S.trend.timeline}</h2>
      <DatedLines start={axis.start} end={axis.end} axis={axis} label={S.trend.timeline}
        series={SERIES.map((key) => ({ name: S.trend.series[key], points: points.map((p) => ({ date: p.date, value: p[key] })) }))} />
      <div className="legend">
        {SERIES.map((key, k) => <span key={key} className={`legend__item legend__item--${k}`}>{S.trend.series[key]}</span>)}
      </div>
      <p className="caption">{S.trend.timelineWhy}</p>
    </section>
  )
}

function Levels({ levels }: { levels: Record<string, Entry[]> }) {
  const [level, setLevel] = useState<string | null>(null)
  const rows = level ? levels[level] ?? [] : []
  return (
    <section className="card group" data-testid="levels">
      <h2 className="eyebrow">{S.trend.levels}</h2>
      <div className="trio">
        {LEVELS.map((l) => {
          const n = (levels[l] ?? []).length
          return (
            <button key={l} className={`btn btn--glass${level === l ? ' btn--on' : ''}`} disabled={n === 0}
              aria-pressed={level === l} onClick={() => setLevel(l)}>{S.trend.levelButton(S.warn.level[l] ?? l, n)}</button>
          )
        })}
      </div>
      {rows.map((r, i) => (
        <div key={`${r.date}${i}`} className="group">
          <p><b>{r.date}</b> · {S.trend.entry(shown(r.tightness), shown(r.pain))}{r.severity != null ? S.trend.severity(plain(r.severity)) : ''}</p>
          {r.parts && <p className="caption">{S.warn.areas(r.parts)}</p>}
          {r.sensation && <p className="caption">{S.trend.sensation(r.sensation)}</p>}
        </div>
      ))}
    </section>
  )
}

function AnalysisCard({ gate, a }: { gate: Gate; a: Analysis | null }) {
  const columns = a && a.slopes.length > 0 ? Object.keys(a.slopes[0]!) : []
  return (
    <section className="card group" data-testid="analysis">
      <h2 className="eyebrow">{S.trend.analysis}</h2>
      <div className="figures">
        <div className="figure">
          <span className="eyebrow">{S.trend.bioDays}</span>
          <span className="num figure__value">{gate.bio_days}</span>
        </div>
        <div className="figure">
          <span className="eyebrow">{S.trend.sessions}</span>
          <span className="num figure__value">{gate.sessions}</span>
        </div>
      </div>
      {!gate.enough && <p className="alert" data-testid="trend-gate">{S.trend.needMore(gate.needed, gate.bio_days)}</p>}
      {a && (
        <>
          <p><Marked text={S.trend.direction(a.recovery_label)} /></p>
          {columns.length > 0 && (
            <div className="dtable">
              <table>
                <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{a.slopes.map((row, i) => <tr key={i}>{columns.map((c) => <td key={c}>{row[c]}</td>)}</tr>)}</tbody>
              </table>
            </div>
          )}
          <h3 className="eyebrow">{S.trend.notable}</h3>
          {a.notable.length > 0
            ? a.notable.map((c) => <p key={`${c.pair}${c.lag_days}`}><Marked text={S.trend.notableLine(c.pair, c.lag_days, c.r, c.strength, c.direction)} /></p>)
            : <p className="notice">{S.trend.noNotable}</p>}
          <h3 className="eyebrow">{S.trend.reading}</h3>
          <p><b>{a.interpretation.headline}</b></p>
          <p><Marked text={S.trend.trajectory(a.interpretation.recovery_label)} /></p>
          {a.interpretation.load_management_note && <p className="notice">{a.interpretation.load_management_note}</p>}
          {a.interpretation.correlations.length > 0 && (
            <>
              <h3 className="eyebrow">{S.trend.pairs}</h3>
              {a.interpretation.correlations.map((c) => (
                <div key={`${c.variable_pair}${c.lag_days}`} className="group">
                  <p><Marked text={S.trend.pairLine(c.variable_pair, c.lag_days)} /></p>
                  <p className="caption">{c.clinical_note}</p>
                </div>
              ))}
            </>
          )}
          {a.interpretation.recommendations.length > 0 && (
            <>
              <h3 className="eyebrow">{S.trend.recommendations}</h3>
              <ul className="list">{a.interpretation.recommendations.map((r) => <li key={r}>{r}</li>)}</ul>
            </>
          )}
        </>
      )}
    </section>
  )
}

/** The screen drawn from one read: the tests draw it in each state. */
export function TrendsBody({ view, reduced }: { view: View<Trends>; reduced: boolean }) {
  const d = view.data
  const regions = (d?.regions ?? []) as Region[]
  const timeline = (d?.timeline ?? []) as Point[]
  const axis = d?.timeline_axis as Axis | null | undefined
  const levels = (d?.levels ?? {}) as Record<string, Entry[]>
  const parsed = LEVELS.some((l) => (levels[l] ?? []).length > 0)
  return (
    <div className="screen insights" data-testid="trends">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.trends} />
      <Freshness view={view} />
      {d && timeline.length === 0 && <p className="notice" data-testid="no-checkins">{S.trend.noCheckins}</p>}
      {regions.length > 0 && (
        <section className="card group" data-testid="regions">
          <h2 className="eyebrow">{S.trend.regions}</h2>
          {regions.map((r) => (
            <Contributor key={r.region} name={r.region} value={S.trend.mentions(r.mentions)} fraction={r.share} note="" reduced={reduced} />
          ))}
          <p className="caption">{S.trend.regionsWhy}</p>
        </section>
      )}
      {timeline.length > 0 && axis && <Timeline points={timeline} axis={axis} />}
      {d && (parsed
        ? <Levels levels={levels} />
        : <p className="notice" data-testid="no-parsed">{S.trend.noParsed}</p>)}
      {d && <AnalysisCard gate={d.gate as unknown as Gate} a={d.analysis as unknown as Analysis | null} />}
    </div>
  )
}

export function TrendsScreen() {
  const { store, ctx, reduced } = useApp()
  return <TrendsBody view={useCached<Trends>(store, TRENDS, null, ctx)} reduced={reduced} />
}
