# CLAUDE.md — Health Engine

*Last updated: 2026-07-31 after adding Oura+Garmin MOVEMENT fusion (`services/sleep_movement.py`, the movement tick strip on the Home Sleep drill-down, `sleep_fusion.RULES_VERSION` 2's movement-aware staging rules, and the Oura `movement_30_sec`/HR/HRV and Garmin `sleepMovement`/HR/stress columns). Before that: Oura+Garmin sleep-stage fusion (`services/sleep_fusion.py`, the Garmin Sleep Stages and Sleep Fusion tabs, Garmin 429 backoff + circuit breaker). Previously: heart-rate-derived strain (`services/hr_load.py` — Edwards' TRIMP — and `services/hr_matching.py`), true per-set training capture, readiness-based auto-shift session scheduling (`services/scheduling.py`), double-progression weight/rep tracking, weekly tonnage (`services/volume.py`), Sleep Debt scoring, and the per-night wake-time adjustment.*

---

## Required Reading (in order)

Before writing any new code, read these files in this sequence:

1. **`docs/resume.md`** — architecture decisions, data model, stage machine, design philosophy, keyword library, rules for future development. All locked decisions live here.
2. **`patient_profile.py`** — MRI findings, biomechanical assessment (2026-06-28), muscle imbalances, pre-session release protocol, stage exit criteria. Updated before each new training block.
3. **Local clinical profile documents in `Input_files/`** — gitignored, never committed (same status as `Input_files/MRI_Lower_back.pdf`, the source `patient_profile.py` was built from). Currently present: `2025-training-year.md` (full-year strength log + movement-pattern analysis), `injury_profile.md`, `hypermobility-profile.md`, and `stage1_recent_data_summary.md` — read whatever is in `Input_files/*.md` beyond the MRI PDF, since more may be added. See `docs/clinical_profile_weighting.md` for how each is weighted.
4. **`docs/clinical_profile_weighting.md`** — how the local profile documents above modulate training design (injury recency/resolution, hypermobility, strength baseline). Read alongside them, not standalone.
5. **`services/rules.py`** — `STAGE_CONSTRAINTS` (ACWR ceilings, RPE caps, volume caps per stage). `MOVEMENT_RULES` (contraindicated / caution / cleared). Single source of truth for safety guardrails.
6. **`services/engine.py`** — deterministic math: strain, ACWR, traffic light, injury weight decay, volume recommendation. Derives ceilings from `services.rules.STAGE_CONSTRAINTS`. No I/O, no Streamlit, no buried clock reads (`today` is always an explicit param).

---

## Deterministic Gate

Run after every change before committing:

```
python -m pytest tests/
```

Expected: **1031/1031 passed** (or higher — this count grows as tests are added; treat it as a floor, not an exact match)

- Never delete or weaken a test to make the gate pass.
- Never weaken a `services/rules.py` guardrail.
- If you add new engine/stats/rules logic, add a corresponding test.
- `tests/test_no_streamlit_in_services.py` enforces that `services/` never imports `streamlit` — don't weaken it either.

---

## Definition of Done

A change is complete when:

