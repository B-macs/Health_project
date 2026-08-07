# RESUME: Health & Performance Autoregulation Engine

## PROJECT OBJECTIVE
Build a highly private, data-driven Health and Performance Application that eliminates training guesswork and optimises physical recovery and athletic scaling. The application acts as an objective "Autoregulation Engine" — using historical data, subjective daily inputs, and objective biometrics to dictate exact daily training volumes — while protecting the user from injury relapse through mathematical safety guardrails separated from predictive AI parsing.

---

## ARCHITECTURE — CURRENT STATE (as built)

> **Note on original spec:** The original architecture spec called for local-only SQLite. This changed during development. The decisions below reflect what is actually running.

| Layer | Original Decision | Current Decision | Reason Changed |
|---|---|---|---|
| **Execution** | Local only | Streamlit + Notion cloud DB | Notion provides structured database, relation properties, and a queryable API without a local server to maintain |
| **Frontend / UI** | Streamlit + AG Grid | Streamlit + responsive CSS (no AG Grid in active use) | Data Grid page removed; responsive dual-theme (Oura/Whoop) CSS system replaces it |
| **Database** | Local SQLite | Notion API — 4 databases | Notion selected; SQLite schema preserved in resume.md for reference but not in use |
| **Biometrics source** | Manual Apple Health entry on Autoregulation page | Blended Oura + Garmin read (`services/biometrics.py`) — Oura 70%/Garmin 30% for RHR and sleep duration, Garmin 80%/Oura 20% for steps. **HRV is held at Oura-only** (`HRV_GARMIN_HOLD = True`): `blend_biometric_day` routes HRV around `blend_metric` entirely, so the declared 70/30 HRV weighting has never once run, and a Garmin-only night yields `None` rather than a wrist value rescaling a finger-baselined series. Lift it on a measurement, not a date — `Repository.hrv_blend_status()` | Apple Health auto-export (Sheet1) proved unreliable; Oura/Garmin were already integrated archivally, so the engine now reads a weighted blend of both instead. Sheet1 is historical-only (one-time backfill source) |
| **Training entry** | Manual session logging via Training Entry page | Auto-logged by Training Plan on session completion | Training Entry page removed; logging is triggered by completing a guided day |
| **Body composition** | Not in the original spec | Two devices in **separate lanes**, display-only, never blended and never wired to the engine (`services/body_composition.py`, 2026-08-05) | The home scale contributes exactly one measurement — weight — since its body fat percent is fitted from weight and age; the gym's InBody measures genuinely but was run against four different typed heights. Blending them would invent agreement, and neither is measured on a cadence that could safely inform a training decision |

---

## DEVELOPMENT PHILOSOPHY — DETERMINISTIC FIRST (Non-Negotiable)

> **This rule applies to every new feature, every new bucket, every new function added to this project from this point forward. It is not optional and not context-dependent.**

### The Rule: Deterministic Before AI

Every new piece of functionality must be built in two explicit phases. Phase 1 is mandatory. Phase 2 is only permitted once Phase 1 is complete, tested, and confirmed working.

**Phase 1 — Deterministic Python (Always built first)**
All logic is implemented as explicit, rule-based Python code:
- If/else decision trees with clearly documented conditions
- Keyword matching tables with hardcoded term lists
- Threshold-based scoring using explicit numeric mappings
- Mathematical formulas applied directly, with no probabilistic components
- Outputs are fully predictable — the same input always produces the same output
- Unit-testable without any external service, API key, or model

**Phase 2 — AI Layer (Only added if Phase 1 is demonstrably insufficient)**
An AI or LLM component may be added on top of a working deterministic implementation only when:
1. The Phase 1 deterministic version has been built and is running
2. There is a specific, documented limitation that AI would improve
3. The AI output feeds into the system as structured data — it never directly controls a safety decision
4. A fallback to the deterministic version exists if the AI call fails

### The Hard Boundary: AI Never Controls Safety

Regardless of how mature the AI layer becomes, these components must always remain 100% deterministic:
- The Traffic Light biometric multiplier (Green / Yellow / Red)
- The ACWR calculation and its hard-lock thresholds
- The Stage 1 / 2 / 3 transition conditions
- The injury decay function and Background Watcher trigger logic
- Any prescribed set, rep, or volume target output to the user

AI components may only populate advisory fields — summaries, tags, flagged body parts, sentiment scores.

---

## CURRENT APPLICATION STRUCTURE

### SPA Navigation

`app.py` is the single Streamlit entry point. Navigation is **four `st.button()` widgets** rendered by `nav.py` and pinned to the bottom of the viewport with CSS — **no JavaScript is involved**; each button's `on_click` sets `st.session_state["_nav_page"]`, which is a WebSocket rerun with no page reload, and the router in `app.py` dispatches to the appropriate view. Routing resolves as `st.session_state["_nav_page"] or st.query_params.get("page", "home")` — session state is primary, `?page=X` is the fallback for direct URLs and first load — and `app.py` mirrors the resolved page back into `?page=X` on every run so a WebSocket reconnect (screen lock, backgrounding, dropped connection) resumes on the right page. `_pages/` was removed — Streamlit 1.36+ auto-detects that directory as a multi-page app and renders an unwanted top-nav bar; no `_pages/` stubs are needed.

| View module | Page | Purpose |
|---|---|---|
| `app.py` (home route) | Home | Dashboard: three cards — Readiness · Strain · Sleep — each opening a drill-down (`?d=<date>&view=readiness\|strain\|sleep`), plus prev/next-day navigation and the Check-In FAB. Card values come from `dashboard.compute_daily_metrics_snapshot`. ACWR, the traffic light and the session directive are **not** on Home — they render in Insights → Engine Data |
| `views/checkin.py` | Morning Check-In | Daily readiness entry: pain score, tightness, sensation tags, lifestyle factors |
| `views/training.py` | Training Plan | Interactive guided session runner for the active phase (Phase 1 → `training_plan.PLAN`, 21 days; Phase 2 → `training_plan.PLAN_STAGE2`, 28 days — mapped in `services/sessions.py::_PLAN_BY_PHASE_NUMBER`, so the day range is however many days are authored, never a fixed 14) with live timers, per-set capture, auto-logging and exit confirmation |
| `views/insights.py` | Insights | Six tabs: BioAge (four category cards — **Strength** via `services/strength.py` + `services/tonnage.py` + `services/bioage.py`, **Metabolism** via `services/body_composition.py`, **Flexibility** via `services/flexibility.py`; only **Cardio** is still "coming soon"), Engine Data (stage progression, ACWR, biometric traffic light, injury weight), Processing Queue, Macro Trends (tightness map + multi-week trend analysis), Sleep Architecture, Sync |
| `views/sync.py` | Voice Training | Embedded Voxplot voice-analysis UI |

### Removed Pages (intentionally)
| Page | Reason Removed |
|---|---|
| Training Entry | Replaced by Training Plan auto-logging |
| Data Grid | Background-only; no user-facing value during Stage 1 |
| Biomechanical Profile | Data moved to `patient_profile.py` (clinical input file) |

### Core Modules

| File | Role |
|---|---|
| `engine.py` | Pure deterministic maths — traffic light, ACWR, injury weight decay, stage state machine, volume recommendation. No DB access, no Streamlit. Derives per-stage ceilings from `rules.STAGE_CONSTRAINTS`. |
| `rules.py` | Movement safety rules — `STAGE_CONSTRAINTS` (ACWR ceilings, RPE caps, volume caps per stage). `MOVEMENT_RULES` (contraindicated / caution / cleared). Single source of truth for guardrails. |
| `repository.py` | The ONLY place Notion property names and Sheet column names live. ~40 methods wrapping `clients/notion.py`, `clients/sheets.py` and `clients/local_cache.py`. (There is no `db.py` or `sync_sheets.py` — both were replaced by this during the services/ extraction.) |
| `training_plan.py` | Exercise prescription data — `PLAN` is the completed Stage 1 block, **21 days** (authored as 14, extended to 21 on 2026-07-13 after the mid-back flare — Week 3 is "Flare Recovery & Reassessment Prep", Days 15-21); `PLAN_STAGE2` is the running 28-day Stage 2A block. Exercise specs, mechanics, biomechanical cues, progressions, regressions, pre-session release protocol integrated per day. |
| `training_constants.py` | Single source for `EXERCISES` catalogue, `ANATOMICAL_LOCATIONS`, `SENSATION_TAGS`, plus `EXERCISE_BODY_REGION` (one primary sector per exercise — feeds `strength.py` and `tonnage.py`) and `EXERCISE_MOVEMENT_WEIGHT` (content-aware AU weighting for Strain/ACWR). |
| `patient_profile.py` | Clinical input file — MRI findings + biomechanical assessment + muscle imbalance summary + `stage_transitions`. **Is** imported by active code: `views/insights.py` reads `PROFILE["imbalances"]` for the muscle-imbalance count. Updated before each new training block. |
| `readiness.py` | Readiness score calculator, `MODEL_VERSION 2` (2026-08-01). Scored from Oura's eight contributors plus our own Sleep Debt, with our weights and our composite — **not** Oura's score taken directly: hrv_balance .21, recovery .17, prev_night .16, rhr .13, body_temp .12, sleep_debt .09, prev_activity .05, sleep_reg .04, activity_bal .03. v1's HRV 40 / Sleep 35 / RHR 25 split is gone; it used `min(100, ratio*100)`, one-sided and saturating, and ran ~15 points high. Alcohol is no longer deducted. |
| `strength.py` | The Overall Strength Score — estimated 1RM against a fixed 2025 baseline (`strength_baselines.py`), plus the regional split. Currently in calibration: every index displays at 50. Measured performance can only push the level UP; the only downward force is detraining decay. |
| `tonnage.py` | Weekly work completed, in kg, overall and per body sector. A **separate** metric from `strength.py` sharing no term with it. No decay. Unloaded work counted in reps and seconds, never converted to kg. |
| `bioage.py` | One function — the muscle-imbalance count. The Stage-Adjusted Recovery Score it used to hold was deleted 2026-08-04 (its docstring says why; a test fails if the names return). |
| `body_composition.py` | The Metabolism screen's backend (2026-08-05). Parses the Foryond scale export, corrects the InBody 770's typed-height defect via `InBodyScan.at_height`, and supplies calendar-aligned `period_window` / `can_step` / `split_runs`. Stores three fields and lists the rest in `DERIVED_COLUMNS` — see BODY COMPOSITION below for the locked decisions, including the two things it refuses to compute. |
| `biometrics.py` | Oura+Garmin blend, nap handling (`split_sleep_periods`, `dedupe_sleep_periods`, `NAP_MIN_SECONDS`), and `HRV_GARMIN_HOLD`. |
| `background_sync.py` | `BackgroundSyncRunner` — runs device syncs off the Streamlit script thread. Builds its OWN `Repository` per run and never touches `st.*`. |
| `stats.py` | Deterministic statistical analysis — lag correlations, slopes, recovery direction. |
| `styles.py` | Responsive dual-theme CSS + component helpers. Oura palette (mobile ≤768px) / Whoop palette (desktop ≥769px). |
| `nav.py` | Bottom nav bar — four real `st.button()` widgets in `st.columns(4)`, pinned to the viewport bottom by CSS. **No JavaScript, no `stNav()`, no hidden trigger buttons**; the only markup it injects is a `display:none` `.stNavRow` marker div that the CSS uses as a `:has()` anchor to find the button row. `on_click` sets `st.session_state["_nav_page"]`. |
| `ai.py` | Phase 2 AI layer — session note parser, tightness parser, macro trend analysis. Advisory only. `MODEL_FAST = MODEL_SMART = "rules-based"` (no LLM called). |

