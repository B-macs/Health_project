# CLAUDE.md — Health Engine

*Last updated: 2026-08-14 — **STAGE 2B IS BUILT AND STARTS 2026-08-17.** `training_plan.PLAN_STAGE2B`, 28 days, registered as **Phase 3 at clinical stage 2** — the block changes, the ACWR/RPE/volume ceilings do not, and `sessions.PHASE_META` says so in one place so "2B" can never be read as stage 3. Block B follows 2026-09-14 → **2026-10-11, which is race day**: two 28-day blocks land the 10 km on Block B's own day 28, and starting on a Monday is what makes both blocks Mon–Sun aligned (`services/plan.py`'s multiple-of-7 invariant) and drops the Ireland trip on days **3–14**, so gym work resumes exactly at the top of week 3. **(1) THE SESSION SHAPE CHANGED**: `[quiet things down] → [load]` becomes `[quiet things down] → [WAKE THINGS BACK UP] → [load]`. Phase 2 is new, mandatory in every session, and was specified FIRST with everything else fitted around it; it is paid for by **restoring** the release block to the 5 minutes `patient_profile.py:439` always specified rather than the drifted 16–22, for a total of **10–15 min, 15 a ceiling**. The raise is an incline WALK, never cycling — the athlete's own 2025 log names cycling as what inhibits the glutes this phase exists to wake. Two corrections rode along: `UPPER_GLUTE_RELEASE` was coded `bilateral` while its own text says *each side*, and the one ≥60 s stretch now runs FIRST. **(2) TWO BLOCKING PREREQUISITES SHIPPED WITH IT, because the block could not run without them.** There was **NO route to a Phase 3 at all** — the begin-block offer was hard-wired to `1 in existing and 2 not in existing`, so from the day 2A lapsed the app would have had no active phase, rendered every day as rest, and silently dropped ACWR's chronic window back to a flat calendar window; `sessions.next_phase_offer` is generic now and takes `length_days` from the authored content. And the **per-set fields** both evidence reviews named as blocking now exist in ONE migration over one set of rows: **`is_warmup`** (excluded from `tonnage.py`, both `strength.py` filters and all three `total_volume_kg` sites via `repository._working_volume_kg`; `actual_sets` deliberately still counts them — volume is a claim about work, a set count is a count of sets), **`rest_taken_seconds`** (stamped in PYTHON at the rest phase's start and differenced at the button press — the timer is a sandboxed iframe that can never hand a value back, so do not try to plumb it), and **`reps_left`/`weight_left`** (the "Edit left side" flow used to overwrite the whole row, so a weaker left arm read as the prescribed weight being declined). **⚠ `rest_taken_seconds` FEEDS NOTHING** — `sessions.REST_TAKEN_FEEDS_DURATION = False`, the `HRV_GARMIN_HOLD` idiom: switching the duration's rest term from prescribed to measured would move Strain and ACWR on *whether the field exists*, putting two units in one ACWR window. Lift it on a measurement, not a date. **THE DEFAULT IS THE LOAD-BEARING PART**: an absent `is_warmup` reads as a WORKING set, because every set logged before this commit has no key and all of them were work. **(3) ONE SAFETY RULE CORRECTED, with the athlete's explicit sign-off**: `rules.py` returned **contraindicated for running at EVERY stage**, because `check_movement` only ever *upgrades* to contraindicated and the rule was already written at that severity — its own `stage_cap=2` and reason text both said the block was meant to end at Stage 2. Now `severity="caution"`. The alternative, naming sessions so they miss the keyword, is the vocabulary failure this repo has already been burned by and was refused. **(4) FOUND BY THE NEW BLOCK'S OWN TESTS, and both are real**: `sessions.RELEASE_EXERCISE_NAMES` was missing `"Right Posterior Hip Capsule Stretch (Revised Cue)"`, so **every Stage 2A gym session has been rendering a release item inside the "Workout" accordion** (display-only, now fixed); and week 4 originally held six sessions against `session_freq_max` 5, which is why **day 27 is a rest day and the block has six runs, not seven** — the day-28 screen should measure the block, not the previous day. **(5) THE TRAVEL FORTNIGHT IS BANDS ONLY** (days 3–14) and needs no engine code: `equipment_type="band"` + `band_tier` on `engine.BAND_TIERS` already existed. Band sets write `weight=0`, so those weeks read **0 kg tonnage with real unloaded reps**, which is true rather than alarming. Band compounds sit at `bodyweight_compound` 0.5, NOT at their loaded tier — scoring a band front squat at `squat` 1.3 would repeat the Stage 1 over-count in the other direction. **(6) RUNNING is six sessions reaching 35 min continuous, deliberately short of the distance** — the left Sartorius has strained twice from running overuse and `clinical_profile_weighting.md` #1 makes that full-weight again the moment a plan re-stresses it. All three run names contain "running" ON PURPOSE so `check_movement` actually fires. **(7) ACWR STAYS ADVISORY THROUGH BLOCK A** (athlete, 2026-08-14): a new phase resets the stage-scoped chronic window, so from 2026-08-30 that window is **12 of 14 travel days** and every returning gym week would divide a real acute average by a band-work chronic mean. Evaluate the hold at Block B, against normal loading. Worth recording separately: for a continuation block inside the SAME clinical stage, resetting chronic at the phase boundary is arguably wrong at all — the original reason for stage-scoping was the rehab→training unit change at Stage 1→2, which does not apply here. **(8) A PSOAS RELEASE WAS MISSING AND NOW EXISTS** (athlete's question, same day). There was none in 2B *or* 2A: Stage 1's three hip-flexor items vanished at the 2A transition with no recorded reason, leaving the **deep hip flexors the only structure on the `overactive_tight` list with no release anywhere in the block** — while the MRI names psoas hypertonicity as what amplifies the L5/S1 compression. `Anterior Hip Pressure Release` joins the release block **from week 3**, one zone, **60 s per side with NO pause between right and left** (athlete's direction), closing the physio's own 2026-08-10 recommendation. Week 3 rather than day 1 because the daily protocol that establishes whether there is anything there to release cannot start until the battery is captured; **off on the day-28 screen**, to keep it comparable with its own history. Measured cost: preparation 11.8 → **13.8 min**, inside the 15-minute ceiling, so **nothing was cut to pay for it** — a trade proposed before measuring turned out not to be needed. **⚠ `pre_session_release` now records the two REMOVALS as well**: the Ischial Tuberosity Hamstring Release (in 2A, out of 2B on the 5-minute budget, physio-confirmed as the right site, owed at the next contact) and the Stage 1 hip-flexor work, each with its revert condition — an unexplained absence is indistinguishable from an oversight. Gate 2691 → 2898. Before that: 2026-08-13 — **REST INTERVALS ARE REVIEWED, AND THE QUESTION RESTED ON A FALSE PREMISE.** `docs/training/rest_interval_evidence_review_2026-08-13.md`, now in Key Rule 11's gate beside the warm-up review, same EVENT-not-date basis. The athlete asked whether rest should go to 3–5 min and whether the right and left sides of a unilateral exercise need a 1-min pause, *"because my current plan only has 45 s to 1 min after doing both sides."* The clock reading is right; the **per-muscle** reading — the quantity every study measures — is not. **`views/training.py:3527` has NO rest timer on the right→left transition**, so the other side's working time IS the first side's rest, and actual per-side rest is **75–105 s**. (1) **Both proposals are refused on evidence and priced in minutes.** The split costs **+9/+9/+11 min per session** to buy a pooled non-local-fatigue effect of **SMD −0.02 [−0.14, 0.09]** (Behm 2021, 52 studies — strength subgroup **+0.11**, nominally *better*), and crossover fatigue is **cumulative**: Doix needed TWO 100-s maximal bouts to move the resting limb, one 30-s effort did nothing. 3–5 min costs **+23.5 min** against guidance that has been withdrawn — **ACSM 2026's umbrella review (137 SRs, >30,000 people) grades inter-set rest "does not impact" strength and issues NO prescription at all**, and the famous "3–5 min" sits in ACSM 2009's *Summary* with **no evidence grade**. (2) **ONE change is supported: 90 s → 120–180 s on Goblet Squat and RDL, Stage 2B only, when the load is actually near-maximal** — Grgic 2018, and it does not apply at 12.5 kg and RPE 6. **90 s is the ceiling in the whole repo**, 4 of 117 values. (3) **The decisive argument is that the mechanism cannot operate here at all**: the entire "longer rest preserves reps" literature uses **sets to failure**, and at RPE 5–6 with a prescribed rep count there is no rep to lose — the cost surfaces as **RPE instead** (Farah 2012). Which is why (4) **a second per-set field now blocks the next block beside the warm-up flag: the rest actually taken.** `session_au` is computed from RPE, so an unlogged rest change moves Strain and ACWR with **no change in work and nothing in the data able to separate the two** — key rule 2b by another door. **Do both fields in one migration.** (5) **Two things found in the tree while pricing it, recorded not fixed:** `estimate_duration` **never reads `laterality`**, so every gym session's estimate omits the second side (**5.5–6.9 min each**; 35–40 shown against ~41–47 real) — which makes the warm-up review's 10–15 min preparation lock **better** supported, not worse, so **do not re-open it**; and coded rest is already 13.0–16.5 min per session. (6) **⚠ Read §2.4 before dosing the Stage 2B isometric holds** — at matched loading time **four 3-s contractions beat one 12-s hold (+57% vs +25%)**, intensity not duration is the variable, the 45-s hold is **n=6 about analgesia** with three failed replications (one **n=91 outright null**), the 30-s hold is **n=1**, and the target tissue is not a tendon but perfusion-limited left trapezius, where sustained low-level contraction is the *provocative* mechanism. A Day 28 question for the physio; **not** a re-opening of the release-block dose, which is closed. (7) **§1.9 records one FABRICATED paper and two miscited claims circulating on this exact topic** — a "36 amateur bodybuilders, 60/90/180 s" trial that does not exist (and is the only study that would answer the question), an AHA-2024 claim absent from its source, and Fink 2018 / Senna 2011 / Jukic 2020 each quoted for the opposite of what they report. **Nothing in `training_plan.py`, `services/` or `views/` is changed by any of this** — it is a review, and the gate is unmoved. Before that: 2026-08-10 — **STRAIN IS NOW LOCALISED**, and the first thing to read is what the measurement said before any of it was built. (1) **The log curve destroys proportionality**, which is the one thing the athlete asked for: on his own hike example an intended 16:1 lower:upper split displays as **2.34:1**, because `load_to_strain` is `21·ln(x+1)/ln(601)`. So **the AU share leads and the strain triple follows** — share is exact, additive, and is what "adds proportionally more to the lowerbody" is actually a statement about. The three 0-21 values are secondary readings, each necessarily **bounded above by the overall** (regional AU ≤ total AU, curve monotonic), so a region can never read higher than the headline; they total 30.1 against 14.5 on a real session, and `additivity_gap()` is the only place they are ever added. (2) **Per-region ACWR was degenerate and is now floored.** Measured directly against `engine.acwr`: a region whose entire in-stage load is one session reads **3.00, overreach_risk, `baseline_established=True`** — and reads the identical 3.00 whether that session was 300 AU or a **1.5 AU wall slide**, because the ratio is scale-free and `ACWR_MIN_IN_STAGE_DAYS` counts CALENDAR days, not days *that region* was loaded (if all in-stage load lands in the acute window the ratio is exactly N/7, independent of AU). `REGION_ACWR_MIN_LOADED_DAYS` (8) and `REGION_ACWR_MIN_CHRONIC_SHARE` (0.10) withhold the ratio and report the facts instead. It does **not** bite his real pattern — over the 28 days to 2026-07-31 his regions were loaded on 19/18/13 days — and that pattern is the reason to build it: **upper body read ACWR 1.87 while the headline read 1.40**, ramping at nearly twice its own baseline, with the interscapular symptom's onset at 2026-07-16. (3) **Distribution, not one-primary**, on the athlete's decision, and it earns its keep: on session 2026-07-30 core goes 8.7% → 23.1% of the day, because a session of RDLs, split squats, hip thrusts and side bridges plainly loads the trunk more than a ninth. `EXERCISE_BODY_REGION` is UNCHANGED and stays — tonnage needs one sector or kilograms become fictional, strength needs one region per 1RM, and `flexibility.leg_loading_days` reads it as the boolean that sets the retest calendar — and the two maps are bound by an **argmax test** so they cannot drift. (4) **An unmapped name is `unattributed`, never spread and never zeroed**: spreading it would assert a yoga pose loaded upper body, and three zeros beside a real strain number would say the body did nothing. A yoga day reads 100% unattributed with its pose names listed, which is also the cheapest way to notice the gap. (5) **Reconstructed exercise time covers only ~50% of elapsed session time** (measured across all 23 logged sessions: 50% overall, range 6%–565%) — `day_content_multiplier` is immune because it is a ratio, a SPLIT is not, so `attributed_fraction` is reported and the panel says when it is thin. Nothing is persisted (the weights are invented and will be revised; a stored column derived from constants you expect to change is the does-not-self-heal failure that bit the Stage 1 over-count), nothing is added to `compute_daily_metrics_snapshot` (its key set is pinned by three consumers — `compute_region_strain_snapshot` is a sibling), and **the Home page is untouched** on the athlete's instruction: card, `_home_css`, Readiness and Sleep all unchanged, with `_SKIN_HOME`/`_SKIN_BOARD` making the palette switch apply to the strain view alone. `tests/test_strain_overall_unchanged.py` was written and committed against the tree BEFORE any of this and is the acceptance criterion: every pre-existing strain number and key is bit-identical. Gate 1811 → 2437. **Also found while planning and NOT fixed — see Known Open Issues: `sync_session_hr_for_date` has never run, so the Session HR tab is empty and strain has been 100% RPE-derived on every day that has ever existed.* 

*2026-08-07 — the battery's first contact with the athlete produced four corrections, all his, all now in code: **(1) the tilt is an ANGLE at the pelvis** (phone flat on the lower back, degrees between sitting tall and deepest tip; unit `°`, bigger-is-better, `TILT_TARGET_DEG`) because forehead height is exactly the number a rounding spine can fake and his rounding is the documented compensation — one number replaced the protocol's two, and an old centimetre tilt reading returns `indeterminate` rather than being read as degrees; **(2) own-power runs before helped** in slot 2, the slot-3 principle (help flatters what follows) applied consistently, stated by him as a requirement; **(3) Gate 0's two-orientation comparison only runs within `GATE0_BONE_RELEVANT_CM` (15 cm) of the floor** — bone meets socket in the last few centimetres of a FULL side split, so at his height the comparison answers nothing, `cluster_a_battery.applicable_tests(draft)` drops the turned-out step live (the view asks it, never re-implements it), and slot 0 passes on the neutral height alone with the skip's reason on screen; **(4) the straddle width is captured beside the tilt reading** (`Reading.setup_value`, same as the heel distance) and the screen offers last session's number back — the setup number is the SAME number every session by design. Also: every test now carries an `input_hint` ("floor to crotch, in cm") rendered AT the input; the Expected-outcome expander is off the screen on his request (the prediction stays in `EXPECTED_PATTERN` — its job is to exist before measuring, not to prime the measurer); and the flexibility screen's captions were unreadable (10px `#5A6377` on near-black) and now override to readable ink. Gate 1613 → 1626. Same day, second pass: **the Prescription's stacking rules are now tests, not prose** (`tests/test_cluster_a.py` "stacking rules" section — isolated-before-integrated with §G/§H's door-opener exemption pinned to their own text, full position last for §B–§E and §G, §F's no-finisher design pinned WITH its reason, bent-before-straight except §E, triangle-before-inline, the per-stack limiter story, the 5-item ceiling), because the audit that prompted them found **§A transcribed in the wrong order** — the Python ran triangle before the ER hold, inverting the source document's own sequence; restored, ER hold first. Gate 1626 → 1634. Third pass, on his review of the §F walkthrough: **every library exercise now says HOW, not just why** — five mandatory patient-facing fields on `cluster_a_mechanics.Exercise` (`position`, `movement` incl. what actually resists you, `feel`, `stop`, `progress`), all 31 entries authored, jargon-scanned AND hedge-scanned (his wording rule: never "it doesn't matter which" after offering options), rendered on screen ahead of the why (`note` demoted to a caption). The complaint that drove it: straddle lift-offs and the flat-back hinge were indistinguishable from their text — now pinned distinguishable (lift-offs name the resistance as his own tissue, not gravity; the hinge states STANDING, a position the old note never gave at all). The mechanics md records that the how-to text is code-authored. Gate 1634 → 1639. Fourth pass: **THE LADDER** — the athlete asked for per-muscle 0-100 scores, which is v1's refuted shape (his own words killed it: *"my flexibility score is nearly 80 for hips"* while the hips were stuck), so what shipped is the honest form he approved: `services/battery.LadderRung` + `cluster_a_battery.ladder()`/`LADDER_INFO` render the battery's decision path as seven rungs, tightest at the bottom, the working rung = the battery's first failure (the ladder DISPLAYS the decision, never makes one). Each measured rung shows its reading, its NAMED denominator and a %-of-target bar; the invented targets stay flagged provisional, while strength-at-depth divides his own isometric by his own passive (relative) and openers divide the active sum by the 180° geometry of a full split. **An unmeasured muscle has no number — None, never zero** — and Keep-going readings surface as "context, not diagnosis" without moving the pattern; Pattern C marks both leverage rungs limiting at once. No aggregate exists, pinned by test. Gate 1639 → 1647 (5 of those skip in a checkout without `Input_files/`). Before that: 2026-08-06 (second pass) — FLEXIBILITY was rebuilt AGAIN, and the churn is the thing to read first: **three models in two days, and the first two are deleted.** v1 scored `sqrt(RANGE x CONTROL)` across eight body regions and the athlete refuted it in one sentence — *we know my hips are stuck in flexion with my back arched, and yet my flexibility score is nearly 80 for hips* — because the hip average buried the one test of his worst capacity. v2 replaced regions with skills and scored `skill = min(rungs)` over fourteen rungs. **v3 is not a refinement of v2**: three new source documents describe a four-slot BATTERY that runs in order and STOPS AT THE FIRST FAILURE, emitting a single pattern label A-I and, in the source's words, nothing else. A decision tree with early exit and a scoring function over everything are different programs — a failing slot 0 does not make the slots below it lower priority, it makes them MEANINGLESS, because a bony block makes the tissue questions unanswerable. `tests/test_cluster_a.py` fails if any of the eleven deleted v1/v2 symbols reappear (`band_score`, `CONTROL_BAND`, `rung_score`, `score_skill`, `SkillScore`, `WIDE_GAP_POINTS`, `RUNGS`, `SKILLS`...). Nothing was lost either time: no assessment had ever been run, and none of Cluster A's measurements were implemented by any v2 rung. **THREE LAYERS, ONE DIRECTION, ENFORCED BY FOUR GUARD TESTS** in the idiom of `tests/test_no_streamlit_in_services.py`: `cluster_a_mechanics.py` (WHY — limiters and the exercise library; no tests, no doses) -> `services/battery.py` + `cluster_a_battery.py` (HOW TO TEST — four slots; names no exercise) -> `cluster_a_prescription.py` (WHAT TO DO — pattern in, ordered stack out; names exercises but DEFINES none, and every name must resolve in the Mechanics library). The fourth guard: **`prescribe(None)` raises rather than guessing** — a prescription without a pattern is a guess, say so rather than guessing — and the refusal names the next action. **The capture flow stops too**, asking the real battery after every step rather than re-implementing the rule, so the screen and the engine cannot disagree; failing gate 0 ends the session after two readings instead of eight more that cannot be interpreted. A third outcome beside pass and fail is `indeterminate`: **a measurement not taken is not evidence of health.** THE FIFTH LIMITER is this athlete's dominant one and is the claim the cluster rests on, in his words: *the lumbar issue is driven from the specific tilt deficit, which needs a specific flexibility training method to fix it.* **The lumbar rounding is the COMPENSATION, not the problem** — he rounds because the pelvis will not rotate forward in sitting (straddle 25/100, reported in four seated positions, 2026-08-05). So section F was REBUILT rather than filtered: pelvic rock for the movement in isolation, elevated flat-back hinge (the elevation IS the assist), straddle lift-offs for production, flat-back hinge to raise the hamstring ceiling. **Success is the block coming down, not the reach going further.** `EXPECTED_PATTERN` is F, written into the code BEFORE measuring so a borderline reading cannot be read toward the answer already in mind — and it disagrees with the generic lax-tissue prediction of H/I, which is worth watching rather than resolving in advance. Also now tests rather than comments: **measure order is active -> isometric -> passive** (passive work leaves tissue looser and flatters everything after it); an isometric reading as deep as passive means the load was too light and the slot reports a botched measurement rather than a gap of zero; **load and measurement are ONE DATUM**; three baseline mornings before a number is trusted, and a change under ~2x the observed spread returns not-a-result rather than a delta; the worse side decides, never an average. `services/rules.py` was the BLOCKING PREREQUISITE and had three defects — 78 movement names from these documents produced 8 matches, 70 `unknown` (which is not a block), and ZERO of the 14 contraindicated-on-mechanism movements caught by the rule written for them. **Vocabulary**: the rules speak movement descriptions, the documents speak skill names — `Straddle Forward Fold` was contraindicated while `Pancake`, the same movement, was unknown. **Punctuation**: `good morning` is not a substring of `good-mornings`, so a loaded lumbar-flexion movement over two annulus tears returned `unknown` — one hyphen between a hard block and silence. **False clearance**: *hands walking forward* matched the `walking` CLEARED rule and returned an affirmative low-impact-movement verdict on the most flexion-loaded item in the set; cleared rules must now HEAD a name, token-wise and plural-tolerant. The three documents are ADAPTED IN PLACE for this body (they are gitignored clinical material), each change carrying its REVERT CONDITION in the `HRV_GARMIN_HOLD` idiom — held on evidence, not deleted. Two adaptations cost nothing because the source supplies them: gate 0 and every triangle side split cue from EXTERNAL ROTATION rather than a lumbar arch (*neither is more correct; both align the joint identically* — one arch cue had propagated into nine prescription instances), and the nerve check became a differentiator rather than a provocation, which the battery's own footer already demanded. Horse stance and Cossack are deferred past **2026-08-16** because an open Stage 2 exit criterion is no-increase-in-Coxa-Saltans-frequency under loaded squat/split-squat work, and two new ER-cued loaded squats would confound the criterion he is about to be assessed on — a measurement cost as much as a safety one. Every stack is prefixed with `patient_profile`'s pre-session release block, which all nine source stacks omitted entirely. `scripts/check_cluster_documents.py` runs every movement NAMED in the three documents through `check_movement` at the live stage — 77 of them, all cleared or caution — extracting structurally rather than by a word list that would fail open when stale. `REST_DAY_CONFLICT_UNRESOLVED` is RETIRED: a cluster session is adaptation-seeking by definition, so a rest day is now the worst window. Gate 1584 -> 1602. Before that: the Metabolism BioAge screen shipped: `services/body_composition.py`, `body_composition_baselines.py` and `views/insights.py::_render_metabolism_detail`, with `docs/resume.md` gaining a BODY COMPOSITION section for its locked decisions. Two devices are kept in permanently separate lanes — a Foryond scale whose fourteen columns are one measurement (its body fat percent is fitted from weight and age at R^2 0.9966) and an InBody 770 whose five scans were run against four different typed heights, corrected by `InBodyScan.at_height`. Gate 1475 -> 1515. Before that: documentation refresh across `docs/` (focus.md, resume.md, playbook.md, progress.json, INVENTORY.md, training/Training_System.md), which had all still described Stage 1 as the current stage five weeks after Stage 2A started on 2026-07-20, and still gave the gate as `python tests.py` → 141/141. Four Known Open Issues rows below were also false and are corrected: the Stage 2 plan is built, the `Training plan/` duplicate is gone, the biomechanical review was done 2026-07-19, and Strength BioAge is no longer dormant. Before that: adding NAP support — `biometrics.split_sleep_periods`/`dedupe_sleep_periods`/`NAP_MIN_SECONDS`, the Day-total panel on the Home Sleep drill-down, and the duration-counts-naps / architecture-does-not split that `services/sleep_score.py` depends on. Before that: body-temperature deviation as a fourth `engine.traffic_light` metric (absolute °C cut points, not a rolling baseline), the `engine.baseline_drift` guard, full Stage 1 coverage in `training_constants.EXERCISE_MOVEMENT_WEIGHT` (Strain/ACWR were counting rehab drills as loaded lifting), and the `sessions.movement_category` mislabelling fix. Before that: Oura+Garmin MOVEMENT fusion (`services/sleep_movement.py`, the movement tick strip on the Home Sleep drill-down, `sleep_fusion.RULES_VERSION` 2's movement-aware staging rules, and the Oura `movement_30_sec`/HR/HRV and Garmin `sleepMovement`/HR/stress columns). Before that: Oura+Garmin sleep-stage fusion (`services/sleep_fusion.py`, the Garmin Sleep Stages and Sleep Fusion tabs, Garmin 429 backoff + circuit breaker). Previously: heart-rate-derived strain (`services/hr_load.py` — Edwards' TRIMP — and `services/hr_matching.py`), true per-set training capture, readiness-based auto-shift session scheduling (`services/scheduling.py`), double-progression weight/rep tracking, weekly tonnage (`services/volume.py`), Sleep Debt scoring, and the per-night wake-time adjustment.*

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

Expected: **2898/2898 passed** (or higher — this count grows as tests are added; treat it as a floor, not an exact match. Measure the number for a commit message against the committed tree only — a shared working tree can carry another session's uncommitted tests. Re-measured on 2026-08-14 after the Stage 2B build (+194: the block's own invariants, the per-set fields, the phase route, and the parametrised coverage tests that pick a new plan up automatically). **A CONCURRENT SESSION IS THE NORMAL CASE, not the exception** — a reading of 2686 taken minutes earlier was correct for its own commit and looked like flakiness until `git log` showed another session had landed `tests/test_no_replay_unsafe_cached_elements.py` (+5) in between. Before diagnosing a changed count as non-determinism, run `git log --oneline -4`.)

