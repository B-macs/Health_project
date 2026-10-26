// The week page on the Training tab (rebuild Phase 7, inventory T8-T36): the rollup banner
// and last week's line, the Monday notices and the redo, the questions that move a session,
// gate 1, the flexibility retest, the strip of the week with its arrows, and the view of the
// day picked in it. Every verdict, count, rule and blocker is the engine's (GET
// /api/training/week and /api/training/day); the phone lays them out and sends the owner's
// answers through the outbox (lib/schedule.ts).
//
// NOTHING MOVES UNTIL THE OWNER ANSWERS (his rule, 2026-08-07): reading the week writes
// nothing (the engine's test pins it), and each question here is a button the owner presses.
// While an answer waits to send, its question says so instead of asking again; until a read
// newer than the answer comes back, the question stays closed (`isOpen`), so a question
// already answered never shows twice.
import { useState } from 'react'
import type { OutboxRow } from '../db/schema'
import type { components } from '../generated/api'
import { useApp } from '../lib/appState'
import { refusalText } from '../lib/schedule'
import { S } from '../strings'
import { useSwipe } from '../ui/hooks'
import { IconCheck } from '../ui/icons'
import { FlowChoice } from './Extras'
import { dayOfMonth, longDate, narrowDay, shortDate } from '../ui/parts'
import { HomeItems, Timeline } from '../ui/timeline'

type Schemas = components['schemas']
export type WeekAnswer = Schemas['TrainingWeekOut']
export type DayAnswer = Schemas['TrainingDayOut']

/** Asks a question: the answer is sent, and the question is closed under `key`. */
export type Answer = (key: string, send: () => Promise<string>) => void

const GATE1_REASON = '/api/training/gate1/reason'
const GATE1_FLARE = '/api/training/gate1/flare'

/** An answer of this kind (and this address) waits in the outbox. */
export function waiting(rows: OutboxRow[], kind: string, path?: string): boolean {
  return rows.some((r) => r.kind === kind && r.state === 'waiting' && (!path || r.path === path))
}

function Waiting() {
  return <p className="caption" role="status" data-testid="answer-waiting">{S.week.waiting}</p>
}

/** The refused answers, each with the engine's reason, until the owner clears it. */
export function Refusals({ rows, onClear }: { rows: OutboxRow[]; onClear: (row: OutboxRow) => void }) {
  return (
    <>
      {rows.filter((r) => r.state === 'failed').map((r) => (
        <section key={r.id} className="card group" data-testid="answer-refused" data-kind={r.kind}>
          <p className="alert">{refusalText(r)}</p>
          <button className="btn btn--glass" onClick={() => onClear(r)}>{S.week.clear}</button>
        </section>
      ))}
    </>
  )
}

/** The rollup banner (T8): the streak, this week's sessions against the plan with the next
 *  line to reach, the lifetime tallies; under it, last week's verdict while it shows (T9). */
export function RollupBanner({ banner }: { banner: Schemas['WeekBanner'] }) {
  const tier = S.week.tier[banner.progress] ?? S.week.tier.normal
  return (
    <>
      <section className="card rollup" data-testid="rollup" data-progress={banner.progress}>
        <div className="rollup__cell">
          <span className="eyebrow">{S.week.streak}</span>
          <span className="rollup__value">
            {banner.streak_weeks ? S.week.streakWeeks(banner.streak_weeks, banner.streak_all_ultimate) : S.week.streakNone}
          </span>
        </div>
        <div className="rollup__cell">
          <span className="eyebrow">{S.week.thisWeek(banner.completed, banner.scheduled)}</span>
          <span className="rollup__value">{tier(banner.to_go)}</span>
        </div>
        <span className="caption rollup__tallies">{S.week.tallies(banner.perfect_count, banner.ultimate_count)}</span>
      </section>
      {banner.last_week && (
        <p className="caption" data-testid="last-week" data-verdict={banner.last_week}>
          {S.week.lastWeek(S.week.verdict[banner.last_week] ?? banner.last_week)}
        </p>
      )}
    </>
  )
}

/** The Monday redo (T12): two presses, the second after the engine's own list of what moves. */
export function RedoOffer({ redo, rows, open, answer, redoWeek }: {
  redo: Schemas['RedoOffer'] | null | undefined; rows: OutboxRow[]; open: boolean
  answer: Answer; redoWeek: () => Promise<string>
}) {
  const [asking, setAsking] = useState(false)
  if (waiting(rows, 'redo')) return <Waiting />
  if (!redo?.offered || !open) return null
  if (!asking) {
    return <button className="btn btn--glass btn--wide" data-testid="redo" onClick={() => setAsking(true)}>{S.week.redo}</button>
  }
  return (
    <section className="card group" role="alertdialog" aria-label={S.week.redo} data-testid="redo-confirm">
      {redo.consequences.map((line) => <p key={line}>{line}</p>)}
      <div className="pair">
        <button className="btn btn--glass" onClick={() => setAsking(false)}>{S.week.cancel}</button>
        <button className="btn btn--primary" onClick={() => answer('redo', redoWeek)}>{S.week.redoYes}</button>
      </div>
    </section>
  )
}

