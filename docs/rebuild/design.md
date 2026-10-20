# Design (rebuild Phase 3)

**Owner's choice** (2026-10-20): *"I pick week for everything but training, where I pick cards for training"*

The app is Week's Today, Insights and frame, with Cards' training screen. The code is
`app/src/` (tokens and theme in `design/`, parts in `ui/`, screens in `screens/`, every word
in `strings.ts`). Screenshots of the chosen design, dark and light, are in
`docs/rebuild/handoff/p3_screens/` (made-up numbers only).

## How the choice was made (2026-10-19 and 20)

1. Three directions on seeded mock data: A Calm (the Streamlit Oura palette), B Board (the
   Whoop board), C Logbook (warm paper, from `design_research.md`). The owner: *"None of
   those, make it more slick like oura style"*.
2. One Oura-style design: a night-sky glow, glass cards, thin numbers, glowing rings. The
   owner: *"I like the style let's reduce the number of new colours and use of more shades
   of the same colour for each page"* — the colour rule below — and *"Give me 3 other like
   this with slightly different styles but the colour rule I mentioned above"*: four styles,
   Glow, Halo, Mist and Line (`24247d7`).
3. *"Take style 1 dark and change it give me 3 different variations not just the shades of
   colour and font. Make one of them a relaxed easy oura look"*: Glow, Calm (the relaxed
   Oura look), Cards and Week (`21c35bc`).
4. The choice above. The styles not chosen are in git history and in
   `reports/rebuild/p3_bakeoff.html`.

## The colour rule

Every page has ONE colour family, used in its shades. Everything else is neutral: the page,
the glass cards, the text, the white button.

| Page | Family |
|---|---|
| Today | teal |
| Training | amber |
| Insights | indigo |
| Check-in, Settings | slate |

- A status (Optimal, Good, Fair, Pay attention, Light, Moderate ...) is a WORD in the page's
  strongest shade, never a colour of its own.
- A morning that needs care is a dimmer morning: the light at the top of Today is less
  bright on a Fair day (0.78) and on a Pay attention day (0.55); the colour stays.
- During a rest the training page uses its faintest shade (the bar, the phase word).
- The app's root carries the page's `.fam-*` class, so the tab bar takes the page colour.
- A warning (Key Rule 20, shown only when that body area is loaded) uses the page's
  strongest shade on its soft tint, with its words. No warning colour exists.

## Tokens (`app/src/design/tokens.ts`)

Each family has five values: `f1` the strongest against the page (it carries text, 4.5:1 or
more on the page and on a card), `f2` the middle shade (lines and fills, 3:1 or more), `f3`
the faintest (tracks, the rest phase), `glow` (the light behind a page or a ring) and `soft`
(a tinted background).

| Family | Dark f1 / f2 / f3 | Light f1 / f2 / f3 |
|---|---|---|
| teal | #8EE3D6 / #52BFB0 / #2E7F76 | #157A70 / #2A9A8C / #9ED8CF |
| amber | #FFC98A / #F59E4C / #A6602A | #9A5212 / #C9742A / #F2C795 |
| indigo | #B7B8FF / #8B8CF2 / #5455A8 | #4B4CC0 / #7071E0 / #C2C3F7 |
| slate | #C9D2E3 / #9AA7C0 / #5D697F | #3E4A63 / #6D7A94 / #C3CBDA |

| Neutral | Dark | Light |
|---|---|---|
| page | #07090E | #F5F5F8 |
| card (glass) | white 5.5 % | white 72 % |
| text | #F3F4F7 | #12141B |
| muted text | #A4AABA | #596070 |
| faint text | #6C7386 | #8B91A0 |
| button | #F3F4F7 on #0A0C12 text | #12141B with white text |

- **Type**: SF Pro Text for words, SF Pro Display for numbers (weight 300; 200 for the large
  ones), tabular figures, tracking −0.03 em. Sizes in rem, so they follow the iPhone text
  size (`html { font: -apple-system-body }`): caption 0.76, small 0.86, body 1, title 1.24,
  display 1.9, score 1.6, hero 3.4, timer `min(7.2rem, 29vw)` (about 120 px: reads from 1.5 m).
