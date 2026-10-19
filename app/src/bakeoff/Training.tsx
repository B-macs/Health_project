// The guided training screen in the middle of a set, style 1 (Glow), in the page's one
// colour family (amber): one thin glowing ring around large light digits, in the bright
// shades while you hold and the faintest while you rest, and the next set below. What
// to do, the numbers and the timer only: no "why" panel (Key Rule 20), no machine units,
// and the screen stays on. The variations (variants/) share the session state and the
// controls exported here.
import type { Exercise, Mock, Step } from '../mock/generate'
import { S } from '../strings'
import { clock, useHoldTimer, useWakeLock, type HoldTimer } from './hooks'
import { IconClose, IconPause, IconPlay } from './icons'
import { Ring } from './parts'

export type TrainingProps = { mock: Mock; onClose: () => void; reduced: boolean }

export function stepText(step: Step, ex: Exercise): string {
  if (step.kind === 'rest') return S.training.restFor(step.seconds)
  const side = step.side ? ` · ${S.training.side[step.side]}` : ''
  return `${S.training.setOf(step.set, ex.sets)}${side} · ${S.training.holdFor(step.seconds)}`
}

export function phaseWord(timer: HoldTimer): string {
  if (timer.phase === 'finished') return S.training.exerciseDone
  if (timer.phase === 'ready') return S.training.ready
  return timer.step?.kind === 'rest' ? S.training.rest : S.training.hold
}

/** Everything a training screen shows, from the mock session and the running timer. */
export function useSession(mock: Mock) {
  const timer = useHoldTimer(mock.guided.steps, mock.guided.elapsedSeconds)
  const held = useWakeLock(true)
  const ex = mock.session.exercises[mock.guided.exerciseIndex]
  const finished = timer.phase === 'finished'
  const resting = timer.step?.kind === 'rest' && !finished
  const seconds = finished ? 0 : timer.remaining
  const [next, then] = mock.guided.steps.slice(timer.index + 1, timer.index + 3)
  const nextText = finished || !next ? S.training.nextExercise(mock.guided.nextExercise) : stepText(next, ex)
  const thenText = !finished && then ? stepText(then, ex) : null
  const counter = S.training.exerciseOf(mock.guided.exerciseIndex + 1, mock.session.exercises.length)
  return { timer, held, ex, finished, resting, seconds, nextText, thenText, counter, step: timer.step }
}

export function Controls({ timer }: { timer: HoldTimer }) {
  if (timer.phase === 'finished') {
    return (
      <div className="controls">
        <button className="btn btn--glass btn--gym btn--wide" onClick={timer.restart}>{S.training.again}</button>
      </div>
    )
  }
  if (timer.phase === 'ready') {
    const side = timer.step?.side
    return (
      <div className="controls">
        <button className="btn btn--primary btn--gym btn--wide" onClick={timer.start}>
          {side ? S.training.startSide(side) : S.training.startSet}
        </button>
      </div>
    )
  }
  const resting = timer.step?.kind === 'rest'
  const pause =
    timer.phase === 'paused' ? (
      <button className="btn btn--glass btn--gym" onClick={timer.resume}>
        <IconPlay /> {S.training.resume}
      </button>
    ) : (
      <button className="btn btn--glass btn--gym" onClick={timer.pause}>
        <IconPause /> {S.training.pause}
      </button>
    )
  if (resting) {
    return (
      <div className="controls">
        {pause}
        <button className="btn btn--glass btn--gym" onClick={() => timer.extend(15)}>{S.training.plus15}</button>
        <button className="btn btn--primary btn--gym" onClick={timer.finishStep}>{S.training.skip}</button>
      </div>
    )
  }
  return (
    <div className="controls">
      {pause}
      <button className="btn btn--primary btn--gym" onClick={timer.finishStep}>{S.training.done}</button>
    </div>
  )
}

export function Training({ mock, onClose, reduced }: TrainingProps) {
  const s = useSession(mock)
  return (
    <div className={`screen train ${s.resting ? 'train--rest' : 'train--hold'}`}>
      <div className="sky" aria-hidden="true" />

      <header className="topbar">
        <button className="iconbtn" onClick={onClose} aria-label={S.training.close}>
          <IconClose />
        </button>
        <div className="topbar__title">
          <div className="topbar__date">{s.counter}</div>
        </div>
        <span className="topbar__note">{s.held ? S.training.screenOn : ''}</span>
      </header>

      <div className="train__title">
        <h1 className="train__name">{s.ex.name}</h1>
        <div className="train__meta">
          {s.step && !s.finished ? (
            <>
              <span>{S.training.setOf(s.step.set, s.ex.sets)}</span>
              {s.step.side && <span className="train__side">{S.training.side[s.step.side]}</span>}
            </>
          ) : (
            <span>{S.training.exerciseDone}</span>
          )}
        </div>
      </div>

      <div className="train__ring">
        <Ring shade={s.resting ? 'rest' : 'main'} className="ring--timer" head fraction={1 - s.timer.fraction}
          reduced={reduced} label={`${phaseWord(s.timer)} ${clock(s.seconds)}`}>
          <span className="num timer__digits">{clock(s.seconds)}</span>
          <span className="timer__word">{phaseWord(s.timer)}</span>
        </Ring>
      </div>

      <Controls timer={s.timer} />

      <section className="card next">
        <div className="eyebrow">{S.training.next}</div>
        <div className="next__main">{s.nextText}</div>
        {s.thenText && (
          <div className="next__then">
            {S.training.then} · {s.thenText}
          </div>
        )}
      </section>
    </div>
  )
}
