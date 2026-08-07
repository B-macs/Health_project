# focus.md — Live Context Stub

*Update this file whenever the active stage or next action changes.*

---

## Current State (2026-08-06)

| Item | Value |
|------|-------|
| Stage | **Stage 2** — Transition (external load) |
| Block | **Stage 2A — 28-Day Gym Strength Block**, started 2026-07-20 (`training_plan.PLAN_STAGE2`) |
| Day | **Day 18 of 28** |
| Gate | **1647/1647** — `python -m pytest tests/` |
| Last code commit | The flexibility ladder — the battery's decision path as rungs, tightest at the bottom, no scores and no numbers for unmeasured muscles |
| Next action | **Day 28 reassessment, 2026-08-16** — physiotherapist sign-off required; run the battery cold BEFORE it |

Stage 1 ran to 2026-07-19, extended by 7 days (Days 15–21) after a mid-back
flare meant the Day 14 exit criteria were not met on the original schedule.
The Day 21 reassessment passed and the physio cleared external load — recorded
in `patient_profile.PROFILE["stage_transitions"]`.

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
3. **Endurance-biased scapular programming** — the interscapular symptom
   persists through a five-day-a-week scapular dose, so the gap is endurance
   under sustained low-load holding, not volume. Long isometric holds are a
   prescription change, hence a physio decision. Brief prepared:
   `docs/training/physio_brief_2026-08-16.md`.

A **fourth workstream** lands the same day, and it is ours rather than the
physiotherapist's: the flexibility cluster session joins the new block as
designed-in training. The full protocol — slot reservation against the
five-per-week ceiling, placement re-derived against the NEW week (running
counts as leg loading), one-new-stressor-at-a-time staggering, the load
accounting that keeps Strain honest, and the pre-written pull-back condition —
is `docs/training/flexibility_integration_2026-08-16.md`. The only place it
meets the physio's decisions is shared weekly capacity.

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
5. Run `python -m pytest tests/` — 1602/1602 or higher.
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
