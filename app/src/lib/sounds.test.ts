// The session's sounds mix with the music already playing (WP-29, the owner, 2026-10-26:
// "Keep Spotify music and Apple Podcasts playing"). "playback" stops other audio on iOS.
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AUDIO_SESSION_TYPE, DEFAULT_SOUND_WAY, HELD_RELEASE_MS, RELEASE_AFTER_MS, audioReport, bell,
  declareMixing, reportAudioOnce, restOver, setBells, setSoundLog, setSoundWay, tick, unlockAudio,
} from './sounds'
import { DEFAULT_SETTINGS } from './settings'

describe('the audio session', () => {
  it('declares sounds that mix with other audio, never a media player', () => {
    const audioSession = { type: 'auto' }
    unlockAudio({ audioSession } as unknown as Navigator)
    expect(audioSession.type).toBe('ambient')
    expect(AUDIO_SESSION_TYPE).not.toBe('playback')
  })

  it('a browser without the Audio Session API is left alone', () => {
    expect(() => unlockAudio({} as Navigator)).not.toThrow()
  })

  it('is declared at the start, before any sound exists (his report, 2026-10-29)', () => {
    const audioSession = { type: 'auto' }
    declareMixing({ audioSession } as unknown as Navigator)
    expect(audioSession.type).toBe('ambient')
    expect(audioReport({ audioSession } as unknown as Navigator).session).toBe('ambient')
  })

  it('reports a browser without the Audio Session API as null, not as a type', () => {
    expect(audioReport({} as Navigator).session).toBeNull()
  })
})

describe('the bells switch (his choice, 2026-10-29)', () => {
  class FakeContext {
    static made = 0
    state = 'suspended'
    closed = false
    constructor() {
      FakeContext.made += 1
    }
    resume() {
      this.state = 'running'
      return Promise.resolve()
    }
    suspend() {
      this.state = 'suspended'
      return Promise.resolve()
    }
    close() {
      this.closed = true
      return Promise.resolve()
    }
  }

  afterEach(() => {
    setBells(true)
    setBells(false)
    setBells(true)
    vi.unstubAllGlobals()
  })

  it('off, a tap starts no sound at all', () => {
    vi.stubGlobal('window', { AudioContext: FakeContext })
    FakeContext.made = 0
    setBells(false)
    unlockAudio({} as Navigator)
    bell('finish')
    tick()
    expect(FakeContext.made).toBe(0)
    expect(audioReport({} as Navigator)).toEqual({ session: null, sound: 'not started', bells: false, way: 'held' })
  })

  it('switched off during a session, the running sound is closed', () => {
    vi.stubGlobal('window', { AudioContext: FakeContext })
    setBells(true)
    unlockAudio({} as Navigator)
    expect(audioReport({} as Navigator).sound).toBe('running')
    setBells(false)
    expect(audioReport({} as Navigator).sound).toBe('not started')
  })
})

