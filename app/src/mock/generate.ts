// Synthetic data for the design bake-off (rebuild Phase 3).
//
// Shaped like the owner's real ranges and NEVER taken from them: the repo and the
// preview address are public. One seed gives one result. app/scripts/make-mock.ts
// writes it to data.ts, and src/mock/mock.test.ts fails if data.ts differs from
// generate(SEED), so no hand-typed value can enter the app.
//
// The labels and tones stand in for what the engine will send. The phone holds no
// rule: in the real app these words and tones come from the API.

export const SEED = 20261019

export type Tone = 'good' | 'fair' | 'low'
export type Score = { value: number; label: string; tone: Tone }
export type Day = {
  date: string
  readiness: Score
  sleep: Score & { minutes: number }
  strain: Score & { soFar: boolean }
}
export type Exercise = {
  name: string
  sets: number
  reps: number | null
  holdSeconds: number | null
  weightKg: number | null
  eachSide: boolean
  warmup: boolean
}
export type Step = { set: number; side: 'right' | 'left' | null; kind: 'hold' | 'rest'; seconds: number }
export type Region = { key: 'upper' | 'lower' | 'core'; value: number | null; learning: boolean }
/** A score's scale as the engine sends it: each band runs up to `upTo`. */
export type Band = { upTo: number; tone: Tone }
export type Mock = {
  seed: number
  days: Day[]
  scales: { readiness: Band[]; sleep: Band[]; strain: Band[] }
  hrv: number[]
  rhr: number[]
  session: { title: string; minutes: number; exercises: Exercise[] }
  guided: { exerciseIndex: number; elapsedSeconds: number; steps: Step[]; nextExercise: string }
  strength: {
    score: number
    weekly: number[]
    change4w: number
    regions: Region[]
    workKg: number
    workByDay: number[]
  }
}

/** Mulberry32: a small seeded generator, the same numbers on every machine. */
function seeded(seed: number): () => number {
  let a = seed | 0
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const round1 = (x: number) => Math.round(x * 10) / 10

function band(value: number): Score {
  if (value >= 85) return { value, label: 'Optimal', tone: 'good' }
  if (value >= 70) return { value, label: 'Good', tone: 'good' }
  if (value >= 60) return { value, label: 'Fair', tone: 'fair' }
  return { value, label: 'Pay attention', tone: 'low' }
}

function strainBand(value: number): Score {
  if (value < 8) return { value, label: 'Light', tone: 'good' }
  if (value < 12) return { value, label: 'Moderate', tone: 'fair' }
  if (value < 16) return { value, label: 'Hard', tone: 'low' }
  return { value, label: 'Strenuous', tone: 'low' }
}

function isoDay(base: Date, offset: number): string {
  const d = new Date(base.getTime() + offset * 86_400_000)
  return d.toISOString().slice(0, 10)
}

export function generate(seed: number): Mock {
  const r = seeded(seed)
  const between = (lo: number, hi: number) => lo + (hi - lo) * r()
  const int = (lo: number, hi: number) => Math.round(between(lo, hi))
  // Whole steps of 2.5 kg, as the plates and dumbbells come.
  const kg = (lo: number, hi: number) => Math.round(between(lo, hi) / 2.5) * 2.5

  const today = new Date(Date.UTC(2026, 9, 19))
  const days: Day[] = []
  for (let offset = -6; offset <= 0; offset++) {
    const isToday = offset === 0
    days.push({
      date: isoDay(today, offset),
      readiness: band(int(55, 88)),
      sleep: { ...band(int(62, 90)), minutes: int(6 * 60 + 5, 8 * 60 + 10) },
      strain: { ...strainBand(round1(isToday ? between(2, 6) : between(4, 15))), soFar: isToday },
    })
  }

  const hrv = Array.from({ length: 7 }, () => int(46, 72))
  const rhr = Array.from({ length: 7 }, () => int(50, 58))

  const exercises: Exercise[] = [
    { name: 'Standing psoas march', sets: 2, reps: 20, holdSeconds: null, weightKg: null, eachSide: true, warmup: true },
    { name: 'Walking lunge', sets: 3, reps: 10, holdSeconds: null, weightKg: kg(10, 15), eachSide: true, warmup: false },
    { name: 'Machine chest press', sets: 3, reps: 10, holdSeconds: null, weightKg: kg(35, 50), eachSide: false, warmup: false },
    { name: 'Machine shoulder press', sets: 3, reps: 8, holdSeconds: null, weightKg: kg(25, 35), eachSide: false, warmup: false },
    { name: 'Reverse cable crossover', sets: 3, reps: 15, holdSeconds: null, weightKg: kg(5, 12.5), eachSide: false, warmup: false },
    { name: 'Side plank', sets: 3, reps: null, holdSeconds: 30, weightKg: null, eachSide: true, warmup: false },
    { name: 'Hip airplane', sets: 3, reps: 10, holdSeconds: null, weightKg: null, eachSide: true, warmup: false },
  ]

  const hold = 30
  const rest = 45
  const steps: Step[] = [
    { set: 2, side: 'right', kind: 'hold', seconds: hold },
    { set: 2, side: 'left', kind: 'hold', seconds: hold },
    { set: 2, side: null, kind: 'rest', seconds: rest },
    { set: 3, side: 'right', kind: 'hold', seconds: hold },
    { set: 3, side: 'left', kind: 'hold', seconds: hold },
  ]

  const weekly: number[] = []
  let level = between(52, 55)
  for (let i = 0; i < 12; i++) {
    level += between(-0.4, 0.9)
    weekly.push(round1(level))
  }
  const score = weekly[weekly.length - 1]
  const workByDay = [int(3200, 4800), 0, int(2800, 4200), 0, int(1800, 3000), 0, 0]

  const hundred: Band[] = [
    { upTo: 60, tone: 'low' },
    { upTo: 70, tone: 'fair' },
    { upTo: 100, tone: 'good' },
  ]
  const scales = {
    readiness: hundred,
    sleep: hundred,
    strain: [
      { upTo: 8, tone: 'good' },
      { upTo: 12, tone: 'fair' },
      { upTo: 21, tone: 'low' },
    ] as Band[],
  }

  return {
    seed,
    days,
    scales,
    hrv,
    rhr,
    session: { title: 'Strength A', minutes: int(54, 62), exercises },
    guided: { exerciseIndex: 5, elapsedSeconds: int(9, 14), steps, nextExercise: 'Hip airplane' },
    strength: {
      score,
      weekly,
      change4w: round1(score - weekly[weekly.length - 5]),
      regions: [
        { key: 'upper', value: 50, learning: true },
        { key: 'lower', value: 50, learning: true },
        { key: 'core', value: null, learning: false },
      ],
      workKg: workByDay.reduce((a, b) => a + b, 0),
      workByDay,
    },
  }
}