### Supporting Directories

| Directory | Contents |
|---|---|
| `views/` | `checkin.py`, `training.py`, `insights.py`, `sync.py` — SPA view modules |
| `_pages/` | **Deleted** — triggered Streamlit 1.36+ auto top-nav; all routing is in `app.py` SPA router |
| `scripts/` | One-shot CLI tools: `init_notion.py`, `build_datastore.py` (rebuilds `services/datastore.py`'s snapshot), `backfill_oura_history.py`, `backfill_garmin_sleep_stages.py`, `backfill_garmin_from_sheet1.py`, `compare_readiness_to_oura.py`, `merge_duplicate_checkins.py`, `prepare_bioage_illustrations.py`, `garmin_login_test.py` |
| `docs/` | `INVENTORY.md`, `resume.md`, `focus.md`, `playbook.md`, `clinical_profile_weighting.md`, `REFACTOR_NOTES.md`, `progress.json`, `training/*.md` |
| `voice_training/voxplot` | Git submodule — standalone Voxplot voice-analysis source; Health pins its commit and embeds its renderer |

---

## LOGIC SEPARATION

### A. Strict Deterministic Engine (`engine.py`)

**Traffic Light Biometric Autoregulation**

Evaluates HRV, RHR and Sleep against a 28-day rolling baseline, plus a **fourth
metric — body-temperature deviation — against absolute cut points** (yellow
+0.35 °C, red +0.60 °C: a deviation has no meaningful ratio to a baseline, and
it is one-sided, only warmth counts against you). It then applies the
`baseline_drift` guard, which can downgrade green → yellow when the 28-day
baseline has itself moved adversely against the window before it — pass the
wider history as `traffic_light(..., drift_rows=)`, since a 28-row list alone
leaves the guard a no-op.

| Signal | Condition | Volume Multiplier | User-Facing Message |
|---|---|---|---|
| Green | Biometrics at or above baseline | **1.0×** — the traffic light itself never overloads (pinned by `tests/test_engine.py`). The 1.05× progressive-overload prescription comes from `volume_recommendation`, and only once observation mode is over, ACWR is not hard-locked and injury weight ≤ 70% | Nothing shown — train normally |
| Yellow | Drop within 10–25% | 0.75× | "Reduced load today — keep session controlled" |
| Red | Drop >25% | 0.0× | "Rest day — mobility and walking only" |
| Grey | Insufficient data (<7 days) | 1.0× | Nothing shown |

**Directive delivery:** The directive surfaces as a plain-language banner at the
top of the Training Plan page — a signal-colour strip plus the coach headline,
which is `directive["action"]` verbatim. It is **not** true that no numbers reach
that page: the headline names the injury-weight percentage on a conservative-load
day, and while `ACWR_ADVISORY_MODE` is on the advisory caption below it carries
the raw ACWR ratio. What stays in Insights → Engine Data is the numeric *panel* —
ACWR acute/chronic/ceiling, HRV/RHR/sleep deltas against the 28-day baseline, and
the raw injury-weight decay.

**Acute-to-Chronic Workload Ratio (ACWR)**
```
ACWR = 7-day avg content-weighted session AU
     / avg content-weighted AU over the CURRENT stage's days inside the 28-day window
Session AU = Session-RPE × Duration (minutes)   [Foster method]
     Stored RAW in Notion; each day is scaled at READ time by
     content_weighting.day_content_multiplier via get_daily_session_au_weighted,
     which is what both live callers pass in.
     Falls back to the flat 28-day mean when no stage_start is given, or when
     fewer than ACWR_MIN_IN_STAGE_DAYS (14) of the window's days belong to the
     current stage — in which case status is `baseline_establishing` and the
     ratio never hard-locks.
```
Stage 1 ACWR ceiling: 1.2. Stage 2: 1.3. **Not enforced right now** —
`engine.ACWR_ADVISORY_MODE = True`, so a breach sets `exceeds_ceiling` and emits
an advisory note (`volume_recommendation()["acwr_advisory"]`) but leaves
`hard_locked` False. The ceiling itself is untouched; flipping that one flag back
to False restores hard-locking with no other edit.

**Injury Weight Decay**
$$\text{Injury Weight} = e^{-\lambda t}$$
λ = 0.05 (default, reviewed every 14 days). t = pain-free days.
- >70%: Conservative load even on green biometric days
- 20–70%: Standard stage constraints apply
- <20%: Background watcher only

**Volume Recommendation Cascade (priority order)**
1. Observation mode (< 14 days biometric data) → hold at comfortable effort
2. Red traffic light → rest/mobility only
3. ACWR hard lock → cap at 75% volume — **currently unreachable**, because
   `ACWR_ADVISORY_MODE = True` forces `hard_locked` False; the breach rides
   along as `rec["acwr_advisory"]` beside whatever the biometrics decided
4. Yellow traffic light → 75% volume
5. Injury weight > 70% (green bio) → 85% volume (conservative)
6. All clear → 105% volume (progressive overload)

---

### B. Probabilistic Engine (`ai.py` — Phase 2, advisory only)

| Component | What it does | Deterministic fallback |
|---|---|---|
| Session note parser | Extracts body parts, sentiment, warning level from free-text | Keyword-to-tag matcher (see library below) |
| Tightness parser | Converts subjective tightness text to severity + body parts | Keyword severity weights |
| Macro trend analysis | Interprets lag correlations across 90-day dataset | Fixed lag-correlation matrix — `stats.compute_all_correlations`, 9 pairs: AU → HRV/RHR/pain/tightness (lags 1–3), sleep → HRV (0–1) and pain (1–2), stress → HRV (0–1) and pain/tightness (0–2). HRV is only ever a *target* series, never a predictor — there is no HRV → pain pair |
| Movement risk assessment | Maps MRI findings + recent session notes to movement flags | Pre-populated movement contraindication list in `rules.py` |

---

## STAGE STATE MACHINE

Evaluated at Day 14 and every 14 days thereafter. **All transition logic is deterministic.**

### Stage 1 — Rehab (Tissue Tolerance Focus) — COMPLETE (ran to 2026-07-19)
- Conservative ACWR ceiling: 1.2
- High injury weight influence (starts at 100%, decays with pain-free days)
- Bodyweight only — no external load
- Session RPE ceiling: 7/10

Extended by 7 days (Days 15–21) after a mid-back flare meant the Day 14 exit
criteria were not met on the original schedule. Still `phase_number=1` — a
continuation, not a new phase.

### Stage 2 — Transition (Work Capacity Focus) ← CURRENT
- Specific rehab movements blend into standard training warm-ups
- ACWR ceiling: 1.3
- External load introduced (barbell, cable)
- 4-week block — reassess after completion
- Progressive overload prescription: +2.5 kg per session (vs +1 rep in Stage 1)

**Active block: Stage 2A — 28-Day Gym Strength Block** (`training_plan.PLAN_STAGE2`),
started 2026-07-20, Day 28 reassessment 2026-08-16. Progression is split
fast-track / slow-track by whether the 2025 log documents the pattern as a
strength or a breakdown point, rather than one global +2.5 kg rule. No overhead
pressing this block, and no running — both deliberate. Current-state detail
lives in `docs/focus.md`; clinical detail in `patient_profile.py`.

### Stage 3 — Performance & Growth
- Injury weight < 20% → becomes silent background watcher
- Full progressive overload protocols
- Background Watcher re-activates on any session note matching trigger terms

**Stage 1 → 2 transition criteria (all must be met):** — SATISFIED 2026-07-19,
recorded in `patient_profile.PROFILE["stage_transitions"]`.

| Criterion | Threshold |
|---|---|
| Pain-free streak | ≥ 14 consecutive days |
| Average 14-day tightness | ≤ 3.0 / 10 |
| McGill Big 3 | Performed pain-free with good form (Day 14 screen) |
| Hip hinge full range | Pain ≤ 2/10 at arms-past-knees range |
| Physiotherapist sign-off | Required |

Note on `pain_free_streak`: agreed with the user 2026-07-13 to treat it as
**informative, not a hard blocker**, provided tightness (≤3.0) and pain (≤2/10)
are met and the physio signs off. A single reversed day inside an otherwise
improving trend should not restart the clock the way a fresh injury does.

**Stage 2 → next-block criteria** live in
`patient_profile.PROFILE["stage_2_exit_criteria"]`, evaluated 2026-08-16.

---

## CLINICAL INPUT — `patient_profile.py`

Updated before each new training block. Single source of truth for MRI findings
and biomechanical assessment. **Not a UI page** — it is the design-time clinical
reference each training block is authored against (`training_plan.py` cites it in
comments only; it does not import it). It is also live input now: `views/insights.py`
imports it and passes `PROFILE["imbalances"]` to `bioage.muscle_imbalance_count`
for the Strength screen, so edits to `imbalances` can break the gate
(`tests/test_bioage.py` pins the count at 8).

### MRI (10.11.2025)

**Primary — L5/S1:**
- Moderately activated osteochondrosis with paradiscal bone oedema and mild erosive changes
- Narrow retrolisthesis + broad-based disc protrusion right dorsolateral
- Moderate right foraminal stenosis; mild left
- Hot level — primary driver of acute symptoms

**Secondary — L3/L4 and L4/5:**
- Flat protrusions left dorsolateral; covered annulus tears (contained, stable)
- Retrolisthesis at L4/5
- Mild foraminal stenosis at both levels

**Cleared:** Spinal canal clear, facet joints clear, SI joints normal, musculature symmetric

**Downstream:** Psoas/hip flexor hypertonicity (L1–L4 origin) amplifying L5/S1 foraminal compression

### Biomechanical Profile (6 Assessed Findings)

| # | Finding | Structures | Training Implication |
|---|---|---|---|
| 1 | Upper glute / hip crest chronic tightness | Glute medius (upper fibres), piriformis | Must INHIBIT before activating — release first, strengthen second |
| 2 | Standing hinge crack — right sit-bone area | RIGHT posterior hip capsule, proximal hamstring tendon at ischial tuberosity | Right posterior capsule needs direct mobilisation; ischial desensitisation required |
| 3 | Sitting forward-bend releases | Thoracic facets T6–T10, horizontal lumbar facets at L5/S1 | Thoracic extension work + thread-the-needle; posterior pelvic tilt for lumbar base |
| 4 | 90° hip click RIGHT side only (painless) | Iliopsoas tendon over iliopectineal eminence | All right hip flexion cues: NEUTRAL or slight INTERNAL rotation — external rotation triggers snap |
| 5 | Wide-stance windmill cracks | Anterior hip capsule, pubic symphysis, lumbar facet joints (rotation) | Lateral lunge, 90/90 flow, Pallof press address these — introduce wide stance slowly |
| 6 | Right shoulder instability — maintenance-dependent, **NOT resolved** (3 anterior dislocations; a capsular repair that still permitted a third, then a Latarjet coracoid transfer; RIGHT only) | Right glenohumeral capsule/labrum (post-Latarjet), scapular stabilisers | Stability is now muscular, not ligamentous — scapular control work is a STANDING requirement, not optional conditioning. No overhead or standing press in Stage 2A; Incline DB Press is this block's pressing pattern instead |

**Primary imbalance:** Under-firing glute max + deep core → upper glutes/hip flexors over-grip for artificial stability → compressed joints + snapping tendons.

**Pre-session release protocol (runs at START of every session, ~5 min):**
1. Upper Glute/TFL Self-Release — wall pressure, 2 × 90s each side
2. Piriformis Contract-Relax (PNF) — 3 × 5 cycles each side
3. *(Hip-focused sessions add)* Right Posterior Hip Capsule Cross-Body Stretch — 3 × 60s right only; Ischial Tuberosity Hamstring Release — 2 × 90s each side
4. *(Right hip loaded)* Right Hip Tendon Path Drill (Coxa Saltans) — 2 × 10 reps right only

---

## STAGE 1 TRAINING PLAN — 21 DAYS (COMPLETE, ran to 2026-07-19)

`training_plan.PLAN` — Days 1-14 as originally authored, plus Days 15-21
("Week 3: Flare Recovery & Reassessment Prep", added 2026-07-13 after the
mid-back flare left the Day 14 exit criteria unmet). The Session Features below
are phase-agnostic and drive both blocks — `views/training.py` resolves the plan
through `services/sessions.py::_PLAN_BY_PHASE_NUMBER` — but the bodyweight
prescription under Structure is Stage 1 only; Stage 2A is externally loaded.

### Structure
- Hardcoded bodyweight prescription in `training_plan.py`
- Interactive session guide in `views/training.py`
- Day number derived from the ACTIVE PHASE's `start_date` (phases are one JSON
  blob under the Notion Config DB key `phases`), with a `date_overrides` entry
  for that date winning over the `(d - start).days + 1` formula — that is how
  `services/scheduling.py`'s readiness auto-shift moves a session day, and
  `day_number 0` means forced rest. The separate `plan_start_date` config key
  does NOT drive the day number: it gates the first-run setup screen, seeds
  Phase 1, and feeds the "Plan Start" metric
