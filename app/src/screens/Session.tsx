// The guided training session (rebuild Phase 6; the owner's pick: Cards; inventory
// T46-T88), in Training's colour family (amber). One exercise at a time with large
// numbers: its set chips, the timer or the reps, the steppers, the controls, what comes
// next, how to do it, the last session, a note, Back and Skip. What to do, the numbers and
// the timer only: no "why" panel; a warning only when the engine sent one (Key Rule 20);
// the weight label never names machine units.
//
// It walks the engine's steps (lib/training.ts) and keeps the session in the phone's
// database after every tap. Timers run on timestamps (lib/timers.ts): a hold rings the
// bell the engine named and moves on by itself 0.7 s later, a rest starts by itself and
// moves on 0.9 s after its rising bell, and a hold the engine marks starts by itself when
// a timer that ran out brought the flow to it (as on the Streamlit page); when the app
// was hidden at the end, nothing moves by itself and the screen says when it ended. The
// screen stays on (the Wake Lock API).
import { useCallback, useEffect, useRef, useState, type InputHTMLAttributes } from 'react'
import { debugLog } from '../debug/console'
import { alertFor, cancelAlert, scheduleAlert } from '../lib/alerts'
import { api, ApiError } from '../lib/api'
import { useApp } from '../lib/appState'
import { bell, reportAudioOnce, restOver, tick, unlockAudio, type Ending } from '../lib/sounds'
import {
  endsAt, extendTimer, hasEnded, holdLengthMs, isRunning, leadInLeftMs, pauseTimer, remainingMs, resumeTimer, shownSeconds,
  startTimer, ticksCrossed, type Timer,
} from '../lib/timers'
import {
  advance, back, backTarget, currentStep, doFirst, doFirstCandidates, exerciseOf, exerciseOrder, exerciseProgress, finished,
  lastRecorded, readingComplete, setBand, setGarmin, setNote, setReading, setRecordedSide, setSide, sideValues, skip,
  skipRestOfRetest, stepBand, stepWeight, swapCandidates, swapTo, timerHere, typedReadings, withTimer,
  type Exercise, type FlowStep, type GarminPull, type Side, type SideValues, type TrainingState,
} from '../lib/training'
import { S } from '../strings'
import { clock, useWakeLock } from '../ui/hooks'
import { IconCheck, IconClose, IconPause, IconPlay } from '../ui/icons'

const HOLD_AUTO_MS = 700
const REST_AUTO_MS = 900
/** How long the watch may take to answer at the end of a walk before the flow moves on. */
const GARMIN_WAIT_MS = 8000
/** The digits turn to the page's strongest shade near the end: a hold's last 3 seconds, an
 *  activity's last 30 (the Streamlit page's timers, T81 and T84). */
const LAST_MS: Record<string, number> = { hold: 3000, duration: 30_000 }

const time = (ms: number) => new Date(ms).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

/** A clock that ticks while a timer runs and whenever the app comes back to the front. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const update = () => setNow(Date.now())
    const visible = () => {
      if (document.visibilityState === 'visible') update()
    }
    document.addEventListener('visibilitychange', visible)
    const id = active ? window.setInterval(update, 200) : undefined
    return () => {
      document.removeEventListener('visibilitychange', visible)
      if (id) window.clearInterval(id)
    }
  }, [active])
  return now
}

/** The timer the entry the flow just reached starts by itself, as the engine marked it
 *  (the walk's `timer_starts`, T81): a rest on any arrival; a hold only when a timer that
 *  ran out moved the flow here (`byTimer`), never after a tap. */
export function arrivalTimer(s: TrainingState, now: number, byTimer: boolean): Timer | null {
  const step = currentStep(s)
  const ex = exerciseOf(s, step)
  if (!step || !ex) return null
  if (step.timer_starts === 'on_arrival') return startTimer('rest', (ex.rest_seconds ?? 0) * 1000, now)
  if (step.timer_starts === 'after_timer' && byTimer) return startTimer('hold', holdLengthMs(ex), now)
  return null
}

/** A field over the stored session. It shows what is typed at once and stores every key:
 *  the store answers a moment later, and a field that showed the stored value would lose
 *  the keys typed in between. Give it a `key` that changes with the entry it edits. */
