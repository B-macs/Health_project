# CLAUDE.md — Health Engine

*Last updated: 2026-08-07 — the battery's first contact with the athlete produced four corrections, all his, all now in code: **(1) the tilt is an ANGLE at the pelvis** (phone flat on the lower back, degrees between sitting tall and deepest tip; unit `°`, bigger-is-better, `TILT_TARGET_DEG`) because forehead height is exactly the number a rounding spine can fake and his rounding is the documented compensation — one number replaced the protocol's two, and an old centimetre tilt reading returns `indeterminate` rather than being read as degrees; **(2) own-power runs before helped** in slot 2, the slot-3 principle (help flatters what follows) applied consistently, stated by him as a requirement; **(3) Gate 0's two-orientation comparison only runs within `GATE0_BONE_RELEVANT_CM` (15 cm) of the floor** — bone meets socket in the last few centimetres of a FULL side split, so at his height the comparison answers nothing, `cluster_a_battery.applicable_tests(draft)` drops the turned-out step live (the view asks it, never re-implements it), and slot 0 passes on the neutral height alone with the skip's reason on screen; **(4) the straddle width is captured beside the tilt reading** (`Reading.setup_value`, same as the heel distance) and the screen offers last session's number back — the setup number is the SAME number every session by design. Also: every test now carries an `input_hint` ("floor to crotch, in cm") rendered AT the input; the Expected-outcome expander is off the screen on his request (the prediction stays in `EXPECTED_PATTERN` — its job is to exist before measuring, not to prime the measurer); and the flexibility screen's captions were unreadable (10px `#5A6377` on near-black) and now override to readable ink. Gate 1613 → 1626. Same day, second pass: **the Prescription's stacking rules are now tests, not prose** (`tests/test_cluster_a.py` "stacking rules" section — isolated-before-integrated with §G/§H's door-opener exemption pinned to their own text, full position last for §B–§E and §G, §F's no-finisher design pinned WITH its reason, bent-before-straight except §E, triangle-before-inline, the per-stack limiter story, the 5-item ceiling), because the audit that prompted them found **§A transcribed in the wrong order** — the Python ran triangle before the ER hold, inverting the source document's own sequence; restored, ER hold first. Gate 1626 → 1634. Third pass, on his review of the §F walkthrough: **every library exercise now says HOW, not just why** — five mandatory patient-facing fields on `cluster_a_mechanics.Exercise` (`position`, `movement` incl. what actually resists you, `feel`, `stop`, `progress`), all 31 entries authored, jargon-scanned AND hedge-scanned (his wording rule: never "it doesn't matter which" after offering options), rendered on screen ahead of the why (`note` demoted to a caption). The complaint that drove it: straddle lift-offs and the flat-back hinge were indistinguishable from their text — now pinned distinguishable (lift-offs name the resistance as his own tissue, not gravity; the hinge states STANDING, a position the old note never gave at all). The mechanics md records that the how-to text is code-authored. Gate 1634 → 1639. Fourth pass: **THE LADDER** — the athlete asked for per-muscle 0-100 scores, which is v1's refuted shape (his own words killed it: *"my flexibility score is nearly 80 for hips"* while the hips were stuck), so what shipped is the honest form he approved: `services/battery.LadderRung` + `cluster_a_battery.ladder()`/`LADDER_INFO` render the battery's decision path as seven rungs, tightest at the bottom, the working rung = the battery's first failure (the ladder DISPLAYS the decision, never makes one). Each measured rung shows its reading, its NAMED denominator and a %-of-target bar; the invented targets stay flagged provisional, while strength-at-depth divides his own isometric by his own passive (relative) and openers divide the active sum by the 180° geometry of a full split. **An unmeasured muscle has no number — None, never zero** — and Keep-going readings surface as "context, not diagnosis" without moving the pattern; Pattern C marks both leverage rungs limiting at once. No aggregate exists, pinned by test. Gate 1639 → 1647 (5 of those skip in a checkout without `Input_files/`). Before that: 2026-08-06 (second pass) — FLEXIBILITY was rebuilt AGAIN, and the churn is the thing to read first: **three models in two days, and the first two are deleted.** v1 scored `sqrt(RANGE x CONTROL)` across eight body regions and the athlete refuted it in one sentence — *we know my hips are stuck in flexion with my back arched, and yet my flexibility score is nearly 80 for hips* — because the hip average buried the one test of his worst capacity. v2 replaced regions with skills and scored `skill = min(rungs)` over fourteen rungs. **v3 is not a refinement of v2**: three new source documents describe a four-slot BATTERY that runs in order and STOPS AT THE FIRST FAILURE, emitting a single pattern label A-I and, in the source's words, nothing else. A decision tree with early exit and a scoring function over everything are different programs — a failing slot 0 does not make the slots below it lower priority, it makes them MEANINGLESS, because a bony block makes the tissue questions unanswerable. `tests/test_cluster_a.py` fails if any of the eleven deleted v1/v2 symbols reappear (`band_score`, `CONTROL_BAND`, `rung_score`, `score_skill`, `SkillScore`, `WIDE_GAP_POINTS`, `RUNGS`, `SKILLS`...). Nothing was lost either time: no assessment had ever been run, and none of Cluster A's measurements were implemented by any v2 rung. **THREE LAYERS, ONE DIRECTION, ENFORCED BY FOUR GUARD TESTS** in the idiom of `tests/test_no_streamlit_in_services.py`: `cluster_a_mechanics.py` (WHY — limiters and the exercise library; no tests, no doses) -> `services/battery.py` + `cluster_a_battery.py` (HOW TO TEST — four slots; names no exercise) -> `cluster_a_prescription.py` (WHAT TO DO — pattern in, ordered stack out; names exercises but DEFINES none, and every name must resolve in the Mechanics library). The fourth guard: **`prescribe(None)` raises rather than guessing** — a prescription without a pattern is a guess, say so rather than guessing — and the refusal names the next action. **The capture flow stops too**, asking the real battery after every step rather than re-implementing the rule, so the screen and the engine cannot disagree; failing gate 0 ends the session after two readings instead of eight more that cannot be interpreted. A third outcome beside pass and fail is `indeterminate`: **a measurement not taken is not evidence of health.** THE FIFTH LIMITER is this athlete's dominant one and is the claim the cluster rests on, in his words: *the lumbar issue is driven from the specific tilt deficit, which needs a specific flexibility training method to fix it.* **The lumbar rounding is the COMPENSATION, not the problem** — he rounds because the pelvis will not rotate forward in sitting (straddle 25/100, reported in four seated positions, 2026-08-05). So section F was REBUILT rather than filtered: pelvic rock for the movement in isolation, elevated flat-back hinge (the elevation IS the assist), straddle lift-offs for production, flat-back hinge to raise the hamstring ceiling. **Success is the block coming down, not the reach going further.** `EXPECTED_PATTERN` is F, written into the code BEFORE measuring so a borderline reading cannot be read toward the answer already in mind — and it disagrees with the generic lax-tissue prediction of H/I, which is worth watching rather than resolving in advance. Also now tests rather than comments: **measure order is active -> isometric -> passive** (passive work leaves tissue looser and flatters everything after it); an isometric reading as deep as passive means the load was too light and the slot reports a botched measurement rather than a gap of zero; **load and measurement are ONE DATUM**; three baseline mornings before a number is trusted, and a change under ~2x the observed spread returns not-a-result rather than a delta; the worse side decides, never an average. `services/rules.py` was the BLOCKING PREREQUISITE and had three defects — 78 movement names from these documents produced 8 matches, 70 `unknown` (which is not a block), and ZERO of the 14 contraindicated-on-mechanism movements caught by the rule written for them. **Vocabulary**: the rules speak movement descriptions, the documents speak skill names — `Straddle Forward Fold` was contraindicated while `Pancake`, the same movement, was unknown. **Punctuation**: `good morning` is not a substring of `good-mornings`, so a loaded lumbar-flexion movement over two annulus tears returned `unknown` — one hyphen between a hard block and silence. **False clearance**: *hands walking forward* matched the `walking` CLEARED rule and returned an affirmative low-impact-movement verdict on the most flexion-loaded item in the set; cleared rules must now HEAD a name, token-wise and plural-tolerant. The three documents are ADAPTED IN PLACE for this body (they are gitignored clinical material), each change carrying its REVERT CONDITION in the `HRV_GARMIN_HOLD` idiom — held on evidence, not deleted. Two adaptations cost nothing because the source supplies them: gate 0 and every triangle side split cue from EXTERNAL ROTATION rather than a lumbar arch (*neither is more correct; both align the joint identically* — one arch cue had propagated into nine prescription instances), and the nerve check became a differentiator rather than a provocation, which the battery's own footer already demanded. Horse stance and Cossack are deferred past **2026-08-16** because an open Stage 2 exit criterion is no-increase-in-Coxa-Saltans-frequency under loaded squat/split-squat work, and two new ER-cued loaded squats would confound the criterion he is about to be assessed on — a measurement cost as much as a safety one. Every stack is prefixed with `patient_profile`'s pre-session release block, which all nine source stacks omitted entirely. `scripts/check_cluster_documents.py` runs every movement NAMED in the three documents through `check_movement` at the live stage — 77 of them, all cleared or caution — extracting structurally rather than by a word list that would fail open when stale. `REST_DAY_CONFLICT_UNRESOLVED` is RETIRED: a cluster session is adaptation-seeking by definition, so a rest day is now the worst window. Gate 1584 -> 1602. Before that: the Metabolism BioAge screen shipped: `services/body_composition.py`, `body_composition_baselines.py` and `views/insights.py::_render_metabolism_detail`, with `docs/resume.md` gaining a BODY COMPOSITION section for its locked decisions. Two devices are kept in permanently separate lanes — a Foryond scale whose fourteen columns are one measurement (its body fat percent is fitted from weight and age at R^2 0.9966) and an InBody 770 whose five scans were run against four different typed heights, corrected by `InBodyScan.at_height`. Gate 1475 -> 1515. Before that: documentation refresh across `docs/` (focus.md, resume.md, playbook.md, progress.json, INVENTORY.md, training/Training_System.md), which had all still described Stage 1 as the current stage five weeks after Stage 2A started on 2026-07-20, and still gave the gate as `python tests.py` → 141/141. Four Known Open Issues rows below were also false and are corrected: the Stage 2 plan is built, the `Training plan/` duplicate is gone, the biomechanical review was done 2026-07-19, and Strength BioAge is no longer dormant. Before that: adding NAP support — `biometrics.split_sleep_periods`/`dedupe_sleep_periods`/`NAP_MIN_SECONDS`, the Day-total panel on the Home Sleep drill-down, and the duration-counts-naps / architecture-does-not split that `services/sleep_score.py` depends on. Before that: body-temperature deviation as a fourth `engine.traffic_light` metric (absolute °C cut points, not a rolling baseline), the `engine.baseline_drift` guard, full Stage 1 coverage in `training_constants.EXERCISE_MOVEMENT_WEIGHT` (Strain/ACWR were counting rehab drills as loaded lifting), and the `sessions.movement_category` mislabelling fix. Before that: Oura+Garmin MOVEMENT fusion (`services/sleep_movement.py`, the movement tick strip on the Home Sleep drill-down, `sleep_fusion.RULES_VERSION` 2's movement-aware staging rules, and the Oura `movement_30_sec`/HR/HRV and Garmin `sleepMovement`/HR/stress columns). Before that: Oura+Garmin sleep-stage fusion (`services/sleep_fusion.py`, the Garmin Sleep Stages and Sleep Fusion tabs, Garmin 429 backoff + circuit breaker). Previously: heart-rate-derived strain (`services/hr_load.py` — Edwards' TRIMP — and `services/hr_matching.py`), true per-set training capture, readiness-based auto-shift session scheduling (`services/scheduling.py`), double-progression weight/rep tracking, weekly tonnage (`services/volume.py`), Sleep Debt scoring, and the per-night wake-time adjustment.*

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

