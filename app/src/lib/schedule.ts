// The schedule answers (rebuild Phase 7): a swap with today, the missed-session carry, the
// readiness shift, the Monday redo and gate 1's two answers. Nothing moves until the owner
// answers (his rule, 2026-08-07); each answer is a write through the outbox, and the engine
// re-checks every rule against what is stored when it arrives.
//
// A swap, a carry, a shift and a redo carry an id the phone mints for the answer
// (action_id): the engine applies an id once, so the outbox may send an answer again after
// a lost answer (a swap applied twice would put the two days back where they were). Gate
// 1's answers need none: a reason is kept per week, and a flare-up per week.
//
// While an answer waits, its question is not asked again; when the engine confirms it, the
// week is read again; when the engine refuses it, the page says why and the owner clears it.
import { useLiveQuery } from 'dexie-react-hooks'
import { useEffect, useRef, useState } from 'react'
import type { HealthDB, OutboxRow } from '../db/schema'
import { S } from '../strings'
import { enqueue } from './outbox'
import { ulid } from './ulid'

export const SCHEDULE_KINDS = ['swap', 'carry', 'shift', 'redo', 'gate1'] as const
export type ScheduleKind = (typeof SCHEDULE_KINDS)[number]

export function isSchedule(kind: string): kind is ScheduleKind {
  return (SCHEDULE_KINDS as readonly string[]).includes(kind)
}

/** The kinds whose answer the engine applies once by its id. */
const ONCE: readonly ScheduleKind[] = ['swap', 'carry', 'shift', 'redo']

export async function sendAnswer(store: HealthDB, kind: ScheduleKind, path: string,
  body: Record<string, unknown> = {}): Promise<string> {
  const sent = ONCE.includes(kind) ? { ...body, action_id: ulid() } : body
  return enqueue(store, { kind, method: 'POST', path, body: sent })
}

export const swapWithToday = (store: HealthDB, day: string) =>
  sendAnswer(store, 'swap', '/api/training/swap', { date: day })
export const answerCarry = (store: HealthDB, accept: boolean) =>
  sendAnswer(store, 'carry', '/api/training/carry', { accept })
export const answerShift = (store: HealthDB, accept: boolean) =>
  sendAnswer(store, 'shift', '/api/training/shift', { accept })
export const redoWeek = (store: HealthDB) => sendAnswer(store, 'redo', '/api/training/redo')
export const gate1Reason = (store: HealthDB, monday: string, reason: string) =>
  sendAnswer(store, 'gate1', '/api/training/gate1/reason', { monday, reason })
export const gate1Flare = (store: HealthDB) => sendAnswer(store, 'gate1', '/api/training/gate1/flare')

/** The schedule answers still in the outbox: waiting to send, or refused. */
export function useScheduleAnswers(store: HealthDB): OutboxRow[] {
  return useLiveQuery(async () => (await store.outbox.orderBy('seq').toArray()).filter((r) => isSchedule(r.kind)),
    [store], [] as OutboxRow[])
}

/** A count that goes up each time the engine confirms a schedule answer (a waiting answer
 *  left the outbox): the week and the day are read again on it, because the schedule
 *  changed. A refused answer the owner clears does not count. */
export function useConfirmed(rows: OutboxRow[]): number {
  const seen = useRef(new Map<string, OutboxRow['state']>())
  const [count, setCount] = useState(0)
  useEffect(() => {
    const now = new Map(rows.map((r) => [r.id, r.state]))
    let confirmed = false
    for (const [id, state] of seen.current) if (!now.has(id) && state === 'waiting') confirmed = true
    seen.current = now
    if (confirmed) setCount((c) => c + 1)
  }, [rows])
  return count
}

/** Clear a refused schedule answer once its reason is read. An answer holds no data the
 *  owner typed, so nothing is lost: a refused session or check-in is never cleared here. */
export async function clearRefused(store: HealthDB, row: OutboxRow): Promise<void> {
  if (row.state !== 'failed' || !isSchedule(row.kind) || row.seq === undefined) return
  await store.outbox.delete(row.seq)
}

/** Why the engine refused an answer, in the screen's words: the engine's code, then the
 *  rule's own words after ": " (each blocker, each refusal). */
export function refusalText(row: OutboxRow): string {
  const raw = row.last_error ?? ''
  const cut = raw.indexOf(': ')
  const code = cut < 0 ? raw : raw.slice(0, cut)
  const detail = cut < 0 ? '' : raw.slice(cut + 2)
  const what = S.week.answerName[row.kind] ?? S.week.answerName.other
  const why = S.week.refusedWhy[code]
  return S.week.refused(what, why ?? '', detail || (why ? '' : code))
}
