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
// The second fix, the same evening ("Let's try both"): the sound runs only while a bell or
// a beep plays. The first tap starts it (iOS starts a sound only from a tap) and every
// sound lets it go again RELEASE_AFTER_MS after it ends, so the phone can give the music
// back between bells; later taps no longer wake it. The log notes the first few releases
// and wakes, which shows whether this phone lets a countdown wake the sound by itself.
//
// WP-42, his report of 2026-11-03: with headphones the music still stops at the end of a
// rest ("On the headphones, End of the rest"); on the loudspeaker it keeps playing. Two
// more ways to play the same sounds, chosen in Settings › Bells, for his test with
// headphones: "held" keeps the sound on from the first countdown beep until HELD_RELEASE_MS
// after the bell, so iOS starts and stops it once a rest instead of four times; "file"
// plays the same recipes (soundFiles.ts) as WAV files through an audio element, a
// different path through iOS. "short" is the way of 2026-10-30.
import {
  BELLS, PARTIALS, REST_OVER, TICK, partialSeconds, renderStrikes, renderTick, wav,
  type Ending, type Strike,
} from './soundFiles'

export type { Ending } from './soundFiles'

/** How the sound plays (Settings › Bells, WP-42). */
export type SoundWay = 'short' | 'held' | 'file'
export const SOUND_WAYS: readonly SoundWay[] = ['short', 'held', 'file']

type Ctx = AudioContext

let ctx: Ctx | null = null
let bellsOn = true
/** The sound has run once from a tap; from then on a bell may wake it by itself. */
let unlocked = false

/** How long after the last bell or beep ends the sound is let go. */
export const RELEASE_AFTER_MS = 500
/** The "held" way: longer than the second between two countdown beeps, so the sound
 *  runs from the first beep until after the bell. */
export const HELD_RELEASE_MS = 2500
let way: SoundWay = 'short'
let releaseTimer: ReturnType<typeof setTimeout> | null = null
let busyUntil = 0

type SoundLog = (kind: string, detail: Record<string, unknown>) => void
let soundLog: SoundLog | null = null
let notes = 0
const MAX_NOTES = 12

/** Where the first releases and wakes of each app start are written (the debug log). */
export function setSoundLog(log: SoundLog | null): void {
  soundLog = log
}

function note(kind: string, detail: Record<string, unknown>): void {
  if (!soundLog || notes >= MAX_NOTES) return
  notes += 1
  soundLog(kind, detail)
}

/** The Settings switch (KEYS.bells). Off closes the sound, so the phone's audio is let go
 *  at once, and no tap or countdown starts it again until the bells are on. */
export function setBells(on: boolean): void {
  bellsOn = on
  if (on) return
  unlocked = false
  busyUntil = 0
  if (releaseTimer !== null) clearTimeout(releaseTimer)
  releaseTimer = null
  if (ctx) {
    const closing = ctx
    ctx = null
    void closing.close().catch(() => undefined)
  }
}

/** The Settings choice of how the sound plays (KEYS.soundWay). The "file" way closes the
 *  live sound, so only the audio elements play. */
export function setSoundWay(next: SoundWay): void {
  way = SOUND_WAYS.includes(next) ? next : 'short'
  if (way !== 'file' || !ctx) return
  const closing = ctx
  ctx = null
  unlocked = false
  void closing.close().catch(() => undefined)
}

export function soundWay(): SoundWay {
  return way
}

/** Keep the sound running until `seconds` from now (the longest sound playing), then let
 *  it go. */
function holdThenRelease(c: Ctx, seconds: number): void {
  busyUntil = Math.max(busyUntil, Date.now() + seconds * 1000)
  if (releaseTimer !== null) clearTimeout(releaseTimer)
  releaseTimer = setTimeout(() => {
    releaseTimer = null
    if (ctx !== c || c.state !== 'running') return
    void c.suspend().then(() => note('sound let go', { sound: c.state }), () => undefined)
  }, busyUntil - Date.now() + (way === 'held' ? HELD_RELEASE_MS : RELEASE_AFTER_MS))
}

