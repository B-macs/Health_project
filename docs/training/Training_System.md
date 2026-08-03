# Training System — Patient
*Last updated: 2026-08-03*

> **This file is explanatory, not authoritative.** Guardrail numbers live in
> `services/rules.py` (`STAGE_CONSTRAINTS`, `MOVEMENT_RULES`) and clinical
> findings live in `patient_profile.py`. Where this document disagrees with
> either, they win — see CLAUDE.md Key Rule 3.

---

## Patient Profile

**Name:** Patient
**Current Stage:** **Stage 2 — Transition.** Active block: Stage 2A, a 28-day
gym strength block started 2026-07-20 (`training_plan.PLAN_STAGE2`), Day 28
reassessment 2026-08-16. Stage 1 ran to 2026-07-19, extended 7 days after a
mid-back flare. Current state: `docs/focus.md`.

**MRI Findings (L-spine):**
- L5/S1: Activated osteochondrosis + Grade 1 retrolisthesis + right dorsolateral disc protrusion (moderate right foraminal stenosis)
- L4/L5: Retrolisthesis + left dorsolateral flat protrusion with covered annular tear
- L3/L4: Left dorsolateral flat protrusion with covered annular tear

**Biomechanical Assessment Findings:**
1. **Upper Glute / Hip Crest Tightness** — Overactive glute medius + piriformis in chronic contraction; primary driver of joint compression. Must be inhibited before any activation work.
2. **Standing Leg Hinge Crack (right)** — Femoral head against tight right posterior hip capsule, or upper hamstring tendon shifting over ischial tuberosity.
3. **Sitting Forward-Bend Releases** — Thoracic facet joints + horizontal lumbar facet slides at L5/S1 base under chronic compression.
4. **90° Hip Click, Right Side Only (Coxa Saltans)** — Iliopsoas tendon snapping over femoral head when right hip lifted to 90° with external rotation.
5. **Wide-Stance Windmill Cracks** — Hip joint capsule + pubic symphysis cavitation + facet joint rotation at end range.

**Imbalance Summary:**
- Primary tightness: glute medius/piriformis, deep right hip flexors/TFL, right posterior hip capsule, upper hamstring attachments at ischial tuberosity, horizontal lumbar base/SIJ
- Primary weakness: gluteus maximus (under-firing), deep core (under-firing)
- Compensation pattern: upper glutes + hip flexors gripping to create artificial stability → compressed joints and snapping tendons

---

## Stage Progression Overview

Mirrored from `services.rules.STAGE_CONSTRAINTS` — **that dict is the single
source of truth**; this table is a reading aid and was wrong on three values
until 2026-08-03 (Stage 2 RPE, and both Stage 3 ceilings).

| Stage | Name | Load Constraint | ACWR Ceiling | Session RPE Ceiling | Volume Cap | Max Sessions/wk |
|-------|------|----------------|--------------|---------------------|-----------|-----------------|
| 1 | Rehab — Tissue Tolerance | Bodyweight only | 1.2 | 7/10 | 70% | 4 |
| 2 | Transition — Work Capacity | +Resistance bands, DB, cable | 1.3 | 8/10 | 90% | 5 |
| 3 | Performance & Growth | Progressive barbell loading | 1.5 | 10/10 | 100% | 6 |

**Progression criteria from Stage 1 → 2** — SATISFIED 2026-07-19 at the Day 21
reassessment (Stage 1 was extended by a week; the criteria were evaluated then,
not at Day 14). Recorded in `patient_profile.PROFILE["stage_transitions"]`.
- Pain ≤2/10 throughout the assessment
- McGill Big 3 performed cleanly (pain-free, good form)
- Single-leg balance: 60s wall-free, eyes closed
- Hip hinge full range: arms past knee level, pain ≤2/10
- Walk 15 min + 2 stair flights at pain ≤2/10
- Physiotherapist sign-off

