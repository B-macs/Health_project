// The Training tab (rebuild Phases 6 and 7). The session the phone keeps (the database's
// `session` row) decides what shows: while one exists, the guided flow or its save (a plan
// session or the accessory session, the same flow); else the "+" menu's screen the address
// names (yoga, outdoor, the accessory session before Start); else the week page.
//
// The week page (screens/Week.tsx): the banner and the week's questions, the strip, and the
// day picked in it. Today's day is the session overview before Start (inventory T37-T47):
// Start downloads the whole session (GET /api/training/session) and mints the ids once. The
// day's and the session's answers are read cache-first, so a session can start at the gym
// with no signal when the phone has read them earlier that day. Every number and word is
// the engine's; the phone only lays it out.
import { useLiveQuery } from 'dexie-react-hooks'
import { useCallback, useState } from 'react'
import type { OutboxRow } from '../db/schema'
import type { components } from '../generated/api'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import {
  answerCarry, answerShift, clearRefused, gate1Flare, gate1Reason, redoWeek, swapWithToday, useConfirmed,
  useScheduleAnswers,
} from '../lib/schedule'
import { endSession, startSession } from '../lib/session'
import { loadState, newExerciseIds, newSessionId, startSessionState, type Plan, type TrainingState } from '../lib/training'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { IconPlus } from '../ui/icons'
import { Sheet } from '../ui/Sheet'
import { HomeItems, Timeline } from '../ui/timeline'
import { AccessoryOverview, ExtrasMenu, Outdoor, YogaDetail, YogaList } from './Extras'
import { SessionFlow } from './Session'
import { SessionSave } from './SessionSave'
import {
  DayView, Gate1, GapScreen, MovePrompts, RedoOffer, Refusals, RestView, Retest, RollupBanner, ScheduleNote, WeekStrip,
  waiting, type Answer, type DayAnswer, type WeekAnswer,
} from './Week'

type Schemas = components['schemas']
type DayPlan = Schemas['TrainingDayOut']

/** A date as the screens write it: "Tuesday 20 October". */
export function longDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
}

/** The load decision's banner (T37), in the page's own shades: strongest for a rest or a
 *  reduced day, a softer note for an injury cap or a missing reading. */
export function Banner({ kind, text }: { kind: string; text: string }) {
  if (!text) return null
  if (kind === 'error' || kind === 'warning') return <p className="alert" data-kind={kind}>{text}</p>
  if (kind === 'info') return <p className="note" data-kind={kind}>{text}</p>
  return <p className="caption" data-kind={kind || 'neutral'}>{text}</p>
}

/** Why there is no session today, from the day's own answer (the block complete, T50,
 *  among them): a key of S.session.noSession, or null. */
export function noSessionReason(day: DayPlan | undefined): string | null {
  const o = day?.overview
  return day?.route === 'rest' ? 'rest_day'
    : day?.route === 'no_phase' ? 'no_phase'
      : o?.screen === 'logged' ? 'already_logged'
        : o?.screen === 'not_started' ? 'not_started'
          : o?.screen === 'complete' ? 'complete' : null
}

function Progress({ value, label }: { value: number; label: string }) {
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100}
      aria-valuenow={Math.round(value * 100)}>
      <span className="progress__fill" style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  )
}

/** Plan start, today and the day of the block (T47). */
function StatusStrip({ phase, today }: { phase: Schemas['PhaseOut']; today: string }) {
  if (phase.day_num == null) return null
  return (
    <section className="figures" aria-label={S.session.blockProgress}>
      <div className="figure"><span className="eyebrow">{S.session.planStart}</span><span className="num">{phase.start_date}</span></div>
      <div className="figure"><span className="eyebrow">{S.session.todayLabel}</span><span className="num">{today}</span></div>
      <div className="figure"><span className="eyebrow">{S.session.dayLabel}</span><span className="num">{S.session.dayShort(phase.day_num, phase.plan_days)}</span></div>
    </section>
  )
}

/** The workout card (T39): the block, the day, the minutes, the effort cap, the focus,
 *  loaded or not, and how far into the block. */
