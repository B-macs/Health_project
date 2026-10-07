import { describe, expect, it } from 'vitest'
import { versionLine } from './version'

describe('versionLine', () => {
  it('shows the number, the commit and when it was built', () => {
    const line = versionLine(
      { number: '0.1.0', commit: 'abc1234', built: '2026-10-07T07:41:00Z' },
      'en-GB',
      'UTC',
    )
    expect(line).toBe('0.1.0 (abc1234) · built 7 Oct, 07:41')
  })

  it('says unknown for a broken build time instead of showing NaN', () => {
    expect(versionLine({ number: '0.1.0', commit: 'dev', built: 'nope' })).toBe(
      '0.1.0 (dev) · built unknown',
    )
  })
})
