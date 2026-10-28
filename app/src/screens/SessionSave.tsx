// The save screen (rebuild Phase 6; inventory T89-T102). What was done, the watch check, how
// hard the session was (the owner's own rating: it feeds the session load), the length to
// save, the session notes, and one Save. The save goes through the outbox with the ids
// minted at Start, so it works offline and the engine stores it once however often it is
// sent (rebuild rule 4); the screen says "saved on the phone", then "saved" when the engine
// confirms it. Then the heart-rate match, when a Garmin workout was started (T97-T101).
//
// The length: the clock counts from the first completion tap, with the plan's floor; past
// the threshold the engine sent with the plan (T93), the owner picks the plan's length or
// the clock's. The load shown is the engine's (POST /api/training/completion), when it
// answers; offline it is worked out when the save is sent. Every figure of the heart-rate
// match is the engine's (sessions.hr_comparison); the phone only words it.
import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { components } from '../generated/api'
import { api, ApiError } from '../lib/api'
import { useApp } from '../lib/appState'
import { KEYS } from '../db/schema'
import { enqueue } from '../lib/outbox'
import {
  asksLength, clockMinutes, exerciseOrder, saveBody, setGarmin, type Exercise, type HeartRate, type TrainingState,
} from '../lib/training'
import { S } from '../strings'
import { IconCheck } from '../ui/icons'

type Schemas = components['schemas']
type Completion = Schemas['CompletionOut']
type OpenActivity = Schemas['OpenActivityOut']
type Update = (f: (s: TrainingState) => TrainingState) => void

/** One exercise as done today (T90; sessions.review_figures): the watch's minutes for a
 *  walk or run it verified, else the engine's estimate; the sets recorded (`done_sets`: none
 *  is a skipped exercise, which the engine stores with no set done, WP-22); the weight of
 *  the last recorded working set, else the prescribed one. */
export function reviewLine(s: TrainingState, ex: Exercise): {
  time: string; sets: number; weight: string; skipped: boolean
} {
  const pull = s.garmin[ex.index]
  const time = pull?.state === 'found' ? S.session.timeGarmin(Math.round(pull.minutes))
    : S.session.timeEstimated(ex.estimated_minutes)
  const done = (s.sets[ex.index] ?? []).length
  const recorded = ex.warmup ? [] : (s.sets[ex.index] ?? [])
  const weight = recorded[recorded.length - 1]?.right?.weight_kg ?? ex.weight_kg ?? null
  return { time, sets: done, weight: weight ? S.session.kg(weight) : S.session.bodyweightShort, skipped: done === 0 }
}