**Progression criteria from Stage 2 → next block:** see
`patient_profile.PROFILE["stage_2_exit_criteria"]`, evaluated 2026-08-16.

---

## Load Calculation Methodology

### Session AU (Arbitrary Units) — Foster Session-RPE Method

```
session_AU = session_RPE × duration_minutes
```

- Session RPE collected via morning check-in slider (0–10 Borg-CR10 scale)
- Duration automatically estimated from exercises in training session, including per-set rest periods (60s default) + 30s setup per exercise + 120s base overhead
- Foster method implicitly accounts for exercise type variation through RPE — harder efforts produce higher RPE ratings

### Cardiovascular Load Factor (CLF) — Stage Adjustment

The Foster method was calibrated for cardiovascular and sport performance training. Bodyweight rehabilitation exercises generate significantly less cardiovascular demand than equivalent sport RPE. The CLF scales raw AU to reflect actual physiological cost relative to the stage.

```
effective_AU = raw_AU × STAGE_CLF[stage]
```

| Stage | CLF | Rationale |
|-------|-----|-----------|
| 1 | 0.04 | Bodyweight rehab only — ~4% of cardiovascular load vs equivalent sport RPE |
| 2 | 0.40 | Mixed resistance + bands — moderate cardiovascular engagement |
| 3 | 1.00 | Performance training — Foster method applies at full scale |

**Calibration target (Stage 1):** A single physio-style bodyweight session should produce strain in the 6–10 range. Two sessions in a day: 10–11.

### Strain Score — Logarithmic 0–21 Scale

```
strain = min(21, ln(effective_AU + 1) / ln(601) × 21)
```

- Logarithmic scale mirrors the non-linear relationship between training load and physiological stress
- Max AU of 600 maps to strain of 21 (theoretical maximum)
- For Stage 1 with CLF 0.04, a session with RPE 5 × 60 minutes produces effective AU ~12 → strain ~5.5

**The RPE path above is now the fallback, not the primary.** Where a Garmin
activity matches a logged session, the *displayed* strain is heart-rate-derived
instead — Edwards' summated-HR-zone TRIMP, in `services/hr_load.py`, calibrated
to land on this same 0–21 scale so the two are continuous. `services/hr_matching.py`
decides which activity IS a logged session, by wall-clock overlap. Read
`hr_load.py`'s docstring for why Edwards' over Banister/Lucia/Stagno.

### ACWR — Acute:Chronic Workload Ratio

```
ACWR = 7-day_rolling_AU / 28-day_rolling_AU
```

- Acute load: sum of session AU over the past 7 days
- Chronic load: rolling 7-day average over the past 28 days (i.e., 28-day total ÷ 4)
- Safe training zone: 0.8–1.3 (**current Stage 2 ceiling: 1.3**; Stage 1 was 1.2, Stage 3 is 1.5 — all from `rules.STAGE_CONSTRAINTS`)
- Values >1.5 indicate high injury risk — training directive turns red

**⚠ ACWR stays on Foster AU — only STRAIN is heart-rate-derived.** `hr_load.py`
never feeds `engine.acwr`. ACWR is a ratio of rolling averages, so mixing
Edwards'-TRIMP days with RPE-fallback days inside one 7/28-day window would
compare different units and swing the ceiling on whether a Garmin activity
happened to get recorded — i.e. on watch-button behaviour rather than
physiology. Unifying them needs a per-athlete conversion regressed from
sessions carrying BOTH signals; do not attempt it until enough paired sessions
exist. This is CLAUDE.md Key Rule 2b.

### Exercise Type Weighting — BUILT

No longer "future". Per-exercise load weighting lives in
`training_constants.EXERCISE_MOVEMENT_WEIGHT`, with the fallback in
`services/content_weighting.py`. **79/79 logged exercise names are mapped.**