Expected: **1652/1652 passed** (or higher — this count grows as tests are added; treat it as a floor, not an exact match)

- Never delete or weaken a test to make the gate pass.
- Never weaken a `services/rules.py` guardrail.
- If you add new engine/stats/rules logic, add a corresponding test.
- `tests/test_no_streamlit_in_services.py` enforces that `services/` never imports `streamlit` — don't weaken it either.

---

## Definition of Done

A change is complete when:

1. `python -m pytest tests/` → 1602/1602 (or higher if new tests were added)
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
                    bioage.py (ONE function — the muscle-imbalance count off
                    patient_profile.PROFILE. It reads clinical data, not
                    training history, which is why it still renders when the
                    log cannot be read. The Stage-Adjusted Recovery Score that
                    used to live here was removed 2026-08-04; its docstring
                    says why, and a test fails if any of it comes back) ·
                    scheduling.py (readiness-based auto-shift of a scheduled
                    gym-session day — sleep debt/short sleep/consecutive-day
                    alcohol triggers a pairwise-adjacent-day swap for the
                    rest of that calendar week) ·
                    volume.py (weekly tonnage — Σ reps×weight — for Stage 2A+
                    double-progression exercises; no sector split, see
                    tonnage.py) ·
                    strength.py (the Overall Strength Score — estimated
                    strength CAPACITY in points, where 100 is the 2025 peak
                    from strength_baselines.py. Read its docstring before
                    touching it: the ONE safety property is that measured
                    performance can only push the level UP and the only
                    downward force is detraining decay, which is what stops
                    pain, a substitution, a rehab restriction or a
                    deliberately light week from reading as strength loss.
                    Regional split via a shrinkage estimator, held in a
                    calibration mode where every index displays at 50 — the
                    identity `overall = Σ shareᵣ × indexᵣ` then holds the
                    overall at 50 for ANY split, which is why calibration can
                    run for months without the headline moving) ·
                    tonnage.py (weekly WORK COMPLETED, in kg, overall and per
                    body sector — a SEPARATE metric that shares no term with
                    strength.py. No decay, no carry-over. Unloaded work is
                    counted in reps and never converted to kilograms) ·
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
                    body_composition.py (the Metabolism screen's backend. Two
                    devices kept in SEPARATE lanes: a Foryond foot-only scale
                    whose 14 columns are one measurement — weight — since its
                    body fat % is itself fitted from weight and age at R² 0.9966,
                    and an InBody 770 whose five scans were run against four
                    different typed heights. `InBodyScan.at_height` re-runs a
                    scan at the true 182 cm; height enters InBody's first step
                    SQUARED, so the correction moves every kilogram and moves
                    neither of the two height-immune readings, phase angle and
                    ECW/TBW. Read the module docstring before adding anything:
                    a fused body-fat number across the two devices and a
                    composition expressed in years are both refused there, and
                    tests pin the refusals) ·
                    sleep_movement.py (fuses the two devices' MOVEMENT series —
                    Oura's ordinal 1-4 class per 30s and Garmin's undocumented
                    float per minute — by quantile-mapping Garmin onto Oura's
                    published alphabet, then blending with AMPLITUDE-DEPENDENT
                    weights: the ring wins at low amplitude, the watch at high.
                    Its docstring states the one hard non-goal — never infer
                    REM from movement, because REM atonia makes REM as
                    motionless as deep sleep) ·
                    battery.py (the GENERAL assessment method, cluster-
                    agnostic. Four slots run IN ORDER and it STOPS AT THE
                    FIRST FAILURE — a decision tree with early exit, not a
                    scoring function. Output is one pattern label and nothing
                    else. NAMES NO EXERCISE, and a test fails if it ever
                    does. Also owns the load window — an isometric reading
                    must come out shallower than passive or the load was too
                    light and you measured passive twice — and the noise
                    floor: three baseline mornings, and a change under ~2x
                    the observed spread is not a result) ·
                    flexibility.py (the ONE place the three layers are
                    joined: run the battery, look up the prescription, refuse
                    when there is no pattern. Holds no tests, no exercises
                    and no doses of its own; when it needs one it asks the
                    layer that owns it. Read its docstring before adding
                    anything — it names the eleven deleted symbols from two
                    earlier models that must never grow back) ·
                    yoga.py (the yoga catalogue and its safety layer.
                    `effective_safety()` cross-checks each pose's authored tag
                    against a live `rules.check_movement()` call, so a new
                    MOVEMENT_RULES keyword is picked up without re-authoring
                    the pose. Tags are ADVISORY — these are externally-sourced
                    videos the athlete chooses to follow, not prescriptions,
                    and nothing here blocks a button. `YogaPose.retest`
                    carries an open clinical question back to the pose that
                    can answer it. **The laterality suffix names the FRONT /
                    WORKED leg, never the side being stretched** — for a
                    pigeon those coincide, for a lunge they are opposite legs,
                    and getting it backwards silently moves every
                    laterality-specific caution onto the wrong side)
  Orchestration:    metrics.py — sync_weekly_rollup(); the one services/
                    module that both computes (via metrics_logic.py) and
                    does I/O (via repository.py) in the same call.
                    background_sync.py — BackgroundSyncRunner, which runs
                    Repository.run_home_syncs off the Streamlit script
                    thread so opening the app never waits on the device
                    APIs. Builds its OWN Repository per run (nothing in one
                    is thread-safe) and holds ONE lock that all three entry
                    points take: start() non-blocking, so the reruns fired
                    by every widget interaction can't stack up a thread
                    each; run_now() and exclusive() waiting, because their
                    callers asked for the work explicitly. exclusive() is
                    what keeps views/' manual syncs out of the automatic
                    chain's way. See Key Rules 12 and 16.
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
                           lower_body; feeds services/strength.py and
                           services/tonnage.py — an exercise missing from it is
                           excluded from every sector total)
  body_composition_baselines.py — the five InBody 770 scans, transcribed from a
                           PAPER print-out with no export path. Carries the raw 50 kHz
                           impedances and the waist/WHR the phone app never synced.
                           Both 2025-05-21 scans are kept: taken 8 minutes apart, they
                           differ by 6.0 pp of body fat purely because the operator
                           corrected the height between them.
  strength_baselines.py — the 2025 peak that "100" means, one entry per exercise,
                           plus each entry's `comparability`. Transcribed from
                           Input_files/2025-training-year.md because NOTION DOES
                           NOT CONTAIN 2025 — the training DB starts 2026-06-29.
                           Lose this file and every index loses its denominator.
  flexibility_baselines.py — the vocabulary SHARED across every cluster: the
                           three measures and their plain-English explanations,
                           the assisted-to-resisted spectrum, the scheduling
                           window, the per-athlete frozen constants, and the
                           provenance of everything measured before the cluster
                           model existed (the Jan-2025 gym goniometry and the 22
                           self-rated pose depths). It holds NO tests, NO
                           exercises and NO prescriptions — those belong to the
                           three layers. Note MEASURE_ORDER is active ->
                           isometric -> passive and is not the order the source
                           documents write them in.
  cluster_a_mechanics.py — Cluster A's WHY: five limiters (the source's four
                           plus the seated-tilt deficit added for this athlete)
                           and the exercise library placed on spectrum zones.
                           Every substitution carries `adapted_from` and
                           `reverts_when`; every deferral carries
                           `deferred_until`. REMOVED records what was taken out
                           entirely and what would put it back, because an
                           unexplained absence is indistinguishable from an
                           oversight.
  cluster_a_battery.py   — Cluster A's slots and their evaluators. Test protocol
                           text is PLAIN ENGLISH by requirement, not by
                           preference: it is read while lying on the floor
                           holding a tape measure, and a test he misunderstands
                           produces a plausible number rather than an obviously
                           wrong one. Anatomy lives in `what_youre_testing`; a
                           test scans the other fields for it.
  cluster_a_prescription.py — pattern label -> ordered stack, plus the mandatory
                           pre-session release block and the dosage rules.
                           References exercises BY NAME from the Mechanics
                           library and defines none of them.
  patient_profile.py    — clinical data; human reference AND, as of the Strength
                           BioAge muscle-imbalance count, actively imported by
                           services/bioage.py (PROFILE["imbalances"], for the
                           muscle-imbalance count)

