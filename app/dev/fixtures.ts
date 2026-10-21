// Made-up engine answers for the mock API (rebuild Phase 5): Today, its week, the day's
// plan, the three detail screens and the check-in form, for any day. Every number is
// invented from the date; nothing comes from a real reading. Typed against the engine's
// contract (src/generated/api.ts), so a change in the contract breaks this file's type
// check instead of a browser test.
import type { components } from '../src/generated/api'
import session from './session_fixture.json' with { type: 'json' }

type Schemas = components['schemas']

const DAY_MS = 86_400_000

export function addDays(day: string, n: number): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + n * DAY_MS).toISOString().slice(0, 10)
}

function seed(day: string): number {
  return Math.floor(Date.parse(`${day}T00:00:00Z`) / DAY_MS)
}

/** The day shown: never after the caller's day; a pick lasts the day it was made on. */
export function opening(requested: string | null, pickedOn: string | null, local: string): string {
  if (!requested || requested >= local) return local
  if (pickedOn !== null && pickedOn !== local) return local
  return requested
}

/** One day in five has no Sleep Score (the screen's all-or-nothing rule has a case). */
export const unscored = (day: string) => seed(day) % 5 === 0

const readinessOf = (day: string) => 55 + (seed(day) * 7) % 40
const sleepOf = (day: string) => (unscored(day) ? null : 60 + (seed(day) * 11) % 35)
const strainOf = (day: string) => Math.round((4 + (seed(day) * 3) % 14) * 10) / 10
const band = (v: number | null) => (v == null ? 'No Readings' : v >= 85 ? 'Optimal' : v >= 70 ? 'Good' : v >= 50 ? 'Pay Attention' : 'Rest')

function frame(day: string, local: string) {
  return {
    date: day,
    previous: addDays(day, -1),
    next: day < local ? addDays(day, 1) : null,
    is_today: day === local,
    date_label: day === local ? 'TODAY' : day,
    bio_failed: false,
  }
}

export function today(day: string, local: string): Schemas['TodayOut'] {
  const r = readinessOf(day)
  const s = sleepOf(day)
  const t = strainOf(day)
  return {
    ...frame(day, local),
    readiness: {
      daily: r, trend: r - 2, headline: r, colour: '', label: band(r), header: 'Ready to train',
      description: 'Made-up numbers for the browser tests.', tertiary: '', scale: 100,
      pair: [{ title: 'DAILY', value: String(r) }, { title: 'TREND', value: String(r - 2) }],
    },
    sleep: {
      score: s, display: s == null ? '--' : String(s), label: band(s), header: s == null ? 'Sleep data missing' : 'Well rested',
      description: '', colour: '', need_hours: 8, base_window: null, scale: 100,
    },
    strain: {
      value: t, display: t.toFixed(1), label: t < 8 ? 'Light' : t < 12 ? 'Moderate' : 'Hard', header: 'Training load',
      description: '', colour: '', card_label: 'STRAIN', is_rolling: false, unscored_reason: '', scale: 21,
      rest_day: false, seven_day: null,
    },
    verdict: day === local
      ? { badge: '', banner_kind: '', banner_text: '', cause: '', has_something_to_say: false, hrv_note: '', reduced: false, tone: '' }
      : null,
    hrv_7d: [40, 42, 41, null, 44, 43, 45],
    rhr_7d: [55, 54, 56, 55, null, 54, 53],
  }
}

export function week(day: string, local: string): Schemas['TodayWeekOut'] {
  const end = Math.round((Date.parse(local) - Date.parse(day)) / DAY_MS) < 7 ? local : day
  return {
    date: day,
    days: Array.from({ length: 7 }, (_, i) => {
      const d = addDays(end, i - 6)
      return { date: d, readiness: readinessOf(d), label: band(readinessOf(d)), is_today: d === local, selected: d === day }
    }),
  }
}

