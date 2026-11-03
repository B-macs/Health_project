// The session's sounds as numbers (WP-42): what each bell and beep is made of, and the
// same sounds written out as WAV files.
//
// WP-42, the athlete, 2026-11-03: with headphones the music still stops at the end of a
// rest ("On the headphones, End of the rest"); on the loudspeaker it keeps playing (his
// test of 2026-10-30). The bells are drawn live (sounds.ts) from the recipes below, and
// Settings › Bells can play the very same recipes as files through an audio element
// instead (the "file" way), which is a different path through iOS. Both ways read these
// recipes, so a bell sounds the same either way.

/** One partial of a struck bell: its ratio to the root, its loudness and how long it
 *  rings, as a share of the strike's length. The higher ones decay fastest. */
export type Partial = { r: number; g: number; d: number }

export const PARTIALS: readonly Partial[] = [
  { r: 1.0, g: 1.0, d: 1.0 },
  { r: 2.0, g: 0.55, d: 0.62 },
  { r: 2.76, g: 0.38, d: 0.42 },
  { r: 4.07, g: 0.22, d: 0.28 },
  { r: 5.4, g: 0.14, d: 0.18 },
]

/** One struck-bell hit: root frequency (Hz), start (s), loudness, length (s). */
export type Strike = { root: number; at: number; volume: number; length: number }

export type Ending = 'continue' | 'switch' | 'finish' | 'done'

const D6 = 1174.7
const C6 = 1046.5
const G5 = 784.0
const E5 = 659.3
const C5 = 523.3

/** The bell a hold rings at its end, by the engine's ending: 1 strike = another rep,
 *  2 falling = swap sides, 3 falling = the set is over, 4 falling = the exercise is over. */
export const BELLS: Readonly<Record<Ending, readonly Strike[]>> = {
  continue: [{ root: D6, at: 0, volume: 0.9, length: 0.45 }],
  switch: [
    { root: D6, at: 0, volume: 0.95, length: 1.2 },
    { root: G5, at: 0.16, volume: 1.0, length: 1.9 },
  ],
  finish: [
    { root: C6, at: 0, volume: 0.9, length: 1.0 },
    { root: G5, at: 0.18, volume: 0.95, length: 1.2 },
    { root: C5, at: 0.36, volume: 1.0, length: 2.6 },
  ],
  done: [
    { root: C6, at: 0, volume: 0.9, length: 1.0 },
    { root: G5, at: 0.18, volume: 0.95, length: 1.1 },
    { root: E5, at: 0.36, volume: 0.95, length: 1.2 },
    { root: C5, at: 0.54, volume: 1.0, length: 2.8 },
  ],
}

/** The rest's end: a rising pair, so it is never the hold's swap. */
export const REST_OVER: readonly Strike[] = [
  { root: G5, at: 0, volume: 0.95, length: 1.5 },
  { root: D6, at: 0.16, volume: 1.0, length: 1.9 },
]

/** The 3-2-1 tick: a thin, short tone, so it never sounds like a bell. */
export const TICK = { frequency: 880, volume: 0.35, seconds: 0.12 }

/** How long a strike's partial sounds, its tail included. */
export function partialSeconds(s: Strike, p: Partial): number {
  return s.length * p.d + 0.02
}

/** How long a list of strikes sounds, from the first to the end of the last tail. */
export function strikesSeconds(strikes: readonly Strike[]): number {
  return Math.max(0, ...strikes.map((s) => s.at + s.length + 0.02))
}

const FLOOR = 0.0001
const ATTACK = 0.002

/** The loudness of one partial `t` seconds after its strike: a 2 ms rise, then an
 *  exponential fall to silence over its ring time (the Web Audio ramps sounds.ts uses). */
function envelope(t: number, peak: number, ring: number): number {
  if (t < 0 || t > ring + 0.02) return 0
  if (t < ATTACK) return FLOOR + (peak - FLOOR) * (t / ATTACK)
  if (t >= ring) return 0
  return peak * Math.pow(FLOOR / peak, (t - ATTACK) / (ring - ATTACK))
}

/** The strikes drawn into samples, mono, at `rate`; clipped to -1..1 as a speaker would. */
export function renderStrikes(strikes: readonly Strike[], rate: number): Float32Array {
  const out = new Float32Array(Math.ceil(strikesSeconds(strikes) * rate))
  for (const s of strikes) {
    for (const p of PARTIALS) {
      const f = s.root * p.r
      const peak = s.volume * p.g
      const ring = s.length * p.d
      const first = Math.floor(s.at * rate)
      const last = Math.min(out.length, Math.ceil((s.at + ring + 0.02) * rate))
      for (let i = first; i < last; i += 1) {
        const t = i / rate - s.at
        out[i] += envelope(t, peak, ring) * Math.sin(2 * Math.PI * f * t)
      }
    }
  }
  for (let i = 0; i < out.length; i += 1) out[i] = Math.max(-1, Math.min(1, out[i]))
  return out
}

/** The tick drawn into samples. */
export function renderTick(rate: number): Float32Array {
  const out = new Float32Array(Math.ceil(TICK.seconds * rate))
  for (let i = 0; i < out.length; i += 1) {
    const t = i / rate
    const gain = TICK.volume * Math.pow(0.001 / TICK.volume, t / TICK.seconds)
    out[i] = gain * Math.sin(2 * Math.PI * TICK.frequency * t)
  }
  return out
}

/** Samples as a 16-bit mono WAV file. */
export function wav(samples: Float32Array, rate: number): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(44 + samples.length * 2)
  const view = new DataView(bytes.buffer)
  const text = (at: number, s: string) => {
    for (let i = 0; i < s.length; i += 1) view.setUint8(at + i, s.charCodeAt(i))
  }
  text(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  text(8, 'WAVE')
  text(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, rate, true)
  view.setUint32(28, rate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  text(36, 'data')
  view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i += 1) {
    view.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, samples[i])) * 32767), true)
  }
  return bytes
}
