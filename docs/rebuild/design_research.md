# Phase 3 design research

*2026-10-19. Input for the design bake-off: A "Calm", B "Board" and C "Logbook" (proposed in section 5). This repo is public: no personal readings here.*

## 1. Main points

1. **One answer first, detail one tap away.** Oura puts its three scores as small shortcuts above one daily highlight. Whoop puts three dials in a row, and each dial opens its own page. Our engine already returns one verdict for the day; every direction shows it first, with no scroll.
2. **The gym screen is read from 1.5 m.** Signs need about 1 inch of letter height per 10 feet, so a digit must be about 12-15 mm tall. On an iPhone (1 pt is about 0.166 mm) that is a timer of **about 120-130 px**. Today the hold timer is 72 px (readable at about 1 m) and the rest timer is 52 px in grey.
3. **A set logger wins on status and speed.** Previous, target and done values look different. One press confirms a set and starts the rest. The next set shows below. A Home-Screen web app has no Live Activity and no vibration, so the screen stays on and the bells carry every cue.
4. **A trend card is one number, one named comparison, one small line.** A value not measured shows "—". A trend with too little history says so (Apple Fitness waits 180 days).
5. **A and B need repairs, not only a port.** Muted text fails contrast in both. 61 lines in `app.py` and `views/training.py` set a 9-11 px font.
6. **Lauscher gives the sibling frame:** the tab bar, safe areas, token names, font, wins and version line. Direction C uses that frame with a light "paper" look, and it uses colour only where colour means something.

## 2. What the best apps do

### Daily score screen
| App | Does well | Fits us | Avoid |
|---|---|---|---|
| Oura (redesign 2024-10-03) | Five tabs became three (Today, Vitals, My Health). Scores are shortcuts at the top, then one highlight, a timeline, discoveries. Three depths: daily glance, focused metric, long trend. One colour system: colour marks what needs attention. | The three depths map to Home, drill-down, Insights. One colour meaning on every screen. For A: compact score shortcuts, not three tall cards. | A highlight that changes with the time of day. Our verdict stays the same on Home and Training all day. |
| Whoop (dials, 2023) | Sleep, Recovery and Strain dials in a row; each opens a deep-dive page. Recovery bands: green 67-100 %, yellow 34-66 %, red 0-33 %. Strain on 0-21 with a daily target. | Our strain is on 0-21 already. Three numbers side by side, each one a door. For B: the dial row on top, tiles below. | A reviewer counted 20+ screens behind Home and found the path to detail unclear. Colour without a word. |
| Apple Fitness | Workout screens: large, high-contrast metrics; pause and stop easy to tap; clear start and stop feedback; a summary that confirms the end; nothing unrelated during a workout. | These are our gym rules. The summary is our session-complete screen. | Apple's rule: do not copy or change the Activity rings for other data. So no three concentric rings for our scores. |

