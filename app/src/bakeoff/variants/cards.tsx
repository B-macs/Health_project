// Style 3, Cards: each score on its own card with its last seven days as bars (the day
// shown in the strongest shade), the vitals as one card, and the session as a numbered
// list. The timer sits under a set tracker — which sides are done, which runs now — with
// a bar in place of a ring. Insights is a stack of cards with the weeks as bars.
import type { Day, Mock, Region } from '../../mock/generate'
import { S } from '../../strings'
import { clock } from '../hooks'
import { IconBack, IconCheck, IconClose, IconForward } from '../icons'
import { AreaChart, Contributor, DayBars, TrendBars, longDate, narrowDay } from '../parts'
import { ExerciseRows, useSwipe, type TodayProps } from '../Today'
import { Controls, phaseWord, useSession, type TrainingProps } from '../Training'

function ScoreCard(props: {
  name: string
  value: string
  label: string
  note: string
  week: number[]
  floor: number
  max: number
  selected: number
  days: string[]
}) {
  return (
    <article className="card scorecard">
      <div className="scorecard__top">
        <span className="scorecard__name">{props.name}</span>
        <span className="chip-status">{props.label}</span>
      </div>
      <div className="scorecard__body">
        <div className="scorecard__main">
          <span className="num scorecard__value">{props.value}</span>
          <span className="caption">{props.note}</span>
        </div>
        <TrendBars values={props.week} floor={props.floor} max={props.max} selected={props.selected}
          labels={props.days} label={`${props.name}, ${S.cards.lastSeven}`} />
      </div>
    </article>
  )
}

export function CardsToday(p: TodayProps) {
  const { readiness: r, sleep: s, strain: t } = p.day
  const days = p.mock.days.map((d: Day) => narrowDay(d.date))
  return (
    <div className={`screen today cards tone-${r.tone}`} {...useSwipe(p)}>
      <div className="sky" aria-hidden="true" />
      <header className="cards-head">
        <div>
          <h1 className="cards-head__title">{S.cards.title}</h1>
          <div className="caption">{longDate(p.day.date)}</div>
        </div>
        <div className="cards-head__arrows">
          <button className="iconbtn" onClick={p.onPrev} disabled={!p.canPrev} aria-label={S.today.previousDay}>
            <IconBack />
          </button>
          <button className="iconbtn" onClick={p.onNext} disabled={!p.canNext} aria-label={S.today.nextDay}>
            <IconForward />
          </button>
        </div>
      </header>

      <ScoreCard name={S.today.readiness} value={String(r.value)} label={r.label}
        note={S.today.readinessLine[r.tone]} week={p.mock.days.map((d) => d.readiness.value)}
        floor={30} max={100} selected={p.dayIndex} days={days} />
      <ScoreCard name={S.today.sleep} value={String(s.value)} label={s.label}
        note={S.today.asleep(s.minutes)} week={p.mock.days.map((d) => d.sleep.value)}
        floor={30} max={100} selected={p.dayIndex} days={days} />
      <ScoreCard name={S.today.strain} value={t.value.toFixed(1)} label={t.label}
        note={t.soFar ? S.today.soFar : S.today.outOf(21)} week={p.mock.days.map((d) => d.strain.value)}
        floor={0} max={21} selected={p.dayIndex} days={days} />

      <section className="card cards-vitals">
        <div className="cards-vital">
          <span className="caption">{S.today.hrv}</span>
          <span><span className="num cards-vital__value">{p.mock.hrv[p.mock.hrv.length - 1]}</span> <span className="unit">{S.today.ms}</span></span>
          <AreaChart values={p.mock.hrv} level={1} label={`${S.today.hrv}, ${S.today.sevenDays}`} className="area--mini" />
        </div>
        <div className="cards-vital">
          <span className="caption">{S.today.rhr}</span>
          <span><span className="num cards-vital__value">{p.mock.rhr[p.mock.rhr.length - 1]}</span> <span className="unit">{S.today.bpm}</span></span>
          <AreaChart values={p.mock.rhr} level={2} label={`${S.today.rhr}, ${S.today.sevenDays}`} className="area--mini" />
        </div>
      </section>

      <section className="card session">
        <div className="session__head">
          <div>
            <div className="eyebrow">{S.today.session}</div>
            <h2 className="session__title">{p.mock.session.title}</h2>
          </div>
          <div className="session__meta">
            {S.today.sessionMeta(p.mock.session.exercises.length, p.mock.session.minutes)}
          </div>
        </div>
        <ExerciseRows mock={p.mock} numbered />
        <button className="btn btn--primary btn--wide" onClick={p.onStart}>
          {S.today.start}
        </button>
      </section>
    </div>
  )
}