export function trainingDay(day: string, local: string, scenario: ReadonlySet<string> = new Set()): Schemas['TrainingDayOut'] {
  const base = { date: day, gap: null, logged: null, note: null, overview: null, phase: null, phases_error: null, planned: null, rest: null, swap: null }
  if (scenario.has('unreadable')) return { ...base, route: 'phases_unreadable', phases_error: 'made-up' }
  if (scenario.has('gap')) return { ...base, route: 'no_phase', gap: gapOf(local) }
  if (day !== local) {
    const phase = phaseOf(local, day)
    const marker = markerOf(day, local)
    if (marker === 'rest') return { ...base, route: 'rest', phase, rest: { is_today: false, yoga_suggestion: YOGA_SUGGESTION } }
    if (marker === 'done') {
      return { ...base, route: 'past_completed', phase, logged: { au: 300, minutes: 52, rpe: 6, exercises: [{ name: 'Made-up squat', movement_type: null, planned_sets: 3 }] } }
    }
    const missed = marker === 'missed'
    return {
      ...base, route: missed ? 'past_missed' : 'future', phase,
      note: missed ? null : { text: 'Made-up: moved from Monday for the tests.', moved: true },
      planned: { day_num: phase.day_num ?? 1, plan_days: 84, objective: `Made-up session ${weekday(day) + 1}`, rpe_target: 7,
        exercises: [lineOf('Made-up hack squat', '3 × 8-12'), lineOf('Made-up chest press', '3 × 8-12')],
        home: missed ? [] : [lineOf('Made-up home stretch', '2 × 30 s', 'Made-up how-to for the tests.')] },
      swap: scenario.has('blocked')
        ? { available: false, check_failed: false, blockers: ['made-up: today already has a logged session'], warnings: [], today_objective: '' }
        : { available: true, check_failed: false, blockers: [], warnings: missed ? [] : ['Made-up warning: two main sessions in a row.'], today_objective: session.objective },
    }
  }
  // Today's overview is the session fixture's own day (dev/session_fixture.json, made by the
  // engine's walk), so the overview and the session that Start opens agree.
  const line = lineOf
  const days = session.plan_days ?? 84
  const dayNum = session.day_num ?? 1
  if (scenario.has('rest_today')) {
    return { ...base, route: 'rest', phase: phaseOf(local, local), rest: { is_today: true, yoga_suggestion: YOGA_SUGGESTION } }
  }
  return {
    ...base,
    route: 'today',
    phase: phaseOf(local, local),
    overview: {
      screen: 'overview', headline: 'Made-up session', subtitle: 'Made-up subtitle for the tests.', phase_name: session.phase,
      day_num: dayNum, plan_days: days,
      card: { exercise_count: session.exercises.length, minutes: session.model_minutes, focus: ['Made-up focus'], loaded: true, rpe_target: session.rpe_target ?? 7 },
      main: session.exercises.map((e) => line(e.name, e.prescription)),
      home: [line('Made-up home stretch', '2 × 30 s', 'Made-up how-to for the tests.')],
      release: [], adaptation: null,
      banner: { kind: 'warning', text: 'Made-up reduced-load banner for the tests.', cause: '', acwr_advisory: '' },
      first_side: session.first_side, first_side_note: 'Start each one-side exercise on the left side today.',
      objective: session.objective,
    },
  }
}

const AXIS: Schemas['ValueAxis'] = { lo: 40, hi: 100, step: 20, ticks: [40, 60, 80, 100] }

function trendChart(day: string, title: string, values: (number | null)[]): Schemas['TrendChart'] {
  const dates = values.map((_, i) => addDays(day, i - values.length + 1))
  return {
    title, subtitle: 'Last 30 days', headline: '', unit: '', decimals: 0, empty: false,
    values, dates, axis: AXIS,
    x_labels: [{ at: 0, text: dates[0].slice(5) }, { at: 1, text: dates[dates.length - 1].slice(5) }],
    y_labels: AXIS.ticks.map((t) => ({ at: (AXIS.hi - t) / (AXIS.hi - AXIS.lo), text: String(t) })),
    points: dates.map((d, i) => ({ title: d, rows: [{ label: title, value: String(values[i] ?? '—') }], extra: [], open_date: d })),
  }
}

const trend = (day: string, title: string, of: (d: string) => number | null) =>
  trendChart(day, title, Array.from({ length: 30 }, (_, i) => of(addDays(day, i - 29))))

