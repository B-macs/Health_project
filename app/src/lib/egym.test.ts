// The EGYM circuit (2026-11-08) on the phone, walked over the circuit the engine's own walk
// made (dev/egym_fixture.json, scripts/make_session_fixture.py): only the tonnage is typed,
// round 2 follows the order of round 1 ("if I switch them around in round one, then in
// round two, they should be the same"), Back puts both rounds back, and the review adds each
// machine's two rounds.
import { describe, expect, it } from 'vitest'
import fixture from '../../dev/egym_fixture.json'
import {
  advance, back, circuitTonnage, currentStep, doFirst, doFirstCandidates, exerciseOf, exerciseOrder, finished, saveBody,
  setSide, skip, startSessionState, type Plan, type TrainingState,
} from './training'

const plan = fixture as unknown as Plan
const T0 = Date.parse('2026-10-20T18:00:00Z')
const N = 14

function fresh(): TrainingState {
  return startSessionState(plan, '2026-10-20-e9e9e9e9', plan.exercises.map((_, i) => `ex-${i}`))
}

const names = (s: TrainingState, from: number, to: number) =>
  exerciseOrder(s).slice(from, to).map((i) => s.plan.exercises[i].name)

/** Type `kg` for the entry the flow is on, then Done. */
function typed(s: TrainingState, kg: number, at = T0): TrainingState {
  const ex = exerciseOf(s)!
  return advance(setSide(s, ex.index, 'right', { weight_kg: kg }), at)
}

describe('the EGYM circuit', () => {
  it('is fourteen machines in two rounds of the same order, each one tonnage', () => {
    expect(plan.kind).toBe('egym')
    expect(plan.exercises).toHaveLength(2 * N)
    expect(plan.exercises.every((e) => e.tonnage_entry && !e.reps_editable)).toBe(true)
    const s = fresh()
    expect(names(s, 0, N)).toEqual(names(s, N, 2 * N))
    expect(plan.steps).toHaveLength(2 * N)
  })

  it('records the typed tonnage as one rep at that weight', () => {
    const s = typed(fresh(), 1240)
    const rec = s.sets[0][0]
    expect(rec.right).toMatchObject({ reps: 1, weight_kg: 1240 })
    expect(currentStep(s)!.ex_idx).toBe(1)
  })

  it('offers only round 1 machines in round 1, and moves round 2 the same way', () => {
    let s = typed(fresh(), 1000)                       // squat done; the flow is on the pulldown
    const offered = doFirstCandidates(s).map((c) => c.exercise.name)
    expect(offered).toEqual(names(fresh(), 2, N))       // round 2 is never offered in round 1
    const row = doFirstCandidates(s).find((c) => c.exercise.name === 'EGYM Row')!
    s = doFirst(s, row.group)
    const round1 = names(s, 0, N)
    expect(round1.slice(0, 3)).toEqual(['EGYM Squat', 'EGYM Row', 'EGYM Lat Pulldown'])
    expect(names(s, N, 2 * N)).toEqual(round1)          // round 2 follows round 1
    const undone = back(s)
    expect(names(undone, N, 2 * N)).toEqual(names(fresh(), 0, N))
  })

  it('in round 2 offers the round 2 machines left, and moves only round 2', () => {
    let s = fresh()
    for (let i = 0; i < N + 1; i += 1) s = typed(s, 500 + i)
    const round1 = names(s, 0, N)
    const offered = doFirstCandidates(s).map((c) => c.exercise.name)
    expect(offered).toEqual(names(s, N + 2, 2 * N))
    s = doFirst(s, doFirstCandidates(s)[0].group)
    expect(names(s, 0, N)).toEqual(round1)
  })

  it('adds each machine’s two rounds in the review; a skipped round counts nothing', () => {
    let s = fresh()
    s = typed(s, 1240)
    s = skip(s)                                         // the pulldown in round 1
    while (!finished(s)) s = typed(s, exerciseOf(s)!.name === 'EGYM Squat' ? 1300 : 100)
    const t = circuitTonnage(s)
    expect(t.machines).toHaveLength(N)
    expect(t.machines[0]).toEqual({ name: 'EGYM Squat', rounds: [1240, 1300], total: 2540 })
    expect(t.machines[1]).toEqual({ name: 'EGYM Lat Pulldown', rounds: [null, 100], total: 100 })
    expect(t.total).toBe(2540 + 100 + 12 * 200)
    const body = saveBody(s, 70, 6, '')
    expect(body.kind).toBe('egym')
    expect(body.exercises).toHaveLength(2 * N)
    expect(body.exercises[0].raw_sets[0].right).toMatchObject({ reps: 1, weight_kg: 1240 })
  })
})
