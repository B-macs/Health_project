// The guided training screen in the middle of a set, Oura-style, in the page's one
// colour family (amber): one thin glowing ring around large light digits, in the bright
// shades while you hold and the faintest while you rest, and the next set below. What to do, the numbers and the timer only:
// no "why" panel (Key Rule 20), no machine units, and the screen stays on.
import type { Exercise, Mock, Step } from '../mock/generate'
import { S } from '../strings'
import { clock, useHoldTimer, useWakeLock, type HoldTimer } from './hooks'
import { IconClose, IconPause, IconPlay } from './icons'
import { Ring } from './parts'

type Props = { mock: Mock; onClose: () => void; reduced: boolean }

function stepText(step: Step, ex: Exercise): string {
  if (step.kind === 'rest') return S.training.restFor(step.seconds)
  const side = step.side ? ` · ${S.training.side[step.side]}` : ''
  return `${S.training.setOf(step.set, ex.sets)}${side} · ${S.training.holdFor(step.seconds)}`
}

function phaseWord(timer: HoldTimer): string {
  if (timer.phase === 'finished') return S.training.exerciseDone
  if (timer.phase === 'ready') return S.training.ready
  return timer.step?.kind === 'rest' ? S.training.rest : S.training.hold
}

function Controls({ timer }: { timer: HoldTimer }) {
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

export function Training({ mock, onClose, reduced }: Props) {
  const timer = useHoldTimer(mock.guided.steps, mock.guided.elapsedSeconds)
  const held = useWakeLock(true)
  const ex = mock.session.exercises[mock.guided.exerciseIndex]
  const finished = timer.phase === 'finished'
  const resting = timer.step?.kind === 'rest' && !finished
  const seconds = finished ? 0 : timer.remaining
  const [next, then] = mock.guided.steps.slice(timer.index + 1, timer.index + 3)
  const step = timer.step

  return (
    <div className={`screen train ${resting ? 'train--rest' : 'train--hold'}`}>
      <div className="sky sky--train" aria-hidden="true" />

      <header className="topbar">
        <button className="iconbtn" onClick={onClose} aria-label={S.training.close}>
          <IconClose />
        </button>
        <div className="topbar__title">
          <div className="topbar__date">
            {S.training.exerciseOf(mock.guided.exerciseIndex + 1, mock.session.exercises.length)}
          </div>
        </div>
        <span className="topbar__note">{held ? S.training.screenOn : ''}</span>
      </header>

      <div className="train__title">
        <h1 className="train__name">{ex.name}</h1>
        <div className="train__meta">
          {step && !finished ? (
            <>
              <span>{S.training.setOf(step.set, ex.sets)}</span>
              {step.side && <span className="train__side">{S.training.side[step.side]}</span>}
            </>
          ) : (
            <span>{S.training.exerciseDone}</span>
          )}
        </div>
      </div>

      <div className="train__ring">
        <Ring shade={resting ? 'rest' : 'main'} className="ring--timer" head fraction={1 - timer.fraction}
          reduced={reduced} label={`${phaseWord(timer)} ${clock(seconds)}`}>
          <span className="num timer__digits">{clock(seconds)}</span>
          <span className="timer__word">{phaseWord(timer)}</span>
        </Ring>
      </div>

      <Controls timer={timer} />

      <section className="card next">
        <div className="eyebrow">{S.training.next}</div>
        <div className="next__main">
          {finished || !next ? S.training.nextExercise(mock.guided.nextExercise) : stepText(next, ex)}
        </div>
        {!finished && then && (
          <div className="next__then">
            {S.training.then} · {stepText(then, ex)}
          </div>
        )}
      </section>
    </div>
  )
}