function contributors(scored: boolean): Schemas['Contributors'] {
  return {
    scored, unscored_reason: scored ? '' : 'The ring recorded no sleep period for this night.', caption: scored ? 'Scored on 7 of 7.' : '',
    rows: scored ? [{ key: 'total', label: 'Total sleep', value_display: '7 h 10 min', weight_display: '35%', bar_pct: 80, colour: '', scored: true }] : [],
  }
}

export function readinessDetail(day: string, local: string): Schemas['ReadinessDetailOut'] {
  const r = readinessOf(day)
  return {
    ...frame(day, local), title: `READINESS · ${frame(day, local).date_label}`, screen_title: 'Readiness History',
    masthead: { colour: '', display: String(r), label: band(r) },
    contributors: { scored: true, unscored_reason: '', caption: 'Scored on 9 of 9.', rows: [
      { key: 'hrv', label: 'HRV balance', value_display: '78', weight_display: '20%', bar_pct: 78, colour: '', scored: true },
    ] },
    key_metrics: [{ label: 'Resting Heart Rate', value: '54 bpm' }, { label: 'Heart Rate Variability', value: '44 ms' }],
    overnight: [],
    trend: trend(day, 'Readiness', readinessOf),
  }
}

export function sleepDetail(day: string, local: string): Schemas['SleepDetailOut'] {
  const s = sleepOf(day)
  const scored = s != null
  const strip: Schemas['Strip'] = {
    codes: '44222111333222111224',
    runs: [{ start: 0, end: 2, code: '4', name: 'Awake' }, { start: 2, end: 5, code: '2', name: 'Light' }, { start: 5, end: 8, code: '1', name: 'Deep' }, { start: 8, end: 11, code: '3', name: 'REM' }, { start: 11, end: 20, code: '2', name: 'Light' }],
    bands: Array.from({ length: 20 }, (_, i) => ({ index: i, left: i / 20, width: 1 / 20, detail: { title: `Slot ${i}`, rows: [], extra: [], open_date: null } })),
  }
  return {
    ...frame(day, local), title: `SLEEP · ${frame(day, local).date_label}`, screen_title: 'Sleep History', mode: scored ? 'scored' : 'unscored',
    masthead: { colour: '', display: s == null ? '--' : String(s), label: band(s) },
    adjusted: false, nights_adjusted: 0, watch_only: null,
    contributors: contributors(scored),
    night: scored
      ? {
          asleep: '7 h 10 min', in_bed: '8 h 02 min', fusion_caption: '', key_metrics: [{ label: 'Efficiency', value: '89%' }],
          debt: { band: 'Low', colour: '', filled: 1, hours: 2.5, threshold: 9.5, value_display: '2.5 h' },
          hypnogram: { empty: false, title: 'Time asleep', source: 'Source: made up', note: 'plain', start: `${day}T23:00:00`, minutes: 480, phantom_minutes: null, x_labels: [{ at: 0, text: '23:00' }, { at: 1, text: '07:00' }], stages: strip, movement: null },
          stages: [{ key: 'deep', code: '1', label: 'Deep', duration: '1 h 30 min', pct: '21%' }],
          naps: null, vitals: [{ label: 'Lowest heart rate', value: '50 bpm' }], overnight: [],
        }
      : null,
    wake: scored ? { label: 'Wake time', caption: 'Correct the wake time Oura recorded.', minutes: 0, editable: true, decrease_to: 0, increase_to: 5, source: 'none' } : null,
    trend: trend(day, 'Sleep Score', sleepOf),
  }
}