/** The exercise's sides as a row of chips: done, running now, still to do. Set 1 was
 *  done before the screen opened; the mock's steps are the rest. */
function SetTracker({ mock, index, finished }: { mock: Mock; index: number; finished: boolean }) {
  const holds = mock.guided.steps
    .map((step, i) => ({ step, i }))
    .filter(({ step }) => step.kind === 'hold')
  const before = [1].flatMap((set) => (['right', 'left'] as const).map((side) => ({ set, side, state: 'done' as const })))
  const after = holds.map(({ step, i }) => ({
    set: step.set,
    side: step.side ?? 'right',
    state: finished || i < index ? ('done' as const) : i === index ? ('now' as const) : ('todo' as const),
  }))
  return (
    <ol className="tracker">
      {[...before, ...after].map((c) => (
        <li key={`${c.set}-${c.side}`} className={`tracker__chip tracker__chip--${c.state}`}>
          <span className="tracker__set">{S.cards.set(c.set)}</span>
          <span className="tracker__side">
            {c.state === 'done' ? <IconCheck /> : S.cards.side[c.side]}
          </span>
        </li>
      ))}
    </ol>
  )
}

export function CardsTraining({ mock, onClose }: TrainingProps) {
  const s = useSession(mock)
  return (
    <div className={`screen train cards ${s.resting ? 'train--rest' : 'train--hold'}`}>
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

      <section className="card cards-ex">
        <h1 className="cards-ex__name">{s.ex.name}</h1>
        <SetTracker mock={mock} index={s.timer.index} finished={s.finished} />
      </section>

      <div className="cards-timer" role="timer" aria-live="off">
        <span className="cards-timer__word">{phaseWord(s.timer)}</span>
        <span className="num cards-timer__digits">{clock(s.seconds)}</span>
        <div className="progress" aria-hidden="true">
          <span className="progress__fill" style={{ width: `${(1 - s.timer.fraction) * 100}%` }} />
        </div>
      </div>

      <Controls timer={s.timer} />

      <section className="card next">
        <div className="eyebrow">{S.training.next}</div>
        <div className="next__main">{s.nextText}</div>
        {s.thenText && <div className="next__then">{S.training.then} · {s.thenText}</div>}
      </section>
    </div>
  )
}

function regionValue(r: Region): string {
  return r.value == null ? S.insights.none : String(r.value)
}

function regionNote(r: Region): string {
  if (r.value == null) return S.insights.noMeasure
  return r.learning ? S.insights.learning : ''
}

export function CardsInsights({ mock, reduced }: { mock: Mock; reduced: boolean }) {
  const st = mock.strength
  return (
    <div className="screen insights cards">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="cards-head">
        <h1 className="cards-head__title">{S.insights.title}</h1>
      </header>

      <article className="card scorecard">
        <div className="scorecard__top">
          <span className="scorecard__name">{S.insights.strength}</span>
          <span className="chip-status">{S.insights.change(st.change4w)}</span>
        </div>
        <div className="scorecard__main">
          <span className="num scorecard__value">{st.score.toFixed(1)}</span>
          <span className="caption">{S.insights.points}</span>
        </div>
        <TrendBars values={st.weekly} floor={Math.floor(Math.min(...st.weekly)) - 2} max={Math.max(...st.weekly)}
          selected={st.weekly.length - 1} label={`${S.insights.overall}, ${S.cards.lastTwelve}`} />
        <div className="caption">{S.cards.lastTwelve}</div>
      </article>

      <article className="card">
        <div className="eyebrow">{S.insights.byArea}</div>
        {st.regions.map((r) => (
          <Contributor key={r.key} name={S.insights.regions[r.key]} value={regionValue(r)}
            fraction={r.value == null ? null : r.value / 100} note={regionNote(r)} reduced={reduced} />
        ))}
      </article>

      <article className="card work-card">
        <div className="work__head">
          <span className="eyebrow">{S.insights.work}</span>
          <span className="num work__kg">{S.insights.workKg(st.workKg)}</span>
        </div>
        <DayBars values={st.workByDay} days={S.insights.days} label={S.insights.work} />
      </article>
      <p className="caption">{S.insights.scale}</p>
    </div>
  )
}
