# focus.md — Live Context Stub

*Update this file whenever the active stage or next action changes.*

---

## Current State (2026-08-14)

| Item | Value |
|------|-------|
| Stage | **Stage 2** — Transition (external load). Unchanged: Stage 2B is a new BLOCK at the same clinical stage |
| Block | **Stage 2B — 28-Day Block**, starts **2026-08-17** (`training_plan.PLAN_STAGE2B`, Phase 3) |
| Day | Block A day 0 — starts Monday |
| Gate | **2920/2920** — `python -m pytest tests/` |
| Last code commit | Per-exercise RPE now comes from heart rate, not from the session slider |
| Next action | **Sun 16 Aug: Stage 2A's last day (day 26). Run the day-28 screen YOURSELF — the app will not offer it** |

### The two blocks, and why the dates are what they are

| | Runs | Ends |
|---|---|---|
| **Block A** | 2026-08-17 (Mon) → 2026-09-13 (Sun) | reassess, and author Block B from its real data |
| **Block B** | 2026-09-14 (Mon) → 2026-10-11 (Sun) | **race day is Block B's own day 28** |

Starting on the Monday is what makes this work. Both blocks land Mon–Sun, which
`services/plan.py`'s multiple-of-7 invariant and every spacing rule assume; the
Ireland trip falls on days **3–14**, so gym work resumes exactly at the top of
week 3 with nothing stranded mid-week; and the 10 km lands as day 28 of Block B
rather than somewhere inside it.

### Next actions, in order — the athlete's, not the code's

1. **Sun 16 Aug — Stage 2A's final day.** The app shows **day 26** (Unilateral/Glute
   + Scapular + Core), which is the last authored day it can reach.
   **⚠ The day-28 reassessment is not in the app's reach and never was.** Stage 2A
   absorbed two days of reschedules, so its own overrides put day 28 on 2026-08-18
   while the block's calendar ended 2026-08-16. The two stranded entries were
   removed on 2026-08-14 so the block finishes cleanly on the Sunday; the athlete
   runs the screen by hand. It is short — McGill Big 3, single-leg balance eyes
   closed, hip hinge full range, 5-minute walk + stairs — and two of the six exit
   criteria (final working loads, functional screen) come from it.
2. **Battery baseline mornings: 16, 19 and 20 Aug.** Cold, first thing, before
   anything else that day. The cluster stack cannot be authored without a
   pattern — `prescribe(None)` raises by design — and the battery has still
   never been run. **Verify each morning with `flexibility.leg_loading_days`
   against the real log rather than by eye**: Saturday's walk may classify as a
   leg day and block the 16th. Capture the straddle width and heel distance at
   the same sitting — the number is the record.
3. **Fri 21 Aug** — the anterior-hip pressure protocol starts, the day AFTER the
   battery baseline and not before. Contaminating the tilt measurement is the
   pre-declared failure mode.
4. **~24 Aug** — two-week verdict on the pec/scar protocol, in the standardised
   prayer position.
5. **This week** — raise the desk to standing elbow height measured ON the
   treadmill deck, and raise the monitor by the same amount. Dominant driver of
   the trapezius symptom; costs nothing.
6. **Before ~Sept** — the InBody bridge scan. Unrecoverable once the gym swaps
   machines.

### Held deliberately

- **ACWR stays advisory through Block A** (athlete, 2026-08-14). A new phase
  resets the stage-scoped chronic window, so from 2026-08-30 that window is
  **12 of 14 travel days**; a breach during the ramp back would be an artefact
  of the trip, not of training. Evaluate at Block B against normal loading.
- **The auto-progression machine is deferred.** Block A keeps the weekly load
  ladders one more block; `docs/training/auto_progression_design.md` is
  unchanged and still design-only.
- **`rest_taken_seconds` feeds nothing** (`sessions.REST_TAKEN_FEEDS_DURATION`).
  Recorded from day one, wired in on a measurement rather than a date.

Stage 1 ran to 2026-07-19, extended by 7 days (Days 15–21) after a mid-back
flare meant the Day 14 exit criteria were not met on the original schedule.
The Day 21 reassessment passed and the physio cleared external load — recorded
in `patient_profile.PROFILE["stage_transitions"]`.

---

## ⏱ REVISIT ON 2026-08-16 — measured RPE vs self-reported

