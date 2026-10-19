// The bridge from tokens.ts to CSS: a style and one mode become the custom properties
// every stylesheet rule reads (the stylesheet never writes a colour or a size of its
// own). All four colour families are written as --teal-1 ... --slate-soft; the page's
// class (.fam-teal and so on) picks one as --f1, --f2, --f3, --f-glow and --f-soft.
// The mode is the iPhone's own setting unless the owner picks one.
import { useEffect, useState } from 'react'
import { FAMILIES, NEUTRALS, type FamilyId, type Mode, type Style } from './tokens'

export type ThemePref = 'auto' | Mode

export function cssVars(s: Style, mode: Mode, reduced: boolean): Record<string, string> {
  const n = { ...NEUTRALS[mode], ...(s.neutrals?.[mode] ?? {}) }
  const vars: Record<string, string> = {
    '--bg': n.bg,
    '--solid': n.solid,
    '--glass': n.glass,
    '--glass-strong': n.glassStrong,
    '--glass-line': n.glassLine,
    '--line': n.line,
    '--text': n.text,
    '--muted': n.muted,
    '--faint': n.faint,
    '--accent': n.accent,
    '--on-accent': n.onAccent,
    '--track': n.track,
    '--tab-bar': n.tabBar,
    '--shadow': n.shadow,
    '--font-body': s.fontBody,
    '--font-number': s.fontNumber,
    '--w-hero': String(s.weightHero),
    '--w-number': String(s.weightNumber),
    '--w-title': String(s.weightTitle),
    '--w-label': String(s.weightLabel),
    '--number-tracking': s.numberTracking,
    '--fs-caption': s.type.caption,
    '--fs-small': s.type.small,
    '--fs-body': s.type.body,
    '--fs-title': s.type.title,
    '--fs-display': s.type.display,
    '--fs-score': s.type.score,
    '--fs-hero': s.type.hero,
    '--fs-timer': s.type.timer,
    '--sp-xs': s.space.xs,
    '--sp-s': s.space.s,
    '--sp-m': s.space.m,
    '--sp-l': s.space.l,
    '--sp-xl': s.space.xl,
    '--r-card': s.radius.card,
    '--r-tile': s.radius.tile,
    '--r-pill': s.radius.pill,
    '--hair': s.line.hair,
    '--ring-w': s.line.ring,
    '--timer-ring-w': s.line.timerRing,
    '--bar': s.line.bar,
    '--icon-stroke': s.line.icon,
    '--tap': s.size.tap,
    '--gym': s.size.gym,
    '--icon': s.size.icon,
    '--bubble': s.size.bubble,
    '--hero-ring': s.size.heroRing,
    '--timer-ring': s.size.timerRing,
    '--sky': s.size.sky,
    '--content': s.size.content,
    '--blur': s.size.blur,
    '--glow': s.size.glow,
    '--quick': reduced ? '0ms' : s.motion.quick,
    '--slow': reduced ? '0ms' : s.motion.slow,
    '--ease': s.motion.easing,
  }
  for (const [id, f] of Object.entries(FAMILIES[mode]) as [FamilyId, (typeof FAMILIES)[Mode][FamilyId]][]) {
    vars[`--${id}-1`] = f.f1
    vars[`--${id}-2`] = f.f2
    vars[`--${id}-3`] = f.f3
    vars[`--${id}-glow`] = f.glow
    vars[`--${id}-soft`] = f.soft
  }
  return vars
}

/** The classes that tell the stylesheet how this style draws the shared screens. */
export function lookClasses(s: Style): string {
  return `style-${s.id} layout-${s.look.layout} sky-${s.look.sky}`
}

function systemMode(): Mode {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

/** The mode in force: the owner's pick, or the iPhone's own setting (followed live). */
export function useMode(pref: ThemePref): Mode {
  const [system, setSystem] = useState<Mode>(systemMode)
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!query) return
    const onChange = () => setSystem(query.matches ? 'dark' : 'light')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return pref === 'auto' ? system : pref
}

/** True when the iPhone asks for less motion (Settings > Accessibility > Motion). */
export function useReducedMotion(): boolean {
  const query = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && !!window.matchMedia?.(query).matches,
  )
  useEffect(() => {
    const list = window.matchMedia?.(query)
    if (!list) return
    const onChange = () => setReduced(list.matches)
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }, [])
  return reduced
}
