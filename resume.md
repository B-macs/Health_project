# RESUME: Health & Performance Autoregulation Engine

## PROJECT OBJECTIVE
Build a highly private, data-driven, **local** Health and Performance Application that eliminates training guesswork and optimizes physical recovery and athletic scaling. The application acts as an objective "Autoregulation Engine" — using historical data, subjective daily inputs, and objective biometrics to dictate exact daily training volumes — while protecting the user from injury relapse through mathematical safety guardrails separated from predictive AI parsing.

---

## LOCKED-IN ARCHITECTURE (Non-Negotiable)

| Layer | Decision |
|---|---|
| **Execution** | Local only — absolute data privacy, zero cloud dependency |
| **Frontend / UI** | Streamlit + AG Grid — high-density data grid, inline editing, no dashboards or Kanban |
| **Database** | Local SQLite — append-only, continuous time-series relational architecture; data is never overwritten |

---

## DEVELOPMENT PHILOSOPHY — DETERMINISTIC FIRST (Non-Negotiable)

> **This rule applies to every new feature, every new bucket, every new function added to this project from this point forward. It is not optional and not context-dependent.**

### The Rule: Deterministic Before AI

Every new piece of functionality must be built in two explicit phases. Phase 1 is mandatory. Phase 2 is only permitted once Phase 1 is complete, tested, and confirmed working.

**Phase 1 — Deterministic Python (Always built first)**
All logic is implemented as explicit, rule-based Python code. This means:
- If/else decision trees with clearly documented conditions
- Keyword matching tables with hardcoded term lists
- Threshold-based scoring using explicit numeric mappings
- Mathematical formulas applied directly, with no probabilistic components
- Outputs are fully predictable — the same input always produces the same output
- Unit-testable without any external service, API key, or model

**Phase 2 — AI Layer (Only added if Phase 1 is demonstrably insufficient)**
An AI or LLM component may be added on top of a working deterministic implementation only when all of the following are true:
1. The Phase 1 deterministic version has been built and is running
2. There is a specific, documented limitation of the deterministic version that AI would improve
3. The AI output feeds into the system as structured data — it never directly controls a safety decision
4. A fallback to the deterministic version exists if the AI call fails or returns an unexpected response

### The Hard Boundary: AI Never Controls Safety

Regardless of how mature the AI layer becomes, the following components must always remain 100% deterministic and must never be influenced by AI output:
- The Traffic Light biometric multiplier (Green / Yellow / Red)
- The ACWR calculation and its hard-lock thresholds
- The Stage 1 / 2 / 3 transition conditions
- The injury decay function and Background Watcher trigger logic
- Any prescribed set, rep, or volume target output to the user

AI components may only populate advisory fields — summaries, tags, flagged body parts, sentiment scores. They are inputs to the human's awareness, not inputs to the engine's calculations.

### How to Apply This Rule When Adding New Code

When a new feature is requested, Claude Code must follow this sequence before writing any code:

1. **State the feature in plain English** — what does it need to do?
2. **Write the deterministic version** — what keyword list, threshold, formula, or decision tree covers 80% of cases?
3. **Identify the gap** — what does the deterministic version fail to handle that would meaningfully affect the user?
4. **Decide** — if the gap is significant and not safety-critical, add an AI layer on top. If the gap is minor or the function is safety-critical, ship the deterministic version only.
5. **Document the decision** in a code comment: `# DETERMINISTIC-ONLY: reason` or `# AI LAYER ADDED: reason, fallback = [function name]`

---

## LOGIC SEPARATION

### A. Strict Deterministic Engine (Hard-coded Math & Rules)

**Traffic Light Biometric Autoregulation**
Evaluates daily morning biometrics (HRV, RHR, Sleep) against 7-day and 28-day rolling averages:

| Signal | Condition | Action |
|---|---|---|
| Green | Biometrics at or above rolling averages | Standard Progressive Overload |
| Yellow | Drop within 10% of rolling average | Scale volume down 20–30%, hold intensity baseline |
| Red | Drastic biometric drop | Hard-lock to deload / mobility-only |

**Acute-to-Chronic Workload Ratio (ACWR)**
```
ACWR = Acute Workload (7-day avg volume) / Chronic Workload (28-day avg volume)
```
Hard constraint: If ACWR > 1.3 → engine hard-locks upper training limits for the week.

---

### B. Probabilistic Engine (AI / LLM — Phase 2 only, advisory output only)

> These components are only active after their deterministic equivalents are built and running. Each has a documented deterministic fallback. None of these outputs feed into safety calculations.

