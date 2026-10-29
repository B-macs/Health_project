// The session's sounds mix with the music already playing (WP-29, the owner, 2026-10-26:
// "Keep Spotify music and Apple Podcasts playing"). "playback" stops other audio on iOS.
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AUDIO_SESSION_TYPE, audioReport, bell, declareMixing, reportAudioOnce, setBells, tick, unlockAudio,
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
