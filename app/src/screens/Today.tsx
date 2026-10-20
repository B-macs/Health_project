// Today (the owner's pick, 2026-10-20: Week), in the page's one colour family (teal):
// a week strip on top (a small readiness ring for each day; tap a day to open it), the
// readiness tile with its sentence, sleep and strain as two tiles, and the session as a
// timeline with its Start button. A horizontal swipe changes the day too. A status is a
// word; the light at the top is dimmer on a morning that needs care.
import { useRef, type TouchEvent } from 'react'
import type { Day, Exercise, Mock } from '../mock/generate'
import { S } from '../strings'
import { Ring, dayOfMonth, longDate, narrowDay } from '../ui/parts'

export type TodayProps = {
  day: Day
  dayIndex: number
  mock: Mock
  canPrev: boolean
  canNext: boolean
  onPrev: () => void
  onNext: () => void
  onDay: (index: number) => void
  onStart: () => void
  reduced: boolean
}

export function dose(ex: Exercise): string {
  const base = ex.holdSeconds != null ? S.dose.hold(ex.sets, ex.holdSeconds) : S.dose.reps(ex.sets, ex.reps ?? 0)
  return ex.eachSide ? `${base} ${S.dose.eachSide}` : base
}

/** A horizontal swipe changes the day, as the week strip does. */
function useSwipe(p: TodayProps) {
  const start = useRef<number | null>(null)
  return {
    onTouchStart: (e: TouchEvent) => {
      start.current = e.touches[0]?.clientX ?? null
    },
    onTouchEnd: (e: TouchEvent) => {
      const from = start.current
      const to = e.changedTouches[0]?.clientX
      start.current = null
      if (from == null || to == null || Math.abs(to - from) < 60) return
      if (to > from && p.canPrev) p.onPrev()
      if (to < from && p.canNext) p.onNext()
    },
  }
}

export function Today(p: TodayProps) {
  const { readiness: r, sleep: s, strain: t } = p.day
  return (
    <div className={`screen today tone-${r.tone}`} {...useSwipe(p)}>
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.today.title}</h1>
        <div className="caption">{longDate(p.day.date)}</div>
      </header>
      <p className="note">{S.sample}</p>

      <nav className="weekstrip" aria-label={S.today.strip}>
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

      <section className="card ready">
        <Ring className="ring--ready" fraction={r.value / 100} reduced={p.reduced}
          label={`${S.today.readiness} ${r.value}, ${r.label}`}>
          <span className="num ready__value">{r.value}</span>
        </Ring>
        <div className="ready__text">
          <span className="eyebrow">{S.today.readiness}</span>
          <span className="word">{r.label}</span>
          <span className="ready__line">{S.today.readinessLine[r.tone]}</span>
        </div>
      </section>

      <section className="pair">
        <article className="card tile">
          <span className="eyebrow">{S.today.sleep}</span>
          <span className="num tile__value">{s.value}</span>
          <span className="word">{s.label}</span>
          <span className="caption">{S.today.asleep(s.minutes)}</span>
        </article>
        <article className="card tile">
          <span className="eyebrow">{S.today.strain}</span>
          <span className="num tile__value">{t.value.toFixed(1)}</span>
          <span className="word">{t.label}</span>
          <span className="caption">{t.soFar ? S.today.soFar : S.today.outOf(21)}</span>
        </article>
      </section>

      <section className="card plan">
        <div className="plan__head">
          <div>
            <div className="eyebrow">{S.today.plan}</div>
            <h2 className="plan__title">{p.mock.session.title}</h2>
          </div>
          <div className="plan__meta">
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
