// The bridge from tokens.ts to CSS: the design and one mode become the custom
// properties every stylesheet rule reads (the stylesheet never writes a colour or a size
// of its own). All four colour families are written as --teal-1 ... --slate-soft; the
// page's class (.fam-teal and so on) picks one as --f1, --f2, --f3, --f-glow and
// --f-soft. The mode is the iPhone's own setting unless the owner picks one.
import { useEffect, useState } from 'react'
import { DESIGN, FAMILIES, NEUTRALS, type FamilyId, type Family, type Mode } from './tokens'

export type ThemePref = 'auto' | Mode

export function cssVars(mode: Mode, reduced: boolean): Record<string, string> {
  const n = NEUTRALS[mode]
  const d = DESIGN
  const vars: Record<string, string> = {
    '--bg': n.bg,
    '--glass': n.glass,
    '--glass-strong': n.glassStrong,
    '--glass-line': n.glassLine,
    '--text': n.text,
    '--muted': n.muted,
    '--faint': n.faint,
    '--accent': n.accent,
    '--on-accent': n.onAccent,
    '--track': n.track,
    '--tab-bar': n.tabBar,
    '--shadow': n.shadow,
    '--sheet': n.sheet,
    '--scrim': n.scrim,
    '--font-body': d.fontBody,
    '--font-number': d.fontNumber,
    '--font-mono': d.fontMono,
    '--w-hero': String(d.weightHero),
    '--w-number': String(d.weightNumber),
    '--w-title': String(d.weightTitle),
    '--w-label': String(d.weightLabel),
    '--number-tracking': d.numberTracking,
    '--fs-caption': d.type.caption,
    '--fs-small': d.type.small,
    '--fs-body': d.type.body,
    '--fs-title': d.type.title,
    '--fs-display': d.type.display,
    '--fs-score': d.type.score,
    '--fs-hero': d.type.hero,
    '--fs-timer': d.type.timer,
    '--sp-xs': d.space.xs,
    '--sp-s': d.space.s,
    '--sp-m': d.space.m,
    '--sp-l': d.space.l,
    '--sp-xl': d.space.xl,
    '--r-card': d.radius.card,
    '--r-tile': d.radius.tile,
    '--r-pill': d.radius.pill,
    '--hair': d.line.hair,
    '--ring-w': d.line.ring,
    '--bar': d.line.bar,
    '--timer-bar': d.line.timerBar,
    '--icon-stroke': d.line.icon,
    '--tap': d.size.tap,
    '--gym': d.size.gym,
    '--icon': d.size.icon,
    '--ready-ring': d.size.readyRing,
    '--sky': d.size.sky,
    '--content': d.size.content,
    '--blur': d.size.blur,
    '--glow': d.size.glow,
    '--quick': reduced ? '0ms' : d.motion.quick,
    '--slow': reduced ? '0ms' : d.motion.slow,
    '--ease': d.motion.easing,
  }
  for (const [id, f] of Object.entries(FAMILIES[mode]) as [FamilyId, Family][]) {
    vars[`--${id}-1`] = f.f1
    vars[`--${id}-2`] = f.f2
    vars[`--${id}-3`] = f.f3
    vars[`--${id}-glow`] = f.glow
    vars[`--${id}-soft`] = f.soft
  }
  return vars
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
