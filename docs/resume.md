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
| **Biometrics source** | Manual Apple Health entry on Autoregulation page | Blended Oura + Garmin read (`services/biometrics.py`) — Oura 70%/Garmin 30% for HRV/RHR/sleep, Garmin 80%/Oura 20% for steps | Apple Health auto-export (Sheet1) proved unreliable; Oura/Garmin were already integrated archivally, so the engine now reads a weighted blend of both instead. Sheet1 is historical-only (one-time backfill source) |
| **Training entry** | Manual session logging via Training Entry page | Auto-logged by Training Plan on session completion | Training Entry page removed; logging is triggered by completing a guided day |

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

`app.py` is the single Streamlit entry point. Navigation is handled by a JS bridge (`nav.py`) that sets `st.session_state["_nav_page"]`; the router in `app.py` dispatches to the appropriate view. `_pages/` was removed — Streamlit 1.36+ auto-detects that directory as a multi-page app and renders an unwanted top-nav bar. All routing is handled by the `st.session_state["_nav_page"]` state machine in `app.py`; no `_pages/` stubs are needed.

| View module | Page | Purpose |
|---|---|---|
| `app.py` (home route) | Home | Dashboard: readiness summary, ACWR, traffic light, session directive |
| `views/checkin.py` | Morning Check-In | Daily readiness entry: pain score, tightness, sensation tags, lifestyle factors |
| `views/training.py` | Training Plan | 14-day interactive rehab session guide with live timers, auto-logging, exit confirmation |
| `views/insights.py` | AI Insights | Engine data tab (ACWR, biometrics, injury weight) + parser queue + tightness map + macro trends + MRI intelligence |
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
| `db.py` | Notion API backend — all read/write. Equivalent to the SQLite schema below but using Notion databases. |
| `sync_sheets.py` | Google Sheets direct reader — pulls biometric rows, maps columns, returns engine-compatible format. No Notion sync needed. |
| `training_plan.py` | 14-day exercise prescription data — exercise specs, mechanics, biomechanical cues, progressions, regressions, pre-session release protocol integrated per day. |
| `training_constants.py` | Single source for `EXERCISES` catalogue, `ANATOMICAL_LOCATIONS`, `SENSATION_TAGS`. Imported by `views/checkin.py`. |
| `patient_profile.py` | Clinical input file — MRI findings + biomechanical assessment + muscle imbalance summary. Not imported by active code; human reference. Updated before each new training block. |
| `readiness.py` | Readiness score calculator — HRV 40% / Sleep 35% / RHR 25%; adaptive baselines; `NOT_COMPUTED` sentinel. |
| `stats.py` | Deterministic statistical analysis — lag correlations, slopes, recovery direction. |
| `styles.py` | Responsive dual-theme CSS + component helpers. Oura palette (mobile ≤768px) / Whoop palette (desktop ≥769px). |
| `nav.py` | Bottom nav bar + JS bridge. Exposes `stNav(page)` in parent window; navigation is URL-based (`?page=X`). No hidden trigger buttons. |
| `ai.py` | Phase 2 AI layer — session note parser, tightness parser, macro trend analysis. Advisory only. `MODEL_FAST = MODEL_SMART = "rules-based"` (no LLM called). |

### Supporting Directories

| Directory | Contents |
|---|---|
| `views/` | `checkin.py`, `training.py`, `insights.py`, `sync.py` — SPA view modules |
| `_pages/` | **Deleted** — triggered Streamlit 1.36+ auto top-nav; all routing is in `app.py` SPA router |
| `scripts/` | `init_notion.py` — one-shot CLI setup for Notion databases |
| `legacy/` | `init_db.py` + `schema.sql` — SQLite era, not used at runtime |
| `docs/` | `INVENTORY.md`, `resume.md`, `focus.md`, `playbook.md`, `progress.json`, `training/*.md` |
| `voice_training/voxplot` | Git submodule — standalone Voxplot voice-analysis source; Health pins its commit and embeds its renderer |

---

## LOGIC SEPARATION

### A. Strict Deterministic Engine (`engine.py`)

**Traffic Light Biometric Autoregulation**

Evaluates HRV, RHR, Sleep against 28-day rolling baseline:

| Signal | Condition | Volume Multiplier | User-Facing Message |
|---|---|---|---|
| Green | Biometrics at or above baseline | 1.05× (overload) | Nothing shown — train normally |
| Yellow | Drop within 10–25% | 0.75× | "Reduced load today — keep session controlled" |
| Red | Drop >25% | 0.0× | "Rest day — mobility and walking only" |
| Grey | Insufficient data (<7 days) | 1.0× | Nothing shown |

