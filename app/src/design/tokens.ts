// The design's tokens (rebuild Phase 3).
//
// The owner looked at three first directions (A Calm, B Board, C Logbook; recorded in
// docs/rebuild/state.md) and chose none: "None of those, make it more slick like oura
// style" (2026-10-19). He liked the Oura-style result, then set the colour rule: "reduce
// the number of new colours and use of more shades of the same colour for each page",
// and asked for "3 other like this with slightly different styles but the colour rule".
// From those four he took style 1 in dark: "Take style 1 dark and change it give me 3
// different variations not just the shades of colour and font. Make one of them a
// relaxed easy oura look". So the styles are now Glow and three layouts of it: Calm
// (the relaxed Oura look), Cards and Week.
//
// THE COLOUR RULE: every page has ONE colour family, used in its shades — Today teal,
// Training amber, Insights indigo, Settings and Check-in slate — as Oura gives each
// section its own hue. Everything else is neutral: the page, the cards, the text, the
// button. A status (Good, Fair, Pay attention) is a word, never a colour of its own.
// The families and the neutrals are shared by all four styles; a style changes layout,
// shape, type and light, never the colours.
//
// Every colour, size, corner, line and timing a screen uses comes from here, through the
// CSS custom properties theme.ts writes on the app's root. Sizes are in rem where text
// should follow the iPhone text size. The words live in strings.ts.

export type Mode = 'light' | 'dark'

/** One page's colour: f1 the strongest against the page (it can carry text), f2 the
 *  middle shade (lines, fills), f3 the faintest (tracks, the rest phase), glow the light
 *  behind a page or a ring, soft a tinted background. */
export type Family = { f1: string; f2: string; f3: string; glow: string; soft: string }
export type FamilyId = 'teal' | 'amber' | 'indigo' | 'slate'

export type Neutrals = {
  bg: string
  solid: string
  glass: string
  glassStrong: string
  glassLine: string
  line: string
  text: string
  muted: string
  faint: string
  accent: string
  onAccent: string
  track: string
  tabBar: string
  shadow: string
}

export const FAMILIES: Record<Mode, Record<FamilyId, Family>> = {
  dark: {
    teal: { f1: '#8EE3D6', f2: '#52BFB0', f3: '#2E7F76', glow: 'rgba(82, 191, 176, 0.42)', soft: 'rgba(142, 227, 214, 0.14)' },
    amber: { f1: '#FFC98A', f2: '#F59E4C', f3: '#A6602A', glow: 'rgba(245, 158, 76, 0.42)', soft: 'rgba(255, 201, 138, 0.14)' },
    indigo: { f1: '#B7B8FF', f2: '#8B8CF2', f3: '#5455A8', glow: 'rgba(139, 140, 242, 0.42)', soft: 'rgba(183, 184, 255, 0.14)' },
    slate: { f1: '#C9D2E3', f2: '#9AA7C0', f3: '#5D697F', glow: 'rgba(154, 167, 192, 0.3)', soft: 'rgba(201, 210, 227, 0.12)' },
  },
  light: {
    teal: { f1: '#157A70', f2: '#2A9A8C', f3: '#9ED8CF', glow: 'rgba(42, 154, 140, 0.3)', soft: 'rgba(21, 122, 112, 0.1)' },
    amber: { f1: '#9A5212', f2: '#C9742A', f3: '#F2C795', glow: 'rgba(201, 116, 42, 0.3)', soft: 'rgba(154, 82, 18, 0.1)' },
    indigo: { f1: '#4B4CC0', f2: '#7071E0', f3: '#C2C3F7', glow: 'rgba(112, 113, 224, 0.3)', soft: 'rgba(75, 76, 192, 0.1)' },
    slate: { f1: '#3E4A63', f2: '#6D7A94', f3: '#C3CBDA', glow: 'rgba(109, 122, 148, 0.24)', soft: 'rgba(62, 74, 99, 0.08)' },
  },
}

export const NEUTRALS: Record<Mode, Neutrals> = {
  dark: {
    bg: '#07090E',
    solid: '#11141B',
    glass: 'rgba(255, 255, 255, 0.055)',
    glassStrong: 'rgba(255, 255, 255, 0.1)',
    glassLine: 'rgba(255, 255, 255, 0.09)',
    line: 'rgba(255, 255, 255, 0.16)',
    text: '#F3F4F7',
    muted: '#A4AABA',
    faint: '#6C7386',
    accent: '#F3F4F7',
    onAccent: '#0A0C12',
    track: 'rgba(255, 255, 255, 0.09)',
    tabBar: 'rgba(10, 12, 18, 0.72)',
    shadow: 'rgba(0, 0, 0, 0.35)',
  },
  light: {
    bg: '#F5F5F8',
    solid: '#FFFFFF',
    glass: 'rgba(255, 255, 255, 0.72)',
    glassStrong: 'rgba(255, 255, 255, 0.92)',
    glassLine: 'rgba(20, 22, 30, 0.07)',
    line: 'rgba(20, 22, 30, 0.14)',
    text: '#12141B',
    muted: '#596070',
    faint: '#8B91A0',
    accent: '#12141B',
    onAccent: '#FFFFFF',
    track: 'rgba(20, 22, 30, 0.08)',
    tabBar: 'rgba(245, 245, 248, 0.8)',
    shadow: 'rgba(40, 46, 70, 0.1)',
  },
}

