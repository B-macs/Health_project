// The guided training screen in the middle of a set (the owner's pick, 2026-10-20:
// Cards), in the page's one colour family (amber): the exercise on a card with its set
// tracker — which sides are done, which runs now, which are still to do — then large
// light timer digits over a bar, the controls, and the next set below. What to do, the
// numbers and the timer only: no "why" panel (Key Rule 20), no machine units, and the
// screen stays on while it is open.
import type { Exercise, Mock, Step } from '../mock/generate'
import { S } from '../strings'
import { clock, useHoldTimer, useWakeLock, type HoldTimer } from '../ui/hooks'
import { IconCheck, IconClose, IconPause, IconPlay } from '../ui/icons'

export type TrainingProps = { mock: Mock; onClose: () => void }

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

/** The exercise's sides as a row of chips: done, running now, still to do. Set 1 was
 *  done before the screen opened; the mock's steps are the rest. */
function SetTracker({ mock, index, finished }: { mock: Mock; index: number; finished: boolean }) {
  const before = (['right', 'left'] as const).map((side) => ({ set: 1, side, state: 'done' as const }))
  const after = mock.guided.steps
    .map((step, i) => ({ step, i }))
    .filter(({ step }) => step.kind === 'hold')
    .map(({ step, i }) => ({
      set: step.set,
      side: step.side ?? 'right',
      state: finished || i < index ? ('done' as const) : i === index ? ('now' as const) : ('todo' as const),
    }))
  return (
    <ol className="tracker">
      {[...before, ...after].map((c) => (
        <li key={`${c.set}-${c.side}`} className={`tracker__chip tracker__chip--${c.state}`}>
          <span className="tracker__set">{S.training.set(c.set)}</span>
          <span className="tracker__side">{c.state === 'done' ? <IconCheck /> : S.training.sideShort[c.side]}</span>
        </li>
      ))}
    </ol>
  )
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

export function Training({ mock, onClose }: TrainingProps) {
  const timer = useHoldTimer(mock.guided.steps, mock.guided.elapsedSeconds)
  const held = useWakeLock(true)
  const ex = mock.session.exercises[mock.guided.exerciseIndex]
  const finished = timer.phase === 'finished'
  const resting = timer.step?.kind === 'rest' && !finished
  const seconds = finished ? 0 : timer.remaining
  const [next, then] = mock.guided.steps.slice(timer.index + 1, timer.index + 3)
  return (
    <div className={`screen train ${resting ? 'train--rest' : 'train--hold'}`}>
      <div className="sky" aria-hidden="true" />
      <header className="topbar">
        <button className="iconbtn" onClick={onClose} aria-label={S.training.close}>
          <IconClose />
        </button>
        <div className="topbar__title">
          {S.training.exerciseOf(mock.guided.exerciseIndex + 1, mock.session.exercises.length)}
        </div>
        <span className="topbar__note">{held ? S.training.screenOn : ''}</span>
      </header>

      <section className="card exercise">
        <h1 className="exercise__name">{ex.name}</h1>
        <SetTracker mock={mock} index={timer.index} finished={finished} />
      </section>

      <div className="timer" role="timer" aria-live="off">
        <span className="timer__word">{phaseWord(timer)}</span>
        <span className="num timer__digits">{clock(seconds)}</span>
        <div className="timer__bar" aria-hidden="true">
          <span className="timer__fill" style={{ width: `${(1 - timer.fraction) * 100}%` }} />
        </div>
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
      <p className="note">{S.sample}</p>
    </div>
  )
}
