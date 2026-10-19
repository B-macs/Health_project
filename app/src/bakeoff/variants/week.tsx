// Style 4, Week: a week strip on top (a small readiness ring for each day; tap a day to
// open it), the readiness tile with its sentence, sleep and strain as two tiles, and the
// session as a timeline. The training screen puts a smaller timer above the list of the
// exercise's sets, with the one that runs now lit. Insights opens with two number tiles.
import type { Mock, Region } from '../../mock/generate'
import { S } from '../../strings'
import { clock } from '../hooks'
import { IconCheck, IconClose } from '../icons'
import { AreaChart, Contributor, DayBars, Ring, dayOfMonth, longDate, narrowDay } from '../parts'
import { dose, useSwipe, type TodayProps } from '../Today'
import { Controls, phaseWord, stepText, useSession, type TrainingProps } from '../Training'

export function WeekToday(p: TodayProps) {
  const { readiness: r, sleep: s, strain: t } = p.day
  return (
    <div className={`screen today week tone-${r.tone}`} {...useSwipe(p)}>
      <div className="sky" aria-hidden="true" />
      <header className="week-head">
        <h1 className="week-head__title">{S.week.title}</h1>
        <div className="caption">{longDate(p.day.date)}</div>
      </header>

      <nav className="weekstrip" aria-label={S.week.strip}>
        {p.mock.days.map((d, i) => (
          <button key={d.date} className={`weekstrip__day${i === p.dayIndex ? ' weekstrip__day--on' : ''}`}
            aria-current={i === p.dayIndex ? 'date' : undefined} onClick={() => p.onDay(i)}>
            <span className="weekstrip__letter">{narrowDay(d.date)}</span>
            <Ring className="ring--day" fraction={d.readiness.value / 100} reduced={p.reduced}
              label={`${longDate(d.date)}, ${S.today.readiness} ${d.readiness.value}`}>
              <span className="num weekstrip__date">{dayOfMonth(d.date)}</span>
            </Ring>
          </button>
        ))}
      </nav>

      <section className="card week-ready">
        <Ring className="ring--ready" fraction={r.value / 100} reduced={p.reduced}
          label={`${S.today.readiness} ${r.value}, ${r.label}`}>
          <span className="num week-ready__value">{r.value}</span>
        </Ring>
        <div className="week-ready__text">
          <span className="eyebrow">{S.today.readiness}</span>
          <span className="week-ready__word">{r.label}</span>
          <span className="week-ready__line">{S.today.readinessLine[r.tone]}</span>
        </div>
      </section>

      <section className="pair">
        <article className="card week-tile">
          <span className="eyebrow">{S.today.sleep}</span>
          <span className="num week-tile__value">{s.value}</span>
          <span className="week-tile__word">{s.label}</span>
          <span className="caption">{S.today.asleep(s.minutes)}</span>
        </article>
        <article className="card week-tile">
          <span className="eyebrow">{S.today.strain}</span>
          <span className="num week-tile__value">{t.value.toFixed(1)}</span>
          <span className="week-tile__word">{t.label}</span>
          <span className="caption">{t.soFar ? S.today.soFar : S.today.outOf(21)}</span>
        </article>
      </section>

      <section className="card week-plan">
        <div className="session__head">
          <div>
            <div className="eyebrow">{S.week.plan}</div>
            <h2 className="session__title">{p.mock.session.title}</h2>
          </div>
          <div className="session__meta">
            {S.today.sessionMeta(p.mock.session.exercises.length, p.mock.session.minutes)}
          </div>
        </div>
        <ol className="timeline">
          {p.mock.session.exercises.map((ex) => (
            <li key={ex.name} className={`timeline__item${ex.warmup ? ' timeline__item--warmup' : ''}`}>
              <span className="timeline__dot" aria-hidden="true" />
              <span className="timeline__name">{ex.name}</span>
              <span className="timeline__dose">
                {dose(ex)}
                {ex.weightKg != null && ` · ${S.dose.kg(ex.weightKg)}`}
              </span>
            </li>
          ))}
        </ol>
        <button className="btn btn--primary btn--wide" onClick={p.onStart}>
          {S.today.start}
        </button>
      </section>
    </div>
  )
}

