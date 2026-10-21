// Insights › Sleep architecture (rebuild Phase 8, inventory I73-I77): how the ring's and the
// watch's nights are merged. The method, the counts (fused, ring only, watch only) and the
// median phantom wake, then one fused night: its three stage strips (Oura as recorded, the
// fused master, Garmin as recorded) on one clock, and its figures. A failed read is named as
// such, never shown as no nights. What wiring fusion into the engine would change is under
// Settings › Data (I78). Every figure and strip is the engine's.
import { useEffect, useState } from 'react'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { longDate } from '../lib/dates'
import { S } from '../strings'
import { StageStrip } from '../ui/charts'
import { Freshness } from '../ui/Freshness'
import { useKept } from '../ui/hooks'
import { InsightsHead } from '../ui/InsightsHead'

type Schemas = components['schemas']
type Arch = Schemas['SleepArchitectureOut']

export const SLEEP_ARCH = '/api/insights/sleep-architecture'

type Night = {
  date: string
  strips: (Schemas['Strip'] & { label: string })[]
  x_labels: Schemas['AxisTick'][]
  oura_sleep_hours: number | null; master_sleep_hours: number | null; phantom_wake_minutes: number | null
  window_overlap_pct: number | null; agreement_pct: number | null; cohen_kappa: number | null
  garmin_covered_minutes: number | null; minutes: number | null
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="figure">
      <span className="eyebrow">{label}</span>
      <span className="num figure__value">{value}</span>
    </div>
  )
}

const pct = (v: number | null) => (v == null ? S.ins.none : `${Math.round(v)}%`)

/** The screen drawn from one read (`data` the last answer shown): the tests draw it. */
export function SleepArchBody({ view, data: d, onNight }: {
  view: View<Arch>; data: Arch | undefined; onNight: (night: string) => void
}) {
  const n = d?.night as Night | null | undefined
  const counts = d?.counts
  return (
    <div className="screen insights" data-testid="sleep-arch">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.sleepArch} />
      <Freshness view={view} />
      <p className="caption">{S.arch.method}</p>
      {d?.load_error && <p className="alert" role="alert" data-testid="arch-unreadable">{S.arch.unreadable(d.load_error)}</p>}
      {d && !d.load_error && counts && (
        <section className="card group" data-testid="arch-counts">
          <div className="figures">
            <Figure label={S.arch.fused} value={String(counts.fused ?? 0)} />
            <Figure label={S.arch.ouraOnly} value={String(counts.oura_only ?? 0)} />
            <Figure label={S.arch.watchOnly} value={String(counts.watch_only ?? 0)} />
            <Figure label={S.arch.phantom} value={d.median_phantom_wake == null ? S.ins.none : S.arch.minutes(d.median_phantom_wake)} />
          </div>
        </section>
      )}
      {d && !d.load_error && !n && <p className="notice" data-testid="arch-empty">{S.arch.empty}</p>}
      {n && (
        <section className="card group" data-testid="arch-night">
          <label className="group">
            <span className="eyebrow">{S.arch.night}</span>
            <select className="field" value={n.date} onChange={(e) => onNight(e.target.value)}>
              {(d?.nights ?? []).map((day) => <option key={day} value={day}>{longDate(day)}</option>)}
            </select>
          </label>
          {n.strips.map((s) => (
            <div key={s.label} className="group">
              <span className="eyebrow">{s.label}</span>
              {s.codes ? <StageStrip label={s.label} strip={s} x={n.x_labels} /> : <p className="caption">{S.ins.none}</p>}
            </div>
          ))}
          <div className="figures">
            <Figure label={S.arch.agreement} value={pct(n.agreement_pct)} />
            <Figure label={S.arch.kappa} value={n.cohen_kappa == null ? S.ins.none : n.cohen_kappa.toFixed(2)} />
            <Figure label={S.arch.hours} value={S.arch.hoursValue(n.oura_sleep_hours, n.master_sleep_hours)} />
            <Figure label={S.arch.phantomNight} value={n.phantom_wake_minutes == null ? S.ins.none : S.arch.minutes(n.phantom_wake_minutes)} />
            <Figure label={S.arch.overlap} value={pct(n.window_overlap_pct)} />
            <Figure label={S.arch.covered} value={n.garmin_covered_minutes == null ? S.ins.none : S.arch.minutes(n.garmin_covered_minutes)} />
          </div>
        </section>
      )}
    </div>
  )
}

export function SleepArchScreen() {
  const { store, ctx } = useApp()
  const [night, setNight] = useState<string | null>(null)
  const [newest, setNewest] = useState<string | null>(null)
  const view = useCached<Arch>(store, night ? `${SLEEP_ARCH}?night=${night}` : SLEEP_ARCH, null, ctx)
  // The night the address with no night in it shows: picked again, it is read there, where
  // the phone kept it, never at a second address (2026-10-21, the warnings calendar's fault).
  const shown = (view.data?.night as { date?: string } | null | undefined)?.date ?? null
  useEffect(() => {
    if (night === null && shown) setNewest(shown)
  }, [night, shown])
  const pick = (day: string) => setNight(day === newest ? null : day)
  return <SleepArchBody view={view} data={useKept(view.data)} onNight={pick} />
}
