// The Insights charts (rebuild Phase 8), drawn as SVG from the engine's answers. The engine
// sends each series and its scale (the strength axis, the tonnage's top, the body-reading
// chart's range and labels); the phone only places them: weeks sit evenly across, a dated
// reading sits by its date inside the period the engine names. No scale is worked out here.
const W = 320
const H = 140
const LEFT = 36
const RIGHT = 8
const TOP = 10
const BOTTOM = 22
const PW = W - LEFT - RIGHT
const PH = H - TOP - BOTTOM

type Axis = { lo: number; hi: number }

function yAt(value: number, axis: Axis): number {
  const span = axis.hi - axis.lo || 1
  return TOP + (1 - (value - axis.lo) / span) * PH
}

const xEven = (i: number, n: number) => LEFT + (n <= 1 ? PW / 2 : (i / (n - 1)) * PW)

function Frame({ yLabels, xLabels }: { yLabels: readonly string[]; xLabels: readonly string[] }) {
  return (
    <g className="ichart__frame">
      {yLabels.map((text, i) => {
        const y = TOP + (yLabels.length <= 1 ? 0 : (i / (yLabels.length - 1)) * PH)
        return (
          <g key={`y${i}`}>
            <line className="ichart__grid" x1={LEFT} x2={W - RIGHT} y1={y} y2={y} />
            <text className="ichart__label" x={LEFT - 4} y={y} textAnchor="end" dominantBaseline="middle">{text}</text>
          </g>
        )
      })}
      {xLabels.map((text, i) => (
        <text key={`x${i}`} className="ichart__label" x={xEven(i, xLabels.length)} y={H - 6}
          textAnchor={i === 0 ? 'start' : i === xLabels.length - 1 ? 'end' : 'middle'}>{text}</text>
      ))}
    </g>
  )
}

/** The value labels of an axis the engine sends only as a range: its ends and three steps
 *  between, written as the engine's own numbers. */
export function rangeLabels(axis: Axis, dp = 0): string[] {
  return Array.from({ length: 5 }, (_, i) => (axis.hi - (i / 4) * (axis.hi - axis.lo)).toFixed(dp))
}

function polyline(values: readonly (number | null)[], axis: Axis): string {
  const n = values.length
  return values.map((v, i) => (v == null ? null : `${xEven(i, n).toFixed(1)},${yAt(v, axis).toFixed(1)}`))
    .filter((p): p is string => p !== null).join(' ')
}

/** The strength score by week: the measured weeks as a dashed grey line (the evidence the
 *  score may respond to, named on the chart), the modelled level as the solid line, the
 *  latest week haloed with its value. */
export function WeekLine({ level, measured, axis, labels, label, measuredWord, emptyWord }: {
  level: readonly (number | null)[]; measured: readonly (number | null)[]; axis: Axis
  labels: readonly string[]; label: string; measuredWord: (v: number) => string; emptyWord: string
}) {
  const n = level.length
  const firstMeasured = measured.findIndex((v) => v != null)
  const lastLevel = level.reduce<number>((at, v, i) => (v == null ? at : i), -1)
  return (
    <svg className="ichart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <Frame yLabels={rangeLabels(axis)} xLabels={labels} />
      {measured.filter((v) => v != null).length > 1 && <polyline className="ichart__line ichart__line--soft" points={polyline(measured, axis)} />}
      {measured.map((v, i) => (v == null ? null
        : <circle key={`m${i}`} className="ichart__dot ichart__dot--soft" cx={xEven(i, n)} cy={yAt(v, axis)} r={3} />))}
      {firstMeasured >= 0 && (
        <text className="ichart__label ichart__label--soft" x={xEven(firstMeasured, n) + 6}
          y={yAt(measured[firstMeasured]!, axis) + 12}>{measuredWord(measured[firstMeasured]!)}</text>
      )}
      {level.filter((v) => v != null).length > 1 && <polyline className="ichart__line" points={polyline(level, axis)} />}
      {level.map((v, i) => (v == null || i === lastLevel ? null
        : <circle key={`l${i}`} className="ichart__dot" cx={xEven(i, n)} cy={yAt(v, axis)} r={3} />))}
      {lastLevel >= 0 && (
        <>
          <circle className="ichart__halo" cx={xEven(lastLevel, n)} cy={yAt(level[lastLevel]!, axis)} r={11} />
          <circle className="ichart__dot" cx={xEven(lastLevel, n)} cy={yAt(level[lastLevel]!, axis)} r={5} />
          <text className="ichart__value" x={xEven(lastLevel, n) - 6} y={yAt(level[lastLevel]!, axis) - 12}
            textAnchor="end">{level[lastLevel]!.toFixed(1)}</text>
        </>
      )}
      {firstMeasured < 0 && lastLevel < 0 && (
        <text className="ichart__label" x={W / 2} y={H / 2} textAnchor="middle">{emptyWord}</text>
      )}
    </svg>
  )
}