- **Medical & Diagnostic Ingestion:** Parses raw unstructured medical text (MRI reports, clinical impressions) to isolate structural pathology and map it to database anatomical tags. *Deterministic fallback: pre-populated keyword tag list from known MRI terminology.*
- **Subjective Text Synthesis:** Evaluates daily qualitative log entries and converts them into structured severity scores and automated tightness maps. *Deterministic fallback: keyword-to-tag matcher covering core sensation terms (sharp, tight, stiff, dull, neural, normal).*
- **Macro Trend Recognition:** Evaluates long-term, non-linear relationships across months of data. *Deterministic fallback: fixed lag-correlation check between 48-hour HRV drop and next-day pain score.*

---

## STAGE STATE MACHINE
Evaluated every 14 days. The user profile moves forward (never backward unless triggered). **All transition logic is deterministic — no AI involvement.**

### Stage 1 — Rehab (Tissue Tolerance Focus)
- Strict volume caps
- Conservative ACWR ceiling (max 1.2)
- High weight on injury parameters

### Stage 2 — Transition (Work Capacity Focus)
- Specific rehab movements blend into standard training warm-ups
- Volume constraints loosen
- ACWR ceiling rises toward 1.3

### Stage 3 — Performance & Growth (Athletic Focus)
- Injury status factor decays via automated time-decay function:

$$\text{Injury Weight} = e^{-\lambda t}$$

where $t$ = days since last flare-up and weeks of pain-free completed load.
- Injury data becomes a silent "Background Watcher" — alerts only if daily subjective inputs or movement patterns align with historical baseline pathologies.

**Stage transition trigger conditions (deterministic, evaluated every 14 days):**

| Condition | Required Value |
|---|---|
| Average daily pain score | < 1.0 over trailing 14 days |
| Plan compliance | > 90% of logged sessions completed |
| HRV trend | Stable or improving (no chronic downward trend over 14 days) |
| Days since last pain score > 2 | ≥ 28 consecutive days to advance from Stage 1 → 2 |

---

## FOUNDATIONAL BASELINE (User Profile)

> **Decay principle:** This baseline is the engine's highest-priority constraint at kickoff. Its weight decays automatically over time as pain-free training milestones are met (e.g., 4 consecutive weeks without a flare-up, Stage progression). By Stage 3 it becomes a silent background watcher — only re-activates if subjective inputs or movement patterns match historical pathology signatures. The raw MRI data is stored permanently in `diagnostic_profile`; only its *influence weight* decays.

---

### Q1 — Injury Profile (MRI — 10.11.2025, DIE RADIOLOGIE Munich)

**Primary active pathology — L5/S1:**
- Moderately activated osteochondrosis with paradiscal bone edema and mild erosive changes
- Narrow retrolisthesis (vertebra sliding posterior) + broad-based disc protrusion **right dorsolateral**
- **Moderate right foraminal stenosis** (nerve root at risk on right side), mild left
- This is the hot level — the one most likely driving acute symptoms

**Secondary pathology — L3/4 and L4/5:**
- Flat disc protrusions **left dorsolateral** at both levels; covered annulus fibrosus tears (contained, stable)
- Retrolisthesis also present at L4/5
- Mild foraminal stenosis at both levels (not moderate)

**Cleared structures:**
- Spinal canal: clear on MR-myelography — no cord or cauda compression
- Facet joints: no significant degeneration or inflammation
- Sacroiliac joints (ISG): normal
- Back musculature: symmetric, no atrophy, no edema — neurological function preserved

**Kinetic chain downstream effects:**
- Hip flexor / glute tightness: psoas originates L1–L4; chronic tightness from sitting pulls lumbar spine into extension, compressing already stenotic foramina at L5/S1 → pain amplifier
- Mid-back strain (resolved): was a compensation pattern; not structurally relevant now but logged as historical compensation

**Movement constraints for Stage 1:**
- Avoid: heavy axial compression, end-range lumbar flexion under load, rotation under load, lumbar hyperextension
- Priority movements: hip-hinge (controlled, light), glute activation, core bracing, walking, hip flexor release
- Right-side loading: monitor closely (L5/S1 foraminal stenosis right side)

**Stage at kickoff:** Stage 1 — Rehab (Tissue Tolerance Focus)

---

### Q2 — Apple Health Metrics (Full Suite)
All available metrics synced. Priority columns for the autoregulation Traffic Light: HRV, RHR, Sleep Duration, Deep Sleep, Active Energy. Full capture also includes: Weight, Steps, Average Heart Rate.

