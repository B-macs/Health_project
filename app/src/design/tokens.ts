// The design's tokens (rebuild Phase 3).
//
// The owner looked at three directions (A Calm, B Board, C Logbook; in git history and
// in reports/rebuild/p3_bakeoff.html) and chose none: "None of those, make it more
// slick like oura style" (2026-10-19). This is that design: a night sky whose glow
// takes the colour of today's readiness, frosted-glass cards, thin light numbers,
// three glowing score rings in a row, contributor bars, and a white pill button. The
// light mode is the same idea in the morning.
//
// Every colour, size, corner, line and timing a screen uses comes from here, through
// the CSS custom properties theme.ts writes on the app's root. Sizes are in rem where
// text should follow the iPhone text size (the stylesheet sets 1rem from it). The words
// live in strings.ts.

export type Mode = 'light' | 'dark'

export type Palette = {
  bg: string
  sky1: string
  sky2: string
  glass: string
  glassStrong: string
  glassLine: string
  text: string
  muted: string
  faint: string
  accent: string
  onAccent: string
  readiness: string
  readinessTo: string
  sleep: string
  strain: string
  good: string
  fair: string
  low: string
  warn: string
  track: string
  tabBar: string
  shadow: string
}

export type Design = {
  fontBody: string
  fontNumber: string
  weightHero: number
  weightNumber: number
  weightTitle: number
  weightLabel: number
  numberTracking: string
  type: {
    caption: string
    small: string
    body: string
    title: string
    display: string
    score: string
    hero: string
    timer: string
  }
  space: { xs: string; s: string; m: string; l: string; xl: string }
  radius: { card: string; tile: string; pill: string }
  line: { hair: string; ring: string; timerRing: string; bar: string; icon: string }
  size: {
    tap: string
    gym: string
    icon: string
    bubble: string
    timerRing: string
    sky: string
    content: string
    blur: string
    glow: string
  }
  motion: { quick: string; slow: string; easing: string }
  light: Palette
  dark: Palette
}

const SYSTEM = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif'
const DISPLAY = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", system-ui, sans-serif'

export const DESIGN: Design = {
  fontBody: SYSTEM,
  fontNumber: DISPLAY,
  weightHero: 200,
  weightNumber: 300,
  weightTitle: 600,
  weightLabel: 500,
  numberTracking: '-0.03em',
  type: {
    caption: '0.76rem',
    small: '0.86rem',
    body: '1rem',
    title: '1.24rem',
    display: '1.9rem',
    score: '1.85rem',
    hero: '4.4rem',
    timer: 'min(6.8rem, 27vw)',
  },
  space: { xs: '4px', s: '8px', m: '16px', l: '24px', xl: '40px' },
  radius: { card: '26px', tile: '20px', pill: '999px' },
  line: { hair: '1px', ring: '6px', timerRing: '3.5px', bar: '6px', icon: '1.5px' },
  size: {
    tap: '46px',
    gym: '60px',
    icon: '1.5rem',
    bubble: '6.2rem',
    timerRing: 'min(84vw, 21rem)',
    sky: '34rem',
    content: '36rem',
    blur: '24px',
    glow: '10px',
  },
  motion: { quick: '240ms', slow: '900ms', easing: 'cubic-bezier(0.16, 1, 0.3, 1)' },
  dark: {
    bg: '#07090E',
    sky1: 'rgba(76, 92, 168, 0.55)',
    sky2: 'rgba(120, 82, 170, 0.35)',
    glass: 'rgba(255, 255, 255, 0.055)',
    glassStrong: 'rgba(255, 255, 255, 0.1)',
    glassLine: 'rgba(255, 255, 255, 0.09)',
    text: '#F3F4F7',
    muted: '#A4AABA',
    faint: '#6C7386',
    accent: '#F3F4F7',
    onAccent: '#0A0C12',
    readiness: '#7FD8CB',
    readinessTo: '#6FA8F0',
    sleep: '#AFA0FF',
    strain: '#F6A46A',
    good: '#86E0C1',
    fair: '#F2C877',
    low: '#F5908A',
    warn: '#E58AC4',
    track: 'rgba(255, 255, 255, 0.09)',
    tabBar: 'rgba(10, 12, 18, 0.72)',
    shadow: 'rgba(0, 0, 0, 0.35)',
  },
  light: {
    bg: '#F5F5F8',
    sky1: 'rgba(168, 186, 255, 0.55)',
    sky2: 'rgba(255, 196, 168, 0.5)',
    glass: 'rgba(255, 255, 255, 0.72)',
    glassStrong: 'rgba(255, 255, 255, 0.92)',
    glassLine: 'rgba(20, 22, 30, 0.07)',
    text: '#12141B',
    muted: '#596070',
    faint: '#8B91A0',
    accent: '#12141B',
    onAccent: '#FFFFFF',
    readiness: '#1D9A8C',
    readinessTo: '#3C7BD6',
    sleep: '#6A58D8',
    strain: '#D9732E',
    good: '#1F8A6E',
    fair: '#A8741A',
    low: '#C9493F',
    warn: '#A3367A',
    track: 'rgba(20, 22, 30, 0.08)',
    tabBar: 'rgba(245, 245, 248, 0.8)',
    shadow: 'rgba(40, 46, 70, 0.1)',
  },
}
