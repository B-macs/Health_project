// The save screen (rebuild Phase 6; inventory T89-T102). What was done, the watch check, how
// hard the session was (the owner's own rating: it feeds the session load), the length to
// save, the session notes, and one Save. The save goes through the outbox with the ids
// minted at Start, so it works offline and the engine stores it once however often it is
// sent (rebuild rule 4); the screen says "saved on the phone", then "saved" when the engine
// confirms it. Then the heart-rate match, when a Garmin workout was started (T97-T101).
//
// THE MATCH IS QUEUED WITH THE SAVE (the athlete, 2026-11-11: "why didnt it take the data
// over at that stage ?"): it was asked only after the engine had confirmed the save AND
// while this screen was still open, so a Done tapped before the answer, or the app put
// away, never sent it (one match in the 30 days to 11 Nov). Now Save puts the match in the
// outbox right behind the session, and the engine stores it at once. The screen holds
// Done, with a turning ring, until both have reached the engine (his words: "I dont want
// the user the option to close until it is sent"); Done comes back when a try fails (no
// connection: the phone keeps both and sends them later) or after HOLD_MAX_MS.
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
import { answerOf, enqueue } from '../lib/outbox'
import {
  asksLength, clockMinutes, egymTonnage, heartRateBody, sessionEnd, exerciseOrder, saveBody, setGarmin, type Exercise,
  type HeartRate, type TrainingState,
} from '../lib/training'
import { S } from '../strings'
import { IconCheck } from '../ui/icons'
import { Spinner } from '../ui/parts'

type Schemas = components['schemas']
type Completion = Schemas['CompletionOut']
type OpenActivity = Schemas['OpenActivityOut']
type Update = (f: (s: TrainingState) => TrainingState) => void

/** An outbox item as the saved screen reads it: still there (waiting, or refused), or gone
 *  (the engine has it); `tried` once a try has failed (no connection, the engine down). */
export interface Queued { state: 'waiting' | 'failed' | 'gone'; tried: boolean }

/** The longest the saved screen holds Done while it sends (2026-11-11). The save takes 5-9 s
 *  and the heart-rate match about 8 s (the engine's log, 23 Oct to 11 Nov); a request that
 *  hangs gives Done back after this, and the phone keeps sending. */
export const HOLD_MAX_MS = 60_000

/** Done waits while the save, then the heart-rate match behind it, is sent for the first
 *  time (undefined: not read yet). A failed try of the save gives Done back at once (the
 *  match waits behind the save, so it cannot be tried before it), and so does a refused
 *  save (its match is not stored, and the screen shows the refusal). */
export function holdsDone(save: Queued | null | undefined, hr: Queued | null | undefined, busy: boolean): boolean {
  if (busy || save === undefined) return true
  if (save !== null && save.state !== 'gone') return save.state === 'waiting' && !save.tried
  if (hr === undefined) return true
  return hr !== null && hr.state === 'waiting' && !hr.tried
}

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

/** The EGYM session's review (2026-11-08): each machine's tonnage, set by set as typed from
 *  the EGYM screen, the sets added, and the whole session. */
