// The session's sounds mix with the music already playing (WP-29, the owner, 2026-10-26:
// "Keep Spotify music and Apple Podcasts playing"). "playback" stops other audio on iOS.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AUDIO_SESSION_TYPE, audioReport, declareMixing, reportAudioOnce, unlockAudio } from './sounds'

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
