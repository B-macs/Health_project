// The session screens (rebuild Phase 6), over the session the engine's own walk made
// (dev/session_fixture.json): the timer an entry starts by itself is the engine's mark,
// read and never decided here; a warning shows only on an exercise the engine sent one
// for (Key Rule 20; the gate's warning_shown_when_not_due counts these renders); the
// weight label never names machine units; and the save goes out through the outbox with
// the ids minted at Start, so a save sent again after a lost answer is the same save.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import fixture from '../../dev/session_fixture.json'
import { HealthDB } from '../db/schema'
import { AppStateProvider } from '../lib/appState'
import { drain, enqueue } from '../lib/outbox'
import {
  advance, doFirst, finished, saveBody, setGarmin, setSide, skip, startSessionState, type HeartRate, type Plan,
  type TrainingState,
} from '../lib/training'
import { S } from '../strings'
import { arrivalTimer, backLabel, SessionFlow } from './Session'
import { HeartRateMatch, reviewLine, SessionSave } from './SessionSave'
import { Banner, longDate, noSessionLine, noSessionReason, TrainedToday, trainedToday } from './TrainingTab'
import * as fx from '../../dev/fixtures'

const plan = fixture as unknown as Plan
const T0 = Date.parse('2026-10-20T08:00:00Z')

function at(step: number): TrainingState {
  return { ...startSessionState(plan, '2026-10-20-0a1b2c3d', plan.exercises.map((_, i) => `ex-${i}`)), step }
}

const firstEntry = (exIdx: number) => plan.steps.findIndex((st) => st.ex_idx === exIdx)

function provide(node: React.ReactNode): string {
  const app = {
    store: new HealthDB(`session-render-${Math.random()}`), ctx: { key: 'k', engineDown: false },
    reduced: true, pick: null, showDay: () => undefined, go: () => undefined,
  }
  return renderToStaticMarkup(<AppStateProvider value={app}>{node}</AppStateProvider>)
}

function render(s: TrainingState): string {
  return provide(<SessionFlow s={s} update={() => undefined} onExit={() => undefined} />)
}

const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/\s+/g, ' ')

function walked(s: TrainingState): TrainingState {
  let t = T0
  while (!finished(s)) {
    s = advance(s, t)
    t += 30_000
  }
  return s
}

describe('the timer an entry starts by itself', () => {
  it('a rest starts on any arrival, for the exercise\'s rest', () => {
    const rests = plan.steps.filter((st) => st.phase === 'resting')
    expect(rests.length).toBeGreaterThan(0)
    for (const st of rests) {
      expect(st.timer_starts).toBe('on_arrival')
      for (const byTimer of [false, true]) {
        const t = arrivalTimer(at(st.index), T0, byTimer)
        expect(t?.kind).toBe('rest')
        expect(t?.lengthMs).toBe((plan.exercises[st.ex_idx].rest_seconds ?? 0) * 1000)
      }
    }
  })

  it('a marked hold starts only when a timer that ran out brought the flow to it', () => {
    const marked = plan.steps.filter((st) => st.timer_starts === 'after_timer')
    expect(marked.length).toBeGreaterThan(0)
    for (const st of marked) {
      expect(arrivalTimer(at(st.index), T0, false)).toBeNull()
      const t = arrivalTimer(at(st.index), T0, true)
      expect(t?.kind).toBe('hold')
      expect(t?.lengthMs).toBe((plan.exercises[st.ex_idx].hold_seconds ?? 0) * 1000)
    }
  })

  it('everything the engine did not mark waits for a tap', () => {
    for (const st of plan.steps.filter((x) => x.timer_starts == null)) {
      expect(arrivalTimer(at(st.index), T0, true)).toBeNull()
    }
    // The timed plank test and the first hold of an exercise among them.
    const timed = plan.exercises.findIndex((e) => e.timer === 'stopwatch')
    expect(plan.steps[firstEntry(timed)].timer_starts).toBeNull()
  })
})