/** Work per week (or day) as bars from zero to the engine's top; a period with none is a short
 *  stub. The bars from `strongFrom` on (by default the last) are drawn in the strongest shade. */
export function WeekBars({ values, hi, labels, label, strongFrom }: {
  values: readonly number[]; hi: number; labels: readonly string[]; label: string; strongFrom?: number
}) {
  const n = values.length
  const slot = PW / Math.max(n, 1)
  const width = slot * 0.56
  const axis = { lo: 0, hi: hi || 1 }
  return (
    <svg className="ichart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <Frame yLabels={rangeLabels(axis)} xLabels={[]} />
      {values.map((v, i) => {
        const x = LEFT + slot * i + (slot - width) / 2
        const y = v > 0 ? yAt(v, axis) : TOP + PH - 2
        return (
          <g key={i}>
            <rect className={`ichart__bar${i >= (strongFrom ?? n - 1) ? ' ichart__bar--now' : ''}`} x={x} y={y}
              width={width} height={Math.max(2, TOP + PH - y)} rx={3} />
            <text className="ichart__label" x={x + width / 2} y={H - 6} textAnchor="middle">{labels[i] ?? ''}</text>
          </g>
        )
      })}
    </svg>
  )
}

type Dated = { date: string; value: number }

const dayNumber = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / 86_400_000

/** Dated readings inside a period: a line through each run the engine sends (a long gap
 *  is never bridged), a dot per reading, the latest haloed with its value. With no reading
 *  in the period (no scale either) the chart says so. */
export function DatedLine({ runs, points, start, end, axis, dp, label, emptyWord }: {
  runs: readonly (readonly Dated[])[]; points: readonly Dated[]; start: string; end: string
  axis: { lo: number; hi: number; y_labels: readonly string[]; x_labels: readonly string[] } | null | undefined
  dp: number; label: string; emptyWord: string
}) {
  const lo = dayNumber(start)
  const span = Math.max(1, dayNumber(end) - lo)
  const xAt = (iso: string) => LEFT + ((dayNumber(iso) - lo) / span) * PW
  const last = points[points.length - 1]
  if (!axis || !last) {
    return (
      <svg className="ichart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label}: ${emptyWord}`}>
        <text className="ichart__label" x={W / 2} y={H / 2} textAnchor="middle">{emptyWord}</text>
      </svg>
    )
  }
  return (
    <svg className="ichart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <Frame yLabels={axis.y_labels} xLabels={axis.x_labels} />
      {runs.filter((run) => run.length > 1).map((run, i) => (
        <polyline key={i} className="ichart__line" points={run.map((p) => `${xAt(p.date).toFixed(1)},${yAt(p.value, axis).toFixed(1)}`).join(' ')} />
      ))}
      {points.map((p, i) => <circle key={i} className="ichart__dot ichart__dot--soft" cx={xAt(p.date)} cy={yAt(p.value, axis)} r={2.5} />)}
      <circle className="ichart__halo" cx={xAt(last.date)} cy={yAt(last.value, axis)} r={10} />
      <circle className="ichart__dot" cx={xAt(last.date)} cy={yAt(last.value, axis)} r={4.5} />
      <text className="ichart__value" x={xAt(last.date) - 8} y={yAt(last.value, axis) - 10}
        textAnchor="end">{last.value.toFixed(dp)}</text>
    </svg>
  )
}

/** Several dated series on one scale (the check-in scores over time): each series a line
 *  through its readings in its own style, a gap where a series has no reading. */
export function DatedLines({ series, start, end, axis, label }: {
  series: readonly { name: string; points: readonly { date: string; value: number | null }[] }[]
  start: string; end: string
  axis: { lo: number; hi: number; y_labels: readonly string[]; x_labels: readonly string[] }; label: string
}) {
  const lo = dayNumber(start)
  const span = Math.max(1, dayNumber(end) - lo)
  const xAt = (iso: string) => LEFT + (span <= 0 ? PW / 2 : ((dayNumber(iso) - lo) / span) * PW)
  return (
    <svg className="ichart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <Frame yLabels={axis.y_labels} xLabels={axis.x_labels} />
      {series.map((s, k) => {
        const shown = s.points.filter((p): p is Dated => p.value != null)
        return (
          <g key={s.name} className={`ichart__series ichart__series--${k}`}>
            {shown.length > 1 && (
              <polyline className="ichart__line" points={shown.map((p) => `${xAt(p.date).toFixed(1)},${yAt(p.value, axis).toFixed(1)}`).join(' ')} />
            )}
            {shown.map((p, i) => <circle key={i} className="ichart__dot" cx={xAt(p.date)} cy={yAt(p.value, axis)} r={2.5} />)}
          </g>
        )
      })}
    </svg>
  )
}
