// The training session on the phone (rebuild Phase 6): one pure state and the taps that
// move it. The session lives in the phone's database from Start to Save (lib/session.ts),
// so it survives a reload, an app kill and an app update, and needs no network until Save.
//
// THE PHONE HOLDS NO RULE. The engine sends the session whole at Start (GET
// /api/training/session): every exercise as dosed today with its seeded numbers, and the
// guided flow walked in advance (`steps`: each position, the event that leaves it, what
// that event records, and the bell a hold's timer rings). The phone walks that list: a
// tap moves to the next entry, Skip to the entry's `skip_to`. It records each set's RAW
// facts — when it was done (the phone's clock, with its UTC offset), each side's numbers,
// the clock readings around the rest that followed — and the engine builds the records
// at Save (session_save.records_from_raw). The steppers move by the engine's increment
// and over the engine's band tiers.
import type { components } from '../generated/api'
import type { Timer } from './timers'

type Schemas = components['schemas']
export type Plan = Schemas['SessionPlanOut']
export type Exercise = Schemas['SessionExercise']
export type FlowStep = Schemas['FlowStep']
export type HeartRate = Schemas['HeartRateOut']
export type Side = 'right' | 'left'

/** A walk's or run's minutes from the watch (T75): found, none of that length today, or
 *  not asked yet because there was no connection when the activity ended (the save screen
 *  asks again). */
export type GarminPull =
  | { state: 'found'; minutes: number; detail: Record<string, unknown> | null }
  | { state: 'none' }
  | { state: 'pending' }

/** One side's live numbers. */
export interface SideValues {
  reps: number | null
  weight_kg: number | null
  seconds: number | null
}

/** One exercise's steppers: each side's own numbers, and the band. Each side starts a set
 *  from its own last set, and a change to one side never changes the other (WP-25, the
 *  owner's note of 2026-10-22: "Uncouple the right and the left so you can change the reps
 *  of both after use"). Until then an unedited second side followed the first. */
export interface Live {
  right: SideValues
  left: SideValues
  band_tier: string | null
}

/** One set as the phone saw it; the engine builds the record (RawSetIn). */
export interface RawSet {
  set_num: number
  completed_at: string
  right?: Partial<SideValues>
  left?: Partial<SideValues>
  band_tier?: string | null
  rest_started_at?: number
  rest_ended_at?: number
}

export interface Snapshot {
  step: number
  live: Record<number, Live>
  sets: Record<number, RawSet[]>
  /** The steps in the order they ran then, when an exercise was moved since (WP-27). */
  steps?: FlowStep[]
}

export interface TrainingState {
  version: 1
  plan: Plan
  sessionId: string
  exerciseIds: string[]
  /** The entry of plan.steps the flow is on; steps.length when every exercise is behind it. */
  step: number
  live: Record<number, Live>
  sets: Record<number, RawSet[]>
  notes: Record<number, string>
  /** The clock (epoch ms) at the first completion tap (a side, a rep, a set or an
   *  activity, as the Training page's clock starts): the session's length counts from it. */
  firstSetAt: number | null
  /** The clock at the last completion tap. */
  lastSetAt: number | null
  /** Up to UNDO_LIMIT earlier positions, newest last (the flow's Back). */
  history: Snapshot[]
  /** The running timer and the entry it belongs to; kept, so a reload shows it right. */
  timer: { step: number; t: Timer } | null
  /** The session is over and the save screen shows. */
  saving: boolean
  /** The outbox id of the save, once Save was pressed (the save waits there until the
   *  engine confirms it), with the body it holds. */
  savedId: string | null
  /** The athlete started a Garmin workout for this session (T42): the save screen checks
   *  the watch, and the heart-rate match runs after the save. */
  garminDeclared: boolean
  /** A walk's or run's minutes from the watch, by exercise index (T75). */
  garmin: Record<number, GarminPull>
  /** A line for the next screen only (the watch's minutes). */
  notice: string | null
  /** What Save stored: the rating, the length and the notes (the heart-rate match reads
   *  them, and the saved screen words them). */
  saved: { rpe: number; minutes: number; notes: string } | null
  /** The heart-rate match's answer after the save (T97-T101), kept across a reload. */
  hr: HeartRate | null
}

