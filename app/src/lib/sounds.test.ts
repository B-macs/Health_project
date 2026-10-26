// The session's sounds mix with the music already playing (WP-29, the owner, 2026-10-26:
// "Keep Spotify music and Apple Podcasts playing"). "playback" stops other audio on iOS.
import { describe, expect, it } from 'vitest'
import { AUDIO_SESSION_TYPE, unlockAudio } from './sounds'

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
})