**Added 2026-08-07. This is a software decision the athlete controls, not a
physiotherapist question — it is listed here because 08-16 is the review date,
not because it needs sign-off.**

Every session now produces **two** intensity figures:

| | Source | Feeds |
|---|---|---|
| **Self-reported RPE** | the slider, always asked | `session_au`, and therefore **Strain and ACWR** |
| **Measured RPE** | Garmin HR, %HRR, active-time weighted | stored beside it, feeds **nothing** |

They are deliberately *not* unified. `CLAUDE.md` key rule 2b keeps load on one
unit because a figure that changes depending on whether the watch happened to
be running would swing the ACWR ceiling on **button behaviour rather than
physiology** — the same hazard as `HRV_GARMIN_HOLD` and the sleep-blend row.
Rule 2b names the exit condition precisely: *a per-athlete conversion regressed
from sessions that have BOTH signals.*

**That is what is now accumulating.** The self-reported rating is collected on
every session, Garmin or not, specifically so the pair exists — a rating taken
only when the watch was off could never be compared against a measurement.

**What to look at on 2026-08-16:**

1. **How many paired sessions exist.** One is not a regression. First data
   point, 2026-08-06: measured **5.2** against self-reported **5** — 333 AU
   vs 320. Encouragingly close, and *only* one point.
2. **Bias and spread** of (measured − reported), the same way the HRV hold is
   judged: a consistent offset can be corrected, a wide spread means no single
   conversion works and the hold should stand.
3. **Whether the athlete's rating is systematically off in one direction**,
   which is interesting in its own right regardless of the switch.

**Do not flip anything on a date.** Flip it on the measurement, exactly as
`HRV_GARMIN_HOLD` requires. If the spread is wide, the correct outcome is to
keep both and say so.

Also worth checking that day: **coverage**. If sessions routinely come back
under ~85% covered, the watch is being started late or stopped early, and the
fix is the prompt — not the model.

---

## Three Decisions Due at Day 28 (2026-08-16)

All three are **explicit deferred decisions**, not oversights. Settle each with
the physiotherapist *before* authoring the next block. Full context in
`patient_profile.py`'s module docstring.

1. **Stage 2B vs. extending Stage 2A** — evaluated against
   `PROFILE["stage_2_exit_criteria"]`.
2. **Running introduction** — deliberately not in Stage 2A. The 10 km race
   periodization (2026-10-11) assumed a 2026-07-12 Stage 2A start; the real
   start was ~9 days later, so the timeline needs re-deriving rather than
   re-using. Note `historical_injuries_low_weight`'s carve-out: the left
   Sartorius strain recurred once, so running volume progresses conservatively.
3. **Endurance-biased scapular programming** — the symptom persists through the
   scapular dose that is actually being run, so the gap is not volume. Long
   isometric holds are a prescription change, hence a physio decision. Brief
   prepared: `docs/training/physio_brief_2026-08-16.md`.
   **⚠ Two corrections, 2026-08-13, both already in CLAUDE.md** — do not
   re-derive the originals. (a) *"a five-day-a-week scapular dose"* is **false**:
   the log says **4, then 3, then 2, then 2**. That figure came from
   `training_plan.py` rather than `training_exercises`; verify a dose against
   the log, and rebuild the datastore snapshot first. The conclusion survives —
   Wall Slide ran 2026-08-11, Face Pull 2026-08-12, and **2026-08-12 is the
   worst day on record** — only the arithmetic was inflated. (b) The mechanism
   is **perfusion, not endurance capacity**: the tissue is named as left
   trapezius, position-loaded, where sustained low-level contraction occludes
   flow. That reframes the ask — see `physio_brief_2026-08-16.md` **§10b**, added
   2026-08-13, where the primary tendon literature says **four 3-second efforts
   beat one 12-second hold at matched loading time** and intensity rather than
   duration is the variable.

A **fourth workstream** lands the same day, and it is ours rather than the
physiotherapist's: the flexibility cluster session joins the new block as
designed-in training. The full protocol — slot reservation against the
five-per-week ceiling, placement re-derived against the NEW week (running
counts as leg loading), one-new-stressor-at-a-time staggering, the load
accounting that keeps Strain honest, and the pre-written pull-back condition —
is `docs/training/flexibility_integration_2026-08-16.md`. The only place it
meets the physio's decisions is shared weekly capacity.