function WorkoutCard({ o, plan }: { o: Schemas['TodayOverview']; plan: Plan }) {
  const card = o.card
  const day = o.day_num ?? plan.day_num ?? 0
  return (
    <section className="card plan" data-testid="workout-card">
      <div className="plan__head">
        <div>
          <div className="eyebrow">{o.phase_name || plan.phase}</div>
          <h2 className="plan__title">{S.session.dayBig(day)}</h2>
        </div>
        <div className="plan__meta">{S.session.exerciseCount(card?.exercise_count ?? plan.exercises.length)}</div>
      </div>
      <ul className="list">
        <li className="caption">{S.session.minutes(card?.minutes ?? plan.model_minutes)}</li>
        {(card?.rpe_target ?? plan.rpe_target) != null && <li className="caption">{S.session.effortCap(card?.rpe_target ?? plan.rpe_target!)}</li>}
        <li className="caption">{card?.focus.length ? card.focus.join(', ') : S.session.fullBody}</li>
        {card && <li className="caption">{card.loaded ? S.session.loaded : S.session.bodyweight}</li>}
      </ul>
      {o.plan_days > 0 && (
        <div className="group">
          <span className="caption">{S.session.sessionsOf(day, o.plan_days)}</span>
          <Progress value={day / o.plan_days} label={S.session.sessionsOf(day, o.plan_days)} />
        </div>
      )}
    </section>
  )
}

/** The adapt dialog (T44): what the day's load decision did to the volume, and how it
 *  works. The numbers are the engine's. */
function AdaptSheet({ a, onClose }: { a: Plan['adaptation']; onClose: () => void }) {
  const unchanged = a.volume_factor === 1 && !a.reduced
  return (
    <Sheet title={S.session.adapt} closeLabel={S.session.close} onClose={onClose}>
      <div className="group">
        {unchanged ? <p>{S.session.adaptNone}</p> : (
          <>
            <p>{a.volume_factor === 1 ? S.session.adaptHeld
              : S.session.adaptTo(Math.round(a.volume_factor * 100), a.volume_factor > 1)}</p>
            {a.volume_note && <p className="caption">{a.volume_note}</p>}
          </>
        )}
        {a.reduced && (
          <p className={a.banner_kind === 'info' ? 'note' : 'alert'}>
            {a.banner_kind === 'info' ? S.session.adaptHeldDay : S.session.adaptReducedDay}
          </p>
        )}
        <p className="caption">{S.session.adaptHow}</p>
        <button className="btn btn--glass btn--wide" onClick={onClose}>{S.session.close}</button>
      </div>
    </Sheet>
  )
}

/** Today's view: the session overview before Start, or why there is none (a rest day with
 *  its yoga flow, the gap between blocks). Start waits while an answer that can change
 *  today's session waits to send (`waitingMove`), and until the session is read again after
 *  the last such answer (`movedAt`). */
function Overview({ day, onStart, starting, waitingMove, movedAt }: {
  day: View<DayPlan>; onStart: (plan: Plan, garmin: boolean) => void; starting: boolean
  waitingMove: boolean; movedAt: string | undefined
}) {
  const { store, ctx } = useApp()
  const session = useCached<Plan>(store, '/api/training/session', null, ctx)
  const held = waitingMove || (movedAt !== undefined && (session.state !== 'fresh' || (session.fetchedAt ?? '') < movedAt))
  const [garmin, setGarmin] = useState(false)
  const [adapting, setAdapting] = useState(false)
  const today = localDay()
  const d = day.data && day.data.date === today ? day.data : undefined
  const o = d?.overview
  const plan = session.data && session.data.date === today ? session.data : null
  const reason = noSessionReason(d)
  const warmups = new Set((plan?.exercises ?? []).filter((e) => e.warmup).map((e) => e.name))
  // The day's own lists (today's dosed values, fault F20); the session's when only it is saved.
  const main = o && (o.main.length || o.release.length) ? o.main : (plan?.exercises ?? [])
  if (d?.route === 'rest') return <><ScheduleNote note={d.note} /><RestView rest={d.rest} /></>
  if (d?.route === 'no_phase') return <GapScreen gap={d.gap} />
  if (d?.route === 'phases_unreadable') return <p className="alert">{S.week.phasesUnreadable}</p>
  return (
    <div className="group" data-testid="today-overview">
      {/* The week's read says how fresh the page is; the session's only when it failed. */}
      {session.state !== 'fresh' && session.state !== 'loading' && <Freshness view={session} />}
      <ScheduleNote note={d?.note} />
      {d?.phase && <StatusStrip phase={d.phase} today={today} />}
      {o?.banner && <Banner kind={o.banner.kind} text={o.banner.text} />}
      {o?.banner?.acwr_advisory && <p className="caption">{o.banner.acwr_advisory}</p>}
      {plan ? (
        <>
          {(o?.headline || o?.subtitle) && (
            <section className="group">
              {o?.headline && <h2 className="plan__title">{o.headline}</h2>}
              {o?.subtitle && <p className="caption">{o.subtitle}</p>}
            </section>
          )}
          {o ? <WorkoutCard o={o} plan={plan} /> : (
            <section className="card plan">
              <div className="eyebrow">{plan.phase}</div>
              <h2 className="plan__title">{plan.objective}</h2>
              <div className="plan__meta">{S.session.minutes(plan.model_minutes)}</div>
            </section>
          )}
          {plan.adaptation.badge_shown && <span className="badge" data-kind={plan.adaptation.banner_kind}>{S.session.adapted}</span>}
          {plan.adaptation.volume_note && <p className="caption">{plan.adaptation.volume_note}</p>}
          {o && o.release.length > 0 && <Timeline title={S.session.release} items={o.release} warmups={warmups} />}
          <Timeline title={S.session.workout} items={main} warmups={warmups} />
          {o?.home && <HomeItems items={o.home} />}
          {plan.garmin_configured && (
            <section className="card group" aria-label={S.session.beforeStart}>
              <h3 className="eyebrow">{S.session.beforeStart}</h3>
              <p>{S.session.garminStart}</p>
              <label className="field-row">
                <span>{S.session.garminDeclare}</span>
                <input type="checkbox" role="switch" className="switch" checked={garmin}
                  onChange={(e) => setGarmin(e.target.checked)} />
              </label>
              <p className="caption">{S.session.garminDeclareHelp}</p>
            </section>
          )}
          {o?.first_side_note && <p className="caption">{o.first_side_note}</p>}
          {held && <p className="note" data-testid="start-held">{S.week.startHeld}</p>}
          <div className="pair">
            <button className="btn btn--glass btn--gym" onClick={() => setAdapting(true)}>{S.session.adapt}</button>
            <button className="btn btn--primary btn--gym" disabled={starting || held} onClick={() => onStart(plan, garmin)}>
              {starting ? S.session.starting : S.session.start}
            </button>
          </div>
          {adapting && <AdaptSheet a={plan.adaptation} onClose={() => setAdapting(false)} />}
        </>
      ) : (
        <p className="caption" data-testid="no-session">
          {reason
            ? S.session.noSession[reason]
            : session.state === 'loading' ? S.fresh.loading
              : session.state === 'offline' || session.state === 'engine_unavailable' ? S.session.needsEngine
                : S.session.noSessionOther}
        </p>
      )}
    </div>
  )
}

