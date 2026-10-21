// Insights › Warnings: the days the app told him to lower the load, and why (the owner,
// 2026-10-21: "I thought the warning was the days that it says reduce load because of
// tiredness or other reason strain? Can we change it to this? This is more relevant").
// Each marked day is that day's own decision, the one Home and Training showed: rest
// advised, reduced load, or the load held at the last session. It opens on today, with
// today picked; any day up to today can be picked. The months, each day's level and its
// reason are the engine's (services/load_warnings.py); the screen steps the month the
// engine names. (Until that day the calendar showed the keyword parse of typed notes,
// which Settings > Data still lists.)
import { useState } from 'react'
import type { components } from '../generated/api'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { dayOfMonth, fullDate, monthName } from '../lib/dates'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { InsightsHead } from '../ui/InsightsHead'
import { useKept } from '../ui/hooks'
import { IconBack, IconForward } from '../ui/icons'

type Warnings = components['schemas']['WarningsOut']
type Day = components['schemas']['WarningDay']

export const WARNINGS = '/api/insights/warnings'

/** The address of a month's warnings. Today's month is always the address with no month
 *  in it, however it was reached, so a month read once shows again at once from what the
 *  phone kept (the owner, 2026-10-21: "when I went from October calendar to September and
 *  then back to October it wasn't automatic even though I just loaded that information";
 *  coming back, October was asked for at a second address the phone had kept nothing at). */
export function warningsPath(month: { year: number; month: number } | null, today: string): string {
  if (!month || (month.year === Number(today.slice(0, 4)) && month.month === Number(today.slice(5, 7)))) {
    return WARNINGS
  }
  return `${WARNINGS}?year=${month.year}&month=${month.month}`
}

/** The levels, strongest first: the key under the calendar lists them in this order. */
const LEVELS = ['rest', 'reduced', 'held'] as const

/** The calendar drawn from one read (`data` the last answer shown): the tests draw it. */
export function WarningsBody({ view, data: d, today, picked, onPick, onMonth }: {
  view: View<Warnings>; data: Warnings | undefined; today: string; picked: string | null
  onPick: (day: string) => void; onMonth: (m: { year: number; month: number }) => void
}) {
  const days = d ? d.weeks.flat() : []
  const chosen: Day | undefined = days.find((day) => day.date === picked && (day.in_month || day.level))
  return (
    <div className="screen insights" data-testid="warnings">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.warnings} />
      <Freshness view={view} />
      <p className="caption">{S.warn.intro}</p>
      {d && (
        <section className="card group" data-testid="calendar">
          <div className="stepper">
            <button className="iconbtn" aria-label={S.warn.previous} onClick={() => onMonth(d.previous)}><IconBack /></button>
            <span className="num" data-testid="month">{monthName(d.year, d.month)}</span>
            <button className="iconbtn" aria-label={S.warn.next} onClick={() => onMonth(d.next)}><IconForward /></button>
          </div>
          <div className="cal">
            {S.warn.weekdays.map((w) => <span key={w} className="cal__head">{w}</span>)}
            {days.map((day) => {
              const classes = ['cal__day', day.in_month ? '' : 'cal__day--out', day.is_today ? 'cal__day--today' : '',
                picked === day.date ? 'cal__day--on' : ''].filter(Boolean).join(' ')
              // Any day up to today can be picked: a clear day says so.
              return day.date <= today && (day.in_month || day.level) ? (
                <button key={day.date} className={classes} data-level={day.level ?? undefined}
                  aria-label={S.warn.dayLabel(fullDate(day.date), day.level ? S.warn.load[day.level] ?? '' : S.warn.clear)}
                  aria-pressed={picked === day.date} onClick={() => onPick(day.date)}>{dayOfMonth(day.date)}</button>
              ) : <span key={day.date} className={classes}>{dayOfMonth(day.date)}</span>
            })}
          </div>
          <ul className="areakey" aria-label={S.warn.key} data-testid="warnings-key">
            {LEVELS.map((level) => (
              <li key={level} className="areakey__item">
                <span className={`areakey__chip warnkey--${level}`} aria-hidden="true" />
                {S.warn.count(S.warn.load[level] ?? level, d.counts[level] ?? 0)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {chosen && (
        <section className="card group" data-testid="day-entries" data-level={chosen.level ?? 'none'}>
          <h2 className="eyebrow">{fullDate(chosen.date)}</h2>
          {chosen.level ? (
            <>
              <p><b>{S.warn.load[chosen.level] ?? chosen.level}</b></p>
              <p className="caption">{chosen.cause || S.warn.why[chosen.level] || ''}</p>
            </>
          ) : <p className="caption">{S.warn.noneOnDay}</p>}
        </section>
      )}
    </div>
  )
}

export function WarningsScreen() {
  const { store, ctx } = useApp()
  const today = localDay()
  const [month, setMonth] = useState<{ year: number; month: number } | null>(null)
  const [picked, setPicked] = useState<string | null>(today)
  const path = warningsPath(month, today)
  const view = useCached<Warnings>(store, path, null, ctx)
  const data = useKept(view.data)
  return <WarningsBody view={view} data={data} today={today} picked={picked} onPick={setPicked} onMonth={setMonth} />
}