---

### Q3 — Data Entry Method (Custom Gym UI + Notes)
- **Set input:** Dial / spinner for reps + weight per set. No free-text volume entry.
- **Rest timer:** Auto-started between sets; rest duration captured automatically in seconds.
- **Session notes:** In-gym typed free-text describing how exercises felt, perceived difficulty, physical sensations. Stored raw. In Phase 1, parsed by deterministic keyword matcher. In Phase 2, optionally parsed by AI if deterministic output is insufficient.

---

### Initial Training Program Structure
**Weeks 1–2: Observation-Only Phase**
No structured progressive overload targets. Purpose: establish baseline data across all inputs before the engine makes programming decisions.
- Log all movement sessions (type, sets, reps, weight, RPE)
- Capture daily biometrics via Apple Health sync
- Record daily readiness + subjective notes each session
- Engine reads and learns — no auto-generated training targets issued until end of Week 2
- At end of Week 2: first 7-day and 14-day rolling averages are valid → Traffic Light system activates → ACWR baseline established → Bucket 4 logic becomes meaningful

---

## DATABASE SCHEMA (SQLite)

Schema refined from answers above. Changes vs. original spec: `daily_biometrics` expanded for full Apple Health suite; `training_log` split into session-level + per-set-level tables; `session_notes` table added for qualitative input with both deterministic and AI-parseable fields.

```sql
-- Core baseline medical context and history
CREATE TABLE diagnostic_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    injury_focus TEXT,               -- E.g., "Lower back bulging disc"
    mri_raw_text TEXT,               -- Unstructured diagnostic text
    historical_compensations TEXT    -- Past injuries causing potential kinetic imbalances
);

-- Continuous timeline for daily tracking & subjective logs
CREATE TABLE daily_readiness (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    current_condition TEXT,          -- General readiness/feeling
    subjective_tightness TEXT,       -- Sensation text
    pain_score INTEGER               -- Scale 0-10
);

-- Session-level training record (one row per session)
CREATE TABLE training_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    movement_name TEXT,              -- E.g., "Romanian Deadlift"
    movement_type TEXT,              -- "Weight", "Stretch", "Conditioning", "Rehab"
    planned_sets INTEGER,
    planned_reps INTEGER,
    rpe INTEGER                      -- Rate of Perceived Exertion (1-10)
);

-- Per-set granular data captured via dial + auto-timer
CREATE TABLE training_set_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    training_log_id INTEGER REFERENCES training_log(id),
    set_number INTEGER,
    reps_completed INTEGER,          -- captured from dial
    weight_kg REAL,                  -- captured from dial
    rest_time_seconds INTEGER,       -- captured from auto-timer
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Free-text session notes with deterministic parse fields populated first
-- AI summary fields only populated if Phase 2 AI layer is active
CREATE TABLE session_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    training_log_id INTEGER REFERENCES training_log(id),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_text TEXT,                        -- verbatim input
    -- Phase 1 deterministic fields (always populated)
    det_matched_keywords TEXT,            -- comma-separated matched sensation terms
    det_flagged_body_parts TEXT,          -- matched anatomical terms from keyword list
    det_severity_score REAL,             -- rule-based 0.0-5.0 from keyword weights
    -- Phase 2 AI fields (only populated if AI layer active, never used in safety calc)
    ai_summary TEXT,                      -- populated after AI parsing
    ai_sentiment_score REAL,             -- parsed: -1.0 (negative) to 1.0 (positive)
    ai_flagged_body_parts TEXT           -- AI-extracted anatomical tags
);

-- Centralized Apple Health data sync repository (full suite)
CREATE TABLE daily_biometrics (
    date DATE PRIMARY KEY,
    resting_heart_rate INTEGER,
    heart_rate_avg INTEGER,          -- daily average
    hrv_ms REAL,
    sleep_duration_hours REAL,
    sleep_deep_hours REAL,
    active_energy_kcal INTEGER,
    weight_kg REAL,
    steps INTEGER
);
```

---

## AGILE ROADMAP

| Bucket | Title | Status |
|---|---|---|
| **1** | Discovery & Dynamic Logic Blueprint | COMPLETE ✅ |
| **2** | Local Database Schema & Initialization Scripts | COMPLETE ✅ |
| **3** | Data Input Engine & Interactive Data Grid Setup | COMPLETE ✅ |
| **4** | The Autoregulation & ACWR Mathematical Algorithm | COMPLETE ✅ |
| **5** | AI Text / MRI Parsing Engines & Multi-Month Performance Scaling | COMPLETE ✅ |

