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
import { drain, enqueue } from '../lib/outbox'
import { advance, finished, saveBody, startSessionState, type Plan, type TrainingState } from '../lib/training'
import { S } from '../strings'
import { arrivalTimer, SessionFlow } from './Session'

const plan = fixture as unknown as Plan
const T0 = Date.parse('2026-10-20T08:00:00Z')

function at(step: number): TrainingState {
  return { ...startSessionState(plan, '2026-10-20-0a1b2c3d', plan.exercises.map((_, i) => `ex-${i}`)), step }
}

const firstEntry = (exIdx: number) => plan.steps.findIndex((st) => st.ex_idx === exIdx)

function render(s: TrainingState): string {
  return renderToStaticMarkup(<SessionFlow s={s} update={() => undefined} onExit={() => undefined} />)
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
