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
| **Biometrics source** | Manual Apple Health entry on Autoregulation page | Google Sheets sync — Export Health App → Google Sheets → App | Auto-sync removes manual entry entirely; engine reads directly without a sync step |
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

### Pages (Streamlit sidebar navigation)

| File | Page | Purpose |
|---|---|---|
| `app.py` | Morning Check-In | Daily readiness entry: pain score, tightness, sensation tags, lifestyle factors |
| `pages/0_Training_Plan.py` | Training Plan | 14-day interactive rehab session guide with live timers, auto-logging, exit confirmation |
| `pages/3_Autoregulation.py` | Autoregulation | Background config only — stage selector + directive summary. Full data in AI Insights |
| `pages/4_AI_Insights.py` | AI Insights | Engine data tab (ACWR, biometrics, injury weight) + parser queue + tightness map + macro trends + MRI intelligence |
| `pages/6_Sync.py` | Sync | Google Sheets biometric data status viewer |

### Removed Pages (intentionally)
| Page | Reason Removed |
|---|---|
| Training Entry | Replaced by Training Plan auto-logging |
| Data Grid | Background-only; no user-facing value during Stage 1 |
| Biomechanical Profile | Data moved to `patient_profile.py` (clinical input file) |

### Core Modules

| File | Role |
|---|---|
| `engine.py` | Pure deterministic maths — traffic light, ACWR, injury weight decay, stage state machine, volume recommendation. No DB access, no Streamlit. |
| `db.py` | Notion API backend — all read/write. Equivalent to the SQLite schema below but using Notion databases. |
| `sync_sheets.py` | Google Sheets direct reader — pulls biometric rows, maps columns, returns engine-compatible format. No Notion sync needed. |
| `training_plan.py` | 14-day exercise prescription data — all exercise specs, mechanics, biomechanical cues, progressions, regressions. |
| `patient_profile.py` | Clinical input file — MRI findings + biomechanical assessment + muscle imbalance summary + pre-session release protocol. Updated before each new training block. |
| `styles.py` | Responsive dual-theme CSS + component helpers. Oura palette (mobile ≤768px) / Whoop palette (desktop ≥769px). |
| `ai.py` | Phase 2 AI layer — session note parser, tightness parser, macro trend analysis. Advisory only. |
| `rules.py` | Movement safety rules — maps exercises to stage contraindications. |
| `stats.py` | Deterministic statistical analysis — lag correlations, slopes, recovery direction. |

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
- Interactive session guide in `pages/0_Training_Plan.py`
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

```
Export Health App (iPhone)
        ↓
Google Sheets (daily_biometrics_master / Sheet1)
        ↓  [gspread service account — read only]
sync_sheets.get_biometric_rolling(sheet_id, days=28)
        ↓  [30-min cache via @st.cache_data(ttl=1800)]
engine.traffic_light(biometric_rows)
        ↓
Directive → Training Plan banner (plain language)
Full data → AI Insights → Engine Data tab
```

### Column Mapping (Google Sheets → Engine)

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

---

## NOTION DATABASE SCHEMA (current backend)

Four databases, replacing the original SQLite schema. Equivalent data structure.

| Notion DB | Replaces SQLite Table | Key Properties |
|---|---|---|
| `NOTION_DB_READINESS` | `daily_readiness` | Date, Condition, Tightness (0–10), Pain (0–10), Body Areas (multi-select), Sensations (multi-select), Note, Tightness Score parsed |
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
| **11** | Biomechanical Profile Integration into Training Plan | IN PROGRESS 🔄 (agent running) |
| **12** | 4-Week Stage 2 Transition Plan | PENDING — begins after Day 14 assessment |
| **13** | Apple Health Direct API Sync | PENDING — replace Google Sheets intermediary |
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

---

## OPEN DECISIONS / KNOWN GAPS

| Item | Status | Notes |
|---|---|---|
| HRV data from Google Sheets | Often blank | Export Health App does not always capture HRV daily; traffic light runs on available data |
| Notion biometrics DB | No longer written to | Could be removed in future; kept for backwards compat with `get_biometric_rolling()` in db.py |
| Stage 2 training plan | Not yet built | Needs barbell/cable movement library, updated ACWR ceiling, external load auto-logging |
| Apple Health direct sync | Not implemented | Would remove Google Sheets intermediary; requires Apple Health HealthKit API or shortcut automation |
| `training_plan.py` | Agent update in progress | Biomechanical profile integration being written; includes pre-session release blocks for all 14 days |
| `14_day_plan.md` | Agent writing | Readable document of full 14-day plan — not yet in project root |

---

*Last updated: 2026-06-29*
