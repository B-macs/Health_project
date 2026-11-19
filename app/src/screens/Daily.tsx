// The Training tab's two tiles and the daily tendon session (WP-40, 2026-10-28). The owner:
// "the first tile when selected will bring me to the normal training day and what is
// required for that day. the other tile will be the daily training day."
//
// - The tiles: side by side on the week page (/training), right under its week dates, which
//   nothing goes above (the owner, 2026-10-28: "Keep all the rest of the data on the
//   training page just put the two title right and left of each other", and "Make the week
//   dates at the top of the page always, nothing goes above them"). "Training day" is the
//   page they sit on and takes the strip back to today; "Daily tendon session" opens its
//   overview (/training/daily).
// - The daily session: the same session every day, from the engine (GET
//   /api/training/daily), run in the same guided flow as the plan session and saved as its
//   own kind, so it never marks the training day done. Its 8-hour line is a reminder only:
//   Start is never locked ("Reminder only let me make the desicion on when to do it and
//   never locked"). Every number and word is the engine's or strings.ts's.
// - The evening mobility session (2026-11-11): on the evening of a strength day with no
//   strength the next day the engine answers the same address with kind 'mobility' ("The
//   mobility training will replace the tendon training on those days"). The engine decides
//   the day; the phone only shows the answer, with its own title and no gelatin line.
// - The day picked in the strip (2026-11-18: "When I select each day today every one of them
//   is mobility ? Tomorrow should be tendon?"): the second tile asks the engine for that day
//   (?date=), and opens that day's session to read; Start is offered on the day itself only.
// - Swap with another day (2026-11-19: "If for what ever reason I dont want to do Evening
//   mobility today or if I dont want to do daily tendon, I should be able to swap with another
//   day"): the days the engine allows (swap_targets), and the answer through the outbox.
import { useLiveQuery } from 'dexie-react-hooks'
import { useState } from 'react'
import type { components } from '../generated/api'
import { KEYS } from '../db/schema'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached } from '../lib/cache'
import { swapEvening, useScheduleAnswers } from '../lib/schedule'
import { startSession } from '../lib/session'
import { newExerciseIds, newSessionId, startSessionState, type Plan } from '../lib/training'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { Sheet } from '../ui/Sheet'
import { Timeline } from '../ui/timeline'
import { Head } from './Extras'
import { longDate, trainedToday } from './TrainingTab'
import { waiting } from './Week'

type Schemas = components['schemas']
type DayPlan = Schemas['TrainingDayOut']
type Reminder = Schemas['DailyReminder']

export const DAILY = '/api/training/daily'

/** The second tile's address for a day: today's has no date in it, so the phone keeps one
 *  answer for "today" whatever the date (the same rule as the day's own address). */
export function dailyAddress(day: string, today: string): string {
  return day === today ? DAILY : `${DAILY}?date=${day}`
}

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

function Tile({ title, line, note, testId, current, onOpen }: {
  title: string; line: string; note: string | null; testId: string; current?: boolean; onOpen: () => void
}) {
  return (
    <button className="card tile tile--button" data-testid={testId} aria-current={current ? 'page' : undefined}
      onClick={onOpen}>
      <span className="eyebrow">{title}</span>
      <span className="tile__line">{line}</span>
      {note && <span className="caption">{note}</span>}
    </button>
  )
}

/** The second tile's title: the evening mobility session on its evenings, else the daily
 *  tendon session. */
export function secondTileTitle(plan: Plan | null | undefined): string {
  return plan?.kind === 'mobility' ? S.daily.mobilityTitle : S.daily.dailyTitle
}

/** The two tiles, side by side, under the week page's week dates. The second one follows
 *  the day picked in the strip (`selected`): that day's tendon or mobility session. */
