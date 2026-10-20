// The session's sounds (rebuild Phase 6), ported from the Streamlit training page's own
// (views/training.py, the athlete's requests of 2026-08-17 and 2026-10-13).
//
// THE SIGNAL IS HOW MANY STRIKES. Mid-set he holds a position with his eyes shut, so the
// bell says what comes next: 1 strike = another rep, 2 falling = swap sides, 3 falling =
// the set is over, 4 falling = the exercise is over. Which one a hold rings is the
// engine's (the walk's `ending`, sessions.hold_ending), never decided here. The rest's
// end is a RISING pair, and the 3-2-1 ticks are a short thin tone. Each bell that is
// followed by another rep is one short strike, so it dies before the next rep starts.
//
// iOS: audio starts only after a tap, so the first tap of the session unlocks it; the
// page declares itself a media player (the Audio Session API, Safari 17), which lets the
// sounds play with the silent switch on. Web apps on iOS cannot vibrate.
export type Ending = 'continue' | 'switch' | 'finish' | 'done'

type Ctx = AudioContext

let ctx: Ctx | null = null

function context(): Ctx | null {
  if (typeof window === 'undefined') return null
  const Audio = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Audio) return null
  ctx ??= new Audio()
  return ctx
}

/** Declare a media player (so the silent switch does not mute the bells) and wake the
 *  audio. Call from a tap. */
export function unlockAudio(nav: Navigator = navigator): void {
  const session = (nav as Navigator & { audioSession?: { type: string } }).audioSession
  if (session) session.type = 'playback'
  const c = context()
  if (c && c.state !== 'running') void c.resume().catch(() => undefined)
}

export function audioState(): string {
  return ctx?.state ?? 'not started'
}

function play(build: (c: Ctx, out: AudioNode) => void): void {
  const c = context()
  if (!c) return
  const go = () => {
    try {
      build(c, c.destination)
    } catch {
      // a sound that cannot play must never stop the session
    }
  }
  if (c.state === 'suspended') void c.resume().then(go, go)
  else go()
}

/** A plain tone: the 3-2-1 ticks. Thin and short, so it never sounds like a bell. */
export function tick(): void {
  play((c, out) => {
    const o = c.createOscillator()
    const g = c.createGain()
    o.connect(g)
    g.connect(out)
    o.type = 'sine'
    o.frequency.value = 880
    g.gain.setValueAtTime(0.35, c.currentTime)
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + 0.12)
    o.start(c.currentTime)
    o.stop(c.currentTime + 0.12)
  })
}

/** One struck-bell hit: mildly inharmonic partials, the higher ones decaying fastest. */
function strike(root: number, at: number, volume: number, length: number): void {
  play((c, out) => {
    const t0 = c.currentTime + at
    const partials = [
      { r: 1.0, g: 1.0, d: 1.0 },
      { r: 2.0, g: 0.55, d: 0.62 },
      { r: 2.76, g: 0.38, d: 0.42 },
      { r: 4.07, g: 0.22, d: 0.28 },
      { r: 5.4, g: 0.14, d: 0.18 },
    ]
    for (const p of partials) {
      const o = c.createOscillator()
      const g = c.createGain()
      o.connect(g)
      g.connect(out)
      o.type = 'sine'
      o.frequency.setValueAtTime(root * p.r, t0)
      g.gain.setValueAtTime(0.0001, t0)
      g.gain.linearRampToValueAtTime(volume * p.g, t0 + 0.002)
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + length * p.d)
      o.start(t0)
      o.stop(t0 + length * p.d + 0.02)
    }
  })
}

const D6 = 1174.7
const C6 = 1046.5
const G5 = 784.0
const E5 = 659.3
const C5 = 523.3

/** The bell a hold rings at its end, by the engine's ending. */
export function bell(ending: Ending): void {
  if (ending === 'continue') {
    strike(D6, 0, 0.9, 0.45)
  } else if (ending === 'switch') {
    strike(D6, 0, 0.95, 1.2)
    strike(G5, 0.16, 1.0, 1.9)
  } else if (ending === 'finish') {
    strike(C6, 0, 0.9, 1.0)
    strike(G5, 0.18, 0.95, 1.2)
    strike(C5, 0.36, 1.0, 2.6)
  } else {
    strike(C6, 0, 0.9, 1.0)
    strike(G5, 0.18, 0.95, 1.1)
    strike(E5, 0.36, 0.95, 1.2)
    strike(C5, 0.54, 1.0, 2.8)
  }
}

/** The rest's end: a rising pair, so it is never the hold's swap. */
export function restOver(): void {
  strike(G5, 0, 0.95, 1.5)
  strike(D6, 0.16, 1.0, 1.9)
}
