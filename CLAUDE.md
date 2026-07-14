# CLAUDE.md — Health Engine

*Last updated: 2026-07-14 after adding the Strength BioAge Stage-Adjusted Recovery Score engine (`services/bioage.py`).*

---

## Required Reading (in order)

Before writing any new code, read these files in this sequence:

1. **`docs/resume.md`** — architecture decisions, data model, stage machine, design philosophy, keyword library, rules for future development. All locked decisions live here.
2. **`patient_profile.py`** — MRI findings, biomechanical assessment (2026-06-28), muscle imbalances, pre-session release protocol, stage exit criteria. Updated before each new training block.
3. **Local clinical profile documents in `Input_files/`** — gitignored, never committed (same status as `Input_files/MRI_Lower_back.pdf`, the source `patient_profile.py` was built from). Currently: `2025-training-year.md` (full-year strength log + movement-pattern analysis). Expect an injury-history document and a hypermobility-profile document to be added the same way — read whatever is present in `Input_files/*.md` beyond the MRI PDF. See `docs/clinical_profile_weighting.md` for how each is weighted.
4. **`docs/clinical_profile_weighting.md`** — how the local profile documents above modulate training design (injury recency/resolution, hypermobility, strength baseline). Read alongside them, not standalone.
5. **`services/rules.py`** — `STAGE_CONSTRAINTS` (ACWR ceilings, RPE caps, volume caps per stage). `MOVEMENT_RULES` (contraindicated / caution / cleared). Single source of truth for safety guardrails.
6. **`services/engine.py`** — deterministic math: strain, ACWR, traffic light, injury weight decay, volume recommendation. Derives ceilings from `services.rules.STAGE_CONSTRAINTS`. No I/O, no Streamlit, no buried clock reads (`today` is always an explicit param).

---

## Deterministic Gate

Run after every change before committing:

```
python -m pytest tests/
```

Expected: **383/383 passed** (or higher — this count grows as tests are added; treat it as a floor, not an exact match)

- Never delete or weaken a test to make the gate pass.
- Never weaken a `services/rules.py` guardrail.
- If you add new engine/stats/rules logic, add a corresponding test.
- `tests/test_no_streamlit_in_services.py` enforces that `services/` never imports `streamlit` — don't weaken it either.

---

## Definition of Done

A change is complete when:

1. `python -m pytest tests/` → 383/383 (or higher if new tests were added)
2. All affected imports resolve without error: `python -c "import app"` (or the relevant module)
3. The change is committed with a descriptive message explaining the *why*
4. No behaviour was changed without explicit approval — filing moves files and fixes imports only

---

## Architecture in One Page

```
app.py (entry point — SPA router)
  │  reads st.session_state["_nav_page"]
  ├── "home"      → inline home dashboard
  ├── "checkin"   → views/checkin.py
  ├── "training"  → views/training.py
  ├── "insights"  → views/insights.py
  └── "sync"      → views/sync.py

repo.py — Streamlit-layer bootstrap: builds a services.config.Config from
  st.secrets and hands back a cached services.repository.Repository
  (@st.cache_resource). This is the ONLY place st.secrets is read.

services/ — framework-agnostic backend + business logic. ZERO Streamlit
  imports anywhere (enforced by tests/test_no_streamlit_in_services.py).
  Pure logic:      engine.py · readiness.py · stats.py · rules.py · ai.py ·
                    plan.py · sessions.py · dashboard.py · insights.py ·
                    metrics_logic.py (Weekly Rollup / Perfect-Ultimate Week scoring) ·
                    biometrics.py (Oura+Garmin blend weights — the engine's
                    biometric source, replacing Sheet1/Apple Health) ·
                    bioage.py (Strength BioAge Stage-Adjusted Recovery Score —
                    per-region 0-100 scores stay None until a region has real
                    logged *weighted* volume; see its module docstring)
  Orchestration:    metrics.py — sync_weekly_rollup(); the one services/
                    module that both computes (via metrics_logic.py) and
                    does I/O (via repository.py) in the same call.
  Typed models:     models.py (Phase, SessionRecord, ExerciseEntry, DayCell,
                    CheckInRecord, BiometricRecord, WeekScore, StreakInfo —
                    dataclasses)
  I/O clients:      clients/notion.py, clients/sheets.py (generic primitives
                    only, no column/property names), clients/local_cache.py
                    (local JSON file — Oura sync-throttle marker, survives
                    process restarts unlike st.cache_data)
  Data access:      repository.py — the ONLY place Notion property names /
                    Sheet column names live; ~40 methods, wraps clients/
  Config:           config.py — Config dataclass + load_config(overrides),
                    env-var-first. Never reads st.secrets directly.

  Streamlit pages are thin presentation shells: they call
  repo.get_repository().*() and services.*, and own all @st.cache_data
  wrapping (the service layer itself is cache-agnostic).

UI helpers:
  nav.py   — bottom nav bar + JS bridge (stNav() in parent window)
  styles.py — dual-theme CSS: Oura palette ≤768px / Whoop palette ≥769px

Reference data:
  training_plan.py      — PLAN dict (14 exercise days, exercise objects)
  training_constants.py — EXERCISES catalogue, ANATOMICAL_LOCATIONS, SENSATION_TAGS,
                           EXERCISE_BODY_REGION (exercise name → upper_body/core/
                           lower_body, feeds services/bioage.py)
  patient_profile.py    — clinical data; human reference AND, as of the Strength
                           BioAge muscle-imbalance count, actively imported by
                           services/bioage.py (PROFILE["imbalances"])

tests/       — pytest suite (192 tests), the sole deterministic gate
_pages/      — removed; SPA router handles all routing; Streamlit 1.36+ auto-detects this dir
scripts/     — one-shot CLI tools (init_notion.py)
legacy/      — SQLite era, not used at runtime (init_db.py, schema.sql)
docs/        — INVENTORY.md, resume.md, training/*.md, playbook.md, focus.md,
               REFACTOR_NOTES.md (services/ extraction: smells found, not fixed)
```