export function TrainingTiles({ onTrainingDay, selected }: { onTrainingDay: () => void; selected?: string }) {
  const { store, ctx, go } = useApp()
  const today = localDay()
  const picked = selected ?? today
  const day = useCached<DayPlan>(store, '/api/training/day', null, ctx, { today: true })
  const daily = useCached<Plan>(store, dailyAddress(picked, today), null, ctx, { today: picked === today })
  const savedOn = useLiveQuery(async () => (await store.settings.get(KEYS.trainedOn))?.value ?? null, [store])
  const d = daily.data && daily.data.date === picked ? daily.data : null
  const isToday = picked === today
  return (
    <div className="pair tiles" data-testid="training-tiles">
      <Tile title={S.daily.trainingDay} testId="tile-training-day" current onOpen={onTrainingDay}
        line={trainingDayLine(day.data, savedOn, today)} note={null} />
      <Tile title={secondTileTitle(d)} testId="tile-daily"
        onOpen={() => go(isToday ? '/training/daily' : `/training/daily/${picked}`)}
        line={d?.done_today ? (isToday ? S.daily.doneToday : S.daily.doneThatDay)
          : S.daily.minutes(d?.model_minutes ?? null)}
        note={isToday ? reminderLine(d?.reminder) : null} />
    </div>
  )
}

/** The second tile's session before Start: the entries, the 8-hour line and the gelatin line
 *  (the tendon session only), the note, each item's how-to, and Start (never locked). For a
 *  day other than today (`day`, picked in the strip) the same page to read, with no Start. */
export function DailyOverview({ day }: { day?: string } = {}) {
  const { store, ctx, go } = useApp()
  const today = localDay()
  const wanted = day ?? today
  const other = wanted !== today
  const view = useCached<Plan>(store, dailyAddress(wanted, today), null, ctx, { today: !other })
  const busy = useLiveQuery(async () => (await store.session.get('current')) !== undefined, [store], false)
  const [starting, setStarting] = useState(false)
  const plan = view.data && view.data.date === wanted
    && (view.data.kind === 'daily' || view.data.kind === 'mobility') ? view.data : null
  const mobility = plan?.kind === 'mobility'
  // The days this session can swap with, from the engine; none while a swap waits to be sent.
  const answers = useScheduleAnswers(store)
  const [swapping, setSwapping] = useState(false)
  const targets = plan && !plan.done_today && !waiting(answers, 'evening') ? plan.swap_targets ?? [] : []
  const swapTo = (to: string) => {
    setSwapping(false)
    void swapEvening(store, wanted, to).then(() => go('/training'))
  }
  const start = async () => {
    if (!plan || starting || other) return
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
      <Head title={secondTileTitle(plan)} back={S.session.title} onBack={() => go('/training')}
        caption={!plan ? undefined : mobility ? S.daily.mobilityCaption(plan.exercises.length, plan.model_minutes)
          : S.daily.rounds(plan.exercises.length, plan.model_minutes)} />
      <Freshness view={view} />
      {other && <p className="caption" data-testid="daily-other-day">{S.daily.otherDay(longDate(wanted))}</p>}
      {busy && !other && <p className="alert" data-testid="daily-blocked">{S.daily.blocked}</p>}
      {!plan ? (
        view.state !== 'loading' && <p className="caption">{S.daily.needsEngine}</p>
      ) : (
        <>
          {plan.done_today && <p className="note" data-testid="daily-done">{S.daily.doneToday}</p>}
          {line && <p className="note" data-testid="daily-reminder">{line}</p>}
          {!mobility && <p className="caption">{S.daily.gelatin}</p>}
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
            {!other && (
              <button className="btn btn--primary btn--gym" data-testid="daily-start" disabled={busy || starting}
                onClick={() => void start()}>{plan.done_today ? S.daily.again : S.daily.start}</button>
            )}
          </div>
          {targets.length > 0 && (
            <button className="btn btn--glass btn--wide" data-testid="daily-swap" onClick={() => setSwapping(true)}>
              {S.daily.swap}
            </button>
          )}
          {swapping && (
            <Sheet title={S.daily.swap} closeLabel={S.daily.cancel} onClose={() => setSwapping(false)}>
              <div className="group" data-testid="daily-swap-days">
                <p className="caption">{S.daily.swapIntro(secondTileTitle(plan))}</p>
                {targets.map((t) => (
                  <button key={t.date} className="btn btn--glass btn--wide" data-testid={`daily-swap-${t.date}`}
                    onClick={() => swapTo(t.date)}>
                    {S.daily.swapTo(longDate(t.date), t.kind === 'mobility' ? S.daily.mobilityTitle : S.daily.dailyTitle)}
                  </button>
                ))}
              </div>
            </Sheet>
          )}
        </>
      )}
    </div>
  )
}