1. `python -m pytest tests/` → 1031/1031 (or higher if new tests were added)
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
                    logged *weighted* volume; see its module docstring) ·
                    scheduling.py (readiness-based auto-shift of a scheduled
                    gym-session day — sleep debt/short sleep/consecutive-day
                    alcohol triggers a pairwise-adjacent-day swap for the
                    rest of that calendar week) ·
                    volume.py (weekly tonnage — Σ reps×weight — for Stage 2A+
                    double-progression exercises) ·
                    hr_load.py (Edwards' summated-HR-zone TRIMP → the 0-21
                    strain scale; see its docstring for why Edwards' over
                    Banister/Lucia/Stagno, and for the calibration that keeps
                    HR-derived and RPE-derived strain on one continuous scale) ·
                    hr_matching.py (which Garmin activity IS a logged session,
                    by wall-clock overlap; plus per-exercise HR attribution
                    off the per-set timestamps) ·
                    sleep_fusion.py (merges the Oura and Garmin per-minute
                    hypnograms into one master sequence — Oura supplies stage,
                    Garmin supplies permission-to-call-Awake. RULES_VERSION 2
                    adds movement-aware rules 5-7 on top, degrading exactly to
                    version 1 on a night with no movement data. Also emits
                    SOURCE_GARMIN_ONLY for nights the ring was not worn: the
                    watch is worn ~2x as often, so this is where most of the
                    coverage gain over Oura alone comes from. DISPLAY-ONLY:
                    read its module docstring before wiring any of it into the
                    engine, the shadow report showed partial coverage makes
                    the traffic light STRICTER, not looser) ·
                    sleep_movement.py (fuses the two devices' MOVEMENT series —
                    Oura's ordinal 1-4 class per 30s and Garmin's undocumented
                    float per minute — by quantile-mapping Garmin onto Oura's
                    published alphabet, then blending with AMPLITUDE-DEPENDENT
                    weights: the ring wins at low amplitude, the watch at high.
                    Its docstring states the one hard non-goal — never infer
                    REM from movement, because REM atonia makes REM as
                    motionless as deep sleep)
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

tests/       — pytest suite (1031 tests), the sole deterministic gate
_pages/      — removed; SPA router handles all routing; Streamlit 1.36+ auto-detects this dir
scripts/     — one-shot CLI tools (init_notion.py, backfill_oura_history.py,
               backfill_garmin_sleep_stages.py — probe before spending calls)
