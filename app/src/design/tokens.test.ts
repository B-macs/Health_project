// The design's tokens are complete and readable in both modes (rebuild Phase 3).
// Contrast is WCAG 2's: 4.5 for text, 3 for large numbers and graphics; a glass colour
// is laid over the page colour before it is measured.
import { describe, expect, it } from 'vitest'
import { DESIGN, FAMILIES, NEUTRALS, PAGE_FAMILY, type FamilyId, type Mode } from './tokens'

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
const FAMILY_IDS = Object.keys(FAMILIES.dark) as FamilyId[]

function surfaces(mode: Mode): { name: string; rgb: RGB }[] {
  const n = NEUTRALS[mode]
  return [
    { name: 'page', rgb: parse(n.bg).rgb },
    { name: 'card', rgb: over(n.glass, n.bg) },
  ]
}

describe('the colour rule', () => {
  it('every page has one colour family', () => {
    for (const family of Object.values(PAGE_FAMILY)) expect(FAMILY_IDS).toContain(family)
  })

  it('both modes name the same families and neutrals', () => {
    expect(Object.keys(FAMILIES.light).sort()).toEqual([...FAMILY_IDS].sort())
    expect(Object.keys(NEUTRALS.light).sort()).toEqual(Object.keys(NEUTRALS.dark).sort())
  })
})

describe.each(MODES)('%s mode contrast', (mode) => {
  const n = NEUTRALS[mode]

  it.each(surfaces(mode).map((s) => [s.name, s.rgb] as const))('text and muted text read on the %s', (_name, rgb) => {
    expect(contrast(parse(n.text).rgb, rgb)).toBeGreaterThanOrEqual(7)
    expect(contrast(parse(n.muted).rgb, rgb)).toBeGreaterThanOrEqual(4.5)
  })

  it('the button word reads on the button', () => {
    expect(contrast(parse(n.onAccent).rgb, parse(n.accent).rgb)).toBeGreaterThanOrEqual(4.5)
  })

  it.each(FAMILY_IDS)('%s: the strongest shade carries text, the middle one draws lines', (id) => {
    const f = FAMILIES[mode][id]
    for (const s of surfaces(mode)) {
      expect(contrast(parse(f.f1).rgb, s.rgb), `${id} f1 on the ${s.name}`).toBeGreaterThanOrEqual(4.5)
      expect(contrast(parse(f.f2).rgb, s.rgb), `${id} f2 on the ${s.name}`).toBeGreaterThanOrEqual(3)
    }
    expect(contrast(parse(n.onAccent).rgb, parse(f.f1).rgb), `${id}: a word on its strongest shade`).toBeGreaterThanOrEqual(4.5)
  })
})

describe('sizes', () => {
  it('every tap target is 44 pt or more', () => {
    for (const size of [DESIGN.size.tap, DESIGN.size.gym]) expect(parseFloat(size)).toBeGreaterThanOrEqual(44)
  })

  it('text sizes are in rem, so they follow the iPhone text size', () => {
    for (const size of Object.values(DESIGN.type)) expect(size).toMatch(/rem/)
  })
})
