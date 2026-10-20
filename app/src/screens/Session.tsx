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
import { bell, restOver, tick, unlockAudio, type Ending } from '../lib/sounds'
import {
  endsAt, extendTimer, hasEnded, isRunning, pauseTimer, remainingMs, resumeTimer, shownSeconds, startTimer,
  ticksCrossed, type Timer,
} from '../lib/timers'
import {
  advance, back, currentStep, exerciseOf, finished, setBand, setNote, setSide, sideValues, skip, stepBand,
  stepWeight, timerHere, withTimer, type Exercise, type FlowStep, type Side, type TrainingState,
} from '../lib/training'
import { S } from '../strings'
import { clock, useWakeLock } from '../ui/hooks'
import { IconCheck, IconClose, IconPause, IconPlay } from '../ui/icons'

const HOLD_AUTO_MS = 700
const REST_AUTO_MS = 900

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
  if (step.timer_starts === 'after_timer' && byTimer) return startTimer('hold', (ex.hold_seconds ?? 0) * 1000, now)
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

/** The reps, the weight and the band of the side the step is on. */
function Steppers({ s, step, ex, update }: {
  s: TrainingState
  step: FlowStep
  ex: Exercise
  update: (f: (s: TrainingState) => TrainingState) => void
}) {
  const first = s.plan.first_side as Side
  const side = (ex.laterality === 'unilateral' ? step.side : 'right') as Side
  const live = s.live[ex.index]
  const values = sideValues(live, side, first)
  const tiers = s.plan.band_tiers.map((b) => b.tier)
  const showReps = ex.type === 'reps' || ex.type === 'hold_reps' ? ex.reps_editable || !!ex.equipment_type : false
  const showWeight = !!ex.equipment_type && ex.equipment_type !== 'band'
  const showBand = ex.equipment_type === 'band'
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
          value={ex.increment_unit === 'kg' ? S.session.kg(values.weight_kg ?? 0) : String(values.weight_kg ?? 0)}
          onLess={() => update((x) => setSide(x, ex.index, side, { weight_kg: stepWeight(values.weight_kg, -1, ex.increment_size) }))}
          onMore={() => update((x) => setSide(x, ex.index, side, { weight_kg: stepWeight(values.weight_kg, 1, ex.increment_size) }))} />
      )}
      {showBand && (
        <Stepper label={S.session.band}
          value={s.plan.band_tiers.find((b) => b.tier === live.band_tier)?.label || live.band_tier || '—'}
          onLess={() => update((x) => setBand(x, ex.index, stepBand(live.band_tier, -1, tiers) ?? ''))}
          onMore={() => update((x) => setBand(x, ex.index, stepBand(live.band_tier, 1, tiers) ?? ''))} />
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

export function SessionFlow({ s, update, onExit }: {
  s: TrainingState
  update: (f: (s: TrainingState) => TrainingState) => void
  onExit: () => void
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
  const [asking, setAsking] = useState<'exit' | 'skip' | null>(null)

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
  const n = s.plan.exercises.length
  const ended = t && hasEnded(t, now)
  const seconds = t ? shownSeconds(t, now) : null
  const fraction = t && t.lengthMs ? Math.min(1, 1 - remainingMs(t, now) / t.lengthMs) : 0
  const word = resting ? S.session.rest : t?.kind === 'hold' ? S.session.hold : S.session.ready
  const live = s.live[ex.index]
  const typed = sideValues(live, side, first).seconds
  const isFirstSide = ex.laterality === 'unilateral' && step.side === first && step.record_set == null

  const doneLabel = resting ? S.session.nextSet
    : ex.type === 'duration' ? S.session.activityDone
      : ex.type === 'hold_reps' && step.record_set == null && !isFirstSide ? S.session.repDone(step.rep)
        : isFirstSide ? S.session.sideDone(step.side)
          : S.session.setDone(step.set_num)

  const start = (timer: Timer) => {
    unlockAudio()
    update((x) => withTimer(x, timer))
  }

  return (
    <div className={`screen train ${resting ? 'train--rest' : 'train--hold'}`} data-step={s.step}
      onPointerDown={() => unlockAudio()}>
      <div className="sky" aria-hidden="true" />
      <header className="topbar">
        <button className="iconbtn" onClick={() => setAsking('exit')} aria-label={S.session.exit}>
          <IconClose />
        </button>
        <div className="topbar__title">{S.session.exerciseOf(ex.index + 1, n)}</div>
        <span className="topbar__note">{held ? S.session.screenOn : ''}</span>
      </header>

      {asking && (
        <section className="card group" role="alertdialog" aria-label={asking === 'exit' ? S.session.exit : S.session.skip}>
          <p>{asking === 'exit' ? S.session.exitAsk : S.session.skipAsk}</p>
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

      {(t || resting || ex.timer) && (
        <div className="timer" role="timer" aria-live="off">
          <span className="timer__word">{ended && t?.kind !== 'stopwatch' ? S.session.go : word}</span>
          <span className="num timer__digits">
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
        </div>
      )}

      {!resting && <Steppers s={s} step={step} ex={ex} update={update} />}

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
        {!t && ex.timer === 'hold' && !resting && (
          <button className="btn btn--glass btn--gym" onClick={() => start(startTimer('hold', (ex.hold_seconds ?? 0) * 1000, Date.now()))}>
            <IconPlay /> {S.session.startHold}
          </button>
        )}
        {!t && ex.timer === 'duration' && !resting && (
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
        <button className="btn btn--primary btn--gym" disabled={ex.timer === 'stopwatch' && !resting && typed == null}
          onClick={() => { unlockAudio(); move((x, at) => advance(x, at)) }}>
          {doneLabel}
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

      <div className="pair">
        <button className="btn btn--glass" disabled={!s.history.length}
          onClick={() => update((x) => { const b = back(x); return withTimer(b, arrivalTimer(b, Date.now(), false)) })}>
          {S.session.back}
        </button>
        <button className="btn btn--glass" onClick={() => setAsking('skip')}>{S.session.skip}</button>
      </div>
    </div>
  )
}