/** The kinds of answer that can change today's session. */
const MOVES_TODAY = ['swap', 'carry', 'shift']

/** The page the owner's answers re-read: it is mounted again each time the engine confirms
 *  one (`version`), so every read under it asks again. */
function WeekBody({ weekStart, setWeekStart, selected, setSelected, answered, answer, rows, onStart, starting, onClear }: {
  weekStart: string | null; setWeekStart: (week: string | null) => void
  selected: string; setSelected: (day: string) => void
  answered: Record<string, string>; answer: Answer; rows: OutboxRow[]
  onStart: (plan: Plan, garmin: boolean) => void; starting: boolean; onClear: (row: OutboxRow) => void
}) {
  const { store, ctx } = useApp()
  const today = localDay()
  const week = useCached<WeekAnswer>(store, weekStart ? `/api/training/week?week_start=${weekStart}` : '/api/training/week', null, ctx)
  const day = useCached<DayAnswer>(store, selected === today ? '/api/training/day' : `/api/training/day?date=${selected}`, null, ctx)
  const w = week.data
  // A question answered on this page stays closed until a read newer than the answer.
  const isOpen = (key: string) => {
    const at = answered[key]
    return !at || (week.state === 'fresh' && week.fetchedAt !== null && week.fetchedAt > at)
  }
  const movedAt = Object.entries(answered).filter(([k]) => MOVES_TODAY.includes(k.split(':')[0]))
    .map(([, at]) => at).sort().pop()
  const waitingMove = MOVES_TODAY.some((k) => waiting(rows, k))
  const swap = (date: string) => {
    setSelected(today)
    answer(`swap:${date}`, () => swapWithToday(store, date))
  }
  // The week strip leads the page, with the day it picks right under it (the owner,
  // 2026-10-21: "Move the week tab to the top of the page in training"). The questions about
  // this week stay above the day, since Start waits for them; the streak, gate 1 and the
  // retest notice follow the day.
  const ok = w !== undefined && w.phases_readable
  return (
    <>
      <Freshness view={week} />
      <Refusals rows={rows} onClear={onClear} />
      {w && !w.phases_readable && <p className="alert" data-testid="phases-unreadable">{S.week.phasesUnreadable}</p>}
      {ok && w.strip.length > 0 && (
        <WeekStrip week={w} selected={selected} onPick={setSelected}
          onWeek={(step) => setWeekStart(shiftDay(w.week_start ?? today, step))}
          onToday={() => { setWeekStart(null); setSelected(today) }} />
      )}
      {ok && (
        <>
          <RedoOffer redo={w.redo} rows={rows} open={isOpen('redo')} answer={answer} redoWeek={() => redoWeek(store)} />
          <MovePrompts week={w} rows={rows} isOpen={isOpen} answer={answer}
            carry={(accept) => answerCarry(store, accept)} shift={(accept) => answerShift(store, accept)} />
        </>
      )}
      {selected === today
        ? <Overview day={day} onStart={onStart} starting={starting} waitingMove={waitingMove} movedAt={movedAt} />
        : day.data && day.data.date === selected
          ? <DayView day={day.data} rows={rows} onSwap={swap} />
          : <Freshness view={day} />}
      {ok && (
        <>
          {w.banner && <RollupBanner banner={w.banner} />}
          {w.repeat_notice && <p className="note" data-testid="repeat-notice">{w.repeat_notice}</p>}
          {w.gate1 && (
            <Gate1 card={w.gate1} rows={rows} isOpen={isOpen} answer={answer}
              reason={(monday, key) => gate1Reason(store, monday, key)} flare={() => gate1Flare(store)} />
          )}
          {w.retest && <Retest notice={w.retest} />}
        </>
      )}
    </>
  )
}