describe('the screen rules', () => {
  it('a warning shows only on an exercise the engine sent one for', () => {
    let shownNotDue = 0
    let shownDue = 0
    for (const ex of plan.exercises) {
      const shown = (render(at(firstEntry(ex.index))).match(/data-testid="warning"/g) ?? []).length
      if (ex.warning) shownDue += shown
      else shownNotDue += shown
    }
    expect(shownNotDue).toBe(0)
    expect(shownDue).toBe(plan.exercises.filter((e) => e.warning).length)
  })

  it('the weight label is plain, and no unit word is drawn for a machine', () => {
    const machine = {
      ...plan,
      exercises: plan.exercises.map((e) => (e.index === 2 ? { ...e, increment_unit: 'machine units' } : e)),
    }
    const s = { ...at(firstEntry(2)), plan: machine }
    const html = render(s)
    expect(html).toContain(`>${S.session.weight}<`)
    expect(html).not.toMatch(/machine|units/i)
  })

  it('the engine sends no reasoning to draw: no "why" fields reach the phone', () => {
    for (const ex of plan.exercises) {
      for (const field of ['biomechanical_focus', 'progression', 'regression']) expect(ex).not.toHaveProperty(field)
    }
  })
})

describe('the save through the outbox', () => {
  it('a save whose answer is lost goes again with the same ids, then leaves the outbox', async () => {
    let s = at(0)
    let t = T0
    while (!finished(s)) {
      s = advance(s, t)
      t += 30_000
    }
    const store = new HealthDB(`session-save-${Date.now()}`)
    await enqueue(store, { kind: 'session', method: 'POST', path: '/api/training/sessions', body: saveBody(s, 30, 6, '') }, new Date(T0))
    const bodies: { session_id: string; exercises: { exercise_id: string }[] }[] = []
    const statuses = [503, 200]
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      bodies.push(JSON.parse(String(init?.body)))
      const status = statuses.shift() ?? 200
      return new Response(JSON.stringify(status === 200 ? { saved: true } : { error: 'engine_unavailable' }),
        { status, headers: { 'content-type': 'application/json' } })
    })
    const ctx = { key: 'k', engineDown: false, fetchImpl }
    expect(await drain(store, { ...ctx, now: () => new Date(T0) })).toBe('offline')
    expect(await store.outbox.count()).toBe(1)
    expect(await drain(store, { ...ctx, now: () => new Date(T0 + 3_600_000) })).toBe('done')
    expect(await store.outbox.count()).toBe(0)
    expect(bodies).toHaveLength(2)
    expect(bodies[1]).toEqual(bodies[0])
    expect(bodies[0].session_id).toBe('2026-10-20-0a1b2c3d')
    expect(bodies[0].exercises.map((e) => e.exercise_id)).toEqual(plan.exercises.map((_, i) => `ex-${i}`))
  })
})

describe('both sides of a one-side exercise (WP-25)', () => {
  const split = plan.exercises.findIndex((e) => e.name === 'Made-up split squat')
  const first = plan.first_side as 'left' | 'right'
  const second = first === 'left' ? 'right' : 'left'

  it('a working step shows the other side\'s own numbers to change, named with their side', () => {
    const html = text(render(at(firstEntry(split))))
    expect(html).toContain(S.session.side[second])
    expect(render(at(firstEntry(split)))).toContain(
      `aria-label="${S.session.more(S.session.named(S.session.side[second], S.session.reps))}"`)
  })

  it('the rest after a set shows that set, each side to change', () => {
    let s = at(firstEntry(split))
    while (currentStepOf(s).phase !== 'resting') s = advance(s, T0)
    const html = render(s)
    expect(html).toContain('data-testid="just-done"')
    expect(text(html)).toContain(S.session.justDone(1))
    for (const side of [first, second]) {
      expect(html).toContain(`aria-label="${S.session.less(
        S.session.named(S.session.named(S.session.setN(1), S.session.side[side]), S.session.reps))}"`)
    }
  })
})

function currentStepOf(s: TrainingState) {
  return s.plan.steps[s.step]
}

describe('"In use? Do another first" (WP-27)', () => {
  it('shows at a lift that moves, and not at the warm-up that never does', () => {
    const squat = plan.exercises.findIndex((e) => e.name === 'Made-up squat')
    expect(text(render(at(firstEntry(squat))))).toContain(S.session.inUse)
    expect(text(render(at(0)))).not.toContain(S.session.inUse)
  })
})

/** Walk to an exercise's first entry, then Skip it. */
function skipOne(s: TrainingState, exIdx: number): TrainingState {
  let t = T0
  while (currentStepOf(s).ex_idx !== exIdx) {
    s = advance(s, t)
    t += 30_000
  }
  return skip(s)
}

