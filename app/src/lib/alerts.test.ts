// The timer alerts (rebuild Phase 6, T87): when the phone can take them, what an alert says
// when a countdown ends with the phone locked (the app's words; the bell's ending and the next
// entry are the engine's walk), and the two keepalive requests that ask for one and cancel it.
import { describe, expect, it, vi } from 'vitest'
import fixture from '../../dev/session_fixture.json'
import { S } from '../strings'
import { alertFor, alertSupport, cancelAlert, scheduleAlert, type Host } from './alerts'
import { pauseTimer, startTimer } from './timers'
import { startSessionState, type Plan, type TrainingState } from './training'

const plan = fixture as unknown as Plan
const T0 = Date.parse('2026-10-20T08:00:00Z')
const at = (step: number): TrainingState =>
  ({ ...startSessionState(plan, '2026-10-20-0a1b2c3d', plan.exercises.map((_, i) => `ex-${i}`)), step })
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X)'
const host = (h: Partial<Host>): Host => ({ userAgent: IPHONE, standalone: true, push: true, permission: 'default', ...h })

describe('when the phone can take alerts', () => {
  it('an iPhone needs the app opened from the Home Screen first', () => {
    expect(alertSupport(host({ standalone: false }))).toBe('install-first')
    expect(alertSupport(host({}))).toBe('ready')
  })

  it('no push support, or alerts blocked, say so', () => {
    expect(alertSupport(host({ push: false, permission: null }))).toBe('unsupported')
    expect(alertSupport(host({ permission: 'denied' }))).toBe('denied')
    expect(alertSupport(host({ userAgent: 'Mozilla/5.0 (Windows NT 10.0)', standalone: false }))).toBe('ready')
  })
})

describe('what an alert says', () => {
  it('a rest: over, and what comes next', () => {
    const rest = plan.steps.findIndex((st) => st.phase === 'resting')
    const next = plan.steps[rest + 1]
    const ex = plan.exercises[next.ex_idx]
    const alert = alertFor(at(rest), startTimer('rest', 20_000, T0))!
    expect(alert.at).toBe(T0 + 20_000)
    expect(alert.tag).toBe('rest')
    expect(alert.title).toBe(S.session.alertRest)
    const side = ex.laterality === 'unilateral' ? ` · ${S.session.side[next.side]}` : ''
    expect(alert.body).toBe(S.session.alertNext(`${S.session.setN(next.set_num)}${side}`, ex.name))
  })

  it("a hold: the bell's own ending, from the engine's walk", () => {
    const holds = plan.steps.filter((st) => st.phase !== 'resting' && plan.exercises[st.ex_idx].timer === 'hold')
    expect(new Set(holds.map((st) => st.ending)).size).toBeGreaterThan(1)
    for (const st of holds) {
      const alert = alertFor(at(st.index), startTimer('hold', 6_000, T0))!
      expect(alert.title).toBe(S.session.alertHold[st.ending ?? 'continue'])
      expect(alert.body).toBe(plan.exercises[st.ex_idx].name)
    }
  })

  it('an activity timer says it is done; a stopwatch or a paused timer asks for nothing', () => {
    const walk = plan.steps.find((st) => plan.exercises[st.ex_idx].type === 'duration')!
    expect(alertFor(at(walk.index), startTimer('duration', 60_000, T0))?.title).toBe(S.session.alertActivity)
    const timed = plan.steps.find((st) => plan.exercises[st.ex_idx].timer === 'stopwatch')!
    expect(alertFor(at(timed.index), startTimer('stopwatch', 0, T0))).toBeNull()
    expect(alertFor(at(walk.index), pauseTimer(startTimer('duration', 60_000, T0), T0 + 1_000))).toBeNull()
  })
})

describe('asking and cancelling', () => {
  const ctx = { key: 'k', engineDown: false }
  const recorder = (status = 204) => {
    const calls: { path: string; init: RequestInit }[] = []
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ path: String(input), init: init ?? {} })
      return new Response(status === 204 ? null : JSON.stringify({ error: 'push_not_configured' }), { status })
    }) as unknown as typeof fetch
    return { calls, fetchImpl }
  }

  it('the alert goes as a keepalive PUT with the key, and the cancel as a keepalive DELETE', async () => {
    const { calls, fetchImpl } = recorder()
    await scheduleAlert(ctx, { at: T0 + 20_000, title: 'Rest over', body: 'Next', tag: 'rest' }, fetchImpl)
    await cancelAlert(ctx, fetchImpl)
    expect(calls.map((c) => [c.path, c.init.method, c.init.keepalive])).toEqual([
      ['/api/push/alert', 'PUT', true],
      ['/api/push/alert', 'DELETE', true],
    ])
    expect(new Headers(calls[0].init.headers).get('authorization')).toBe('Bearer k')
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ at: T0 + 20_000, title: 'Rest over', body: 'Next', tag: 'rest' })
  })

  it('a refused or failed request never stops the session', async () => {
    const { fetchImpl } = recorder(503)
    await expect(scheduleAlert(ctx, { at: T0, title: 'x', body: '', tag: 'rest' }, fetchImpl)).resolves.toBeUndefined()
    const offline = vi.fn(async () => {
      throw new TypeError('offline')
    }) as unknown as typeof fetch
    await expect(cancelAlert(ctx, offline)).resolves.toBeUndefined()
  })
})
