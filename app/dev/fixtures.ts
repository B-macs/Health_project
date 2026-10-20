// Made-up engine answers for the mock API (rebuild Phase 5): Today, its week, the day's
// plan, the three detail screens and the check-in form, for any day. Every number is
// invented from the date; nothing comes from a real reading. Typed against the engine's
// contract (src/generated/api.ts), so a change in the contract breaks this file's type
// check instead of a browser test.
import type { components } from '../src/generated/api'

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

export function trainingDay(day: string, local: string): Schemas['TrainingDayOut'] {
  const base = { date: day, gap: null, logged: null, note: null, overview: null, phase: null, phases_error: null, planned: null, rest: null, swap: null }
  if (day !== local) {
    return { ...base, route: 'past_completed', logged: { au: 300, minutes: 52, rpe: 6, exercises: [{ name: 'Made-up squat', movement_type: null, planned_sets: 3 }] } }
  }
  const line = (name: string, prescription: string) => ({ icon: '', laterality: null, mechanics: '', name, prescription, type: null })
  return {
    ...base,
    route: 'today',
    overview: {
      screen: 'overview', headline: 'Made-up session', subtitle: null, phase_name: 'Made-up block', day_num: 3, plan_days: 84,
      card: { exercise_count: 2, minutes: 45, focus: [], loaded: true, rpe_target: 7 },
      main: [line('Made-up squat', '3 × 10 · 20 kg'), line('Made-up row', '3 × 12 · 30 kg')],
      home: [], release: [], adaptation: null, banner: null, first_side: null, first_side_note: null, objective: null,
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
    source: { kind: 'rpe', label: 'RPE only', hr_rows: [], blend: null },
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