docs/        — INVENTORY.md, resume.md, training/*.md, playbook.md, focus.md,
               REFACTOR_NOTES.md (services/ extraction: smells found, not fixed)
```

---

## Key Rules (non-negotiable)

1. **Deterministic before AI** — implement the rule-based version first; AI layer is only added on top once the deterministic version is tested and working.
2. **AI never controls safety** — traffic light multiplier, ACWR ceiling, stage transitions, and final prescribed volume are always deterministic. AI output is advisory only.
2b. **ACWR stays on Foster AU; only STRAIN is heart-rate-derived.** `services/hr_load.py` feeds the displayed strain value, never `engine.acwr`. ACWR is a ratio of rolling averages, so mixing Edwards'-TRIMP days with RPE-fallback days inside one 7/28-day window would compare different units and swing the ceiling on whether a Garmin activity happened to be recorded — i.e. on watch-button behaviour rather than physiology. Unifying them requires a per-athlete conversion regressed from sessions that have BOTH signals; do not attempt it until enough paired sessions exist.
3. **`services.rules.STAGE_CONSTRAINTS` is the single source of truth** for per-stage ACWR ceilings, RPE ceilings, and volume caps. `services/engine.py` derives from it; do not duplicate values.
4. **Notion is the write backend; Oura + Garmin (blended) is the engine's biometric read source.** `services/biometrics.py` blends HRV/RHR/sleep duration at Oura 70% / Garmin 30%, and steps at Garmin 80% / Oura 20% — see `services.repository.Repository.get_biometric_rolling`. Google Sheets is still the intermediary (each platform's own tab, synced by `sync_oura_all`/`sync_garmin_daily_if_due`), and Sheet1/Apple Health is retired from the live pipeline — historical-only, feeding `get_sheet1_biometric_rolling` and the one-time `scripts/backfill_garmin_from_sheet1.py`. `get_biometric_rolling` itself is a **live recompute, not persisted** — the "Biometric Blend" sheet tab (`sync_biometric_blend`/`get_biometric_blend_history`) is the fixed historical record of what was actually computed on a given day, written once/day and viewable unbounded in Insights → Sync. Do not add manual biometric entry anywhere. Exception: a per-night wake-time correction for Sleep Score purposes is allowed (`services/repository.py`'s `get_wake_time_adjustment`/`set_wake_time_adjustment`) — this corrects a known, specific Oura measurement pattern (wake-time overestimation), not general manual biometric entry. Both the raw Oura reading and the adjustment are stored separately; the raw reading is never overwritten.
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
| Garmin HRV is absent, two independent causes | RESOLVED-as-empty (probed 2026-07-31): `get_hrv_data` returns `{}` for this account, so `hrvSummary.lastNightAvg` has nothing to map. Separately, the Garmin Daily tab had been created before `hrv_ms` joined `_GARMIN_DAILY_HEADER`, so every sync wrote it into an unheadered column that `get_all_records` discarded — `services/biometrics.py`'s documented Oura-70/Garmin-30 HRV blend has silently been 100% Oura. The column is repaired (`Repository.rebuild_garmin_daily`); the endpoint may start returning data with a watch that supports HRV status. |
| Garmin backfill | Run `scripts/backfill_garmin_from_sheet1.py` (dry-run first, then `--apply`) once to backfill pre-wearable history into the Garmin Daily tab so readiness baselines aren't starting from empty |
| Quiet-wakefulness rule — measured, then abandoned | **Do not re-attempt without reading `services/sleep_fusion.py`'s docstring.** Best precision ~12% against a 1.9% base rate, i.e. ~88% of flagged minutes would be wrong, and REM is indistinguishable from Awake (both elevated-and-motionless). Probing found no finer HR exists on this account. The blocking problem is not sample size — it is that there is **no ground truth**: validation uses the hypnogram's own Awake labels, but the rule exists to find minutes the hypnogram did *not* label Awake. Needs PSG/EEG ground truth plus beat-to-beat intervals. |
| Movement calibration is n=26 | `Repository.sleep_movement_cutpoints` quantile-maps Garmin's undocumented float onto Oura's 1-4 alphabet from paired nights only; currently 26, floor is 14. The ACTIVE boundary sits far into the tail and is the least stable of the three, which is why rule 7 treats class 4 as corroboration rather than proof. Re-check the fitted values as paired nights accumulate. |
| Sleep coverage is worn-device-limited, not sensor-limited | Over the 71 nights of the Garmin era the ring recorded 27 nights and the watch 53. Fusing them plus emitting `garmin_only` nights takes stage coverage from 38% to 76% of calendar nights (+217h of sleep Oura never saw). The remaining gap is the 17 nights neither device recorded — no code change reaches those. |
| Sheets tabs silently drop newly-added columns | Any tab created before a column joined its `_HEADER` keeps the old header forever — `get_or_create_worksheet` writes row 1 only on creation and `upsert_row_by_key` never touches it, so values land in an unheadered column and `get_all_records` discards them. Bit `hrv_ms` (above) and would have bit the movement columns. `Repository.rebuild_tab(worksheet, header, ...)` re-heads a tab and carries every existing row through; call it after adding any column. |
| Cold app start renders empty for ~60s | First page load runs the Oura/Garmin sync inline before `_bio_rolling`, so the drill-down shows its empty states until it finishes. Pre-existing, unrelated to fusion; the fix is to make that sync non-blocking. |
| Biomechanical review due | 2026-07-19 — update `patient_profile.py` before Stage 2 |
| Strength BioAge scores dormant | By design (`services/bioage.py`) until weighted training begins — training is still Stage 1 bodyweight-only, so all 3 region scores + the hero value show "—". Muscle-imbalance count is unaffected (reads `patient_profile.py` directly) and already shows a real number. |
| `training_constants.EXERCISE_BODY_REGION` needs upkeep | When Stage 2's training plan is built (row above), its new exercise names need entries here too, or `services/bioage.py` silently excludes them from any region — see that dict's own comment in `training_constants.py`. |
| See `docs/REFACTOR_NOTES.md` | Smells/bugs found during the services/ extraction, noted but not fixed beyond what the extraction itself required |
