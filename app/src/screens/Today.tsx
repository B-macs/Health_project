// Today (the owner's pick, 2026-10-20: Week), in the page's one colour family (teal), on the
// engine's numbers (rebuild Phase 5; inventory H6-H24): the week strip (a small readiness
// ring for each day; tap a day to open it), the readiness card with the engine's verdict
// under it on today, sleep and strain as two tiles, and the day's session. Arrows, the
// strip and a sideways swipe change the day; a past day shows "Back to today". A card opens
// its detail screen. A status is a word; the light at the top is dimmer on a morning the
// engine marks with a warning (fair) or an error (low).
//
// Every figure, word and sentence is the engine's (GET /api/today, /api/today/week and
// /api/training/day), read cache-first: the last answer shows at once.
import { useEffect } from 'react'
import type { components } from '../generated/api'
import { localDay } from '../lib/api'
import { useApp } from '../lib/appState'
import { useCached, type View } from '../lib/cache'
import { dayPath } from '../lib/day'
import { S } from '../strings'
import { Freshness } from '../ui/Freshness'
import { useSwipe } from '../ui/hooks'
import { IconBack, IconForward } from '../ui/icons'
import { Ring, dayOfMonth, longDate, narrowDay } from '../ui/parts'

type Schemas = components['schemas']
type TodayAnswer = Schemas['TodayOut']
type WeekAnswer = Schemas['TodayWeekOut']
type DayPlan = Schemas['TrainingDayOut']
type Status = Schemas['StatusOut']

/** The light at the top follows the engine's verdict on today (presentation only). */
export function tone(today: TodayAnswer | undefined): 'good' | 'fair' | 'low' {
  const kind = today?.verdict?.banner_kind ?? ''
  return kind === 'error' ? 'low' : kind === 'warning' ? 'fair' : 'good'
}

/** The verdict's lines under today's card, in the Home page's order: the reading the
 *  engine named, the banner, the HRV note (H14). */
export function verdictLines(verdict: Schemas['VerdictOut'] | null | undefined): string[] {
  if (!verdict) return []
  const lines = verdict.has_something_to_say ? [verdict.cause, verdict.banner_text] : []
  return [...lines, verdict.hrv_note].filter((line) => line && line.trim())
}


function WeekStrip({ week, reduced }: { week: WeekAnswer; reduced: boolean }) {
  const { showDay } = useApp()
  return (
    <nav className="weekstrip" aria-label={S.today.strip}>
      {week.days.map((d) => (
        <button key={d.date} className={`weekstrip__day${d.selected ? ' weekstrip__day--on' : ''}`}
          aria-current={d.selected ? 'date' : undefined} onClick={() => showDay(d.is_today ? null : d.date)}>
          <span className="weekstrip__letter">{narrowDay(d.date)}</span>
          <Ring className="ring--day" fraction={(d.readiness ?? 0) / 100} reduced={reduced}
            label={S.today.dayRing(longDate(d.date), d.readiness == null ? null : Math.round(d.readiness), d.label)}>
            <span className="num weekstrip__date">{dayOfMonth(d.date)}</span>
          </Ring>
        </button>
      ))}
    </nav>
  )
}

function Plan({ plan }: { plan: DayPlan }) {
  const { go } = useApp()
  const o = plan.overview
  if (plan.route === 'today' && o?.screen === 'overview' && o.card) {
    return (
      <section className="card plan" aria-label={S.today.plan}>
        <div className="plan__head">
          <div>
            <div className="eyebrow">{S.today.plan}</div>
            <h2 className="plan__title">{o.headline ?? o.phase_name}</h2>
          </div>
          <div className="plan__meta">{S.today.sessionMeta(o.card.exercise_count, o.card.minutes)}</div>
        </div>
        {o.subtitle && <p className="caption">{o.subtitle}</p>}
        <ol className="timeline">
          {o.main.map((ex) => (
            <li key={ex.name} className="timeline__item">
              <span className="timeline__dot" aria-hidden="true" />
              <span className="timeline__name">{ex.name}</span>
              <span className="timeline__dose">{ex.prescription}</span>
            </li>
          ))}
        </ol>
        <button className="btn btn--primary btn--wide" onClick={() => go('/training/day')}>{S.today.start}</button>
      </section>
    )
  }
  const line =
    plan.route === 'rest' ? S.today.rest
      : plan.route === 'past_completed' || o?.screen === 'logged' ? S.today.done(plan.logged?.minutes ?? null)
        : plan.route === 'past_missed' ? S.today.missed
          : plan.route === 'no_phase' || plan.route === 'phases_unreadable' ? S.today.noPlan
            : o?.screen === 'not_started' ? S.today.notStarted
              : o?.screen === 'complete' ? S.today.blockDone
                : S.today.noPlan
  const names = plan.logged?.exercises.map((e) => e.name) ?? plan.planned?.exercises.map((e) => e.name) ?? []
  return (
    <section className="card plan" aria-label={S.today.plan}>
      <div className="eyebrow">{S.today.plan}</div>
      <p className="plan__title">{line}</p>
      {plan.rest?.yoga_suggestion && (
        <p className="caption">{S.today.yoga(plan.rest.yoga_suggestion.name, plan.rest.yoga_suggestion.minutes)}</p>
      )}
      {names.length > 0 && <p className="caption">{names.join(' · ')}</p>}
      {plan.note?.text && <p className="caption">{plan.note.text}</p>}
    </section>
  )
}

/** The plan Home shows: only the plan of the day on the header (2026-10-22: the day
 *  before's saved "Rest day" stood under Thursday's date while the engine answered). */
export function planForDay(plan: DayPlan | undefined, shownDay: string): DayPlan | undefined {
  return plan?.date === shownDay ? plan : undefined
}

