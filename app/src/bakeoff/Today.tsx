// Today, Oura-style, in the page's one colour family (teal): the three scores as rings,
// one sentence about the day, the vitals, and today's session with its button. Two
// layouts: "trio" (three equal rings in a row, styles 1, 3 and 4) and "hero" (one large
// readiness ring with a halo and two small cards, style 2). A status is a word; the
// light at the top is dimmer on a morning that needs care.
import { useRef, type TouchEvent } from 'react'
import type { Day, Exercise, Mock } from '../mock/generate'
import { S } from '../strings'
import { IconBack, IconForward } from './icons'
import { AreaChart, Ring, greetingKey, longDate } from './parts'

export type TodayProps = {
  layout: 'trio' | 'hero'
  day: Day
  mock: Mock
  canPrev: boolean
  canNext: boolean
  onPrev: () => void
  onNext: () => void
  onStart: () => void
  reduced: boolean
}

export function dose(ex: Exercise): string {
  const base = ex.holdSeconds != null ? S.dose.hold(ex.sets, ex.holdSeconds) : S.dose.reps(ex.sets, ex.reps ?? 0)
  return ex.eachSide ? `${base} ${S.dose.eachSide}` : base
}

/** A horizontal swipe changes the day, as the arrows do. */
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

function TopBar(p: TodayProps) {
  return (
    <header className="topbar">
      <button className="iconbtn" onClick={p.onPrev} disabled={!p.canPrev} aria-label={S.today.previousDay}>
        <IconBack />
      </button>
      <div className="topbar__title">
        <div className="greeting">{S.greeting[greetingKey(new Date().getHours())]}</div>
        <div className="topbar__date">{longDate(p.day.date)}</div>
      </div>
      <button className="iconbtn" onClick={p.onNext} disabled={!p.canNext} aria-label={S.today.nextDay}>
        <IconForward />
      </button>
    </header>
  )
}

function Status({ name, label, main }: { name: string; label: string; main?: boolean }) {
  return (
    <span className={`status${main ? ' status--main' : ''}`}>
      <span className="status__dot" />
      {name} · {label}
    </span>
  )
}

function Bubbles({ day, reduced }: { day: Day; reduced: boolean }) {
  const { readiness: r, sleep: s, strain: t } = day
  return (
    <section className="bubbles">
      <figure className="bubble">
        <Ring className="ring--bubble" fraction={r.value / 100} reduced={reduced}
          label={`${S.today.readiness} ${r.value}, ${r.label}`}>
          <span className="num bubble__value">{r.value}</span>
        </Ring>
        <figcaption className="bubble__name">{S.today.readiness}</figcaption>
      </figure>
      <figure className="bubble">
        <Ring className="ring--bubble" fraction={s.value / 100} reduced={reduced}
          label={`${S.today.sleep} ${s.value}, ${s.label}`}>
          <span className="num bubble__value">{s.value}</span>
        </Ring>
        <figcaption className="bubble__name">{S.today.sleep}</figcaption>
      </figure>
      <figure className="bubble">
        <Ring className="ring--bubble" fraction={t.value / 21} reduced={reduced}
          label={`${S.today.strain} ${t.value}, ${t.label}`}>
          <span className="num bubble__value">{t.value.toFixed(1)}</span>
        </Ring>
        <figcaption className="bubble__name">{S.today.strain}</figcaption>
      </figure>
    </section>
  )
}

function Insight({ day }: { day: Day }) {
  const { readiness: r, sleep: s, strain: t } = day
  return (
    <section className="card insight">
      <Status name={S.today.readiness} label={r.label} main />
      <p className="insight__line">{S.today.readinessLine[r.tone]}</p>
      <div className="insight__meta">
        <Status name={S.today.sleep} label={s.label} />
        <Status name={S.today.strain} label={t.label} />
      </div>
    </section>
  )
}

