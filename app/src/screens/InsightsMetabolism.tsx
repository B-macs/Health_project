// Insights › Metabolism (rebuild Phase 8, inventory I16-I24): body composition. The latest
// weigh-in as kilograms of fat and fat-free mass, the split of that weight, one measure over a
// period you step through, the two readings only the gym scan takes, and every other figure
// marked with what it is: measured, worked out from the weight, or not measured.
//
// The scale and the gym scan stay apart and nothing is fused (services/body_composition.py).
// Every figure, the chart's scale and labels, the change and whether it is better or worse
// for that measure are the engine's (services/metabolism_screen.py); the screen lays them out.
import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useState } from 'react'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { enqueue } from '../lib/outbox'
import { useCached, type View } from '../lib/cache'
import { yearDate } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { useKept } from '../ui/hooks'
import { DatedLine } from '../ui/InsightsCharts'
import { InsightsHead } from '../ui/InsightsHead'
import { IconBack, IconForward } from '../ui/icons'

type Schemas = components['schemas']
export type MetabolismAnswer = Schemas['MetabolismOut']

export const METABOLISM = '/api/insights/metabolism'

/** The engine's address for a choice; nothing chosen is the engine's own default, which is
 *  also what the Insights page reads, so the two share one saved answer. */
export function metabolismPath(metric: string | null, kind: string | null, offset: number): string {
  const q = new URLSearchParams()
  if (metric) q.set('metric', metric)
  if (kind) q.set('kind', kind)
  if (offset !== 0) q.set('offset', String(offset))
  const query = q.toString()
  return query ? `${METABOLISM}?${query}` : METABOLISM
}

function Unit({ unit }: { unit: string }) {
  return unit ? <span className="unit">{unit}</span> : null
}

/** The latest weigh-in as fat and fat-free kilograms (I16): the most the scale supports. */
function Composition({ latest }: { latest: MetabolismAnswer['latest'] }) {
  const fat = latest?.fat_mass_kg
  const lean = latest?.fat_free_mass_kg
  return (
    <section className="card group" aria-label={S.ins.composition} data-testid="composition">
      <span className="eyebrow">{S.ins.composition}</span>
      {latest && fat != null && lean != null ? (
        <>
          <div className="figures">
            <div className="figure">
              <span className="num tile__value">{fat.toFixed(1)}</span>
              <span className="caption">{S.ins.fat}</span>
            </div>
            <div className="figure">
              <span className="num tile__value">{lean.toFixed(1)}</span>
              <span className="caption">{S.ins.lean}</span>
            </div>
          </div>
          <span className="badge">{S.ins.measuredOn(yearDate(latest.date))}</span>
        </>
      ) : (
        <>
          <span className="num tile__value">{S.ins.none}</span>
          <span className="caption">{S.ins.noWeighIn}</span>
        </>
      )}
    </section>
  )
}

/** Fat against fat-free (I18): together they are the weight, one number told twice. */
function Split({ split }: { split: MetabolismAnswer['split'] }) {
  if (!split) return null
  const fatPct = split.fat_pct
  return (
    <section className="card group" aria-label={S.ins.splitTitle} data-testid="split">
      <div className="share" aria-hidden="true">
        <span className="share__part share__part--fat" style={{ width: `${fatPct}%` }} />
        <span className="share__part share__part--lean" style={{ width: `${100 - fatPct}%` }} />
      </div>
      <div className="kv">
        <span>{S.ins.splitFat(split.fat, fatPct)}</span>
        <span>{S.ins.splitLean(split.lean, 100 - fatPct)}</span>
      </div>
      <span className="caption">{S.ins.splitTotal(split.total)}</span>
    </section>
  )
}

/** The latest reading in the period and the change from its first (I21). */
function Readout({ d }: { d: MetabolismAnswer }) {
  const s = d.series
  const metric = d.metrics.find((m) => m.label === d.metric)
  const unit = metric?.unit ?? ''
  const dp = metric?.dp ?? 1
  const last = s.last
  const first = s.first
  const change = s.change
  return (
    <div className="figures" data-testid="metab-readout">
      <div className="figure">
        <span className="eyebrow">{last ? S.ins.latestOn(yearDate(last.date)) : S.ins.latest}</span>
        <span className="num figure__value">
          {last ? <>{last.value.toFixed(dp)}<Unit unit={unit} /></> : S.ins.none}
        </span>
      </div>
      <div className="figure" data-tone={s.tone ?? 'none'}>
        <span className="eyebrow">
          {last && first && change != null ? S.ins.changeOver(yearDate(first.date), yearDate(last.date))
            : last ? S.ins.oneReading : S.ins.change}
        </span>
        <span className="num figure__value">
          {change == null ? S.ins.none
            : <>{S.ins.signedChange(change, dp, s.tone === 'flat')}<Unit unit={unit} /></>}
        </span>
      </div>
    </div>
  )
}

/** One measure over a period (I19-I22): the measure, the period's size, the step back and
 *  forward the engine allows, the readout and the chart. */