A **fifth workstream** is also ours: **the warm-up, which does not exist yet.**
`docs/training/warmup_evidence_review_2026-08-10.md` is REQUIRED READING before
the block is authored (see "What Happens at the Next Block Entry" step 1b). The
next block is the first to run near-maximal loads, and today a gym day runs
16–22 minutes of release work — labelled as 5 — and then goes straight into the
first working set with no raise and no ramp. The review is evidence-graded
throughout and settles the two questions that prompted it: at near-max loads a
general warm-up under ~5 minutes is measurably no better than none, while at
~10RM loads a specific warm-up is worth approximately nothing. **One item needs
deciding WITH the physiotherapist on the day** — whether any of the release
block's 16–22 minutes is re-allocatable, since the Right Posterior Hip Capsule
Stretch (2 × 60 s) is the single item sitting at the stretch dose where the
force deficit turns large.

**The protocol is authored in this shape, and the review says so in three
places:**

```
TODAY:    [ quiet things down ] → [ load ]

REQUIRED: [ quiet things down ] → [ wake things back up ] → [ load ]
```

Phase 1 is the existing release block — it exists, it costs 16–22 minutes, and
nothing in it needs deleting. **Phase 2 does not exist at all, and it is the
entire deliverable:** its job is to undo phase 1's acute cost (stretching leaves
tissue slack; a subsequent active warm-up buys it back) and to get glute max
contracting before the bar asks it to. Use these three names in patient-facing
text.