describe('the sound runs only while a bell or a beep plays (his choice, 2026-10-29)', () => {
  // No oscillators: building a sound throws inside play(), which a session survives, and
  // the hold and the release still run.
  class FakeContext {
    static resumes = 0
    state = 'suspended'
    resume() {
      FakeContext.resumes += 1
      this.state = 'running'
      return Promise.resolve()
    }
    suspend() {
      this.state = 'suspended'
      return Promise.resolve()
    }
    close() {
      return Promise.resolve()
    }
  }

  afterEach(() => {
    setSoundWay(DEFAULT_SOUND_WAY)
    setBells(false)
    setBells(true)
    setSoundLog(null)
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  // The way of 2026-10-29/30, still offered in Settings as "short".
  const start = async () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', { AudioContext: FakeContext })
    setSoundWay('short')
    FakeContext.resumes = 0
    unlockAudio({} as Navigator)
    await vi.advanceTimersByTimeAsync(0)
  }

  it('the first tap starts the sound, and it is let go right after', async () => {
    await start()
    expect(audioReport({} as Navigator).sound).toBe('running')
    await vi.advanceTimersByTimeAsync(RELEASE_AFTER_MS)
    expect(audioReport({} as Navigator).sound).toBe('suspended')
  })

  it('a later tap leaves the sound alone', async () => {
    await start()
    await vi.advanceTimersByTimeAsync(RELEASE_AFTER_MS)
    unlockAudio({} as Navigator)
    await vi.advanceTimersByTimeAsync(0)
    expect(FakeContext.resumes).toBe(1)
    expect(audioReport({} as Navigator).sound).toBe('suspended')
  })

  it('a beep wakes the sound and lets it go once the beep has ended', async () => {
    await start()
    await vi.advanceTimersByTimeAsync(RELEASE_AFTER_MS)
    tick()
    await vi.advanceTimersByTimeAsync(0)
    expect(audioReport({} as Navigator).sound).toBe('running')
    await vi.advanceTimersByTimeAsync(120 + RELEASE_AFTER_MS)
    expect(audioReport({} as Navigator).sound).toBe('suspended')
  })

  it('a long bell keeps the sound until its last strike has rung out', async () => {
    await start()
    bell('finish')
    await vi.advanceTimersByTimeAsync(2000)
    expect(audioReport({} as Navigator).sound).toBe('running')
    await vi.advanceTimersByTimeAsync(1500)
    expect(audioReport({} as Navigator).sound).toBe('suspended')
  })

  it('writes the first wakes and releases into the log', async () => {
    const lines: string[] = []
    setSoundLog((kind) => lines.push(kind))
    await start()
    await vi.advanceTimersByTimeAsync(RELEASE_AFTER_MS)
    tick()
    await vi.advanceTimersByTimeAsync(120 + RELEASE_AFTER_MS)
    expect(lines).toEqual(['sound let go', 'sound woken for a bell', 'sound let go'])
  })
})

describe('the first tap report', () => {
  afterEach(() => vi.useRealTimers())

  it('logs once per app start: at the tap and a second later', () => {
    vi.useFakeTimers()
    const lines: Record<string, unknown>[] = []
    const nav = { audioSession: { type: 'ambient' } } as unknown as Navigator
    reportAudioOnce((d) => lines.push(d), nav)
    reportAudioOnce((d) => lines.push(d), nav)
    expect(lines).toEqual([expect.objectContaining({ at: 'first tap', session: 'ambient' })])
    vi.advanceTimersByTime(1000)
    expect(lines.map((d) => d.at)).toEqual(['first tap', 'a second later'])
  })
})

describe('the headphone test ways (WP-42, his report of 2026-11-03)', () => {
  // "On the headphones, End of the rest": the music stops after the 3-2-1 beeps.
  class FakeContext {
    static resumes = 0
    static made = 0
    state = 'suspended'
    constructor() {
      FakeContext.made += 1
    }
    resume() {
      FakeContext.resumes += 1
      this.state = 'running'
      return Promise.resolve()
    }
    suspend() {
      this.state = 'suspended'
      return Promise.resolve()
    }
    close() {
      return Promise.resolve()
    }
  }

  afterEach(() => {
    setSoundWay(DEFAULT_SOUND_WAY)
    setBells(false)
    setBells(true)
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  const restEnd = async () => {
    for (let i = 0; i < 3; i += 1) {
      tick()
      await vi.advanceTimersByTimeAsync(1000)
    }
    restOver()
    await vi.advanceTimersByTimeAsync(2100)
  }

  const started = async (way: 'short' | 'held') => {
    vi.useFakeTimers()
    vi.stubGlobal('window', { AudioContext: FakeContext })
    setSoundWay(way)
    unlockAudio({} as Navigator)
    await vi.advanceTimersByTimeAsync(HELD_RELEASE_MS)
    FakeContext.resumes = 0
  }

  it('short: the end of a rest starts the sound four times', async () => {
    await started('short')
    await restEnd()
    expect(FakeContext.resumes).toBe(4)
  })

  it('held: the sound starts once at the first beep and stays on through the bell', async () => {
    await started('held')
    await restEnd()
    expect(FakeContext.resumes).toBe(1)
    expect(audioReport({} as Navigator)).toMatchObject({ sound: 'running', way: 'held' })
    await vi.advanceTimersByTimeAsync(HELD_RELEASE_MS)
    expect(audioReport({} as Navigator).sound).toBe('suspended')
  })

  it('file: the sounds play as audio files and the live sound never starts', async () => {
    const played: string[] = []
    let files = 0
    class FakeAudio {
      muted = false
      preload = ''
      currentTime = 0
      constructor(public src: string) {}
      play() {
        if (!this.muted) played.push(this.src)
        return Promise.resolve()
      }
      pause() {}
    }
    vi.stubGlobal('window', { AudioContext: FakeContext })
    vi.stubGlobal('Audio', FakeAudio)
    vi.stubGlobal('URL', { createObjectURL: () => `blob:${(files += 1)}` })
    FakeContext.made = 0
    setSoundWay('file')
    unlockAudio({} as Navigator)
    await Promise.resolve()
    expect(files).toBe(6)
    tick()
    restOver()
    bell('done')
    expect(played).toHaveLength(3)
    expect(new Set(played).size).toBe(3)
    expect(FakeContext.made).toBe(0)
    expect(audioReport({} as Navigator).way).toBe('file')
  })

  it('an unknown way reads as held, the default', () => {
    setSoundWay('loud' as never)
    expect(audioReport({} as Navigator).way).toBe('held')
  })

  it('held is the way unless Settings says otherwise (his test with AirPods, 2026-11-09)', () => {
    expect(DEFAULT_SOUND_WAY).toBe('held')
    expect(DEFAULT_SETTINGS.soundWay).toBe('held')
  })
})
