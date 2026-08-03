# CLAUDE.md — Health Engine

*Last updated: 2026-08-01 after adding body-temperature deviation as a fourth `engine.traffic_light` metric (absolute °C cut points, not a rolling baseline), the `engine.baseline_drift` guard, full Stage 1 coverage in `training_constants.EXERCISE_MOVEMENT_WEIGHT` (Strain/ACWR were counting rehab drills as loaded lifting), and the `sessions.movement_category` mislabelling fix. Before that: Oura+Garmin MOVEMENT fusion (`services/sleep_movement.py`, the movement tick strip on the Home Sleep drill-down, `sleep_fusion.RULES_VERSION` 2's movement-aware staging rules, and the Oura `movement_30_sec`/HR/HRV and Garmin `sleepMovement`/HR/stress columns). Before that: Oura+Garmin sleep-stage fusion (`services/sleep_fusion.py`, the Garmin Sleep Stages and Sleep Fusion tabs, Garmin 429 backoff + circuit breaker). Previously: heart-rate-derived strain (`services/hr_load.py` — Edwards' TRIMP — and `services/hr_matching.py`), true per-set training capture, readiness-based auto-shift session scheduling (`services/scheduling.py`), double-progression weight/rep tracking, weekly tonnage (`services/volume.py`), Sleep Debt scoring, and the per-night wake-time adjustment.*

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

Expected: **1218/1218 passed** (or higher — this count grows as tests are added; treat it as a floor, not an exact match)

- Never delete or weaken a test to make the gate pass.
- Never weaken a `services/rules.py` guardrail.
- If you add new engine/stats/rules logic, add a corresponding test.
- `tests/test_no_streamlit_in_services.py` enforces that `services/` never imports `streamlit` — don't weaken it either.

---

## Definition of Done

A change is complete when:

1. `python -m pytest tests/` → 1218/1218 (or higher if new tests were added)
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
                    background_sync.py — BackgroundSyncRunner, which runs
                    Repository.run_home_syncs off the Streamlit script
                    thread so opening the app never waits on the device
                    APIs. Builds its OWN Repository per run (nothing in one
                    is thread-safe) and takes a non-blocking lock so the
                    reruns fired by every widget interaction can't stack up
                    a thread each. See Key Rule 12.
  Typed models:     models.py (Phase, SessionRecord, ExerciseEntry, DayCell,
                    CheckInRecord, BiometricRecord, WeekScore, StreakInfo —
                    dataclasses)
  I/O clients:      clients/notion.py, clients/sheets.py (generic primitives
                    only, no column/property names), clients/local_cache.py
                    (local JSON file — durable sync-throttle markers,
                    survives process restarts unlike st.cache_data; locked
                    and atomically replaced because the background sync
                    thread writes it while the script thread reads it),
                    clients/datastore_reader.py (read-only SQLite stand-in
                    for a Sheets worksheet — see "Offline mode" below)
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

tests/       — pytest suite (1218 tests), the sole deterministic gate
_pages/      — removed; SPA router handles all routing; Streamlit 1.36+ auto-detects this dir
scripts/     — one-shot CLI tools (init_notion.py, backfill_oura_history.py,
               backfill_garmin_sleep_stages.py — probe before spending calls)