- Never delete or weaken a test to make the gate pass.
- Never weaken a `services/rules.py` guardrail.
- If you add new engine/stats/rules logic, add a corresponding test.
- `tests/test_no_streamlit_in_services.py` enforces that `services/` never imports `streamlit` — don't weaken it either.

---

## Definition of Done

A change is complete when:

1. `python -m pytest tests/` → passes at the current floor in "Deterministic Gate" above (or higher if new tests were added)
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
                    rest of that calendar week — plus SESSION_PRIORITY
                    (test > main > stretch > rest, the one ranking table) and
                    missed_reschedules: a session missed earlier this week
                    carries onto a later same-week day of STRICTLY lower
                    priority by SWAPPING day-numbers, so the displaced
                    session becomes the missed one; spacing rules keep mains
                    non-adjacent and off the day before a test; a miss with
                    nowhere to go is dropped visibly, and nothing ever
                    crosses the week's Sunday. ASK-FIRST, the athlete's
                    rule: NO proposal that moves a session is ever written
                    without an explicit confirmation button press, however
                    loudly the readings argue — has_real_move draws the
                    line, only no-movement records (holds, drops, declines)
                    persist unasked, and declined_entries remembers a "no"
                    so the prompt never nags. The rule cuts both ways:
                    manual_swap_blockers/warnings/entries let the athlete
                    swap ANY other in-phase day with today from its
                    day-strip view — a past missed day carried forward OR a
                    future day pulled in ("Do this session today");
                    structural impossibilities block, the automatic path's
                    priority/spacing rules demote to warnings, and the
                    logged check uses the PLAN-day yoga-excluding set so a
                    yoga session never blocks the athlete's own tool) ·
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
                    strain_regions.py (STRAIN, LOCALISED to upper_body/core/
                    lower_body — additive information beside the headline,
                    never a re-derivation of it. THE SHARE IS THE ANSWER AND
                    THE STRAIN IS THE SCALE: engine.load_to_strain is a log
                    curve, so three regional strains never sum to the overall
                    (a hike's intended 16:1 lower:upper reads 2.34:1 once
                    through it), which is why the AU share — exact, additive,
                    and the quantity "proportionally more" is actually about —
                    is what leads. The strain triple is three secondary
                    readings on the familiar 0-21 scale, each bounded above by
                    the overall, and additivity_gap() is the ONLY place they
                    are added. An unmapped exercise name goes to an explicit
                    `unattributed` bucket and is NAMED — never spread across
                    the three (that would assert a yoga pose loaded upper
                    body) and never zeroed; a session where nothing maps has
                    regions_known False and callers must render "—". Mass is
                    weighted by seconds x movement_weight, which IS
                    content_weighting's own numerator. Per-region ACWR is
                    three DELEGATED engine.acwr calls plus a loaded-day floor
                    the global one does not need, and hard_locked is forced
                    False unconditionally — a source-level test pins that
                    engine.py and rules.py cannot import this module) ·
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
  training_plan.py      — PLAN (Stage 1) · PLAN_STAGE2 (2A) · PLAN_STAGE2B (2B,
                           Phase 3, starts 2026-08-17). `_ex(warmup=True)` marks a
                           RAMP exercise: authored as its own entry beside the lift
                           it prepares, not as the first N sets of it, so the guided
                           flow needs no per-set weight machine and the athlete SEES
                           the ramp in the timeline.
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