export function strainDetail(day: string, local: string, showWeek: boolean): Schemas['StrainDetailOut'] {
  const t = strainOf(day)
  return {
    ...frame(day, local), title: `STRAIN · ${frame(day, local).date_label}`, screen_title: 'Strain History', is_rolling: false, stage_unread: '',
    masthead: { colour: '', display: t.toFixed(1), label: t < 8 ? 'Light' : 'Moderate' },
    region: {
      state: 'split', reason: null, can_show_window: true, showing_week: showWeek, week: showWeek, ceiling: null, mapped_only: true,
      non_additive_note: null, overall: t, regions_total: t, shares_basis: null, shares_version: 1, stage: 2, thin_sample_pct: null,
      tick_pct: null, unattributed_pct: 0, unmapped_names: [], window_days: showWeek ? 7 : 1,
      regions: [
        { id: 'upper_body', name: 'Upper body', short: 'Upper', strain: 5.1, au: 80, au_pct: 30, fill_pct: 40, colour: '', acwr: null },
        { id: 'core', name: 'Core', short: 'Core', strain: 4.2, au: 60, au_pct: 20, fill_pct: 30, colour: '', acwr: null },
        { id: 'lower_body', name: 'Lower body', short: 'Lower', strain: 8.3, au: 160, au_pct: 50, fill_pct: 60, colour: '', acwr: null },
      ],
    },
    source: { kind: 'rpe', label: 'Your session rating only: the watch had no heart rate for this session', hr_rows: [], blend: null },
    hrv_7d: trend(day, 'HRV', () => 44),
    rhr_7d: trend(day, 'Resting heart rate', () => 54),
    trend: trend(day, 'Strain', strainOf),
  }
}

const DEFAULTS: Schemas['CheckInValues'] = {
  current_condition: 'Excellent', tightness_score: 0, pain_score: 0, anatomical_locations: [], sensation_tags: [],
  subjective_tightness: '', alcohol_units: 0, travel_flag: false, psych_stress_score: 1, instability_events: 0,
  bristol_type: 4, unusual_stool_colour: false, hunger_deviation: 0, thirst_intensity: 1, electrolytes_taken: false,
  meditation_minutes: 0, relaxation_depth: 3,
}

export function checkinForm(day: string, local: string, stored: Schemas['CheckInValues'] | undefined): Schemas['CheckInFormOut'] {
  return {
    date: day, options: [0, 1, 2, 3].map((n) => addDays(local, -n)), is_today: day === local,
    existing: stored !== undefined, read_failed: false, values: stored ?? DEFAULTS,
    conditions: ['Excellent', 'Good', 'Average', 'Below Average', 'Poor'],
    whole: [
      { field: 'tightness_score', min: 0, max: 10 }, { field: 'pain_score', min: 0, max: 10 }, { field: 'psych_stress_score', min: 1, max: 5 },
      { field: 'instability_events', min: 0, max: 20 }, { field: 'bristol_type', min: 0, max: 7 }, { field: 'hunger_deviation', min: -2, max: 2 },
      { field: 'thirst_intensity', min: 1, max: 5 }, { field: 'relaxation_depth', min: 1, max: 5 },
    ],
    decimal: [{ field: 'alcohol_units', min: 0, max: 20, step: 0.5 }, { field: 'meditation_minutes', min: 0, max: 120, step: 5 }],
    switches: ['travel_flag', 'unusual_stool_colour', 'electrolytes_taken'],
    locations: ['Lower back', 'Right hip', 'Left hip'], tags: ['Tight', 'Sore', 'Sharp'],
  }
}

// ── The training week (rebuild Phase 7) ──────────────────────────────────────
// A made-up block that started two weeks before this Monday, 84 days long. The days follow
// one pattern: Monday, Tuesday, Thursday and Friday train (a past Monday and Thursday done,
// a past Tuesday and Friday missed), the other days rest.

/** 0 = Monday. */
export const weekday = (day: string) => (new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7
export const mondayOf = (day: string) => addDays(day, -weekday(day))
const blockStart = (local: string) => addDays(mondayOf(local), -14)
const BLOCK_DAYS = 84
const TRAINS = new Set([0, 1, 3, 4])
const DONE_WHEN_PAST = new Set([0, 3])

export function lineOf(name: string, prescription: string, mechanics = ''): Schemas['ExerciseLine'] {
  return { icon: '', laterality: null, mechanics, name, prescription, type: null }
}

function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / DAY_MS)
}

export function phaseOf(local: string, day: string): Schemas['PhaseOut'] {
  const start = blockStart(local)
  const n = daysBetween(start, day) + 1
  return { number: 5, name: session.phase, start_date: start, length_days: BLOCK_DAYS, plan_days: BLOCK_DAYS,
    day_num: n >= 1 && n <= BLOCK_DAYS ? n : null }
}