function Progress({ d, onMetric, onKind, onStep }: {
  d: MetabolismAnswer; onMetric: (label: string) => void; onKind: (kind: string) => void; onStep: (to: number) => void
}) {
  const s = d.series
  const metric = d.metrics.find((m) => m.label === d.metric)
  return (
    <section className="card group" aria-label={S.ins.progress} data-testid="metab-progress">
      <h2 className="eyebrow">{S.ins.progress}</h2>
      <div className="chips" role="radiogroup" aria-label={S.ins.measure}>
        {d.metrics.map((m) => (
          <button key={m.label} role="radio" aria-checked={d.metric === m.label}
            className={`chip${d.metric === m.label ? ' chip--on' : ''}`} onClick={() => onMetric(m.label)}>{m.label}</button>
        ))}
      </div>
      <div className="segmented" role="radiogroup" aria-label={S.ins.period}>
        {d.ranges.map((r) => (
          <button key={r.kind} role="radio" aria-checked={d.kind === r.kind}
            className={`segmented__item${d.kind === r.kind ? ' segmented__item--on' : ''}`}
            onClick={() => onKind(r.kind)}>{r.label}</button>
        ))}
      </div>
      <div className="stepper" data-testid="metab-period">
        <button className="iconbtn" aria-label={S.ins.previousPeriod} disabled={!s.can_back}
          onClick={() => onStep(d.offset - 1)}><IconBack /></button>
        <div className="group group--centre">
          <span className="num">{s.window.label}</span>
          <span className="caption">{s.window.sub}</span>
        </div>
        <button className="iconbtn" aria-label={S.ins.nextPeriod} disabled={!s.can_forward}
          onClick={() => onStep(d.offset + 1)}><IconForward /></button>
      </div>
      <Readout d={d} />
      <DatedLine runs={s.runs} points={s.points} start={s.window.start} end={s.window.end} axis={s.axis}
        dp={metric?.dp ?? 1} label={S.ins.chartOf(d.metric, s.points.length, s.window.label)}
        emptyWord={S.ins.noReadingIn(s.window.label)} />
    </section>
  )
}

/** One figure card: its name, value and unit, when it was taken, what it is (measured,
 *  worked out, or not measured) and, for a gym-scan reading, its age. */
function FigureCard({ name, value, unit, when, source, age }: {
  name: string; value: string; unit: string; when: string; source: string; age?: string
}) {
  return (
    <div className="card mcard" data-source={source}>
      <div className="kv">
        <span className="eyebrow">{name}</span>
        <span className="caption">{when}</span>
      </div>
      <span className="num figure__value">{value}{value !== S.ins.none && <Unit unit={unit} />}</span>
      <div className="kv">
        <span className="caption mcard__source">{S.ins.source[source] ?? source}</span>
        {age && <span className="caption">{age}</span>}
      </div>
    </div>
  )
}

/** Phase angle and ECW/TBW (I23): the two readings the typed height cannot reach, and the
 *  only ones on the screen that are not the weight told again. */
function Cellular({ cell }: { cell: MetabolismAnswer['cellular'] }) {
  if (!cell) return null
  const when = yearDate(cell.date)
  const age = S.ins.daysOld(cell.days_old)
  return (
    <section className="group" aria-label={S.ins.cellular} data-testid="cellular">
      <h2 className="eyebrow">{S.ins.cellular}</h2>
      <span className="caption">{S.ins.cellularNote(cell.device)}</span>
      <div className="mcards">
        <FigureCard name={S.ins.phaseAngle} unit="°" when={when} age={age}
          value={cell.phase_angle_deg ? cell.phase_angle_deg.toFixed(1) : S.ins.none}
          source={cell.phase_angle_deg ? 'measured' : 'absent'} />
        <FigureCard name={S.ins.ecwTbw} unit="" when={when} age={age}
          value={cell.ecw_tbw != null ? cell.ecw_tbw.toFixed(3) : S.ins.none}
          source={cell.ecw_tbw != null ? 'measured' : 'absent'} />
      </div>
    </section>
  )
}

type Card = { name: string; value: number | null; unit: string; dp: number; source: string }
type Group = { group: string; blurb: string; cards: Card[] }

/** Every other figure (I24), grouped as the engine groups them, each marked with what it
 *  really is. No card says "Normal": that was no check. */