tests/       — pytest suite (2691 tests), the sole deterministic gate
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
- **Notion is covered too, as of 2026-08-11 — offline now means offline.**
  `Repository._query` is the Notion analogue of `_ws()`: all 29 Notion reads
  already went through it, so `clients/notion_reader.py` slots in behind one
  branch rather than a rewrite of forty getters. It returns PAGE-shaped
  dicts, duck-typed against `notion.query_database` exactly as
  `OfflineWorksheet` is against gspread, so `notion.get_property` stays the
  one place a Notion property is decoded and the two lanes cannot drift.
  Measured 2026-08-11 over 13 representative reads: **8,884 ms live → 38 ms
  offline (232×)**, with **zero field mismatches** across all 24 shared
  readiness dates and all 29 shared sessions (per-exercise set counts and
  volumes included). Notion's query language is huge; these four databases
  use five operators (`equals`, `on_or_after`, `on_or_before`, `is_empty`,
  `is_not_empty`) over five property kinds plus `and`/`or`. That closed set
  is implemented exactly and **anything outside it RAISES** — a silently
  ignored filter returns every row, which reads as a successful query over a
  wider window. `get_raw_sheet_rows()` (Sheet1 raw passthrough) still raises
  offline — the datastore holds Sheet1 mapped.
- **Notion WRITES raise offline** (`Repository._nc`), matching the Sheets
  contract. Reading a local snapshot while writing to the live backend is
  the worst of the three options, and it is the one that became possible the
  moment reads stopped going to Notion.
- **Adding a tab means adding a row to `_DATASTORE_TABLE_BY_TAB` AND a table
  to `datastore_schema.sql`**, or offline reads of it return `[]` forever.
  The Notion equivalent is `notion_reader.PROPERTIES` — a property Repository
  reads but that map does not carry reads as `None` offline, i.e. as data
  that is simply absent, with no error anywhere. `tests/test_notion_reader.py`
  scrapes `repository.py` for every `get_property` call and fails on any that
  is unmapped, so the two cannot drift silently.

## Cache mode — the HOSTED runtime (added 2026-08-12)

*Key rule 18 says the app runs on a hosted server. That needed a third mode,
because the two that existed were mutually exclusive: `datastore_path` unset
meant live reads (~8,884 ms) and live writes; `datastore_path` set meant local
reads (**32 ms**) and writes that RAISE. A server wants local reads AND live
writes — the combination `clients/datastore_reader.py` calls "worse still".*

**`HEALTH_DATASTORE_MODE=cache`** (default `readonly`, so every existing
checkout, script and test is unchanged). It is safe where a snapshot is not,
because the cache is **WRITTEN THROUGH, not merely refreshed**: every write
lands in the local copy synchronously, in the same call as the backend write.
Measured end-to-end on the real datastore: reads **30.9 ms**, and a written
row — through both the Sheets seam and the Notion three-table fan-out — is
visible to the very next read.

- **Why a snapshot was refused and this is not.** Stale cache + live writes
  means a logged session the next page has never heard of, so strain, ACWR and
  tomorrow's prescription compute from data already wrong — no error, entirely
  plausible numbers. Write-through removes exactly that.
- **The rows already existed.** Every write fans into `supabase_store.OUTBOX`
  in datastore-row shape, so the cache is a SECOND sink for the SAME rows.
  `clients/datastore_writer.py` applies them through the same three modes, and
  SQLite's `ON CONFLICT DO UPDATE` has PostgREST's merge-duplicates semantics
  — verified: a partial upsert leaves unnamed columns alone.
- **A failed cache write RAISES**, unlike a failed Supabase flush. A mirror
  falling behind leaves a replica stale; the cache falling behind leaves the
  thing the app READS FROM disagreeing with the system of record.