### Set logger (Strong, Hevy)
- **Hevy**: a PREVIOUS column on the left of each set row; a tap copies it into today's set. A tick completes the set and starts that exercise's rest timer: ±15 s, skip, off. On the lock screen a Live Activity shows the exercise, the next set, weight × reps and the countdown, with a button that completes the set.
- **Strong**: aims to "stay out of your way". Users of other apps ask for its rest timer, which starts by itself when a set is entered.
- **A design write-up adds**: label every value by status (target from the plan, previous from history, done today); pre-filled values look unconfirmed; undo is cheap; the rest timer keeps an end time, so it stays right in the background.
- **Fits us**: the guided flow already shows one set at a time and stamps the rest at its start. Keep one confirm press per set. Show "Last time" in muted text, the target large, the done value in ink with a tick.
- **Avoid**: dense five-column rows (fine at arm's length, unreadable at 1.5 m). A web app cannot show a Live Activity, so keep the screen on instead.

### Guided timer
- **Interval-timer apps**: one colour per phase (warm for work, cool for rest), digits across the full width, sound cues so the eyes can stay off the screen. A glimpse of colour tells the phase.
- **Today's app**: hold 72 px; rest 52 px in #6B7280 (3.9:1); Start and Reset at 14 px. The four bells (continue, switch, finish, done) are right: they say what comes next.
- **Fits us**: the phase fills the screen; digits about 128 px with tabular figures; "Next: set 3 · 10 reps · 20 kg" below at 28-44 px; Pause, +15 s and Skip at 64 px in the bottom third; the bell names the ending.
- **Avoid**: a countdown ring around the digits (it costs size and it moves); digits that change size; small buttons.

### Trend cards
- **Apple Health**: a highlight is one sentence that compares this week with last week, with a small chart. **Apple Fitness** trends compare the 90-day average with the 365-day average, show an up or down arrow, and open a graph on tap.
- **Oura** keeps the daily glance on top and long trends in My Health. **Whoop** has a weekly strain-against-recovery graph that opens.
- **Fits us**: label · big number with unit · change against a named period ("+3.5 vs 6 weeks ago") · a 48 px line with no axis · a tap opens the full chart with axes (the current axis code stays).
- **Avoid**: a change without its period; a line scaled to its own min and max (noise looks like change); green or red on a trend with no good or bad direction.

## 3. The current look (A and B rebuild these)

Sources: `styles.py` (`OURA` at 768 px and below, `WHOOP` above), the Home cards in `app.py`, the band colours in `services/dashboard.py`.

| Token | A Calm (Oura, phone) | B Board (Whoop, desktop) |
|---|---|---|
| Background | #0B0F1E | #07080D |
| Surface / raised | #131929 / #1A2238 | #0E1018 / #13161F |
| Text | #D4DCEE | #FFFFFF |
| Muted text | #6B7A9B (4.1:1 on surface: fails) | #5A6377 (3.2:1: fails) |
| Border | #1E2840 | #1C1F2C |
| Good / fair / low | #6BAF8B / #BFA06A / #C47878 | #00E874 / #F5C700 / #FF2D44 |
| Radius | 18 px cards, 14 px buttons, 12 px inputs | 4 px |
| h1 / h2 / h3 | 26 / 18 / 14 px, weight 300-500 | 20 / 11 / 10 px, capitals, tracking 1.5-2 px |
| Body / caption | 15 px (line height 1.65) / 12 px | 13 px / 10 px |
| Metric value | 30 px, weight 300, system-ui | 22 px, weight 700, monospace |
| Buttons | 15 px, padding 14 px, primary filled green | 12 px, primary filled green |
| Card edge | shadow 0 2px 14px rgba(0,0,0,.3), no border | 1 px border, no shadow |

The Strength screen's board skin (`_SKIN_BOARD`): panel #0E1018, ink #F4F6FB / #9AA3B2 / #5A6377, hairline rgba(255,255,255,.06), radius 16 px. Sleep stages: deep #1E4D7B, light #3C8FD4, REM #8FCDF0, awake #EFE9DD (cream, so waking is not an alarm colour).

**Home cards today**: three cards, each 460 px tall, a full-bleed photo under a dark scrim (18 % to 80 % black). Overline 10 px capitals, tracking 3 px. A 270° arc gauge, 220 px, stroke 11, track white at 12 %. The score sits inside the arc: 58 px weight 800 (readiness shows two numbers at 42 px, daily and trend). Below: the band word at 13 px in the band colour, a 9.5 px monospace badge, a 20 px header, a 13 px sentence in white at 70 %. A fixed 56 px header with 44 × 56 px day arrows, a 52 px white check-in button, and a 68 px tab bar whose active tab uses B's #00E874 on A's navy.

**A, done properly**: muted text at 4.5:1 or more (axis text #5A6785 is 3.1:1 and "#555" is 2.1-2.6:1 today); no text under 13 px; all three scores visible without scroll (three 460 px cards take about 1,400 px); one arc per score, never concentric; a light mode; the tab bar in A's own colours.
**B, done properly**: muted text at 4.5:1 or more; labels in sentence case at 13 px or more (no 9-10 px capitals); a real phone layout (two-column tiles, numbers 32 px or more), not the desktop board made small; one green, not two (#00E874 beside #6BAF8B today); a light mode.

## 4. Lauscher: what the owner already likes (`../lauscher/app/src`)

- **Tab bar** (`ui/parts.tsx`, `styles.css`): three tabs, `grid-template-columns: repeat(3, 1fr)`, padding `8px 8px calc(env(safe-area-inset-bottom) + 8px)`. Each tab is `min-height: var(--tap)` (52 px), icon 26 px, label 13 px weight 700; active `--brand`, others `--muted`; background `--bg`, top line 1 px `--line`. Height 68 px plus the home-indicator inset. A tap on the open tab scrolls to the top. The full-screen player hides the bar.
- **Page shape**: `html` and `body` never scroll; one inner `.scroller` in a `100dvh` column; the bars sit in a `.dock` below it (iOS misplaces fixed bars when the whole page scrolls). Inner screens have a sticky back bar: a 52 px round back button over `blur(12px)` and 86 % `--bg`.
- **Safe areas**: `viewport-fit=cover`; top padding `calc(env(safe-area-inset-top) + 12px)`; sheets pad `env(safe-area-inset-bottom)`. `theme-color` and splash images for light and dark.
- **Tokens**: `--bg --surface --surface-2 --text --muted --line --brand --brand-ink --accent --goal --radius --shadow --tap --font`. Light #f6f1e7 / #fffdf8 / #1e2a2f, brand #1f4b57; dark #14181b / #1d2327 / #ede6da, brand #3a7f8f. `--radius` 18 px, `--tap` 52 px. Dark mode follows the iPhone (`prefers-color-scheme`, `color-scheme: light dark`).
- **Type**: Atkinson Hyperlegible Next Variable (fontsource 5.3.0) with a plain zero (the owner's choice D22); body 18 px, line height 1.45; `tabular-nums` for times. Buttons 52 px high, radius 16 px, 18 px bold, full width.
- **Wins** (`wins/WinOverlay.tsx`): a full-screen layer over everything, one radial gradient per kind, title 34 px, text 19 px, one 58 px button that marks the win as seen. At most two per trigger, only when the player is idle; a short tune (a setting); confetti and number rolls only without Reduce Motion.
- **Version line** (Settings, last line): small, muted, centred: `Version 0.1.0 · 7 Oct, 08:12 (451d289)` (version, build time in the interface language, commit). Taps on it open a debug console. A banner offers a waiting update with a reload button.
- **Reduce Motion**: one global rule sets every animation to 1 ms and turns transitions off.
- **Screen on** (`player/wakeLock.ts`): asks for the Wake Lock inside a tap, asks again on `visibilitychange`, lets go on pause or exit. It works in Home-Screen apps from iOS 18.4.

## 5. Direction C proposal: "Logbook"

**Idea.** Each screen is one page of a training log: warm paper, dark ink, one large number or one plain sentence at the top, nothing decorative. Colour means something or it is absent: a score band, the timer's phase, a warning.

It differs from A (navy, photos, arc gauges) and from B (black, neon, small capitals): light by default, no photos, no gauges, numbers as type. It is Lauscher's sibling (same font, tab bar, token names, tap size and version line) with its own ink-blue accent.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | #F5F2EC | #131517 | page |
| `--surface` | #FFFDF9 | #1C1F22 | cards, sheets |
| `--surface-2` | #ECE7DE | #26292D | tracks, steppers, rest phase |
| `--text` | #171C21 | #F2EEE6 | ink and every number |
| `--muted` | #56606A | #A2A9AF | "Last time", captions |
| `--line` | #DDD6CA | #33373B | hairlines |
| `--accent` | #1F4FBF | #8DB0FF | buttons, active tab, hold phase |
| `--good` | #00795A | #3DD1A0 | band: ready |
| `--fair` | #A86400 | #F5B23D | band: take it measured |
| `--low` | #B3261E | #FF6B5E | band: rest |
| `--warn` | #A3367A | #E58AC4 | the strain warning, nothing else |

Checked (WCAG): text 12.6-16.9:1; muted 5.2-7.7:1; accent 5.8:1 or more; score colours 3.8:1 or more on every surface (3:1 is the floor for large text and graphics). Band words sit on a filled pill: white text 4.7-6.5:1 in light, `--bg` text 6.6-9.9:1 in dark. The hues follow the colour-blind-safe Okabe-Ito set (bluish green, orange, vermilion, reddish purple), and every band also shows its word.

**Type**: Atkinson Hyperlegible Next with Lauscher's plain zero; `tabular-nums` on every number; `html { font: -apple-system-body }`, so 1 rem = 17 px at the default iPhone text size.

| Role | Size | Weight | Where |
|---|---|---|---|
| Timer | `min(7.5rem, 30vw)`, about 120-128 px | 700 | hold and rest digits (about 15 mm tall) |
| Big number | 4.25 rem, about 72 px | 700 | today's main score; reps × weight of the set |
| Number | 2.625 rem, about 44 px | 700 | tiles, next set, trend card |
| Title | 1.625 rem, about 28 px | 700 | screen title |
| Verdict | 1.375 rem, about 23 px | 600 | the one sentence |
| Body | 1 rem, 17 px | 400 | text, line height 1.45 |
| Label | 0.875 rem, about 15 px | 700 | tile labels, tabs |
| Caption | 0.8125 rem, about 14 px | 400 | the floor: nothing smaller |

**Shape and space.** Radius 16 px for cards and buttons, 12 px for rows and inputs, 999 px for pills, 0 for the full-screen timer. Spacing in 4 px steps (4, 8, 12, 16, 24, 32, 48); side margin 16 px; card padding 16 px; 12 px between cards. Taps: 52 px by default, 44 px at the least, 64 px for gym controls, and a 72 px "Done" in the bottom third.

**Motion.** Motion only shows a change of state: fades 160 ms, sheets 240 ms ease-out, the rest bar drains at a constant rate. Nothing loops on a screen at rest. Timer digits tick; they never slide, scale or pulse. A phase change fades the background in 200 ms and rings its bell. With Reduce Motion on: Lauscher's global rule (1 ms, no transitions), no confetti, no number rolls.

**The four screens in C**
- *Today*: the verdict sentence and the main score (72 px) with its band pill; Sleep and Strain as two tiles below (44 px). All three show without scroll. The check-in is the main button until it is done.
- *Set*: exercise name, "Set 2 of 3", the target at 72 px, "Last time" in muted text, 64 px steppers, a 72 px "Done". The next set waits below at 23 px.
- *Timer*: hold fills the screen with `--accent` and white digits (dark mode: `--bg` digits); rest uses `--surface-2`, ink digits and an accent bar. "Next: …" at 28-44 px. Pause, +15 s and Skip at 64 px.
- *Trend card*: label, a 44 px number with its unit, the change with its period, a 48 px line, "—" when not measured.

## 6. Rules every direction follows

- [ ] No "why" panel on the training screen: what to do, nothing more (Key Rule 20).
- [ ] A warning shows only when that exercise's body area is over the strain line. The engine decides; the phone only shows it.
- [ ] Machine units never show: the label reads "Weight".
- [ ] Large numbers; tap targets 44 pt or more (52 px by default, 64 px in the gym).
- [ ] One-hand use: session controls in the bottom third; nothing vital in the top corners.
- [ ] The screen stays on during a session (Wake Lock; ask again when the app comes back).
- [ ] Cues by sound and screen: Safari on iPhone has no vibration.
- [ ] Plain English; no Stage 1 text; all screen text in one strings file that the text scanners read.
- [ ] Light and dark mode, following the iPhone setting; `theme-color` for both.
- [ ] Reduce Motion respected (`prefers-reduced-motion`).
- [ ] Text scales with the iPhone text size (`font: -apple-system-body`, rem units); check at 200 %.
- [ ] Safe areas in standalone mode: `viewport-fit=cover`, `env(safe-area-inset-*)`, the page itself never scrolls; check on the iOS 26 phone.
- [ ] Contrast 4.5:1 for text up to 17 pt, 3:1 for larger text and graphics. Colour never alone: each band shows its word.
- [ ] "—" for anything not measured; the Sleep screen is all or nothing.
- [ ] Navigation stays inside the app, with no full page reload (Key Rule 17).
- [ ] The version line in Settings, in Lauscher's format.

## Sources

- Oura, the new app (2024-10-03): https://ouraring.com/blog/new-oura-app-experience/ · Instrument case study: https://www.instrument.com/work/oura-app
- WHOOP Home: https://www.whoop.com/us/en/thelocker/the-all-new-whoop-home-screen/ · review: https://the5krunner.com/2023/03/28/new-whoop-home-screen-looks-pretty-but-is-it-as-intuitive/ · bands: https://developer.whoop.com/docs/whoop-101
- Apple HIG, Activity rings, Workouts and Accessibility (44 pt, contrast, 200 % text, Reduce Motion): https://developer.apple.com/design/human-interface-guidelines/activity-rings · https://developer.apple.com/design/human-interface-guidelines/workouts · https://developer.apple.com/design/human-interface-guidelines/accessibility
- Apple Fitness trends (90 vs 365 days): https://www.macworld.com/article/233093/ios-13-and-apple-watch-activity-trends-give-you-the-big-picture.html
- Hevy: https://www.hevyapp.com/features/workout-rest-timer/ · https://www.hevyapp.com/features/live-activity/ · https://help.hevyapp.com/hc/en-us/articles/36011896355479 · Strong: https://www.strong.app/ · its timer as users describe it: https://ideas.abcfitness.com/forums/167887-coach-trainer-abc-trainerize/suggestions/45891910-change-the-regular-workout-functionality-to-have-a
- Workout tracker design lessons: https://screensdesign.com/articles/workout-tracker-app-design-examples/ · interval timer phase colours: https://apps.apple.com/app/id6762538816
- Letter height and distance: https://www.signs.com/blog/?p=16381
- Wake Lock in Home-Screen apps: https://progressier.com/pwa-capabilities/screen-wake-lock · Dynamic Type on the web: https://vispero.com/resources/text-resizing-web-pages-ios-using-dynamic-type/ · no vibration in WebKit: https://lists.w3.org/Archives/Public/public-device-apis-log/2024Jun/0061.html