- Session completion auto-logs all exercises to Notion Training DB

### Session Features
- Exercise-by-exercise guided flow — one exercise shown at a time
- Live countdown timers: hold timer (isometric), rest timer (auto-starts after set complete), duration timer (walking, breathing)
- Timer state persisted to browser `localStorage` — navigating away and returning resumes mid-timer
- Session state persisted in `st.session_state` — navigate to any other page and return exactly where you left off
- Exit Training button in the SESSION IN PROGRESS strip at the top of the Training page (only visible when a session is active) — requires confirmation before discarding progress. **There is no sidebar anywhere in this app** — it is suppressed in `app.py`, and `st.sidebar` has zero occurrences repo-wide
- Rest timer auto-starts on entering rest phase; no Skip button (Next Set serves that function)
- On completion: RPE slider + session notes → auto-logged to Notion. **Duration is not entered** — it is auto-timed from the first completed set (5-minute floor, falling back to `sessions.estimate_duration()` if no set was marked complete) and shown read-only as "Session duration: N min (auto-timed)"

### Week 1 Focus: Neural Reset (Days 1–7)
Daily pre-session biomechanical release block → tissue tolerance, neural desensitisation, psoas inhibition, McGill protocol introduction, gluteal activation foundation, thoracic mobility, walking baseline

### Week 2 Focus: Neuromuscular Loading (Days 8–14)
McGill protocol progression, functional hip hinge (RDL), single-leg stability, isometric endurance, functional integration (sit-to-stand, step-ups, plank), Day 14 stage readiness assessment

### Week 3 Focus: Flare Recovery & Reassessment Prep (Days 15–21)
Added 2026-07-13 after the mid-back flare left Day 14's exit criteria unmet.
Still Stage 1 — bodyweight only, ACWR ceiling 1.2, RPE ceiling 7 — with session
RPE targets held at Week-1 levels (3–5) rather than Week 2's, i.e. a gentle
re-entry rather than a resumption. Right-shoulder scapular stability introduced
as a standing requirement per biomechanical finding #6 (Scapular Wall Slide,
Prone Y-Raise), the revised right hip capsule cue replacing the original
cross-body version, and Day 21 repeating the full Day 14 assessment battery —
McGill Big 3, single-leg balance eyes-closed, hip hinge full range, 5-minute
walk + stair — for a directly comparable reassessment data point.

---

## BIOMETRICS PIPELINE

As of 2026-07-13, the engine's live biometric source is a blended Oura+Garmin
read — Sheet1/Apple Health auto-export was retired from the live pipeline
(unreliable auto-export) and is now historical-only.

```
Oura API (official)                    Garmin Connect (unofficial)
        ↓  sync_oura_all(days=7)               ↓  sync_garmin_daily_if_due(days=2)
        ↓  [2h cache, app.py, on Home open]     ↓  [every 2h, Config-DB gated,
        ↓                                         stops for the day once
        ↓                                         today's check-in is in —
        ↓                                         app.py Home + training.py]
Oura Daily / Oura Sleep Periods sheet tabs    Garmin Daily sheet tab
        └──────────────────┬──────────────────────┘
                            ↓
         Repository.get_biometric_rolling(days, today)
                            ↓  [reads all 3 tabs, groups by date]
         services.biometrics.blend_biometric_day(date, oura, garmin)
                            ↓  [Oura 70%/Garmin 30% for RHR/sleep;
                            ↓   Garmin 80%/Oura 20% for steps; HRV bypasses
                            ↓   the blend entirely while HRV_GARMIN_HOLD is
                            ↓   True and is Oura's or None; renormalizes to
                            ↓   100% of whichever source is present if the
                            ↓   other is missing that day]
                  engine.traffic_light(biometric_rows)
                            ↓
      Directive → Training Plan banner (plain language)
      Full data + sources_missing flags → AI Insights → Engine Data tab

         Repository.sync_biometric_blend(days, today)   [same blend fn]
                            ↓  [every 2h, app.py → run_home_syncs; also
                            ↓   on-demand full-
                            ↓   history backfill button, Insights → Sync]
              Biometric Blend sheet tab (persisted, keyed by date)
                            ↓
      Repository.get_biometric_blend_history(start, end) — unbounded
                            ↓
      Insights → Sync → "Biometric Blend History" table
```

`get_biometric_rolling()` above is a **live recompute** — calling it twice
for the same past date can, in principle, give a different answer if Oura/
Garmin have revised that day's raw reading since, or if the blend weights
change. `sync_biometric_blend` persists each day's result once to its own
"Biometric Blend" sheet tab; a day stops being touched (and so becomes a
fixed historical record) once it falls outside whichever rolling window the
next sync runs with (7 days for the 2-hourly auto-sync). This is what makes
"look back at last month" show a stable value rather than a live re-derivation.

Sheet1/Apple Health: `Repository.get_sheet1_biometric_rolling()` /
`get_all_sheet1_biometric_records()` retain the old mapping+read, used only
by `scripts/backfill_garmin_from_sheet1.py` (one-time historical backfill
into the Garmin Daily tab, so readiness.py's 14/28/56-day rolling baselines
have pre-wearable history) and the legacy raw-preview table in Insights →
Sync.

### Column Mapping (legacy Sheet1 → Engine, historical/backfill only)

| Sheet Column | Engine Field | Conversion |
|---|---|---|
| `Date/Time` | `date` | Extract YYYY-MM-DD |
| `Active Energy (kJ)` | `active_kcal` | ÷ 4.184 |
| `Heart Rate Variability (ms)` | `hrv_ms` | Direct |
| `Resting Heart Rate (count/min)` | `resting_heart_rate` | Direct |
| `Sleep Analysis [Total] (hr)` | `sleep_duration_hours` | Direct |
| `Sleep Analysis [Deep] (hr)` | `sleep_deep_hours` | Direct |
| `Step Count (count)` | `steps` | Direct |
| `Weight (kg)` | `weight_kg` | Direct |

### Blend Mapping (Oura + Garmin → Engine, live pipeline)

| Engine Field | Oura Source | Garmin Source | Weights |
|---|---|---|---|
| `hrv_ms` | Sleep Periods tab, main sleep period `average_hrv` | Daily tab `hrv_ms` (from `get_hrv_data`) | **Oura 100%** — held by `HRV_GARMIN_HOLD`; the 70/30 is declared but has never run |
| `resting_heart_rate` | Sleep Periods tab, main sleep period `lowest_heart_rate` | Daily tab `resting_hr` | Oura 70% / Garmin 30% |
| `sleep_duration_hours` | Sleep Periods tab, **DAY TOTAL**: the deduped main sleep period **plus every remaining nap ≥ `biometrics.NAP_MIN_SECONDS` (900 s)**, ÷ 3600. The main period's own `total_sleep_duration` is kept separately as `oura_sleep_total_seconds`, the REM/deep denominator — duration counts naps, architecture does not | Daily tab `sleep_hours` | Oura 70% / Garmin 30% |
| `steps` | Daily tab `steps` (from `daily_activity`) | Daily tab `steps` | Garmin 80% / Oura 20% |

`active_kcal` and `sleep_deep_hours` are out of scope for the blend (nothing in
`engine.py`/`stats.py`/`insights.py` reads them) and are `None` on blended
records. `weight_kg` is also `None` here and stays that way: body composition
has its own pipeline and is deliberately **not** part of the biometric blend —
see below.

---

## FLEXIBILITY (v3, 2026-08-06 — clusters. v1 and v2 are both deleted)

`cluster_a_mechanics.py` + `services/battery.py` + `cluster_a_battery.py` +
`cluster_a_prescription.py`, joined by `services/flexibility.py` and rendered by
`views/insights.py::_render_flexibility_detail`. Storage via the five
`Repository.*_flexibility_*` methods on `clients/local_cache.py`.

