# Training Screen — every message shown to the athlete

*Compiled 2026-08-20 by static extraction from `views/training.py` (147 unique
emitted strings) and `training_plan.py` (the five per-exercise text fields the
view renders). Purpose: decide what stays on screen. Mark each row KEEP / CUT /
MOVE in the right-hand column.*

> **STATUS 2026-08-20 — four decisions applied, gate 3555 green.**
> Categories **B (the why)** and the machine-unit rows in **D** are REMOVED
> from the screen. Category **C (safety warning)** is now GATED on regional
> strain > 16 rather than shown every set. Everything removed is still
> authored in `training_plan.py` — this was a display change throughout.
> Remaining categories are still open for you to mark.

**One number first.** A Stage 2B gym day (day 2, 14 exercises) puts **11,581
characters — about 2,300 words** of exercise prose on screen across the
session. Split: `mechanics` 4,688 · `biomechanical_focus` 4,161 ·
`regression` 1,051 · `progression` 989 · `warning` 692. Three of the 14
exercises carry a warning.

---

## The two channels

Messages reach the screen by two different routes, and they are edited in
different places:

| Channel | Source | Rendered at |
|---|---|---|
| **Exercise content** — the bulk of the words | `training_plan.py`, per exercise | `views/training.py:3727, 3732, 4205, 4216` |
| **Screen messages** — status, alerts, controls | `views/training.py` literals | throughout |

---

## A. Exercise instruction — how to do it