/** The questions that move a session (T30-T32): the missed-session carry and the readiness
 *  shift. The engine sends a question only when its answer would move something. */
export function MovePrompts({ week, rows, isOpen, answer, carry, shift }: {
  week: WeekAnswer; rows: OutboxRow[]; isOpen: (key: string) => boolean; answer: Answer
  carry: (accept: boolean) => Promise<string>; shift: (accept: boolean) => Promise<string>
}) {
  const c = week.carry_prompt
  const sh = week.shift_prompt
  return (
    <>
      {waiting(rows, 'carry') ? <Waiting /> : c && isOpen('carry') && (
        <section className="card group" data-testid="carry" data-in-order={c.in_order}>
          <p className="alert">{c.in_order ? S.week.carryInOrder : S.week.carry}</p>
          <ul className="list">{c.lines.map((line) => <li key={line} className="caption">{line}</li>)}</ul>
          <div className="pair">
            <button className="btn btn--glass" onClick={() => answer('carry', () => carry(false))}>
              {c.in_order ? S.week.keepPlanned : S.week.carryKeep}
            </button>
            <button className="btn btn--primary" onClick={() => answer('carry', () => carry(true))}>
              {c.in_order ? S.week.carryRun : S.week.carryApply}
            </button>
          </div>
        </section>
      )}
      {waiting(rows, 'shift') ? <Waiting /> : sh && isOpen('shift') && (
        <section className="card group" data-testid="shift">
          <p className="alert">{S.week.shift(sh.reason)}</p>
          <div className="pair">
            <button className="btn btn--glass" onClick={() => answer('shift', () => shift(false))}>{S.week.keepPlanned}</button>
            <button className="btn btn--primary" onClick={() => answer('shift', () => shift(true))}>{S.week.shiftMove}</button>
          </div>
        </section>
      )}
    </>
  )
}

/** Gate 1 (T33-T35): the one-tap reason for a week with fewer core sessions than the gate
 *  asks, the card with the count and the four main lifts, and the flare-up (asked twice). */
export function Gate1({ card, rows, isOpen, answer, reason, flare }: {
  card: Schemas['Gate1Card']; rows: OutboxRow[]; isOpen: (key: string) => boolean; answer: Answer
  reason: (monday: string, key: string) => Promise<string>; flare: () => Promise<string>
}) {
  const [confirming, setConfirming] = useState(false)
  const run = Number(card.count.run ?? 0)
  const weeks = Number(card.count.required ?? 0)
  const w = card.waiting
  return (
    <>
      {w && (waiting(rows, 'gate1', GATE1_REASON) ? <Waiting /> : isOpen(`gate1:${w.monday}`) && (
        <section className="card group" data-testid="gate1-ask">
          <p className="alert">{S.week.gate1Ask(shortDate(w.monday), w.core_done, w.core_required, weeks)}</p>
          <div className="chips">
            {card.reasons.map((r) => (
              <button key={r.key} className="chip" onClick={() => answer(`gate1:${w.monday}`, () => reason(w.monday, r.key))}>
                {r.label}
              </button>
            ))}
          </div>
        </section>
      ))}
      <details className="card guide" data-testid="gate1">
        <summary className="tapline">{S.week.gate1Title(run, weeks, card.lifts_met, card.rows.length)}</summary>
        <div className="group">
          {card.how && <p className="caption">{card.how}</p>}
          <p>{S.week.gate1Weeks(run, weeks)}</p>
          <ul className="list">
            {card.rows.map((l) => (
              <li key={l.lift} className="lift" data-met={l.met}>
                <span className="lift__mark" aria-label={l.met ? S.week.gate1Met : S.week.gate1NotMet}>
                  {l.met ? <IconCheck /> : '·'}
                </span>
                <span>{S.week.gate1Lift(l.lift, S.week.kg(l.first), S.week.kg(l.latest), S.week.kg(l.target))}</span>
              </li>
            ))}
          </ul>
          {card.flare_this_week ? <p className="caption">{S.week.flareRecorded}</p>
            : waiting(rows, 'gate1', GATE1_FLARE) ? <Waiting />
              : !isOpen('flare') ? null
                : confirming ? (
                  <section className="group" role="alertdialog" aria-label={S.week.flareAsk}>
                    <p className="alert">{S.week.flareConfirm(weeks)}</p>
                    <div className="pair">
                      <button className="btn btn--glass" onClick={() => setConfirming(false)}>{S.week.cancel}</button>
                      <button className="btn btn--primary" onClick={() => answer('flare', flare)}>{S.week.flareYes}</button>
                    </div>
                  </section>
                ) : (
                  <button className="btn btn--glass btn--wide" onClick={() => setConfirming(true)}>{S.week.flareAsk}</button>
                )}
        </div>
      </details>
    </>
  )
}