Display-only. **Nothing here feeds the engine** — same standing rule as Body
Composition below. Flexibility is not a safety input (Key Rule 2);
`services/rules.py` remains the only thing that constrains movement.

### Two models were built and deleted before this one. Read why before proposing a third.

**v1** scored eight body regions as `sqrt(RANGE × CONTROL)` and averaged them.
The athlete refuted it in one sentence — *"we know my hips are stuck in flexion
with my back arched and this is a huge issue for me, and yet my flexibility
score is nearly 80 for hips"* — because the `hip` average buried Deep Lunge, the
one thing testing his worst documented capacity, under four healthy
contributions. It also scored a self-rated depth on a **two-sided band** where a
rating of 88 scored 46, inferring absence of control from presence of range with
no evidence for the step.

**v2** replaced regions with skills, scored `skill = min(rungs)` over fourteen
rungs, and named the limiting rung. Better, and still the wrong shape.

**v3 is not a refinement of v2.** The battery is a **decision tree with early
exit**; `min()` is a scoring function over everything. A failing slot 0 does not
make the slots below it lower priority — it makes them **meaningless**, because
a bony block makes the tissue questions unanswerable. Those are different
programs and the second cannot be tuned into the first.

Guards live in `tests/test_cluster_a.py`: the v1 names (`band_score`,
`CONTROL_BAND`, `OVERSHOOT_SLOPE`…) and the v2 names (`rung_score`,
`score_skill`, `SkillScore`, `WIDE_GAP_POINTS`, `RUNGS`, `SKILLS`) all fail the
gate if they reappear.

Nothing was lost in either deletion: no assessment had ever been run, and none
of Cluster A's measurements were implemented by any v2 rung — the closest,
`adductors`, tested the same tissue at the same leverage from a different
position with a different landmark.

### Three layers, one direction, enforced by tests

```
MECHANICS  (why)          limiters + the exercise library
    ↓                     no tests, no doses
BATTERY    (how to test)  four slots, one pattern label out
    ↓                     no exercise names
PRESCRIPTION (what to do) pattern in, ordered stack out
                          no tests; names exercises but defines none
```

Stating the rule is not enough — this repo already makes exactly this class of
rule executable in `tests/test_no_streamlit_in_services.py`, and the four guards
do the same job here:

1. The battery layer's source contains no exercise name from the Mechanics
   library, and no dose.
2. Every exercise the Prescription names **resolves in the Mechanics library**.
   This is the load-bearing one: a name that does not resolve means the
   Prescription invented an exercise, which is how two documents end up defining
   the same thing.
3. `Exercise` has nowhere to put a dose, and Mechanics defines no pattern
   labels. Checked structurally rather than by scanning for "× 8", because the
   Copenhagen note legitimately records what he last performed in 2025.
4. **`prescribe(None)` raises `NoPatternError`** and the message names the next
   action. The source is explicit: *"a prescription without a pattern is a guess.
   Say so rather than guessing."*

### The four slots, and stopping

| Slot | Question | What the answer decides |
|---|---|---|
| **0 Structure** | Is a bone stopping you? | Whether anything below is valid |
| **1 Regressed** | Is the tissue short at low demand? | *Which* exercises |
| **2 Prerequisite** | Do you have the component the skill needs? | *Whether* it is trainable, and where the fix sits |
| **3 Spectrum** | Passive, isometric, active | *Which end* — assisted or resisted |

Output is **one pattern label, A–I, and nothing else**. Not a score, not a
ranking. `services/battery.py` walks the evaluators in order and returns as soon
as one does not pass; the slots below are never evaluated.

**The capture flow stops too**, and it asks the real battery after every step
rather than re-implementing the rule, so the screen and the engine cannot
disagree about when to stop. Failing gate 0 on orientation ends the session
after two readings instead of walking him through eight more that cannot be
interpreted. Continuing is offered but is not the default — a curious athlete
taking extra readings is harmless, and forbidding it would be paternalistic, but
the time is real.

**A third outcome beside pass and fail: `indeterminate`.** The readings were not
taken, so the battery stops without naming a limiter. That is honestly different
from "you passed" and must never collapse into it — **a measurement not taken is
not evidence of health.**

### The fifth limiter, and the claim the whole cluster rests on

The source names four limiters: bone, adductor length, end-range strength,
puller strength. A fifth was added for this athlete, and it is his dominant one.

> *"The lumbar issue is driven from the specific tilt deficit, which needs a
> specific flexibility training method to fix it."* — athlete, 2026-08-06

**The lumbar rounding is the compensation, not the problem.** He rounds because
the pelvis will not rotate forward in sitting — straddle fold 25/100, *"hips
stuck in flexion with tail bone down, back fully rounds"*, reported
independently in four seated positions on 2026-08-05. That distinction decides
the programme: the answer is not to fold more carefully, it is to build the tilt
until there is no reason to compensate. A stack that only removes the fold takes
away the symptom and leaves the cause.

It has two components, which map exactly onto slot 2's Range/Production split:

| Component | Evidence | Fix |
|---|---|---|
| **Hamstring reserve** | 89°/86°, called *Normal* — but long-sitting upright with a straight knee is already ~90° of hip flexion, so he is at the limit **just sitting up** | Hinge flat-backed, never fold. Or sit above it — elevation removes the requirement |
| **Hip flexor production** | Untested. *"You need end-range hip flexor strength to pull yourself into the anterior tilt"* | Resisted work — lift-offs from a flat back |

This is not short hamstrings. It is **normal length with no reserve** under an
exceptional lumbar spine, which is why every further degree of fold has to come
from the spine.

### §F is the tilt-specific method, rebuilt rather than filtered

`cluster_a_battery.EXPECTED_PATTERN` is **F**, written into the code *before
measuring* so a borderline reading cannot be quietly read toward the answer
already in mind. It also disagrees with the generic lax-tissue prediction of H
or I — he has a specific range deficit inside an otherwise hypermobile body, and
that disagreement is worth watching rather than resolving in advance.

The source's §F was four pancake variations, three using a plate or a strap to
reach depth. For a body that folds by rounding, that assistance produces depth
**through the spine** — the contraindicated route and the wrong measurement.
Removing them would have left a stack of leftovers. Four prongs instead:

1. **Seated pelvic rock, mid-range** — the tilt as an isolated movement. You
   cannot train a position through a joint action you cannot perform alone.
2. **Elevated flat-back straddle hinge, no added weight** — sitting above foot
   level rotates the pelvis forward on its own. **Lowering the block over months
   is the progression**, not reaching further at a fixed height.
3. **Straddle lift-offs from a flat back** — hip flexor strength to *produce* the
   tilt rather than be placed into it.
4. **Flat-back hip hinge, legs together** — raises the hamstring ceiling.

**Success is not depth.** The number that should move first is the height at
which the lower back stops being flat. Forehead height may not move for weeks
and that is not failure.

### Procedural rules that are now tests, not comments

- **Measure order is active → isometric → passive.** Passive work leaves tissue
  looser for an hour, so a passive trial taken first flatters everything after
  it — the rule most likely to be broken by working through the tests in written
  order.
- **The load window.** An isometric reading as deep as the passive one means the
  load was too light and passive tissue absorbed it; the slot reports a botched
  measurement rather than a gap of zero. **Load and measurement are one datum**
  and round-trip together.
- **Three baselines on three mornings** before a number is trusted. The spread is
  the noise; a change under ~2× it returns *"not a result"* rather than a delta,
  and before three mornings exist `is_a_result` is False for any change —
  the safe direction, because a wrong True changes a programme for nothing.
  `BatteryResult.trusted` is separate from `.complete`: a pattern off one session
  is a **hypothesis**, and the screen says so.
- **Measure cold**, and **the worse side decides** — never an average.

### The documents are adapted, not filtered at runtime

The three source documents in `Input_files/` are edited **in place** for this
body (dated 2026-08-06), because leaving two documents defining one thing is the
failure the layering exists to prevent. Every adaptation carries the **condition
that reverts it** — the `biometrics.HRV_GARMIN_HOLD` idiom, held on evidence
rather than deleted. `cluster_a_mechanics.REMOVED` and `.DEFERRED` carry the same
in code, and a test asserts every one names its revert condition.

Two adaptations cost nothing because the source supplies them: gate 0 and every
triangle side split are cued from **external rotation** rather than a lumbar arch
(*"neither is more correct; both align the joint identically"* — one arch cue had
propagated into nine prescription instances), and the nerve check became a
differentiator rather than a provocation, which the battery's own footer already
demanded.

Held with stated conditions: loaded end-range work is unloaded pending the
anterior-hip question raised 2026-08-05; horse stance and Cossack are deferred
past **2026-08-16**, because an open Stage 2 exit criterion reads *"no increase
in Coxa Saltans frequency under loaded squat/split-squat work"* and introducing
two ER-cued loaded squats inside the assessment window would confound the
criterion he is about to be assessed on — a measurement cost as much as a safety
one.

Every stack is prefixed with `patient_profile.PROFILE["pre_session_release"]`,
which all nine source stacks omitted entirely because it comes from the clinical
file rather than from any flexibility method.

`scripts/check_cluster_documents.py` runs every movement **named** in all three
documents through `check_movement` at the live stage — 77 of them, all resolving
to cleared or caution. Extraction is structural (a table whose header declares an
exercise column, or a numbered item with a bolded head) rather than a word list,
which would need updating whenever a document gained a term and would fail open
when it hadn't. `tests/test_cluster_documents.py` pins it and skips cleanly when
`Input_files/` is absent.

### The rest-day question is closed

`REST_DAY_CONFLICT_UNRESOLVED` is **retired**. The Prescription's dosage section
settles it: a cluster session is adaptation-seeking by definition, so
`flexibility_window` now returns `poor` for a rest day rather than deliberately
ignoring the flag. A restorative yoga flow on a rest day remains fine — that is
`services/yoga.py`'s business. Placement is set against the real week: Stage 2A
loads legs on days 1, 3 and 5, leaving **day 7** clean with day 2 as the
same-day-evening fallback.

The window's physiological mechanism is still **not encoded and not relied on** —
the source's own "what to hold loosely" section says the calpain story is stated
past what the evidence carries, and it is treated as motivation the way
`services/sleep_fusion.py` treats the abandoned quiet-wake rule.

### Refusals (all pinned)

- **No score out of 100.** The battery's output is a label and "nothing else".
- **No flexibility age in years.** The gym ships 28 against a live age of 31,
  measured when he was 30 — a stale measurement against a moving comparator.