/** How many taps Back can undo (the Streamlit flow's limit, T78). */
export const UNDO_LIMIT = 30

const EMPTY: SideValues = { reps: null, weight_kg: null, seconds: null }

/** The steppers' starting values: the engine's seeded entry, else the prescription. */
export function startingLive(ex: Exercise): Live {
  const entry = (ex.entry ?? {}) as Record<string, unknown>
  const num = (v: unknown) => (typeof v === 'number' ? v : null)
  const reps = num(entry.reps) ?? (ex.type === 'hold_reps' ? ex.reps_in_set ?? null : ex.reps ?? null)
  const weight = num(entry.weight_kg) ?? ex.weight_kg ?? null
  const side: SideValues = { reps, weight_kg: weight, seconds: null }
  const band = (typeof entry.band_tier === 'string' ? entry.band_tier : null) ?? ex.band_tier ?? null
  return { right: { ...side }, left: { ...side }, band_tier: band }
}

/** A session stored before WP-25 kept `secondEdited`, and its unedited second side showed
 *  the first side's numbers. Keep the numbers it showed, then drop the flag. */
function uncoupled(live: Record<number, Live & { secondEdited?: boolean }>, first: Side): Record<number, Live> {
  const second: Side = first === 'right' ? 'left' : 'right'
  return Object.fromEntries(Object.entries(live).map(([idx, l]) => {
    const { secondEdited, ...rest } = l
    const kept: Live = secondEdited === false
      ? { ...rest, [second]: { ...rest[first], seconds: rest[second].seconds } }
      : rest
    return [idx, kept]
  }))
}

export function startSessionState(plan: Plan, sessionId: string, exerciseIds: string[],
  garminDeclared = false): TrainingState {
  if (exerciseIds.length !== plan.exercises.length) throw new Error('one id per exercise')
  return {
    version: 1,
    plan,
    sessionId,
    exerciseIds,
    step: 0,
    live: Object.fromEntries(plan.exercises.map((ex) => [ex.index, startingLive(ex)])),
    sets: {},
    notes: {},
    firstSetAt: null,
    lastSetAt: null,
    history: [],
    timer: null,
    saving: false,
    savedId: null,
    garminDeclared,
    garmin: {},
    notice: null,
    saved: null,
    hr: null,
  }
}

/** The stored session as this version reads it: a field a session stored by an earlier
 *  version lacks takes its starting value. Null for anything that is not a session. */
export function loadState(data: unknown): TrainingState | null {
  const s = data as Partial<TrainingState> | null
  if (!s || s.version !== 1 || !s.plan) return null
  const first = s.plan.first_side as Side
  return {
    garminDeclared: false, garmin: {}, notice: null, saved: null, hr: null,
    ...s,
    live: uncoupled(s.live ?? {}, first),
    history: (s.history ?? []).map((h) => ({ ...h, live: uncoupled(h.live, first) })),
  } as TrainingState
}

/** The timer of the entry the flow is on, or null when it belongs to another entry. */
export function timerHere(s: TrainingState): Timer | null {
  return s.timer && s.timer.step === s.step ? s.timer.t : null
}

export function withTimer(s: TrainingState, t: Timer | null): TrainingState {
  return { ...s, timer: t ? { step: s.step, t } : null }
}

export function currentStep(s: TrainingState): FlowStep | null {
  return s.plan.steps[s.step] ?? null
}

export function finished(s: TrainingState): boolean {
  return s.step >= s.plan.steps.length
}

export function exerciseOf(s: TrainingState, step: FlowStep | null = currentStep(s)): Exercise | null {
  return step ? s.plan.exercises[step.ex_idx] ?? null : null
}