describe('the save screen', () => {
  it('a skipped exercise reads as skipped, with no set done (WP-22)', () => {
    const s = walked(skipOne(at(0), 1))
    const line = reviewLine(s, plan.exercises[1])
    expect(line.skipped).toBe(true)
    expect(line.sets).toBe(0)
  })

  it('each exercise shows its time (the watch, else the estimate), its recorded sets and its weight', () => {
    const walk = plan.exercises.findIndex((e) => e.garmin_pull)
    let s = at(0)
    // The ramp's weight changed during the set: a ramp is not a working set, so its line keeps
    // the prescribed weight (sessions.review_figures).
    s = setSide(s, 1, 'right', { weight_kg: 18 })
    s = walked(setGarmin(s, walk, { state: 'found', minutes: 31.4, detail: null }, null))
    const lines = plan.exercises.map((ex) => reviewLine(s, ex))
    expect(lines[walk].time).toBe(S.session.timeGarmin(31))
    expect(lines[2].time).toBe(S.session.timeEstimated(plan.exercises[2].estimated_minutes))
    expect(lines.map((l) => l.sets)).toEqual(plan.exercises.map((e) => e.sets ?? 1))
    expect(lines[1].weight).toBe(S.session.kg(plan.exercises[1].weight_kg!))
    expect(lines[2].weight).toBe(S.session.kg(22.5))
    expect(lines[0].weight).toBe(S.session.bodyweightShort)
  })

  const savedState = (declared: boolean, hr: HeartRate | null): TrainingState => ({
    ...walked(startSessionState(plan, '2026-10-20-0a1b2c3d', plan.exercises.map((_, i) => `ex-${i}`), declared)),
    saving: true, savedId: 'outbox-1', saved: { rpe: 6, minutes: 30, notes: '' }, hr,
  })
  const matchOf = (s: TrainingState, confirmed = true) =>
    text(provide(<HeartRateMatch s={s} update={() => undefined} confirmed={confirmed} />))

  it('with no Garmin workout, the session keeps the rating and says how to get a measured figure', () => {
    expect(matchOf(savedState(false, null))).toContain(S.session.hrNotStarted(6))
  })

  it('the match waits for the engine to have the save', () => {
    expect(matchOf(savedState(true, null), false).trim()).toBe('')
  })

  it('a match shows the measured figures against the rating, in the engine\'s numbers', () => {
    const hr: HeartRate = { state: 'matched', reason: '', candidates: [], comparison: {
      measured_rpe: 6.8, measured_au: 204, active_minutes: 28, rpe_delta: 0.8, au_delta: 24, verdict: 'under',
      coverage: 0.6, low_coverage: true, activity: 'Strength', covered_exercises: 7, total_exercises: 9 } }
    const shown = matchOf(savedState(true, hr))
    expect(shown).toContain(S.session.hrMeasuredRpe)
    expect(shown).toContain(S.session.hrVsYours(0.8, 6))
    expect(shown).toContain(S.session.hrVsYoursAu(24, 180))
    expect(shown).toContain(S.session.hrVerdict.under)
    expect(shown).toContain(S.session.hrLowCover(0.6))
  })

  it('a session the watch cannot place offers the day\'s activities to choose from', () => {
    const hr: HeartRate = { state: 'choose', reason: 'no activity lines up', comparison: null, candidates: [
      { activity_id: '7', name: 'Strength', type: 'strength', start_time_local: '2026-10-20 07:05:00',
        duration_minutes: 52, shift_hours: -1, quality: 0.8 }] }
    const html = provide(<HeartRateMatch s={savedState(true, hr)} update={() => undefined} confirmed />)
    expect(text(html)).toContain(S.session.hrChoose('no activity lines up'))
    expect((html.match(/role="radio"/g) ?? []).length).toBe(1)
    expect(text(html)).toContain(S.session.hrUse)
  })

  it('no match says why and keeps the rating', () => {
    const hr: HeartRate = { state: 'no_match', reason: 'no activity today', candidates: [], comparison: null }
    expect(matchOf(savedState(true, hr))).toContain(S.session.hrNone('no activity today', 6))
  })
})