- **No prescription without a pattern.** Raises, with the next action named.
- **No averaging of anything with anything**, including left against right.
- **No reading carried over** from the legacy gym goniometry or the 22 pose
  ratings. They answer none of the battery's questions, and a self-rating of a
  yoga pose isolates no locked joint. Kept as provenance; nothing computes from
  them.

### Open

- **Zero assessments run.** Everything above is a model waiting for its first
  reading. Run it **before 2026-08-16** — it is measurement, not prescription,
  and it puts a pattern label in front of the physiotherapist instead of a plan
  to get one.
- **Every threshold is provisional** — `GATE0_ORIENTATION_GAIN_CM`,
  `LEVERAGE_TARGETS`, `TILT_TARGET_DEG`, `SPECTRUM_GAP_CM` all come from the
  source (or were invented to make the code run) rather than from his own
  spread, which has never been measured. `GATE0_BONE_RELEVANT_CM` (15) is
  different in kind: the athlete's own call (2026-08-07) about where the bony
  mechanism operates — bone meets socket only in the last few centimetres of a
  full split — so above it `applicable_tests` skips the turned-out comparison
  and slot 0 passes on the neutral height alone.
- **The tilt is an ANGLE, own power first (2026-08-07).** Degrees of pelvic tip
  read off a phone held flat on the lower back, sitting tall vs deepest tip.
  Forehead height was exactly the number a rounding spine can fake — and the
  rounding is his documented compensation — so the angle needs no second guard
  measurement and one number replaced two. Production runs before the helped
  trial for the same reason slot 3 runs active → isometric → passive: help
  flatters whatever follows it. A tilt reading stored in centimetres is from
  the retired protocol and comes back `indeterminate`, never read as degrees.
- **Two frozen constants still uncaptured**: the traced side-split stance and
  the floor reference. Straddle width and the tailor's heel distance are now
  captured beside their readings (`Reading.setup_value`), and the capture
  screen offers last session's number back rather than trusting memory.
  `block_height_cm` is deliberately *not* frozen — it is the progression
  variable.
- **Cluster B is unbuilt.** The blueprint's Pike is defined as *"touching your
  toes; forward fold"*, wording that hits two contraindicated rules outright — a
  whole-cluster collision to resolve before that one is authored.


## BODY COMPOSITION (2026-08-05)

`services/body_composition.py` + `body_composition_baselines.py` +
`views/insights.py::_render_metabolism_detail`. Display-only. **Nothing here
feeds the engine** — not the traffic light, not ACWR, not readiness, not the
volume recommendation — and it must not, until composition is measured on a
fixed cadence. Body composition is not a safety input (Key Rule 2).

### Two devices, kept in separate lanes — permanently

| | Foryond foot-only scale | InBody 770 (gym) |
|---|---|---|
| Source | `Input_files/Fitdays-Brian.csv`, gitignored | paper print-out, no export path |
| Cadence | near-daily when the habit holds | five scans, then nothing for 404 days |
| Real measurements | **weight, and nothing else** | segmental impedance |
| Unique to it | — | **phase angle, ECW/TBW** |

They are never blended. Measured across five paired dates the weight gap
averages **+0.24 kg** (sd 0.35) and on 2025-05-21 both read 79.5 kg exactly —
but everything else they *estimate* separately, so a fused number would invent
an agreement that is not there. Weight is the only quantity they may share.

### The scale's fourteen columns are one measurement

Its body fat percent is itself fitted from weight and age at **R² 0.9966**,
residual **0.051 pp** against the 0.1 pp step it prints — and it read 78.8 kg
on three occasions across 111 days and printed 16.0% every time. Every other
column reproduces from weight to inside its own display precision: BMR is
Katch-McArdle on fat-free mass, skeletal muscle % is `77.80 − BMI`, bone is
4.994% of fat-free mass, and so on. `DERIVED_COLUMNS` lists all of them and a
test fails if any becomes a stored field. One number presented as fourteen
agreeing measurements is how a screen misleads without stating anything false.

### The InBody height defect, and why the fix is a correction not a dismissal

InBody derives total body water from `k · height² / R`, then fat-free mass as
`TBW / 0.73450`, then fat as the remainder — so **height enters squared, in the
first step**, at a measured **−0.89 pp of body fat per centimetre**. The gym
typed a different height on four of five scans; back-solving `√(weight ÷ BMI)`
recovers **185.5, 175.1, 174.9, 181.6, 181.8 cm** against a true **182.0**.

The proof needs no fitting: two scans **eight minutes apart** on 2025-05-21
report 20.0% and 14.0% body fat at an identical 79.5 kg, because BMI moved
while weight did not.

`InBodyScan.at_height` re-runs a scan through the device's own chain at 182 cm.
What matters is what survives it:

- the eight-minute pair goes from **6.0 pp apart to 0.31 pp**
- the five-scan spread falls **8.2 → 4.64 pp**
- 13 Jan → 27 Jun 2025 becomes **−4.22 kg fat, +0.72 kg lean** on a −3.5 kg
  weight change — three figures that reconcile exactly, inside the year's
  strongest training block
- no height exponent between 0 and 6 removes the residual

**Correcting a measurement is not the same as dismissing it.** The correction
is what made the real recomposition visible.

### Phase angle and ECW/TBW are the only height-immune readings

Both are quotients of directly measured quantities — `arctan(Xc/R)` and a ratio
of two volumes — so no value typed at a console can move either. Phase angle
read **6.1° on all three scans that report it** while printed body fat went
20.0 → 14.0 → 11.8%; ECW/TBW held **0.375–0.379** across all five. They get
their own block on the screen, above the derived cards, and tests pin that
`at_height` leaves them untouched.

### Refused, with tests

1. **A fused body-fat number across the two devices.** The scale contributes no
   composition information, so fusing adds a term with no signal and would make
   the result look more certain than the InBody alone.
2. **Any composition expressed in years.** The scale already ships one:
   `−20.73 + 1.226·body_fat% + 0.900·chronological age`. That is age predicting
   age.

Both are the Stage-Adjusted Recovery Score's mistake in a new place — a
plausible formula over inputs too weak to carry it. `test_body_composition.py`
fails if either name reappears.

### Known limits, deliberately not solved yet

- **Cross-device calibration is infeasible at this cadence.** The body-fat gap
  has sd 3.30 pp across five pairings; the mean offset needs **11 paired scans**
  for SE < 1.0 pp and **44** for SE < 0.5. At monthly gym visits that is a year
  and four years. Segregate rather than calibrate.
- **The training log cannot produce kilograms of lean mass.** No calibrated
  within-person e1RM→kg mapping exists, the chain would be e1RM → regional CSA
  → whole-body lean (two lossy conversions), and the log records no per-set
  laterality so it cannot be matched to the InBody's left/right segments. The
  intended use is a **consistency gate** — flagging a scan whose regional lean
  change contradicts regional strength — not an input to a fused number.
- **A block-level lean readout is arithmetically pointless.** Published
  two-scan minimal difference for InBody fat-free mass is 1.60–2.32 kg against
  a plausible 28-day signal of ≤1 kg. And BIA fat-free mass *is* a water
  measurement, so returning to loaded training repletes glycogen and its bound
  water by 1–2 kg with no new contractile protein.
- **A 183 → 182 cm discontinuity exists in the scale series** from 2026-08-05.
  The re-export did not back-apply, so all 142 historical rows remain at 183.0.
  The next reading steps **BMI +0.27** guaranteed, and possibly **+0.9 pp** body
  fat, from the setting alone. That step is a setting, never fat gain.

---

## NOTION DATABASE SCHEMA (current backend)

Four databases, replacing the original SQLite schema. Equivalent data structure.

| Notion DB | Replaces SQLite Table | Key Properties |
|---|---|---|
| `NOTION_DB_READINESS` | `daily_readiness` | Date, Condition, Tightness (0–10), Pain (0–10), Body Areas (multi-select), Sensations (multi-select), Note, Tightness Score parsed, Stress Level (covers both stress and mental clarity), Alcohol Units, Travel. Plus (2026-07-14, `Repository.ensure_checkin_extension_columns`): Instability Events, Bristol Type, Unusual Stool Colour, Hunger Deviation, Thirst Intensity, Electrolytes Taken, Meditation Done (inferred from minutes > 0, not a UI toggle), Meditation Minutes, Relaxation Depth. Craving Type and Sodium (mg) were added then removed the same day — the Notion columns may still exist but are no longer read/written |
| `NOTION_DB_TRAINING` | `training_log` + `training_set_log` | Movement, Session Date, Session ID, Type, Planned Sets/Reps, Exercise RPE, Sets (JSON), Session RPE, Session Duration, Session AU, Notes |
| `NOTION_DB_BIOMETRICS` | `daily_biometrics` | Log Date, RHR, HRV, Sleep Hours, Deep Sleep Hours, Active kcal, Weight kg, Steps |
| `NOTION_DB_CONFIG` | Config + `diagnostic_profile` | Key/Value store — plan_start_date, current_stage, phases (JSON), training_progress (JSON), diagnostic_profile (JSON, which itself carries `injury_weight_decay_lambda` — it is not a flat Config row), latest_movement_risk (JSON), plus sync markers garmin_daily_last_synced_at / garmin_rate_limited_until |

> **Note:** The Notion Biometrics DB is no longer written to by the app —
> `Repository.save_biometrics_today` still exists but has zero callers; it is
> retained for backwards compatibility and read-only use. Google Sheets remains
> the biometric store, but **`sync_sheets.py` is gone**: its Sheet1 column
> mapping was consolidated into `Repository._sheets_biometric_records`, which now
> serves only the legacy Apple Health history and the Garmin backfill script.
> The engine's live read is `Repository.get_biometric_rolling`, a live
> Oura+Garmin blend off each platform's own Sheet tab — never Sheet1.

---

## RESPONSIVE UI SYSTEM (`styles.py`)

Two visual themes applied automatically via CSS media query at 768px breakpoint:

| Breakpoint | Theme | Palette | Typography | Components |
|---|---|---|---|---|
| ≥ 769px (desktop) | **Whoop** | Near-black `#07080D`, high-contrast white, `#00E874` green | Dense, tight, monospace labels | Compact left-bordered stat blocks, 4px radius |
| ≤ 768px (mobile) | **Oura** | Deep navy `#0B0F1E`, muted pastels — sage green, muted amber, dusty coral | Large, light-weight headings, generous spacing | Soft rounded cards (18px radius), SVG arc rings |

`inject_css()` called once per page. `dual_layout(desktop_html, mobile_html)` wraps content in `.whoop-only` / `.oura-only` divs toggled by `@media` query.

### Voice Training / Voxplot Boundary

Voxplot remains a separate Git repository, embedded in Health as the
`voice_training/voxplot` submodule. Health owns the route in `views/sync.py`;
Voxplot owns acoustic analysis, its presentation, and its independent test
suite. Health records a specific Voxplot commit rather than duplicating its
source. Voxplot's recordings, research datasets, logs, virtual environment,
and generated validation output are ignored locally and are never staged.

