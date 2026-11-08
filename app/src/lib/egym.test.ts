// The EGYM session (2026-11-08) on the phone, walked over the session the engine's own walk
// made (dev/egym_fixture.json, scripts/make_session_fixture.py): only the tonnage is typed,
// both sets of a machine run one after the other ("it can't be a circuit because of the
// current usage; I will have to do both sets just after each other"), any machine can run
// next when one is in use, and the review adds each machine's sets.
import { describe, expect, it } from 'vitest'
import fixture from '../../dev/egym_fixture.json'
import {
  advance, back, currentStep, doFirst, doFirstCandidates, egymTonnage, exerciseOf, exerciseOrder, finished, saveBody,
  setSide, skip, startSessionState, type Plan, type TrainingState,
} from './training'

const plan = fixture as unknown as Plan
const T0 = Date.parse('2026-10-20T18:00:00Z')
const N = 14

function fresh(): TrainingState {
  return startSessionState(plan, '2026-10-20-e9e9e9e9', plan.exercises.map((_, i) => `ex-${i}`))
}

const names = (s: TrainingState) => exerciseOrder(s).map((i) => s.plan.exercises[i].name)

/** Type `kg` for the set the flow is on, tap Done, then end the rest when one follows. */
function typed(s: TrainingState, kg: number, at = T0): TrainingState {
  const ex = exerciseOf(s)!
  let x = advance(setSide(s, ex.index, 'right', { weight_kg: kg }), at)
  if (currentStep(x)?.phase === 'resting') x = advance(x, at + 30_000)
  return x
}

describe('the EGYM session', () => {
  it('is fourteen machines, each two sets one after the other, each set one tonnage', () => {
    expect(plan.kind).toBe('egym')
    expect(plan.exercises).toHaveLength(N)
    expect(plan.exercises.every((e) => e.tonnage_entry && !e.reps_editable && e.sets === 2)).toBe(true)
    const first = plan.steps.filter((st) => st.ex_idx === 0).map((st) => [st.phase, st.record_set])
    expect(first).toEqual([['intro', 1], ['resting', null], ['intro', 2]])
  })

  it('records each typed tonnage as one rep at that weight, and starts the next set empty', () => {
    let s = advance(setSide(fresh(), 0, 'right', { weight_kg: 1240 }), T0)
    expect(s.sets[0][0].right).toMatchObject({ reps: 1, weight_kg: 1240 })
    expect(s.live[0].right.weight_kg).toBeNull()          // set 2 needs its own number
    s = advance(s, T0 + 30_000)                            // the rest ends
    s = advance(setSide(s, 0, 'right', { weight_kg: 1300 }), T0 + 90_000)
    expect(s.sets[0].map((r) => [r.set_num, r.right?.weight_kg])).toEqual([[1, 1240], [2, 1300]])
    expect(currentStep(s)!.ex_idx).toBe(1)
  })

  it('offers every machine left when one is in use, and moves both its sets', () => {
    let s = typed(typed(fresh(), 1240), 1300)              // the squat done
    const offered = doFirstCandidates(s).map((c) => c.exercise.name)
    expect(offered).toEqual(names(fresh()).slice(2))
    const row = doFirstCandidates(s).find((c) => c.exercise.name === 'EGYM Row')!
    s = doFirst(s, row.group)
    expect(names(s).slice(0, 3)).toEqual(['EGYM Squat', 'EGYM Row', 'EGYM Lat Pulldown'])
    const rowSteps = s.plan.steps.filter((st) => s.plan.exercises[st.ex_idx].name === 'EGYM Row')
    expect(rowSteps.map((st) => st.index)).toEqual([3, 4, 5]) // set 1, the rest, set 2, together
    expect(names(back(s))).toEqual(names(fresh()))
  })

  it('adds each machine’s sets in the review; a skipped machine counts nothing', () => {
    let s = typed(typed(fresh(), 1240), 1300)
    s = skip(s)                                            // the pulldown
    while (!finished(s)) s = typed(s, 100)
    const t = egymTonnage(s)
    expect(t.machines).toHaveLength(N)
    expect(t.machines[0]).toEqual({ name: 'EGYM Squat', sets: [1240, 1300], total: 2540 })
    expect(t.machines[1]).toEqual({ name: 'EGYM Lat Pulldown', sets: [null, null], total: 0 })
    expect(t.total).toBe(2540 + 12 * 200)
    const body = saveBody(s, 70, 6, '')
    expect(body.kind).toBe('egym')
    expect(body.exercises).toHaveLength(N)
    expect(body.exercises[0].raw_sets.map((r) => r.right)).toEqual([
      expect.objectContaining({ reps: 1, weight_kg: 1240 }), expect.objectContaining({ reps: 1, weight_kg: 1300 })])
  })
})