export function Today() {
  const { store, ctx, pick, showDay } = useApp()
  // With no day picked the addresses answer for today: a copy saved on an earlier day is
  // not shown (lib/cache.ts ReadOptions), so the day shown is never the day before's.
  const view = useCached<TodayAnswer>(store, dayPath('/api/today', pick), null, ctx, { today: !pick })
  const week = useCached<WeekAnswer>(store, dayPath('/api/today/week', pick), null, ctx, { today: !pick })
  const shownDay = view.data?.date ?? pick?.day ?? localDay()
  const planToday = shownDay === localDay()
  const plan = useCached<DayPlan>(store, planToday ? '/api/training/day' : `/api/training/day?date=${shownDay}`, null, ctx,
    { today: planToday })
  // The engine opened another day than the one picked (a pick lasts the day it was made
  // on): follow the engine.
  const answered = view.data?.date
  const answeredToday = view.data?.is_today
  useEffect(() => {
    if (answered && pick && answered !== pick.day) showDay(answeredToday ? null : answered)
  }, [answered, answeredToday, pick, showDay])
  const status = useCached<Status>(store, '/api/status', null, ctx)
  return <TodayView view={view} week={week.data} plan={planForDay(plan.data, shownDay)} shownDay={shownDay}
    notices={status.data?.notices ?? []} />
}

/** The engine's sync notices (H21-H24): a dead Oura login is an alert, a failed step a caption. */
function Notices({ notices }: { notices: readonly Schemas['Notice'][] }) {
  return (
    <>
      {notices.map((n) => (
        <p key={n.code} className={n.level === 'error' ? 'alert' : 'caption'} role={n.level === 'error' ? 'alert' : undefined}>
          {S.today.notices[n.code] ?? n.code}
        </p>
      ))}
    </>
  )
}

export function TodayView({ view, week, plan, shownDay, notices = [] }: {
  view: View<TodayAnswer>
  week: WeekAnswer | undefined
  plan: DayPlan | undefined
  shownDay: string
  notices?: readonly Schemas['Notice'][]
}) {
  const { showDay, go, reduced } = useApp()
  const t = view.data
  const prev = t ? () => showDay(t.previous) : null
  const next = t?.next ? () => showDay(t.next === localDay() ? null : t.next) : null
  const swipe = useSwipe(prev, next)
  const lines = verdictLines(t?.verdict)
  return (
    <div className={`screen today tone-${tone(t)}`} {...swipe}>
      <div className="sky" aria-hidden="true" />
      <header className="head">
        <h1 className="head__title">{S.today.title}</h1>
        <div className="dayarrows">
          <button className="iconbtn" aria-label={S.detail.previous} disabled={!prev} onClick={() => prev?.()}>
            <IconBack />
          </button>
          <span className="dayarrows__label">{longDate(shownDay)}</span>
          <button className="iconbtn" aria-label={S.detail.next} disabled={!next} onClick={() => next?.()}>
            <IconForward />
          </button>
        </div>
      </header>
      {t && !t.is_today && (
        <button className="btn btn--glass pill" onClick={() => showDay(null)}>{S.today.backToToday}</button>
      )}
      <Freshness view={view} />
      {t?.bio_failed && <p className="caption" role="alert">{S.today.bioFailed}</p>}
      <Notices notices={notices} />

      {week && <WeekStrip week={week} reduced={reduced} />}

      <button className="card ready" onClick={() => go('/readiness')} aria-label={S.today.openReadiness}>
        <Ring className="ring--ready" fraction={(t?.readiness.headline ?? 0) / 100} reduced={reduced}
          label={S.today.readinessRing(t?.readiness.headline == null ? null : Math.round(t.readiness.headline), t?.readiness.label ?? '')}>
          <span className="num ready__value">{t?.readiness.headline == null ? S.none : Math.round(t.readiness.headline)}</span>
        </Ring>
        <span className="ready__text">
          <span className="eyebrow">{S.today.readiness}</span>
          <span className="word">{t?.readiness.label ?? S.none}</span>
          <span className="ready__line">{t?.readiness.header ?? ''}</span>
          {t && <span className="caption">{t.readiness.pair.map((p) => `${S.today.pairTitle(p.title)} ${p.value}`).join(' · ')}</span>}
        </span>
      </button>

      {t?.verdict && (t.verdict.badge || lines.length > 0) && (
        <section className="verdict" aria-label={S.today.verdict} data-testid="verdict">
          {t.verdict.badge && <span className="badge">{t.verdict.badge}</span>}
          {lines.map((line) => <p key={line} className="caption">{line}</p>)}
        </section>
      )}

      <section className="pair">
        <button className="card tile" onClick={() => go('/sleep')} aria-label={S.today.openSleep}>
          <span className="eyebrow">{S.today.sleep}</span>
          <span className="num tile__value">{t?.sleep.display ?? S.none}</span>
          <span className="word">{t?.sleep.label ?? S.none}</span>
          <span className="caption">{t?.sleep.header ?? ''}</span>
        </button>
        <button className="card tile" onClick={() => go('/strain')} aria-label={S.today.openStrain}>
          <span className="eyebrow">{t ? S.today.strainLabel(t.strain.card_label) : S.today.strain}</span>
          <span className="num tile__value">{t?.strain.display ?? S.none}</span>
          <span className="word">{t?.strain.label ?? S.none}</span>
          <span className="caption">{t?.strain.header ?? ''}</span>
          {t?.strain.rest_day && t.strain.seven_day != null && (
            <span className="caption" data-testid="strain-7d">{S.today.sevenDay(t.strain.seven_day.toFixed(1))}</span>
          )}
        </button>
      </section>

      {plan && <Plan plan={plan} />}
    </div>
  )
}