export type Marker = 'done' | 'today' | 'missed' | 'planned' | 'rest'

export function markerOf(day: string, local: string): Marker {
  const trains = TRAINS.has(weekday(day))
  if (day < blockStart(local)) return 'rest'
  if (day === local) return 'today'
  if (day < local) return trains ? (DONE_WHEN_PAST.has(weekday(day)) ? 'done' : 'missed') : 'rest'
  return trains ? 'planned' : 'rest'
}

const YOGA_SUGGESTION = { slug: 'made-up-flow', name: 'Made-up hip flow', minutes: 15 }

function gapOf(local: string): Schemas['GapScreen'] {
  return { next: { name: 'Made-up next block', start_date: addDays(local, 5), days_away: 5 }, stranded: null }
}

/** What the owner's answers did in one browser test (the mock keeps one per test, by the
 *  cookie `e2e_run`): the answers applied, each id once, and the yoga and outdoor saves. */
export interface WeekRun {
  applied: string[]
  swaps: string[]
  carry: boolean
  shift: boolean
  redo: boolean
  flare: boolean
  reasons: Record<string, string>
  yoga: Record<string, string>
  outdoor: Record<string, string>
  /** The flexibility capture (Phase 8): the engine's answer the run has reached, or null. */
  flexStep: number | null
  flexFinished: boolean
  /** The engine's sync (Phase 9): when the phone ran it in this run (null: not yet). */
  syncedAt: string | null
}

export const newRun = (): WeekRun => ({
  applied: [], swaps: [], carry: false, shift: false, redo: false, flare: false, reasons: {}, yoga: {},
  outdoor: {}, flexStep: null, flexFinished: false, syncedAt: null,
})

const BANNER: Schemas['WeekBanner'] = {
  scheduled: 4, completed: 1, progress: 'normal', to_go: 2, streak_weeks: 2, streak_all_ultimate: false,
  perfect_count: 3, ultimate_count: 1, last_week: 'perfect',
}

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** The week answer: `scenario` names what the test asks for (the cookie `e2e_week`):
 *  carry, carry_in_order, shift, redo, gate1, retest, gap, unreadable. */
export function trainingWeek(local: string, asked: string | null, scenario: ReadonlySet<string>,
  run: WeekRun): Schemas['TrainingWeekOut'] {
  const base: Schemas['TrainingWeekOut'] = {
    phases_readable: true, phases_error: '', today: local, phase: null, banner: null, repeat_notice: null,
    load_held: false, redo: null, gate1: null, retest: null, week_start: null, is_current_week: false,
    can_go_back: false, can_go_forward: false, strip: [], viewed_week_status: null, gap: null,
    carry_prompt: null, shift_prompt: null,
  }
  if (scenario.has('unreadable')) return { ...base, phases_readable: false, phases_error: 'made-up' }
  const gap = scenario.has('gap')
  const current = mondayOf(local)
  const lo = mondayOf(blockStart(local))
  const hi = mondayOf(addDays(blockStart(local), BLOCK_DAYS - 1))
  let ws = mondayOf(asked ?? local)
  if (!gap) ws = ws < lo ? lo : ws > hi ? hi : ws
  const strip = Array.from({ length: 7 }, (_, i) => {
    const d = addDays(ws, i)
    const marker: Marker = gap ? (d === local ? 'today' : 'rest') : markerOf(d, local)
    const moved = marker === 'planned' && weekday(d) === 4
    return {
      date: d, weekday_label: WEEKDAY_LABELS[i], marker, state: marker,
      day_num: gap ? null : phaseOf(local, d).day_num,
      note: moved ? { text: 'Made-up: moved from Monday for the tests.', moved: true } : null,
    }
  })
  if (gap) {
    return {
      ...base, banner: { ...BANNER, scheduled: 0, completed: 0, progress: 'no_plan', to_go: 0, last_week: null },
      week_start: ws, is_current_week: ws === current, can_go_back: true, can_go_forward: true, strip, gap: gapOf(local),
    }
  }
  const failed = scenario.has('redo')
  const lastMonday = addDays(current, -7)
  return {
    ...base,
    phase: phaseOf(local, local),
    banner: { ...BANNER, last_week: failed ? 'failed' : 'perfect', progress: failed ? 'failing' : 'normal' },
    repeat_notice: failed ? 'Made-up: last week had 2 of 7 days logged, so it failed and runs again this week.' : null,
    load_held: failed,
    redo: failed && !run.redo
      ? { offered: true, consequences: ['Next week runs this week’s sessions again.', 'Made-up: the block ends a week later.'] }
      : { offered: false, consequences: [] },
    gate1: {
      count: { run: 2, required: 6 },
      lifts_met: 1,
      rows: [
        { lift: 'Made-up squat', first: 80, latest: 90, target: 88, met: true },
        { lift: 'Made-up press', first: 40, latest: 42, target: 44, met: false },
      ],
      waiting: scenario.has('gate1') && !run.reasons[lastMonday]
        ? { monday: lastMonday, core_done: 2, core_required: 3 } : null,
      reasons: [{ key: 'hips_back', label: 'Hips or back' }, { key: 'travel_illness', label: 'Travel or illness' },
        { key: 'other', label: 'Other' }],
      flare_this_week: run.flare,
      how: 'Made-up: running starts when the gate is passed.',
    },
    retest: scenario.has('retest') ? { kind: 'info', status: 'ready', reason: 'made-up: 84 days since the last test' } : null,
    week_start: ws,
    is_current_week: ws === current,
    can_go_back: ws > lo,
    can_go_forward: ws < hi,
    strip,
    viewed_week_status: ws < current ? 'normal' : null,
    carry_prompt: (scenario.has('carry') || scenario.has('carry_in_order')) && !run.carry
      ? { in_order: scenario.has('carry_in_order'), lines: ['Made-up: the missed session moves to Wednesday.'] } : null,
    shift_prompt: scenario.has('shift') && !run.shift ? { reason: 'made-up short sleep last night' } : null,
  }
}

