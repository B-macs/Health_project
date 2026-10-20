// The Training tab (rebuild Phase 6): today's session before Start (the overview the engine
// sends, inventory T37-T45), the guided flow while a session runs, and the save at its
// end. The session the phone keeps (the database's `session` row) decides which: it
// survives a reload, an app kill and an app update, so the app opens on it again.
//
// Start downloads the whole session (GET /api/training/session) and mints the ids once.
// The session's answer is read cache-first when the tab opens, so a session can start at
// the gym with no signal when the phone has read it earlier that day.
import { useLiveQuery } from 'dexie-react-hooks'
import { useCallback, useState } from 'react'
import type { components } from '../generated/api'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { endSession, startSession } from '../lib/session'
import { newExerciseIds, newSessionId, startSessionState, type Plan, type TrainingState } from '../lib/training'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { SessionFlow } from './Session'
import { SessionSave } from './SessionSave'

type DayPlan = components['schemas']['TrainingDayOut']

function Overview({ onStart, starting }: { onStart: (plan: Plan) => void; starting: boolean }) {
  const { store, ctx } = useApp()
  const day = useCached<DayPlan>(store, '/api/training/day', null, ctx)
  const session = useCached<Plan>(store, '/api/training/session', null, ctx)
  const o = day.data?.overview
  const plan = session.data && session.data.date === localDay() ? session.data : null
  // Why there is no session today, from the day's own answer.
  const reason = day.data?.route === 'rest' ? 'rest_day'
    : day.data?.route === 'no_phase' ? 'no_phase'
      : o?.screen === 'logged' ? 'already_logged'
        : o?.screen === 'not_started' ? 'not_started'
          : o?.screen === 'complete' ? 'complete' : null
  return (
    <div className="screen train">
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.session.title}</h1>
        {o && <div className="caption">{S.session.dayOf(o.day_num ?? 0, o.plan_days)}</div>}
      </header>
      <Freshness view={session} />
      {o?.banner?.text && <p className={o.banner.kind === 'error' ? 'alert' : 'caption'}>{o.banner.text}</p>}
      {o?.banner?.acwr_advisory && <p className="caption">{o.banner.acwr_advisory}</p>}
      {plan ? (
        <section className="card plan">
          <div className="plan__head">
            <div>
              <div className="eyebrow">{plan.phase}</div>
              <h2 className="plan__title">{o?.headline ?? plan.objective}</h2>
            </div>
            <div className="plan__meta">{S.session.minutes(plan.model_minutes)}</div>
          </div>
          {o?.subtitle && <p className="caption">{o.subtitle}</p>}
          {plan.rpe_target != null && <p className="caption">{S.session.rpeTarget(plan.rpe_target)}</p>}
          {plan.adaptation.badge_shown && <span className="badge">{S.session.adapted}</span>}
          {plan.adaptation.volume_note && <p className="caption">{plan.adaptation.volume_note}</p>}
          {o?.first_side_note && <p className="caption">{o.first_side_note}</p>}
          <ol className="timeline">
            {plan.exercises.map((ex) => (
              <li key={ex.index} className={`timeline__item${ex.warmup ? ' timeline__item--warmup' : ''}`}>
                <span className="timeline__dot" aria-hidden="true" />
                <span className="timeline__name">{ex.name}</span>
                <span className="timeline__dose">{ex.prescription}</span>
              </li>
            ))}
          </ol>
          {o?.home && o.home.length > 0 && (
            <ul className="list">
              {o.home.map((h) => <li key={h.name} className="caption">{`${h.name} · ${h.prescription}`}</li>)}
            </ul>
          )}
          {plan.garmin_configured && <p className="caption">{S.session.garminFirst}</p>}
          <button className="btn btn--primary btn--wide btn--gym" disabled={starting} onClick={() => onStart(plan)}>
            {starting ? S.session.starting : S.session.start}
          </button>
        </section>
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
  const state = (row?.data as TrainingState | undefined) ?? null
  const update = useCallback((f: (s: TrainingState) => TrainingState) => {
    void store.transaction('rw', store.session, async () => {
      const current = await store.session.get('current')
      if (!current) return
      await store.session.put({ ...current, data: f(current.data as TrainingState) })
    })
  }, [store])
  const start = async (plan: Plan) => {
    setStarting(true)
    try {
      const data = startSessionState(plan, newSessionId(plan.date), newExerciseIds(plan.exercises.length))
      await startSession(store, data)
    } finally {
      setStarting(false)
    }
  }
  const leave = useCallback(() => void endSession(store).then(() => go('/')), [store, go])
  if (row === undefined) return null
  if (!state || state.version !== 1) return <Overview onStart={(p) => void start(p)} starting={starting} />
  if (state.saving) return <SessionSave s={state} update={update} onDone={leave} />
  return <SessionFlow s={state} update={update} onExit={leave} />
}

