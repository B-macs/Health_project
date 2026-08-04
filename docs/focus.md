# focus.md — Live Context Stub

*Update this file whenever the active stage or next action changes.*

---

## Current State (2026-08-03)

| Item | Value |
|------|-------|
| Stage | **Stage 2** — Transition (external load) |
| Block | **Stage 2A — 28-Day Gym Strength Block**, started 2026-07-20 (`training_plan.PLAN_STAGE2`) |
| Day | **Day 15 of 28** |
| Gate | **1290/1290** — `python -m pytest tests/` |
| Last commit | `79bb0cf` — corrected the interscapular record (endurance gap, not volume gap) |
| Next action | **Day 28 reassessment, 2026-08-16** — physiotherapist sign-off required |

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
5. Run `python -m pytest tests/` — 1290/1290 or higher.
6. Update this file: block, day, gate, next action.

---

## Open Questions

- [ ] Will `coxa saltans` (right snapping hip) resolve or persist under Stage 2
      loading? Tracked in `stage_2_exit_criteria`.
- [ ] Is the left interscapular load a compensation worth loading **on the
      left**, or a consequence of the documented **right** eccentric-control
      deficit? Determines which side gets programmed — see the physio brief.
- [ ] Anterior knee cues for right TFL offload — carried over from Stage 1,
      still unresolved.
- [ ] Lift `biometrics.HRV_GARMIN_HOLD`? The gate is a measurement, not a date:
      `Repository.hrv_blend_status()` reporting `ready` (≥14 paired nights)
      with an acceptable `mean_bias`/`sd_bias`. Blocked on a watch that reports
      HRV — the 645 does not.

*Resolved since Stage 1: Apple Health sync — Sheet1/Apple Health is retired
from the live pipeline; the engine's biometric source is the Oura+Garmin blend
in `services/biometrics.py`.*

---

*The table above is always current-state-only. If this file disagrees with
`patient_profile.py`, `patient_profile.py` wins.*
