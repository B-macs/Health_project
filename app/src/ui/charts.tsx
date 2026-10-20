// The detail screens' charts (rebuild Phase 5), drawn as SVG from the engine's series.
//
// The engine sends everything a chart needs: the values, the rounded axis the line is drawn
// against, the tick labels as fractions (x across, y from the top), and one tap band per
// slot with the reading under it (services/dashboard.py hit_bands, value_axis). The phone
// only draws: no scale, no tick and no band is computed here, so the Streamlit charts and
// these cannot drift apart. A tap selects a band (a button over the chart: no link, no page
// load; Key Rule 17) and the point's detail shows below the chart.
import { useState, type ReactNode } from 'react'
import type { components } from '../generated/api'
import { S } from '../strings'
import { IconClose } from './icons'

type Schemas = components['schemas']
export type PointDetail = Schemas['PointDetail']
type Tick = Schemas['AxisTick']
type Axis = Schemas['ValueAxis']
type Band = Schemas['TapBand']
type Strip = Schemas['Strip']
type Movement = Schemas['MovementStrip']

const W = 320
const H = 120

/** The line's path: one segment per run of readings, broken where a reading is missing. */
export function linePath(values: readonly (number | null)[], axis: Axis): string {
  const n = values.length
  const span = axis.hi - axis.lo || 1
  let path = ''
  let open = false
  values.forEach((v, i) => {
    if (v == null) {
      open = false
      return
    }
    const x = n > 1 ? (i / (n - 1)) * W : W / 2
    const y = ((axis.hi - v) / span) * H
    path += `${open ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
    open = true
  })
  return path
}

function y(value: number, axis: Axis): number {
  return ((axis.hi - value) / (axis.hi - axis.lo || 1)) * H
}

export function PointPanel({ detail, onClose, onOpen }: {
  detail: PointDetail
  onClose: () => void
  onOpen?: (day: string) => void
}) {
  return (
    <div className="point" role="status">
      <div className="point__head">
        <span className="point__title">{detail.title}</span>
        <button className="iconbtn iconbtn--small" aria-label={S.charts.close} onClick={onClose}>
          <IconClose />
        </button>
      </div>
      {[...detail.rows, ...detail.extra].map((row) => (
        <div key={row.label} className="kv">
          <span className="caption">{row.label}</span>
          <span>{row.value}</span>
        </div>
      ))}
      {detail.open_date && onOpen && (
        <button className="btn btn--glass btn--wide" onClick={() => onOpen(detail.open_date!)}>
          {S.charts.open(detail.open_date)}
        </button>
      )}
    </div>
  )
}

function Hits({ bands, selected, onSelect }: { bands: readonly Band[]; selected: number | null; onSelect: (i: number) => void }) {
  return (
    <div className="chart__hits">
      {bands.map((band) => (
        <button key={band.index} className={`chart__hit${band.index === selected ? ' chart__hit--on' : ''}`}
          style={{ left: `${band.left * 100}%`, width: `${band.width * 100}%` }}
          aria-label={band.detail?.title ?? String(band.index)} onClick={() => onSelect(band.index)} />
      ))}
    </div>
  )
}

function Labels({ x, yTicks }: { x: readonly Tick[]; yTicks: readonly Tick[] }) {
  return (
    <>
      <div className="chart__y" aria-hidden="true">
        {yTicks.map((t) => <span key={t.text + t.at} style={{ top: `${t.at * 100}%` }}>{t.text}</span>)}
      </div>
      <div className="chart__x" aria-hidden="true">
        {x.map((t) => <span key={t.text + t.at} style={{ left: `${t.at * 100}%` }}>{t.text}</span>)}
      </div>
    </>
  )
}

/** A line over time: an overnight panel (with its average) or a 30-day trend. */
export function LineChart(p: {
  label: string
  values: readonly (number | null)[]
  axis: Axis | null
  x: readonly Tick[]
  y: readonly Tick[]
  bands: readonly Band[]
  average?: number | null
  onOpen?: (day: string) => void
}) {
  const [selected, setSelected] = useState<number | null>(null)
  if (!p.axis || p.values.filter((v) => v != null).length < 2) {
    return <p className="caption">{S.charts.empty}</p>
  }
  const axis = p.axis
  const n = p.values.length
  const chosen = selected == null ? null : p.bands.find((b) => b.index === selected) ?? null
  const v = selected == null ? null : p.values[selected]
  return (
    <figure className="chart">
      <div className="chart__plot">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={p.label}>
          {axis.ticks.map((t) => (
            <line key={t} className="chart__grid" x1="0" x2={W} y1={y(t, axis)} y2={y(t, axis)}
              vectorEffect="non-scaling-stroke" />
          ))}
          {p.average != null && (
            <line className="chart__avg" x1="0" x2={W} y1={y(p.average, axis)} y2={y(p.average, axis)}
              vectorEffect="non-scaling-stroke" />
          )}
          <path className="chart__line" d={linePath(p.values, axis)} vectorEffect="non-scaling-stroke" />
          {selected != null && v != null && (
            <line className="chart__cursor" x1={(selected / Math.max(n - 1, 1)) * W} x2={(selected / Math.max(n - 1, 1)) * W}
              y1="0" y2={H} vectorEffect="non-scaling-stroke" />
          )}
        </svg>
        <Labels x={p.x} yTicks={p.y} />
        <Hits bands={p.bands} selected={selected} onSelect={(i) => setSelected(i === selected ? null : i)} />
      </div>
      {chosen?.detail && <PointPanel detail={chosen.detail} onClose={() => setSelected(null)} onOpen={p.onOpen} />}
    </figure>
  )
}

/** One band per slot for a series without bands of its own (the 30-day trend): the
 *  slots tile the width evenly, as the engine's hit_bands does below its merge limit. */
export function slotBands(points: readonly (PointDetail | null)[]): Band[] {
  const n = points.length
  return points.map((detail, index) => ({ index, left: index / n, width: 1 / n, detail }))
}

function Runs({ strip, rows, className }: { strip: Strip; rows: (code: string) => number | null; className: (code: string) => string }) {
  const total = strip.codes.length || 1
  const rowH = H / 4
  return (
    <>
      {strip.runs.map((run) => {
        const row = rows(run.code)
        if (row == null) return null
        return (
          <rect key={`${run.start}-${run.code}`} className={className(run.code)}
            x={(run.start / total) * W} width={((run.end - run.start) / total) * W}
            y={row * rowH} height={rowH} />
        )
      })}
    </>
  )
}

/** The night's stages: Awake on top, then REM, Light and Deep (the codes 4 to 1). */
export function StageStrip({ label, strip, x, children }: { label: string; strip: Strip; x: readonly Tick[]; children?: ReactNode }) {
  const [selected, setSelected] = useState<number | null>(null)
  const chosen = selected == null ? null : strip.bands.find((b) => b.index === selected) ?? null
  return (
    <figure className="chart chart--strip">
      <div className="chart__plot">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
          <Runs strip={strip} rows={(code) => (code >= '1' && code <= '4' ? 4 - Number(code) : null)}
            className={(code) => `stage stage--${code}`} />
        </svg>
        <Labels x={x} yTicks={[]} />
        <Hits bands={strip.bands} selected={selected} onSelect={(i) => setSelected(i === selected ? null : i)} />
      </div>
      {children}
      {chosen?.detail && <PointPanel detail={chosen.detail} onClose={() => setSelected(null)} />}
    </figure>
  )
}

/** The night's movement on the same clock: taller is more movement (the classes 1 to 4). */
export function MovementStrip({ strip }: { strip: Movement }) {
  const [selected, setSelected] = useState<number | null>(null)
  const total = strip.codes.length || 1
  const chosen = selected == null ? null : strip.bands.find((b) => b.index === selected) ?? null
  return (
    <figure className="chart chart--movement">
      <div className="chart__plot">
        <svg viewBox={`0 0 ${W} ${H / 2}`} preserveAspectRatio="none" role="img" aria-label={strip.title}>
          {strip.runs.map((run) => {
            const level = Number(run.code)
            if (!(level >= 1 && level <= 4)) return null
            const h = (level / 4) * (H / 2)
            return (
              <rect key={`${run.start}-${run.code}`} className={`move move--${run.code}`}
                x={(run.start / total) * W} width={((run.end - run.start) / total) * W} y={H / 2 - h} height={h} />
            )
          })}
        </svg>
        <Hits bands={strip.bands} selected={selected} onSelect={(i) => setSelected(i === selected ? null : i)} />
      </div>
      {chosen?.detail && <PointPanel detail={chosen.detail} onClose={() => setSelected(null)} />}
    </figure>
  )
}