- **Write-through bumps `sheets.bump_write_generation()`**, process-wide.
  Per-instance invalidation would not do — the background sync writes through
  on its own `Repository` (key rule 12) while the script thread holds its own
  read cache and is the one about to render the number. Relying on the live
  Sheets write to bump it as a side effect would leave a NOTION write-through
  invisible to the next read.
- **Two handles per tab**: `_ws()` returns the offline read handle, and
  `_write_target()` resolves the LIVE tab for writes. One object doing both
  would hide which side of the split a call was on.
- **`repo.get_repository()` hydrates a missing cache from Supabase**
  (`datastore.ensure_local_cache`) before anything can read through it — a
  hosted redeploy wipes the disk, and an empty datastore returns `[]` rather
  than raising, so the app would render as though nothing had ever been
  logged. An EXISTING cache is never silently replaced; refresh it
  deliberately with `scripts/pull_datastore_from_supabase.py`.
- **⚠ Nothing inside `get_repository()` may call `st.toast` (or
  `st.chat_input`) — fixed 2026-08-13, and it took the hosted app down.** A
  cache-decorated function RECORDS the st elements it emits and REPLAYS them on
  every later cache hit, and the replay seeds its DeltaGenerator map with the
  main and sidebar containers ONLY. Toast renders on the EVENT container, so
  the lookup raises `KeyError` and Streamlit re-raises it as
  `CacheReplayClosureError` — at `app.py`'s first line of work, on the SECOND
  script run and every one after. **The failure is shaped to hide**: it fires
  only where the hydration actually runs (cache mode, after a redeploy wiped
  the disk), i.e. only on the hosted deploy and never in a local checkout; the
  first paint looks healthy and the first navigation dies, which reads as "the
  Training page is broken" when nothing in `views/training.py` is involved. The
  notice is now recorded by `repo.pop_cache_hydration_notice()` and rendered by
  the CALLER. Ordinary elements (`st.warning`, `st.write`) replay fine — this
  is not a general ban on drawing from a cached function.
  `tests/test_no_replay_unsafe_cached_elements.py` AST-scans the whole app for
  the pattern, because no local run reproduces it.

## Supabase — a live MIRROR, never a read path

*Added 2026-08-11. Notion and Sheets are still the system of record and
**nothing reads from Postgres**. This runs the new write path beside the old
one, the same staging idiom as `HRV_GARMIN_HOLD`, ACWR advisory mode and
measured-RPE-beside-self-reported: switch on evidence, not on a date.*

**Reading from Postgres was measured and REJECTED.** All 22 tables: SQLite
**32 ms**, PostgREST **4,284 ms** — 132×. The cost is *latency, not payload*:
a single round trip is **~136 ms** and a 2-row table times the same as a
600-row one. Live Notion+Sheets is 8,884 ms for 13 reads, so Postgres would
be ~2× faster than today and **113× slower than the local datastore**. So:
**Postgres holds the truth, SQLite serves the reads.**
`tests/test_supabase_mirror.py` fails (AST-matched) if `repository.py` ever
calls a read method on the Supabase client.

- **One write seam.** All eleven upsert-by-key call sites go through
  `Repository._upsert_sheet_row`, which writes the tab and queues the same
  row for Supabase — the same shape as `_ws()` for Sheets reads and
  `_query()` for Notion reads. A source test fails if a twelfth direct
  `sheets.upsert_row_by_key` appears, because that row would be written and
  never mirrored.
- **Buffered, not per-row**, for the 136 ms reason above: rows accumulate per
  table and flush in ONE request each, at the END of `run_home_syncs`.
- **The sheet header IS the column list.** Already load-bearing —
  `services/datastore.py` inserts `_read_records` output straight into these
  tables — so a mirrored row is the header zipped onto the values just
  written. A positional list would shift every value one column left the
  first time a column was inserted.
- **A flush NEVER raises**, and drops its rows on failure rather than
  retrying forever (a `Repository` lives for a whole Streamlit process; the
  full push is the repair path). The Sheets write it mirrors has already
  succeeded, so failing a sync over an unreachable replica trades a working
  app for a consistent copy nothing reads. Failures land on
  `Repository.mirror_last_error` — a mirror that quietly stopped working
  looks exactly like one that is up to date.
- **Partial upserts are safe, verified live**: `resolution=merge-duplicates`
  with a subset of columns updates only those columns and leaves the rest
  alone (checked against a real row — `readiness_score` survived a
  `strain`-only write).
- **The Notion BIOMETRICS database was RETIRED 2026-08-12.** It held ten pages
  with every column NULL — including `date`, its primary key — and had no live
  writer, so the Multi-Week Trend Analysis panel that read it had always
  reported "Biometric days available: 0" and refused to compute.
  `get_macro_trend_data` now reads the **Oura+Garmin blend** (key rule 4's
  actual biometric source, same eight fields): 49 days instead of 0, so that
  panel computes for the first time. `NOTION_DB_BIOMETRICS` is no longer read
  by `config.py` — an existing secrets.toml can keep or drop it freely. Three
  Notion databases remain: Readiness, Training, Config.
- **Notion writes mirror too, via `mirror_notion_write`**, which decodes the
  property payload with `notion_reader.row_from_properties` — the inverse of
  the same `PROPERTIES` map the offline reader uses, so a column cannot be
  read from one place and written to another. **Mirror the PROPERTIES, never
  the record**: that is what makes a checkbox 1/0 and a multi_select a JSON
  array *string* for free, because the decoder applies the getters' own
  conventions. Mirroring a `CheckInRecord` would send Python bools into
  BIGINT columns.
- **⚠ Three Notion-specific hazards, all found by audit rather than by
  running it, none of which raises:**
  - **A partial update PATCHes, it never upserts.** `merge-duplicates`
    INSERTs when the key is absent, so mirroring an AI note update against a
    page logged before the mirror existed would create a `training_exercises`
    row holding four AI columns and NULL `session_id`, `movement_name` and
    every set — indistinguishable from a real logged exercise to anything
    counting rows. PATCH changes nothing when the row is absent; the full
    push backfills history.
  - **One training page spans THREE tables.** Notion stores a session flat,
    so `session_duration_minutes`/`session_rpe`/`session_au` decode out of an
    *exercise* payload, and `"Sets"` maps to `_sets_json`, which is **not a
    column of anything**. Posting the decoded row whole is a 400. A test
    asserts every mirrored key is a real column of its table.
  - **`actual_sets`/`total_volume_kg` have no Notion property** — they are
    derived on read, and are recomputed at the write site using
    `get_all_training_exercises_raw`'s own expression.
- **`training_sets` is REPLACED (delete-by-`exercise_id` then insert), never
  upserted**: its primary key is a surrogate the writer never supplies, so
  `merge-duplicates` has nothing to conflict on and every re-log would
  duplicate every set. A Notion write always carries the COMPLETE set list,
  which is what makes replacement faithful. **An empty list still deletes** —
  it means the exercise now has no sets. Verified live: re-logging with one
  set left one row, not three.
- **Parents flush before children** (`LOAD_ORDER`), because the foreign keys
  are enforced in Postgres.
- **`update_readiness_ai` needs its date passed in.** `readiness_checkins` is
  keyed by DATE while that method is handed a Notion page id, and there is no
  page-id→date index; the caller has it free as `entry["timestamp"]`. Omit it
  and the Notion write still happens, only the mirror is skipped.
- **Whole-tab rewrites mirror too** (`_rewrite_sheet`/`_append_sheet_rows`),
  as plain upserts — correct ONLY because every one of those callers MERGES
  (`rebuild_tab`, `sync_sleep_fusion`, `rebuild_oura_tabs` each carry the
  existing rows through), so a rewrite is always a **superset** and no row
  disappears. **A rewrite that could SHRINK a tab needs delete-then-insert**,
  the way `training_sets` does. Rows are filtered to the table's real columns,
  matching `_insert_rows` — `rebuild_oura_tabs` rewrites against the tab's OWN
  header, and PostgREST rejects the whole batch on one unknown key.
- **`apply_check_in_merge` mirrors**: `merge_check_in_group` now writes the
  Date back explicitly (a no-op in Notion, since every page in the group was
  grouped on that exact value) so the merged property set can name its own
  row. **The archived duplicates need no delete** — they share the survivor's
  primary key, so deleting would remove the surviving merged row.
- **CLI scripts flush at process exit** (`atexit`, once per process). Five
  scripts write mirrored tables and then simply exit without running a sync
  chain; without the hook every row they queued is dropped.
- **`scripts/pull_datastore_from_supabase.py`** fills `datastore.db` from
  Supabase the way `build_datastore.py` fills it from Notion and Sheets —
  the direction that makes the read cache independent of both. `--round-trip`
  pushes, pulls back and diffs every cell; it is what found three columns
  that were silently lossy (see the Known Open Issues row).
- **Adding a table means Supabase needs the DDL** — PostgREST has no DDL
  route, so `services/datastore_schema_postgres.sql` (or just the new
  `CREATE TABLE`) is pasted into the SQL editor by hand. `push()` preflights
  every table with a read before issuing a single DELETE, so a missing one
  refuses with "Nothing was deleted" instead of half-emptying the project.

## Key Rules (non-negotiable)