> **Note on Bucket 5 status:** Bucket 5 is marked complete for its deterministic Phase 1 implementations. Any AI components within Bucket 5 are advisory-only overlays and must not be assumed to be the primary logic path. Verify via codebase audit which Phase 2 components are active before adding new features.

---

## BUCKET 2 SCOPE

All three foundational questions are answered. Bucket 2 deliverables:

1. `schema.sql` — Full SQLite schema (all 7 tables above), with `IF NOT EXISTS` guards
2. `init_db.py` — Python script that creates the database file (`health_engine.db`), runs the schema, and seeds `diagnostic_profile` with the user's baseline injury data
3. `requirements.txt` — Python dependencies: `streamlit`, `pandas`, `sqlite3` (stdlib), `anthropic` (available for Phase 2 AI calls — not imported or used until Phase 1 equivalent is confirmed working)

**Seed data for `diagnostic_profile` (run once at init):**
- `injury_focus`: "L5/S1 activated osteochondrosis with retrolisthesis and right dorsolateral disc protrusion; moderate right foraminal stenosis. Secondary flat protrusions L3/4 and L4/5 left dorsolateral with covered annulus tears and mild foraminal stenosis. Downstream: chronic hip flexor/glute tightness (psoas, L1-L4 origin)."
- `historical_compensations`: "Mid-back muscle strain (resolved); was a compensation pattern from lower back tightness. No structural residual. Psoas tightness from prolonged sitting amplifies L5/S1 foraminal compression."
- `mri_raw_text`: "MRI LWS mit Myelographie und knöch. Becken, 10.11.2025, DIE RADIOLOGIE München. LWK5/SWK1: Moderat ausgeprägte aktivierte Osteochondrose mit bandförmigem paradiscalem Knochenödem und geringen erosiven Veränderungen. Schmale breitbasige Retrospondylose und Bandscheibenprotrusion mit rechts dorsolateraler Betonung. Dadurch moderate Foramenstenose rechts, geringgradig links. LWK 3/4: Flache breitbasige Bandscheibenprotrusion links dorsolateral mit gedecktem Riss im Anulus fibrosus. Geringgradige Foramenstenose. LWK 4/5: Flache Retrospondylose und Bandscheibenprotrusion links dorsolateral mit gedecktem Riss im Anulus fibrosus. Geringgradige Foramenstenose. Kein Nachweis einer Myelonkompression. Rückenmuskulatur seitengleich ohne wesentliche Atrophie."
- `injury_weight_decay_lambda`: 0.05 *(suggested starting λ — decay reviewed every 14 days at stage evaluation)*

---

## KEYWORD LIBRARY — DETERMINISTIC PARSER (Phase 1 Reference)

> This is the master keyword list used by the deterministic session note parser. It must be updated manually when new terms are encountered. This is the source of truth for Phase 1 parsing — AI parsing in Phase 2 supplements this list, it does not replace it.

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
| glute, glutes, buttock | glute |
| hip flexor, psoas, hip | hip_flexor |
| hamstring, back of leg | hamstring |
| calf, achilles, ankle | lower_leg |
| mid back, thoracic | mid_back |
| neck, cervical | neck |

### Background Watcher Trigger Terms
If any of the following appear in session notes while in Stage 3, the Background Watcher re-activates a 48-hour conservative volume constraint automatically:

`shooting`, `nerve`, `numb`, `tingling`, `right leg`, `right foot`, `L5`, `S1`, `sciatica`, `disc`, `foraminal`

---

## RULES FOR FUTURE DEVELOPMENT

The following rules apply to every Claude Code session working on this project:

1. **Read this file first** before writing any new code. The architecture decisions here are locked. Do not re-litigate them.

2. **Deterministic first, always.** No AI component is to be added to any new feature until the deterministic equivalent is written, tested, and confirmed working. State this explicitly in a comment.

3. **AI never touches safety outputs.** The Traffic Light multiplier, ACWR ratio, stage transitions, and final prescribed volume are always the product of deterministic code. Period.

4. **No new dependency without justification.** Before adding any new Python package, state what it replaces and why the existing stack cannot handle it.

5. **Schema changes require a migration script.** Never alter the live `.db` file manually. All schema changes go through a versioned migration script so the data history is never at risk.

6. **Every new function needs a one-line comment** stating whether it is `DETERMINISTIC` or `AI-LAYER` and what its fallback is if it fails.

7. **The keyword library above is the living document** for the deterministic parser. Update it in this file whenever new terms are added to the code.

---