**Directive delivery:** The directive surfaces as a plain-language banner at the top of the Training Plan page. Numeric data (ACWR, HRV delta, injury weight %) is never shown in Training Plan — only in AI Insights.

**Acute-to-Chronic Workload Ratio (ACWR)**
```
ACWR = 7-day avg session AU / 28-day avg session AU
Session AU = Session-RPE × Duration (minutes)   [Foster method]
```
Stage 1 ACWR ceiling: 1.2. Stage 2: 1.3. Hard-lock triggers if exceeded.

**Injury Weight Decay**
$$\text{Injury Weight} = e^{-\lambda t}$$
λ = 0.05 (default, reviewed every 14 days). t = pain-free days.
- >70%: Conservative load even on green biometric days
- 20–70%: Standard stage constraints apply
- <20%: Background watcher only

**Volume Recommendation Cascade (priority order)**
1. Observation mode (< 14 days biometric data) → hold at comfortable effort
2. Red traffic light → rest/mobility only
3. ACWR hard lock → cap at 75% volume
4. Yellow traffic light → 75% volume
5. Injury weight > 70% (green bio) → 85% volume (conservative)
6. All clear → 105% volume (progressive overload)

---

### B. Probabilistic Engine (`ai.py` — Phase 2, advisory only)

| Component | What it does | Deterministic fallback |
|---|---|---|
| Session note parser | Extracts body parts, sentiment, warning level from free-text | Keyword-to-tag matcher (see library below) |
| Tightness parser | Converts subjective tightness text to severity + body parts | Keyword severity weights |
| Macro trend analysis | Interprets lag correlations across 90-day dataset | Fixed lag-correlation (HRV drop → pain score 48h later) |
| Movement risk assessment | Maps MRI findings + recent session notes to movement flags | Pre-populated movement contraindication list in `rules.py` |

---

## STAGE STATE MACHINE

Evaluated at Day 14 and every 14 days thereafter. **All transition logic is deterministic.**

### Stage 1 — Rehab (Tissue Tolerance Focus) ← CURRENT
- Conservative ACWR ceiling: 1.2
- High injury weight influence (starts at 100%, decays with pain-free days)
- Bodyweight only — no external load
- Session RPE ceiling: 7/10

### Stage 2 — Transition (Work Capacity Focus) ← NEXT BLOCK
- Specific rehab movements blend into standard training warm-ups
- ACWR ceiling: 1.3
- External load introduced (barbell, cable)
- 4-week block — reassess after completion
- Progressive overload prescription: +2.5 kg per session (vs +1 rep in Stage 1)

### Stage 3 — Performance & Growth
- Injury weight < 20% → becomes silent background watcher
- Full progressive overload protocols
- Background Watcher re-activates on any session note matching trigger terms

**Stage 1 → 2 transition criteria (all must be met):**

| Criterion | Threshold |
|---|---|
| Pain-free streak | ≥ 14 consecutive days |
| Average 14-day tightness | ≤ 3.0 / 10 |
| McGill Big 3 | Performed pain-free with good form (Day 14 screen) |
| Hip hinge full range | Pain ≤ 2/10 at arms-past-knees range |
| Physiotherapist sign-off | Required |

---

## CLINICAL INPUT — `patient_profile.py`

Updated before each new training block. Single source of truth for MRI findings and biomechanical assessment. **Not a UI page** — it is code that the training plan reads.

### MRI (10.11.2025, DIE RADIOLOGIE Munich)

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

### Biomechanical Profile (5 Assessed Findings)

| # | Finding | Structures | Training Implication |
|---|---|---|---|
| 1 | Upper glute / hip crest chronic tightness | Glute medius (upper fibres), piriformis | Must INHIBIT before activating — release first, strengthen second |
| 2 | Standing hinge crack — right sit-bone area | RIGHT posterior hip capsule, proximal hamstring tendon at ischial tuberosity | Right posterior capsule needs direct mobilisation; ischial desensitisation required |
| 3 | Sitting forward-bend releases | Thoracic facets T6–T10, horizontal lumbar facets at L5/S1 | Thoracic extension work + thread-the-needle; posterior pelvic tilt for lumbar base |
| 4 | 90° hip click RIGHT side only (painless) | Iliopsoas tendon over iliopectineal eminence | All right hip flexion cues: NEUTRAL or slight INTERNAL rotation — external rotation triggers snap |
| 5 | Wide-stance windmill cracks | Anterior hip capsule, pubic symphysis, lumbar facet joints (rotation) | Lateral lunge, 90/90 flow, Pallof press address these — introduce wide stance slowly |