function Field({ initial, onValue, ...props }: {
  initial: string
  onValue: (value: string) => void
} & Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'>) {
  const [value, setValue] = useState(initial)
  return (
    <input {...props} value={value} onChange={(e) => {
      const typed = e.target.value
      setValue(typed)
      onValue(typed)
    }} />
  )
}

/** Where the session is (T51, T52): the day, today's progress, and every exercise with
 *  done, now and next marked. */
function SessionHeader({ s }: { s: TrainingState }) {
  const { done, total } = exerciseProgress(s)
  return (
    <section className="group" aria-label={S.session.todaysSession}>
      {s.plan.day_num != null && (
        <p className="caption">{S.session.dayHeader(s.plan.day_num, s.plan.plan_days ?? null, s.plan.rpe_target)}</p>
      )}
      <div className="kv">
        <span className="caption">{S.session.todaysSession}</span>
        <span className="caption num">{S.session.progressOf(done, total)}</span>
      </div>
      <div className="progress" role="progressbar" aria-label={S.session.todaysSession} aria-valuemin={0}
        aria-valuemax={total} aria-valuenow={done}>
        <span className="progress__fill" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
      </div>
      <details className="guide">
        <summary className="tapline">{S.session.allExercises}</summary>
        <ol className="list">
          {exerciseOrder(s).map((exIdx, i) => (
            <li key={exIdx} className="kv" data-state={i < done ? 'done' : i === done ? 'now' : 'todo'}>
              <span>{s.plan.exercises[exIdx].name}</span>
              <span className="caption">
                {i < done ? S.session.doneMark : i === done ? S.session.nowMark : i === done + 1 ? S.session.nextMark : ''}
              </span>
            </li>
          ))}
        </ol>
      </details>
    </section>
  )
}