/** The phone's clock as the set records carry it: ISO with the phone's own UTC offset. */
export function localStamp(ms: number): string {
  const d = new Date(ms)
  const pad = (n: number, w = 2) => String(Math.abs(n)).padStart(w, '0')
  const offset = -d.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    + `${sign}${pad(Math.floor(Math.abs(offset) / 60))}:${pad(Math.abs(offset) % 60)}`
}

/** One side's own numbers (WP-25: the sides never follow each other). */
export function sideValues(live: Live, side: Side): SideValues {
  return live[side]
}

/** The set just done: the exercise's recorded set with the highest number, or null. */
export function lastRecorded(s: TrainingState, exIdx: number): RawSet | null {
  const rows = s.sets[exIdx] ?? []
  return rows.length ? rows.reduce((a, b) => (b.set_num > a.set_num ? b : a)) : null
}

function snapshot(s: TrainingState): Snapshot {
  return { step: s.step, live: structuredClone(s.live), sets: structuredClone(s.sets), steps: s.plan.steps }
}

function remember(s: TrainingState): Snapshot[] {
  return [...s.history, snapshot(s)].slice(-UNDO_LIMIT)
}

/** The step's event (complete, or next_set to end a rest) at `now` (epoch ms). */
export function advance(s: TrainingState, now: number): TrainingState {
  const step = currentStep(s)
  if (!step) return s
  const sets = structuredClone(s.sets)
  let firstSetAt = s.firstSetAt
  let lastSetAt = s.lastSetAt
  if (step.rest_ends) {
    // The rest that just ended belongs to the set whose completion began it.
    const rows = sets[step.ex_idx] ?? []
    const open = [...rows].reverse().find((r) => r.rest_started_at != null && r.rest_ended_at == null)
    if (open) open.rest_ended_at = now / 1000
  }
  if (step.record_set != null) {
    const live = s.live[step.ex_idx]
    const ex = s.plan.exercises[step.ex_idx]
    const right = sideValues(live, 'right')
    const left = sideValues(live, 'left')
    const record: RawSet = {
      set_num: step.record_set,
      completed_at: localStamp(now),
      right: { ...right },
      ...(ex.laterality === 'unilateral' ? { left: { ...left } } : {}),
      ...(live.band_tier ? { band_tier: live.band_tier } : {}),
      ...(step.rest_begins ? { rest_started_at: now / 1000 } : {}),
    }
    const rows = (sets[step.ex_idx] ?? []).filter((r) => r.set_num !== record.set_num)
    sets[step.ex_idx] = [...rows, record]
  }
  if (step.event === 'complete') {
    firstSetAt ??= now
    lastSetAt = now
  }
  return { ...s, history: remember(s), step: s.step + 1, sets, firstSetAt, lastSetAt, notice: null }
}

/** The watch's answer for a walk or run (T75), kept with the session. */
export function setGarmin(s: TrainingState, exIdx: number, pull: GarminPull, notice: string | null): TrainingState {
  return { ...s, garmin: { ...s.garmin, [exIdx]: pull }, notice }
}

/** Skip the rest of this exercise: on to the next exercise's first entry (T79). */
export function skip(s: TrainingState): TrainingState {
  const step = currentStep(s)
  if (!step) return s
  return { ...s, history: remember(s), step: step.skip_to, notice: null }
}

/** Back: the position and the numbers before the last tap (T78). */
export function back(s: TrainingState): TrainingState {
  const last = s.history[s.history.length - 1]
  if (!last) return s
  const plan = last.steps ? { ...s.plan, steps: last.steps } : s.plan
  return { ...s, plan, step: last.step, live: last.live, sets: last.sets, history: s.history.slice(0, -1) }
}

/** The order the exercises run in now: each exercise's index, by its first entry in the
 *  steps (the engine's walk, with any group moved since, WP-27). */
export function exerciseOrder(s: TrainingState): number[] {
  const order: number[] = []
  for (const st of s.plan.steps) if (!order.includes(st.ex_idx)) order.push(st.ex_idx)
  return order
}