describe('the overview and the flow, as drawn', () => {
  it("the load banner keeps the page's shades: strongest for a rest or reduced day", () => {
    const html = (kind: string) => renderToStaticMarkup(<Banner kind={kind} text="Made-up banner" />)
    expect(html('error')).toContain('class="alert"')
    expect(html('warning')).toContain('class="alert"')
    expect(html('info')).toContain('class="note"')
    expect(html('')).toContain('class="caption"')
    expect(renderToStaticMarkup(<Banner kind="error" text="" />)).toBe('')
  })

  it("a day with no session to start says why, in the engine's own terms", () => {
    const today = fx.trainingDay('2026-10-20', '2026-10-20')
    expect(noSessionReason(today)).toBeNull()
    const ended = { ...today, overview: { ...today.overview!, screen: 'complete' } }
    expect(S.session.noSession[noSessionReason(ended)!]).toBe('The block is complete.')
    expect(noSessionReason({ ...today, route: 'rest', overview: null })).toBe('rest_day')
    expect(noSessionReason({ ...today, overview: { ...today.overview!, screen: 'logged' } })).toBe('already_logged')
  })

  it('the date is written out', () => {
    expect(longDate('2026-10-20')).toBe('Tuesday 20 October')
  })

  it('the flow shows the day, the progress, the exercise list, the numbers and the how-to', () => {
    const squat = at(firstEntry(2))
    const shown = text(render(squat))
    expect(shown).toContain(S.session.dayHeader(plan.day_num!, plan.plan_days ?? null, plan.rpe_target))
    expect(shown).toContain(S.session.progressOf(2, plan.exercises.length))
    for (const ex of plan.exercises) expect(shown).toContain(ex.name)
    const ex = plan.exercises[2]
    expect(shown).toContain(ex.prescription.replace(/\s+/g, ' '))
    expect(shown).toContain(ex.previous_caption)
    expect(shown).toContain(ex.entry_caption)
    expect(shown).toContain(S.session.howTo)
    expect(shown).toContain(S.session.kg(22.5))
  })

  it('a held set shows its rep; a walk with a watch shows what to do instead of a timer', () => {
    const deadBug = plan.exercises.findIndex((e) => e.type === 'hold_reps')
    expect(text(render(at(firstEntry(deadBug))))).toContain(S.session.repOf(1, plan.exercises[deadBug].reps_in_set ?? 1))
    const walk = plan.exercises.findIndex((e) => e.garmin_pull)
    const html = render(at(firstEntry(walk)))
    expect(html).toContain('data-testid="garmin-activity"')
    expect(html).not.toContain('role="timer"')
  })
})

// 2026-10-22: the first open of the morning took 45-64 s, the phone stopped waiting at 30 s,
// and the overview said there was no connection.
describe("today's overview while it has no session", () => {
  it('says it is reading while the session is on its way', () => {
    expect(noSessionLine(null, { state: 'loading' })).toEqual({ text: S.session.reading, reading: true })
  })

  it('a read the engine was too slow for is said as such, never as no connection', () => {
    const line = noSessionLine(null, { state: 'offline', code: 'timeout' })
    expect(line).toEqual({ text: S.session.slowEngine, reading: false })
    expect(line.text).not.toBe(S.session.needsEngine)
  })

  it('no network, or the engine down, still says the session needs the engine', () => {
    expect(noSessionLine(null, { state: 'offline', code: 'network' }).text).toBe(S.session.needsEngine)
    expect(noSessionLine(null, { state: 'engine_unavailable' }).text).toBe(S.session.needsEngine)
  })

  it("the day's own reason comes first", () => {
    expect(noSessionLine('rest_day', { state: 'loading' })).toEqual({ text: S.session.noSession.rest_day, reading: false })
    expect(noSessionLine(null, { state: 'fresh' }).text).toBe(S.session.noSessionOther)
  })
})