1. **Deterministic before AI** — implement the rule-based version first; AI layer is only added on top once the deterministic version is tested and working.
2. **AI never controls safety** — traffic light multiplier, ACWR ceiling, stage transitions, and final prescribed volume are always deterministic. AI output is advisory only.
2b. **ACWR stays on Foster AU; only STRAIN is heart-rate-derived.** `services/hr_load.py` feeds the displayed strain value, never `engine.acwr`. ACWR is a ratio of rolling averages, so mixing Edwards'-TRIMP days with RPE-fallback days inside one 7/28-day window would compare different units and swing the ceiling on whether a Garmin activity happened to be recorded — i.e. on watch-button behaviour rather than physiology. Unifying them requires a per-athlete conversion regressed from sessions that have BOTH signals; do not attempt it until enough paired sessions exist.
3. **`services.rules.STAGE_CONSTRAINTS` is the single source of truth** for per-stage ACWR ceilings, RPE ceilings, and volume caps. `services/engine.py` derives from it; do not duplicate values.
4. **Notion is the write backend; Oura + Garmin (blended) is the engine's biometric read source.** `services/biometrics.py` blends HRV/RHR/sleep duration at Oura 70% / Garmin 30%, and steps at Garmin 80% / Oura 20% — see `services.repository.Repository.get_biometric_rolling`. Google Sheets is still the intermediary (each platform's own tab, synced by `sync_oura_all`/`sync_garmin_daily_if_due`), and Sheet1/Apple Health is retired from the live pipeline — historical-only, feeding `get_sheet1_biometric_rolling` and the one-time `scripts/backfill_garmin_from_sheet1.py`. `get_biometric_rolling` itself is a **live recompute, not persisted** — the "Biometric Blend" sheet tab (`sync_biometric_blend`/`get_biometric_blend_history`) is the fixed historical record of what was actually computed on a given day, written once/day and viewable unbounded in Insights → Sync. Do not add manual biometric entry anywhere. Exception: a per-night wake-time correction for Sleep Score purposes is allowed (`services/repository.py`'s `get_wake_time_adjustment`/`set_wake_time_adjustment`) — this corrects a known, specific Oura measurement pattern (wake-time overestimation), not general manual biometric entry. Both the raw Oura reading and the adjustment are stored separately; the raw reading is never overwritten.
5. **Training sessions are logged automatically by Training Plan.** No manual entry page. (Supplementary imports — yoga flows, and the Garmin outdoor importer's hike/walk/trail-run sessions — are not manual entry: every number comes from the device or the athlete's own RPE rating, they log under `Type` values in `Repository.SUPPLEMENTARY_SESSION_TYPES`, count toward strain/ACWR via Foster AU, count as leg days, and never mark a plan day as done.)
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
17. **In-app navigation NEVER uses an HTML anchor — new screens open IN the same page, never as a new one.** This app is an SPA: `app.py` routes on `st.session_state["_nav_page"]`, and every navigation must set state and let Streamlit rerun over the **existing** WebSocket. A real `<a href="?...">` does the opposite — a full browser navigation that reloads the page, reconnects the WebSocket, wipes `session_state` and leaves every `@st.cache_data` cold. On a phone that is seconds, and it reads as *"it opened a new page"*. Use `st.button(..., on_click=...)`, styled to look like whatever the design needs: `nav.py` styles buttons into the fixed bottom bar, and `views/insights.py`'s BioAge cards are a worked example of a button styled as a 150px image card (`st.button(key="x")` emits a `.st-key-x` class, which is the documented styling hook). **Carrying state in the URL is still fine and often right** — assigning to `st.query_params` sends a `page_info_changed` message and the frontend rewrites the URL via the history API with **no reload** (`streamlit/runtime/state/query_params.py::_send_query_param_msg`), which is why the Home screen can keep `d`/`view`/`pt` in the URL for reconnect survival (`app.py`'s own note) while still navigating by button. The anchor is the problem, not the query string. `tests/test_spa_navigation.py` enforces this: `views/` must stay at zero in-app anchors (it is fully clean), and `app.py`/`styles.py` may only hold the three anchors listed in its `_KNOWN` map — all in-chart, all **STRUCTURAL**: `chart_hits()`'s up-to-48 hit bands over a generated SVG, and the two controls inside `_point_detail_block`. All three are anchors inside an HTML *string another element renders*, so there is no point in the element tree at which a button could sit. The list may shrink freely; it may only grow by a deliberate edit with a stated reason. **⚠ A JS bridge for those three was built, shipped as `77c6984`, and reverted the same day — do not re-attempt it without reading `styles.enable_chart_links`' docstring.** It made them `data-nav` spans and turned a click into `history.replaceState` + a hidden-button rerun. The Python side supports that (`app_session.py` feeds `ClientState.query_string` into `RerunData`) but the **browser** decides what goes in that field, and the shipped frontend's `getQueryString` is `state.queryParams || document.location.search` — the live URL is read *only* when Streamlit's own cache is empty, and that cache is written solely by Python assigning `st.query_params`. `app.py`'s router assigns `page` every run, so it is never empty and `replaceState` is ignored. **The failure is silent and looks exactly like success**: URL updates, no reload, no error, and Python keeps reading the old selection. It passed a browser test whose probe app never assigned `st.query_params` — the one condition that cannot hold in the real app. Measure any replacement against a page that ALREADY carries a query param. A real fix means a chart component with genuine selection events, not click interception on hand-built SVG.

18. **The app runs primarily on a HOSTED SERVER, not locally** (athlete, 2026-08-12 — settled, do not re-open). This decides the storage architecture and is not visible from the code. Reads stay on the local SQLite datastore because PostgREST measured **4,284 ms vs 32 ms** over the same 22 tables — the cost is ~136 ms *per round trip* whatever the payload, so Supabase must never become the read path. But a hosted filesystem is typically **ephemeral**: a redeploy wipes `datastore.db`, so the read cache has to be **rebuilt at startup from Supabase** (`supabase_store.pull`, ~4-5 s), never from Notion/Sheets and never assumed to persist. **That startup rebuild does not exist yet** — it is the one build item this decision creates, and it is the real prerequisite for Supabase becoming the system of record, since there is no durable local disk to fall back on.