const groupOf = (s: TrainingState, exIdx: number) => s.plan.exercises[exIdx]?.move ?? null

/** The exercises that may run now, before the one the flow is on ("Machine busy", WP-27):
 *  only at the first entry of a group that moves, before any of its sets; each a later
 *  group that moves and whose `after` groups have all run. One exercise names each group:
 *  its last (the lift, not its ramp). The engine sent the groups; nothing is decided here. */
export function doFirstCandidates(s: TrainingState): { group: number; exercise: Exercise }[] {
  const step = currentStep(s)
  if (!step || step.phase === 'resting') return []
  const here = groupOf(s, step.ex_idx)
  if (!here?.movable) return []
  if (s.plan.steps.findIndex((st) => groupOf(s, st.ex_idx)?.group === here.group) !== s.step) return []
  const ran = new Set(s.plan.steps.slice(0, s.step).map((st) => groupOf(s, st.ex_idx)?.group))
  const named = new Map<number, number>()
  for (const st of s.plan.steps.slice(s.step)) {
    const g = groupOf(s, st.ex_idx)
    if (g && g.group !== here.group && g.movable && g.after.every((a) => ran.has(a))) named.set(g.group, st.ex_idx)
  }
  return [...named].map(([group, exIdx]) => ({ group, exercise: s.plan.exercises[exIdx] }))
}

/** The steps numbered again after a move: each entry's place, and Skip's target, the next
 *  exercise's first entry (the walk's own skip_to, over the new order). */
function renumbered(steps: FlowStep[]): FlowStep[] {
  const firstOf = new Map<number, number>()
  steps.forEach((st, i) => { if (!firstOf.has(st.ex_idx)) firstOf.set(st.ex_idx, i) })
  const order = [...firstOf.keys()]
  return steps.map((st, i) => {
    const next = order[order.indexOf(st.ex_idx) + 1]
    return { ...st, index: i, skip_to: next === undefined ? steps.length : firstOf.get(next)! }
  })
}

/** Run `group` now (WP-27): its steps move, in one block, in front of the group the flow is
 *  on, which then comes straight after it. Back undoes the move. */
export function doFirst(s: TrainingState, group: number): TrainingState {
  const steps = s.plan.steps
  const moving = steps.filter((st, i) => i >= s.step && groupOf(s, st.ex_idx)?.group === group)
  if (!moving.length) return s
  const rest = steps.filter((st, i) => !(i >= s.step && groupOf(s, st.ex_idx)?.group === group))
  const next = renumbered([...rest.slice(0, s.step), ...moving, ...rest.slice(s.step)])
  return { ...s, history: remember(s), plan: { ...s.plan, steps: next }, timer: null, notice: null }
}

/** Change one side's numbers (reps, weight or held seconds). The other side keeps its own. */
export function setSide(s: TrainingState, exIdx: number, side: Side, patch: Partial<SideValues>): TrainingState {
  const live = s.live[exIdx]
  const next: Live = { ...live, [side]: { ...live[side], ...patch } }
  return { ...s, live: { ...s.live, [exIdx]: next } }
}

/** Change one side of a set already recorded (in the rest after it, WP-25): the set's own
 *  record, and that side's live numbers, so the next set starts from what was done. */
export function setRecordedSide(s: TrainingState, exIdx: number, setNum: number, side: Side,
  patch: Partial<SideValues>): TrainingState {
  const rows = (s.sets[exIdx] ?? []).map((r) =>
    r.set_num === setNum ? { ...r, [side]: { ...(r[side] ?? {}), ...patch } } : r)
  const moved = setSide(s, exIdx, side, patch)
  return { ...moved, sets: { ...s.sets, [exIdx]: rows } }
}

export function setBand(s: TrainingState, exIdx: number, band: string): TrainingState {
  return { ...s, live: { ...s.live, [exIdx]: { ...s.live[exIdx], band_tier: band } } }
}