export function WeekTraining({ mock, onClose, reduced }: TrainingProps) {
  const s = useSession(mock)
  const { timer } = s
  // Set 1 was done before the screen opened; the mock's steps are the rest.
  const done = [1].flatMap((set) => (['right', 'left'] as const).map((side) => ({ set, side })))
  return (
    <div className={`screen train week ${s.resting ? 'train--rest' : 'train--hold'}`}>
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

      <div className="week-timer">
        <Ring shade={s.resting ? 'rest' : 'main'} className="ring--weektimer" head fraction={1 - timer.fraction}
          reduced={reduced} label={`${phaseWord(timer)} ${clock(s.seconds)}`}>
          <span className="num week-timer__digits">{clock(s.seconds)}</span>
          <span className="timer__word">{phaseWord(timer)}</span>
        </Ring>
        <div className="week-timer__text">
          <h1 className="week-timer__name">{s.ex.name}</h1>
          <span className="caption">{S.week.sets}</span>
        </div>
      </div>

      <ol className="steps">
        {done.map((d) => (
          <li key={`${d.set}-${d.side}`} className="steps__row steps__row--done">
            <IconCheck />
            <span>{`${S.training.setOf(d.set, s.ex.sets)} · ${S.training.side[d.side]}`}</span>
            <span className="steps__time">{S.week.done}</span>
          </li>
        ))}
        {mock.guided.steps.map((step, i) => {
          const state = s.finished || i < timer.index ? 'done' : i === timer.index ? 'now' : 'todo'
          return (
            <li key={i} className={`steps__row steps__row--${state}`}>
              {state === 'done' ? <IconCheck /> : <span className="steps__dot" aria-hidden="true" />}
              <span>{stepText(step, s.ex)}</span>
              <span className="steps__time num">
                {state === 'now' ? clock(s.seconds) : state === 'done' ? S.week.done : clock(step.seconds)}
              </span>
            </li>
          )
        })}
      </ol>

      <Controls timer={timer} />
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

export function WeekInsights({ mock, reduced }: { mock: Mock; reduced: boolean }) {
  const st = mock.strength
  return (
    <div className="screen insights week">
      <div className="sky sky--quiet" aria-hidden="true" />
      <header className="week-head">
        <h1 className="week-head__title">{S.insights.title}</h1>
      </header>

      <section className="pair">
        <article className="card week-tile">
          <span className="eyebrow">{S.insights.strength}</span>
          <span className="num week-tile__value">{st.score.toFixed(1)}</span>
          <span className="week-tile__word">{S.insights.change(st.change4w)}</span>
          <span className="caption">{S.insights.points}</span>
        </article>
        <article className="card week-tile">
          <span className="eyebrow">{S.insights.work}</span>
          <span className="num week-tile__value week-tile__value--long">{S.insights.workKg(st.workKg)}</span>
          <DayBars values={st.workByDay} days={S.insights.days} label={S.insights.work} />
        </article>
      </section>

      <section className="card">
        <div className="eyebrow">{S.insights.weeks}</div>
        <AreaChart values={st.weekly} level={1} label={`${S.insights.overall}, ${S.insights.weeks}`} className="area--wide" />
      </section>

      <section className="card">
        <div className="eyebrow">{S.insights.byArea}</div>
        {st.regions.map((r) => (
          <Contributor key={r.key} name={S.insights.regions[r.key]} value={regionValue(r)}
            fraction={r.value == null ? null : r.value / 100} note={regionNote(r)} reduced={reduced} />
        ))}
      </section>
      <p className="caption">{S.insights.scale}</p>
    </div>
  )
}