### Voice Training Measurement Policy (2026-07-14)

Voxplot's **Voice Quality** score remains intentionally visible as the athlete's
personal baseline/trend score. Its established `voice_quality_v1` recipe is
unchanged: equal reference-mapped AVQI-like overall index and Voxplot
breathiness estimate. The score is not a diagnosis, does not silently fall
back to one component, and is now labelled as a personal acoustic trend.

New Voxplot sessions use a versioned `de_windowed_3s_v2` capture protocol:
the user selects at least 3 seconds for each task, then Voxplot
deterministically chooses an activity-rich contiguous 3-second vowel and
speech window. It records non-audio QC/provenance (durations, activity,
level/clipping, codec/source metadata available to Streamlit, model hash,
raw/display index values, runtime/Praat/CPPS settings, and reference
cutoffs). Raw audio remains deliberately absent from JSONL and Supabase.
Legacy sessions stay readable but cannot be recalculated; when v2 data
exists, default trends compare only matching protocol/scoring versions and
usable-quality sessions. Same-day retakes now use a median with spread/count,
and local Europe/Berlin calendar dates prevent UTC/server-date distortion.

The 2020 German AVQI v03.01 paper reports a 1.85 cutoff under its own
equalised/reference implementation. Voxplot retains 2.70 only as the
existing personal-reference boundary pending reference-script parity, not as
a German diagnostic cutoff; changing it now would falsely imply calibration
and break baseline continuity. The existing CPPS `subtract trend before
smoothing=True` setting is likewise versioned but unchanged until parity
outputs exist. The 2.10 custom-breathiness threshold now has one source of
truth in the VQD-Lasso model JSON; it is not the published ABI or a
German-phone clinical cutoff.

Full rationale, implementation details, citations, and still-required
external validation are in
[`voice_training/voxplot/docs/voice_quality_measurement_policy.md`](../voice_training/voxplot/docs/voice_quality_measurement_policy.md).

### Voice Training Activity Library (2026-07-14)

At the user's request, Voxplot now has ten new activity-card entries:
Supported Voice Reset, Lip Trill Ease, Voiced /v/ Flow, Nasal Resonance
Ladder, Resonant Phrase Carryover, Small-Step Pitch Pattern, Gentle Phrase
Pacing, Easy Articulation Practice, Chant-to-Speech Bridge, and Brief Voice
Recovery Break. They reuse the existing four-step explanation/countdown/
results template; no acoustic calculation, Voice Quality score, recording
protocol, or storage behaviour changed.

Days 1-10 were **replaced, not kept**: the 2026-07-31 revision of the pinned
Voxplot submodule rebuilt them as a breath-led block, leading with breath/tension
work every day, dropping Pulmo-Train from ten days to four, and scheduling eight
of the ten cards above directly into the plan — leaving only
`small_step_pitch_pattern` and `voice_recovery_break` library-only. Day 1 is now
gated behind a daily "is your voice worse today?" readiness question. The
Training tab exposes a separate selectable library containing all **26**
activities: the 12 baseline cards, these ten, and four later breath/laryngeal
cards (`diaphragmatic_breathing_reset`, `belly_breath_phonation`,
`laryngeal_tension_release`, `breath_hold_awareness`). The 10-day plan now draws
on 19 distinct library cards; the remaining 7 are library-only.
`EXERCISE_LIBRARY` is the single catalogue
for both the library and later plan authoring, so a future plan can mix and
match its stable activity ids without duplicating definitions. `NEW_RECORDING`
remains a daily-plan capture step, not a library activity.

Library practice is explicitly isolated from the daily plan: starting or
finishing a library card uses the same explanation/countdown/results template
but does not mark an item complete, change XP, streak, history, or plan
progress, and does not auto-start the next planned activity. The library is
available on the Training tab **at all times** — before the plan has started
(beside the readiness gate), alongside each day's cards, while the next baseline
day is locked, and after Day 10 is complete.

Seven connected-speech cards now supply a stable three-sentence practice
paragraph at the exact explanation step and throughout the timer: Pulmo-Train
Reading Carryover, Twang Brightness, Resonant Phrase Carryover, Gentle Phrase
Pacing, Easy Articulation Practice, Chant-to-Speech Bridge, and Cool-Down &
Carryover Check. The paragraph is a training prompt selected by Voxplot's
analysis language (currently German), not the short versioned recording
passage; it therefore does not change capture protocol, Voice Quality scoring,
provenance, or historical comparability. Brief Voice Recovery Break stays
quiet-rest-first and retains only its optional closing sentence.

**Authoring rule:** every future Voxplot activity that requests connected
speech (words, phrases, sentences, or reading) must attach a purpose-selected
paragraph to the exact ActivityStep; the user must not have to invent text.
The activity documentation must state why the wording matches its target:
consonant-rich/tongue-twister-style text is for slow articulation precision,
natural sentences are for resonance, pacing, carryover, or breath-voice work,
and low-effort text is used only under the activity's comfort/stop conditions.
Tongue twisters raise articulatory coordination demand; they must never be
framed as a way to force vocal-fold effort, loudness, or range. Isolated
sounds, glides, and quiet-rest activities remain paragraph-free unless they
explicitly transition into connected speech.

The content intentionally reflects the patient profile it was authored under
(Stage 1 rehabilitation, an active mid-/lower-back flare, and generalised
hypermobility). New cards permit a supported chair or easy neutral standing,
avoid a held posture-correction cue and physical loading, and require a
position change or stop if back symptoms rise. Those constraints still stand
under Stage 2 — hypermobility is a standing modifier that does not get
reassessed away, and the no-held-posture-correction rule is if anything more
load-bearing now, given the 2026-07-06 strain it came from and the ongoing
desk-posture interscapular pattern. The latest Voice Training
recording was quality-limited by low sustained-vowel SNR, so this expansion
does not use its score to progress work or claim a voice change. Complete
rationale, source links, library behaviour, and stop/escalation rules are in
[`voice_training/voxplot/docs/training_activity_catalogue.md`](../voice_training/voxplot/docs/training_activity_catalogue.md).

---

## AGILE ROADMAP

| Bucket | Title | Status |
|---|---|---|
| **1** | Discovery & Dynamic Logic Blueprint | COMPLETE ✅ |
| **2** | Local Database Schema & Initialization | COMPLETE ✅ (migrated to Notion) |
| **3** | Data Input Engine — Morning Check-In, Biometrics, Training | COMPLETE ✅ |
| **4** | Autoregulation & ACWR Mathematical Engine | COMPLETE ✅ |
| **5** | AI Text / MRI Parsing & Macro Trend Analysis | COMPLETE ✅ (Phase 1 deterministic + Phase 2 AI layer) |
| **6** | Interactive Training Plan (Stage 1 Rehab — authored as 14 days, ran to 21) | COMPLETE ✅ |
| **7** | Google Sheets Biometric Auto-Sync | COMPLETE ✅ |
| **8** | Responsive UI System (Oura/Whoop dual-theme) | COMPLETE ✅ |
| **9** | Clinical Input Profile System (`patient_profile.py`) | COMPLETE ✅ |
| **10** | Autoregulation → Background; Directive into Training Plan | COMPLETE ✅ |
| **11** | Biomechanical Profile Integration into Training Plan | COMPLETE ✅ |
| **12** | 4-Week Stage 2 Transition Plan | COMPLETE ✅ — `training_plan.PLAN_STAGE2`, built after the Day 21 (not Day 14) assessment; running deliberately excluded |
| **13** | Apple Health Direct API Sync | SUPERSEDED — replaced by the Oura+Garmin blend (2026-07-13) rather than a direct Apple HealthKit sync; Sheet1/Apple Health retired from the live pipeline instead |
| **14** | Stage 2 Training Entry (barbell/cable — external load) | COMPLETE ✅ — live since 2026-07-20; weighted sets logged across all three body regions |
| **15** | Stage 2B / next block | PENDING — three decisions due at the Day 28 reassessment (2026-08-16): Stage 2B vs. extending 2A, running introduction, endurance-biased scapular programming. See `docs/focus.md`. |
| **16** | Strength metric — capacity and volume, separated | COMPLETE ✅ (2026-08-04) — `services/strength.py` (Overall Strength Score: estimated 1RM vs the 2025 baselines in `strength_baselines.py`, currently in calibration at 50) and `services/tonnage.py` (weekly kg by body sector). They share no term, so a heavier week cannot raise the score and a rest week cannot lower it. Replaced the Stage-Adjusted Recovery Score, which was deleted — it could only ever read 100 |
| **17** | Metabolism BioAge screen | COMPLETE ✅ (2026-08-05) — `services/body_composition.py`, `body_composition_baselines.py`, `views/insights.py::_render_metabolism_detail`. Two devices in separate lanes, the InBody's typed-height defect corrected rather than dismissed, and the two height-immune readings (phase angle, ECW/TBW) surfaced above the derived cards. Display-only; see BODY COMPOSITION above for the locked decisions and the two refusals |
| **18** | Body-composition accuracy layer | DEFERRED to 2027 (user decision, 2026-08-05) — revisit once a year of standardised readings exists. The design is recorded: weigh 4–5×/week under fixed conditions (protocol standardisation is worth 24% at zero extra weigh-ins, against 33% for tripling frequency), a monthly tape baseline as the one fat signal independent of impedance, and the training log as a **consistency gate** rather than an input. The bridge scan is the only time-limited piece — see below |
| **19** | Flexibility — Cluster A | **BUILT, UNMEASURED** (2026-08-06) — three layers with a one-directional dependency made executable by four guard tests: `cluster_a_mechanics.py` (why), `services/battery.py` + `cluster_a_battery.py` (how to test), `cluster_a_prescription.py` (what to do), joined by `services/flexibility.py`. **Two earlier models were built and deleted** — v1's `sqrt(RANGE × CONTROL)` and v2's `min(rungs)`; the battery is a decision tree with early exit and neither scoring function could be tuned into it. Output is one pattern label and nothing else. Zero assessments run. Display-only |
| **20** | Flexibility as a standing training goal | PENDING — ranked *below* the 10 km on 2026-10-11 by the athlete (2026-08-05). Blocked on nothing but running the first assessment, which should happen **before 2026-08-16** so a pattern label reaches the physiotherapist rather than a plan to get one |

---

## KEYWORD LIBRARY — DETERMINISTIC PARSER (Phase 1 Reference)

### Sensation Tags — `services/ai.py` `_SENSATION_MAP`

Substring match. `extract_sensation_types` returns EVERY tag whose keyword
appears in the text, ordered by the map (neural first) — it is a list, not a
single winner. There is **no per-tag severity weight**; severity is a separate
table (below).