function Analysis({ d }: { d: MetabolismAnswer }) {
  const when = d.latest ? yearDate(d.latest.date) : ''
  return (
    <section className="group" aria-label={S.ins.bodyAnalysis} data-testid="analysis">
      <h2 className="eyebrow">{S.ins.bodyAnalysis}</h2>
      {(d.analysis as Group[]).map((g) => (
        <div key={g.group} className="group">
          <div className="kv">
            <span className="eyebrow">{g.group}</span>
            <span className="caption">{g.blurb}</span>
          </div>
          <div className="mcards">
            {g.cards.map((c) => (
              <FigureCard key={`${c.name}${c.unit}`} name={c.name} unit={c.unit} source={c.source}
                value={c.value == null ? S.ins.none : c.value.toFixed(c.dp)}
                when={c.value == null ? S.ins.noReading : when} />
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}

/** The latest SECA scan (WP-37), its own lane: each figure (a blank one reads not measured)
 *  with its change since the scan before, and each arm's and leg's muscle, right against
 *  left. Every figure is the engine's. */
export function Seca({ seca }: { seca: MetabolismAnswer['seca'] }) {
  if (!seca) {
    return (
      <section className="card group" aria-label={S.ins.seca} data-testid="seca">
        <h2 className="eyebrow">{S.ins.seca}</h2>
        <p className="caption">{S.ins.secaNone}</p>
      </section>
    )
  }
  return (
    <section className="card group" aria-label={S.ins.seca} data-testid="seca">
      <h2 className="eyebrow">{S.ins.seca}</h2>
      <span className="badge">{S.ins.measuredOn(yearDate(seca.date))}</span>
      <div className="figures">
        {seca.figures.map((f) => (
          <div key={f.key} className="figure" data-key={f.key}>
            <span className="eyebrow">{f.label}</span>
            <span className="num figure__value">
              {f.value == null ? S.ins.notMeasured : f.value.toFixed(f.dp)}
              {f.value != null && <Unit unit={f.unit} />}
            </span>
            {f.change != null && <span className="caption">{S.ins.secaChange(f.change, f.dp, f.unit)}</span>}
          </div>
        ))}
      </div>
      {seca.sides.map((side) => (
        <p key={side.label} className="kv">
          <span>{S.ins.secaSide(side.label)}</span>
          <span className="caption">{S.ins.secaSides(side.left_kg, side.right_kg, side.right_vs_left_pct ?? null)}</span>
        </p>
      ))}
      {seca.torso_kg != null && <p className="caption">{S.ins.secaTorso(seca.torso_kg)}</p>}
      {seca.height_cm != null && <p className="caption">{S.ins.secaHeight(seca.height_cm)}</p>}
      <p className="caption">{S.ins.secaLane}</p>
    </section>
  )
}

/** Add a SECA scan (WP-37): the machine's table export, sent through the outbox like every
 *  write; the screen reads again once the engine has it. */
function SecaImport({ onStored }: { onStored: () => void }) {
  const { store } = useApp()
  const [id, setId] = useState<string | null>(null)
  const state = useLiveQuery(async () => {
    if (!id) return null
    const row = await store.outbox.where('id').equals(id).first()
    return row ? (row.state === 'failed' ? 'refused' : 'waiting') : 'stored'
  }, [store, id])
  useEffect(() => {
    if (state === 'stored') onStored()
    // once, when the engine has it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])
  const pick = async (file: File | undefined) => {
    if (!file) return
    const csv = await file.text()
    setId(await enqueue(store, { kind: 'seca', method: 'POST', path: `${METABOLISM}/seca`, body: { csv } }))
  }
  return (
    <section className="group" data-testid="seca-import">
      <label className="btn btn--glass btn--wide">
        {S.ins.secaAdd}
        <input type="file" accept=".csv,text/csv" hidden onChange={(e) => void pick(e.target.files?.[0])} />
      </label>
      {state && <p className="caption" data-state={state}>{S.ins.secaState[state]}</p>}
    </section>
  )
}

/** The screen drawn from one read: `view` is the chosen measure and period, `kept` the last
 *  answer shown (the parts that do not depend on the choice stay while another loads). */
export function MetabolismBody({ view, kept, onMetric, onKind, onStep, onStored }: {
  view: View<MetabolismAnswer>; kept: MetabolismAnswer | undefined
  onMetric: (label: string) => void; onKind: (kind: string) => void; onStep: (to: number) => void
  /** A SECA scan reached the engine: read again. */
  onStored?: () => void
}) {
  const d = view.data
  return (
    <div className="screen insights" data-testid="metabolism">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.metabolism} />
      <Freshness view={view} />
      {kept && (
        <>
          <Seca seca={kept.seca} />
          {onStored && <SecaImport onStored={onStored} />}
          <Composition latest={kept.latest} />
          {kept.load_error && <p className="alert" data-testid="metab-load-error">{S.ins.readFailed(kept.load_error)}</p>}
          <Split split={kept.split} />
          {d ? <Progress d={d} onMetric={onMetric} onStep={onStep} onKind={onKind} /> : (
            <section className="card group" aria-label={S.ins.progress}>
              <h2 className="eyebrow">{S.ins.progress}</h2>
              <p className="caption">{S.fresh.loading}</p>
            </section>
          )}
          <Cellular cell={kept.cellular} />
          <Analysis d={kept} />
        </>
      )}
    </div>
  )
}

export function MetabolismScreen() {
  const { store, ctx } = useApp()
  const [metric, setMetric] = useState<string | null>(null)
  const [kind, setKind] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const view = useCached<MetabolismAnswer>(store, metabolismPath(metric, kind, offset), null, ctx)
  const kept = useKept(view.data)
  return (
    <MetabolismBody view={view} kept={kept} onMetric={setMetric} onStep={setOffset} onStored={view.again}
      onKind={(next) => {
        // A new period size opens on the period that holds today.
        setKind(next)
        setOffset(0)
      }} />
  )
}