function TonnageReview({ s }: { s: TrainingState }) {
  const t = egymTonnage(s)
  return (
    <section className="card group" aria-label={S.session.tonnageTitle} data-testid="tonnage-review">
      <h2 className="eyebrow">{S.session.tonnageTitle}</h2>
      <ul className="list">
        {t.machines.map((m) => (
          <li key={m.name} className="group" data-testid="tonnage-line">
            <span className="kv"><span>{m.name}</span><span className="num">{S.session.tonnageKg(m.total)}</span></span>
            <span className="caption">{S.session.tonnageSets(m.sets.map((v) => S.session.tonnageKg(v)))}</span>
          </li>
        ))}
      </ul>
      <p className="kv" data-testid="tonnage-total"><span>{S.session.tonnageTotal}</span><span className="num">{S.session.tonnageKg(t.total)}</span></p>
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

/** The heart-rate match after the save (T97-T101). Queued with the save (`s.hrId`), its
 *  answer comes back through the outbox; a save from before the queue asks once the engine
 *  has the session. The athlete's pick in the travel case is asked here, on the screen. */
export function HeartRateMatch({ s, update, confirmed, queued, onBusy }: {
  s: TrainingState; update: Update; confirmed: boolean
  /** The queued match's outbox item: undefined while it is read, null when none was queued. */
  queued?: Queued | null
  onBusy?: (busy: boolean) => void
}) {
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
        body: heartRateBody(s, saved, choice),
      })
      update((x) => ({ ...x, hr: answer }))
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }
  useEffect(() => onBusy?.(busy), [busy, onBusy])
  // The queued match has reached the engine: its answer is the one the outbox kept. When the
  // app was opened again since, that answer is gone from memory, and the match is asked again
  // (the engine stores the same row).
  useEffect(() => {
    if (!s.hrId || queued?.state !== 'gone' || s.hr || asked.current) return
    asked.current = true
    const answer = answerOf(s.hrId) as HeartRate | undefined
    if (answer) update((x) => ({ ...x, hr: answer }))
    else void match()
    // read once, when the queued match leaves the outbox
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queued?.state])
  // A save made before the match was queued with it: asked once the engine has the save.
  useEffect(() => {
    if (!s.hrId && confirmed && s.garminDeclared && !s.hr && !asked.current) {
      asked.current = true
      void match()
    }
    // asked once, when the engine has confirmed the save
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmed])
  if (!saved) return null
  if (!s.garminDeclared) return <p className="caption" data-testid="hr">{S.session.hrNotStarted(saved.rpe)}</p>
  const hr = s.hr
  if (!hr && s.hrId && queued?.state !== 'failed') {
    // Queued: nothing to show while the session itself is still on its way.
    if (!confirmed || !queued || (queued.state === 'gone' && !busy && !failed)) return null
    if (queued.state === 'waiting' && queued.tried) {
      return <p className="caption" data-testid="hr" data-state="later">{S.session.hrLater}</p>
    }
    if (queued.state === 'waiting' || busy) {
      return <p className="caption sending" data-testid="hr" data-state="matching"><Spinner />{S.session.hrMatching}</p>
    }
  }
  if (!s.hrId && !confirmed) return null
  if (busy) return <p className="caption sending" data-testid="hr" data-state="matching"><Spinner />{S.session.hrMatching}</p>
  if (failed || !hr || hr.state === 'no_match') {
    return (
      <section className="group" data-testid="hr" data-state="no_match">
        <p className="caption">{S.session.hrNone(hr?.reason ?? '', saved.rpe)}</p>
        {(failed || (!hr && queued?.state === 'failed')) && (
          <button className="btn btn--glass" onClick={() => void match()}>{S.session.watchAgain}</button>
        )}
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
  // The session ended at the last completion tap, not when this screen opened.
  const end = useMemo(() => sessionEnd(s, Date.now()), [s])
  const clock = clockMinutes(s, end)
  const ask = asksLength(s, clock)
  const accessory = s.plan.kind === 'accessory'
  // The daily tendon session (WP-40): like the accessory session, it is not the training
  // day, so it never marks the day trained.
  const daily = s.plan.kind === 'daily'
  // The EGYM session (2026-11-08): extra to the plan day, so it never marks the day trained.
  const egym = s.plan.kind === 'egym'
  const extra = accessory || daily || egym
  // The EGYM machines' tonnage list: the "+" menu's session, and session D of the block from
  // week 4 (2026-11-11), which is a plan session and marks the day trained.
  const tonnage = s.plan.exercises.some((e) => e.tonnage_entry)
  // The slider starts at 5, and on the accessory and daily sessions at their own effort target.
  const [rpe, setRpe] = useState(extra ? (s.plan.rpe_target ?? 3) : 5)
  const [choice, setChoice] = useState<'plan' | 'clock'>(ask ? 'plan' : 'clock')
  const [notes, setNotes] = useState('')
  const [completion, setCompletion] = useState<Completion | null>(null)
  const minutes = choice === 'plan' ? s.plan.model_minutes : clock
  // The save and the queued heart-rate match, as the outbox holds them.
  const sent = useLiveQuery(async () => {
    const read = async (id: string | null): Promise<Queued | null> => {
      if (!id) return null
      const row = await store.outbox.where('id').equals(id).first()
      if (!row) return { state: 'gone', tried: false }
      return { state: row.state === 'failed' ? 'failed' : 'waiting', tried: row.attempts > 0 || !!row.last_error }
    }
    return { save: await read(s.savedId), hr: await read(s.hrId) }
  }, [store, s.savedId, s.hrId])
  const saved = !s.savedId ? ('unsaved' as const) : !sent?.save ? undefined
    : sent.save.state === 'gone' ? ('confirmed' as const)
      : sent.save.state === 'failed' ? ('refused' as const) : ('waiting' as const)
  const [hrBusy, setHrBusy] = useState(false)
  const [heldTooLong, setHeldTooLong] = useState(false)
  useEffect(() => {
    if (!s.savedId) return
    const timer = setTimeout(() => setHeldTooLong(true), HOLD_MAX_MS)
    return () => clearTimeout(timer)
  }, [s.savedId])
  const holding = !heldTooLong && holdsDone(sent?.save, sent ? sent.hr : undefined, hrBusy)

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
    // The heart-rate match goes right behind the session (nothing overtakes it in the outbox).
    const hrId = s.garminDeclared ? await enqueue(store, {
      kind: 'heart-rate', method: 'POST', path: '/api/training/heart-rate', body: heartRateBody(s, { rpe, minutes, notes }),
    }) : null
    if (!extra) await store.settings.put({ key: KEYS.trainedOn, value: s.plan.date })
    update((x) => ({ ...x, savedId: id, hrId, saved: { rpe, minutes, notes } }))
  }

  if (s.savedId) {
    return (
      <div className="screen train">
        <div className="sky" aria-hidden="true" />
        <div className="celebrate" aria-hidden="true" data-testid="celebrate"><IconCheck /></div>
        <header className="head">
          <h1 className="head__title">{accessory ? S.session.accessoryLogged : daily ? S.session.dailyLogged
            : egym ? S.session.egymLogged : S.session.congrats}</h1>
          {!extra && <div className="caption">{S.session.congratsNext(exerciseOrder(s).length)}</div>}
        </header>
        <section className="card group" role="status" data-testid="save-state" data-state={saved ?? 'waiting'}>
          {saved === 'confirmed' ? <p>{S.session.saved}</p> : saved === 'refused' ? <p>{S.session.refused}</p>
            : saved === undefined || !sent?.save?.tried
              ? <p className="sending" data-testid="sending"><Spinner />{S.session.sending}</p>
              : <p>{S.session.savedPhone}</p>}
        </section>
        {tonnage && <TonnageReview s={s} />}
        <HeartRateMatch s={s} update={update} confirmed={saved === 'confirmed'} queued={sent ? sent.hr : undefined}
          onBusy={setHrBusy} />
        {s.plan.next_day && <p className="caption">{S.session.tomorrow(s.plan.next_day.day_num, s.plan.next_day.objective)}</p>}
        {holding
          ? <p className="caption" data-testid="hold-done">{S.session.holdDone}</p>
          : <button className="btn btn--primary btn--wide" onClick={onDone}>{S.session.done}</button>}
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
      {tonnage ? <TonnageReview s={s} /> : <Review s={s} />}
      <WatchCheck s={s} />
      <section className="card group">
        <label className="group">
          <span className="kv"><span>{S.session.effort}</span><span className="num">{S.session.effortValue(rpe)}</span></span>
          <input type="range" className="slider" min={1} max={10} step={1} value={rpe} aria-label={S.session.effort}
            onChange={(e) => setRpe(Number(e.target.value))} />
        </label>
        {accessory && <p className="caption">{S.session.accessoryEffortHelp}</p>}
        {daily && <p className="caption">{S.session.dailyEffortHelp}</p>}
        {egym && <p className="caption">{S.session.egymEffortHelp}</p>}
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
