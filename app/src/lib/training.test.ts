// The session state machine (rebuild Phase 6), walked over a session the engine's own
// guided_flow.walk made (dev/session_fixture.json, scripts/make_session_fixture.py): every
// set recorded once with its side's numbers, the rests measured on the phone's clock and
// attached to the set they followed, Skip and Back, the second side following the first
// until it is edited, the steppers, the length question, and the complete save body.
import { describe, expect, it } from 'vitest'
import fixture from '../../dev/session_fixture.json'
import {
  advance, asksLength, back, clockMinutes, currentStep, exerciseOf, exerciseProgress, finished, loadState,
  localStamp, newExerciseIds, newSessionId, saveBody, setBand, setGarmin, setSide, sideValues, skip,
  startSessionState, stepBand, stepWeight, UNDO_LIMIT, type Plan, type TrainingState,
} from './training'

const plan = fixture as unknown as Plan
const T0 = Date.parse('2026-10-20T08:00:00Z')

function fresh(): TrainingState {
  return startSessionState(plan, '2026-10-20-0a1b2c3d', plan.exercises.map((_, i) => `ex-${i}`))
}

/** Every step taken, a minute apart. */
function walkAll(s: TrainingState): TrainingState {
  let t = T0
  while (!finished(s)) {
    s = advance(s, t)
    t += 60_000
  }
  return s
}

describe('walking the engine steps', () => {
  it('records each set of each exercise once, as the engine walk says', () => {
    const s = walkAll(fresh())
    for (const ex of plan.exercises) {
      const expected = plan.steps.filter((st) => st.ex_idx === ex.index && st.record_set != null).map((st) => st.record_set)
      expect((s.sets[ex.index] ?? []).map((r) => r.set_num), ex.name).toEqual(expected)
    }
    expect(s.firstSetAt).not.toBeNull()
  })

  it('a rest is measured on the phone clock and belongs to the set it followed', () => {
    let s = fresh()
    const squat = plan.exercises.findIndex((e) => e.name === 'Made-up squat')
    while (currentStep(s)!.ex_idx !== squat) s = advance(s, T0)
    s = advance(s, T0)                 // set 1 done: its rest begins
    s = advance(s, T0 + 75_000)        // the rest ends 75 s later
    const one = s.sets[squat].find((r) => r.set_num === 1)!
    expect(one.rest_started_at).toBe(T0 / 1000)
    expect(one.rest_ended_at).toBe((T0 + 75_000) / 1000)
  })

  it('a one-side exercise records both sides; the second follows the first until edited', () => {
    let s = fresh()
    const split = plan.exercises.findIndex((e) => e.name === 'Made-up split squat')
    const first = plan.first_side as 'left' | 'right'
    const second = first === 'left' ? 'right' : 'left'
    s = setSide(s, split, first, { reps: 7 })
    expect(sideValues(s.live[split], second, first).reps).toBe(7)
    s = setSide(s, split, second, { reps: 6 })
    s = setSide(s, split, first, { reps: 8 })
    expect(sideValues(s.live[split], second, first).reps).toBe(6)
    while (currentStep(s)!.ex_idx !== split || currentStep(s)!.record_set == null) s = advance(s, T0)
    s = advance(s, T0)
    const set1 = s.sets[split][0]
    expect(set1[first]?.reps).toBe(8)
    expect(set1[second]?.reps).toBe(6)
  })

  it('Skip moves to the next exercise, and Back undoes the last tap', () => {
    let s = fresh()
    s = advance(s, T0)
    const before = s.step
    const nextEx = currentStep(s)!.skip_to
    s = skip(s)
    expect(s.step).toBe(nextEx)
    s = back(s)
    expect(s.step).toBe(before)
    s = back(s)
    expect(s.step).toBe(0)
    expect(s.sets).toEqual({})
  })

  it('Back remembers at most the last thirty taps', () => {
    let s = fresh()
    for (let i = 0; i < 31 && !finished(s); i++) s = advance(s, T0)
    expect(s.history.length).toBe(UNDO_LIMIT)
  })

  it('a set redone after Back is recorded once, with the new numbers', () => {
    let s = fresh()
    s = advance(s, T0)
    while (currentStep(s)!.record_set == null) s = advance(s, T0)
    const exIdx = exerciseOf(s)!.index
    s = advance(s, T0)
    s = back(s)
    s = setSide(s, exIdx, 'right', { reps: 3 })
    s = setSide(s, exIdx, 'left', { reps: 3 })
    s = advance(s, T0 + 1000)
    const sets = s.sets[exIdx]
    expect(new Set(sets.map((r) => r.set_num)).size).toBe(sets.length)
  })
})