export function setNote(s: TrainingState, exIdx: number, note: string): TrainingState {
  return { ...s, notes: { ...s.notes, [exIdx]: note } }
}

/** One weight step by the engine's increment, snapped to whole increments, never below 0. */
export function stepWeight(weight: number | null, direction: 1 | -1, increment: number | null): number {
  const inc = increment && increment > 0 ? increment : 1
  const stepped = Math.round(((weight ?? 0) + direction * inc) / inc) * inc
  return Math.max(0, Math.round(stepped * 100) / 100)
}

/** One band along the engine's tiers, clamped at both ends. */
export function stepBand(band: string | null, direction: 1 | -1, tiers: readonly string[]): string | null {
  if (!tiers.length) return band
  const at = Math.max(0, tiers.indexOf(band ?? tiers[0]))
  return tiers[Math.max(0, Math.min(tiers.length - 1, at + direction))]
}

/** The minutes the save's clock reads: from the first set to `end`, at least the plan's
 *  floor; the modelled minutes when no set was ever completed. */
export function clockMinutes(s: TrainingState, end: number): number {
  if (s.firstSetAt == null) return s.plan.model_minutes
  return Math.max(s.plan.min_minutes, Math.floor((end - s.firstSetAt) / 60_000))
}

/** Whether the save asks which length to keep: the engine's threshold, sent with the plan. */
export function asksLength(s: TrainingState, minutes: number): boolean {
  const above = s.plan.ask_length_above_minutes
  return above != null && minutes > above
}

/** The complete session for POST /api/training/sessions (SessionSaveIn): every exercise in
 *  the order trained, with its plan fields, its steppers, its raw sets and its note. */
export function saveBody(s: TrainingState, minutes: number, rpe: number, notes: string): Schemas['SessionSaveIn'] {
  return {
    session_id: s.sessionId,
    date: s.plan.date,
    kind: s.plan.kind,
    duration_minutes: Math.max(1, Math.round(minutes)),
    session_rpe: rpe,
    notes,
    // The session's own note (the accessory session's): the engine stores it before `notes`.
    plan_note: s.plan.note ?? '',
    // In the order trained (WP-27): an exercise moved by "Machine busy" goes where it ran.
    exercises: exerciseOrder(s).map((i) => {
      const ex = s.plan.exercises[i]
      const live = s.live[ex.index]
      const right = sideValues(live, 'right')
      return {
        exercise_id: s.exerciseIds[i],
        exercise: ex as unknown as Record<string, unknown>,
        // The steppers' final values (the main pair); each side's own numbers ride in
        // the raw sets, where the engine maps them.
        actual: { reps: right.reps, weight_kg: right.weight_kg, band_tier: live.band_tier },
        sets: [],
        raw_sets: (s.sets[ex.index] ?? []).map((r) => ({ ...r, right: r.right ?? null, left: r.left ?? null })),
        note: s.notes[ex.index] ?? '',
        // The watch's minutes for a walk or run, when it had them (T75).
        garmin_minutes: pulled(s, ex.index)?.minutes ?? null,
        garmin_detail: pulled(s, ex.index)?.detail ?? null,
      }
    }),
  }
}

function pulled(s: TrainingState, exIdx: number) {
  const pull = s.garmin[exIdx]
  return pull?.state === 'found' ? pull : null
}

/** Where the flow is in today's list: the exercises behind it, and the one it is on. */
export function exerciseProgress(s: TrainingState): { done: number; total: number } {
  const step = currentStep(s)
  const order = exerciseOrder(s)
  return { done: step ? order.indexOf(step.ex_idx) : order.length, total: order.length }
}

/** A session id in the Training page's shape (the date, then 8 hex digits), minted once. */
export function newSessionId(day: string): string {
  const bytes = crypto.getRandomValues(new Uint8Array(4))
  return `${day}-${Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')}`
}

export function newExerciseIds(n: number): string[] {
  return Array.from({ length: n }, () => crypto.randomUUID())
}

export { EMPTY as EMPTY_SIDE }