| Category | Multiplier | Exercises |
|---|---|---|
| `squat` | 1.3 | 2 |
| `hinge` | 1.0 | 2 |
| `pull` | 0.7 | 2 |
| `upper_push` | 0.7 | 1 |
| `bodyweight_compound` | 0.5 | 10 |
| `isolation` | 0.3 | 10 |
| `mobility_core` | 0.25 | 52 |
| *(unmapped fallback)* | 1.0 | — |

`bodyweight_compound` (0.5) was added for Stage 1's unloaded multi-joint work —
sit-to-stand, step-ups, lunges, wall sits, single-leg RDL. It sits between
`isolation` 0.3 and `pull`/`upper_push` 0.7 because scoring a bodyweight
sit-to-stand at `squat` 1.3 would be as wrong as the 1.0 default it replaced.
`tests/test_movement_weight_coverage.py` pins the ordering and the
one-category-one-weight invariant.

**Why full coverage matters, learned the hard way.** The map originally covered
only `PLAN_STAGE2`'s exercise universe, so **34 of the 63 names in the logged
history** hit the 1.0 fallback — every Supine Knee-to-Chest and Diaphragmatic
Breathing drill was counted as fully-loaded barbell work. Correcting it dropped
Strain on a pure-mobility day from ~4.9 to ~2.0 and *raised* ACWR 1.23 → 1.44,
because the old Stage 1 inflation had been padding the chronic denominator and
hiding how steep the Stage 2 ramp actually was. **Add every new block's
exercise names here**, or the same failure recurs silently.

---

## Readiness Score — MODEL_VERSION 2 (2026-08-01)

Scored from Oura's eight contributors plus our own Sleep Debt, with **our**
weights and **our** composite — this is not Oura's score taken directly.
Weights re-normalise automatically when individual metrics are missing.
Authoritative values: `services/readiness.py` `_WEIGHTS`.

| Component | Weight | Source | What it carries |
|---|---|---|---|
| HRV Balance | 21% | Oura | Primary autonomic recovery marker |
| Recovery Index | 17% | Oura | Oura's own overnight-recovery contributor |
| Previous Night | 16% | Oura | Last night's sleep, quality-aware |
| Resting Heart Rate | 13% | Oura | Supporting cardiovascular indicator |
| Body Temperature | 12% | Oura | Thermal load against personal norm |
| **Sleep Debt** | **9%** | **ours** | Trailing 7-night cumulative deficit |
| Previous Day Activity | 5% | Oura | Training-load spillover |
| Sleep Regularity | 4% | Oura | Circadian consistency |
| Activity Balance | 3% | Oura | Accumulated training load |

Returns `NOT_COMPUTED` when insufficient data exists.

### Why version 1 was replaced

v1 was `(HRV × 0.40) + (Sleep × 0.35) + (RHR × 0.25)`, with HRV and RHR derived
here as ratios against a 28-day personal mean — `min(100, today/baseline*100)`
and `min(100, baseline/today*100)`. Both were **one-sided and saturating**: any
day at or above baseline scored a flat 100, so they could only penalise, never
distinguish among good days. It read **84.8 on a day Oura read 57**. The cause
was not the imported contributors (those matched exactly) but those two
components, plus four synced Oura contributors that were being ignored entirely.

Measured over a year, v2 vs Oura: **r = 0.992**, mean bias −0.9, sd 2.8, 91%
within 5 points. v1 ran ~15 points high.

**Alcohol is no longer deducted.** It is self-reported and invisible to Oura, so
scoring it made the two series incomparable. `services/scheduling.py` still
shifts sessions on consecutive-day alcohol, independently of readiness.

### HRV / RHR Baselines — still exported, no longer scored

`hrv_baseline()` and `rhr_baseline()` remain exported and tested but **do not
feed `compute_readiness`** under v2 — both come from Oura's trend-aware,
unclipped contributors instead. They are kept deliberately: they are the
natural tool for measuring a device changeover, which is exactly what the
Garmin 265 will need.

