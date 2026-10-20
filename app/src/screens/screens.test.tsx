// Each screen in each state (rebuild Phase 5): from the cache (the saved answer, the engine
// still asked), refreshed (the engine answered), no score (the Sleep screen's
// all-or-nothing rule), and the engine down (with and without a saved answer). The
// screens are drawn to HTML without a browser (react-dom/server) from the mock's made-up
// answers, which are typed against the engine's contract.
import type { ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import * as fx from '../../dev/fixtures'
import { HealthDB } from '../db/schema'
import { AppStateProvider, type AppState } from '../lib/appState'
import type { View } from '../lib/cache'
import { S } from '../strings'
import { MovementStrip } from '../ui/charts'
import { DetailFrame } from '../ui/detail'
import { CheckInForm } from './CheckIn'
import { ReadinessBody, SleepBody, StrainBody } from './Details'
import { TodayView, tone, verdictLines } from './Today'

const LOCAL = '2026-10-20'
const SAVED_AT = '2026-10-20T05:00:00Z'

function state(): AppState {
  return {
    store: new HealthDB(`screens-${Math.random()}`),
    ctx: { key: 'k', engineDown: false },
    reduced: true,
    pick: null,
    showDay: () => undefined,
    go: () => undefined,
  }
}

const draw = (node: ReactNode) => renderToStaticMarkup(<AppStateProvider value={state()}>{node}</AppStateProvider>)
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/\s+/g, ' ')

const cached = <T,>(data: T): View<T> => ({ data, fetchedAt: SAVED_AT, state: 'loading' })
const fresh = <T,>(data: T): View<T> => ({ data, fetchedAt: SAVED_AT, state: 'fresh' })
const down = <T,>(data: T): View<T> => ({ data, fetchedAt: SAVED_AT, state: 'engine_unavailable' })
const nothing = <T,>(): View<T> => ({ data: undefined, fetchedAt: null, state: 'engine_unavailable' })

/** The first day on or before LOCAL that the mock scores, or does not score. */
function dayWhere(scored: boolean): string {
  for (let i = 0; i < 10; i++) {
    const day = fx.addDays(LOCAL, -i)
    if (fx.unscored(day) !== scored) return day
  }
  throw new Error('no such day in the mock')
}

describe('Today', () => {
  const answer = fx.today(LOCAL, LOCAL)
  const week = fx.week(LOCAL, LOCAL)
  const plan = fx.trainingDay(LOCAL, LOCAL)
  const figure = String(Math.round(answer.readiness.headline!))

  it.each([
    ['from the cache', cached(answer)],
    ['refreshed', fresh(answer)],
  ])('%s: the three scores, the week and the plan', (_name, view) => {
    const html = text(draw(<TodayView view={view} week={week} plan={plan} shownDay={LOCAL} />))
    expect(html).toContain(figure)
    expect(html).toContain(answer.sleep.display)
    expect(html).toContain(answer.strain.display)
    expect(html).toContain(S.today.start)
    expect(html).not.toContain(S.fresh.saved)
  })

  it('with the engine down, the saved answer stays and says why', () => {
    const html = text(draw(<TodayView view={down(answer)} week={week} plan={plan} shownDay={LOCAL} />))
    expect(html).toContain(figure)
    expect(html).toContain(S.fresh.saved)
    expect(html).toContain(S.fresh.why.engine_unavailable)
  })

  it('with the engine down and nothing saved, the frame still shows, with the reason', () => {
    const html = text(draw(<TodayView view={nothing()} week={undefined} plan={undefined} shownDay={LOCAL} />))
    expect(html).toContain(S.today.title)
    expect(html).toContain(S.today.readiness)
    expect(html).toContain(S.fresh.nothingSaved)
  })

  it('a past day offers the way back to today', () => {
    const past = fx.addDays(LOCAL, -2)
    const html = text(draw(<TodayView view={fresh(fx.today(past, LOCAL))} week={fx.week(past, LOCAL)} plan={fx.trainingDay(past, LOCAL)} shownDay={past} />))
    expect(html).toContain(S.today.backToToday)
  })

  it('the badge, a failed read and the sync notices show, each in its own words', () => {
    const marked = { ...answer, bio_failed: true, verdict: { ...answer.verdict!, badge: 'REDUCED LOAD' } }
    const notices = [{ level: 'error', code: 'oura_unauthorised' }, { level: 'caption', code: 'garmin_unavailable' }]
    const html = text(draw(<TodayView view={fresh(marked)} week={week} plan={plan} shownDay={LOCAL} notices={notices} />))
    expect(html).toContain('REDUCED LOAD')
    expect(html).toContain(S.today.bioFailed)
    expect(html).toContain(S.today.notices.oura_unauthorised)
    expect(html).toContain(S.today.notices.garmin_unavailable)
  })

  it("the verdict's lines keep the Home page's order and drop empty ones", () => {
    const verdict = { ...answer.verdict!, has_something_to_say: true, cause: 'cause', banner_text: 'banner', hrv_note: 'hrv' }
    expect(verdictLines(verdict)).toEqual(['cause', 'banner', 'hrv'])
    expect(verdictLines({ ...verdict, has_something_to_say: false })).toEqual(['hrv'])
    expect(verdictLines(null)).toEqual([])
  })

  it('the light at the top follows the engine verdict', () => {
    const withKind = (banner_kind: string) => ({ ...answer, verdict: { ...answer.verdict!, banner_kind } })
    expect([tone(withKind('')), tone(withKind('warning')), tone(withKind('error')), tone(undefined)])
      .toEqual(['good', 'fair', 'low', 'good'])
  })
})

