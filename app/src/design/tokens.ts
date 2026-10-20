// The app's design tokens (rebuild Phase 3; the decisions are in docs/rebuild/design.md).
//
// THE OWNER'S CHOICE (2026-10-20): "I pick week for everything but training, where I
// pick cards for training". The way there: three first directions he rejected ("make it
// more slick like oura style"), one Oura-style design, his colour rule ("reduce the
// number of new colours and use of more shades of the same colour for each page"), four
// styles, and three variations of style 1 dark — Calm, Cards and Week. The app is Week's
// Today, Insights and frame with Cards' training screen. The rest is in git history
// (24247d7, 21c35bc) and in reports/rebuild/p3_bakeoff.html.
//
// THE COLOUR RULE: every page has ONE colour family, used in its shades — Today teal,
// Training amber, Insights indigo, Settings and Check-in slate. Everything else is
// neutral: the page, the glass cards, the text, the white button. A status (Good, Fair,
// Pay attention) is a word, never a colour of its own.
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
  glass: string
  glassStrong: string
  glassLine: string
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
    glass: 'rgba(255, 255, 255, 0.055)',
    glassStrong: 'rgba(255, 255, 255, 0.1)',
    glassLine: 'rgba(255, 255, 255, 0.09)',
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
    glass: 'rgba(255, 255, 255, 0.72)',
    glassStrong: 'rgba(255, 255, 255, 0.92)',
    glassLine: 'rgba(20, 22, 30, 0.07)',
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

const SYSTEM = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif'
const DISPLAY = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", system-ui, sans-serif'

export const DESIGN = {
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
    score: '1.6rem',
    hero: '3.4rem',
    timer: 'min(7.2rem, 29vw)',
  },
  space: { xs: '4px', s: '8px', m: '14px', l: '20px', xl: '32px' },
  radius: { card: '22px', tile: '18px', pill: '999px' },
  line: { hair: '1px', ring: '6px', bar: '6px', timerBar: '10px', icon: '1.5px' },
  size: {
    tap: '46px',
    gym: '60px',
    icon: '1.5rem',
    readyRing: '6.6rem',
    sky: '34rem',
    content: '36rem',
    blur: '24px',
    glow: '10px',
  },
  motion: { quick: '240ms', slow: '900ms', easing: 'cubic-bezier(0.16, 1, 0.3, 1)' },
} as const

export type Design = typeof DESIGN
