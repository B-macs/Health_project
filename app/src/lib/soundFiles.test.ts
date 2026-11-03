// The sounds as numbers (WP-42): the bells' signal is how many strikes, and the WAV files
// the "file" way plays are drawn from the same recipes.
import { describe, expect, it } from 'vitest'
import { BELLS, REST_OVER, TICK, renderStrikes, renderTick, strikesSeconds, wav } from './soundFiles'

describe('the recipes', () => {
  it('a bell says what comes next by how many strikes, each one lower', () => {
    expect(BELLS.continue).toHaveLength(1)
    expect(BELLS.switch).toHaveLength(2)
    expect(BELLS.finish).toHaveLength(3)
    expect(BELLS.done).toHaveLength(4)
    for (const strikes of [BELLS.switch, BELLS.finish, BELLS.done]) {
      for (let i = 1; i < strikes.length; i += 1) expect(strikes[i].root).toBeLessThan(strikes[i - 1].root)
    }
  })

  it("the rest's end rises, so it is never the hold's swap", () => {
    expect(REST_OVER).toHaveLength(2)
    expect(REST_OVER[1].root).toBeGreaterThan(REST_OVER[0].root)
  })
})

describe('the files', () => {
  const rate = 22050

  it('a bell is drawn for its whole length and never past full scale', () => {
    const samples = renderStrikes(BELLS.done, rate)
    expect(samples.length).toBe(Math.ceil(strikesSeconds(BELLS.done) * rate))
    expect(Math.max(...samples.map(Math.abs))).toBeLessThanOrEqual(1)
    expect(Math.max(...samples.slice(0, rate / 10).map(Math.abs))).toBeGreaterThan(0.3)
  })

  it('the tick is short and thin', () => {
    const samples = renderTick(rate)
    expect(samples.length).toBe(Math.ceil(TICK.seconds * rate))
    expect(Math.max(...samples.map(Math.abs))).toBeLessThanOrEqual(TICK.volume)
  })

  it('is a 16-bit mono WAV at the rate given', () => {
    const bytes = wav(new Float32Array([0, 1, -1]), rate)
    const view = new DataView(bytes.buffer)
    const text = (at: number) => String.fromCharCode(...bytes.slice(at, at + 4))
    expect([text(0), text(8), text(12), text(36)]).toEqual(['RIFF', 'WAVE', 'fmt ', 'data'])
    expect(view.getUint16(22, true)).toBe(1)
    expect(view.getUint32(24, true)).toBe(rate)
    expect(view.getUint32(40, true)).toBe(6)
    expect([view.getInt16(44, true), view.getInt16(46, true), view.getInt16(48, true)]).toEqual([0, 32767, -32767])
  })
})