/** The flexibility retest (T36): the day before (keep the legs quiet today), due, or due
 *  but not today. */
export function Retest({ notice }: { notice: Schemas['RetestNotice'] }) {
  const text = S.week.retest[notice.status]?.(notice.reason) ?? notice.reason
  return <p className={notice.kind === 'warning' ? 'alert' : 'note'} data-testid="retest" data-status={notice.status}>{text}</p>
}

/** The week strip (T16, T17): one week of the block, a marker on each day (done, today,
 *  missed, planned, rest: the engine's), the full width of the screen as on Today. A sideways
 *  swipe changes the week, inside the block's weeks; there are no arrows (the owner,
 *  2026-10-20). "Today" when another week shows. Under it, that week's stored verdict (T10). */
export function WeekStrip({ week, selected, onPick, onWeek, onToday }: {
  week: WeekAnswer; selected: string; onPick: (day: string) => void
  onWeek: (step: number) => void; onToday: () => void
}) {
  const swipe = useSwipe(week.can_go_back ? () => onWeek(-7) : null, week.can_go_forward ? () => onWeek(7) : null)
  return (
    <section className="group" aria-label={S.week.strip}>
      {!week.is_current_week && (
        <button className="btn btn--glass pill" data-testid="week-today" onClick={onToday}>{S.week.today}</button>
      )}
      <nav className="weekstrip" aria-label={S.week.strip} data-week={week.week_start ?? ''} {...swipe}>
        {week.strip.map((d) => {
          const on = d.date === selected
          return (
            <button key={d.date} className={`weekstrip__day${on ? ' weekstrip__day--on' : ''}`}
              aria-current={on ? 'date' : undefined} data-date={d.date} data-marker={d.marker}
              aria-label={S.week.dayLabel(longDate(d.date), S.week.marker[d.marker] ?? d.marker)}
              onClick={() => onPick(d.date)}>
              <span className="weekstrip__letter">{narrowDay(d.date)}</span>
              <span className={`mark mark--${d.marker}`} aria-hidden="true">{d.marker === 'done' && <IconCheck />}</span>
              <span className="num weekstrip__date">{dayOfMonth(d.date)}</span>
            </button>
          )
        })}
      </nav>
      {/* The same two moves for a screen reader, which cannot swipe; nothing shows on screen. */}
      <div className="sr-only">
        <button disabled={!week.can_go_back} onClick={() => onWeek(-7)}>{S.week.previousWeek}</button>
        <button disabled={!week.can_go_forward} onClick={() => onWeek(7)}>{S.week.nextWeek}</button>
      </div>
      {week.viewed_week_status && week.week_start && (
        <p className="caption" data-testid="week-status">
          {S.week.weekOf(longDate(week.week_start), S.week.verdict[week.viewed_week_status] ?? week.viewed_week_status)}
        </p>
      )}
    </section>
  )
}

/** Why a day's session sits where it does (T18): "Session moved" only when it really moved. */
export function ScheduleNote({ note }: { note: Schemas['ScheduleNote'] | null | undefined }) {
  if (!note) return null
  return <p className="note" data-testid="schedule-note" data-moved={note.moved}>{note.moved ? S.week.moved(note.text) : note.text}</p>
}

/** No block covers today (T26), and a block that ran out of calendar before its last days
 *  (T27). Blocks start by themselves on their date: there is nothing to press. */
export function GapScreen({ gap }: { gap: Schemas['GapScreen'] | null | undefined }) {
  const stranded = gap?.stranded as { name?: string; last_date?: string; days?: [number, string, string][] } | null | undefined
  return (
    <section className="card group" data-testid="gap">
      <h2 className="plan__title">{S.week.gapTitle}</h2>
      <p className="caption">
        {gap?.next ? S.week.gapNext(gap.next.name, gap.next.start_date, gap.next.days_away) : S.week.gapNone}
      </p>
      {stranded?.days?.length ? (
        <p className="alert" data-testid="stranded">
          {S.week.stranded(stranded.name ?? '', stranded.days.map(([n, type, iso]) => S.week.strandedDay(n, type, iso)).join(', '),
            stranded.last_date ?? '')}
        </p>
      ) : null}
    </section>
  )
}

