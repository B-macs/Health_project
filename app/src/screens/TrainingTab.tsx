// The Training tab (rebuild Phase 6): today's session before Start (the overview the engine
// sends, inventory T37-T47), the guided flow while it runs, and the save at its end. The
// session the phone keeps (the database's `session` row) decides which: it survives a
// reload, an app kill and an app update, so the app opens on it again.
//
// Start downloads the whole session (GET /api/training/session) and mints the ids once.
// The day's and the session's answers are read cache-first when the tab opens, so a
// session can start at the gym with no signal when the phone has read them earlier that
// day. Every number and word of the overview is the engine's; the phone only lays it out.
import { useLiveQuery } from 'dexie-react-hooks'
import { useCallback, useState } from 'react'
import type { components } from '../generated/api'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { endSession, startSession } from '../lib/session'
import { loadState, newExerciseIds, newSessionId, startSessionState, type Plan, type TrainingState } from '../lib/training'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { Sheet } from '../ui/Sheet'
import { SessionFlow } from './Session'
import { SessionSave } from './SessionSave'

type Schemas = components['schemas']
type DayPlan = Schemas['TrainingDayOut']
type Line = Schemas['ExerciseLine']

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

function Timeline({ title, items, warmups }: { title: string; items: Line[]; warmups: Set<string> }) {
  return (
    <section className="card group" aria-label={title}>
      <h3 className="eyebrow">{title}</h3>
      <ol className="timeline">
        {items.map((ex, i) => (
          <li key={`${ex.name}-${i}`} className={`timeline__item${warmups.has(ex.name) ? ' timeline__item--warmup' : ''}`}>
            <span className="timeline__dot" aria-hidden="true" />
            <span className="timeline__name">{ex.name}</span>
            <span className="timeline__dose">{ex.prescription}</span>
          </li>
        ))}
      </ol>
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

function Overview({ onStart, starting }: { onStart: (plan: Plan, garmin: boolean) => void; starting: boolean }) {
  const { store, ctx } = useApp()
  const day = useCached<DayPlan>(store, '/api/training/day', null, ctx)
  const session = useCached<Plan>(store, '/api/training/session', null, ctx)
  const [garmin, setGarmin] = useState(false)
  const [adapting, setAdapting] = useState(false)
  const today = localDay()
  const o = day.data?.overview
  const plan = session.data && session.data.date === today ? session.data : null
  const reason = noSessionReason(day.data)
  const warmups = new Set((plan?.exercises ?? []).filter((e) => e.warmup).map((e) => e.name))
  // The day's own lists (today's dosed values, fault F20); the session's when only it is saved.
  const main: Line[] = o && (o.main.length || o.release.length) ? o.main : (plan?.exercises ?? [])
  return (
    <div className="screen train">
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.session.title}</h1>
        <div className="caption">{longDate(day.data?.date ?? today)}</div>
      </header>
      <Freshness view={session} />
      {day.data?.phase && <StatusStrip phase={day.data.phase} today={today} />}
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
          {o?.home && o.home.length > 0 && (
            <section className="card group" aria-label={S.session.atHome}>
              <h3 className="eyebrow">{S.session.atHome}</h3>
              {o.home.map((h) => (
                <details key={h.name} className="guide">
                  <summary className="tapline">{`${h.name} · ${h.prescription}`}</summary>
                  {h.mechanics && <p className="caption">{h.mechanics}</p>}
                </details>
              ))}
            </section>
          )}
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
          <div className="pair">
            <button className="btn btn--glass btn--gym" onClick={() => setAdapting(true)}>{S.session.adapt}</button>
            <button className="btn btn--primary btn--gym" disabled={starting} onClick={() => onStart(plan, garmin)}>
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

export function TrainingTab() {
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
  if (!state) return <Overview onStart={(p, garmin) => void start(p, garmin)} starting={starting} />
  if (state.saving) return <SessionSave s={state} update={update} onDone={leave} />
  return <SessionFlow s={state} update={update} onExit={leave} />
}
