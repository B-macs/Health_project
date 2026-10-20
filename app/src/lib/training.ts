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

type Schemas = components['schemas']
export type Plan = Schemas['SessionPlanOut']
export type Exercise = Schemas['SessionExercise']
export type FlowStep = Schemas['FlowStep']
export type Side = 'right' | 'left'

/** One side's live numbers. */
export interface SideValues {
  reps: number | null
  weight_kg: number | null
  seconds: number | null
}

/** One exercise's steppers: each side's numbers, the band, and whether the second side
 *  was edited (an unedited second side follows the first). */
export interface Live {
  right: SideValues
  left: SideValues
  band_tier: string | null
  secondEdited: boolean
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
  return { right: { ...side }, left: { ...side }, band_tier: band, secondEdited: false }
}

export function startSessionState(plan: Plan, sessionId: string, exerciseIds: string[]): TrainingState {
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
  }
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

/** The second side's numbers: the first side's until the second was edited (T68). */
export function sideValues(live: Live, side: Side, first: Side): SideValues {
  if (side === first || live.secondEdited) return live[side]
  return { ...live[first], seconds: live[side].seconds }
}

function snapshot(s: TrainingState): Snapshot {
  return { step: s.step, live: structuredClone(s.live), sets: structuredClone(s.sets) }
}

function remember(s: TrainingState): Snapshot[] {
  return [...s.history, snapshot(s)].slice(-UNDO_LIMIT)
}

/** The step's event (complete, or next_set to end a rest) at `now` (epoch ms). */
export function advance(s: TrainingState, now: number): TrainingState {
  const step = currentStep(s)
  if (!step) return s
  const first = s.plan.first_side as Side
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
    const right = sideValues(live, 'right', first)
    const left = sideValues(live, 'left', first)
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
  return { ...s, history: remember(s), step: s.step + 1, sets, firstSetAt, lastSetAt }
}

/** Skip the rest of this exercise: on to the next exercise's first entry (T79). */
export function skip(s: TrainingState): TrainingState {
  const step = currentStep(s)
  if (!step) return s
  return { ...s, history: remember(s), step: step.skip_to }
}

/** Back: the position and the numbers before the last tap (T78). */
export function back(s: TrainingState): TrainingState {
  const last = s.history[s.history.length - 1]
  if (!last) return s
  return { ...s, step: last.step, live: last.live, sets: last.sets, history: s.history.slice(0, -1) }
}

/** Change one side's numbers (reps, weight or held seconds). Editing the second side
 *  stops it following the first. */
export function setSide(s: TrainingState, exIdx: number, side: Side, patch: Partial<SideValues>): TrainingState {
  const live = s.live[exIdx]
  const first = s.plan.first_side as Side
  const second = side !== first
  const base = second && !live.secondEdited ? sideValues(live, side, first) : live[side]
  const next: Live = {
    ...live,
    [side]: { ...base, ...patch },
    secondEdited: live.secondEdited || (second && (patch.reps !== undefined || patch.weight_kg !== undefined)),
  }
  return { ...s, live: { ...s.live, [exIdx]: next } }
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
  const first = s.plan.first_side as Side
  return {
    session_id: s.sessionId,
    date: s.plan.date,
    kind: s.plan.kind,
    duration_minutes: Math.max(1, Math.round(minutes)),
    session_rpe: rpe,
    notes,
    exercises: s.plan.exercises.map((ex, i) => {
      const live = s.live[ex.index]
      const right = sideValues(live, 'right', first)
      return {
        exercise_id: s.exerciseIds[i],
        exercise: ex as unknown as Record<string, unknown>,
        // The steppers' final values (the main pair); each side's own numbers ride in
        // the raw sets, where the engine maps them.
        actual: { reps: right.reps, weight_kg: right.weight_kg, band_tier: live.band_tier },
        sets: [],
        raw_sets: (s.sets[ex.index] ?? []).map((r) => ({ ...r, right: r.right ?? null, left: r.left ?? null })),
        note: s.notes[ex.index] ?? '',
        garmin_minutes: null,
        garmin_detail: null,
      }
    }),
  }
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