| Field | Where | What it is | Keep? |
|---|---|---|---|
| `name` | Always, heading | Exercise name | |
| `mechanics` | Always, main body ([training.py:3727](../views/training.py#L3727)) | The full how-to. **~937 words/session** — the single biggest block on screen | |
| `tempo`, `sets`, `reps`, `hold_seconds`, `rest_seconds` | Always, dose row | The prescription | |

## B. Exercise rationale — why you are doing it  ·  ❌ REMOVED FROM SCREEN

| Field | Where | What it is | Keep? |
|---|---|---|---|
| `biomechanical_focus` | ~~training.py:4205~~ | The reasoning, ~832 words/session | **CUT 2026-08-20** — field kept, panel gone |
| `progression` | ~~training.py:4216~~ | "▲ Progress if: …" | **CUT 2026-08-20** — field kept |
| `regression` | ~~training.py:4217~~ | "▼ Regress if: …" | **CUT 2026-08-20** — field kept |

## C. Safety stop

| Line | Text | Keep? |
|---|---|---|
| [3758](../views/training.py#L3758) | `st.error("⚠️ {warning}")` — **GATED 2026-08-20**: shows only when that exercise's own body area is over strain 16 (higher of today-so-far and yesterday). 13 exercises carry one; all 13 kept, all 13 region-mapped | **KEPT, gated** |

## D. Load and dose readouts

| Line | Text | Keep? |
|---|---|---|
| [3379](../views/training.py#L3379) | metric **Sets** | |
| [3380](../views/training.py#L3380) | metric **Weight** | |
| [3876](../views/training.py#L3876) | label **WEIGHT (KG)**, or plain **WEIGHT** when the stack is not in kg | **DONE 2026-08-20** — "MACHINE UNITS" removed |
| ~~3883~~ | "⚠ Unit-based — this machine's scale isn't calibrated to kg yet…" | **CUT 2026-08-20** — background fact |
| [3815](../views/training.py#L3815) | "Left side: {reps} — {weight}" | |
| [3818](../views/training.py#L3818) | expander **Edit left side** | |

## E. Engine directive and readiness adaptation

| Line | Text | Keep? |
|---|---|---|
| [1231](../views/training.py#L1231) | "⚠️ Prescription contradiction — {…}" | |
| [1232](../views/training.py#L1232) | "The engine flagged today as reduced load but produced a higher prescription. Falling back to your last completed session." | |
| [2086](../views/training.py#L2086) | "**No adaptation today** — your readiness supports the full prescribed volume." | |
| [2090](../views/training.py#L2090) | "**Volume held at 100%** of the standard prescription." | |
| [2092](../views/training.py#L2092) | "**Volume {up/down} to {n}%** of the standard prescription." | |
| [2095](../views/training.py#L2095) | "Reduced-load day: no weight, rep or band tier will be seeded above your last completed session, whatever your readiness…" | |
| [2100](../views/training.py#L2100) | "Based on your last 3 days of HRV, RHR and sleep, then held down by the engine directive where the two disagree." | |

## F. Scheduling — swaps, missed sessions, block boundaries

| Line | Text | Keep? |
|---|---|---|
| [1613](../views/training.py#L1613) | "Session moved — {…}" | |
| [1858](../views/training.py#L1858) / [1955](../views/training.py#L1955) | "Day {n} of {m} has no authored content on record / yet." | |
| [1860](../views/training.py#L1860) | "Day {n} of {m} — {name} (planned, not done)" | |
| [1884](../views/training.py#L1884) | "Finish or exit today's session before swapping days." | |
| [1891](../views/training.py#L1891) | "Couldn't check logged sessions just now — the swap option is hidden until the page reloads." | |
| [1896](../views/training.py#L1896) | "Swap with today isn't available: {reason}" | |
| [1918](../views/training.py#L1918) | "That swap was not saved: {…}. Every week is its own block, so a session can move within its week but not into the next." | |
| [1997](../views/training.py#L1997) | "To train anyway, open any other day in the strip above and swap it onto today." | |
| [2052](../views/training.py#L2052) | "**{phase} ended before its last days were reached.** Its schedule still lists {days} — after the block's final date of {date}" | |
| [2336](../views/training.py#L2336) | "There's a session in progress. Finish it or exit it first — an accessory session shares the same saved progress." | |
| [2954](../views/training.py#L2954) | "Carry-forward not saved: {…}." | |
| [2973](../views/training.py#L2973) | "Missed session — proposed reschedule (nothing is changed until you choose):" | |
| [3040](../views/training.py#L3040) | "Readiness shift not saved: {…}." | |
| [3055](../views/training.py#L3055) | "Readiness suggests moving today's session — {…}. Nothing is changed until you choose." | |
| [3087–3091](../views/training.py#L3087) | "Flexibility retest — {…}" / "…due — {…}" / "…due, but {…}" | |
| [3236](../views/training.py#L3236) | "Your plan starts in {n} day(s) on {date}. Come back then." | |

## G. Garmin and heart rate

| Line | Text | Keep? |
|---|---|---|
| [2203](../views/training.py#L2203) | checkbox "I've started a Garmin workout" + "Leave unticked to train without the watch — you'll just rate the session yourself at the end." | |
| [3415](../views/training.py#L3415) | "✅ Garmin workout found — **{name}**, {n} min. Heart rate will be matched to each exercise." | |
| [3421](../views/training.py#L3421) | "⏱️ **Stop your Garmin workout now**, then tap Re-check." | |
| [3428](../views/training.py#L3428) | "No Garmin workout was started for this session, so your rating below is the only intensity record." | |
| [3505](../views/training.py#L3505) | "⚠️ **Couldn't line this session up with your watch** — {…}. This normally means you trained in a different timezone…" | |
| [3550–3560](../views/training.py#L3550) | metrics **Measured RPE**, **Measured AU**, **Active time** (+ the Foster explainer on hover) | |
| [3565](../views/training.py#L3565) | "**{verdict}** You rated this {x}; heart rate says {y}. Neither replaces the other — yours measures how close to failure…" | |
| [3570](../views/training.py#L3570) | "Matched to *{activity}* · {n}/{m} exercises had heart-rate cover ({pct} of block time)." | |
| [3579](../views/training.py#L3579) | "Heart rate covers only {pct} of this session — the watch was probably paused or stopped early." | |
| [3584](../views/training.py#L3584) | "This is metabolic demand, measured. Your own session RPE is still what drives ACWR." | |
| [3596](../views/training.py#L3596) | "Logged at your rating of RPE {n}. Start a Garmin workout next session to get a measured figure alongside it." | |
| [3982](../views/training.py#L3982) | "🏃 Start **{name}** on your Garmin watch now. Tap Complete below when you're done." | |
| [4009](../views/training.py#L4009) / [4011](../views/training.py#L4011) | toast "Pulled {n} min from Garmin" / "No Garmin activity today lasting {a}-{b} min — logged with the planned duration." | |
| [2777–2830](../views/training.py#L2777) | Manual activity import: sync-busy, search failed, no activities, family mismatch, log confirmation | |

## H. Confirmation and completion

| Line | Text | Keep? |
|---|---|---|
| [2513](../views/training.py#L2513) | "Accessory session logged." | |
| [2673](../views/training.py#L2673) | toast "Logged {name} — nice work." | |
| [3127](../views/training.py#L3127) | "Plan starts {date}. Come back each day for your session." | |
| [3243](../views/training.py#L3243) | "**{n}-Day Stage 1 Rehab Complete.** Your objectives: tissue tolerance established, neural desensitisation, gluteal activation…" | |
| [3250](../views/training.py#L3250) | "**{n}-Day Stage 2A Gym Strength Block Complete.** Final working loads and the Day 28 functional screen are logged…" | |
| [3259](../views/training.py#L3259) | "**{n}-Day {name} Complete.**" | |
| [3211–3214](../views/training.py#L3211) | metrics **Plan Start**, **Today**, **Day {n}/{m}** | |

## I. Errors and system failures

| Line | Text | Keep? |
|---|---|---|
| [1934](../views/training.py#L1934) | "Couldn't save the swap — nothing was changed. Try again." | |
| [2540](../views/training.py#L2540) | "Couldn't save the session: {err}" | |
| [2826](../views/training.py#L2826) | "Couldn't log it — nothing was saved: {err}" | |
| [2864](../views/training.py#L2864) | "Couldn't read your training phases — the stored data looks corrupted or a read just failed. Not auto-resetting…" | |
| [3149](../views/training.py#L3149) | "Weekly rollup sync unavailable — showing live data only." | |
| [3151](../views/training.py#L3151) | "Garmin daily sync unavailable — will retry next visit." | |
| [1767](../views/training.py#L1767) | "No exercises in this section." | |
| [2697](../views/training.py#L2697) | "No yoga sessions have been added yet — check back soon." | |

## J. Controls, inputs and section headers

33 buttons, 9 expanders, 6 note boxes, 5 sliders, 2 radios, 1 selectbox.
Notable text-carrying ones:

| Line | Text | Keep? |
|---|---|---|
| [2172](../views/training.py#L2172) / [2175](../views/training.py#L2175) | expanders "Release Protocol · {…}" and "Workout · {…}" | |
| [2556](../views/training.py#L2556) | expander "Why this session" (accessory) | |
| [3362](../views/training.py#L3362) | selectbox "Review an exercise" | |
| [3434](../views/training.py#L3434) | slider "1 = very easy · 10 = maximal effort" | |
| [3437](../views/training.py#L3437) | "Session duration: **{n} min** (auto-timed) · Estimated AU: **{n}** (RPE × duration)" | |
| [3441](../views/training.py#L3441) | placeholder "e.g. Hip flexors felt looser. Slight tightness on last bird-dog set." | |
| [3602](../views/training.py#L3602) | expander "Preview: Day {n} — {name}" | |
| [3669](../views/training.py#L3669) | expander "Today's Exercises" | |
| [3746](../views/training.py#L3746) | expander "📝 Add a note for this exercise" | |
| [3747](../views/training.py#L3747) | placeholder "e.g. right hip felt tight on the last set, form cue worked well…" | |
| [4223](../views/training.py#L4223) | expander "Skip this exercise" | |
| [4224](../views/training.py#L4224) | "Only skip if pain prevents performance. Log the reason in session notes." | |
| [2522](../views/training.py#L2522) | slider "Session RPE — how hard did it feel?" + "This one should be low. If it is climbing past about 4 it has stopped being an accessory session." | |
| [2551](../views/training.py#L2551) | "{n} items · about {m} min (reads low — per-side work is counted once)" | |
| [2811](../views/training.py#L2811) | slider "How hard was it? (session RPE)" + the Foster explainer | |

---

## Reference

Regenerate with the extractor in the session scratchpad, or re-run the same
`ast` walk over `views/training.py` for every `st.*` output call.