tests/       — pytest suite (1602 tests), the sole deterministic gate
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
16. **Every user-triggered sync in `views/` runs inside `BackgroundSyncRunner.exclusive()`.** The manual buttons call `Repository.sync_*` directly rather than `run_home_syncs`, so the runner's lock is the only thing that can serialise them against the background chain. Racing does not merely waste API calls, it corrupts rows: `sheets.upsert_row_by_key` is a *find-then-write pair*, so two chains upserting a date not yet on the tab both find nothing and both append, leaving that date with two rows — and the date most likely to be missing is today's, exactly the one both are writing. Sheets' 60-ops-per-minute quota is the second reason; a 429 mid-chain reads as missing data, not as an error. Serialising costs nothing because every button runs the *same work over a wider window* (blend 400d vs 7, fusion 1200d vs 14, Garmin daily 7d vs 2, Oura an identical 7d), so the wider window writes a superset. **Wait (`exclusive()`) for an explicit button press; skip (`exclusive(timeout=0)`, catching `SyncBusyError`) for anything that fires on every render** — `views/training.py`'s Garmin call is the latter, since waiting there would reintroduce the page blocking that `background_sync.py` exists to prevent. `tests/test_manual_sync_serialised.py` enforces this against the source; adding a new sync button without the wrapper fails it.
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
| **⏳ Flexibility: ZERO assessments run** | Open by design, and the only thing between this sector and usefulness. The four-slot battery is built, its early exit is verified end to end, and nothing has been measured. **Run it BEFORE 2026-08-16** — it is measurement, not prescription, and it puts a pattern label in front of the physiotherapist instead of a plan to get one. **Measure COLD.** Every threshold (`GATE0_ORIENTATION_GAIN_CM`, `LEVERAGE_TARGETS`, `TILT_TARGET_DEG`, `SPECTRUM_GAP_CM`) comes from the source rather than from his own spread, which has never been measured; three baseline mornings set the noise floor, and until then `BatteryResult.trusted` is False and the screen calls the pattern a hypothesis rather than a verdict. 2026-08-07, on the athlete's direction: **the tilt is an ANGLE at the pelvis** (phone on the lower back; a rounding spine cannot fake it, so one number replaced the old two), **own-power runs before helped** (help flatters what follows — the slot-3 principle applied to slot 2), and **Gate 0's two-orientation comparison only runs within `GATE0_BONE_RELEVANT_CM` (15) of the floor** — bone meets socket in the last few centimetres of a full split, so above the line `applicable_tests` drops the turned-out attempt and slot 0 passes on the neutral height alone. An old centimetre tilt reading returns `indeterminate` rather than being read against the degree target. |
| **⏳ The cluster session joins the next block on 2026-08-16 — protocol written, not yet executed** | `docs/training/flexibility_integration_2026-08-16.md` (2026-08-07). The blueprint's training rules were already encoded (`flexibility_window`, `FREQUENCY`, `LENGTH`); the protocol governs the BLOCK BUILD: reserve the slot inside the five-per-week ceiling (never author 5 gym days then bolt it on), re-derive placement against the NEW week with **running counted as leg loading**, one new stressor per week (cluster ×1 in week 1; the second weekly session is EARNED by two clean weeks), map every stack/release name into `EXERCISE_MOVEMENT_WEIGHT` + `EXERCISE_BODY_REGION` so nothing falls to the 1.0 default (the Stage 1 bug by another door), judge the Coxa Saltans holds at the same sitting, calendar the mid-September retest, and the pull-back condition is pre-written in the `HRV_GARMIN_HOLD` idiom. 2026-08-07 addition, the athlete's rule: **a retest is never the morning after leg training** — day-before leg work reads as extra tightness in exactly the tested areas, the same contamination class as a warm-up, one day earlier. `flexibility.retest_readiness()`/`retest_due_on()`/`leg_loading_days()` (leg days judged by `EXERCISE_BODY_REGION`, the sectors' own map — one definition of "a leg day" everywhere); surfaced as a training-screen banner the day before (swap prompt if today already loaded legs) and the day of, a due-date line on the flexibility screen, and a warn-never-block notice on the capture cold gate. `RETEST_INTERVAL_DAYS` (28) lives on the Prescription — cadence is dosage. Gate 1647 → 1652. |
| **Frozen constants: two of four are now captured in-flow** | Straddle width (at the tilt, 2026-08-07) and the tailor's heel distance (at the bent-knee leverage, 2026-08-06) are recorded beside the reading as `Reading.setup_value`, and the screen offers last session's number back — THE NUMBER IS THE RECORD. Still uncaptured: the traced side-split stance and the floor reference, which remain setup discipline with no field. `block_height_cm` is deliberately NOT frozen: it is the section-F progression variable and lowering it IS the progress. |
| **The app offers yoga on rest days** | **RESOLVED 2026-08-06.** The Prescription's dosage section settles what this row recorded as open: a cluster session is adaptation-seeking by definition, so `flexibility_window` now returns `poor` for a rest day rather than accepting the flag and ignoring it, and `REST_DAY_CONFLICT_UNRESOLVED` is retired. A restorative yoga flow on a rest day remains fine — that is `services/yoga.py`'s business. Placement is set against the real week: Stage 2A loads legs on days 1, 3 and 5, leaving day 7 clean with day 2 as the same-day-evening fallback. |
| **Cluster B is unbuilt, and its first skill collides on wording** | Open. The blueprint defines Pike as *touching your toes; forward fold* — wording that hits two contraindicated `rules.py` keywords outright. That is a whole-cluster collision to resolve before Cluster B is authored, not after. The same flat-back redefinition that made the pancake trainable is the likely answer, but it needs the same explicit treatment rather than being assumed. |
| **⏳ The InBody bridge scan expires when the gym swaps machines (~Sept 2026)** | **Time-limited, and unrecoverable if missed.** Under the never-pool-two-devices rule a reading on the new machine cannot be compared with the five corrected 2025 scans unless both machines measure the same body the same morning. One visit: confirm **182.0 cm** entered, scan the old 770 **twice ~8 minutes apart** (the only estimate you will ever get of its own test-retest spread — the existing 8-minute pair is confounded by the height re-type), scan the new machine, take a tape baseline, keep the **print-out** not the app summary. Full protocol in `docs/focus.md`. |
| Foryond height corrected 183 → 182 cm on 2026-08-05, history NOT back-applied | Open by design. All 142 stored rows keep 183.0; the next weigh-in steps **BMI +0.27** guaranteed and possibly **+0.9 pp** body fat from the setting alone. **That step is a setting, never fat gain** — the same class of artefact the gym made five times in the other direction. The next reading also answers whether this device uses height in its body-fat model at all. |
| Body-composition accuracy layer deferred to 2027 | Deliberate (user decision, 2026-08-05) — revisit against a year of standardised readings. Design recorded in `docs/resume.md`: weigh 4–5×/week under fixed conditions (**protocol standardisation is worth 24% at zero extra weigh-ins**, against 33% for tripling frequency, and the curve flattens hard past four), a monthly tape as the one fat signal whose errors share no mechanism with impedance, and the training log as a **consistency gate** rather than an input — it cannot produce kilograms of lean mass, and the log records no per-set laterality so it cannot be matched to the InBody's left/right segments. |
| **⏱ Measured RPE runs BESIDE self-reported, not instead of it — revisit 2026-08-16** | Deliberate (2026-08-07), same pattern as `HRV_GARMIN_HOLD`. Every session now yields two intensity figures: the slider (always asked, feeds `session_au` → Strain/ACWR) and an HR-derived RPE from `compute_session_hr` (%HRR, active-time-weighted, feeds **nothing**). Not unified, because rule 2b's hazard is exactly this — a load figure that moves depending on whether the watch was running swings the ceiling on **button behaviour rather than physiology**. Rule 2b also names the exit: *a per-athlete conversion regressed from sessions with BOTH signals*, which is why the rating is collected even on no-Garmin days. **First paired point 2026-08-06: measured 5.2 vs reported 5.0 (333 AU vs 320)** — one point, not a regression. **Lift on the measurement, never on the date**: check n, the bias and the SPREAD of (measured − reported); a wide spread means no single conversion works and the hold stands. Full criteria in `docs/focus.md`. Also check session `hr_coverage` — routinely under ~85% means the watch is started late or stopped early, and the fix is the prompt, not the model. |
| **⚠ ACWR enforcement is HELD — `engine.ACWR_ADVISORY_MODE = True`** | Deliberate (user decision, 2026-08-03), same pattern as `biometrics.HRV_GARMIN_HOLD`: a breach is **reported but never caps volume**, riding beside the biometric directive as `volume_recommendation()["acwr_advisory"]`. **The ceiling is untouched** — `rules.STAGE_CONSTRAINTS` is unchanged and `acwr()["exceeds_ceiling"]` still carries the raw fact, so flipping the flag to `False` restores hard-locking with no other edit. Two tests pin both directions. Lift it once the app is validated against more real training and the other planned engine work lands — **on that work being done, not on a date**. |
| ACWR chronic window is scoped per stage | Fixed 2026-08-03. A flat 28-day window spanning the Stage 1 → 2A boundary divided a training-load acute term by a rehab-load chronic term: **20 of the block's first 30 days breached 1.3 (67%)**, peaking at 1.78 — and the breach barely depended on training. 2026-07-25→27 were three consecutive **zero-AU days pinned at 1.73**, and the scheduled rest day 2026-08-09 projected to 1.54. `engine.acwr(..., stage_start=)` now averages chronic over current-stage days only (`services.plan.current_stage_start` supplies it; `None` during a reassessment gap falls back to the calendar window, and every caller omitting it is bit-identical). Measured effect on 2026-08-03: **1.32 → 0.93**; forward breach rate 62% → 38%, with the remainder landing on Week 4's genuine RPE 6→7 step rather than on the stage boundary. Prior-stage days are **excluded, never down-weighted** — they are the denominator, so ×0.5 moved ACWR 1.32 → **1.50**, the opposite of the intent (`test_downweighting_would_have_moved_the_wrong_way` pins this). Below `ACWR_MIN_IN_STAGE_DAYS` (14) the ratio is reported with status `baseline_establishing` and never locks — a chronic window no longer than the 7-day acute one collapses toward 1.0 by construction. |
| `Training plan/` folder at root | **RESOLVED 2026-08-03** — the directory no longer exists at root; contents live in `docs/training/` |
| Stage 2 training plan | **BUILT — live since 2026-07-20.** `training_plan.PLAN_STAGE2`, a 28-day gym strength block; physio signed off on external load at the Day 21 (not Day 14) reassessment, recorded in `patient_profile.PROFILE["stage_transitions"]`. Day 28 reassessment is **2026-08-16**, where three explicitly deferred decisions land: Stage 2B vs. extending 2A, running introduction, and endurance-biased scapular programming. See `docs/focus.md`. |
| Interscapular endurance gap — deferred to the post-Stage-2A block | Onset **2026-07-16, four days BEFORE Stage 2A began** — the loaded block did not cause it. Bilateral with left dominance (right on 07-16/07-23, left from 07-21), flat at tightness 1-3 / pain 0, no neural signs. Scapular work already runs **five days a week** (Face Pull D1, Lat Pulldown + DB Row D3, Scapular Wall Slide D4/D5/D7, Prone Y-Raise D5) and the symptom persists through it, so the gap is **endurance under sustained low-load holding, not volume** — the same "lumbar endurance low / deep core off under fatigue" pattern from the 2025 log, in a new region. Long isometric holds are a prescription change: **no `training_plan.py` change this block by design**, physio decides at Day 28 (2026-08-16). See `patient_profile.py` `symptom_log` 2026-08-03 and `docs/training/physio_brief_2026-08-16.md`. |
| Garmin HRV is absent, two independent causes | RESOLVED-as-empty (probed 2026-07-31): `get_hrv_data` returns `{}` for this account, so `hrvSummary.lastNightAvg` has nothing to map. Separately, the Garmin Daily tab had been created before `hrv_ms` joined `_GARMIN_DAILY_HEADER`, so every sync wrote it into an unheadered column that `get_all_records` discarded — `services/biometrics.py`'s documented Oura-70/Garmin-30 HRV blend has silently been 100% Oura. The column is repaired (`Repository.rebuild_garmin_daily`); the endpoint may start returning data with a watch that supports HRV status. |
| Garmin backfill | Run `scripts/backfill_garmin_from_sheet1.py` (dry-run first, then `--apply`) once to backfill pre-wearable history into the Garmin Daily tab so readiness baselines aren't starting from empty |
| Quiet-wakefulness rule — measured, then abandoned | **Do not re-attempt without reading `services/sleep_fusion.py`'s docstring.** Best precision ~12% against a 1.9% base rate, i.e. ~88% of flagged minutes would be wrong, and REM is indistinguishable from Awake (both elevated-and-motionless). Probing found no finer HR exists on this account. The blocking problem is not sample size — it is that there is **no ground truth**: validation uses the hypnogram's own Awake labels, but the rule exists to find minutes the hypnogram did *not* label Awake. Needs PSG/EEG ground truth plus beat-to-beat intervals. |
| Movement calibration is n=26 | `Repository.sleep_movement_cutpoints` quantile-maps Garmin's undocumented float onto Oura's 1-4 alphabet from paired nights only; currently 26, floor is 14. The ACTIVE boundary sits far into the tail and is the least stable of the three, which is why rule 7 treats class 4 as corroboration rather than proof. Re-check the fitted values as paired nights accumulate. |
| Metrics History `sleep_score` gap | NOT a population failure — corrected 2026-08-01 by querying the datastore offline. 21 of 34 rows carry a score; exactly 13 consecutive dates are blank, **2026-06-29 → 2026-07-11**, and everything from 2026-07-12 on is populated. An earlier reading of "33 rows, all None" was a throttled Sheets read (429) misread as absent data — the exact failure the offline datastore now prevents. The 13 dates predate the column and would need a `sync_metrics_history` backfill over that window if wanted. |
| Sleep coverage is worn-device-limited, not sensor-limited | Over the 71 nights of the Garmin era the ring recorded 27 nights and the watch 53. Fusing them plus emitting `garmin_only` nights takes stage coverage from 38% to 76% of calendar nights (+217h of sleep Oura never saw). The remaining gap is the 17 nights neither device recorded — no code change reaches those. |
| Sleep Cycle (iOS) export — CONSIDERED AND NOT IMPLEMENTED (closed) | **MEASURED 2026-08-05**, 296 nights 2024-10-31→2026-07-23, 43 paired vs Oura / 11 vs Garmin. It holds wide calendar coverage — **119 nights no device recorded** (corrected 2026-08-05 from 245 once the Garmin duration history was backfilled; see the coverage row below) — and the only acoustic channel. **No channel passed.** Time asleep agrees at bias +0.47h with 95% LoA (−0.50, +1.44) — three times the pre-registered 45-min half-width; everything else fails on bias, LoA or information ratio; staging reads **UNTESTABLE not failed** (n=19). Four structural facts decided most of it before any statistic: `Time in bed` ≡ `End − Start` to 0.00s (a hand-opened recording window, not a measurement) and Awake is its arithmetic residual; `Snore>0` and `Breathing disruptions>0` are the **identical 180 nights, zero off-diagonal** (one detector, two readouts); ambient noise steps ~23.5→~19.5 dB across late 2025 (**two phones — do not transfer a coefficient across it**, same prohibition as 645/265); and all 29 columns are night-level scalars, so nothing can enter `sleep_movement.py`'s 30s grid at ANY agreement level. **The acoustic channel is NOT THE ATHLETE'S**: splitting on whether a night was slept alone or with a co-sleeper present (25 vs 141 nights; classification supplied by the athlete and read from a **gitignored** `Input_files/sleepcycle_cosleeper.json`, since a home location and travel history are identifying details and this repo is public), P(snore>0) is 0.120 vs 0.674, RD **+0.554, 95% CI (+0.316, +0.752)**, holding in both instrument regimes with ambient noise identical within each — and the athlete's own alcohol tag produces no rise. Movement is *not* co-sleeper-contaminated (p=0.42), merely uncorrelated with Oura (ρ=+0.24, CI spans 0). **Nothing in `services/` or `views/` reads any of it**, and per rule 2b + `sleep_fusion.py`'s shadow report, importing 119 uncalibrated nights would raise the 56-night sleep baseline exactly where no device was worn. Against Garmin (n=168 after the backfill) the bias is **−0.73h, sd 0.70** — a SMALLER systematic offset than Garmin-vs-Oura's +1.01h but **50% more night-to-night scatter** (sd 0.70 vs 0.46), which is the comparison that actually matters for substitution. **DECIDED 2026-08-05 by the athlete: stop recording, do not implement.** The measurement's own verdict was the softer 'keep recording, do not ingest' — justified solely by the coverage archive — but once the Garmin backfill cut the unique contribution from 245 nights to 119 (58%→77% coverage) and the 265 arrived, the case did not survive: nothing here beats wearing the ring and the watch. **Do not re-open without new evidence, and note that more nights of the same observational data is not new evidence** — the blocking problems are structural (S1/S2/S4/S7), not sample size. Re-run `scripts/compare_sleepcycle_to_devices.py` (docstring carries the full tables — the CSV is gitignored, so it is their only durable record). |
| **⚠⚠ Garmin reads ~1 HOUR more sleep than Oura, and `sleep_duration_hours` blends them 70/30** | **REPLICATED 2026-08-05 on two independent samples**: +1.11h (sd 0.64) over the 26 `fused` nights, and **+1.02h (sd 0.48, r=0.914, n=57)** over the 2024-11→2025-03 backfill — so this is a stable instrument offset, not sampling noise. Minute-by-minute stage agreement is **52.3% at Cohen's κ 0.178** ("slight"). **The live consequence is in `biometrics._BLEND_FIELDS`:** `sleep_duration_hours` is Oura 0.70 / Garmin 0.30 with a missing source falling back to 100% of the other, so the blended value is Oura+0.31h on a both-devices night, Oura+0.00h on a ring-only night, and **Oura+1.02h on a watch-only night**. That is a step of up to an hour driven by *which device was worn*, feeding readiness Sleep, Sleep Debt and `sleep_score`'s Total Sleep — precisely the "swings on watch-button behaviour rather than physiology" failure rule 2b names, and the same hazard `HRV_GARMIN_HOLD` was created to stop for HRV. **Not yet fixed, and NOT to be fixed by writing the backfilled Garmin durations into the sheet** — that would retroactively move the stored series on ~130 nights. Options are a `SLEEP_GARMIN_HOLD` mirroring the HRV one, or subtracting the measured offset before blending; both need a decision, and the offset is now measured well enough (n=83 across two windows) to make either an act of evidence. Also: never describe a candidate source's offset as an over- or under-estimate without naming the comparator — Sleep Cycle is +0.47h vs Oura and −0.65h vs Garmin. |
| Garmin sleep-DURATION backfill — **COMPLETE 2026-08-05** | `scripts/backfill_garmin_daily_sleep.py` (new): one API call per night vs `sync_garmin_daily`'s four, archives raw payloads to `Input_files/garmin_export/sleep_<date>.json` (same convention as the stages script, so neither re-fetches the other's nights), and writes to the sheet only via a separate zero-API `--to-sheets` pass. **618 nights archived over 2024-10-31→2026-07-28 — every calendar night. 361 carry a CONFIRMED duration, 108 UNCONFIRMED, 149 none.** The unconfirmed 23% matters: an unconfirmed `sleepWindowConfirmationType` is Garmin inferring a window the watch did not clearly observe, so `--to-sheets` writes those as blank rather than as a number. **Stage history is permanently unavailable** (`sleepLevels` on 0/10 probed dates): Garmin keeps the daily total and discards the hypnogram, so the 53 captured nights are all there will ever be. **`--to-sheets` has NOT been run** — see the blend row above; writing these would move the stored `sleep_duration_hours` series on ~360 nights. Note `sleepWindowConfirmationType` comes back **lower-cased** (`enhanced_confirmed`); comparing it against upper-case constants silently classifies every good night as a guess (the first version of the script did exactly that). IP rate limiting is real — two mobile login paths 429'd during the run, though the fallback path completed the span. |
| Coverage over the Sleep Cycle era, now that Garmin history exists | Measured 2026-08-05 over the 631 nights 2024-10-31→2026-07-23. **Garmin (confirmed) 357 (57%), Oura only 65 (10%), EITHER device 368 (58%).** Sleep Cycle covers 296 (47%) and **uniquely adds 119 nights (19% of the era, and 40% of its own nights)**, taking total coverage 58% → 77%. **144 nights (23%) have no record from any source** and nothing reaches them. This corrects the "245 nights no device recorded" figure in the Sleep Cycle row above, which was an artefact of Garmin history never having been pulled — the true unique contribution is 119. Note how thin Oura is here: the ring covers a tenth of the era, so the watch, not the ring, is this project's dominant sleep sensor over 2024-2026 even though the engine weights Oura 70/30. |
| Sheets tabs silently drop newly-added columns | Any tab created before a column joined its `_HEADER` keeps the old header forever — `get_or_create_worksheet` writes row 1 only on creation and `upsert_row_by_key` never touches it, so values land in an unheadered column and `get_all_records` discards them. Bit `hrv_ms` (above) and would have bit the movement columns. `Repository.rebuild_tab(worksheet, header, ...)` re-heads a tab and carries every existing row through; call it after adding any column. |
| Cold app start latency | FIXED 2026-08-01. The startup sync ran before `_bio_rolling`, so every cold load spent ~77s (`sync_oura_all` 50s + `sync_garmin_daily_if_due` 27s) showing "No Readings" to avoid displaying data a couple of hours old — buying freshness with total unavailability. `app.py::_run_startup_sync()` now runs last and reruns once; first paint of real sleep data is **18.5s**. Remaining latency is the Sheets reads themselves. |
| Strain/ACWR history changed on 2026-08-01 — Stage 1 was over-counted | `EXERCISE_MOVEMENT_WEIGHT` covered only `PLAN_STAGE2`'s exercise universe, so **34 of the 63 exercise names in the logged history** hit `content_weighting.UNMAPPED_EXERCISE_WEIGHT` (1.0) — every Supine Knee-to-Chest and Diaphragmatic Breathing drill counted as fully-loaded barbell work. Now 79/79 mapped. Live reads self-heal (multipliers recompute from each day's Sets JSON on every call), so Strain on a pure-mobility day drops ~4.9 → ~2.0. **The already-persisted `Metrics History` strain column does NOT self-heal** — it holds the old inflated snapshots; re-run `sync_metrics_history` over the Stage 1 window if the stored series matters. Correcting it *raised* ACWR 1.23 → 1.44 (chronic 40.8 → 35.0): the old Stage 1 inflation was padding the denominator, hiding how steep the Stage 2 ramp actually is. |
| `bodyweight_compound` is a new weight tier (0.5) | Added for Stage 1's unloaded multi-joint work (Chair Sit-to-Stand, step-ups, lunges, wall sits, Single-Leg RDL). Sits between `isolation` 0.3 and `pull`/`upper_push` 0.7 — scoring a bodyweight sit-to-stand at `squat` 1.3 would be as wrong as the 1.0 default it replaced. `tests/test_movement_weight_coverage.py` pins the ordering and the one-category-one-weight invariant. |
| Baseline-drift guard is dormant until ~mid-Sept 2026 | `engine.baseline_drift` needs `DRIFT_MIN_PRIOR_DAYS` (21) rows *before* the current 28-row window. The ring was worn intermittently before mid-2026, so a 90-day fetch yields only 11 prior rows; `DRIFT_RECOMMENDED_FETCH_DAYS` (400) yields 62 and does fire (HRV −18.7%, sleep −11.4%, severity `severe`). Windows count ROWS not calendar days, deliberately — a calendar window shrinks to nothing across a sparse stretch. Both UI call sites already pass the wide fetch. |
| Historical Notion rows keep their old `movement_type` label | `sessions.movement_category`'s fallback used to swallow every unrecognised name into "Mobility", so Lat Pulldown / Incline DB Press / Single-Arm DB Row / Face Pull / Hip Thrust (Loaded) were all *written* to Notion as "Mobility". Fixed for new writes only — rows logged before 2026-08-01 keep the wrong string. Display-only (nothing computes from it; Strain/ACWR weighting reads `EXERCISE_MOVEMENT_WEIGHT` by exercise NAME), so this is cosmetic and needs a backfill only if the history's labels matter. |
| Readiness rebuilt as `MODEL_VERSION 2` | **RESOLVED 2026-08-01.** v1 read 84.8 where Oura read 57. Cause was not the imported contributors (those matched exactly) but v1's own HRV and RHR components, `min(100, ratio*100)` — **one-sided and saturating**, so any day at/above baseline scored a flat 100 — plus four Oura contributors that were synced and ignored. v2 scores from Oura's eight contributors plus our own Sleep Debt, with our weights and our composite (**not** Oura's score taken directly). Measured over a year: **r = 0.992** with Oura, mean bias −0.9, sd 2.8, 91% within 5 points; v1 ran ~15 points high. Alcohol is no longer deducted — self-reported and invisible to Oura, so scoring it made the two incomparable; `services/scheduling.py` still shifts sessions on consecutive-day alcohol independently. All 52 Metrics History rows re-derived and stamped `readiness_model_version`. |
| Naps are discarded from `sleep_duration_hours` | **RESOLVED 2026-08-03**, with approval, at a 15-minute floor (`biometrics.NAP_MIN_SECONDS`). `split_sleep_periods` now returns (main night, qualifying naps); duration counts both, architecture counts only the night. **23 days move, +14.6 h.** The conflation the old note flagged is now the design and is load-bearing: `sleep_duration_hours` includes naps (readiness Sleep, Sleep Debt, sleep_score Total Sleep), while `oura_sleep_total_seconds` stays the main night because `sleep_score` divides REM/deep seconds by it — unifying the two would silently deflate every REM and deep share on a nap day. HRV/RHR also stay main-period-only. The floor matters: over half the 57 non-main periods run 1-13 min at 2-38% efficiency, and counting them adds 11 days for 2.8 h of ring noise. Metrics History re-derived over 2026-07-17→08-03 only (18 rows); the Sleep Debt window means one nap moves readiness for ~14 days after it (2026-07-21: 39.6 → 52.3). |
| Oura emits DUPLICATE sleep periods, and any sum must dedupe first | Found while adding nap support. Oura re-analyses a night by writing a **second row** rather than updating the first: 8 nights in April 2024 carry the same physical sleep twice under distinct `sleep_id`s — identical bedtime window and `time_in_bed`, totals a minute or two apart, one of each pair often carrying a sentinel `lowest_heart_rate` of 255. Picking one period hid this completely; **summing without deduping reads 2024-04-19 as 14.78 h instead of 7.42 h**. `biometrics.dedupe_sleep_periods` collapses overlapping windows to their longest member and every reader now goes through it. It compares ABSOLUTE INSTANTS, not wall-clock strings — 2024-04-20 stores one period as both `+01:00` and `+02:00`, and string comparison reads that as two naps an hour apart. |
| 36 Metrics History rows predated the background-sync commits | **RESOLVED 2026-08-03**, with approval, via the new `Repository.rederive_metrics_history()`. All 54 stored rows re-derived, 24 changed, **readiness blanked on 16 rows across 2025-09-27 → 2025-10-13** — they held flat-repeated values (91.2 for 11 straight days), the stale carry-forward `adec27d` ("a new day is blank until it has actually been measured") was written to fix, and there is no biometric reading behind them. Nap support moved none of them (verified 0 of 36 before the run). |
| ⚠ A persisted Metrics History value depends on how WIDE the sync that wrote it ran | Found 2026-08-03 during the re-derive, **pre-existing, not fixed.** `sync_metrics_history` fetches `days + 60` biometric rows, so a `days=7` routine sync computes a date against a 67-day lookback while a full re-derive computes the SAME date against a 372-day one. The 56-night progressive sleep baseline and the readiness EMA both read that window, so the two disagree: 2026-07-25 was written 43.3 by the narrow run and 42.9 by the wide one. Only ~0.4 points here, but it means a stored row is not reproducible without knowing the width that produced it, and the 2-hourly `sync_metrics_history_if_due(days=7)` will drift recent rows back toward the narrow-window value. Fixing it means pinning one lookback width for persistence regardless of `days` — do not do that casually, it moves every stored row again. |
| Biomechanical review due | **DONE 2026-07-19** — Day 21 reassessment passed, physio cleared external load, `patient_profile.py` updated and `stage_transitions` appended. **Next review: 2026-08-16** (Day 28), which gates the next block. |
| `training_constants.EXERCISE_BODY_REGION` needs upkeep | Stage 2A's names are all mapped — verified 2026-08-03, 9/9 weighted lifts resolve to a region. The rule now applies to the **next** block: every new exercise name needs an entry here or `services/strength.py` and `services/tonnage.py` silently exclude it from any region (`weekly_tonnage` returns the unmapped names as its second value, which is the cheapest way to notice), **and** an entry in `EXERCISE_MOVEMENT_WEIGHT` or it falls back to `UNMAPPED_EXERCISE_WEIGHT` 1.0 and inflates Strain/ACWR (that one already bit 34 of 63 Stage 1 names — see the Strain/ACWR row below). See both dicts' own comments in `training_constants.py`. |
| Stage-Adjusted Recovery Score retired from the Strength screen | **RESOLVED 2026-08-04.** It was `min(100, current_28d / (best_ever_28d × cap) × 100)` with the current window INSIDE the set its own denominator maximised over, so it could never exceed 1 — it returned a flat 100 for the whole first 28 days of any block and had produced exactly one distinct value (100.0) across all 16 days it existed. Same one-sided saturating ratio readiness `MODEL_VERSION 2` removed. Replaced by `services/strength.py` + `services/tonnage.py`. The seven retired functions and their 17 tests were **deleted** 2026-08-04; `muscle_imbalance_count` is all that remains of the module, and `tests/test_bioage.py` fails if any of the removed names reappear. |
| Overall Strength Score is in CALIBRATION | Every regional index displays at **50** and the overall is held at `strength_baselines.ANCHOR_VALUE` (50, anchored 2026-07-30). The measured indices are computed and returned, just not displayed. Exit is per region on **confidence ≥ 0.70** (`quantity × comparability × consistency`); today upper is 0.46, lower 0.37, core 0.00. Decay is suspended while calibrating. Nothing jumps when it completes — the identity `overall = Σ shareᵣ × indexᵣ` already holds. |
| Core cannot be calibrated at all | Its only loaded movement is Pallof Press and its 2025 peak is recorded as "orange band × 15" — a band, not a kilogram, so `comparability` is 0 and confidence is 0 no matter how much is logged. Core's share runs on `REGION_PRIOR` alone. **The fix is already in the 2025 log:** Copenhagen plank (30s × 3) and side plank + march (15/15 × 3) are both recorded and repeatable, and neither needs a 1RM. |
| No per-set warm-up flag | `services/tonnage.py` counts a set as eligible when it carries reps AND a real external load. Warm-ups are NOT excluded, because the log has no way to mark one — so "working sets only" is an assumption the data cannot currently support. A boolean per set closes it. |
| Unloaded work needs TWO counters, and a hold is not a rep | `services/sessions.py` writes a hold or a timed piece as **reps=1 with the work in `tut`**, so a 60-second plank and one dead bug are both "1 rep". Across `training_plan.PLAN`, holds and durations are **54 of 113 exercises and 11,955 seconds** but only **113 of 1,603 reps (7%)** — summing reps alone misrepresents exactly the work the counter exists to represent. `SectorWeek` therefore carries `unloaded_reps` AND `unloaded_seconds`, and they are **never added**: no exchange rate between a rep and a second is defined here, the same reason a bodyweight hold never becomes kilograms. |
| 0 of 17 e1RM estimates are inside Epley's validated range | Sets are logged at 10-12 reps at RPE 5-6, i.e. 14-18 *effective* reps against a limit of ~10. `services/strength.estimated_1rm` returns a `within_epley_range` flag for this. The fix is a periodic ~5-rep set at RPE 8 per movement pattern, not a constant change. |
| See `docs/REFACTOR_NOTES.md` | Smells/bugs found during the services/ extraction, noted but not fixed beyond what the extraction itself required |
