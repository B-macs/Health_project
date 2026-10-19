// The bridge from tokens.ts to CSS: the design and one mode become the custom
// properties every stylesheet rule reads (the stylesheet never writes a colour or a
// size of its own). The mode is the iPhone's own setting unless the owner picks one.
import { useEffect, useState } from 'react'
import type { Design, Mode } from './tokens'

export type ThemePref = 'auto' | Mode

export function cssVars(d: Design, mode: Mode, reduced: boolean): Record<string, string> {
  const p = mode === 'dark' ? d.dark : d.light
  return {
    '--bg': p.bg,
    '--sky-1': p.sky1,
    '--sky-2': p.sky2,
    '--glass': p.glass,
    '--glass-strong': p.glassStrong,
    '--glass-line': p.glassLine,
    '--text': p.text,
    '--muted': p.muted,
    '--faint': p.faint,
    '--accent': p.accent,
    '--on-accent': p.onAccent,
    '--readiness': p.readiness,
    '--readiness-to': p.readinessTo,
    '--sleep': p.sleep,
    '--strain': p.strain,
    '--good': p.good,
    '--fair': p.fair,
    '--low': p.low,
    '--warn': p.warn,
    '--track': p.track,
    '--tab-bar': p.tabBar,
    '--shadow': p.shadow,
    '--font-body': d.fontBody,
    '--font-number': d.fontNumber,
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
    '--timer-ring-w': d.line.timerRing,
    '--bar': d.line.bar,
    '--icon-stroke': d.line.icon,
    '--tap': d.size.tap,
    '--gym': d.size.gym,
    '--icon': d.size.icon,
    '--bubble': d.size.bubble,
    '--timer-ring': d.size.timerRing,
    '--sky': d.size.sky,
    '--content': d.size.content,
    '--blur': d.size.blur,
    '--glow': d.size.glow,
    '--quick': reduced ? '0ms' : d.motion.quick,
    '--slow': reduced ? '0ms' : d.motion.slow,
    '--ease': d.motion.easing,
  }
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