/** The accessory session: the engine-made session, as the "+" menu's second session. */
export function accessoryPlan(local: string) {
  return {
    ...session, date: local, kind: 'accessory', day_num: null, plan_days: null, objective: 'Made-up accessory session',
    ask_length_above_minutes: null, next_day: null, reasons: ['Made-up: the upper body is the least loaded area today.'],
    note: 'Made-up accessory note.',
  }
}

export function yogaCatalogue(): Schemas['YogaCatalogueOut'] {
  return {
    stage_read: true,
    flows: [{
      slug: YOGA_SUGGESTION.slug, name: YOGA_SUGGESTION.name, minutes: YOGA_SUGGESTION.minutes, rpe: 2,
      video_url: 'https://www.youtube.com/watch?v=made-up',
      poses: [{ name: 'Made-up pose A', hold_seconds: 30 }, { name: 'Made-up pose B', hold_seconds: 45 }],
      cautions: [{ pose: 'Made-up pose B', severity: 'caution', note: 'Made-up form note for the tests.' }],
    }, {
      // A name as long as the real ones, so a row that does not wrap shows in the layout test
      // (2026-10-21: a real flow's name ran off both sides of the page).
      slug: 'made-up-long-flow', name: 'Made-up 20-Minute Hip, Spine & Shoulder Mobility Flow', minutes: 20, rpe: 2,
      video_url: 'https://www.youtube.com/watch?v=made-up-long',
      poses: [{ name: 'Made-up pose C', hold_seconds: 30 }],
      cautions: [],
    }],
  }
}

export function outdoorList(day: string): Schemas['OutdoorListOut'] {
  const au = (minutes: number) => Array.from({ length: 10 }, (_, i) => (i + 1) * minutes)
  return {
    date: day,
    activities: [
      { activity_id: '501', name: 'Made-up walk', type: 'walking', duration_minutes: 47.6, distance_km: 4.1, avg_hr: 112,
        logs_as: 'Outdoor Walk', in_family: true, minutes: 48, au_by_rpe: au(48) },
      { activity_id: '502', name: 'Made-up ride', type: 'cycling', duration_minutes: 30.2, distance_km: 11.0, avg_hr: 125,
        logs_as: 'Outdoor Activity', in_family: false, minutes: 30, au_by_rpe: au(30) },
    ],
  }
}