describe('Back beside the main button (WP-34)', () => {
  const walk = (n: number) => {
    let s = at(0)
    for (let i = 0; i < n; i++) s = advance(s, T0 + i * 1000)
    return s
  }

  it('says where it goes: the side, the rest or the exercise before', () => {
    expect(backLabel(at(0))).toBe(S.session.back)
    expect(backLabel(walk(1))).toBe(S.session.backTo(`${S.session.setN(1)} · ${S.session.side.left}`))
    expect(backLabel(walk(3))).toBe(S.session.backTo(S.session.backRest))
    expect(backLabel(walk(5))).toBe(S.session.backTo('Made-up march'))
  })

  it('after a change of order it says it puts the order back', () => {
    const squat = walk(6)
    expect(squat.plan.steps[squat.step].ex_idx).toBe(2)
    const moved = doFirst(squat, 3)
    expect(backLabel(moved)).toBe(S.session.backOrder)
  })

  it('sits in the controls row before the main button, and Skip stays below', () => {
    const html = render(walk(1))
    const controls = html.slice(html.indexOf('class="controls"'))
    const row = controls.slice(0, controls.indexOf('</div>'))
    expect(row).toContain('data-testid="back"')
    expect(row.indexOf('data-testid="back"')).toBeLessThan(row.indexOf('btn--primary'))
    expect(text(html)).toContain(S.session.skip)
    expect(render(at(0))).not.toContain('data-testid="back"')
  })
})

describe('the exercise the flow is on (WP-31)', () => {
  it('is the one row of the list marked now', () => {
    const html = render(at(6))
    expect(html.match(/data-state="now"/g)?.length).toBe(1)
  })
})

describe('a trained day stays trained (WP-32)', () => {
  const today = fx.trainingDay('2026-10-20', '2026-10-20')
  const logged = { ...today, overview: { ...today.overview!, screen: 'logged' },
    logged: { rpe: 6, minutes: 50, au: 300, exercises: [{ name: 'Made-up squat', movement_type: 'Strength', planned_sets: 3 }] } }

  it('the engine\'s logged answer or a save on this phone today: never Start again', () => {
    expect(trainedToday(today, null, '2026-10-20')).toBe(false)
    expect(trainedToday(logged, null, '2026-10-20')).toBe(true)
    expect(trainedToday(today, '2026-10-20', '2026-10-20')).toBe(true)
    expect(trainedToday(today, '2026-10-19', '2026-10-20')).toBe(false)
  })

  it('shows what was logged, or that the save is on its way', () => {
    const shown = text(provide(<TrainedToday day={logged} />))
    expect(shown).toContain(S.session.trainedToday)
    expect(shown).toContain('Made-up squat')
    expect(text(provide(<TrainedToday day={today} />))).toContain(S.session.trainedSaving)
    expect(provide(<TrainedToday day={logged} />)).not.toContain(S.session.start)
  })

  it('the saved screen congratulates with a check that grows into place', () => {
    const s = { ...walked(at(0)), saving: true, savedId: 'outbox-1', saved: { rpe: 6, minutes: 30, notes: '' } }
    const html = provide(<SessionSave s={s} update={() => undefined} onDone={() => undefined} />)
    expect(html).toContain('data-testid="celebrate"')
    expect(text(html)).toContain(S.session.congrats)
  })
})

describe('a test of the flexibility retest on the screen (WP-33)', () => {
  const testPlan = (): Plan => ({
    ...plan,
    exercises: plan.exercises.map((e) => (e.index === 8 ? {
      ...e, name: 'Made-up test (Test)', timer: null, garmin_pull: false, garmin_window: null,
      reading: { test_key: 'one', unit: 'cm', sides: ['left', 'right'], input_hint: 'Made-up hint',
        setup_input: 'Made-up setup (cm)', prior_setup: 30, takes_load: false },
    } : e)),
  })

  it('asks for each side and the setup number, with no timer, and waits for the values', () => {
    const p = testPlan()
    const s = { ...startSessionState(p, '2026-11-01-00000001', p.exercises.map((_, i) => `ex-${i}`)),
      step: p.steps.findIndex((st) => st.ex_idx === 8) }
    const html = render(s)
    const shown = text(html)
    expect(html).toContain('data-testid="reading"')
    expect(shown).toContain('Made-up hint')
    expect(shown).toContain(S.session.readingFor('left', 'cm'))
    expect(shown).toContain('Made-up setup (cm)')
    expect(html).toContain('value="30"')
    expect(shown).toContain(S.session.readingDone)
    expect(html).not.toContain('role="timer"')
    expect(html).toMatch(/disabled=""[^>]*>Reading done/)
  })
})

describe('leaving a session (WP-33)', () => {
  it('Leave for now is offered beside losing it', () => {
    expect(S.session.exitAsk).toContain('Leave for now')
    expect(S.session.leaveForNow).toBe('Leave for now')
  })
})