function Chips({ s, step }: { s: TrainingState; step: FlowStep }) {
  const chips = s.plan.steps
    .map((st, i) => ({ st, i }))
    .filter(({ st }) => st.ex_idx === step.ex_idx && st.phase !== 'resting')
  return (
    <ol className="tracker">
      {chips.map(({ st, i }) => {
        const state = i < s.step ? 'done' : i === s.step ? 'now' : 'todo'
        return (
          <li key={i} className={`tracker__chip tracker__chip--${state}`}>
            <span className="tracker__set">{S.session.setN(st.set_num)}</span>
            <span className="tracker__side">
              {state === 'done' ? <IconCheck /> : exerciseOf(s, st)?.laterality === 'unilateral' ? S.session.sideShort[st.side] : ''}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function Stepper({ label, value, onLess, onMore }: { label: string; value: string; onLess: () => void; onMore: () => void }) {
  return (
    <div className="bigstep">
      <span className="eyebrow">{label}</span>
      <div className="stepper">
        <button className="iconbtn iconbtn--gym" aria-label={S.session.less(label)} onClick={onLess}>{S.detail.minus}</button>
        <span className="num bigstep__value">{value}</span>
        <button className="iconbtn iconbtn--gym" aria-label={S.session.more(label)} onClick={onMore}>{S.detail.plus}</button>
      </div>
    </div>
  )
}

/** A small stepper: the other side's numbers beside the big ones, and the set just done.
 *  `name` names the buttons with the side and the set, so no two buttons share a name. */
function MiniStepper({ label, name, value, onLess, onMore }: {
  label: string; name: string; value: string; onLess: () => void; onMore: () => void
}) {
  return (
    <div className="ministep">
      <span className="caption">{label}</span>
      <div className="stepper">
        <button className="iconbtn" aria-label={S.session.less(name)} onClick={onLess}>{S.detail.minus}</button>
        <span className="num stepper__value">{value}</span>
        <button className="iconbtn" aria-label={S.session.more(name)} onClick={onMore}>{S.detail.plus}</button>
      </div>
    </div>
  )
}

/** Which of reps, weight and band an exercise's steppers show. */
function shown(ex: Exercise) {
  return {
    reps: ex.type === 'reps' || ex.type === 'hold_reps' ? ex.reps_editable || !!ex.equipment_type : false,
    weight: !!ex.equipment_type && ex.equipment_type !== 'band',
    band: ex.equipment_type === 'band',
  }
}

const weightText = (ex: Exercise, w: number | null | undefined) =>
  (ex.increment_unit === 'kg' ? S.session.kg(w ?? 0) : String(w ?? 0))

/** One side's reps and weight as small steppers (WP-25). `title` is the side's name on a
 *  one-side exercise; `prefix` starts each button's name. */
function SideRow({ ex, title, prefix, values, onChange }: {
  ex: Exercise
  title: string | null
  prefix: string
  values: Partial<SideValues>
  onChange: (patch: Partial<SideValues>) => void
}) {
  const show = shown(ex)
  return (
    <div className="siderow">
      {title && <span className="eyebrow">{title}</span>}
      <div className="siderow__steps">
        {show.reps && (
          <MiniStepper label={S.session.reps} name={S.session.named(prefix, S.session.reps)} value={String(values.reps ?? '—')}
            onLess={() => onChange({ reps: Math.max(1, (values.reps ?? 1) - 1) })}
            onMore={() => onChange({ reps: (values.reps ?? 0) + 1 })} />
        )}
        {show.weight && (
          <MiniStepper label={S.session.weight} name={S.session.named(prefix, S.session.weight)}
            value={weightText(ex, values.weight_kg)}
            onLess={() => onChange({ weight_kg: stepWeight(values.weight_kg ?? null, -1, ex.increment_size) })}
            onMore={() => onChange({ weight_kg: stepWeight(values.weight_kg ?? null, 1, ex.increment_size) })} />
        )}
      </div>
    </div>
  )
}

/** The set just done, in the rest after it (WP-25): each side's numbers, changed in that
 *  set's own record; the next set starts from them. */
function JustDone({ s, ex, update }: {
  s: TrainingState
  ex: Exercise
  update: (f: (s: TrainingState) => TrainingState) => void
}) {
  const rec = lastRecorded(s, ex.index)
  const show = shown(ex)
  if (!rec || !(show.reps || show.weight)) return null
  const first = s.plan.first_side as Side
  const oneSide = ex.laterality === 'unilateral'
  const sides: Side[] = oneSide ? [first, first === 'right' ? 'left' : 'right'] : ['right']
  return (
    <section className="card group" data-testid="just-done">
      <p className="eyebrow">{S.session.justDone(rec.set_num)}</p>
      {sides.map((side) => (
        <SideRow key={side} ex={ex} title={oneSide ? S.session.side[side] : null}
          prefix={oneSide ? S.session.named(S.session.setN(rec.set_num), S.session.side[side]) : S.session.setN(rec.set_num)}
          values={rec[side] ?? {}}
          onChange={(patch) => update((x) => setRecordedSide(x, ex.index, rec.set_num, side, patch))} />
      ))}
    </section>
  )
}

/** The reps, the weight and the band of the side the step is on; on a one-side exercise,
 *  the other side's own numbers below them, to change at any time (WP-25). */
function Steppers({ s, step, ex, update }: {
  s: TrainingState
  step: FlowStep
  ex: Exercise
  update: (f: (s: TrainingState) => TrainingState) => void
}) {
  const side = (ex.laterality === 'unilateral' ? step.side : 'right') as Side
  const other: Side = side === 'right' ? 'left' : 'right'
  const live = s.live[ex.index]
  const values = sideValues(live, side)
  const tiers = s.plan.band_tiers.map((b) => b.tier)
  const { reps: showReps, weight: showWeight, band: showBand } = shown(ex)
  if (!showReps && !showWeight && !showBand) return null
  return (
    <section className="card steppers">
      {showReps && (
        <Stepper label={S.session.reps} value={String(values.reps ?? '—')}
          onLess={() => update((x) => setSide(x, ex.index, side, { reps: Math.max(1, (values.reps ?? 1) - 1) }))}
          onMore={() => update((x) => setSide(x, ex.index, side, { reps: (values.reps ?? 0) + 1 }))} />
      )}
      {showWeight && (
        <Stepper label={S.session.weight}
          value={weightText(ex, values.weight_kg)}
          onLess={() => update((x) => setSide(x, ex.index, side, { weight_kg: stepWeight(values.weight_kg, -1, ex.increment_size) }))}
          onMore={() => update((x) => setSide(x, ex.index, side, { weight_kg: stepWeight(values.weight_kg, 1, ex.increment_size) }))} />
      )}
      {showBand && (
        <Stepper label={S.session.band}
          value={s.plan.band_tiers.find((b) => b.tier === live.band_tier)?.label || live.band_tier || '—'}
          onLess={() => update((x) => setBand(x, ex.index, stepBand(live.band_tier, -1, tiers) ?? ''))}
          onMore={() => update((x) => setBand(x, ex.index, stepBand(live.band_tier, 1, tiers) ?? ''))} />
      )}
      {ex.laterality === 'unilateral' && (showReps || showWeight) && (
        <SideRow ex={ex} title={S.session.side[other]} prefix={S.session.side[other]}
          values={sideValues(live, other)}
          onChange={(patch) => update((x) => setSide(x, ex.index, other, patch))} />
      )}
    </section>
  )
}

/** A test of the flexibility retest (WP-33): a value per side, typed here, with the
 *  setup number (the last one offered back) and the added load when the test takes one. */
function ReadingCard({ s, ex, update }: {
  s: TrainingState
  ex: Exercise
  update: (f: (s: TrainingState) => TrainingState) => void
}) {
  const spec = ex.reading
  if (!spec) return null
  const typed = s.readings[ex.index]
  const num = (v: string) => (v === '' ? null : Number(v))
  const text = (v: number | null | undefined) => (v == null ? '' : String(v))
  return (
    <section className="card group" data-testid="reading">
      <p className="caption">{spec.input_hint}</p>
      {spec.sides.map((side) => (
        <label key={side || 'one'} className="group">
          <span>{S.session.readingFor(side, spec.unit)}</span>
          <Field key={`reading-${ex.index}-${side}`} className="field" type="number" inputMode="decimal" min={0}
            initial={text(typed?.values[side])}
            onValue={(v) => update((x) => setReading(x, ex.index, { values: { [side]: num(v) } }))} />
        </label>
      ))}
      {spec.setup_input && (
        <label className="group">
          <span>{spec.setup_input}</span>
          <Field key={`setup-${ex.index}`} className="field" type="number" inputMode="decimal" min={0}
            initial={text(typed?.setup_value)}
            onValue={(v) => update((x) => setReading(x, ex.index, { setup_value: num(v) }))} />
        </label>
      )}
      {spec.takes_load && (
        <label className="group">
          <span>{S.session.readingLoad}</span>
          <Field key={`load-${ex.index}`} className="field" type="number" inputMode="decimal" min={0}
            initial={text(typed?.load_kg)}
            onValue={(v) => update((x) => setReading(x, ex.index, { load_kg: num(v) }))} />
        </label>
      )}
    </section>
  )
}

function nextText(s: TrainingState, offset: number): string | null {
  const st = s.plan.steps[s.step + offset]
  if (!st) return null
  const ex = exerciseOf(s, st)!
  if (st.phase === 'resting') return S.session.rest
  const current = currentStep(s)
  if (current && st.ex_idx !== current.ex_idx) return S.session.nextExercise(ex.name)
  const side = ex.laterality === 'unilateral' ? ` · ${S.session.side[st.side]}` : ''
  return `${S.session.setN(st.set_num)}${side}`
}

/** What Back's button says (WP-34): the entry it goes back to, or the order before a
 *  change of order. */
export function backLabel(s: TrainingState): string {
  const target = backTarget(s)
  if (!target) return S.session.back
  if (target.reordered) return S.session.backOrder
  const { step } = target
  const ex = exerciseOf(s, step)
  if (!ex) return S.session.back
  if (step.phase === 'resting') return S.session.backTo(S.session.backRest)
  if (step.ex_idx !== currentStep(s)?.ex_idx) return S.session.backTo(ex.name)
  const side = ex.laterality === 'unilateral' ? ` · ${S.session.side[step.side]}` : ''
  return S.session.backTo(`${S.session.setN(step.set_num)}${side}`)
}

export function SessionFlow({ s, update, onExit, onLeave }: {
  s: TrainingState
  update: (f: (s: TrainingState) => TrainingState) => void
  /** Leave and lose the session. */
  onExit: () => void
  /** Leave for now (WP-33): the session stays on the phone where it was. */
  onLeave?: () => void
}) {
  const step = currentStep(s)
  const ex = exerciseOf(s, step)
  const t = timerHere(s)
  const now = useNow(!!t && isRunning(t))
  const lastNow = useRef(now)
  // The countdown whose end was handled (a new start is a new object, so Back and a
  // restart ring again).
  const handled = useRef<Timer | null>(null)
  const held = useWakeLock(true)
  const [asking, setAsking] = useState<'exit' | 'skip' | 'busy' | null>(null)
  const [pulling, setPulling] = useState(false)
  const { ctx, alerts } = useApp()

  // The timer alerts (lib/alerts.ts): as the app goes to the background with a countdown
  // running, ask for an alert at its end; when the app comes back, cancel it.
  const latest = useRef(s)
  latest.current = s
  useEffect(() => {
    if (!alerts) return
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        const x = latest.current
        const running = timerHere(x)
        const alert = running ? alertFor(x, running) : null
        if (alert && alert.at > Date.now()) void scheduleAlert(ctx, alert)
      } else {
        void cancelAlert(ctx)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [alerts, ctx])

  /** Move the flow with `f` at the clock, starting the timer the next entry runs itself;
   *  `byTimer` when a timer that ran out moved it, not a tap. */
  const move = useCallback((f: (x: TrainingState, at: number) => TrainingState, byTimer = false) => {
    update((x) => {
      const at = Date.now()
      const moved = f(x, at)
      const next = moved.step !== x.step ? withTimer(moved, arrivalTimer(moved, at, byTimer)) : moved
      return finished(next) ? { ...next, saving: true, timer: null } : next
    })
  }, [update])

  // The ticks of the last three seconds, and the end of a countdown.
  useEffect(() => {
    const before = lastNow.current
    lastNow.current = now
    if (!t || !step || !ex) return
    if (isRunning(t)) for (const _ of ticksCrossed(t, before, now)) tick()
    // The slow start's end (WP-40): one tick as the hold itself begins.
    const leadMs = (ex.lead_in_seconds ?? 0) * 1000
    if (isRunning(t) && leadInLeftMs(t, leadMs, before) > 0 && leadInLeftMs(t, leadMs, now) === 0
      && now - before <= 1500) tick()
    if (!isRunning(t) || !hasEnded(t, now) || handled.current === t) return
    handled.current = t
    const endedAt = endsAt(t) ?? now
    if (document.visibilityState !== 'visible' || now - endedAt > 2000) return   // ended while hidden
    if (t.kind === 'rest') {
      restOver()
      window.setTimeout(() => move((x, at) => (x.step === s.step ? advance(x, at) : x), true), REST_AUTO_MS)
    } else if (t.kind === 'hold') {
      bell((step.ending ?? 'continue') as Ending)
      window.setTimeout(() => move((x, at) => (x.step === s.step ? advance(x, at) : x), true), HOLD_AUTO_MS)
    } else if (t.kind === 'duration') {
      bell('done')
    }
  }, [now, t, step, ex, s.step, move])

  if (!step || !ex) return null
  const first = s.plan.first_side as Side
  const resting = step.phase === 'resting'
  const side = (ex.laterality === 'unilateral' ? step.side : 'right') as Side
  const order = exerciseOrder(s)
  const n = order.length
  const candidates = !resting && !t ? doFirstCandidates(s) : []
  const swaps = !resting && !t ? swapCandidates(s) : []
  const ended = t && hasEnded(t, now)
  // A hold with a slow start (WP-40): its first seconds count the slow start down, then the
  // hold runs its own seconds; the bar fills over the hold only.
  const leadMs = t?.kind === 'hold' ? (ex.lead_in_seconds ?? 0) * 1000 : 0
  const leadLeft = t ? leadInLeftMs(t, leadMs, now) : 0
  const inLead = leadLeft > 0 && !ended
  const seconds = t ? (inLead ? Math.ceil(leadLeft / 1000) : shownSeconds(t, now)) : null
  const span = t ? t.lengthMs - leadMs : 0
  const fraction = t && span > 0 && !inLead ? Math.min(1, 1 - remainingMs(t, now) / span) : 0
  const word = resting ? S.session.rest : inLead ? S.session.leadIn : t?.kind === 'hold' ? S.session.hold : S.session.ready
  const live = s.live[ex.index]
  const typed = sideValues(live, side).seconds
  const isFirstSide = ex.laterality === 'unilateral' && step.side === first && step.record_set == null

  const doneLabel = resting ? S.session.nextSet
    : ex.reading ? S.session.readingDone
    : ex.type === 'duration' ? S.session.activityDone
      : ex.type === 'hold_reps' && step.record_set == null && !isFirstSide ? S.session.repDone(step.rep)
        : isFirstSide ? S.session.sideDone(step.side)
          : S.session.setDone(step.set_num)

  const start = (timer: Timer) => {
    unlockAudio()
    update((x) => withTimer(x, timer))
  }

  /** The main button. At the end of a walk or run the watch is asked for its minutes first
   *  (T75); with no answer in a few seconds the flow moves on and the save asks again. */
  const done = async () => {
    unlockAudio()
    if (ex.reading && !resting) {
      // After each test, the engine's early answer (WP-33): with a pattern, the tests left
      // cannot be interpreted and are skipped. No connection: every test runs.
      move((x, at) => advance(x, at))
      const readings = typedReadings(s)
      void api<{ pattern: string | null; label: string }>('/api/training/flexibility-check', {
        method: 'POST', key: ctx.key, engineDown: ctx.engineDown, day: s.plan.date, body: { readings },
      }).then((answer) => {
        if (answer.pattern) update((x) => skipRestOfRetest(x, S.session.retestAnswered(answer.label || answer.pattern!)))
      }, () => undefined)
      return
    }
    if (!(ex.garmin_pull && step.event === 'complete' && ex.garmin_window)) {
      move((x, at) => advance(x, at))
      return
    }
    const [low, high] = ex.garmin_window
    setPulling(true)
    let pull: GarminPull
    let notice: string
    try {
      const got = await api<{ minutes: number; detail: Record<string, unknown> | null }>(
        `/api/training/garmin/activity-minutes?planned_minutes=${ex.duration_minutes ?? 0}`,
        { key: ctx.key, engineDown: ctx.engineDown, day: s.plan.date, timeoutMs: GARMIN_WAIT_MS })
      pull = got.minutes > 0 ? { state: 'found', minutes: got.minutes, detail: got.detail } : { state: 'none' }
      notice = got.minutes > 0 ? S.session.garminPulled(got.minutes, ex.name) : S.session.garminNone(low, high)
    } catch (err) {
      const reachable = err instanceof ApiError && (err.kind === 'rejected' || err.kind === 'server')
      pull = reachable ? { state: 'none' } : { state: 'pending' }
      notice = reachable ? S.session.garminNone(low, high) : S.session.garminLater
    } finally {
      setPulling(false)
    }
    const index = ex.index
    move((x, at) => {
      const moved = advance(x, at)
      return { ...setGarmin(moved, index, pull, notice) }
    })
  }

  return (
    <div className={`screen train ${resting ? 'train--rest' : 'train--hold'}`} data-step={s.step}
      onPointerDown={() => {
        unlockAudio()
        reportAudioOnce((detail) => debugLog('audio', detail))
      }}>
      <div className="sky" aria-hidden="true" />
      <header className="topbar">
        <button className="iconbtn" onClick={() => setAsking('exit')} aria-label={S.session.exit}>
          <IconClose />
        </button>
        <div className="topbar__title">{S.session.exerciseOf(order.indexOf(ex.index) + 1, n)}</div>
        <span className="topbar__note">{held ? S.session.screenOn : ''}</span>
      </header>

      <SessionHeader s={s} />
      {s.notice && <p className="note" role="status" data-testid="notice">{s.notice}</p>}

      {asking === 'busy' && (
        <section className="card group" role="dialog" aria-label={S.session.inUse} data-testid="in-use">
          {swaps.length > 0 && <p>{S.session.swapAsk}</p>}
          {swaps.map((a) => (
            <button key={a.name} className="btn btn--glass btn--wide" onClick={() => {
              setAsking(null)
              update((x) => swapTo(x, a))
            }}>{S.session.swapFor(a.name)}</button>
          ))}
          {candidates.length > 0 && <p>{S.session.doFirstAsk}</p>}
          {candidates.map((c) => (
            <button key={c.group} className="btn btn--glass btn--wide" onClick={() => {
              setAsking(null)
              update((x) => doFirst(x, c.group))
            }}>{S.session.doFirst(c.exercise.name)}</button>
          ))}
          <button className="btn btn--primary btn--wide" onClick={() => setAsking(null)}>{S.session.keepOrder}</button>
        </section>
      )}

      {(asking === 'exit' || asking === 'skip') && (
        <section className="card group" role="alertdialog" aria-label={asking === 'exit' ? S.session.exit : S.session.skip}>
          <p>{asking === 'exit' ? S.session.exitAsk : S.session.skipAsk}</p>
          {asking === 'exit' && onLeave && (
            <button className="btn btn--glass btn--wide" data-testid="leave-for-now" onClick={() => {
              setAsking(null)
              onLeave()
            }}>{S.session.leaveForNow}</button>
          )}
          <div className="pair">
            <button className="btn btn--glass" onClick={() => setAsking(null)}>{S.session.keep}</button>
            <button className="btn btn--primary" onClick={() => {
              setAsking(null)
              if (asking === 'exit') onExit()
              else move((x) => skip(x))
            }}>{asking === 'exit' ? S.session.discard : S.session.skipYes}</button>
          </div>
        </section>
      )}

      <section className="card exercise">
        <h1 className="exercise__name">{ex.name}</h1>
        <p className="caption">{ex.prescription}</p>
        {ex.laterality === 'unilateral' && !resting && <span className="word">{S.session.side[step.side]}</span>}
        {ex.type === 'hold_reps' && !resting && <span className="caption">{S.session.repOf(step.rep, ex.reps_in_set ?? 1)}</span>}
        <Chips s={s} step={step} />
        {ex.warning && <p className="alert" data-testid="warning">{ex.warning}</p>}
      </section>

      {ex.garmin_pull && ex.garmin_window && !resting && (
        <p className="note" data-testid="garmin-activity">
          {S.session.garminActivity(ex.name, ex.garmin_window[0], ex.garmin_window[1])}
        </p>
      )}

      {(t || resting || (ex.timer && !ex.garmin_pull)) && (
        <div className="timer" role="timer" aria-live="off">
          <span className="timer__word">
            {ended && t?.kind === 'duration' ? S.session.timerDone : ended && t?.kind !== 'stopwatch' ? S.session.go : word}
          </span>
          <span className={`num timer__digits${t && isRunning(t) && LAST_MS[t.kind] != null
            && remainingMs(t, now) <= LAST_MS[t.kind] ? ' timer__digits--last' : ''}`}>
            {seconds != null ? clock(seconds) : ex.timer === 'duration' ? clock((ex.duration_minutes ?? 0) * 60) : clock(ex.hold_seconds ?? 0)}
          </span>
          {t && t.kind !== 'stopwatch' && (
            <div className="timer__bar" aria-hidden="true">
              <span className="timer__fill" style={{ width: `${(1 - fraction) * 100}%` }} />
            </div>
          )}
          {ended && t && endsAt(t) != null && now - endsAt(t)! > 2000 && (
            <span className="caption">{S.session.endedAt(time(endsAt(t)!))}</span>
          )}
          {leadMs > 0 && !inLead && !ended && <span className="caption" data-testid="let-go">{S.session.letGo}</span>}
        </div>
      )}

      {!resting && <Steppers s={s} step={step} ex={ex} update={update} />}
      {!resting && <ReadingCard s={s} ex={ex} update={update} />}
      {resting && <JustDone s={s} ex={ex} update={update} />}

      {ex.timer === 'stopwatch' && !resting && (
        <section className="card group">
          <label className="group">
            <span>{S.session.secondsHeld(ex.laterality === 'unilateral' ? step.side : '')}</span>
            <Field key={`seconds-${s.step}`} className="field" type="number" inputMode="numeric" min={0}
              initial={typed == null ? '' : String(typed)}
              onValue={(v) => update((x) => setSide(x, ex.index, side, { seconds: v === '' ? null : Number(v) }))} />
          </label>
        </section>
      )}

      <div className="controls">
        {s.history.length > 0 && (
          <button className="btn btn--glass btn--gym btn--back" data-testid="back"
            onClick={() => update((x) => { const b = back(x); return withTimer(b, arrivalTimer(b, Date.now(), false)) })}>
            {backLabel(s)}
          </button>
        )}
        {!t && ex.timer === 'hold' && !resting && (
          <button className="btn btn--glass btn--gym" onClick={() => start(startTimer('hold', holdLengthMs(ex), Date.now()))}>
            <IconPlay /> {S.session.startHold}
          </button>
        )}
        {!t && ex.timer === 'duration' && !ex.garmin_pull && !resting && (
          <button className="btn btn--glass btn--gym" onClick={() => start(startTimer('duration', (ex.duration_minutes ?? 0) * 60_000, Date.now()))}>
            <IconPlay /> {S.session.startTimer(ex.duration_minutes ?? 0)}
          </button>
        )}
        {!t && ex.timer === 'stopwatch' && !resting && (
          <button className="btn btn--glass btn--gym" onClick={() => start(startTimer('stopwatch', 0, Date.now()))}>
            <IconPlay /> {S.session.startWatch}
          </button>
        )}
        {t && !ended && t.kind !== 'stopwatch' && (
          isRunning(t)
            ? <button className="btn btn--glass btn--gym" onClick={() => update((x) => withTimer(x, pauseTimer(t, Date.now())))}><IconPause /> {S.session.pause}</button>
            : <button className="btn btn--glass btn--gym" onClick={() => update((x) => withTimer(x, resumeTimer(t, Date.now())))}><IconPlay /> {S.session.resume}</button>
        )}
        {t && !ended && t.kind === 'hold' && (
          <button className="btn btn--glass btn--gym" onClick={() => update((x) => withTimer(x, null))}>{S.session.reset}</button>
        )}
        {t && ended && t.kind === 'duration' && (
          <button className="btn btn--glass btn--gym"
            onClick={() => start(startTimer('duration', (ex.duration_minutes ?? 0) * 60_000, Date.now()))}>
            <IconPlay /> {S.session.again}
          </button>
        )}
        {t && t.kind === 'stopwatch' && (
          isRunning(t)
            ? <button className="btn btn--glass btn--gym" onClick={() => update((x) => withTimer(x, pauseTimer(t, Date.now())))}>{S.session.stopWatch}</button>
            : <button className="btn btn--glass btn--gym" onClick={() => update((x) => withTimer(x, null))}>{S.session.reset}</button>
        )}
        {resting && t && !ended && (
          <button className="btn btn--glass btn--gym" onClick={() => update((x) => withTimer(x, extendTimer(t, 15_000)))}>{S.session.plus15}</button>
        )}
        <button className="btn btn--primary btn--gym"
          disabled={pulling || (ex.timer === 'stopwatch' && !resting && typed == null)
            || (!!ex.reading && !resting && !readingComplete(s, ex))}
          onClick={() => void done()}>
          {pulling ? S.session.garminChecking : doneLabel}
        </button>
      </div>

      <section className="card next">
        <div className="eyebrow">{S.session.next}</div>
        <div className="next__main">{nextText(s, 1) ?? S.session.lastOne}</div>
        {nextText(s, 2) && <div className="next__then">{S.session.then} · {nextText(s, 2)}</div>}
      </section>

      {(ex.previous_caption || ex.entry_caption || ex.contradiction) && (
        <section className="card group" aria-label={S.session.numbers}>
          {ex.previous_caption && <p className="caption">{`${ex.previous_caption}${ex.delta ? ` · ${ex.delta}` : ''}`}</p>}
          {ex.entry_caption && <p className="caption">{ex.entry_caption}</p>}
          {typeof (ex.entry as Record<string, unknown> | null)?.next_step === 'string' && (ex.entry as Record<string, string>).next_step && (
            <p className="caption">{(ex.entry as Record<string, string>).next_step}</p>
          )}
          {ex.contradiction && <p className="caption">{ex.contradiction}</p>}
        </section>
      )}

      {ex.mechanics && (
        <details className="card guide">
          <summary className="tapline">{S.session.howTo}</summary>
          <p className="caption">{ex.mechanics}</p>
        </details>
      )}

      <label className="group">
        <span className="caption">{S.session.note}</span>
        <Field key={`note-${ex.index}`} className="field" type="text" initial={s.notes[ex.index] ?? ''}
          onValue={(v) => update((x) => setNote(x, ex.index, v))} />
      </label>

      <button className="btn btn--glass btn--wide" onClick={() => setAsking('skip')}>{S.session.skip}</button>
      {(candidates.length > 0 || swaps.length > 0) && (
        <button className="btn btn--glass btn--wide" onClick={() => setAsking('busy')}>{S.session.inUse}</button>
      )}
    </div>
  )
}