/** An ISO day moved by whole days. */
export function shiftDay(iso: string, days: number): string {
  return new Date(Date.parse(`${iso}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10)
}

function WeekPage({ onStart, starting }: { onStart: (plan: Plan, garmin: boolean) => void; starting: boolean }) {
  const { store } = useApp()
  const rows = useScheduleAnswers(store)
  const confirmed = useConfirmed(rows)
  const [cleared, setCleared] = useState(0)
  const [weekStart, setWeekStart] = useState<string | null>(null)
  const [selected, setSelected] = useState(localDay())
  const [answered, setAnswered] = useState<Record<string, string>>({})
  const [menu, setMenu] = useState(false)
  const answer: Answer = (key, send) => {
    setAnswered((a) => ({ ...a, [key]: new Date().toISOString() }))
    void send()
  }
  const clear = (row: OutboxRow) => void clearRefused(store, row).then(() => setCleared((c) => c + 1))
  return (
    <div className="screen train" data-testid="week-page">
      <div className="sky" aria-hidden="true" />
      <header className="head head--row">
        <div>
          <h1 className="head__title">{S.session.title}</h1>
          <div className="caption">{longDate(localDay())}</div>
        </div>
        <button className="iconbtn" aria-label={S.week.plus} data-testid="plus" onClick={() => setMenu(true)}>
          <IconPlus />
        </button>
      </header>
      <WeekBody key={confirmed + cleared} weekStart={weekStart} setWeekStart={setWeekStart}
        selected={selected} setSelected={setSelected} answered={answered} answer={answer} rows={rows}
        onStart={onStart} starting={starting} onClear={clear} />
      {menu && <ExtrasMenu onClose={() => setMenu(false)} />}
    </div>
  )
}

/** The "+" menu's screens, by address. */
export type Extra = 'yoga' | 'outdoor' | 'accessory'

export function TrainingTab({ extra, slug }: { extra?: Extra; slug?: string }) {
  const { store, go } = useApp()
  // undefined while the database is read; null when no session is kept.
  const row = useLiveQuery(async () => (await store.session.get('current')) ?? null, [store])
  const [starting, setStarting] = useState(false)
  const state = row ? loadState(row.data) : null
  const update = useCallback((f: (s: TrainingState) => TrainingState) => {
    void store.transaction('rw', store.session, async () => {
      const current = await store.session.get('current')
      const kept = current ? loadState(current.data) : null
      if (!current || !kept) return
      await store.session.put({ ...current, data: f(kept) })
    })
  }, [store])
  const start = async (plan: Plan, garmin: boolean) => {
    setStarting(true)
    try {
      const data = startSessionState(plan, newSessionId(plan.date), newExerciseIds(plan.exercises.length), garmin)
      await startSession(store, data)
    } finally {
      setStarting(false)
    }
  }
  const leave = useCallback(() => void endSession(store).then(() => go('/')), [store, go])
  if (row === undefined) return null
  if (state?.saving) return <SessionSave s={state} update={update} onDone={leave} />
  if (state) return <SessionFlow s={state} update={update} onExit={leave} />
  if (extra === 'yoga') return slug ? <YogaDetail slug={slug} /> : <YogaList />
  if (extra === 'outdoor') return <Outdoor />
  if (extra === 'accessory') return <AccessoryOverview />
  return <WeekPage onStart={(p, garmin) => void start(p, garmin)} starting={starting} />
}
