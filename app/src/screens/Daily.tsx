// The Training tab's two tiles and the daily tendon session (WP-40, 2026-10-28). The owner:
// "the first tile when selected will bring me to the normal training day and what is
// required for that day. the other tile will be the daily training day."
//
// - The tiles (/training): "Training day" opens the week page as before (/training/day);
//   "Daily tendon session" opens its overview (/training/daily).
// - The daily session: the same session every day, from the engine (GET
//   /api/training/daily), run in the same guided flow as the plan session and saved as its
//   own kind, so it never marks the training day done. Its 8-hour line is a reminder only:
//   Start is never locked ("Reminder only let me make the desicion on when to do it and
//   never locked"). Every number and word is the engine's or strings.ts's.
import { useLiveQuery } from 'dexie-react-hooks'
import { useState } from 'react'
import type { components } from '../generated/api'
import { KEYS } from '../db/schema'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { startSession } from '../lib/session'
import { newExerciseIds, newSessionId, startSessionState, type Plan } from '../lib/training'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { Timeline } from '../ui/timeline'
import { Head } from './Extras'
import { trainedToday } from './TrainingTab'

type Schemas = components['schemas']
type DayPlan = Schemas['TrainingDayOut']
type Reminder = Schemas['DailyReminder']

export const DAILY = '/api/training/daily'

/** The 8-hour line, or null (a rest day, or nothing known). */
export function reminderLine(r: Reminder | null | undefined): string | null {
  if (!r) return null
  return r.kind === 'after' && r.time ? S.daily.after(r.time) : r.kind === 'before' ? S.daily.before : null
}

/** What the "Training day" tile says about today: trained, a rest day, or the session's
 *  own headline. */
export function trainingDayLine(day: DayPlan | undefined, savedOn: unknown, today: string): string {
  if (!day || day.date !== today) return S.daily.trainingDayOpen
  if (trainedToday(day, savedOn, today)) return S.session.trainedToday
  if (day.route === 'rest') return S.session.noSession.rest_day
  return day.overview?.headline || S.daily.trainingDayOpen
}

function Tile({ title, line, note, testId, onOpen }: {
  title: string; line: string; note: string | null; testId: string; onOpen: () => void
}) {
  return (
    <button className="card tile tile--button" data-testid={testId} onClick={onOpen}>
      <span className="eyebrow">{title}</span>
      <span className="plan__title">{line}</span>
      {note && <span className="caption">{note}</span>}
    </button>
  )
}

/** The Training tab's landing: the two tiles. */
export function TrainingTiles() {
  const { store, ctx, go } = useApp()
  const today = localDay()
  const day = useCached<DayPlan>(store, '/api/training/day', null, ctx, { today: true })
  const daily = useCached<Plan>(store, DAILY, null, ctx, { today: true })
  const savedOn = useLiveQuery(async () => (await store.settings.get(KEYS.trainedOn))?.value ?? null, [store])
  const d = daily.data && daily.data.date === today ? daily.data : null
  return (
    <div className="screen train" data-testid="training-tiles">
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.session.title}</h1>
      </header>
      <Freshness view={day} />
      <div className="group">
        <Tile title={S.daily.trainingDay} testId="tile-training-day" onOpen={() => go('/training/day')}
          line={trainingDayLine(day.data, savedOn, today)} note={null} />
        <Tile title={S.daily.dailyTitle} testId="tile-daily" onOpen={() => go('/training/daily')}
          line={d?.done_today ? S.daily.doneToday : S.daily.minutes(d?.model_minutes ?? null)}
          note={reminderLine(d?.reminder)} />
      </div>
    </div>
  )
}

/** The daily session before Start: the entries, the 8-hour line, the gelatin line, the
 *  effort and pain rules, each item's how-to, and Start (never locked). */
export function DailyOverview() {
  const { store, ctx, go } = useApp()
  const view = useCached<Plan>(store, DAILY, null, ctx, { today: true })
  const busy = useLiveQuery(async () => (await store.session.get('current')) !== undefined, [store], false)
  const [starting, setStarting] = useState(false)
  const today = localDay()
  const plan = view.data && view.data.date === today && view.data.kind === 'daily' ? view.data : null
  const start = async () => {
    if (!plan || starting) return
    setStarting(true)
    try {
      // One session at a time: a session already kept on this phone is never replaced.
      if (await store.session.get('current')) return
      await startSession(store, startSessionState(plan, newSessionId(plan.date), newExerciseIds(plan.exercises.length)))
      go('/training')
    } finally {
      setStarting(false)
    }
  }
  const line = reminderLine(plan?.reminder)
  // Each item once, for its how-to: the entries repeat across the rounds.
  const items = plan ? plan.exercises.filter((e, i, all) => all.findIndex((x) => x.name === e.name) === i) : []
  return (
    <div className="screen train" data-testid="daily">
      <div className="sky" aria-hidden="true" />
      <Head title={S.daily.dailyTitle} back={S.session.title} onBack={() => go('/training')}
        caption={plan ? S.daily.rounds(plan.exercises.length, plan.model_minutes) : undefined} />
      <Freshness view={view} />
      {busy && <p className="alert" data-testid="daily-blocked">{S.daily.blocked}</p>}
      {!plan ? (
        view.state !== 'loading' && <p className="caption">{S.daily.needsEngine}</p>
      ) : (
        <>
          {plan.done_today && <p className="note" data-testid="daily-done">{S.daily.doneToday}</p>}
          {line && <p className="note" data-testid="daily-reminder">{line}</p>}
          <p className="caption">{S.daily.gelatin}</p>
          {plan.note && <p className="caption" data-testid="daily-note">{plan.note}</p>}
          <Timeline title={S.session.workout} items={plan.exercises.map((e) => ({
            name: e.name, type: e.type, icon: e.icon, prescription: e.prescription, laterality: e.laterality ?? null, mechanics: e.mechanics,
          }))} />
          <section className="card group" aria-label={S.daily.howTo}>
            <h3 className="eyebrow">{S.daily.howTo}</h3>
            {items.map((e) => (
              <details key={e.name} className="guide">
                <summary className="tapline">{`${e.name} · ${e.prescription}`}</summary>
                {e.mechanics && <p className="caption">{e.mechanics}</p>}
              </details>
            ))}
          </section>
          <div className="pair">
            <button className="btn btn--glass btn--gym" onClick={() => go('/training')}>{S.daily.cancel}</button>
            <button className="btn btn--primary btn--gym" data-testid="daily-start" disabled={busy || starting}
              onClick={() => void start()}>{plan.done_today ? S.daily.again : S.daily.start}</button>
          </div>
        </>
      )}
    </div>
  )
}