**🔒 LOCKED 2026-08-10, athlete's direction (review §3.0): phase 2 is MANDATORY
and is the fixed point of the block build** — specified first from the evidence,
with everything else adjusting around it, including the release block's
duration. Two consequences. First, **do not price phase 2 at 15 minutes**: it
has two jobs, and the mandatory one (undo phase 1's cost) is supported by
evidence about its *presence* with **no duration specified**, while the 15-min
figure answers a different, optional question that only pays near 1RM. Second,
this **forces the release-block dose question** — it is no longer optional and
must be answered with the physiotherapist, with three specific items to take in
(review §4.2). Nothing in the release block is cut by this repo; the answer is
theirs.

**🔒 LOCKED 2026-08-10, athlete's direction (review §3.0-b): TOTAL preparation
time is 10–15 minutes** — phases 1 and 2 together, first movement to first
working rep, with 15 as a ceiling rather than a target. Today's ~30 min sits
against a **~30 min working portion**, so preparation is half the session; the
athlete's words were *"otherwise the entire time is just warming up"*, and at
50% that is literally accurate. **The budget RESTORES the prescription rather
than cutting it:** `patient_profile.py:439` says *"5-minute release block before
every session"* and the coded doses drifted to 16–22 min. Indicative split —
phase 1 ≈ 5 min (the profile's own figure), phase 2 ≈ 5–10 min. The ceiling is
the athlete's; the split inside it is the physiotherapist's.

**⚠ Corrected 2026-08-13 — the "~30 min working portion" above is short.**
`services/sessions.py`'s `estimate_duration` **never reads `laterality`**, so
every gym session's estimate omits the second side of every unilateral exercise
— **5.5–6.9 minutes each**. The real working portion is **~41–47 min**, not ~30.
This makes the 10–15 min lock **better** supported, not worse: preparation moves
from 25–33% of the session to 18–27%. **The ceiling is unchanged and is not
re-opened.** Recorded so the next person to do this arithmetic does not
"discover" a discrepancy and re-litigate a settled decision. Detail in
`docs/training/rest_interval_evidence_review_2026-08-13.md` §0.2 and §3.5.

A **sixth workstream**, also ours: **rest intervals, reviewed 2026-08-13.**
`docs/training/rest_interval_evidence_review_2026-08-13.md` is REQUIRED READING
before the block is authored, in Key Rule 11's gate beside the warm-up review
and on the same EVENT-not-date basis. It answers a question the athlete asked
three days before Day 28 — should rest go to 3–5 min, and should the right and
left sides of a unilateral exercise be separated — and **the premise turned out
to be the finding**: there is no rest timer on the right→left transition, so the
other side's working time IS the first side's rest, and actual per-side rest is
**75–105 s rather than the coded 45–60**. Both proposals are refused on evidence
and priced (**+9/+9/+11 min** for the split, against a pooled non-local-fatigue
effect of **SMD −0.02**; **+23.5 min** for 3–5 min, against an ACSM 2026
umbrella review that issues no rest prescription at all). **One change is
supported: 90 s → 120–180 s on Goblet Squat and RDL, Stage 2B only, once the
loads are genuinely near-maximal** — it costs 1–3 min and does not apply at the
current 12.5 kg. **It is blocked on a per-set rest field that does not exist**,
for the same reason the ramp sets are blocked on the warm-up flag: `session_au`
comes from RPE, short rest inflates RPE without changing work, and the two are
indistinguishable in the data. **Both fields land in one migration.** The review
also raises a Day 28 question for the physiotherapist about the isometric hold
*structure* — see `physio_brief_2026-08-16.md` §10b — and it competes for the
same clock as phase 2, so sequence phase 2 first.

---

## Stage 2 Exit Criteria (`PROFILE["stage_2_exit_criteria"]`)

- Pain ≤ 2/10 across all working lifts, no worsening trend through the block
- No increase in Coxa Saltans frequency under loaded squat/split-squat work
- No instability sensation or left-tilt compensation under incline pressing
- Final working loads logged on all six primary lifts, as the new baseline
- Functional screen (McGill Big 3, Single-Leg Balance, Hip Hinge Full Range,
  Walk+Stair) matching or beating the Day 21 Stage 1 screen
- Physiotherapist sign-off — manual, external, not automated

Guardrails for the stage itself live in `services/rules.py`
`STAGE_CONSTRAINTS[2]` (ACWR ceiling 1.3), which `services/engine.py` derives
from. Never duplicate those values.

**ACWR enforcement is currently HELD** — `engine.ACWR_ADVISORY_MODE = True`, so
the ratio is reported and can exceed the ceiling without capping volume. The
ceiling above is the value that *will* bind when the hold lifts, not what is
binding today. `engine.ACWR_MIN_IN_STAGE_DAYS` (14) also gates the ratio as
non-diagnostic until a stage has that many days behind it.

---

## What Happens at the Next Block Entry

1. Read every local clinical profile document and **state how each influenced
   the plan** — `patient_profile.py` plus every `Input_files/*.md`. This is
   CLAUDE.md Key Rule 11, and it is checkable, not a formality.
1b. **Read `docs/training/warmup_evidence_review_2026-08-10.md` in full**, and
   state how it influenced the plan the same way. Same gate, same standard.
   **Gated on this event, not on a date** — the plan is NOT being rebuilt on
   2026-08-16 (athlete, 2026-08-10), so the document waits for the block build
   rather than expiring with the reassessment. The next block is the first to
   run loads close to maximum, and the system contains **no warm-up at all**
   today — a gym day goes from the last release hold straight into the first
   working set. Two hard prerequisites live in that document: ramp sets
   **corrupt tonnage, Strain and e1RM** unless a per-set warm-up flag lands
   first (`services/tonnage.py`'s eligibility is `if reps and weight`), and a
   warm-up change touches every session, so it collides with the
   one-new-stressor-per-week rule.
2. Update `patient_profile.py` with post-assessment findings, then append a
   `stage_transitions` record — that list is the evidence a transition's
   criteria were actually met, not merely stated.
3. Build the block in `training_plan.py`.
4. Add any new exercise names to **both** `training_constants.EXERCISE_BODY_REGION`
   (or `services/strength.py` and `services/tonnage.py` silently drop them
   from every region — `weekly_tonnage` returns the unmapped names) **and**
   `training_constants.EXERCISE_MOVEMENT_WEIGHT` (or they fall back to
   `UNMAPPED_EXERCISE_WEIGHT` 1.0 and inflate Strain/ACWR — this already
   happened once, across 34 of 63 Stage 1 exercise names).
5. Run `python -m pytest tests/` — 2437/2437 or higher.
6. Update this file: block, day, gate, next action.

---

## Standing Goal: Flexibility — Cluster A, built and unmeasured

**Status: zero assessments run.** The battery is built, its early exit is
verified end to end, and nothing has been measured against the athlete's body.
Locked decisions in `docs/resume.md` § FLEXIBILITY; the model itself in
`cluster_a_mechanics.py`, `services/battery.py`, `cluster_a_battery.py` and
`cluster_a_prescription.py`.

This is a **standing goal with no deadline**, explicitly ranked *below* the
10 km on 2026-10-11 (athlete, 2026-08-05).

### Run it before 2026-08-16

It is **measurement, not prescription**, so it does not conflict with the
standing "no self-directed exercise changes" instruction — and running it first
means walking into the Day 28 reassessment with a pattern label and real numbers
instead of a plan to get some. Roughly 20 minutes, not 40: it usually stops
early.

1. **COLD. No warm-up, ever.** A warm reading measures a viscoelastic effect
   that is gone within hours. The flow gates on this and it is the single
   easiest thing to get wrong.
2. **Capture the frozen constants at the same session.** Straddle width and the
   tailor's heel distance are now asked for in the flow itself, beside the
   reading they belong to — type them, don't chalk them. The traced side-split
   stance and the floor reference still have no field and remain setup
   discipline. **The number is the record**: a chalk mark is gone by next month
   and one re-placed by eye silently invalidates every reading taken against
   it. Note `block_height_cm` is deliberately *not* frozen — lowering it is the
   progress.
3. **Expect it to stop early.** Four slots run in order and it stops at the
   first failure, because a reading taken below a failing slot cannot be
   interpreted. Continuing is offered; it is not the default. The turned-out
   attempt of Gate 0 skips itself entirely while the neutral reading sits more
   than 15 cm off the floor — bone only engages in the last few centimetres of
   a full split (his call, 2026-08-07).
4. **Each step prints its own setup, LOCK and measurement.** A lost lock makes
   the number *better*, not worse, so nothing warns you — which is why every
   lock names a tell you can see from outside.
5. **Assisted work always comes after unassisted.** Within the spectrum slot the
   order is active → isometric → passive, and the tilt runs own-power before
   helped — neither is the order the source writes them in. Passive or helped
   work leaves everything looser and would flatter what follows it.
6. **The tilt is an angle, not a distance** (2026-08-07): phone flat on the
   lower back, degrees between sitting tall and the deepest tip. A rounding
   spine cannot fake it, which is why it replaced forehead height and the
   flat-back guard number in one move. Bring the phone to the mat.

**Expected outcome, recorded in the code before measuring:** Pattern **F**, tilt
range. That is what the 2026-08-05 straddle report predicts, and it *disagrees*
with the generic hypermobility prediction of H or I — he has a specific range
deficit inside an otherwise lax body. Worth watching rather than resolving in
advance.

**A pattern from one morning is a hypothesis.** Three baseline mornings set the
noise floor; until then no single reading is a reason to change anything, and
the screen says so.

### What to bring to the physiotherapist

- The pattern label and the readings behind it.
- The **collision table** in `docs/training/physio_brief_2026-08-16.md` — 14
  movements in the source material are contraindicated as written, and the
  substitutions made for each.
- **Every threshold is provisional.** They come from the source document, not
  from this athlete's spread.
- The **anterior-hip question** from 2026-08-05, which gate 0 can provoke and
  must not adjudicate.
- Whether **horse stance and Cossack** can come off deferral. They are held only
  because an open Stage 2 exit criterion is judged at that appointment.

---

## Time-Limited: the InBody bridge scan

**The gym is replacing its InBody 770 (~Sept 2026). One visit, and it expires
when the old machine leaves the floor.**

Under the never-pool-two-devices rule, a reading on the new machine cannot be
compared with the five corrected 2025 scans unless both machines measure the
same body on the same morning. Miss it and that history is permanently
orphaned and the lean-mass clock restarts at zero — the same lesson the
Garmin 645 → 265 movement-calibration refit records in CLAUDE.md.

One morning, fasted, before training:

1. Confirm **182.0 cm** is entered — check it before the operator starts. Four
   of the five 2025 scans were run against a wrong height, at −0.89 pp of body
   fat per centimetre.
2. Scan on the **old 770**.
3. Scan on the **old 770 again**, ~8 minutes later. This is the only estimate
   you will ever get of that machine's own test-retest spread, and it is the
   input to every later threshold. The existing 8-minute pair is confounded by
   the height re-type and cannot serve.
4. Scan on the **new machine**.
5. Take a **tape baseline** — waist and hip. Compare against the InBody's
   estimated 82.8 cm / 0.84.
6. Keep the **print-out**, not the app summary: the app drops the raw impedance
   table, the scan history, the waist and the fitness score.

Record the model and serial with every row. Add the new scans to
`body_composition_baselines.py`.

---

## Open Questions

- [ ] Will `coxa saltans` (right snapping hip) resolve or persist under Stage 2
      loading? Tracked in `stage_2_exit_criteria`.
- [ ] Is the left interscapular load a compensation worth loading **on the
      left**, or a consequence of the documented **right** eccentric-control
      deficit? Determines which side gets programmed — see the physio brief.
- [ ] Specialization / high-frequency cycle (the daily-training experiment) —
      **deferred past the Day 28 reassessment by athlete decision 2026-08-05**,
      to after the 10 km on **2026-10-11**. Running introduction and the Stage
      2B decision already land on 2026-08-16; a fourth simultaneous change
      makes attribution impossible when something flares. First trial is
      **arms only, 1–3 months** — the lowest-consequence target available (0
      direct sets/week today, no spinal or scapular loading), so a failed
      trial costs nothing. Expand elsewhere only if it runs clean. The
      blocking risk is connective tissue, not muscle: the cited 2024 daily-bench
      study injured >half of trained lifters, and hypermobility + post-Latarjet
      shoulder + three lumbar protrusions is exactly that failure mode. Boundary
      question is on the physio brief as §9.
      **First question in October is whether this is still relevant at all** —
      re-derive it against the state of the record then, don't resume it by
      default. Specifically: did the Day 28 and post-race reassessments change
      the picture, is `services/strength.py` out of calibration (it cannot
      evaluate a trial while every index reads 50), did the running block
      surface a tendon issue, and is arms still the lagging region it is
      today (0 direct sets/week). Any of those can retire the question rather
      than answer it.
      **Sequencing, added 2026-08-05:** if connective tissue is what blocks the
      trial, and tendon capacity is buildable, then the order is *build tendon
      capacity first, trial second* — not "wait until October, then start". So
      the October question is two questions: is it still relevant, and has
      anything been done in the meantime that changes the risk. Decide the
      prep in **September**, not on the day. Tendon capacity comes mainly from
      heavy slow resistance and loaded lengthened positions — largely the block
      already running, executed with deliberate eccentric tempo — with
      isometrics as the early-rehab/analgesia tool rather than the whole
      picture. Physio brief §10 carries the detail and the two questions put to
      the physiotherapist.
- [ ] **Is the overhead restriction a lat, a pec, or the capsule?** The new
      `lats` rung exists to answer exactly this and nothing else does — three
      tissues stop an overhead reach and only the lat crosses the lumbar spine,
      so pelvic tilt isolates it. `shoulders_overhead` low **and** `lats` low ⇒
      the lat limits. `shoulders_overhead` low **with** `lats` fine ⇒ pec or
      capsule. This matters more than the score: post-Latarjet, a capsular
      restriction makes aggressive stretching the wrong answer for an
      anterior-instability shoulder, not merely an ineffective one. Unanswerable
      until the first assessment runs.
- [ ] Anterior knee cues for right TFL offload — carried over from Stage 1,
      still unresolved.
- [ ] Lift `biometrics.HRV_GARMIN_HOLD`? The gate is a measurement, not a date:
      `Repository.hrv_blend_status()` reporting `ready` (≥14 paired nights)
      with an acceptable `mean_bias`/`sd_bias`. Blocked on a watch that reports
      HRV — the 645 does not.
- [ ] Does the Foryond use height in its body-fat model at all? The setting was
      corrected 183 → 182 cm on 2026-08-05 and the export did **not**
      back-apply, so the next weigh-in is the test: BMI must step **+0.27**; if
      body fat also steps about **+0.9 pp**, height is in its model too. Either
      way that step is a setting, never fat gain.

*Resolved since Stage 1: Apple Health sync — Sheet1/Apple Health is retired
from the live pipeline; the engine's biometric source is the Oura+Garmin blend
in `services/biometrics.py`.*

---

*The table above is always current-state-only. If this file disagrees with
`patient_profile.py`, `patient_profile.py` wins.*