- 14-day average until 28 days of data exist, then a permanent 28-day rolling average
- Minimum 14 observations before a baseline is considered reliable

### Sleep Baseline — Progressive Personal Baseline

Progressive window selects the longest available period among 7, 14, 28, 56 nights.

```
7 nights → 14 nights → 28 nights → 56 nights (maximum for now; may extend to 90)
```

**Outlier exclusion:** Nights < 4 hours or > 11 hours are excluded before averaging. These represent anomalous readings (travel, illness, device error) that would corrupt the personal baseline.

**Purpose:** Measures sleep relative to your own biological requirement, not a population average. A person who normally sleeps 6.5h scoring 7h is well-rested; a person who normally sleeps 8.5h scoring 7h is under-recovered.

Falls back to 8.0h default until 7 clean nights are logged.

---

## Injury Weight — Load Modifier

**BUILT** — `services/engine.py` `injury_weight(lambda_val, days_pain_free)`.
Exponential decay, not the linear sketch this section used to describe:

```
injury_weight = exp(-lambda × max(0, days_pain_free))
```

Weight starts at 1.0 (full influence) on a symptomatic day and decays toward 0
as pain-free days accumulate; `engine.injury_weight_signal(weight)` maps the
result to a display band. The per-stage RPE ceiling and CLF still apply on top —
they are ceilings, not substitutes for the modifier.

---

## Data Sources

| Data | Source | Refresh |
|------|--------|---------|
| Training sessions, readiness check-ins | Notion database (the write backend) | Real-time |
| HRV, RHR, sleep, steps | **Oura + Garmin, blended** — `services/biometrics.py`. HRV/RHR/sleep duration at Oura 70 / Garmin 30; steps at Garmin 80 / Oura 20. Google Sheets is the intermediary (one tab per platform), not the source | Daily sync, on app open, 2-hourly cadence |
| Stage config | Notion config table | Per session |

**Sheet1 / Apple Health is retired** from the live pipeline — historical only.
**HRV is currently held at Oura-only** on purpose (`biometrics.HRV_GARMIN_HOLD`):
the 645 reports no HRV, so the documented 70/30 has never actually run, and
flipping it on the day the hardware changes would step the series that readiness
baselines are built from. Lift it on a measurement, not a date — see CLAUDE.md.

Biometric data fetched over a 60-day rolling window to support the 56-night sleep baseline.

---

## Files

| File | Purpose |
|------|---------|
| [Stage_1_14_Day_Plan.md](Stage_1_14_Day_Plan.md) | Full day-by-day exercise prescription with mechanics, focus, and progression/regression cues |
| `training_plan.py` | Machine-readable plan data — `PLAN` (Stage 1) and `PLAN_STAGE2` (current block) |
| `training_constants.py` | `EXERCISES`, `EXERCISE_BODY_REGION`, `EXERCISE_MOVEMENT_WEIGHT` — keep all three current when a block adds exercise names |
| `services/engine.py` | AU, strain, ACWR, CLF, injury weight, traffic light, baseline drift |
| `services/rules.py` | `STAGE_CONSTRAINTS` + `MOVEMENT_RULES` — **the** guardrail source of truth |
| `services/readiness.py` | Readiness score (MODEL_VERSION 2) + baseline computation |
| `services/hr_load.py` | Edwards' TRIMP — heart-rate-derived strain |
| `services/biometrics.py` | Oura+Garmin blend — the engine's biometric read source |
| `app.py` | SPA router + home dashboard |
| `services/repository.py` | The only place Notion property / Sheet column names live |
| `repo.py` | Streamlit bootstrap — the only place `st.secrets` is read |

*The old root-level `db.py`, `sync_sheets.py`, `engine.py` and `readiness.py`
no longer exist; all backend and business logic moved under `services/`, which
must never import Streamlit (enforced by `tests/test_no_streamlit_in_services.py`).*