- **Space**: 4, 8, 14, 20, 32 px. **Corners**: card 22 px, tile 18 px, pill 999 px.
- **Lines**: hairline 1 px, ring 6 px, bar 6 px, timer bar 10 px, icon 1.5 px.
- **Sizes**: tap 46 px (44 pt or more everywhere), gym buttons 60 px, icon 1.5 rem, the
  readiness ring 6.6 rem, the light at the top 34 rem high, content 36 rem wide, glass blur
  24 px, glow 10 px.
- **Motion**: quick 240 ms, slow 900 ms, ease `cubic-bezier(0.16, 1, 0.3, 1)`.

## Components

- **Score ring** (`ui/parts.tsx` Ring): a track, the value as a gradient from f1 to f2 with
  a soft glow (no glow in light mode). The day-strip ring (0.9 × tap) and the readiness ring
  (6.6 rem). It grows in once when it first shows, then follows its value.
- **Card**: glass — the card colour, a hairline, a 24 px blur, a soft shadow; 22 px corners
  (tiles 18 px).
- **Day strip** (Today): seven days — the weekday letter and a small readiness ring with the
  day of the month. The open day sits on the soft tint; a tap opens a day, a sideways swipe
  moves one day.
- **Timeline** (Today's plan): a hairline in f3 through one dot per exercise (f1 with glow;
  a hollow dot for a warm-up), the name, then the dose and the weight; the white Start button
  below.
- **Set row** (Training's set tracker): one chip per side of each set — done (soft tint and a
  tick), now (filled f1 with glow), still to do (track).
- **Timer** (Training): the phase word (f1; muted while resting), the digits at the timer
  size, a 10 px bar (f2 to f1; f3 while resting); the controls: Pause and Done; while resting
  Pause, +15 s and Skip; between sides one wide Start right side / Start left side; the next
  set on a card below. The tab bar is hidden; the screen stays on.
- **Tiles** (Today, Insights): a label, one large thin number (a long one in kilograms at the
  display size), the status word, a note.
- **Contributor bar** (Insights' body areas): name and value, a 6 px bar from f2 to f1, a
  note; "—" when nothing is measured.
- **Area chart** (Insights): a smooth line in f1, a fading fill, a glowing last point.
- **Sheet** (not built yet; the rule for Phase 4 on): glass from the bottom, card corners on
  top, a grab handle; it slides up in the quick time with the ease, appears without sliding
  under Reduce Motion, and closes on a swipe down or a tap outside.
- **Tab bar**: a glass dock with five tabs (Today, Check-in, Training, Insights, Settings),
  icon and word; the open tab in the text colour with its icon in f1 and a glow.
- **Buttons**: the white pill (main action), the glass pill (second action), 60 px gym
  buttons; round 46 px icon buttons; a segmented control for Settings.

## Motion rules

- A ring or a bar grows in once (slow, eased), then follows its value.
- A timer moves every tick in a short linear step (quick).
- A press scales to 0.97. The light at the top changes with the page and the day.
- Nothing loops; nothing moves on a screen at rest.
- Reduce Motion (the iPhone setting): one rule turns every transition off and rings and bars
  show their value at once.

## Page shape

- `html` and `body` never scroll; one inner scroller fills the screen and the tab bar docks
  below it (Lauscher's shape: iOS misplaces fixed bars when the page scrolls).
- Safe areas in standalone mode: the light at the top runs under the status bar, the tab bar
  pads the home indicator.
- Dark and light follow the iPhone unless Settings picks one.

## Strings

- Every word on screen is in `app/src/strings.ts`; a screen file writes no sentence.
- Plain English, how before why, no hedging, no Stage 1 text (Key Rule 19 and the
  patient-facing text rules).
- The p3 gate's `text_rule_violations` runs the jargon, repo-internal and hedge lists and the
  Stage 1 scan from `tests/` over every string.