| Keyword(s) | `sensation_type` |
|---|---|
| pins and needles, shooting pain, shooting, radiating, radiate, electric, numbness, numb, tingling, burning, sciatica, down my leg / down the leg, into my foot / into the foot, weakness, weak leg | neural |
| very sharp, sharp | sharp |
| very tightened, very tight, tightened, tight | tight |
| stiff | stiff |
| dull ache, aching, throbbing, sore, ache, dull | dull_ache |
| exhausted, fatigued, fatigue, heavy legs, heavy, tired | fatigue |
| feels normal, normal, comfortable, fine, good | normal |

**Severity is separate** — a keyword → 0-10 table (`_SEVERITY_TABLE`), and
`infer_severity` scans the whole table and returns the HIGHEST match as a float
(worst-case clinical conservatism): excruciating 10 · unbearable/agonising/agony 9 ·
very sharp/severe 8 · very tight/very tightened/sharp/intense/radiating 7 ·
significant 6 · persistent/constant/moderate 5 · dull ache/aching/ache/sore/tight/tightened 4 ·
stiff/uncomfortable 3 · slightly tight/slightly tired/mild tiredness/mild/slight/slightly 2 ·
minimal/barely 1 · no pain/pain free/pain-free/no tightness/feels normal/feels good/
feeling good/all good/normal/fine/good 0.

The check-in picker offers a third, different list — `training_constants.SENSATION_TAGS`:
Normal, Tight, Stiff, Dull Ache, Sharp, Neural, Mild Tiredness, Very Tight, Slightly Tired.

### Anatomical Location Tags — `services/ai.py` `_BODY_PART_MAP`

The parser emits **20 canonical Title Case, laterality-qualified strings** — not
snake_case tags. Phrases match in list order, laterality-qualified before
generic, so "right glute" resolves before "glute". Note the emitted strings use
an ASCII double hyphen (`--`) whereas the check-in picker's
`training_constants.ANATOMICAL_LOCATIONS` spells the same regions with an em
dash: only `Central Lower Back` and `Thoracic / Mid Back` are byte-identical
across the two, so never compare parser output to the picker list directly.

| Keyword(s) (laterality-qualified matched first) | Emitted location |
|---|---|
| right l5, l5/s1 right, l5 right, right side l5, l5/s1, l5-s1, l5 s1, s1 junction, lumbosacral junction, l5 | Lumbar -- L5/S1 (Right -- Primary) |
| left l5, l5/s1 left, l5 left, left side l5 | Lumbar -- L5/S1 (Left) |
| l4/l5, l4-l5, l4 l5, l4 | Lumbar -- L4/L5 (Left) |
| l3/l4, l3-l4, l3 l4, l3 | Lumbar -- L3/L4 (Left) |
| lower back, low back, lumbar, lumbosacral, l-spine | Central Lower Back |
| right hip flexor, right psoas, right iliopsoas | Hip Flexor / Psoas -- Right |
| left hip flexor / psoas / iliopsoas, hip flexor, psoas, iliopsoas | Hip Flexor / Psoas -- Left |
| right sacroiliac, right si joint, right si | Sacroiliac Joint -- Right |
| left sacroiliac / si joint / si, sacroiliac, si joint, sij | Sacroiliac Joint -- Left |
| right glute medius, right glute med | Glute Medius -- Right |
| left glute medius / glute med, glute medius, glute med | Glute Medius -- Left |
| right glute, right buttock | Glute -- Right |
| left glute / buttock, glute, gluteus, buttock | Glute -- Left |
| right piriformis | Piriformis -- Right |
| left piriformis, piriformis | Piriformis -- Left |
| right hamstring | Hamstring -- Right |
| left hamstring, hamstring | Hamstring -- Left |
| right calf, right gastrocnemius, right soleus | Calf -- Right |
| left calf / gastrocnemius / soleus, calf, gastrocnemius, soleus | Calf -- Left |
| mid back, midback, middle back, thoracic, t-spine, upper back, between shoulder | Thoracic / Mid Back |

`ANATOMICAL_LOCATIONS` additionally offers Upper Back — General / Rhomboids /
Trapezius and Other in the check-in picker; the parser never emits those. There
is **no** neck/cervical, upper-glute/TFL/hip-crest, or generic right-side /
left-side location, and "disc", "deep hip", "achilles", "ankle", "sit bone",
"ischial" and "groin" are not keywords. ("right side", "right leg", "right hip"
appear only in `_MRI_INJURY_KEYWORDS`, which drives `correlates_with_injury`,
not location tagging.)

### Neural / urgent trigger terms — `services/stats.py`, applied at EVERY stage

`auto_warning_level(text)` takes **no stage argument**, so this runs on every
check-in and session note regardless of stage — it is not a Stage 3 feature.
Urgent is tested first, but both lists resolve to the same warning level `"flag"`.

`NEURAL_KEYWORDS` (20 terms): `shooting`, `radiating`, `radiate`, `electric`,
`numb`, `numbness`, `tingling`, `pins and needles`, `weakness`, `weak leg`,
`foot drop`, `dead leg`, `burning down`, `sciatica`, `sciatic`, `nerve pain`,
`down my leg`, `down the leg`, `into my foot`, `into the foot`

`URGENT_KEYWORDS` (11 terms, cauda equina red flags, checked first): `bowel`,
`bladder`, `incontinence`, `saddle numbness`, `saddle anaesthesia`, `can't walk`,
`cannot walk`, `loss of sensation`, `paralysis`, `paralysed`, `cauda equina`

Injury-correlation terms — `services/ai.py` `_MRI_INJURY_KEYWORDS` (15 terms),
matched against the canonical body-part labels returned by `extract_body_parts`,
not against raw text, to set `correlates_with_injury`: `l5`, `s1`, `l4`, `l3`,
`lower back`, `lumbar`, `hip flexor`, `psoas`, `glute`, `sacroiliac`, `si joint`,
`right side`, `right leg`, `right hip`, `right back`

Stage 3's "passive background watcher" (`rules.STAGE_CONSTRAINTS[3]["description"]`)
is a label on the stage, not a separate term list — no such list exists in code.

---

## RULES FOR FUTURE DEVELOPMENT

1. **Read `resume.md` and `patient_profile.py`** before writing any new code. Architecture decisions here are locked. Do not re-litigate them.

2. **Deterministic first, always.** No AI component is to be added to any new feature until the deterministic equivalent is written, tested, and confirmed working.

3. **AI never touches safety outputs.** Traffic Light multiplier, ACWR ratio, stage transitions, and final prescribed volume are always deterministic. Period.

4. **No new dependency without justification.** State what it replaces and why the existing stack cannot handle it. Pin to exact version in `requirements.txt`.

5. **Notion is the write backend; Oura + Garmin (blended) is the biometric read source.** Do not add manual biometric entry anywhere in the app. The pipeline is: Oura + Garmin APIs → their own Google Sheets tabs (`sync_oura_all` / `sync_garmin_daily_if_due`) → `services/biometrics.py`'s blend → `get_biometric_rolling` → engine. Sheet1/Apple Health is retired to historical-only. **`sync_sheets.py` no longer exists** — its Sheets primitives became `services/clients/sheets.py` and its column mappings became `services/repository.py`. The one sanctioned exception to "no manual entry" is the per-night wake-time correction (`get_wake_time_adjustment`/`set_wake_time_adjustment`), which is stored separately and never overwrites the raw reading.

6. **Autoregulation is background.** The engine directive reaches the Training Plan as plain language, and a small fixed set of engine numbers rides along with it there: the injury-weight % embedded in the CONSERVATIVE LOAD directive text, the ACWR advisory caption (shown while `ACWR_ADVISORY_MODE` is set, and also whenever the stage baseline is still establishing), and the readiness-modifier badge. Everything else — HRV/RHR deltas, ACWR acute/chronic averages, traffic-light data days, the raw injury-weight decay — stays in Insights → Engine Data. "No numbers in Training Plan" is the intent, not a literal invariant.

7. **Training sessions are logged automatically by the Training Plan.** No manual training entry page. Do not re-add one.

8. **The pre-session release protocol must precede every training session.** The biomechanical profile mandates inhibiting overactive structures (glute medius, piriformis) before activating underactive ones (glute max, deep core). Any new training block must preserve this sequencing.

9. **Right-side asymmetry is a clinical finding, not a preference.** All exercises involving right hip flexion >60° require a neutral/internal rotation cue. All right posterior hip capsule mobilisation is unilateral (right only). Document this wherever it appears.

10. **`patient_profile.py` is updated before each new training block.** After each block's reassessment, update findings, imbalances and stage exit criteria — and append a `stage_transitions` record, which is the evidence the criteria were actually met rather than merely stated — before generating the next plan. Note the file is now live input as well as human reference — `views/insights.py` reads `PROFILE["imbalances"]` and passes it to `bioage.muscle_imbalance_count`, and `tests/test_bioage.py` pins the count at 8 — so edits to `imbalances` can break the gate. `services/bioage.py` itself imports nothing; it takes the dict as a parameter, which is what keeps `services/` free of I/O.

11. **Every new function needs a one-line comment** stating whether it is `DETERMINISTIC` or `AI-LAYER` and what its fallback is if it fails.

12. **The keyword library above is the living document** for the deterministic parser. Update it in this file whenever new terms are added to the code.

13. **Bottom nav (Home / Training / Insights / Voice Training) must be present and functional on every page at all times.** The fourth item's route key is still `"sync"` (`nav.py`'s `_ITEMS`), which is why `app.py` dispatches it to `views/sync.py` — but that route is the embedded Voxplot Voice Training page; device-sync controls live in the Insights → Sync tab, not on the nav. `nav.inject(active)` must be called on every route in `app.py`. The call must come *after* all page content is rendered, because the nav is real `st.button()` widgets in document order — inject early and they appear above the cards. The FAB (+) for Check-In does **not** go through the nav at all: it is a plain `<a href="?page=checkin">`, the only real link in the app, which is precisely why `app.py` mirrors the resolved page back into `?page=X` (a reload after using the FAB would otherwise land back on Check-In). Do not remove or reorder `nav.inject()` without testing both the bottom bar and the FAB.

---

## OPEN DECISIONS / KNOWN GAPS