docs/        — INVENTORY.md, resume.md, training/*.md, playbook.md, focus.md,
               REFACTOR_NOTES.md (services/ extraction: smells found, not fixed)
```

---

## Offline mode — test against the datastore, not Google Sheets

*Added 2026-08-01. Google Sheets allows 60 reads+writes per minute per user;
an afternoon of iterating on one page exhausts it, and a throttled read does
not look like an error — it looks like missing data. That already produced
one wrong finding (a "Metrics History sleep_score is unpopulated" conclusion
that was really a 429; 21 of 34 rows are populated, and the gap is a bounded
2026-06-29 → 2026-07-11 window).*

Set **`HEALTH_DATASTORE_PATH=datastore.db`** and every Google Sheets READ is
served from the local snapshot instead. Not fewer API calls — **zero**,
including the service-account auth handshake.

```
python scripts/build_datastore.py          # refresh the snapshot (one full read pass)
HEALTH_DATASTORE_PATH=datastore.db python -m pytest tests/
HEALTH_DATASTORE_PATH=datastore.db python -m streamlit run app.py
```

- **One seam.** All 14 tab getters go through `Repository._ws()`, which
  returns a `datastore_reader.OfflineWorksheet` — duck-typed against
  gspread, so `_read_records` and every call site work unmodified.
  `tests/test_repository_offline_datastore.py` asserts all 14 route through
  it; a getter that opens a tab directly fails that test.
- **Writes raise**, they never silently no-op — a caller believing a sync
  persisted is worse than a crash. The file is opened `mode=ro` as well.
- **Either/or, never a fallback.** A failed live read keeps failing rather
  than quietly serving a snapshot. `app.py` shows an unmissable banner with
  the snapshot's build time on every page when offline.
- **Fidelity is the point**, and is what the tests actually pin: blank cells
  read back as `""` (not `None`), digit-coded hypnograms stay `str`,
  gspread's `'TRUE'`/`'FALSE'` stay verbatim, and every header column is
  present even when empty. Verified end-to-end against 2026-07-28: score,
  contributors, hypnogram, movement strip, κ, cut points and vitals all
  identical to the live values.
- **Not covered: Notion.** `readiness_checkins`/`training_*` are in the
  datastore but reshaped, so Notion-backed getters still hit the network.
  Sleep/biometrics work is 100% Sheets, which is why this was worth doing
  without solving Notion too. `get_raw_sheet_rows()` (Sheet1 raw
  passthrough) also raises offline — the datastore holds Sheet1 mapped.
- **Adding a tab means adding a row to `_DATASTORE_TABLE_BY_TAB` AND a table
  to `datastore_schema.sql`**, or offline reads of it return `[]` forever.

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
12. **The device sync runs on a background thread, and that thread must never touch Streamlit.** `services/background_sync.py` owns it; `repo.get_sync_runner()` holds one per process via `st.cache_resource`. The worker builds its **own** `Repository` from the `Config` and shares nothing with the UI thread's — a `Repository` owns a gspread session, a Notion client and two mutable caches, none of them thread-safe, and the script thread reads through its copy the whole time. A worker has no `ScriptRunContext`, so no `st.*` call (including `st.session_state`) is legal from it. Results are read back off the runner by whichever script run asks next.
13. **`_run_startup_sync` waits only while today's numbers are missing.** `dashboard.snapshot_is_complete` on today's persisted Metrics History row decides: not settled → run inline (last night's row isn't in Sheets yet, so backgrounding would leave the cards on yesterday until the next open); settled → hand to the worker and return. Cadence is 2h per step either way, durably marked, triggered by opening the app.
14. **Never `st.rerun()` or `st.cache_data.clear()` after a sync.** Both were tried and made it strictly worse: clearing forces a re-read of six tabs at the moment the sync has just spent a burst of writes, which walks into Sheets' 60-per-minute quota. Leaving them out is also what keeps the day's numbers stable — once shown they stay, and change only when a later read genuinely differs.
15. **A sync loop snapshots its tab once via `_rows_by_key`, then passes each row into the upsert.** `_read_records` is keyed on `sheets.write_generation()`, so the first real write invalidates it and per-row lookups would re-download the whole tab for every subsequent row. The upserts skip writes whose values are unchanged (`_cell_eq` compares the way a spreadsheet does — `71.0 == 71`, `"" == None`, but `"" != 0`), which is what makes "only overwrite when new information arrives" true of the stored data and not just of the numbers.
11. **Before authoring any new training block, explicitly confirm each local clinical profile document has been read** — `patient_profile.py` plus every `Input_files/*.md` document present — and state how each one influenced the plan, per `docs/clinical_profile_weighting.md`. This is the checkable form of "understood and acknowledged," not a formality to skip.

---

## Garmin 645 → 265 upgrade — what to re-test

*Recorded 2026-07-31, before the upgrade. Every "645" figure below is measured
from the 53 archived nights in `Input_files/garmin_export/`, not assumed.*

Several findings that currently read as "the data does not exist" are **limits
of the Forerunner 645, not of the Garmin API**. Re-test each after the 265 is
worn for ~2 weeks. The measured 645 baseline is given so the comparison is
real rather than impressionistic.

| Capability | 645, measured | Expect on 265 | What it unblocks |
|---|---|---|---|
| SpO2 / Pulse Ox | `averageSpO2Value` null on **0/53** nights | present | A Garmin cross-check on Oura's `spo2_average`; currently the Vitals panel's blood-oxygen row is Oura-only |
| Respiration rate | `averageRespirationValue` null on **0/53**; `get_respiration_data` returns empty arrays | present | Same — respiration is Oura-only today |
| HRV | `get_hrv_data` returns `{}` | HRV Status supported | `services/biometrics.py`'s documented Oura-70/**Garmin-30** HRV blend, which has silently been 100% Oura (see the column-drop row below — that half is already repaired) |
| Skin temperature | `skinTempDataExists` **False on 53/53** | present | A second temperature signal beside Oura's `readiness_temperature_deviation` |
| REM staging | `deviceRemCapable`, `remSleepData: True` on **53/53** | unchanged | Already working — this is why fusion works at all |
| Overnight HR resolution | 120 s (`sleepHeartRate`), and `get_heart_rates` is also 120 s | **probably unchanged** — 120 s looks like a Connect API storage decision, not a sensor one | Verify before assuming the quiet-wake rule is revived; see below |

**Two things that do NOT automatically improve, and one real hazard:**

1. **The quiet-wakefulness rule stays blocked even if HR resolution improves.**
   Its decisive objection was never resolution — it is that there is no ground
   truth (validation uses the hypnogram's own Awake labels, but the rule
   exists to find minutes the hypnogram did *not* label Awake). A better watch
   does not supply PSG. Read `services/sleep_fusion.py`'s docstring before
   re-attempting.
2. **Coverage is worn-device-limited.** The 38% → 76% gain came from wearing
   the watch more often than the ring, not from sensor quality. A better watch
   does not reach the 17 nights neither device recorded.
3. **⚠ REFIT the movement calibration, and do NOT pool 645 and 265 nights.**
   `Repository.sleep_movement_cutpoints` quantile-maps Garmin's undocumented
   `activityLevel` float onto Oura's 1-4 alphabet. The current cut points
   (**1.450, 2.430, 5.630**, fitted on 26 paired 645 nights) are specific to
   the 645's accelerometer and its scale. Elevate Gen 5 may well report a
   different distribution, and pooling two devices into one fit is exactly the
   units error that made an early version map a real night to 94.7% "still"
   with zero postural shifts. Every stored night records the calibration it
   was produced under in `movement_cutpoints`, which is what makes a refit
   auditable — check whether the 265's fitted values diverge before
   backfilling, and re-derive history with `sync_sleep_fusion(days=1500)`.
4. **⚠ HRV is HELD at Oura-only, on purpose** — `biometrics.HRV_GARMIN_HOLD`.
   The documented Oura-70/Garmin-30 HRV blend has never actually run (the
   645 has no HRV Status), so a watch that supports it would flip the blend
   to a real 70/30 on the day the hardware changed and step the HRV series
   readiness baselines are built from — a device artefact, not physiology.
   Wrist and finger PPG do not agree on HRV: it comes from beat-to-beat
   intervals, where a few ms of beat-detection error swamps RMSSD.
   While held, HRV is Oura's **or nothing** — a night with only Garmin HRV
   yields `None` rather than a wrist value silently rescaling a
   finger-baselined series. **Lift it on a measurement, not a date:** run
   `Repository.hrv_blend_status()`, confirm `ready` (≥14 paired nights),
   look at `mean_bias` (signed garmin−oura; negative = Garmin lower =
   readiness would quietly drop) and `sd_bias` (wide spread means the offset
   is not constant and no single weighting fixes it), then set
   `HRV_GARMIN_HOLD = False`. Two tests pin that the 70/30 returns intact.

**Which device is more accurate, for the record.** HRV: **Oura**, and not
close — finger PPG, measured during stillness, all night. HR: **Oura**
overnight/at rest, **265** for running and daytime; for resistance training
neither is trustworthy (wrist flexion and grip wreck wrist PPG) and a chest
strap beats both. Measured baseline to re-test against, from 24 paired
nights on the 645: Garmin RHR − Oura lowest HR = **mean +2.6, median +3.5,
sd 3.4**; Garmin min HR − Oura lowest = **mean −4.4, sd 3.9**. Note that is
partly definitional (Garmin's RHR is a smoothed daily figure, min_hr a
single sample, Oura's is the sleep-period low) — the **sd ≈3.4 bpm** is the
real disagreement. HRV could not be compared at all: 0 Garmin nights.

**Re-test procedure** (all of it costs one probe plus a rebuild):

```
python scripts/backfill_garmin_sleep_stages.py --probe          # confirm data exists
python scripts/backfill_garmin_sleep_stages.py --apply --limit 20
python -c "...; repo.sync_sleep_fusion(days=1500)"              # refit + re-derive
```
Then re-run the by-stage HR/HRV/stress separation measurement that killed the
quiet-wake rule, and compare against the recorded 645 figures in
`services/sleep_fusion.py`'s docstring.

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
| Metrics History `sleep_score` gap | NOT a population failure — corrected 2026-08-01 by querying the datastore offline. 21 of 34 rows carry a score; exactly 13 consecutive dates are blank, **2026-06-29 → 2026-07-11**, and everything from 2026-07-12 on is populated. An earlier reading of "33 rows, all None" was a throttled Sheets read (429) misread as absent data — the exact failure the offline datastore now prevents. The 13 dates predate the column and would need a `sync_metrics_history` backfill over that window if wanted. |
| Sleep coverage is worn-device-limited, not sensor-limited | Over the 71 nights of the Garmin era the ring recorded 27 nights and the watch 53. Fusing them plus emitting `garmin_only` nights takes stage coverage from 38% to 76% of calendar nights (+217h of sleep Oura never saw). The remaining gap is the 17 nights neither device recorded — no code change reaches those. |
| Sheets tabs silently drop newly-added columns | Any tab created before a column joined its `_HEADER` keeps the old header forever — `get_or_create_worksheet` writes row 1 only on creation and `upsert_row_by_key` never touches it, so values land in an unheadered column and `get_all_records` discards them. Bit `hrv_ms` (above) and would have bit the movement columns. `Repository.rebuild_tab(worksheet, header, ...)` re-heads a tab and carries every existing row through; call it after adding any column. |
| Cold app start latency | FIXED 2026-08-01. The startup sync ran before `_bio_rolling`, so every cold load spent ~77s (`sync_oura_all` 50s + `sync_garmin_daily_if_due` 27s) showing "No Readings" to avoid displaying data a couple of hours old — buying freshness with total unavailability. `app.py::_run_startup_sync()` now runs last and reruns once; first paint of real sleep data is **18.5s**. Remaining latency is the Sheets reads themselves. |
| Strain/ACWR history changed on 2026-08-01 — Stage 1 was over-counted | `EXERCISE_MOVEMENT_WEIGHT` covered only `PLAN_STAGE2`'s exercise universe, so **34 of the 63 exercise names in the logged history** hit `content_weighting.UNMAPPED_EXERCISE_WEIGHT` (1.0) — every Supine Knee-to-Chest and Diaphragmatic Breathing drill counted as fully-loaded barbell work. Now 79/79 mapped. Live reads self-heal (multipliers recompute from each day's Sets JSON on every call), so Strain on a pure-mobility day drops ~4.9 → ~2.0. **The already-persisted `Metrics History` strain column does NOT self-heal** — it holds the old inflated snapshots; re-run `sync_metrics_history` over the Stage 1 window if the stored series matters. Correcting it *raised* ACWR 1.23 → 1.44 (chronic 40.8 → 35.0): the old Stage 1 inflation was padding the denominator, hiding how steep the Stage 2 ramp actually is. |
| `bodyweight_compound` is a new weight tier (0.5) | Added for Stage 1's unloaded multi-joint work (Chair Sit-to-Stand, step-ups, lunges, wall sits, Single-Leg RDL). Sits between `isolation` 0.3 and `pull`/`upper_push` 0.7 — scoring a bodyweight sit-to-stand at `squat` 1.3 would be as wrong as the 1.0 default it replaced. `tests/test_movement_weight_coverage.py` pins the ordering and the one-category-one-weight invariant. |
| Baseline-drift guard is dormant until ~mid-Sept 2026 | `engine.baseline_drift` needs `DRIFT_MIN_PRIOR_DAYS` (21) rows *before* the current 28-row window. The ring was worn intermittently before mid-2026, so a 90-day fetch yields only 11 prior rows; `DRIFT_RECOMMENDED_FETCH_DAYS` (400) yields 62 and does fire (HRV −18.7%, sleep −11.4%, severity `severe`). Windows count ROWS not calendar days, deliberately — a calendar window shrinks to nothing across a sparse stretch. Both UI call sites already pass the wide fetch. |
| Historical Notion rows keep their old `movement_type` label | `sessions.movement_category`'s fallback used to swallow every unrecognised name into "Mobility", so Lat Pulldown / Incline DB Press / Single-Arm DB Row / Face Pull / Hip Thrust (Loaded) were all *written* to Notion as "Mobility". Fixed for new writes only — rows logged before 2026-08-01 keep the wrong string. Display-only (nothing computes from it; Strain/ACWR weighting reads `EXERCISE_MOVEMENT_WEIGHT` by exercise NAME), so this is cosmetic and needs a backfill only if the history's labels matter. |
| Readiness rebuilt as `MODEL_VERSION 2` | **RESOLVED 2026-08-01.** v1 read 84.8 where Oura read 57. Cause was not the imported contributors (those matched exactly) but v1's own HRV and RHR components, `min(100, ratio*100)` — **one-sided and saturating**, so any day at/above baseline scored a flat 100 — plus four Oura contributors that were synced and ignored. v2 scores from Oura's eight contributors plus our own Sleep Debt, with our weights and our composite (**not** Oura's score taken directly). Measured over a year: **r = 0.992** with Oura, mean bias −0.9, sd 2.8, 91% within 5 points; v1 ran ~15 points high. Alcohol is no longer deducted — self-reported and invisible to Oura, so scoring it made the two incomparable; `services/scheduling.py` still shifts sessions on consecutive-day alcohol independently. All 52 Metrics History rows re-derived and stamped `readiness_model_version`. |
| Naps are discarded from `sleep_duration_hours` | **Measured, not yet fixed.** `biometrics.pick_main_sleep_period` returns only the `long_sleep` entry, so 57 nap periods across 50 days — **34.1 h of sleep, largest nap 217 min** — never count. 2026-07-19 scores 3.70 h against an actual ~6.0 h. Feeds readiness Sleep (18%) + Sleep Debt (10%), sleep_score Total Sleep (25%), the sleep baseline, `traffic_light` and `scheduling`. Two questions are conflated: which period's *architecture* to display (rightly the main night) vs the day's *total duration* (the actual bug). Needs explicit approval — it moves historical scores. |
| Biomechanical review due | 2026-07-19 — update `patient_profile.py` before Stage 2 |
| Strength BioAge scores dormant | By design (`services/bioage.py`) until weighted training begins — training is still Stage 1 bodyweight-only, so all 3 region scores + the hero value show "—". Muscle-imbalance count is unaffected (reads `patient_profile.py` directly) and already shows a real number. |
| `training_constants.EXERCISE_BODY_REGION` needs upkeep | When Stage 2's training plan is built (row above), its new exercise names need entries here too, or `services/bioage.py` silently excludes them from any region — see that dict's own comment in `training_constants.py`. |
| See `docs/REFACTOR_NOTES.md` | Smells/bugs found during the services/ extraction, noted but not fixed beyond what the extraction itself required |