**Primary imbalance:** Under-firing glute max + deep core → upper glutes/hip flexors over-grip for artificial stability → compressed joints + snapping tendons.

**Pre-session release protocol (runs at START of every session, ~5 min):**
1. Upper Glute/TFL Self-Release — wall pressure, 2 × 90s each side
2. Piriformis Contract-Relax (PNF) — 3 × 5 cycles each side
3. *(Hip-focused sessions add)* Right Posterior Hip Capsule Cross-Body Stretch — 3 × 60s right only
4. *(Right hip loaded)* Right Hip Tendon Path Drill (Coxa Saltans) — 2 × 10 reps right only

---

## 14-DAY TRAINING PLAN (Stage 1)

### Structure
- Hardcoded bodyweight prescription in `training_plan.py`
- Interactive session guide in `views/training.py`
- Day determined automatically from plan start date stored in Notion Config DB
- Session completion auto-logs all exercises to Notion Training DB

### Session Features
- Exercise-by-exercise guided flow — one exercise shown at a time
- Live countdown timers: hold timer (isometric), rest timer (auto-starts after set complete), duration timer (walking, breathing)
- Timer state persisted to browser `localStorage` — navigating away and returning resumes mid-timer
- Session state persisted in `st.session_state` — navigate to any other page and return exactly where you left off
- Exit Training button in sidebar (only visible when session is active) — requires confirmation before discarding progress
- Rest timer auto-starts on entering rest phase; no Skip button (Next Set serves that function)
- On completion: RPE slider + duration input + session notes → auto-logged to Notion

### Week 1 Focus: Neural Reset (Days 1–7)
Daily pre-session biomechanical release block → tissue tolerance, neural desensitisation, psoas inhibition, McGill protocol introduction, gluteal activation foundation, thoracic mobility, walking baseline

### Week 2 Focus: Neuromuscular Loading (Days 8–14)
McGill protocol progression, functional hip hinge (RDL), single-leg stability, isometric endurance, functional integration (sit-to-stand, step-ups, plank), Day 14 stage readiness assessment

---

## BIOMETRICS PIPELINE

As of 2026-07-13, the engine's live biometric source is a blended Oura+Garmin
read — Sheet1/Apple Health auto-export was retired from the live pipeline
(unreliable auto-export) and is now historical-only.