---

## Key Rules (non-negotiable)

1. **Deterministic before AI** — implement the rule-based version first; AI layer is only added on top once the deterministic version is tested and working.
2. **AI never controls safety** — traffic light multiplier, ACWR ceiling, stage transitions, and final prescribed volume are always deterministic. AI output is advisory only.
3. **`services.rules.STAGE_CONSTRAINTS` is the single source of truth** for per-stage ACWR ceilings, RPE ceilings, and volume caps. `services/engine.py` derives from it; do not duplicate values.
4. **Notion is the write backend; Oura + Garmin (blended) is the engine's biometric read source.** `services/biometrics.py` blends HRV/RHR/sleep duration at Oura 70% / Garmin 30%, and steps at Garmin 80% / Oura 20% — see `services.repository.Repository.get_biometric_rolling`. Google Sheets is still the intermediary (each platform's own tab, synced by `sync_oura_all`/`sync_garmin_daily_if_due`), and Sheet1/Apple Health is retired from the live pipeline — historical-only, feeding `get_sheet1_biometric_rolling` and the one-time `scripts/backfill_garmin_from_sheet1.py`. `get_biometric_rolling` itself is a **live recompute, not persisted** — the "Biometric Blend" sheet tab (`sync_biometric_blend`/`get_biometric_blend_history`) is the fixed historical record of what was actually computed on a given day, written once/day and viewable unbounded in Insights → Sync. Do not add manual biometric entry anywhere.
5. **Training sessions are logged automatically by Training Plan.** No manual entry page.
6. **Pre-session release protocol precedes every training session.** Inhibit overactive structures (glute medius, piriformis) before activating underactive ones (glute max, deep core). Preserve this order in all new training blocks.
7. **Right-side asymmetry is a clinical finding.** All exercises involving right hip flexion >60° require a neutral/internal rotation cue. Right posterior hip capsule mobilisation is unilateral (right only).
8. **`patient_profile.py` is updated before each new training block**, after the Day 14 assessment updates findings, imbalances, and stage exit criteria.
9. **Secrets stay in `.streamlit/secrets.toml`** (gitignored). Never commit API keys or service account credentials. `services/` must never read `st.secrets` directly — only `repo.py` adapts it into a `Config` at startup.
10. **`services/` has zero Streamlit imports.** All backend I/O (Notion, Google Sheets) and business/plan logic lives there so it can be reused by a future non-Streamlit frontend. Streamlit pages (`app.py`, `views/*.py`) are thin presentation shells that call `repo.get_repository()` and `services.*`.
11. **Before authoring any new training block, explicitly confirm each local clinical profile document has been read** — `patient_profile.py` plus every `Input_files/*.md` document present — and state how each one influenced the plan, per `docs/clinical_profile_weighting.md`. This is the checkable form of "understood and acknowledged," not a formality to skip.

---

## Known Open Issues

| Issue | Status |
|-------|--------|
| `Training plan/` folder at root | Stale duplicate of `docs/training/` — delete manually (`Remove-Item -Recurse "Training plan"`) |
| Stage 2 training plan | Not yet built — begins after Day 14 physiotherapist sign-off |
| Garmin HRV field mapping | Unverified against a live payload — `hrvSummary.lastNightAvg` is the commonly-documented shape; confirm with `scripts/garmin_login_test.py` and fix `Repository._garmin_daily_row` if it doesn't match |
| Garmin backfill | Run `scripts/backfill_garmin_from_sheet1.py` (dry-run first, then `--apply`) once to backfill pre-wearable history into the Garmin Daily tab so readiness baselines aren't starting from empty |
| Biomechanical review due | 2026-07-19 — update `patient_profile.py` and `init_db.py` seed before Stage 2 |
| Strength BioAge scores dormant | By design (`services/bioage.py`) until weighted training begins — training is still Stage 1 bodyweight-only, so all 3 region scores + the hero value show "—". Muscle-imbalance count is unaffected (reads `patient_profile.py` directly) and already shows a real number. |
| `training_constants.EXERCISE_BODY_REGION` needs upkeep | When Stage 2's training plan is built (row above), its new exercise names need entries here too, or `services/bioage.py` silently excludes them from any region — see that dict's own comment in `training_constants.py`. |
| See `docs/REFACTOR_NOTES.md` | Smells/bugs found during the services/ extraction, noted but not fixed beyond what the extraction itself required |
