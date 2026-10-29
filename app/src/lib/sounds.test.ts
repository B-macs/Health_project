// The session's sounds mix with the music already playing (WP-29, the owner, 2026-10-26:
// "Keep Spotify music and Apple Podcasts playing"). "playback" stops other audio on iOS.
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AUDIO_SESSION_TYPE, RELEASE_AFTER_MS, audioReport, bell, declareMixing, reportAudioOnce, setBells,
  setSoundLog, tick, unlockAudio,
} from './sounds'

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
    expect(audioReport({} as Navigator)).toEqual({ session: null, sound: 'not started', bells: false })
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
    setBells(false)
    setBells(true)
    setSoundLog(null)
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  const start = async () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', { AudioContext: FakeContext })
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
