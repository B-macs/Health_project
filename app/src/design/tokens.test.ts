// The design's tokens are complete and readable in both modes (rebuild Phase 3).
// Contrast is WCAG 2's: 4.5 for text, 3 for large numbers and graphics; a glass
// colour is laid over the page colour before it is measured.
import { describe, expect, it } from 'vitest'
import { DESIGN, type Mode, type Palette } from './tokens'

type RGB = [number, number, number]

function parse(colour: string): { rgb: RGB; alpha: number } {
  const hex = colour.match(/^#([0-9a-f]{6})$/i)
  if (hex) {
    const n = parseInt(hex[1], 16)
    return { rgb: [(n >> 16) & 255, (n >> 8) & 255, n & 255], alpha: 1 }
  }
  const rgba = colour.match(/^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/)
  if (rgba) return { rgb: [+rgba[1], +rgba[2], +rgba[3]], alpha: +rgba[4] }
  throw new Error(`not a colour: ${colour}`)
}

/** A colour laid over an opaque background. */
function over(top: string, under: string): RGB {
  const t = parse(top)
  const u = parse(under).rgb
  return t.rgb.map((c, i) => Math.round(c * t.alpha + u[i] * (1 - t.alpha))) as RGB
}

function luminance([r, g, b]: RGB): number {
  const lin = (c: number) => {
    const s = c / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

function contrast(a: RGB, b: RGB): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const MODES: Mode[] = ['dark', 'light']
const KEYS = Object.keys(DESIGN.dark) as (keyof Palette)[]

describe('the palettes', () => {
  it('name the same colours in both modes', () => {
    expect(Object.keys(DESIGN.light).sort()).toEqual([...KEYS].sort())
  })

  it.each(MODES)('%s: every colour parses', (mode) => {
    for (const key of KEYS) expect(() => parse(DESIGN[mode][key]), key).not.toThrow()
  })
})

describe.each(MODES)('%s mode contrast', (mode) => {
  const p = DESIGN[mode]
  const page = parse(p.bg).rgb
  const card = over(p.glass, p.bg)

  it('body text reads at 7:1 or more on the page and on a card', () => {
    expect(contrast(parse(p.text).rgb, page)).toBeGreaterThanOrEqual(7)
    expect(contrast(parse(p.text).rgb, card)).toBeGreaterThanOrEqual(7)
  })

  it('muted text reads at 4.5:1 or more on the page and on a card', () => {
    expect(contrast(parse(p.muted).rgb, page)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(parse(p.muted).rgb, card)).toBeGreaterThanOrEqual(4.5)
  })

  it('the button word reads on the button', () => {
    expect(contrast(parse(p.onAccent).rgb, parse(p.accent).rgb)).toBeGreaterThanOrEqual(4.5)
  })

  it.each(['readiness', 'sleep', 'strain', 'good', 'fair', 'low'] as const)(
    '%s is visible on a card (3:1, graphics and large text)',
    (key) => {
      expect(contrast(parse(p[key]).rgb, card)).toBeGreaterThanOrEqual(3)
    },
  )
})

describe('sizes', () => {
  it('every tap target is 44 pt or more', () => {
    for (const size of [DESIGN.size.tap, DESIGN.size.gym]) expect(parseFloat(size)).toBeGreaterThanOrEqual(44)
  })

  it('text sizes are in rem, so they follow the iPhone text size', () => {
    for (const size of Object.values(DESIGN.type)) expect(size).toMatch(/rem/)
  })
})