| Item | Status | Notes |
|---|---|---|
| HRV data from Sheet1/Apple Health | Often blank (historical only) | No longer the engine's source — see Oura+Garmin blend above. Still true of the retired pipeline for backfill purposes |
| Garmin HRV field mapping | RESOLVED-as-empty (2026-07-31) | `get_hrv_data` returns `{}` for this account, so `hrvSummary.lastNightAvg` has nothing to map. Separately, the Garmin Daily tab predated `hrv_ms` joining its header and silently discarded the column — repaired via `Repository.rebuild_garmin_daily`. The blend is held at Oura-only on purpose (`biometrics.HRV_GARMIN_HOLD`) |
| Notion biometrics DB | No longer written to | Could be removed in future; kept for backwards compat |
| Stage 2 training plan | BUILT — live since 2026-07-20 | `training_plan.PLAN_STAGE2`. Barbell/cable library, ACWR ceiling 1.3 from `STAGE_CONSTRAINTS[2]`, per-set external-load capture all in place. Next block's decisions are due 2026-08-16 — see `docs/focus.md` |
| Garmin backfill from Sheet1 | Needs to be run once | `scripts/backfill_garmin_from_sheet1.py` — dry-run first, then `--apply` — so readiness baselines have pre-wearable history in the Garmin Daily tab |
| `Training plan/` folder | RESOLVED (2026-08-03) | Directory no longer exists at root; contents live in `docs/training/` |
| `patient_profile.py` not imported | SUPERSEDED | No longer true — `views/insights.py` reads `PROFILE["imbalances"]` and passes it to `bioage.muscle_imbalance_count`, and `tests/test_bioage.py` pins the result at 8. (`services/bioage.py` itself imports nothing — it takes the dict as a parameter, which is what keeps `services/` free of I/O.) The file is now both human reference **and** live input, so edits to `imbalances` can break the gate |
| Overall Strength Score is calibrating | Expected, not a gap | Every regional index displays at 50 and the overall is held at `strength_baselines.ANCHOR_VALUE`. Exit is per region on confidence ≥ 0.70 (`quantity × comparability × consistency`); today upper 0.46, lower 0.37, **core 0.00**. Core cannot be calibrated at all until a repeatable core measurement is logged — its only loaded movement is Pallof Press and its 2025 peak is recorded as a band, not a kilogram |
| No per-set warm-up flag | Open | `services/tonnage.py` counts a set as eligible when it carries reps AND a real external load. Warm-ups are not excluded because the log cannot mark one, so "working sets only" is an assumption the data does not support. A boolean per set closes it |
| Interscapular endurance gap | Deferred to the post-Stage-2A block | Onset 2026-07-16, predates the block. Scapular work already runs five days a week and the symptom persists through it, so the gap is endurance under sustained low-load holding, not volume. Physio decides 2026-08-16 — `docs/training/physio_brief_2026-08-16.md` |
| Flexibility: zero assessments run | Open — the only thing between this sector and usefulness | The four-slot battery is built, its early exit is verified end to end, and nothing has been measured. **Measure COLD.** Every threshold is provisional until three baseline mornings exist, and a pattern from one session is a hypothesis rather than a verdict — `BatteryResult.trusted` says so and the screen renders it |
| Frozen constants: two of four now captured in-flow | Half-resolved 2026-08-07 | Straddle width (at the tilt) and the tailor's heel distance (at the bent-knee leverage) are recorded beside the reading as `Reading.setup_value`, and the screen offers last session's number back. Still uncaptured: the traced side-split stance and the floor reference. `block_height_cm` is deliberately NOT frozen — it is the §F progression variable and is meant to move |
| Rest-day yoga vs. the adaptation window | **RESOLVED 2026-08-06** | The Prescription's dosage section settles it: a cluster session is adaptation-seeking by definition, so `flexibility_window` now returns `poor` on a rest day rather than ignoring the flag, and `REST_DAY_CONFLICT_UNRESOLVED` is retired. A restorative yoga flow there is still fine — `services/yoga.py`'s business, not this one's |
| Every Cluster A threshold is provisional | Open | `GATE0_ORIENTATION_GAIN_CM`, `LEVERAGE_TARGETS`, `TILT_TARGET_DEG` and `SPECTRUM_GAP_CM` all come from the source document (or were invented to make the code run) rather than from this athlete's own spread, which has never been measured. Three baseline mornings set the noise floor; until then no single reading is a reason to change anything. `GATE0_BONE_RELEVANT_CM` (15) is the athlete's own call about mechanism, not a borrowed cut point |

---

*Last updated: 2026-08-06 (second pass) — the FLEXIBILITY section was rewritten
AGAIN, for the third model in two days, and the churn itself is the thing worth
recording. v1 scored `sqrt(RANGE × CONTROL)` across eight regions; v2 scored
`min(rungs)` across fourteen rungs under eight skills; v3 runs four slots in
order and stops at the first failure, emitting a pattern label and nothing else.
Only v3 matches the source method, and the reason the first two did not is
structural rather than a matter of tuning: a battery is a decision tree with
early exit, and a scoring function computes over everything. A failing slot 0
does not make the rest lower priority, it makes them unanswerable. Both earlier
models are deleted, and `tests/test_cluster_a.py` fails if any of their eleven
named symbols reappear. The section now leads with why they died, because that
reasoning is the most reusable thing three attempts produced. Also corrected
here: roadmap 19 and 20 rewritten for the cluster model, three open-gap rows
replaced (zero assessments rather than "0 of 14 rungs", four frozen constants
rather than three, and the rest-day conflict marked RESOLVED — the Prescription's
dosage section answered a question this file had recorded as open). Before that,
earlier the same day — the FLEXIBILITY section was **rewritten from scratch**
for v2. The v1 text this replaced was not merely stale, it documented a model the
athlete had refuted and the code had deleted: `sqrt(RANGE × CONTROL)` averaged
across eight regions, the two-sided `CONTROL_BAND` where a depth rating of 88
scored 46, and "currently 80/100 on 44% of the evidence" — a headline number the
current code cannot produce, since `ASSESSMENTS` is empty and nothing is
averaged. A session reading the old section would have rebuilt the defect. The
new section leads with **why v1 died**, because that reasoning is the most
reusable thing the sector produced. Also corrected here: the Insights row still
called Flexibility and Metabolism "coming soon" when both are built (only Cardio
is); roadmap buckets 19 and 20 opened; four open-gap rows added (0 of 14 rungs
measured, three uncaptured frozen constants, the deferred rest-day `intent`
field, and two provisional constants). One count was wrong in the source as well
as the docs — six rung tests carry `replaces`, not four, and
`flexibility_baselines.py`'s own docstring said four. Before that: 2026-08-04 —
third and final audit sweep, 63 findings across six
section auditors each adversarially verified, covering the whole file rather than
one section. Corrected, in code order: the traffic light evaluates a FOURTH metric
(body-temperature deviation, absolute cut points, not a baseline ratio) and
applies the `baseline_drift` guard; green's multiplier is **1.0×, not 1.05×** —
the light itself never overloads, `volume_recommendation` does, and only under
three further conditions; ACWR's chronic term is stage-scoped and content-weighted,
not a flat 28-day mean of raw AU; the ACWR hard lock is **currently unreachable**
because `ACWR_ADVISORY_MODE` is on; the lag-correlation fallback is a 9-pair
matrix in which HRV is only ever a target, so the documented "HRV drop → pain 48h
later" pair does not exist. Clinically: the Biomechanical Profile listed **5
findings when `patient_profile.py` holds 6** — the missing one is the right
shoulder instability (three dislocations, a failed capsular repair, then a
Latarjet), which is why scapular control is a standing requirement and why there
is no overhead press in Stage 2A; and the pre-session release protocol omitted
the Ischial Tuberosity Hamstring Release. The Stage 1 plan section was headed
"14-DAY" and stopped at Week 2, when `PLAN` is 21 days with a Week 3 flare-recovery
block; the day number comes from the active phase's `start_date` and its
`date_overrides` (which is how the readiness auto-shift moves a day), not from
`plan_start_date`; the Exit Training button was placed "in sidebar" when the app
has no sidebar at all; and the completion form was said to take a duration input
when duration is auto-timed and read-only. Pipeline figures: `sync_oura_all` runs
at `days=7` not 2, and the blend persists every 2h, not once a day. The entire
KEYWORD LIBRARY section was fiction — a "Severity Weight" column that exists
nowhere, snake_case location tags that no code emits (the parser emits 20
Title Case laterality-qualified strings), and a "Background Watcher Trigger Terms
(Stage 3)" list that is neither stage-gated nor a real list. Voxplot: days 1-10
were rebuilt, not kept, the library holds 26 activities not 22, and it is
available at all times. Before that, the second sweep over the
"CURRENT APPLICATION STRUCTURE" section, which had drifted furthest. Five
unhedged rows described code that no longer exists: navigation was called "a JS
bridge (`nav.py`)" exposing `stNav(page)` when `nav.py` contains no JavaScript at
all (four `st.button()` widgets — `stNav(` appears in zero `.py` files repo-wide,
and the FAB is a plain `<a href>`, not the same bridge); Home was said to render
ACWR, the traffic light and the session directive, all three of which are in
Insights → Engine Data and return zero hits in `app.py`; the training runner was
"14-day" when `PLAN` is 21 days and `PLAN_STAGE2` is 28 and the runner is
phase-driven; the Insights row named four tabs including "MRI intelligence",
deleted 2026-07-14 in `f386121` — there are six; and the biometrics row claimed a
70/30 HRV blend that `HRV_GARMIN_HOLD` has always bypassed (also corrected in the
pipeline diagram and the Blend Mapping table, which repeated it). Three of the
five contradicted other lines in this same file. Before that, the same day — the Core Modules table
still listed `db.py` and `sync_sheets.py`, neither of which exists (both became
`services/repository.py` during the services/ extraction), gave readiness's
retired v1 weights (HRV 40 / Sleep 35 / RHR 25) rather than `MODEL_VERSION 2`'s
nine Oura-contributor weights, described `patient_profile.py` as "not imported by
active code" when `views/insights.py` reads it, and omitted ten services/ modules
including `strength.py`, `tonnage.py`, `biometrics.py` and `background_sync.py`.
The scripts/ row listed one of nine tools. Roadmap bucket 16 opened and closed for
the strength/tonnage split; two open-gap rows added for the calibration state and
the missing warm-up flag. Before that (2026-08-03) — documentation refresh: the stage machine, agile roadmap and open-gaps table had all still described Stage 1 as current, five weeks after Stage 2A started (2026-07-20). Stage 1 is marked complete with its 7-day extension recorded, Stage 2 marked current with the active block named, roadmap buckets 12/14 closed and a bucket 15 opened for the three decisions due at the Day 28 reassessment (2026-08-16). Four open-gap rows corrected against reality: `patient_profile.py` IS now imported (`services/bioage.py`), the `Training plan/` duplicate is gone, Garmin HRV is resolved-as-empty and held at Oura-only, and the Stage 2 plan is built. Before that (2026-07-14): the Voxplot Voice Training Measurement Policy, separate 22-card activity library, and supplied connected-speech paragraph; the original 10-day baseline remains fixed, and optional library practice cannot change daily-plan progress. Sheet1/Apple Health remains retired as the engine's biometric source; the live health blend is Oura+Garmin (`services/biometrics.py`).*
