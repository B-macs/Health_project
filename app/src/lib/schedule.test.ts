// The schedule answers (rebuild Phase 7): a move carries an id the phone mints for the
// answer, so the engine applies it once however often the outbox sends it; gate 1's answers
// need none; a refused answer says why in the screen's words and is cleared by the owner,
// and only a schedule answer can be cleared that way (a refused session save or check-in
// holds what the owner typed, and stays). The outbox keeps each answer for the screen
// that waits on it.
import { describe, expect, it, vi } from 'vitest'
import { HealthDB, type OutboxRow } from '../db/schema'
import { S } from '../strings'
import { ANSWERS_KEPT, answerOf, drain, enqueue } from './outbox'
import {
  answerCarry, answerShift, clearRefused, gate1Flare, gate1Reason, isSchedule, redoWeek, refusalText, swapWithToday,
} from './schedule'
import { ULID } from './ulid'

let n = 0
const store = () => new HealthDB(`schedule-test-${++n}-${Date.now()}`)

const bodies = async (db: HealthDB) => (await db.outbox.orderBy('seq').toArray()).map((r) => [r.kind, r.path, r.body])

describe('the answers', () => {
  it('a move carries an id minted for the answer; each answer its own', async () => {
    const db = store()
    await swapWithToday(db, '2026-10-22')
    await answerCarry(db, true)
    await answerShift(db, false)
    await redoWeek(db)
    const rows = await db.outbox.orderBy('seq').toArray()
    expect(rows.map((r) => [r.kind, r.path])).toEqual([
      ['swap', '/api/training/swap'], ['carry', '/api/training/carry'], ['shift', '/api/training/shift'],
      ['redo', '/api/training/redo'],
    ])
    const ids = rows.map((r) => (r.body as { action_id: string }).action_id)
    for (const id of ids) expect(id).toMatch(ULID)
    expect(new Set(ids).size).toBe(4)
    expect(rows[0].body).toMatchObject({ date: '2026-10-22' })
    expect(rows[1].body).toMatchObject({ accept: true })
    expect(rows[2].body).toMatchObject({ accept: false })
  })

  it("gate 1's answers carry no id: a reason is kept per week, a flare-up per week", async () => {
    const db = store()
    await gate1Reason(db, '2026-10-12', 'travel_illness')
    await gate1Flare(db)
    expect(await bodies(db)).toEqual([
      ['gate1', '/api/training/gate1/reason', { monday: '2026-10-12', reason: 'travel_illness' }],
      ['gate1', '/api/training/gate1/flare', {}],
    ])
  })

  it('the same answer sent again by the outbox is the same body, id included', async () => {
    const db = store()
    await answerCarry(db, true)
    const sent: unknown[] = []
    let first = true
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      sent.push(JSON.parse(String(init?.body)))
      // The answer of the first send is lost: the engine stored it, the phone never heard.
      if (first) {
        first = false
        return new Response(JSON.stringify({ error: 'engine_unavailable' }), { status: 503 })
      }
      return new Response(JSON.stringify({ stored: true }), { status: 200 })
    })
    const t0 = new Date()
    await drain(db, { key: 'k', engineDown: false, fetchImpl, now: () => t0 })
    await drain(db, { key: 'k', engineDown: false, fetchImpl, now: () => new Date(t0.getTime() + 60_000) })
    expect(sent).toHaveLength(2)
    expect(sent[1]).toEqual(sent[0])
    expect(await db.outbox.count()).toBe(0)
  })
})

describe('a refused answer', () => {
  const row = (kind: string, state: OutboxRow['state'], last_error?: string): OutboxRow => ({
    id: 'X', kind, method: 'POST', path: '/api/training/swap', body: {}, day: '2026-10-20',
    created_at: '2026-10-20T07:00:00Z', attempts: 1, next_at: '2026-10-20T07:00:00Z', state, last_error,
  })

  it("says why in the screen's words, with the rule's own words after", () => {
    expect(refusalText(row('swap', 'failed', 'refused: day 5 would land in week 2'))).toBe(
      S.week.refused(S.week.answerName.swap, S.week.refusedWhy.refused, 'day 5 would land in week 2'))
    expect(refusalText(row('carry', 'failed', 'nothing_to_carry'))).toBe(
      S.week.refused(S.week.answerName.carry, S.week.refusedWhy.nothing_to_carry, ''))
    // A code the screen has no words for is shown as the engine sent it.
    expect(refusalText(row('redo', 'failed', 'made_up_code'))).toBe(
      S.week.refused(S.week.answerName.redo, '', 'made_up_code'))
  })

  it('is cleared by the owner; a waiting answer, a session save and a check-in never are', async () => {
    const db = store()
    const add = async (kind: string, state: OutboxRow['state']) => {
      const id = await enqueue(db, { kind, method: 'POST', path: `/api/${kind}`, body: {} })
      await db.outbox.where('id').equals(id).modify({ state })
      return (await db.outbox.where('id').equals(id).first())!
    }
    const refusedSwap = await add('swap', 'failed')
    const waitingSwap = await add('swap', 'waiting')
    const refusedSession = await add('session', 'failed')
    const refusedCheckin = await add('checkin', 'failed')
    for (const r of [refusedSwap, waitingSwap, refusedSession, refusedCheckin]) await clearRefused(db, r)
    expect((await db.outbox.toArray()).map((r) => r.kind).sort()).toEqual(['checkin', 'session', 'swap'])
    expect(isSchedule('swap') && isSchedule('gate1') && !isSchedule('session') && !isSchedule('yoga')).toBe(true)
  })
})

describe("the engine's answer, for the screen that waits on it", () => {
  it('is kept by the item id once the item is sent', async () => {
    const db = store()
    const id = await enqueue(db, { kind: 'yoga', method: 'POST', path: '/api/training/yoga', body: {} })
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ logged: false }), { status: 200 }))
    await drain(db, { key: 'k', engineDown: false, fetchImpl })
    expect(answerOf(id)).toEqual({ logged: false })
    expect(await db.outbox.count()).toBe(0)
  })

  it('keeps only the newest answers', async () => {
    const db = store()
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ stored: true }), { status: 200 }))
    const ids: string[] = []
    for (let i = 0; i <= ANSWERS_KEPT; i++) {
      ids.push(await enqueue(db, { kind: 'yoga', method: 'POST', path: '/api/training/yoga', body: { i } }))
    }
    await drain(db, { key: 'k', engineDown: false, fetchImpl })
    expect(answerOf(ids[0])).toBeUndefined()
    expect(answerOf(ids[ids.length - 1])).toEqual({ stored: true })
  })
})