11. **Before authoring any new training block, explicitly confirm each local clinical profile document has been read** — `patient_profile.py` plus every `Input_files/*.md` document present — and state how each one influenced the plan, per `docs/clinical_profile_weighting.md`. This is the checkable form of "understood and acknowledged," not a formality to skip. **From 2026-08-10 this gate also covers `docs/training/warmup_evidence_review_2026-08-10.md`, and from 2026-08-13 `docs/training/rest_interval_evidence_review_2026-08-13.md`** — same standard, same checkable form for each: state how it influenced the plan, or say plainly that it did not and why. **Gated on the EVENT, not a date** (`HRV_GARMIN_HOLD` idiom): the plan is NOT being rebuilt on 2026-08-16 (athlete, 2026-08-10), so both wait for the block build rather than expiring with the Day 28 reassessment. The warm-up review is in the gate rather than in a docs list because the next block is the first to run near-maximal loads and **the system contains no warm-up at all**; a gym day goes from the last release hold straight into the first working set. The rest-interval review is in it because **the two documents share a clock and a prerequisite**: warm-up phase 2 adds 5–10 min, the one supported rest change adds 1–3 min, and both are gated on a per-set field that does not exist. Each carries a hard software prerequisite — see the Known Open Issues rows.

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
| **⛔ WARM-UP: none exists, and the next block is the first to need one — REQUIRED READING before the next block is authored** | `docs/training/warmup_evidence_review_2026-08-10.md` (2026-08-10), now inside Key Rule 11's gate. **Gated on the EVENT, not a date** — the plan is NOT being rebuilt on 2026-08-16 (athlete, 2026-08-10), so this waits for the block build rather than expiring with the Day 28 reassessment; if Stage 2A is extended rather than replaced, the budget and the shape can land in the extension, which is the athlete's call. Two facts drove it: **there is no warm-up anywhere in the training layer** — a Stage 2A gym day runs four release items and goes straight into the first working set of Goblet Squat (`training_plan.py:1900-1985`), no raise, no ramp — and **the block that looks like one costs 16–22 minutes while `patient_profile.py:439` calls it a "5-minute release block"** (a live discrepancy sits inside it: `UPPER_GLUTE_RELEASE` is coded `laterality="bilateral"` while its own `mechanics` text and the profile both say *each side*, a 2× difference on the largest item). The review is evidence-graded throughout (A = meta-analysis … E = expert framework). Headlines: warm-up value is **not a constant** — at near-1RM loads a general warm-up earns +3–8% (Barroso 2013 n=16; Abad 2011 n=13) but **5 minutes measured indistinguishable from none** (p = 0.99) while 15 min *easy* gave +3% and 15 min *moderate* **−4%**; at ~10RM loads a specific warm-up is worth ≈nothing (2025 crossover n=29, *strong evidence against*); on small isolation work it **reduced** reps (ES −0.4/−0.5). So warm-ups are scaled **per exercise, never per session** — which is exactly the "warm up everything, train only biceps" failure the athlete named. PAPE is excluded (ES ≈0.13 needing 4–7 min rest). **There is NO evidence warm-up prevents resistance-training injury** — the FIFA 11+ team-sport literature does not transfer, and the rationale here must be stated as mechanistic rather than borrowing that authority. The athlete's own 2025 log is the highest-weight evidence in the document: *"very dependent on warm-up to fire properly"* and **"glutes not warmed up before squats"** named as a cause of the squat breakdown — so the job is glute activation before squat/hinge, not the performance bump. **⚠ The literature's best general warm-up (15 min low-intensity cycling) is the thing his own log blames for glute inhibition**, so modality is an open question, not an assumption. **Hard software prerequisite: the per-set warm-up flag lands BEFORE ramp sets do** — see the row below; `tonnage.py`'s eligibility is `if reps and weight`, so ramp sets would silently inflate tonnage, Strain/AU and e1RM. Two corrections already applied, do NOT re-derive the originals: the ≥60 s force-deficit dose is **one exercise** (Right Posterior Hip Capsule, 2 × 60 s), not the PNF (3 s bouts, trivial bucket) and not the pressure releases (no force cost at all); and the **orthostatic transition is RARE and is NOT a design driver** (athlete's correction 2026-08-10 — the profile's *intermittent* had been read as frequent). **THE SHAPE THE PROTOCOL IS AUTHORED IN**, canonical and stated in three places in the review (banner, §2.3, §3.3): today the session is `[ quiet things down ] → [ load ]`; it must become **`[ quiet things down ] → [ wake things back up ] → [ load ]`**. Phase 1 is the existing release block — it exists, costs 16–22 min, and **nothing in it needs deleting**. **Phase 2 does not exist at all and is the entire deliverable**: its job is not the performance bump but to undo phase 1's acute cost (stretching leaves tissue slack — a bad trade at Beighton 6/9, where muscle is the primary restraint) while keeping phase 1's clinical benefit, which is precisely what the 83-study meta-analysis says a subsequent active warm-up does. Use these three names in patient-facing text (`feedback_patient_facing_text`: how before why). **🔒 LOCKED 2026-08-10, athlete's direction (review §3.0): PHASE 2 IS MANDATORY AND IS THE FIXED POINT OF THE BLOCK BUILD** — specified first from the evidence, everything else adjusting around it, including the release block's duration. It supersedes the review's earlier framing that treated phase 2 as fitting into leftover time. The "must" is conditional on two things both true here — stretching runs immediately before load, and loads are near max — and must NOT be quoted as a universal law in a later block. **⚠ Do not price phase 2 at 15 minutes:** it has TWO jobs, and only one is locked. **Job A (restore)** — undo phase 1's slack, wake glute max — is Warneke 2024's counteraction finding, which is about *presence* and **specifies no duration**. **Job B (maximise)** is the 15-min low-intensity raise, pays only near 1RM, is worth ≈nothing at 10RM, and is optional. Conflating them spends the entire time budget buying something Job A does not need. "Mandatory" means the phase exists every session, NOT that every exercise gets a ramp — per-exercise scaling still holds, and ramping the face pull is pure fatigue. **Consequence: the release-block dose question is FORCED, not optional** — 16–22 min of phase 1 plus a Job-B-sized phase 2 is 30+ min before the first working set, rejected on its face. That question is the physiotherapist's and **nothing in the release block is cut by this repo**; three specific items to take to the physio are listed in review §4.2 (the PNF's 30 cycles, the `laterality` discrepancy worth ~4 min, and whether the capsule stretch survives 2 × 45 s). **🔒 LOCKED 2026-08-10, athlete's direction (review §3.0-b): TOTAL preparation time is 10–15 MINUTES** — phases 1 and 2 together, first movement to first working rep, 15 a ceiling not a target. Today's ~30 min sits against a **~30 min working portion** (derived by summing Session A's coded tempos, reps and `rest_seconds`), so preparation is **half the session** — the athlete's *"otherwise the entire time is just warming up"* is literally accurate at that ratio; 10–15 min puts it at 25–33%. **⚠ The budget RESTORES the prescription rather than cutting it:** `patient_profile.py:439` reads *"5-minute release block before every session"* while the coded doses drifted to 16–22 min, so compressing phase 1 toward ~5 min returns to the documented intent. That also reframes the physio conversation from *"may we reduce this?"* to ***"which items carry the clinical effect at the 5 minutes your own note specifies?"*** Indicative split: phase 1 ≈ 5 min, phase 2 ≈ 5–10 min (a ramp is ~1 set of ~6 reps at ~60–65% of working load on the heavy compounds only — seconds of work). **The ceiling is the athlete's and is settled; the split inside it is the physiotherapist's, and this repo still cuts nothing.** |
| **⏱ REST INTERVALS: reviewed, ONE change supported, and it is blocked on a field that does not exist — REQUIRED READING before the next block is authored** | `docs/training/rest_interval_evidence_review_2026-08-13.md` (2026-08-13), now inside Key Rule 11's gate, same EVENT-not-date basis as the warm-up review. **The question rested on a false premise and the premise is the finding: `views/training.py:3527` has NO rest timer on the right→left transition, so the other side's working time IS the first side's rest.** Actual per-side rest in Stage 2A is **75–105 s**, not the coded 45–60 — every unilateral exercise already sits in the zone where Singer 2024 found the return flattens (*"did not detect appreciable differences in hypertrophy when resting >90 s"*). **Both proposals are refused on evidence AND priced:** a 1-min right/left split costs **+9/+9/+11 min per session** (9, 9 and 11 two-sided transitions — the right-ONLY items are coded `laterality="unilateral"` and must be excluded) to buy a pooled non-local-fatigue effect of **SMD −0.02 [−0.14, 0.09]** (Behm 2021, 52 studies, 278 effect sizes; strength subgroup **+0.11**, i.e. nominally *better*), and crossover fatigue is **cumulative** — Doix needed TWO 100-s maximal bouts to move the resting limb, one 30-s effort did nothing; 3–5 min costs **+23.5 min** against guidance that no longer exists, since **ACSM's 2026 umbrella review (137 SRs, >30,000 people) grades inter-set rest "does not impact" strength and issues NO rest prescription**, and the famous "3–5 min" line is in ACSM 2009's *Summary* with **no evidence grade at all**. **The ONE supported change: 90 s → 120–180 s on Goblet Squat and RDL, STAGE 2B ONLY, when the loads are actually near-maximal** (Grgic 2018's *">2 min to maximise 1RM in resistance-trained individuals"* — ⚠ synthesis judgement, that review pools nothing); costs 1–3 min; **does not apply at 12.5 kg and RPE 6**. Note **90 s is the ceiling in the whole repo** — 4 of 117 coded values. **⛔ HARD PREREQUISITE, same class and same block as the per-set warm-up flag: rest duration is NOT LOGGED ANYWHERE.** At a fixed rep target short rest does not reduce work, it **inflates RPE** (Farah 2012), and `session_au` is computed from RPE — so a rest change moves Strain and ACWR with **no change in work performed and nothing in the data able to tell the two apart**. That is key rule 2b's hazard by another door; it also contaminates the measured-RPE-vs-self-reported comparison window, which is under review the same day. The timer value exists at the button press and is discarded. **Two things found in the tree while pricing this, recorded NOT fixed:** (1) **`estimate_duration` never reads `laterality`** (`services/sessions.py:879-895`), so every gym session's estimate omits the second side — **5.5–6.9 min each**, i.e. 35–40 min shown against ~41–47 min real; this means the warm-up review's *"~30 min working portion"* denominator was short, which makes its 10–15 min preparation lock **better** supported, not worse — **do not re-open it**; (2) coded rest is already **13.0–16.5 min per session**, 32–42% of it. **⚠ Read §2.4 before dosing the Stage 2B isometric holds** — out of scope of the athlete's question and the most consequential item: at matched loading time **four 3-s contractions beat one 12-s hold (+57% vs +25% stiffness, Bohm 2014)**, intensity not duration is the variable (>70% MVC SMD 0.90 vs ≤70% 0.04), the 45-s hold is **n=6 about analgesia** and has failed to replicate three times (Holden n=21; van der Vlist **n=91 outright null**; Clifford meta p=0.19), the 30-s hold is **n=1**, and the "10 min / 6 h" rule is **in-vitro engineered ligament**. The target tissue is not a tendon — it is perfusion-limited left trapezius, where **sustained low-level contraction is the provocative mechanism**. That is a Day 28 question for the physio, NOT a re-opening of the release-block dose (closed, physio-confirmed 2026-08-12), and **nothing in `training_plan.py` is changed by this document**. **⚠ §1.9 records one FABRICATED paper and two miscited claims in circulation on this exact topic — a "36 amateur bodybuilders, 60/90/180 s" trial that does not exist (and is the only study that would answer the question), an AHA-2024 claim that is not in the source, and Fink 2018 / Senna 2011 / Jukic 2020 each quoted for the opposite of what they report.** Do not re-import them. |
| **🐛 `sync_session_hr_for_date` has NEVER run — the Session HR tab is empty and strain is 100% RPE-derived** | **Found 2026-08-10, verified, NOT fixed.** `services/repository.py:2851` does `ex.sets` on a `models.ExerciseEntry`, whose fields are `name, movement_type, planned_sets, planned_reps, exercise_rpe, actual_sets, total_volume_kg` — **there is no `sets` field**, so it raises `AttributeError` every call. The chain makes it total and nearly silent: `save_session_hr` has exactly ONE caller, three lines after the broken expression; that caller's only caller runs inside `run_sync_if_due`, which catches and returns `(False, message)`; `views/training.py:2821`/`:2885` call `compute_session_hr` but never `save_session_hr` (they put the result in `st.session_state.tp_hr_au` for display); and `tests/test_repository_sync_throttle.py:275` monkeypatches the broken method itself, so the gate never executes the line. **Consequence: `get_session_hr_history()` has always returned `[]`, `blend_strain(None, rpe)` always returns `SOURCE_RPE`, and the Edwards'-TRIMP half of strain — the 70% HR weighting, the `Garmin HR + RPE` source label, the whole `hr_load` blend — has reached the displayed number on zero days ever.** Fix is `{i: ex.sets ...}` → the per-set records the live path already passes; note the two writers use DIFFERENT index spaces (`views/training.py` passes plan-day indices with gaps preserved, `sync_session_hr_for_date` renumbers 0..n over logged exercises only), so they must be reconciled before per-exercise HR is trusted. Deliberately out of scope of the localised-strain change, which is why `strain_regions.region_hr_load` ships with the AU-share basis as its only path. |
| **⏳ Flexibility: ZERO assessments run** | Open by design, and the only thing between this sector and usefulness. The four-slot battery is built, its early exit is verified end to end, and nothing has been measured. **Run it BEFORE 2026-08-16** — it is measurement, not prescription, and it puts a pattern label in front of the physiotherapist instead of a plan to get one. **Measure COLD.** Every threshold (`GATE0_ORIENTATION_GAIN_CM`, `LEVERAGE_TARGETS`, `TILT_TARGET_DEG`, `SPECTRUM_GAP_CM`) comes from the source rather than from his own spread, which has never been measured; three baseline mornings set the noise floor, and until then `BatteryResult.trusted` is False and the screen calls the pattern a hypothesis rather than a verdict. 2026-08-07, on the athlete's direction: **the tilt is an ANGLE at the pelvis** (phone on the lower back; a rounding spine cannot fake it, so one number replaced the old two), **own-power runs before helped** (help flatters what follows — the slot-3 principle applied to slot 2), and **Gate 0's two-orientation comparison only runs within `GATE0_BONE_RELEVANT_CM` (15) of the floor** — bone meets socket in the last few centimetres of a full split, so above the line `applicable_tests` drops the turned-out attempt and slot 0 passes on the neutral height alone. An old centimetre tilt reading returns `indeterminate` rather than being read against the degree target. |
| **⏳ The cluster session joins the next block on 2026-08-16 — protocol written, not yet executed** | `docs/training/flexibility_integration_2026-08-16.md` (2026-08-07). The blueprint's training rules were already encoded (`flexibility_window`, `FREQUENCY`, `LENGTH`); the protocol governs the BLOCK BUILD: reserve the slot inside the five-per-week ceiling (never author 5 gym days then bolt it on), re-derive placement against the NEW week with **running counted as leg loading**, one new stressor per week (cluster ×1 in week 1; the second weekly session is EARNED by two clean weeks), map every stack/release name into `EXERCISE_MOVEMENT_WEIGHT` + `EXERCISE_BODY_REGION` so nothing falls to the 1.0 default (the Stage 1 bug by another door), judge the Coxa Saltans holds at the same sitting, calendar the mid-September retest, and the pull-back condition is pre-written in the `HRV_GARMIN_HOLD` idiom. 2026-08-07 addition, the athlete's rule: **a retest is never the morning after leg training** — day-before leg work reads as extra tightness in exactly the tested areas, the same contamination class as a warm-up, one day earlier. `flexibility.retest_readiness()`/`retest_due_on()`/`leg_loading_days()` (leg days judged by `EXERCISE_BODY_REGION`, the sectors' own map — one definition of "a leg day" everywhere); surfaced as a training-screen banner the day before (swap prompt if today already loaded legs) and the day of, a due-date line on the flexibility screen, and a warn-never-block notice on the capture cold gate. `RETEST_INTERVAL_DAYS` (28) lives on the Prescription — cadence is dosage. Gate 1647 → 1652. |
| **Frozen constants: two of four are now captured in-flow** | Straddle width (at the tilt, 2026-08-07) and the tailor's heel distance (at the bent-knee leverage, 2026-08-06) are recorded beside the reading as `Reading.setup_value`, and the screen offers last session's number back — THE NUMBER IS THE RECORD. Still uncaptured: the traced side-split stance and the floor reference, which remain setup discipline with no field. `block_height_cm` is deliberately NOT frozen: it is the section-F progression variable and lowering it IS the progress. |
| **The app offers yoga on rest days** | **RESOLVED 2026-08-06.** The Prescription's dosage section settles what this row recorded as open: a cluster session is adaptation-seeking by definition, so `flexibility_window` now returns `poor` for a rest day rather than accepting the flag and ignoring it, and `REST_DAY_CONFLICT_UNRESOLVED` is retired. A restorative yoga flow on a rest day remains fine — that is `services/yoga.py`'s business. Placement is set against the real week: Stage 2A loads legs on days 1, 3 and 5, leaving day 7 clean with day 2 as the same-day-evening fallback. |
| **Cluster B is unbuilt, and its first skill collides on wording** | Open. The blueprint defines Pike as *touching your toes; forward fold* — wording that hits two contraindicated `rules.py` keywords outright. That is a whole-cluster collision to resolve before Cluster B is authored, not after. The same flat-back redefinition that made the pancake trainable is the likely answer, but it needs the same explicit treatment rather than being assumed. |
| **⏳ The InBody bridge scan expires when the gym swaps machines (~Sept 2026)** | **Time-limited, and unrecoverable if missed.** Under the never-pool-two-devices rule a reading on the new machine cannot be compared with the five corrected 2025 scans unless both machines measure the same body the same morning. One visit: confirm **182.0 cm** entered, scan the old 770 **twice ~8 minutes apart** (the only estimate you will ever get of its own test-retest spread — the existing 8-minute pair is confounded by the height re-type), scan the new machine, take a tape baseline, keep the **print-out** not the app summary. Full protocol in `docs/focus.md`. |
| Foryond height corrected 183 → 182 cm on 2026-08-05, history NOT back-applied | Open by design. All 142 stored rows keep 183.0; the next weigh-in steps **BMI +0.27** guaranteed and possibly **+0.9 pp** body fat from the setting alone. **That step is a setting, never fat gain** — the same class of artefact the gym made five times in the other direction. The next reading also answers whether this device uses height in its body-fat model at all. |
| Body-composition accuracy layer deferred to 2027 | Deliberate (user decision, 2026-08-05) — revisit against a year of standardised readings. Design recorded in `docs/resume.md`: weigh 4–5×/week under fixed conditions (**protocol standardisation is worth 24% at zero extra weigh-ins**, against 33% for tripling frequency, and the curve flattens hard past four), a monthly tape as the one fat signal whose errors share no mechanism with impedance, and the training log as a **consistency gate** rather than an input — it cannot produce kilograms of lean mass, and the log records no per-set laterality so it cannot be matched to the InBody's left/right segments. |
| **⏱ Measured RPE runs BESIDE self-reported, not instead of it — revisit 2026-08-16** | Deliberate (2026-08-07), same pattern as `HRV_GARMIN_HOLD`. Every session now yields two intensity figures: the slider (always asked, feeds `session_au` → Strain/ACWR) and an HR-derived RPE from `compute_session_hr` (%HRR, active-time-weighted, feeds **nothing**). Not unified, because rule 2b's hazard is exactly this — a load figure that moves depending on whether the watch was running swings the ceiling on **button behaviour rather than physiology**. Rule 2b also names the exit: *a per-athlete conversion regressed from sessions with BOTH signals*, which is why the rating is collected even on no-Garmin days. **First paired point 2026-08-06: measured 5.2 vs reported 5.0 (333 AU vs 320)** — one point, not a regression. **Lift on the measurement, never on the date**: check n, the bias and the SPREAD of (measured − reported); a wide spread means no single conversion works and the hold stands. Full criteria in `docs/focus.md`. Also check session `hr_coverage` — routinely under ~85% means the watch is started late or stopped early, and the fix is the prompt, not the model. |
| **⚠ ACWR enforcement is HELD — `engine.ACWR_ADVISORY_MODE = True`** | Deliberate (user decision, 2026-08-03), same pattern as `biometrics.HRV_GARMIN_HOLD`: a breach is **reported but never caps volume**, riding beside the biometric directive as `volume_recommendation()["acwr_advisory"]`. **The ceiling is untouched** — `rules.STAGE_CONSTRAINTS` is unchanged and `acwr()["exceeds_ceiling"]` still carries the raw fact, so flipping the flag to `False` restores hard-locking with no other edit. Two tests pin both directions. Lift it once the app is validated against more real training and the other planned engine work lands — **on that work being done, not on a date**. **Athlete, 2026-08-12: evaluate this WITH Stage 2B** — i.e. at the block that starts 2026-08-16, against its real loading rather than Stage 2A's. |
| ACWR chronic window is scoped per stage | Fixed 2026-08-03. A flat 28-day window spanning the Stage 1 → 2A boundary divided a training-load acute term by a rehab-load chronic term: **20 of the block's first 30 days breached 1.3 (67%)**, peaking at 1.78 — and the breach barely depended on training. 2026-07-25→27 were three consecutive **zero-AU days pinned at 1.73**, and the scheduled rest day 2026-08-09 projected to 1.54. `engine.acwr(..., stage_start=)` now averages chronic over current-stage days only (`services.plan.current_stage_start` supplies it; `None` during a reassessment gap falls back to the calendar window, and every caller omitting it is bit-identical). Measured effect on 2026-08-03: **1.32 → 0.93**; forward breach rate 62% → 38%, with the remainder landing on Week 4's genuine RPE 6→7 step rather than on the stage boundary. Prior-stage days are **excluded, never down-weighted** — they are the denominator, so ×0.5 moved ACWR 1.32 → **1.50**, the opposite of the intent (`test_downweighting_would_have_moved_the_wrong_way` pins this). Below `ACWR_MIN_IN_STAGE_DAYS` (14) the ratio is reported with status `baseline_establishing` and never locks — a chronic window no longer than the 7-day acute one collapses toward 1.0 by construction. |
| `Training plan/` folder at root | **RESOLVED 2026-08-03** — the directory no longer exists at root; contents live in `docs/training/` |
| **Stage 2B CONFIRMED — starts 2026-08-16** | Athlete + physio, 2026-08-12. Day 28 is **signed off**; Stage 2B replaces Stage 2A rather than extending it. **Running is introduced, slowly, as already planned** (10 km 2026-10-11 — see `docs/focus.md`). **Isometric hold durations follow the scientific literature for tendon adaptation, dosed across a ~10-minute period** (athlete's direction; this settles the interscapular endurance question — scapular holds are trained normally and to the literature, physio-confirmed, no further questions). **The 5-minute release block is physio-confirmed** — the dose question raised in the warm-up review is CLOSED, and nothing further goes to the physio on it. |
| Stage 2 training plan | **BUILT — live since 2026-07-20.** `training_plan.PLAN_STAGE2`, a 28-day gym strength block; physio signed off on external load at the Day 21 (not Day 14) reassessment, recorded in `patient_profile.PROFILE["stage_transitions"]`. Day 28 reassessment is **2026-08-16**, where three explicitly deferred decisions land: Stage 2B vs. extending 2A, running introduction, and endurance-biased scapular programming. See `docs/focus.md`. |
| **✅ Interscapular symptom SOLVED to a tissue 2026-08-13 — left TRAPEZIUS, position-loaded, perfusion-limited** | Onset **2026-07-16, four days BEFORE Stage 2A began** — the loaded block did not cause it. Flat at tightness 1-3 / pain 0, no neural signs. **The athlete marked the area on an anatomy plate and ran discriminating tests; `symptom_log` 2026-08-13 holds the finding and the three earlier entries now carry tombstones pointing at it.** Tissue is **left trapezius (upper/middle fibres + the C7-T3 aponeurosis)**; **rhomboid**, **levator scapulae** and the **deep cervicothoracic layer** are each ruled out by a named test (the decisive one: pinning the shoulder blade abolishes it at identical neck end-range, which spine-to-spine muscles could not do). Mechanism is **PERFUSION, not capacity** — sustained low-level contraction occludes flow, so movement, face pulls and heat all relieve it while eight hours of holding does not; a shrug held 20-30s in the provocative position is worse *after release*, i.e. reperfusion, which is the physio's own 2026-08-10 "positional ischemic cramp" mechanism in a different muscle. **⚠ FOUR THINGS IN THE RECORD WERE WRONG AND ARE CORRECTED:** (1) the location is **~2-4cm lateral to the spinous processes, C7/T1-T4/T5**, NOT the medial scapular border — the 07-31 entry had it right before the 08-03 entry moved it; (2) "sitting, standing AND treadmill alike" does NOT mean duration-not-posture — all three load the same tissue by different routes, and **a standing desk is WORSE than sitting here** unless the arms are supported; (3) driver (1) is now **MEASURED** — at matched prone-raise height the left works harder than the right, which is why it is the left (the right's 20cm vs left's 40cm ceiling is the **Latarjet** limiting horizontal extension, not weakness to train through); (4) **"scapular work runs five days a week" is FALSE** — the log says **4, then 3, then 2, then 2**; that figure came from `training_plan.py`, not `training_exercises`. **⚠ But the conclusion built on it SURVIVES and a first pass wrongly overturned it.** Wall Slide ran **2026-08-11** and Face Pull **2026-08-12**, and **2026-08-12 is the worst day on record** (tightness 3, **pain 1** — first above 0/10 in three weeks), so *"the symptom persists through that dose"* holds and only the arithmetic was inflated. **Prone Y-Raise (last run 2026-07-24) is the one genuine omission.** The wrong pass counted off a datastore snapshot built **two days stale**, read "0 scapular days this week", and missed the two most recent sessions. **Method: verify a dose against `training_exercises`, AND rebuild the snapshot first (`scripts/build_datastore.py`) — a stale local read does not look like an error, it looks like absent data, which is the exact failure the offline datastore exists to prevent, arriving by the other door.** **Training is exonerated by the log** — six interscapular reports on six weekdays, three clean weekends, AU predicts nothing, and a 10km hike produced no symptoms, so **running is NOT implicated for Stage 2B**. **Tendon question: LESS LIKELY, NOT EXCLUDED** — loading the sheet in neutral leaves it unchanged where tendinopathy escalates, but heat helping and morning-stiffness-easing-with-movement do NOT discriminate (an earlier overclaim, corrected); two cheap tests stay open (three-round retraction, focal-vs-diffuse palpation) and neither changes the prescription. Interventions are **self-directed and already cleared** — raise the too-low desk to standing elbow height measured **on the treadmill deck**, raise the monitor by the same amount, and **reinstate the two low-load scapular holds that silently dropped out**. Long isometric holds are a prescription change: **no `training_plan.py` change this block by design**, physio decides at Day 28 (2026-08-16). **2026-08-10: the physio answered the brief's §1-§13 six days early** (`symptom_log` 2026-08-10; §14's micro-dose asks and the stage-gate decisions rest on Day 28's data — `PLAN_STAGE2[28]` is a SELF-administered test session, and the required physio sign-off on its results is format-free, remote fine) — scapular strengthening APPROVED (both sides; right is the weaker, left overcompensates), and the premise was corrected twice: the chair's forearm supports already removed most of the pressure, and the 50-60s fatigue onset was **REMOVED from the record at the athlete's direction** — no basis (one casual self-observation), not reproducible (studio retest held Down Dog 4+ min, arms fail first; shoulder blades can train normally to failure; the issue is stillness/stiffness, not weakness). The removed figure was scrubbed the same day from `services/yoga.py`, `tests/test_yoga.py`, `docs/training/Yoga_Library.md` and the brief; hold DURATIONS are unchanged everywhere — lengthening the scapular holds is the prescription itself and lands at the block build as a recorded decision. See `patient_profile.py` `symptom_log` 2026-08-03 and `docs/training/physio_brief_2026-08-16.md`. |
| **⏱ Two release protocols running as pre-registered hypothesis tests (2026-08-10)** | `docs/training/release_protocols_2026-08-10.md`, authored on the athlete's direction from the Cluster D source documents (`Input_files/cluster_d_*.md`) + Baar annex §4 conduct rules, implementing the physio's 2026-08-10 prescriptions. **Pec/scar release + anterior-wall active reciprocation (right):** starts immediately; instrument is the standardised prayer position (seconds-to-onset + 0-10 intensity, weekly re-check, never daily); verdict due ~2026-08-24 — unchanged at two weeks routes to professional soft-tissue treatment per Cluster D §F, and any pain/neural/instability sign stops it. **Anterior-hip sustained pressure:** starts only AFTER the battery baseline is captured — the tilt is the battery's central measurement and contaminating it is the pre-declared failure mode; any tilt gain is pre-attributed to the F-stack, the release's own instruments are tender-point quieting and after-sitting ease; a null at 4 weeks retires it. Baar annex §6.4 gates 1-2 updated in place (gate 1 RESOLVED — tissue named, prescription followed; gate 2 answered early, its 50-60s anchor removed). Athlete's same-day §15 decisions: ER cue confirmed for horse/Cossack (reopens if the click appears under them), right-biased scapular emphasis is the arm under trial, thoracic mobility stays with movement breaks. |
| Garmin HRV is absent, two independent causes | RESOLVED-as-empty (probed 2026-07-31): `get_hrv_data` returns `{}` for this account, so `hrvSummary.lastNightAvg` has nothing to map. Separately, the Garmin Daily tab had been created before `hrv_ms` joined `_GARMIN_DAILY_HEADER`, so every sync wrote it into an unheadered column that `get_all_records` discarded — `services/biometrics.py`'s documented Oura-70/Garmin-30 HRV blend has silently been 100% Oura. The column is repaired (`Repository.rebuild_garmin_daily`); the endpoint may start returning data with a watch that supports HRV status. |
| Garmin backfill | Run `scripts/backfill_garmin_from_sheet1.py` (dry-run first, then `--apply`) once to backfill pre-wearable history into the Garmin Daily tab so readiness baselines aren't starting from empty |
| Quiet-wakefulness rule — measured, then abandoned | **Do not re-attempt without reading `services/sleep_fusion.py`'s docstring.** Best precision ~12% against a 1.9% base rate, i.e. ~88% of flagged minutes would be wrong, and REM is indistinguishable from Awake (both elevated-and-motionless). Probing found no finer HR exists on this account. The blocking problem is not sample size — it is that there is **no ground truth**: validation uses the hypnogram's own Awake labels, but the rule exists to find minutes the hypnogram did *not* label Awake. Needs PSG/EEG ground truth plus beat-to-beat intervals. |
| Movement calibration is n=26 | `Repository.sleep_movement_cutpoints` quantile-maps Garmin's undocumented float onto Oura's 1-4 alphabet from paired nights only; currently 26, floor is 14. The ACTIVE boundary sits far into the tail and is the least stable of the three, which is why rule 7 treats class 4 as corroboration rather than proof. Re-check the fitted values as paired nights accumulate. |
| Metrics History `sleep_score` gap | NOT a population failure — corrected 2026-08-01 by querying the datastore offline. 21 of 34 rows carry a score; exactly 13 consecutive dates are blank, **2026-06-29 → 2026-07-11**, and everything from 2026-07-12 on is populated. An earlier reading of "33 rows, all None" was a throttled Sheets read (429) misread as absent data — the exact failure the offline datastore now prevents. The 13 dates predate the column and would need a `sync_metrics_history` backfill over that window if wanted. |
| Sleep coverage is worn-device-limited, not sensor-limited | Over the 71 nights of the Garmin era the ring recorded 27 nights and the watch 53. Fusing them plus emitting `garmin_only` nights takes stage coverage from 38% to 76% of calendar nights (+217h of sleep Oura never saw). The remaining gap is the 17 nights neither device recorded — no code change reaches those. |
| Sleep Cycle (iOS) export — CONSIDERED AND NOT IMPLEMENTED (closed) | **MEASURED 2026-08-05**, 296 nights 2024-10-31→2026-07-23, 43 paired vs Oura / 11 vs Garmin. It holds wide calendar coverage — **119 nights no device recorded** (corrected 2026-08-05 from 245 once the Garmin duration history was backfilled; see the coverage row below) — and the only acoustic channel. **No channel passed.** Time asleep agrees at bias +0.47h with 95% LoA (−0.50, +1.44) — three times the pre-registered 45-min half-width; everything else fails on bias, LoA or information ratio; staging reads **UNTESTABLE not failed** (n=19). Four structural facts decided most of it before any statistic: `Time in bed` ≡ `End − Start` to 0.00s (a hand-opened recording window, not a measurement) and Awake is its arithmetic residual; `Snore>0` and `Breathing disruptions>0` are the **identical 180 nights, zero off-diagonal** (one detector, two readouts); ambient noise steps ~23.5→~19.5 dB across late 2025 (**two phones — do not transfer a coefficient across it**, same prohibition as 645/265); and all 29 columns are night-level scalars, so nothing can enter `sleep_movement.py`'s 30s grid at ANY agreement level. **The acoustic channel is NOT THE ATHLETE'S**: splitting on whether a night was slept alone or with a co-sleeper present (25 vs 141 nights; classification supplied by the athlete and read from a **gitignored** `Input_files/sleepcycle_cosleeper.json`, since a home location and travel history are identifying details and this repo is public), P(snore>0) is 0.120 vs 0.674, RD **+0.554, 95% CI (+0.316, +0.752)**, holding in both instrument regimes with ambient noise identical within each — and the athlete's own alcohol tag produces no rise. Movement is *not* co-sleeper-contaminated (p=0.42), merely uncorrelated with Oura (ρ=+0.24, CI spans 0). **Nothing in `services/` or `views/` reads any of it**, and per rule 2b + `sleep_fusion.py`'s shadow report, importing 119 uncalibrated nights would raise the 56-night sleep baseline exactly where no device was worn. Against Garmin (n=168 after the backfill) the bias is **−0.73h, sd 0.70** — a SMALLER systematic offset than Garmin-vs-Oura's +1.01h but **50% more night-to-night scatter** (sd 0.70 vs 0.46), which is the comparison that actually matters for substitution. **DECIDED 2026-08-05 by the athlete: stop recording, do not implement.** The measurement's own verdict was the softer 'keep recording, do not ingest' — justified solely by the coverage archive — but once the Garmin backfill cut the unique contribution from 245 nights to 119 (58%→77% coverage) and the 265 arrived, the case did not survive: nothing here beats wearing the ring and the watch. **Do not re-open without new evidence, and note that more nights of the same observational data is not new evidence** — the blocking problems are structural (S1/S2/S4/S7), not sample size. Re-run `scripts/compare_sleepcycle_to_devices.py` (docstring carries the full tables — the CSV is gitignored, so it is their only durable record). |
| **⚠⚠ Garmin reads ~1 HOUR more sleep than Oura, and `sleep_duration_hours` blends them 70/30** | **REPLICATED 2026-08-05 on two independent samples**: +1.11h (sd 0.64) over the 26 `fused` nights, and **+1.02h (sd 0.48, r=0.914, n=57)** over the 2024-11→2025-03 backfill — so this is a stable instrument offset, not sampling noise. Minute-by-minute stage agreement is **52.3% at Cohen's κ 0.178** ("slight"). **The live consequence is in `biometrics._BLEND_FIELDS`:** `sleep_duration_hours` is Oura 0.70 / Garmin 0.30 with a missing source falling back to 100% of the other, so the blended value is Oura+0.31h on a both-devices night, Oura+0.00h on a ring-only night, and **Oura+1.02h on a watch-only night**. That is a step of up to an hour driven by *which device was worn*, feeding readiness Sleep, Sleep Debt and `sleep_score`'s Total Sleep — precisely the "swings on watch-button behaviour rather than physiology" failure rule 2b names, and the same hazard `HRV_GARMIN_HOLD` was created to stop for HRV. **Not yet fixed, and NOT to be fixed by writing the backfilled Garmin durations into the sheet** — that would retroactively move the stored series on ~130 nights. Options are a `SLEEP_GARMIN_HOLD` mirroring the HRV one, or subtracting the measured offset before blending. **⏸ DECIDED-TO-WAIT (athlete, 2026-08-12): sleep stays OURA-ONLY and this is NOT to be raised again until ~2026-08-16** — two weeks from the Monday the Forerunner 265 arrived, which coincides with the Stage 2B block start. He reports the two devices now read more closely on the 265 than the 645 gap measured here, and ALL new-watch metrics (HRV, SpO2, respiration, skin temperature, the movement cut-point refit) are reviewed together at that point, once there is enough data. The question is settled until then; do not re-open it. Also: never describe a candidate source's offset as an over- or under-estimate without naming the comparator — Sleep Cycle is +0.47h vs Oura and −0.65h vs Garmin. |
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
| **✅ Per-set warm-up flag and logged rest — SHIPPED 2026-08-14** | **Both fields exist, in one migration over one set of rows, plus `reps_left`/`weight_left` for the unilateral overwrite.** `is_warmup` is a property of the AUTHORED exercise (`_ex(warmup=True)`), not a per-set toggle — a ramp is prescribed rather than decided in the moment, so no UI was needed for it. Excluded from `tonnage.py`, both `strength.py` filters and all three `total_volume_kg` sites; `actual_sets` still counts them. `rest_taken_seconds` is stamped in Python when the rest phase begins and differenced at the button press — the rest timer is a `components.html` iframe whose countdown can never return a value, so do NOT re-attempt plumbing it back; anything over 20 min is dropped as an interruption rather than stored as a rest. **⚠ It feeds NOTHING yet** (`sessions.REST_TAKEN_FEEDS_DURATION = False`) — see the header. **The default is the load-bearing part: an absent key reads as a WORKING set at an UNMEASURED rest with SYMMETRIC sides**, which is what all pre-2026-08 history is; getting `is_warmup` backwards would silently empty the entire tonnage and strength history, a failure that looks exactly like a quiet month. **Postgres DDL must be pasted into Supabase by hand — `scripts/migrate_2026-08-14_training_sets_per_set_fields.sql`, four `ADD COLUMN IF NOT EXISTS`, safe to re-run.** PostgREST has no DDL route. **⚠ Do NOT paste `services/datastore_schema_postgres.sql` instead: it opens with 21 `DROP TABLE ... CASCADE` and would empty the project.** Until the migration runs, PostgREST rejects the whole batch on the unknown column, so the mirror silently stops mirroring sets — a failed flush is recorded on `mirror_last_error`, never raised; a stale `datastore.db` degrades to "not recorded" rather than raising. `tests/test_warmup_sets.py` (17 tests) pins the defaults, the three storage projections and the round trip. |
| Unloaded work needs TWO counters, and a hold is not a rep | `services/sessions.py` writes a hold or a timed piece as **reps=1 with the work in `tut`**, so a 60-second plank and one dead bug are both "1 rep". Across `training_plan.PLAN`, holds and durations are **54 of 113 exercises and 11,955 seconds** but only **113 of 1,603 reps (7%)** — summing reps alone misrepresents exactly the work the counter exists to represent. `SectorWeek` therefore carries `unloaded_reps` AND `unloaded_seconds`, and they are **never added**: no exchange rate between a rep and a second is defined here, the same reason a bodyweight hold never becomes kilograms. |
| 0 of 17 e1RM estimates are inside Epley's validated range | Sets are logged at 10-12 reps at RPE 5-6, i.e. 14-18 *effective* reps against a limit of ~10. `services/strength.estimated_1rm` returns a `within_epley_range` flag for this. The fix is a periodic ~5-rep set at RPE 8 per movement pattern, not a constant change. |
| See `docs/REFACTOR_NOTES.md` | Smells/bugs found during the services/ extraction, noted but not fixed beyond what the extraction itself required |