function Review({ s }: { s: TrainingState }) {
  return (
    <section className="card group" aria-label={S.session.review}>
      <h2 className="eyebrow">{S.session.review}</h2>
      <ul className="list">
        {exerciseOrder(s).map((i) => s.plan.exercises[i]).map((ex) => {
          const line = reviewLine(s, ex)
          return (
            <li key={ex.index} className="group" data-testid="review-line">
              <span>{ex.name}</span>
              <span className="caption">
                {line.skipped ? S.session.skipped : `${line.time} · ${S.session.setsDone(line.sets)} · ${line.weight}`}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/** The watch check before the save (T91): only when a Garmin workout was started. */
function WatchCheck({ s }: { s: TrainingState }) {
  const { ctx } = useApp()
  const [check, setCheck] = useState<{ state: 'checking' | 'found' | 'missing' | 'offline'; answer?: OpenActivity }>(
    { state: 'checking' })
  const run = () => {
    if (!s.garminDeclared) return
    setCheck({ state: 'checking' })
    api<OpenActivity>('/api/training/garmin/open-activity', { key: ctx.key, engineDown: ctx.engineDown, day: s.plan.date })
      .then((answer) => setCheck({ state: answer.found ? 'found' : 'missing', answer }),
        () => setCheck({ state: 'offline' }))
  }
  // once at the screen's start; Check again runs it again
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(run, [])
  if (!s.garminDeclared) return <p className="caption" data-testid="watch-check">{S.session.noWatch}</p>
  const activity = check.answer?.activity
  return (
    <section className="card group" data-testid="watch-check" data-state={check.state}>
      <p className={check.state === 'missing' ? 'alert' : undefined}>
        {check.state === 'checking' ? S.session.watchChecking
          : check.state === 'found' ? S.session.watchFound(activity?.name ?? '', activity?.duration_minutes ?? null)
            : check.state === 'missing' ? S.session.watchStop : S.session.watchNoConnection}
      </p>
      {check.state !== 'found' && check.state !== 'checking' && (
        <button className="btn btn--glass" onClick={run}>{S.session.watchAgain}</button>
      )}
    </section>
  )
}

/** The heart-rate match after the save (T97-T101): asked once the engine has the session. */
export function HeartRateMatch({ s, update, confirmed }: { s: TrainingState; update: Update; confirmed: boolean }) {
  const { ctx } = useApp()
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const [pick, setPick] = useState(0)
  const asked = useRef(false)
  const saved = s.saved
  const match = async (choice?: { activity_id: string; shift_hours: number }) => {
    if (!saved) return
    setBusy(true)
    setFailed(false)
    try {
      const answer = await api<HeartRate>('/api/training/heart-rate', {
        method: 'POST', key: ctx.key, engineDown: ctx.engineDown, day: s.plan.date,
        body: {
          date: s.plan.date, session: saveBody(s, saved.minutes, saved.rpe, saved.notes),
          duration_minutes: saved.minutes, reported_rpe: saved.rpe, ...(choice ?? {}),
        },
      })
      update((x) => ({ ...x, hr: answer }))
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }
  useEffect(() => {
    if (confirmed && s.garminDeclared && !s.hr && !asked.current) {
      asked.current = true
      void match()
    }
    // asked once, when the engine has confirmed the save
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmed])
  if (!saved) return null
  if (!s.garminDeclared) return <p className="caption" data-testid="hr">{S.session.hrNotStarted(saved.rpe)}</p>
  if (!confirmed) return null
  if (busy) return <p className="caption" data-testid="hr">{S.session.hrMatching}</p>
  const hr = s.hr
  if (failed || !hr || hr.state === 'no_match') {
    return (
      <section className="group" data-testid="hr" data-state="no_match">
        <p className="caption">{S.session.hrNone(hr?.reason ?? '', saved.rpe)}</p>
        {failed && <button className="btn btn--glass" onClick={() => void match()}>{S.session.watchAgain}</button>}
      </section>
    )
  }
  if (hr.state === 'choose') {
    const options = hr.candidates
    return (
      <section className="card group" data-testid="hr" data-state="choose">
        <p className="alert">{S.session.hrChoose(hr.reason)}</p>
        <div className="segmented segmented--wrap" role="radiogroup" aria-label={S.session.hrWhich}>
          {options.map((c, i) => (
            <button key={c.activity_id || i} role="radio" aria-checked={pick === i}
              className={`segmented__item${pick === i ? ' segmented__item--on' : ''}`} onClick={() => setPick(i)}>
              {S.session.hrCandidate(c.start_time_local.slice(11, 16), c.name || c.type, c.duration_minutes ?? null,
                c.shift_hours, c.quality ?? null)}
            </button>
          ))}
        </div>
        {options.length > 0 && (
          <button className="btn btn--primary" onClick={() => void match({
            activity_id: options[pick].activity_id, shift_hours: options[pick].shift_hours })}>
            {S.session.hrUse}
          </button>
        )}
        <p className="caption">{S.session.hrSkip}</p>
      </section>
    )
  }
  const c = hr.comparison!
  const yoursAu = c.au_delta != null ? c.measured_au - c.au_delta : null
  return (
    <section className="card group" data-testid="hr" data-state="matched">
      <div className="figures">
        <div className="figure">
          <span className="eyebrow">{S.session.hrMeasuredRpe}</span>
          <span className="num figure__value">{c.measured_rpe}</span>
          {c.rpe_delta != null && <span className="caption">{S.session.hrVsYours(c.rpe_delta, saved.rpe)}</span>}
        </div>
        <div className="figure">
          <span className="eyebrow">{S.session.hrMeasuredAu}</span>
          <span className="num figure__value">{Math.round(c.measured_au)}</span>
          {c.au_delta != null && yoursAu != null && <span className="caption">{S.session.hrVsYoursAu(c.au_delta, yoursAu)}</span>}
        </div>
        {c.active_minutes != null && (
          <div className="figure">
            <span className="eyebrow">{S.session.hrActive}</span>
            <span className="num figure__value">{S.session.hrMinutes(c.active_minutes)}</span>
          </div>
        )}
      </div>
      {c.verdict && <p className="caption">{`${S.session.hrVerdict[c.verdict]} ${S.session.hrBoth(saved.rpe, c.measured_rpe)}`}</p>}
      <p className="caption">{S.session.hrMatchedTo(c.activity ?? '', c.covered_exercises ?? null, c.total_exercises ?? null, c.coverage)}</p>
      {c.low_coverage && <p className="note">{S.session.hrLowCover(c.coverage)}</p>}
    </section>
  )
}

export function SessionSave({ s, update, onDone }: { s: TrainingState; update: Update; onDone: () => void }) {
  const { store, ctx } = useApp()
  const end = useMemo(() => Date.now(), [])
  const clock = clockMinutes(s, end)
  const ask = asksLength(s, clock)
  const accessory = s.plan.kind === 'accessory'
  // The daily tendon session (WP-40): like the accessory session, it is not the training
  // day, so it never marks the day trained.
  const daily = s.plan.kind === 'daily'
  const extra = accessory || daily
  // The slider starts at 5, and on the accessory and daily sessions at their own effort target.
  const [rpe, setRpe] = useState(extra ? (s.plan.rpe_target ?? 3) : 5)
  const [choice, setChoice] = useState<'plan' | 'clock'>(ask ? 'plan' : 'clock')
  const [notes, setNotes] = useState('')
  const [completion, setCompletion] = useState<Completion | null>(null)
  const minutes = choice === 'plan' ? s.plan.model_minutes : clock
  const saved = useLiveQuery(async () => {
    if (!s.savedId) return 'unsaved' as const
    const row = await store.outbox.where('id').equals(s.savedId).first()
    return row ? (row.state === 'failed' ? ('refused' as const) : ('waiting' as const)) : ('confirmed' as const)
  }, [store, s.savedId])

  // The load at each rating for each length, from the engine (no rule here).
  useEffect(() => {
    if (s.savedId || !s.firstSetAt) return
    void api<Completion>('/api/training/completion', {
      method: 'POST', key: ctx.key, engineDown: ctx.engineDown,
      body: { model_minutes: s.plan.model_minutes, start_ts: s.firstSetAt / 1000, end_ts: end / 1000, rpe, kind: s.plan.kind },
    }).then(setCompletion, () => setCompletion(null))
    // once, at the screen's start; the answer carries every rating's load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // A walk or run that ended with no connection: the watch is asked again here (T75), at
  // the screen's start and when the phone comes back online. A save made before the
  // answer keeps the planned minutes, as the Streamlit page does with no watch answer.
  const pending = s.plan.exercises.filter((ex) => s.garmin[ex.index]?.state === 'pending')
  const asking = useRef(false)
  useEffect(() => {
    if (s.savedId || !pending.length) return
    const ask = () => {
      if (asking.current) return
      asking.current = true
      void Promise.all(pending.map((ex) => api<{ minutes: number; detail: Record<string, unknown> | null }>(
        `/api/training/garmin/activity-minutes?planned_minutes=${ex.duration_minutes ?? 0}`,
        { key: ctx.key, engineDown: ctx.engineDown, day: s.plan.date, timeoutMs: 8000 })
        .then((got) => update((x) => setGarmin(x, ex.index, got.minutes > 0
          ? { state: 'found', minutes: got.minutes, detail: got.detail } : { state: 'none' }, x.notice)),
        (err) => {
          if (err instanceof ApiError && (err.kind === 'rejected' || err.kind === 'server')) {
            update((x) => setGarmin(x, ex.index, { state: 'none' }, x.notice))
          }
        }))).finally(() => { asking.current = false })
    }
    ask()
    window.addEventListener('online', ask)
    return () => window.removeEventListener('online', ask)
    // the pending walks, while the session is not saved
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.savedId, pending.length])
  const au = completion?.choices.find((c) => c.minutes === minutes)?.au_by_rpe[rpe - 1]

  // A second tap before the first is stored would queue the save twice (the engine would
  // still keep one, by its ids): the button waits for the first.
  const sending = useRef(false)
  const [busy, setBusy] = useState(false)
  const save = async () => {
    if (sending.current) return
    sending.current = true
    setBusy(true)
    const id = await enqueue(store, { kind: 'session', method: 'POST', path: '/api/training/sessions', body: saveBody(s, minutes, rpe, notes) })
    if (!extra) await store.settings.put({ key: KEYS.trainedOn, value: s.plan.date })
    update((x) => ({ ...x, savedId: id, saved: { rpe, minutes, notes } }))
  }

  if (s.savedId) {
    return (
      <div className="screen train">
        <div className="sky" aria-hidden="true" />
        <div className="celebrate" aria-hidden="true" data-testid="celebrate"><IconCheck /></div>
        <header className="head">
          <h1 className="head__title">{accessory ? S.session.accessoryLogged : daily ? S.session.dailyLogged : S.session.congrats}</h1>
          {!extra && <div className="caption">{S.session.congratsNext(exerciseOrder(s).length)}</div>}
        </header>
        <section className="card group" role="status" data-testid="save-state" data-state={saved}>
          <p>{saved === 'confirmed' ? S.session.saved : saved === 'refused' ? S.session.refused : S.session.savedPhone}</p>
        </section>
        <HeartRateMatch s={s} update={update} confirmed={saved === 'confirmed'} />
        {s.plan.next_day && <p className="caption">{S.session.tomorrow(s.plan.next_day.day_num, s.plan.next_day.objective)}</p>}
        <button className="btn btn--primary btn--wide" onClick={onDone}>{S.session.done}</button>
      </div>
    )
  }

  return (
    <div className="screen train">
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.session.complete(s.plan.day_num)}</h1>
        <div className="caption">{S.session.allDone(exerciseOrder(s).length)}</div>
      </header>
      {s.notice && <p className="note" role="status" data-testid="notice">{s.notice}</p>}
      <Review s={s} />
      <WatchCheck s={s} />
      <section className="card group">
        <label className="group">
          <span className="kv"><span>{S.session.effort}</span><span className="num">{S.session.effortValue(rpe)}</span></span>
          <input type="range" className="slider" min={1} max={10} step={1} value={rpe} aria-label={S.session.effort}
            onChange={(e) => setRpe(Number(e.target.value))} />
        </label>
        {accessory && <p className="caption">{S.session.accessoryEffortHelp}</p>}
        {daily && <p className="caption">{S.session.dailyEffortHelp}</p>}
      </section>
      {ask && (
        <section className="card group">
          <p>{S.session.lengthAsk(clock, s.plan.model_minutes)}</p>
          <div className="segmented segmented--wrap" role="radiogroup" aria-label={S.session.lengthAsk(clock, s.plan.model_minutes)}>
            {(['plan', 'clock'] as const).map((c) => (
              <button key={c} role="radio" aria-checked={choice === c}
                className={`segmented__item${choice === c ? ' segmented__item--on' : ''}`} onClick={() => setChoice(c)}>
                {c === 'plan' ? S.session.lengthPlan(s.plan.model_minutes) : S.session.lengthClock(clock)}
              </button>
            ))}
          </div>
        </section>
      )}
      <p className="caption">{S.session.duration(minutes, ask)}</p>
      <p className="caption">{au != null ? S.session.load(au) : S.session.loadLater}</p>
      <label className="group">
        <span className="caption">{S.session.sessionNotes}</span>
        <textarea className="field field--area" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <button className="btn btn--primary btn--wide" disabled={busy} onClick={() => void save()}>{S.session.save}</button>
    </div>
  )
}