/** The colour family of each page. */
export const PAGE_FAMILY = {
  today: 'teal',
  training: 'amber',
  insights: 'indigo',
  checkin: 'slate',
  settings: 'slate',
} as const satisfies Record<string, FamilyId>

export type StyleId = '1' | '2' | '3' | '4'

/** How a style draws the screens. `layout` picks the screen components; the rest are
 *  classes the stylesheet reads. */
export type Look = {
  layout: 'glow' | 'calm' | 'cards' | 'week'
  sky: 'glow' | 'soft'
}

export type Style = {
  id: StyleId
  look: Look
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
    heroRing: string
    timerRing: string
    sky: string
    content: string
    blur: string
    glow: string
  }
  motion: { quick: string; slow: string; easing: string }
  /** Per-style changes to the neutrals. */
  neutrals?: Partial<Record<Mode, Partial<Neutrals>>>
}

const SYSTEM = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif'
const DISPLAY = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", system-ui, sans-serif'
const EASE = 'cubic-bezier(0.16, 1, 0.3, 1)'

const GLOW_BASE: Omit<Style, 'id' | 'look'> = {
  fontBody: SYSTEM,
  fontNumber: DISPLAY,
  weightHero: 200,
  weightNumber: 300,
  weightTitle: 600,
  weightLabel: 500,
  numberTracking: '-0.03em',
  type: { caption: '0.76rem', small: '0.86rem', body: '1rem', title: '1.24rem', display: '1.9rem', score: '1.85rem', hero: '4.4rem', timer: 'min(6.8rem, 27vw)' },
  space: { xs: '4px', s: '8px', m: '16px', l: '24px', xl: '40px' },
  radius: { card: '26px', tile: '20px', pill: '999px' },
  line: { hair: '1px', ring: '6px', timerRing: '3.5px', bar: '6px', icon: '1.5px' },
  size: { tap: '46px', gym: '60px', icon: '1.5rem', bubble: '6.2rem', heroRing: '0rem', timerRing: 'min(84vw, 21rem)', sky: '34rem', content: '36rem', blur: '24px', glow: '10px' },
  motion: { quick: '240ms', slow: '900ms', easing: EASE },
}

/** 1 Glow: a glow at the top, glass cards, three rings in a row (the one he took). */
const GLOW: Style = { ...GLOW_BASE, id: '1', look: { layout: 'glow', sky: 'glow' } }

/** 2 Calm, the relaxed Oura look: one soft glowing orb, a big greeting, plenty of space,
 *  the detail one tap away; the lightest numbers and the slowest motion. */
const CALM: Style = {
  ...GLOW_BASE,
  id: '2',
  look: { layout: 'calm', sky: 'soft' },
  weightHero: 100,
  weightNumber: 200,
  weightTitle: 500,
  type: { caption: '0.78rem', small: '0.88rem', body: '1.02rem', title: '1.3rem', display: '2.15rem', score: '1.9rem', hero: '5.4rem', timer: 'min(7.6rem, 30vw)' },
  space: { xs: '4px', s: '10px', m: '20px', l: '32px', xl: '52px' },
  radius: { card: '30px', tile: '22px', pill: '999px' },
  line: { hair: '1px', ring: '2px', timerRing: '2px', bar: '4px', icon: '1.4px' },
  size: { ...GLOW_BASE.size, heroRing: 'min(76vw, 17rem)', timerRing: 'min(84vw, 20rem)', sky: '42rem', blur: '28px', glow: '16px' },
  motion: { quick: '300ms', slow: '1300ms', easing: EASE },
}

/** 3 Cards: each score on its own card with its last seven days; the timer with a set
 *  tracker and a bar. */
const CARDS: Style = {
  ...GLOW_BASE,
  id: '3',
  look: { layout: 'cards', sky: 'glow' },
  type: { ...GLOW_BASE.type, hero: '3.6rem', timer: 'min(7.2rem, 29vw)' },
  radius: { card: '22px', tile: '18px', pill: '999px' },
  line: { ...GLOW_BASE.line, bar: '10px' },
}

/** 4 Week: a week strip on top, tiles for the scores, the session as a timeline; the
 *  timer above the list of the exercise's sets. */
const WEEK: Style = {
  ...GLOW_BASE,
  id: '4',
  look: { layout: 'week', sky: 'glow' },
  type: { ...GLOW_BASE.type, score: '1.6rem', hero: '3.4rem', timer: 'min(4.6rem, 19vw)' },
  space: { xs: '4px', s: '8px', m: '14px', l: '20px', xl: '32px' },
  radius: { card: '22px', tile: '18px', pill: '999px' },
  size: { ...GLOW_BASE.size, bubble: '4.4rem', heroRing: '6.6rem', timerRing: 'min(62vw, 15rem)' },
}

export const STYLES: Record<StyleId, Style> = { '1': GLOW, '2': CALM, '3': CARDS, '4': WEEK }
export const STYLE_IDS: StyleId[] = ['1', '2', '3', '4']
