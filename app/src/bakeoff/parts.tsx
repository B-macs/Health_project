// Drawing parts. Each draws in token colours only (a kind or tone class sets --tone,
// and the stylesheet sets every size). Geometry is in each SVG's own small box.
import { useId, type ReactNode } from 'react'
import type { Tone } from '../mock/generate'
import { useGrow } from './hooks'

export type Kind = 'readiness' | 'sleep' | 'strain' | 'rest'

const R = 45
const C = 2 * Math.PI * R

/** The two gradient stops of a ring, as CSS colours from the tokens. */
function stops(kind: Kind): [string, string] {
  if (kind === 'readiness') return ['var(--readiness)', 'var(--readiness-to)']
  if (kind === 'sleep' || kind === 'rest') return ['var(--sleep)', 'var(--sleep)']
  return ['var(--strain)', 'var(--strain)']
}

/** A glowing score ring, as on Oura's Today: the value sweeps clockwise from the top. */
export function Ring(props: {
  kind: Kind
  fraction: number
  reduced: boolean
  label: string
  className: string
  head?: boolean
  children: ReactNode
}) {
  const id = useId()
  const shown = useGrow(Math.max(0, Math.min(1, props.fraction)), props.reduced)
  const [from, to] = stops(props.kind)
  const angle = (shown * 360 - 90) * (Math.PI / 180)
  return (
    <div className={`ring ${props.className} kind-${props.kind}`} role="img" aria-label={props.label}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" style={{ stopColor: from }} />
            <stop offset="1" style={{ stopColor: to }} />
          </linearGradient>
        </defs>
        <circle className="ring__track" cx="50" cy="50" r={R} />
        <circle className="ring__value" cx="50" cy="50" r={R} stroke={`url(#${id})`}
          strokeDasharray={`${C * shown} ${C}`} transform="rotate(-90 50 50)" />
        {props.head && shown > 0.01 && (
          <circle className="ring__head" cx={50 + R * Math.cos(angle)} cy={50 + R * Math.sin(angle)} r="2.6" />
        )}
      </svg>
      <div className="ring__center">{props.children}</div>
    </div>
  )
}

/** A smooth line through the points (Catmull-Rom as cubic Béziers). */
function smooth(points: readonly (readonly [number, number])[]): string {
  let d = `M${points[0][0]},${points[0][1]}`
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[i + 2] ?? p2
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]
    d += ` C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${p2[0]},${p2[1]}`
  }
  return d
}

/** A soft area chart: a smooth line, a fading fill under it, a glowing last point. */
export function AreaChart(props: { values: readonly number[]; kind: Kind; label: string; className?: string }) {
  const id = useId()
  const lo = Math.min(...props.values)
  const hi = Math.max(...props.values)
  const span = hi - lo || 1
  const n = props.values.length
  const points = props.values.map((v, i) => [(i / (n - 1)) * 96 + 2, 30 - ((v - lo) / span) * 24] as const)
  const line = smooth(points)
  const last = points[n - 1]
  const [from] = stops(props.kind)
  return (
    <svg className={`area ${props.className ?? ''} kind-${props.kind}`} viewBox="0 0 100 34" role="img" aria-label={props.label}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" className="area__fade-top" style={{ stopColor: from }} />
          <stop offset="1" className="area__fade-bottom" style={{ stopColor: from }} />
        </linearGradient>
      </defs>
      <path className="area__fill" d={`${line} L${last[0]},34 L${points[0][0]},34 Z`} fill={`url(#${id})`} />
      <path className="area__line" d={line} />
      <circle className="area__dot" cx={last[0]} cy={last[1]} r="1.9" />
    </svg>
  )
}

/** One rounded bar a day for the week's work; a rest day is a small dot. */
export function DayBars(props: { values: readonly number[]; days: readonly string[]; label: string }) {
  const hi = Math.max(...props.values) || 1
  return (
    <div className="daybars" role="img" aria-label={props.label}>
      {props.values.map((v, i) => (
        <div key={i} className="daybars__col">
          <div className="daybars__slot">
            {v ? (
              <span className="daybars__bar" style={{ height: `${Math.max(8, (v / hi) * 100)}%` }} />
            ) : (
              <span className="daybars__rest" />
            )}
          </div>
          <span className="daybars__day">{props.days[i]}</span>
        </div>
      ))}
    </div>
  )
}

/** An Oura-style contributor: name and value on one line, a thin bar, a note. */
export function Contributor(props: { name: string; value: string; fraction: number | null; note: string; tone?: Tone; reduced: boolean }) {
  const shown = useGrow(props.fraction ?? 0, props.reduced)
  return (
    <div className="contrib">
      <div className="contrib__top">
        <span className="contrib__name">{props.name}</span>
        <span className="num contrib__value">{props.value}</span>
      </div>
      <div className="contrib__track">
        {props.fraction != null && (
          <span className={`contrib__fill tone-${props.tone ?? 'good'}`} style={{ width: `${shown * 100}%` }} />
        )}
      </div>
      {props.note && <div className="contrib__note">{props.note}</div>}
    </div>
  )
}

const LONG = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' })
export const longDate = (iso: string) => LONG.format(new Date(`${iso}T00:00:00Z`))

/** The greeting for the phone's own clock. */
export function greetingKey(hour: number): 'morning' | 'afternoon' | 'evening' {
  if (hour < 12) return 'morning'
  if (hour < 18) return 'afternoon'
  return 'evening'
}