/** Style 2: one large readiness ring with its halo, then sleep and strain as two cards. */
function Hero({ day, reduced }: { day: Day; reduced: boolean }) {
  const { readiness: r, sleep: s, strain: t } = day
  return (
    <>
      <section className="hero">
        <div className="hero__halo" aria-hidden="true" />
        <Ring className="ring--hero" fraction={r.value / 100} reduced={reduced}
          label={`${S.today.readiness} ${r.value}, ${r.label}`}>
          <span className="num hero__value">{r.value}</span>
          <span className="hero__word">{r.label}</span>
        </Ring>
        <div className="hero__name">{S.today.readiness}</div>
        <p className="hero__line">{S.today.readinessLine[r.tone]}</p>
      </section>
      <section className="pair">
        <article className="card mini">
          <Ring className="ring--mini" fraction={s.value / 100} reduced={reduced}
            label={`${S.today.sleep} ${s.value}, ${s.label}`}>
            <span className="num mini__value">{s.value}</span>
          </Ring>
          <div className="mini__text">
            <span className="mini__name">{S.today.sleep}</span>
            <span className="mini__word">{s.label}</span>
            <span className="mini__note">{S.today.asleep(s.minutes)}</span>
          </div>
        </article>
        <article className="card mini">
          <Ring className="ring--mini" fraction={t.value / 21} reduced={reduced}
            label={`${S.today.strain} ${t.value}, ${t.label}`}>
            <span className="num mini__value">{t.value.toFixed(1)}</span>
          </Ring>
          <div className="mini__text">
            <span className="mini__name">{S.today.strain}</span>
            <span className="mini__word">{t.label}</span>
            <span className="mini__note">{t.soFar ? S.today.soFar : S.today.outOf(21)}</span>
          </div>
        </article>
      </section>
    </>
  )
}

export function Today(p: TodayProps) {
  const { readiness: r, sleep: s } = p.day
  const hrv = p.mock.hrv[p.mock.hrv.length - 1]
  const rhr = p.mock.rhr[p.mock.rhr.length - 1]
  return (
    <div className={`screen today tone-${r.tone}`} {...useSwipe(p)}>
      <div className="sky" aria-hidden="true" />
      <TopBar {...p} />

      {p.layout === 'hero' ? (
        <Hero day={p.day} reduced={p.reduced} />
      ) : (
        <>
          <Bubbles day={p.day} reduced={p.reduced} />
          <Insight day={p.day} />
        </>
      )}

      <section className="section">
        <h2 className="section__title">{S.today.vitals}</h2>
        <div className="tiles">
          <div className="card tile">
            <span className="tile__name">{S.today.hrv}</span>
            <span className="tile__value">
              <span className="num">{hrv}</span> <span className="unit">{S.today.ms}</span>
            </span>
            <AreaChart values={p.mock.hrv} level={1} label={`${S.today.hrv}, ${S.today.sevenDays}`} className="area--mini" />
          </div>
          <div className="card tile">
            <span className="tile__name">{S.today.rhrShort}</span>
            <span className="tile__value">
              <span className="num">{rhr}</span> <span className="unit">{S.today.bpm}</span>
            </span>
            <AreaChart values={p.mock.rhr} level={2} label={`${S.today.rhr}, ${S.today.sevenDays}`} className="area--mini" />
          </div>
          <div className="card tile">
            <span className="tile__name">{S.today.sleep}</span>
            <span className="tile__value">
              <span className="num">{S.today.sleepClock(s.minutes)}</span>
            </span>
            <span className="tile__note">{S.today.lastNight}</span>
          </div>
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
        <ol className="rows">
          {p.mock.session.exercises.map((ex) => (
            <li key={ex.name} className="row">
              <span className="row__name">
                {ex.name}
                {ex.warmup && <span className="tag">{S.today.warmup}</span>}
              </span>
              <span className="row__dose">
                <span>{dose(ex)}</span>
                {ex.weightKg != null && <span className="row__kg">{S.dose.kg(ex.weightKg)}</span>}
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
