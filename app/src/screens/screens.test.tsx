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
import { Freshness } from '../ui/Freshness'
import { CheckInForm, checkinStage, type Sending } from './CheckIn'
import { TrainingTiles } from './Daily'
import { ReadinessBody, SleepBody, StrainBody } from './Details'
import { TodayView, planForDay, tone, verdictLines } from './Today'

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

  it('a rest day says so, with the 7 days before on their own line', () => {
    const rest = { ...answer, strain: { ...answer.strain, value: 0, display: '0.0', label: 'Rest', rest_day: true, seven_day: 12.1 } }
    const html = text(draw(<TodayView view={fresh(rest)} week={week} plan={plan} shownDay={LOCAL} />))
    expect(html).toContain('Rest')
    expect(html).toContain(S.today.sevenDay('12.1'))
    expect(text(draw(<TodayView view={fresh(answer)} week={week} plan={plan} shownDay={LOCAL} />))).not.toContain(S.today.sevenDay('12.1'))
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

  it('strain: the card says how the number was measured, and lists no exercise without a body area', () => {
    const base = fx.strainDetail(LOCAL, LOCAL, false)
    const d = {
      ...base,
      region: base.region && { ...base.region, unmapped_names: ['Made-up pose'] },
      source: { kind: 'hr', label: 'Made-up method', hr_rows: [{ label: 'Average heart rate', value: '119 bpm' }],
        blend: { hr_strain: 16.4, rpe_strain: 16.2, hr_weight_pct: 70 } },
    }
    const html = text(draw(<DetailFrame heading={S.detail.strain} view={fresh(d)}>{(x) => <StrainBody d={x} onWeek={() => undefined} />}</DetailFrame>))
    expect(html).toContain(S.detail.source)
    expect(html).toContain('Average heart rate')
    expect(html).toContain(S.detail.blend(70, 16.4, 16.2))
    expect(html).not.toContain('Made-up pose')
  })

  it('strain: a body-area panel with no split says why in words, never its code', () => {
    const base = fx.strainDetail(LOCAL, LOCAL, false)
    const d = { ...base, region: base.region && { ...base.region, state: 'empty', reason: 'rest_day' } }
    const html = text(draw(<DetailFrame heading={S.detail.strain} view={fresh(d)}>{(x) => <StrainBody d={x} onWeek={() => undefined} />}</DetailFrame>))
    expect(html).toContain(S.detail.regionReason.rest_day!)
    expect(html).not.toContain('rest_day')
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

  // The owner, 2026-10-21: "completing" where Save was pressed, then "completed", then the
  // day marked as done with a button for another check-in.
  it('a save in progress turns Save into "Saving…" with the turning ring, and turns the fields off', () => {
    const raw = draw(<CheckInForm form={fx.checkinForm(LOCAL, LOCAL, undefined)} stage="saving" onSaved={() => undefined} />)
    expect(text(raw)).toContain(S.checkin.saving)
    expect(text(raw)).not.toContain(S.checkin.save)
    expect(raw).toContain('data-testid="spinner"')
    expect(raw).toMatch(/<fieldset class="checkin__fields" disabled/)
    expect(raw).toMatch(/<button type="submit"[^>]* disabled/)
  })

  it('the engine has it: "Check-in complete" stands where Save was', () => {
    const html = text(draw(<CheckInForm form={fx.checkinForm(LOCAL, LOCAL, undefined)} stage="complete" onSaved={() => undefined} />))
    expect(html).toContain(S.checkin.complete)
    expect(html).not.toContain(S.checkin.save)
  })

  it('a refused save says why and offers Save again', () => {
    const html = text(draw(<CheckInForm form={fx.checkinForm(LOCAL, LOCAL, undefined)} refused="invalid_checkin" onSaved={() => undefined} />))
    expect(html).toContain(S.checkin.refused('invalid_checkin'))
    expect(html).toContain(S.checkin.save)
  })
})

describe('the check-in sheet\'s stage', () => {
  const stage = (sentId: string | null, sending: Sending | null, existing = false, editing = false, shownComplete = false) =>
    checkinStage({ sentId, sending, existing, editing, shownComplete })

  it('a day not saved yet opens on the form; a stored day, or one still on the phone, opens as done', () => {
    expect(stage(null, null)).toBe('form')
    expect(stage(null, null, true)).toBe('done')
    expect(stage(null, { state: 'waiting' })).toBe('done')
    expect(stage(null, null, true, true)).toBe('form')
    expect(stage(null, { state: 'refused', code: 'x' }, true)).toBe('form')
  })

  it('a save goes saving, then complete where Save was, then done', () => {
    // Pressed, its id not known yet: the new item on the phone must not read as the day done.
    expect(checkinStage({ pressing: true, sentId: null, sending: { state: 'sending' }, existing: false, editing: false, shownComplete: false }))
      .toBe('saving')
    expect(stage('id', null)).toBe('saving')
    expect(stage('id', { state: 'sending' })).toBe('saving')
    expect(stage('id', { state: 'done' })).toBe('complete')
    expect(stage('id', { state: 'done' }, false, false, true)).toBe('done')
  })

  it('a save that has to wait shows the day as done at once; a refused one goes back to the form', () => {
    expect(stage('id', { state: 'waiting' })).toBe('done')
    expect(stage('id', { state: 'refused', code: 'x' })).toBe('form')
  })
})

describe('the freshness line while the engine is asked', () => {
  it('turns a ring for a read asked for by a tap, and beside "Loading…" with nothing saved', () => {
    // The screen's own check is quiet: the saved answer stays as it is (2026-10-21).
    const quiet = draw(<Freshness view={cached({})} />)
    expect(quiet).not.toContain('data-testid="spinner"')
    expect(text(quiet)).not.toContain(S.fresh.reading)
    const raw = draw(<Freshness view={{ ...cached({}), pressed: true }} />)
    expect(text(raw)).toContain(S.fresh.reading)
    expect(raw).toContain('data-testid="spinner"')
    const empty = draw(<Freshness view={{ data: undefined, fetchedAt: null, state: 'loading' }} />)
    expect(text(empty)).toContain(S.fresh.loading)
    expect(empty).toContain('data-testid="spinner"')
    const answered = draw(<Freshness view={fresh({})} />)
    expect(answered).not.toContain('data-testid="spinner"')
    expect(text(answered)).not.toContain(S.fresh.reading)
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

// 2026-10-22: the day before's saved "Rest day" stood under Thursday's date on Home while the
// engine answered.
describe("Home's plan card", () => {
  it('shows only the plan of the day on the header', () => {
    const plan = { date: '2026-10-21', route: 'rest' } as Parameters<typeof planForDay>[0]
    expect(planForDay(plan, '2026-10-22')).toBeUndefined()
    expect(planForDay(plan, '2026-10-21')).toBe(plan)
    expect(planForDay(undefined, '2026-10-22')).toBeUndefined()
  })
})

describe("Training's two tiles", () => {
  // The owner, 2026-10-28: "Keep all the rest of the data on the training page just put the
  // two title right and left of each other".
  it('sit in one row of two, the training day marked as the page they are on', () => {
    const html = draw(<TrainingTiles onTrainingDay={() => undefined} />)
    expect(html).toMatch(/<div class="pair tiles" data-testid="training-tiles">/)
    expect((html.match(/class="card tile tile--button"/g) ?? []).length).toBe(2)
    expect(html.indexOf('tile-training-day')).toBeLessThan(html.indexOf('tile-daily'))
    expect(html).toMatch(/data-testid="tile-training-day" aria-current="page"/)
    expect(html).not.toMatch(/data-testid="tile-daily" aria-current/)
    expect(text(html)).toContain(S.daily.trainingDay)
    expect(text(html)).toContain(S.daily.dailyTitle)
  })
})
