// The preview shows only made-up numbers (rebuild Phase 3): data.ts must be exactly
// what the seeded generator makes, so no hand-typed value can enter the app, and the
// values stay inside the ranges the screens are drawn for.
import { describe, expect, it } from 'vitest'
import { MOCK } from './data'
import { SEED, generate } from './generate'

describe('the mock data', () => {
  it('is exactly the seeded generator output (run app/scripts/make-mock.ts after a change)', () => {
    expect(MOCK).toEqual(generate(SEED))
  })

  it('gives the same numbers on every run', () => {
    expect(generate(SEED)).toEqual(generate(SEED))
  })

  it('keeps every score in its range', () => {
    for (const day of MOCK.days) {
      expect(day.readiness.value).toBeGreaterThanOrEqual(0)
      expect(day.readiness.value).toBeLessThanOrEqual(100)
      expect(day.sleep.value).toBeLessThanOrEqual(100)
      expect(day.strain.value).toBeGreaterThanOrEqual(0)
      expect(day.strain.value).toBeLessThanOrEqual(21)
    }
  })
})
