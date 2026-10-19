// The design's tokens (rebuild Phase 3).
//
// The owner looked at three first directions (A Calm, B Board, C Logbook; recorded in
// docs/rebuild/state.md) and chose none: "None of those, make it more slick like oura
// style" (2026-10-19). He liked the Oura-style result, then set the colour rule: "reduce
// the number of new colours and use of more shades of the same colour for each page",
// and asked for "3 other like this with slightly different styles but the colour rule".
//
// THE COLOUR RULE: every page has ONE colour family, used in its shades — Today teal,
// Training amber, Insights indigo, Settings and Check-in slate — as Oura gives each
// section its own hue. Everything else is neutral: the page, the cards, the text, the
// button. A status (Good, Fair, Pay attention) is a word, never a colour of its own.
// The families and the neutrals are shared by all four styles; a style changes shape,
// type, light and surface, never the colours.
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

/** How a style draws the shared screens. Each value is a class the stylesheet reads. */
export type Look = {
  today: 'trio' | 'hero'
  sky: 'glow' | 'halo' | 'wash' | 'none'
  card: 'glass' | 'tint' | 'mist' | 'line'
  tabbar: 'dock' | 'pill' | 'float' | 'line'
  button: 'white' | 'family'
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
  /** Per-style changes to the neutrals (for example a true black page). */
  neutrals?: Partial<Record<Mode, Partial<Neutrals>>>
}

const SYSTEM = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif'
const DISPLAY = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", system-ui, sans-serif'
const EASE = 'cubic-bezier(0.16, 1, 0.3, 1)'

/** 1 Glow: a night-sky glow at the top, glass cards, three rings in a row. */
const GLOW: Style = {
  id: '1',
  look: { today: 'trio', sky: 'glow', card: 'glass', tabbar: 'dock', button: 'white' },
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

/** 2 Halo: one large readiness ring with a soft halo, cards tinted in the page colour,
 *  the main button in the page colour. */
const HALO: Style = {
  id: '2',
  look: { today: 'hero', sky: 'halo', card: 'tint', tabbar: 'pill', button: 'family' },
  fontBody: SYSTEM,
  fontNumber: DISPLAY,
  weightHero: 200,
  weightNumber: 300,
  weightTitle: 600,
  weightLabel: 500,
  numberTracking: '-0.03em',
  type: { caption: '0.76rem', small: '0.86rem', body: '1rem', title: '1.2rem', display: '1.8rem', score: '1.55rem', hero: '5rem', timer: 'min(7rem, 28vw)' },
  space: { xs: '4px', s: '8px', m: '16px', l: '24px', xl: '40px' },
  radius: { card: '22px', tile: '18px', pill: '999px' },
  line: { hair: '1px', ring: '7px', timerRing: '5px', bar: '6px', icon: '1.6px' },
  size: { tap: '46px', gym: '60px', icon: '1.5rem', bubble: '4.4rem', heroRing: 'min(66vw, 15.5rem)', timerRing: 'min(84vw, 21rem)', sky: '26rem', content: '36rem', blur: '0px', glow: '16px' },
  motion: { quick: '240ms', slow: '1000ms', easing: EASE },
}

/** 3 Mist: the page colour washes down the whole screen, lighter and larger numbers,
 *  very light glass, a floating tab bar. */
const MIST: Style = {
  id: '3',
  look: { today: 'trio', sky: 'wash', card: 'mist', tabbar: 'float', button: 'white' },
  fontBody: SYSTEM,
  fontNumber: DISPLAY,
  weightHero: 100,
  weightNumber: 200,
  weightTitle: 500,
  weightLabel: 500,
  numberTracking: '-0.035em',
  type: { caption: '0.78rem', small: '0.88rem', body: '1.02rem', title: '1.28rem', display: '2.05rem', score: '2.05rem', hero: '4.9rem', timer: 'min(7.4rem, 29vw)' },
  space: { xs: '4px', s: '10px', m: '18px', l: '28px', xl: '44px' },
  radius: { card: '30px', tile: '24px', pill: '999px' },
  line: { hair: '1px', ring: '4px', timerRing: '2.5px', bar: '4px', icon: '1.4px' },
  size: { tap: '48px', gym: '62px', icon: '1.5rem', bubble: '6.6rem', heroRing: '0rem', timerRing: 'min(86vw, 22rem)', sky: '52rem', content: '36rem', blur: '32px', glow: '14px' },
  motion: { quick: '260ms', slow: '1100ms', easing: EASE },
}

/** 4 Line: clean black (or white), thin lines, no glow, cards drawn with outlines only,
 *  steadier medium-weight numbers. */
const LINE: Style = {
  id: '4',
  look: { today: 'trio', sky: 'none', card: 'line', tabbar: 'line', button: 'white' },
  fontBody: SYSTEM,
  fontNumber: DISPLAY,
  weightHero: 300,
  weightNumber: 400,
  weightTitle: 600,
  weightLabel: 500,
  numberTracking: '-0.02em',
  type: { caption: '0.76rem', small: '0.86rem', body: '1rem', title: '1.18rem', display: '1.75rem', score: '1.7rem', hero: '4rem', timer: 'min(7rem, 28vw)' },
  space: { xs: '4px', s: '8px', m: '14px', l: '20px', xl: '32px' },
  radius: { card: '16px', tile: '14px', pill: '999px' },
  line: { hair: '1px', ring: '3px', timerRing: '3px', bar: '3px', icon: '1.6px' },
  size: { tap: '46px', gym: '58px', icon: '1.45rem', bubble: '6rem', heroRing: '0rem', timerRing: 'min(82vw, 20rem)', sky: '0rem', content: '36rem', blur: '0px', glow: '0px' },
  motion: { quick: '200ms', slow: '700ms', easing: EASE },
  neutrals: {
    dark: { bg: '#000000', tabBar: '#000000' },
    light: { bg: '#FFFFFF', tabBar: '#FFFFFF' },
  },
}

export const STYLES: Record<StyleId, Style> = { '1': GLOW, '2': HALO, '3': MIST, '4': LINE }
export const STYLE_IDS: StyleId[] = ['1', '2', '3', '4']
