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
// iOS: audio starts only after a tap, so the first tap of the session unlocks it. The
// page's sounds MIX WITH OTHER AUDIO (WP-29, the owner, 2026-10-26: "Keep Spotify music
// and Apple Podcasts playing ... Play timer beeps over the background audio without
// stopping it"): the Audio Session API's "ambient" type (Safari 17). Safari offers no
// type that both mixes and plays with the silent switch on ("transient" is "ambient" in
// WebKit's DOMAudioSession.cpp), so the bells need silent mode off. Until 2026-10-26 the
// type was "playback", his choice of 2026-10-20 ("always play the bells over
// everything"), which stopped his music at the first tap. Web apps on iOS cannot vibrate.
//
// 2026-10-29, his report: Spotify still stops at his first tap in a session. The type is now
// also declared at the app's start, before any sound exists, and the first tap writes what
// the phone did into the debug log (seven taps on the version line in Settings): whether
// the browser offers the Audio Session API, the type it holds, and the sound's state.
// His log the same evening: "ambient" held at start and at the tap, the sound running a
// second later, and Spotify stopped all the same. So the bells can be switched off in
// Settings (his choice, "start with the first"): off, the app starts no sound at all.
export type Ending = 'continue' | 'switch' | 'finish' | 'done'

type Ctx = AudioContext

let ctx: Ctx | null = null
let bellsOn = true

/** The Settings switch (KEYS.bells). Off closes the sound, so the phone's audio is let go
 *  at once, and no tap or countdown starts it again until the bells are on. */
export function setBells(on: boolean): void {
  bellsOn = on
  if (!on && ctx) {
    const closing = ctx
    ctx = null
    void closing.close().catch(() => undefined)
  }
}

function context(): Ctx | null {
  if (!bellsOn || typeof window === 'undefined') return null
  const Audio = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!Audio) return null
  ctx ??= new Audio()
  return ctx
}

/** The Audio Session type: sounds that mix with the music already playing (WP-29). */
export const AUDIO_SESSION_TYPE = 'ambient'

type SessionHost = Navigator & { audioSession?: { type: string } }

/** Declare sounds that mix with other audio. Call at the app's start, before any sound. */
export function declareMixing(nav: Navigator = navigator): void {
  const session = (nav as SessionHost).audioSession
  if (session) session.type = AUDIO_SESSION_TYPE
}

/** Declare sounds that mix with other audio, and wake the audio. Call from a tap. */
export function unlockAudio(nav: Navigator = navigator): void {
  declareMixing(nav)
  const c = context()
  if (c && c.state !== 'running') void c.resume().catch(() => undefined)
}

export function audioState(): string {
  return ctx?.state ?? 'not started'
}

/** For the debug log: the Audio Session type the phone holds (null: the browser has no
 *  Audio Session API) and the sound's state. */
export function audioReport(nav: Navigator = navigator): { session: string | null; sound: string; bells: boolean } {
  const session = (nav as SessionHost).audioSession
  return { session: session ? session.type : null, sound: audioState(), bells: bellsOn }
}

let reported = false

/** The first tap's report, once per app start, and again a second later, when the sound
 *  has had time to start. */
export function reportAudioOnce(log: (detail: Record<string, unknown>) => void, nav: Navigator = navigator): void {
  if (reported) return
  reported = true
  log({ at: 'first tap', ...audioReport(nav) })
  setTimeout(() => log({ at: 'a second later', ...audioReport(nav) }), 1000)
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