/** A rest day (T24, T25): an optional yoga flow, and on today how to train anyway. */
export function RestView({ rest }: { rest: Schemas['RestView'] | null | undefined }) {
  const { go } = useApp()
  const yoga = rest?.yoga_suggestion
  return (
    <section className="card group" data-testid="day-rest">
      <p>{S.week.rest}</p>
      {yoga && (
        <>
          <span className="eyebrow">{S.week.restOptional}</span>
          <FlowChoice name={yoga.name} minutes={yoga.minutes} onPick={() => go(`/training/yoga/${yoga.slug}`)} />
        </>
      )}
      {rest?.is_today && <p className="caption">{S.week.restTrainAnyway}</p>}
    </section>
  )
}

/** A past day with a logged session (T20), and today once it is logged (WP-32). */
export function LoggedView({ logged }: { logged: Schemas['LoggedSession'] | null | undefined }) {
  if (!logged) return <p className="caption" data-testid="day-logged">{S.week.loggedNoDetail}</p>
  return (
    <section className="card group" data-testid="day-logged">
      <span className="eyebrow logged"><IconCheck />{S.week.logged}</span>
      <p className="caption">{S.week.loggedLine(logged.rpe, logged.minutes, logged.au)}</p>
      <ul className="list">
        {logged.exercises.map((e, i) => (
          <li key={`${e.name}-${i}`} className="kv">
            <span>{e.name}</span>
            <span className="caption">{S.week.loggedExercise(e.movement_type, e.planned_sets)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** A missed day (T21) or a day still to come (T23): what was planned for it. */
function PlannedView({ planned, missed, date }: { planned: Schemas['PlannedDay']; missed: boolean; date: string }) {
  if (!planned.objective) return <p className="caption">{S.week.noContent(planned.day_num)}</p>
  return (
    <>
      <section className="group">
        {missed
          ? <span className="eyebrow" data-testid="not-completed">{S.week.notCompleted}</span>
          : <h2 className="plan__title">{planned.objective}</h2>}
        <p className="caption">
          {missed ? S.week.missedDay(planned.day_num, planned.plan_days, planned.objective)
            : S.week.futureDay(planned.day_num, planned.plan_days, planned.rpe_target ?? null)}
        </p>
        {!missed && <p className="caption">{S.week.scheduledFor(longDate(date))}</p>}
      </section>
      <Timeline title={S.session.workout} items={planned.exercises} />
      {!missed && <HomeItems items={planned.home} />}
    </>
  )
}

/** The swap with today (T22): blocked only by what cannot be done (today already trained,
 *  a date outside the block); the rules the automatic carry keeps show as warnings, because
 *  the press is the owner's choice. */
function SwapOffer({ swap, missed, date, rows, onSwap }: {
  swap: Schemas['SwapOffer']; missed: boolean; date: string; rows: OutboxRow[]; onSwap: (date: string) => void
}) {
  if (waiting(rows, 'swap')) return <Waiting />
  if (swap.check_failed) return <p className="caption" data-testid="swap-unchecked">{S.week.swapCheckFailed}</p>
  if (swap.blockers.length) {
    return <>{swap.blockers.map((b) => <p key={b} className="note" data-testid="swap-blocked">{S.week.swapBlocked(b)}</p>)}</>
  }
  if (!swap.available) return null
  return (
    <section className="card group" data-testid="swap">
      <p className="caption">
        {missed ? S.week.swapIntroMissed(swap.today_objective, longDate(date)) : S.week.swapIntroFuture(swap.today_objective, longDate(date))}
      </p>
      {swap.warnings.map((w) => <p key={w} className="alert">{w}</p>)}
      <button className="btn btn--primary btn--wide" onClick={() => onSwap(date)}>
        {missed ? S.week.swapMissed : S.week.swapFuture}
      </button>
    </section>
  )
}

/** Another day than today, picked in the strip (T19): its rest, done, missed or future view.
 *  Today's view is the session overview (screens/TrainingTab.tsx). */
export function DayView({ day, rows, onSwap }: { day: DayAnswer; rows: OutboxRow[]; onSwap: (date: string) => void }) {
  const head = (
    <>
      <p className="eyebrow" data-testid="day-overline">{longDate(day.date)}</p>
      <ScheduleNote note={day.note} />
    </>
  )
  switch (day.route) {
    case 'phases_unreadable':
      return <p className="alert">{S.week.phasesUnreadable}</p>
    case 'no_phase':
      return <GapScreen gap={day.gap} />
    case 'rest':
      return <>{head}<RestView rest={day.rest} /></>
    case 'past_completed':
      return <>{head}<LoggedView logged={day.logged} /></>
    case 'past_missed':
    case 'future':
      return (
        <div className="group" data-testid={`day-${day.route}`}>
          {head}
          {day.planned && <PlannedView planned={day.planned} missed={day.route === 'past_missed'} date={day.date} />}
          {day.swap && <SwapOffer swap={day.swap} missed={day.route === 'past_missed'} date={day.date} rows={rows} onSwap={onSwap} />}
        </div>
      )
    default:
      return null
  }
}