```
Oura API (official)                    Garmin Connect (unofficial)
        ↓  sync_oura_all(days=2)               ↓  sync_garmin_daily_if_due(days=2)
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
                            ↓  [Oura 70%/Garmin 30% for HRV/RHR/sleep;
                            ↓   Garmin 80%/Oura 20% for steps; renormalizes
                            ↓   to 100% of whichever source is present if
                            ↓   the other is missing that day]
                  engine.traffic_light(biometric_rows)
                            ↓
      Directive → Training Plan banner (plain language)
      Full data + sources_missing flags → AI Insights → Engine Data tab

         Repository.sync_biometric_blend(days, today)   [same blend fn]
                            ↓  [once/day, app.py; also on-demand full-
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
next sync runs with (7 days for the daily auto-sync). This is what makes
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
| `hrv_ms` | Sleep Periods tab, main sleep period `average_hrv` | Daily tab `hrv_ms` (from `get_hrv_data`) | Oura 70% / Garmin 30% |
| `resting_heart_rate` | Sleep Periods tab, main sleep period `lowest_heart_rate` | Daily tab `resting_hr` | Oura 70% / Garmin 30% |
| `sleep_duration_hours` | Sleep Periods tab, main sleep period `total_sleep_duration` ÷ 3600 | Daily tab `sleep_hours` | Oura 70% / Garmin 30% |
| `steps` | Daily tab `steps` (from `daily_activity`) | Daily tab `steps` | Garmin 80% / Oura 20% |

`weight_kg`, `active_kcal`, `sleep_deep_hours` are out of scope for the blend
(nothing in `engine.py`/`stats.py`/`insights.py` reads them) and are `None`
on blended records.

---

## NOTION DATABASE SCHEMA (current backend)

Four databases, replacing the original SQLite schema. Equivalent data structure.

| Notion DB | Replaces SQLite Table | Key Properties |
|---|---|---|
| `NOTION_DB_READINESS` | `daily_readiness` | Date, Condition, Tightness (0–10), Pain (0–10), Body Areas (multi-select), Sensations (multi-select), Note, Tightness Score parsed, Stress Level (covers both stress and mental clarity), Alcohol Units, Travel. Plus (2026-07-14, `Repository.ensure_checkin_extension_columns`): Instability Events, Bristol Type, Unusual Stool Colour, Hunger Deviation, Thirst Intensity, Electrolytes Taken, Meditation Done (inferred from minutes > 0, not a UI toggle), Meditation Minutes, Relaxation Depth. Craving Type and Sodium (mg) were added then removed the same day — the Notion columns may still exist but are no longer read/written |
| `NOTION_DB_TRAINING` | `training_log` + `training_set_log` | Movement, Session Date, Session ID, Type, Planned Sets/Reps, Exercise RPE, Sets (JSON), Session RPE, Session Duration, Session AU, Notes |
| `NOTION_DB_BIOMETRICS` | `daily_biometrics` | Log Date, RHR, HRV, Sleep Hours, Deep Sleep Hours, Active kcal, Weight kg, Steps |
| `NOTION_DB_CONFIG` | Config + `diagnostic_profile` | Key/Value store — plan_start_date, current_stage, diagnostic_profile (JSON), latest_movement_risk (JSON), injury_weight_decay_lambda |

> **Note:** Biometrics DB is no longer written to by the app. Google Sheets is the authoritative source for biometric data, read directly by `sync_sheets.py`. The Notion biometrics DB is retained for backwards compatibility but receives no new writes.

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

Voxplot's **Voice Quality** score remains intentionally visible as Brian's
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

Days 1-10 remain the original fixed baseline. The Training tab now exposes a
separate selectable library containing all 22 activities: the 12 baseline
cards plus these ten new cards. `EXERCISE_LIBRARY` is the single catalogue
for both the library and later plan authoring, so a future plan can mix and
match its stable activity ids without duplicating definitions. `NEW_RECORDING`
remains a daily-plan capture step, not a library activity.

Library practice is explicitly isolated from the daily plan: starting or
finishing a library card uses the same explanation/countdown/results template
but does not mark an item complete, change XP, streak, history, or plan
progress, and does not auto-start the next planned activity. The library is
available when the next baseline day is locked and after Day 10 is complete.

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

The content intentionally reflects the current patient profile: Stage 1
rehabilitation, an active mid-/lower-back flare, and generalised
hypermobility. New cards permit a supported chair or easy neutral standing,
avoid a held posture-correction cue and physical loading, and require a
position change or stop if back symptoms rise. The latest Voice Training
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
| **6** | 14-Day Interactive Training Plan (Stage 1 Rehab) | COMPLETE ✅ |
| **7** | Google Sheets Biometric Auto-Sync | COMPLETE ✅ |
| **8** | Responsive UI System (Oura/Whoop dual-theme) | COMPLETE ✅ |
| **9** | Clinical Input Profile System (`patient_profile.py`) | COMPLETE ✅ |
| **10** | Autoregulation → Background; Directive into Training Plan | COMPLETE ✅ |
| **11** | Biomechanical Profile Integration into Training Plan | COMPLETE ✅ |
| **12** | 4-Week Stage 2 Transition Plan | PENDING — begins after Day 14 assessment |
| **13** | Apple Health Direct API Sync | SUPERSEDED — replaced by the Oura+Garmin blend (2026-07-13) rather than a direct Apple HealthKit sync; Sheet1/Apple Health retired from the live pipeline instead |
| **14** | Stage 2 Training Entry (barbell/cable — external load) | PENDING |

---

## KEYWORD LIBRARY — DETERMINISTIC PARSER (Phase 1 Reference)

### Sensation Tags

| Keyword(s) | Tag | Severity Weight |
|---|---|---|
| sharp, stabbing, shooting | Sharp | 4.0 |
| burning, hot, fire | Burning | 3.5 |
| tight, tightness, stiff, stiffness | Tight | 2.0 |
| dull, ache, aching, throb | Dull Ache | 2.5 |
| numb, numbness, tingle, tingling | Neural | 3.5 |
| weak, weakness, gave way | Weakness | 3.0 |
| normal, fine, good, great, easy | Normal | 0.0 |

### Anatomical Location Tags

| Keyword(s) | Tag |
|---|---|
| lower back, lumbar, L5, S1, disc | lower_back |
| right side, right leg, right hip | right_side |
| left side, left leg, left hip | left_side |
| glute, glutes, buttock, sit bone, ischial | glute |
| hip flexor, psoas, hip, groin | hip_flexor |
| hamstring, back of leg | hamstring |
| calf, achilles, ankle | lower_leg |
| mid back, thoracic | mid_back |
| neck, cervical | neck |
| upper glute, hip crest, TFL | upper_glute |
| piriformis, deep hip | piriformis |

### Background Watcher Trigger Terms (Stage 3 — re-activates conservative constraint)
`shooting`, `nerve`, `numb`, `tingling`, `right leg`, `right foot`, `L5`, `S1`, `sciatica`, `disc`, `foraminal`, `snap`, `click`, `sit bone`, `ischial`

---

## RULES FOR FUTURE DEVELOPMENT

1. **Read `resume.md` and `patient_profile.py`** before writing any new code. Architecture decisions here are locked. Do not re-litigate them.

2. **Deterministic first, always.** No AI component is to be added to any new feature until the deterministic equivalent is written, tested, and confirmed working.

3. **AI never touches safety outputs.** Traffic Light multiplier, ACWR ratio, stage transitions, and final prescribed volume are always deterministic. Period.

4. **No new dependency without justification.** State what it replaces and why the existing stack cannot handle it. Pin to exact version in `requirements.txt`.

5. **Notion is the write backend; Google Sheets is the biometric read source.** Do not add manual biometric entry anywhere in the app. The pipeline is: Export Health App → Google Sheets → `sync_sheets.py` → engine.

6. **Autoregulation is background.** The engine directive is exposed as plain language in the Training Plan only. Numeric metrics (ACWR, HRV delta, injury weight %) appear in AI Insights → Engine Data tab only.

7. **Training sessions are logged automatically by the Training Plan.** No manual training entry page. Do not re-add one.

8. **The pre-session release protocol must precede every training session.** The biomechanical profile mandates inhibiting overactive structures (glute medius, piriformis) before activating underactive ones (glute max, deep core). Any new training block must preserve this sequencing.

9. **Right-side asymmetry is a clinical finding, not a preference.** All exercises involving right hip flexion >60° require a neutral/internal rotation cue. All right posterior hip capsule mobilisation is unilateral (right only). Document this wherever it appears.

10. **`patient_profile.py` is updated before each new training block.** After Day 14 assessment, update findings, imbalances, and stage exit criteria before generating the Stage 2 plan.

11. **Every new function needs a one-line comment** stating whether it is `DETERMINISTIC` or `AI-LAYER` and what its fallback is if it fails.

12. **The keyword library above is the living document** for the deterministic parser. Update it in this file whenever new terms are added to the code.

13. **Bottom nav (Home / Training / Insights / Sync) must be present and functional on every page at all times.** `nav.inject(active)` must be called on every route in `app.py`. The call must come *after* all page content is rendered so that the hidden trigger buttons appear below the cards, not above them. The FAB (+) for Check-In relies on the same JS bridge — do not remove or reorder `nav.inject()` without testing both the bottom bar and the FAB.

---

## OPEN DECISIONS / KNOWN GAPS

| Item | Status | Notes |
|---|---|---|
| HRV data from Sheet1/Apple Health | Often blank (historical only) | No longer the engine's source — see Oura+Garmin blend above. Still true of the retired pipeline for backfill purposes |
| Garmin HRV field mapping | Unverified | `hrvSummary.lastNightAvg` assumed; confirm with `scripts/garmin_login_test.py` against a live payload |
| Notion biometrics DB | No longer written to | Could be removed in future; kept for backwards compat |
| Stage 2 training plan | Not yet built | Needs barbell/cable movement library, updated ACWR ceiling, external load auto-logging |
| Garmin backfill from Sheet1 | Needs to be run once | `scripts/backfill_garmin_from_sheet1.py` — dry-run first, then `--apply` — so readiness baselines have pre-wearable history in the Garmin Daily tab |
| `Training plan/` folder | Stale duplicate | Contents moved to `docs/training/`; manual deletion needed (`Remove-Item -Recurse -Force "Training plan"`) |
| `patient_profile.py` not imported | Informational | Human-readable reference only — not wired into active code. Will be imported when Stage 2 plan reads biomechanical profile programmatically. |

---

*Last updated: 2026-07-14 — added the Voxplot Voice Training Measurement Policy, separate 22-card activity library, and supplied connected-speech paragraph; the original 10-day baseline remains fixed, and optional library practice cannot change daily-plan progress. Sheet1/Apple Health remains retired as the engine's biometric source; the live health blend is Oura+Garmin (`services/biometrics.py`).*
