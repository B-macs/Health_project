// Insights › Warnings (rebuild Phase 8, inventory I64): the month's calendar of the check-in
// and session notes the keyword parse flagged. A marked day is a button; its entries show
// under the calendar. The month to open, each day's marker and the entries are the engine's
// (services/processing_queue.py); the screen steps the month the engine names. It opens on
// today, with today picked (the owner, 2026-10-21: "When I go to warnings it should open on
// the current day"), and says when notes still wait for the warning check.
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

type Queue = components['schemas']['QueueOut']
type Day = components['schemas']['QueueDay']

export const QUEUE = '/api/insights/queue'

/** The calendar drawn from one read (`data` the last answer shown): the tests draw it. */
export function WarningsBody({ view, data: d, picked, onPick, onMonth }: {
  view: View<Queue>; data: Queue | undefined; picked: string | null
  onPick: (day: string) => void; onMonth: (m: { year: number; month: number }) => void
}) {
  const days = d ? d.weeks.flat() : []
  const chosen: Day | undefined = days.find((day) => day.date === picked && (day.in_month || day.entries.length > 0))
  const waiting = d ? d.pending_notes + d.pending_readiness : 0
  return (
    <div className="screen insights" data-testid="warnings">
      <div className="sky sky--quiet" aria-hidden="true" />
      <InsightsHead title={S.ins.warnings} />
      <Freshness view={view} />
      {waiting > 0 && <p className="note" data-testid="warnings-waiting">{S.warn.waiting(waiting)}</p>}
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
              return day.entries.length > 0 ? (
                <button key={day.date} className={classes} data-level={day.level ?? undefined}
                  aria-label={S.warn.dayLabel(fullDate(day.date), S.warn.level[day.level ?? 'none'] ?? '')}
                  aria-pressed={picked === day.date} onClick={() => onPick(day.date)}>{dayOfMonth(day.date)}</button>
              ) : <span key={day.date} className={classes}>{dayOfMonth(day.date)}</span>
            })}
          </div>
        </section>
      )}
      {chosen && (
        <section className="card group" data-testid="day-entries">
          <h2 className="eyebrow">{fullDate(chosen.date)}</h2>
          {chosen.entries.length === 0 && <p className="caption">{S.warn.noneOnDay}</p>}
          {chosen.entries.map((e, i) => (
            <div key={i} className="group" data-level={e.level}>
              <p><b>{S.warn.level[e.level] ?? e.level}</b> · {e.source}{e.movement ? <> · <i>{e.movement}</i></> : null}</p>
              {e.summary && <p className="caption">{e.summary}</p>}
              {e.parts && <p className="caption">{S.warn.areas(e.parts)}</p>}
            </div>
          ))}
        </section>
      )}
    </div>
  )
}

export function WarningsScreen() {
  const { store, ctx } = useApp()
  const [month, setMonth] = useState<{ year: number; month: number } | null>(null)
  const [picked, setPicked] = useState<string | null>(() => localDay())
  const path = month ? `${QUEUE}?year=${month.year}&month=${month.month}` : QUEUE
  const view = useCached<Queue>(store, path, null, ctx)
  const data = useKept(view.data)
  return <WarningsBody view={view} data={data} picked={picked} onPick={setPicked} onMonth={setMonth} />
}
