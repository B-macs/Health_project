# Training System — Patient
*Last updated: 2026-06-30*

---

## Patient Profile

**Name:** Patient  
**Current Stage:** Stage 1 — Rehabilitation

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

| Stage | Name | Load Constraint | ACWR Ceiling | Session RPE Ceiling |
|-------|------|----------------|--------------|---------------------|
| 1 | Rehabilitation | Bodyweight only | 1.2 | 7/10 |
| 2 | Transition | +Resistance bands, light DB | 1.3 | 7.5/10 |
| 3 | Performance | Progressive barbell loading | 1.4 | 8.5/10 |

**Progression criteria from Stage 1 → 2:**
- Pain ≤2/10 throughout Day 14 assessment
- McGill Big 3 performed cleanly (pain-free, good form)
- Single-leg balance: 60s wall-free, eyes closed
- Hip hinge full range: arms past knee level, pain ≤2/10
- Walk 15 min + 2 stair flights at pain ≤2/10
- Physiotherapist sign-off

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

### ACWR — Acute:Chronic Workload Ratio

```
ACWR = 7-day_rolling_AU / 28-day_rolling_AU
```

- Acute load: sum of session AU over the past 7 days
- Chronic load: rolling 7-day average over the past 28 days (i.e., 28-day total ÷ 4)
- Safe training zone: 0.8–1.3 (Stage 1 ceiling: 1.2)
- Values >1.5 indicate high injury risk — training directive turns red

### Exercise Type Weighting — Current vs Future

**Current (Stage 1):** Session RPE captures exercise difficulty implicitly. All Stage 1 exercises are bodyweight; within-session variation (ankle exercises vs full-body holds) is small enough that session-level RPE is sufficient. CLF 0.04 handles the overall scale correction.

**Future (Stage 2+):** When barbell exercises are introduced, per-exercise load weighting will be needed because the RPE difference between 3 ankle exercises and 3 deadlifts is enormous and session RPE cannot represent both accurately. Planned formula:

```
exercise_AU = sets × reps × weight_kg × movement_multiplier
movement_multiplier: deadlift=1.5, squat=1.3, hinge=1.0, upper_push=0.7, isolation=0.3
```

---

## Readiness Score

**Formula:**

```
readiness = (HRV_score × 0.40) + (Sleep_score × 0.35) + (RHR_score × 0.25)
```

Weights re-normalise automatically when individual metrics are missing.

**Component scores (each 0–100):**

| Metric | Score formula | Direction |
|--------|--------------|-----------|
| HRV | `(today_HRV / baseline_HRV) × 100` | Higher = better |
| Sleep | `(tonight_hours / baseline_hours) × 100` | Higher = better |
| RHR | `(baseline_RHR / today_RHR) × 100` | Lower today = better |

Returns `NOT_COMPUTED` when insufficient data exists for any calculation.

### HRV / RHR Baseline — Adaptive Rolling Window

- Uses 14-day average until 28 days of data are available
- Switches permanently to 28-day rolling average once 28 observations exist
- Minimum 14 observations required before baseline is considered reliable

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

Planned for Stage 2+. Decay function maps recent injury/tightness events to a multiplier that reduces the recommended load ceiling:

```
injury_weight = 1.0 - (severity × decay_factor × days_since_event)
```

Currently Stage 1 uses fixed RPE ceiling (7/10) and CLF (0.04) as the injury-aware constraints.

---

## Data Sources

| Data | Source | Refresh |
|------|--------|---------|
| Training sessions, readiness check-ins | Notion database | Real-time |
| HRV, RHR, sleep | Google Sheets (Oura/Whoop export) | Daily sync |
| Stage config | Notion config table | Per session |

Biometric data fetched over a 60-day rolling window to support the 56-night sleep baseline.

---

## Files

| File | Purpose |
|------|---------|
| [Stage_1_14_Day_Plan.md](Stage_1_14_Day_Plan.md) | Full day-by-day exercise prescription with mechanics, focus, and progression/regression cues |
| `training_plan.py` | Machine-readable plan data (exercise objects, sets, reps, holds, types) |
| `engine.py` | AU, strain, ACWR, CLF calculations |
| `readiness.py` | Readiness score + baseline computation |
| `app.py` | SPA router + home dashboard |
| `db.py` | Notion backend (sessions, check-ins) |
| `sync_sheets.py` | Google Sheets biometric sync |