describe('the Sleep screen', () => {
  const sleepHtml = (view: View<ReturnType<typeof fx.sleepDetail>>) =>
    draw(<DetailFrame heading={S.detail.sleep} view={view}>{(d) => <SleepBody d={d} onSaved={() => undefined} />}</DetailFrame>)
  const sleep = (view: View<ReturnType<typeof fx.sleepDetail>>) => text(sleepHtml(view))

  it('a scored night: every panel and the wake-time correction', () => {
    const html = sleep(fresh(fx.sleepDetail(dayWhere(true), LOCAL)))
    expect(html).toContain(S.detail.contributors)
    expect(html).toContain(S.detail.debt)
    expect(html).toContain('Wake time')
  })

  it('no score: the reason line and the day arrows, no night panel and no correction', () => {
    const d = fx.sleepDetail(dayWhere(false), LOCAL)
    const html = sleep(fresh(d))
    expect(html).toContain(d.contributors.unscored_reason)
    expect(sleepHtml(fresh(d))).toContain(`aria-label="${S.detail.previous}"`)
    for (const panel of [S.detail.contributors, S.detail.debt, S.detail.vitals, 'Wake time']) {
      expect(html).not.toContain(panel)
    }
  })

  it('with the engine down, the saved night stays and says why', () => {
    const html = sleep(down(fx.sleepDetail(dayWhere(true), LOCAL)))
    expect(html).toContain(S.fresh.saved)
    expect(html).toContain(S.detail.contributors)
  })

  it('from the cache, the saved night shows before the engine answers', () => {
    expect(sleep(cached(fx.sleepDetail(dayWhere(true), LOCAL)))).toContain(S.detail.contributors)
  })
})

describe('the Readiness and Strain screens', () => {
  it.each([['refreshed', fresh], ['engine down', down]] as const)('readiness %s', (_name, make) => {
    const d = fx.readinessDetail(LOCAL, LOCAL)
    const html = text(draw(<DetailFrame heading={S.detail.readiness} view={make(d)}>{(x) => <ReadinessBody d={x} />}</DetailFrame>))
    expect(html).toContain(d.masthead.display)
    expect(html).toContain(S.detail.contributors)
  })

  it.each([['refreshed', fresh], ['engine down', down]] as const)('strain %s', (_name, make) => {
    const d = fx.strainDetail(LOCAL, LOCAL, false)
    const html = text(draw(<DetailFrame heading={S.detail.strain} view={make(d)}>{(x) => <StrainBody d={x} onWeek={() => undefined} />}</DetailFrame>))
    expect(html).toContain(d.masthead.display)
    expect(html).toContain('Lower body')
    expect(html).toContain(S.detail.showWeek)
  })

  it('with nothing saved and the engine down, a detail screen says why', () => {
    const html = draw(<DetailFrame heading={S.detail.strain} view={nothing<ReturnType<typeof fx.strainDetail>>()}>{() => null}</DetailFrame>)
    expect(text(html)).toContain(S.fresh.nothingSaved)
    expect(html).toContain(`aria-label="${S.detail.back}"`)
  })
})

describe('the check-in form', () => {
  it('draws every field from the engine answer', () => {
    const html = text(draw(<CheckInForm form={fx.checkinForm(LOCAL, LOCAL, undefined)} onSaved={() => undefined} />))
    for (const field of Object.values(S.checkin.fields)) expect(html).toContain(field.label)
    expect(html).toContain(S.checkin.save)
    expect(html).not.toContain(S.checkin.existing)
  })

  it('a day with a stored entry opens with it and says the save replaces it', () => {
    const stored = { ...fx.checkinForm(LOCAL, LOCAL, undefined).values, pain_score: 4 }
    const html = text(draw(<CheckInForm form={fx.checkinForm(LOCAL, LOCAL, stored)} onSaved={() => undefined} />))
    expect(html).toContain(S.checkin.existing)
  })
})

describe('the movement strip', () => {
  it('draws the four strengths as bars and leaves an unmeasured slot blank', () => {
    const strip = {
      title: 'Movement', codes: '1234000', details: [],
      runs: [
        { start: 0, end: 1, code: '1', name: 'No motion' }, { start: 1, end: 2, code: '2', name: 'Restless' },
        { start: 2, end: 3, code: '3', name: 'Tossing' }, { start: 3, end: 4, code: '4', name: 'Active' },
        { start: 4, end: 7, code: '0', name: '' },
      ],
      bands: [],
    }
    const html = draw(<MovementStrip strip={strip} />)
    for (const level of ['1', '2', '3', '4']) expect(html).toContain(`move move--${level}`)
    expect(html).not.toContain('move--0')
  })
})