function context(): Ctx | null {
  if (!bellsOn || way === 'file' || typeof window === 'undefined') return null
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

/** Declare sounds that mix with other audio, and start the sound once, from a tap, so a
 *  bell may wake it later; it is let go again at once. Later taps leave it alone. */
export function unlockAudio(nav: Navigator = navigator): void {
  declareMixing(nav)
  if (way === 'file') {
    if (bellsOn) unlockFiles()
    return
  }
  const c = context()
  if (!c || unlocked) return
  void c.resume().then(() => {
    unlocked = true
    holdThenRelease(c, 0)
  }, () => undefined)
}

export function audioState(): string {
  return ctx?.state ?? 'not started'
}

/** For the debug log: the Audio Session type the phone holds (null: the browser has no
 *  Audio Session API) and the sound's state. */
export function audioReport(nav: Navigator = navigator): { session: string | null; sound: string; bells: boolean; way: SoundWay } {
  const session = (nav as SessionHost).audioSession
  return { session: session ? session.type : null, sound: audioState(), bells: bellsOn, way }
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

/** Play one sound `seconds` long: wake the sound if it was let go, then let it go again
 *  after the sound ends. */
function play(build: (c: Ctx, out: AudioNode) => void, seconds: number): void {
  const c = context()
  if (!c) return
  const go = () => {
    try {
      build(c, c.destination)
    } catch {
      // a sound that cannot play must never stop the session
    }
    holdThenRelease(c, seconds)
  }
  if (c.state === 'running') {
    go()
    return
  }
  void c.resume().then(() => {
    note('sound woken for a bell', { sound: c.state })
    go()
  }, go)
}

// ─── The "file" way (WP-42): the same sounds, played as WAV files ───────────────────

/** The sample rate of the files: the highest partial (D6 × 5.4, about 6.3 kHz) fits. */
export const FILE_RATE = 22050

type FileKey = 'tick' | 'rest' | Ending

const players = new Map<FileKey, HTMLAudioElement>()
let filesUnlocked = false

function samples(key: FileKey): Float32Array {
  if (key === 'tick') return renderTick(FILE_RATE)
  if (key === 'rest') return renderStrikes(REST_OVER, FILE_RATE)
  return renderStrikes(BELLS[key], FILE_RATE)
}

/** The audio element of one sound, made once (its WAV file drawn from the recipe). */
function player(key: FileKey): HTMLAudioElement | null {
  if (!bellsOn || typeof Audio === 'undefined' || typeof URL === 'undefined') return null
  let el = players.get(key)
  if (!el) {
    const url = URL.createObjectURL(new Blob([wav(samples(key), FILE_RATE)], { type: 'audio/wav' }))
    el = new Audio(url)
    el.preload = 'auto'
    players.set(key, el)
  }
  return el
}

const FILE_KEYS: readonly FileKey[] = ['tick', 'rest', 'continue', 'switch', 'finish', 'done']

/** iOS lets an audio element play by itself only after it has played once from a tap: the
 *  first tap plays each one muted and stops it at once. */
function unlockFiles(): void {
  if (filesUnlocked) return
  filesUnlocked = true
  for (const key of FILE_KEYS) {
    const el = player(key)
    if (!el) continue
    el.muted = true
    void el.play().then(() => {
      el.pause()
      el.currentTime = 0
      el.muted = false
    }, () => {
      el.muted = false
      note('a sound file was refused at the tap', { sound: key })
    })
  }
}

function playFile(key: FileKey): void {
  const el = player(key)
  if (!el) return
  try {
    el.currentTime = 0
  } catch {
    // not loaded yet: it plays from the start anyway
  }
  void el.play().catch(() => note('a sound file did not play', { sound: key }))
}

// ─── The sounds ─────────────────────────────────────────────────────────────────────

/** A plain tone: the 3-2-1 ticks. Thin and short, so it never sounds like a bell. */
export function tick(): void {
  if (way === 'file') {
    playFile('tick')
    return
  }
  play((c, out) => {
    const o = c.createOscillator()
    const g = c.createGain()
    o.connect(g)
    g.connect(out)
    o.type = 'sine'
    o.frequency.value = TICK.frequency
    g.gain.setValueAtTime(TICK.volume, c.currentTime)
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + TICK.seconds)
    o.start(c.currentTime)
    o.stop(c.currentTime + TICK.seconds)
  }, TICK.seconds)
}

/** One struck-bell hit: mildly inharmonic partials, the higher ones decaying fastest. */
function strike(s: Strike): void {
  play((c, out) => {
    const t0 = c.currentTime + s.at
    for (const p of PARTIALS) {
      const o = c.createOscillator()
      const g = c.createGain()
      o.connect(g)
      g.connect(out)
      o.type = 'sine'
      o.frequency.setValueAtTime(s.root * p.r, t0)
      g.gain.setValueAtTime(0.0001, t0)
      g.gain.linearRampToValueAtTime(s.volume * p.g, t0 + 0.002)
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + s.length * p.d)
      o.start(t0)
      o.stop(t0 + partialSeconds(s, p))
    }
  }, s.at + s.length + 0.02)
}

/** The bell a hold rings at its end, by the engine's ending. */
export function bell(ending: Ending): void {
  if (way === 'file') {
    playFile(ending)
    return
  }
  for (const s of BELLS[ending]) strike(s)
}

/** The rest's end: a rising pair, so it is never the hold's swap. */
export function restOver(): void {
  if (way === 'file') {
    playFile('rest')
    return
  }
  for (const s of REST_OVER) strike(s)
}