describe('the steppers', () => {
  it('a weight steps by the engine increment and never goes below zero', () => {
    expect(stepWeight(22.5, 1, 2.25)).toBe(24.75)
    expect(stepWeight(2.0, -1, 2.25)).toBe(0)
    expect(stepWeight(null, 1, 2.5)).toBe(2.5)
  })

  it('a band moves along the engine tiers and stops at both ends', () => {
    const tiers = plan.band_tiers.map((b) => b.tier)
    expect(stepBand(tiers[0], -1, tiers)).toBe(tiers[0])
    expect(stepBand(tiers[0], 1, tiers)).toBe(tiers[1])
    expect(stepBand(tiers[tiers.length - 1], 1, tiers)).toBe(tiers[tiers.length - 1])
  })

  it('a band change is kept for the next sets', () => {
    const row = plan.exercises.findIndex((e) => e.equipment_type === 'band')
    expect(setBand(fresh(), row, 'Black').live[row].band_tier).toBe('Black')
  })
})

describe('the save', () => {
  it('the clock counts from the first set, with the plan floor', () => {
    let s = fresh()
    expect(clockMinutes(s, T0)).toBe(plan.model_minutes)
    s = advance(s, T0)
    expect(clockMinutes(s, T0 + 2 * 60_000)).toBe(plan.min_minutes)
    expect(clockMinutes(s, T0 + 47 * 60_000 + 59_000)).toBe(47)
  })

  it('the length question follows the engine threshold', () => {
    const s = fresh()
    const above = plan.ask_length_above_minutes!
    expect(asksLength(s, Math.floor(above))).toBe(false)
    expect(asksLength(s, Math.floor(above) + 1)).toBe(true)
  })

  it('the save body carries every exercise, its ids, plan fields and raw sets', () => {
    const s = walkAll(fresh())
    const body = saveBody(s, 31, 7, 'Felt fine.')
    expect(body.session_id).toBe('2026-10-20-0a1b2c3d')
    expect(body.exercises.map((e) => e.exercise_id)).toEqual(plan.exercises.map((_, i) => `ex-${i}`))
    expect(body.exercises.map((e) => (e.exercise as { name: string }).name)).toEqual(plan.exercises.map((e) => e.name))
    expect(body.duration_minutes).toBe(31)
    expect(body.session_rpe).toBe(7)
    expect(body.exercises.every((e) => (e.raw_sets ?? []).length > 0)).toBe(true)
    expect(body.exercises.every((e) => (e.sets ?? []).length === 0)).toBe(true)
  })
})

describe('the ids and the clock', () => {
  it('a session id has the Training page shape and exercise ids are unique', () => {
    expect(newSessionId('2026-10-20')).toMatch(/^2026-10-20-[0-9a-f]{8}$/)
    const ids = newExerciseIds(9)
    expect(new Set(ids).size).toBe(9)
  })

  it('a set time carries the phone UTC offset', () => {
    expect(localStamp(T0)).toMatch(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$/)
    expect(new Date(localStamp(T0)).getTime()).toBe(T0)
  })
})

describe('the watch and the stored session', () => {
  it('a session stored by an earlier version takes the new fields at their start', () => {
    const old = { ...fresh() } as unknown as Record<string, unknown>
    for (const key of ['garminDeclared', 'garmin', 'notice', 'saved', 'hr']) delete old[key]
    const s = loadState(old)!
    expect([s.garminDeclared, s.garmin, s.notice, s.saved, s.hr]).toEqual([false, {}, null, null, null])
    expect(loadState({ version: 2 })).toBeNull()
    expect(loadState(null)).toBeNull()
  })

  it("a walk's minutes from the watch ride with the save; a pending ask does not", () => {
    const walk = plan.exercises.findIndex((e) => e.garmin_pull)
    expect(walk).toBeGreaterThanOrEqual(0)
    const found = saveBody(walkAll(setGarmin(fresh(), walk, { state: 'found', minutes: 31, detail: { n: 1 } }, null)), 30, 6, '')
    expect([found.exercises[walk].garmin_minutes, found.exercises[walk].garmin_detail]).toEqual([31, { n: 1 }])
    const pending = saveBody(walkAll(setGarmin(fresh(), walk, { state: 'pending' }, null)), 30, 6, '')
    expect([pending.exercises[walk].garmin_minutes, pending.exercises[walk].garmin_detail]).toEqual([null, null])
  })

  it('a notice lasts until the next tap', () => {
    const s = setGarmin(fresh(), 8, { state: 'none' }, 'shown once')
    expect(s.notice).toBe('shown once')
    expect(advance(s, T0).notice).toBeNull()
    expect(skip(s).notice).toBeNull()
  })

  it('the progress counts the exercises behind the flow', () => {
    const total = plan.exercises.length
    expect(exerciseProgress(fresh())).toEqual({ done: 0, total })
    const second = plan.steps.findIndex((st) => st.ex_idx === 1)
    expect(exerciseProgress({ ...fresh(), step: second })).toEqual({ done: 1, total })
    expect(exerciseProgress(walkAll(fresh()))).toEqual({ done: total, total })
  })

  it('a Garmin workout declared at Start is kept with the session', () => {
    const s = startSessionState(plan, '2026-10-20-0a1b2c3d', plan.exercises.map((_, i) => `ex-${i}`), true)
    expect(s.garminDeclared).toBe(true)
    expect(fresh().garminDeclared).toBe(false)
  })
})
