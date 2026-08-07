# Adding the cluster session to the next block — protocol for 2026-08-16

*Written 2026-08-07, before the block exists, so that on the day this is a
lookup rather than a negotiation. The next training block is authored at the
Day 28 reassessment (2026-08-16). The flexibility cluster session becomes real
training that week, and there are exactly two ways this goes wrong if it is
bolted on instead of designed in:*

1. **Overload** — a sixth weekly session, or several new stressors landing the
   same week with no way to attribute a symptom change to any of them.
2. **Silent mis-accounting** — cluster exercise names missing from the weight
   and region maps, so Strain inflates at `UNMAPPED_EXERCISE_WEIGHT` 1.0. This
   is not hypothetical: 34 of 63 Stage 1 names did exactly that, and mobility
   days read as barbell days until 2026-08-01.

---

## What the source says, and where it already lives

The blueprint's training rules are already encoded. This protocol adds no new
engine code — it governs the BLOCK BUILD.

| Blueprint claim | Where it lives |
|---|---|
| 3–5 exercises, each feeding the next, toward 1–2 skills | `cluster_a_prescription.LENGTH`, the stacks, and the stacking-rule tests |
| 1–2 sessions per week, not more | `cluster_a_prescription.FREQUENCY` |
| Best: 2+ days after strength. Second: same day, strength AM / flexibility PM. Third: immediately after, both volumes reduced. Never the day after. Never a rest day as "recovery" | `services/flexibility.flexibility_window()` — the full ranking, tested |
| Fatigue arrives hours after training (the calcium/calpain story) | Held as MOTIVATION, not load-bearing — `flexibility_window`'s docstring says why, and this protocol does not change that |
| Warm stretching is a viscoelastic illusion; lasting change is measured cold | The battery's cold gate |
| Brain adaptations persist; focus on one skill without losing others | The cluster model itself — one pattern, one stack |

---

## The protocol — run in order on 2026-08-16

### 0 · Preconditions, before the block is authored

- [ ] **The battery has been run cold at least once.** Still zero as of
  writing. Without a pattern there is no stack — `prescribe()` refuses by
  design — but the SLOT is reserved regardless (step 1): capacity does not
  depend on which stack fills it.
- [ ] Key Rule 11 as always: every clinical profile document read and its
  influence stated before the block is authored.

### 1 · Reserve the slot in the capacity math

The cluster session is TRAINING and counts against the stage's five-per-week
ceiling — the Prescription says so explicitly. The block is therefore authored
as **at most 4 gym sessions + 1 cluster session**, or 5 gym sessions with the
cluster placed same-day-evening (which spends recovery rather than a calendar
slot, and still counts as a stressor in step 3). What is not allowed: author 5
gym days, then bolt the cluster on top.

### 2 · Place it against the NEW week — the old mapping does not carry over

The current instantiation (Stage 2A: legs on days 1, 3, 5 → day 7 clean, day 2
evening as fallback) is an OUTPUT of the placement rules, not a rule itself. On
the day, re-derive:

1. List the new block's leg-loading days — **and if running enters the block
   (Decision 2), running days count as leg loading** for this rule: impact plus
   hip-flexor and hamstring work, on a leg with a once-recurred Sartorius
   strain that already forces conservative progression.
2. Mark every day-after-legs day as forbidden, and every rest day as forbidden.
3. Pick the best surviving day per the ranking; same-day-evening is the
   fallback; immediately-after with both volumes reduced is the floor.

### 3 · One new stressor at a time

Up to five changes could land in the same week: the new block's loads, running,
the scapular endurance holds, the isometric micro-doses (physio brief §14), and
the cluster session. This repo has already deferred a whole exercise family
(horse stance / Cossacks) purely so that a change stays attributable — the same
logic applies to weeks:

- Week 1 of the new block: **cluster session once**, never twice.
- If running starts in week 1, the cluster starts in week 2 (and vice versa).
  Stagger every new stressor by at least a week where the physio's decisions
  allow it.
- The second weekly cluster session is EARNED, not scheduled: two consecutive
  weeks with (a) no symptom-log entry attributable to cluster work, (b) no
  readiness downtrend coinciding with it, and (c) no ACWR advisory flag
  (`volume_recommendation()["acwr_advisory"]`) in a cluster week — then go to
  2×/week per FREQUENCY.
- Micro-dose streams (brief §14) follow the same stagger: if approved, ONE
  stream enters no earlier than week 2, one stream at a time, and the phase-2
  second daily dose is EARNED by the same two-clean-week criteria as the
  second cluster session. Their exercise names go through step 4's mapping
  like any other addition, and any leg-loading holds (wall sits, split-squat
  holds) count as leg days for step 6's retest rule.

### 4 · Account for the load, or Strain lies

When the cluster session is added to the plan:

- [ ] Every stack AND release exercise name gets an `EXERCISE_MOVEMENT_WEIGHT`
  entry. The release block's five already exist at `mobility_core` 0.25. Stack
  items land by kind — stretches and assisted positions at `mobility_core`
  0.25; isometric strength work (Copenhagen, isometric split holds, adductor
  squeezes, lift-offs, hinges) at `isolation` 0.3; anything that gains external
  load gets judged on the day. **Nothing is allowed to fall through to the 1.0
  default** — that is the Stage 1 bug by another door.
- [ ] Every name gets an `EXERCISE_BODY_REGION` entry (lower_body), or it
  silently leaves every sector total. `weekly_tonnage` returns unmapped names
  as its second value — check it comes back empty.
- [ ] `sessions.movement_category` resolves every name.
- [ ] Names match EXACTLY between the plan day and the dicts — one hyphen once
  turned a hard block into silence in `rules.py`; the same class of bug applies
  here.
- [ ] The session logs an honest sRPE (expect 4–6; it is training). Unloaded
  holds count in reps and seconds, never kilograms — existing tonnage rule.
- [ ] **Every new plan day authors `day_type`** (`scheduling.SESSION_PRIORITY`
  vocabulary: gym days `"main"`, the cluster session `"stretch"`, recovery
  days `"rest"`, any assessment day `"test"`), on ALL days of the block in the
  same commit — partial adoption silently kills the readiness auto-shift
  (unknown mover vs known partner refuses every swap), and
  `test_every_stage2_day_carries_a_valid_day_type` is the model for the
  coverage test the new block needs. This is what makes a missed cluster
  session reschedulable onto a rest day, and what keeps a carried main off
  the day before the retest.

### 5 · Judge the holds at the same sitting

The reassessment evaluates *no increase in Coxa Saltans frequency under loaded
squat/split-squat work* — the exact condition holding horse stance, both
Cossacks, and the battery's 90° leverage test. Clean → the holds lift (stacks
C/E/H regain their items; the battery regains its middle leverage). Not clean →
they stay held. Either way the outcome is RECORDED against
`cluster_a_mechanics.DEFERRED` and the battery's `leverage_90` — a hold judged
on its condition, not expired by a date.

### 6 · The retest lands mid-block — schedule it now, and the app watches it

Four weeks from the first pattern puts the retest around mid-September, inside
the new block. Cold, in the morning, BEFORE any training that day, only the
slots below the one being fixed — **and never the morning after leg training**
(athlete's rule, 2026-08-07): a leg day the day before reads as extra tightness
in exactly the areas being tested, so the reading measures the leg day rather
than the baseline. The same contamination class as a warm-up, one day earlier.

This is surfaced, not remembered: `services/flexibility.retest_readiness()`
computes the status from the last assessment date plus the logged leg days
(judged by `EXERCISE_BODY_REGION` — the same map the sectors read), and

- the **training screen** banners the day before ("keep today off the legs",
  or "swap today" when today's session already loaded them) and the day of;
- the **flexibility screen** shows the due date and whether the morning it
  falls on is clean;
- the **capture cold gate** warns when yesterday loaded the legs — warn, never
  block, but it says what the reading would mean.

When the block is authored, place the retest morning after the rest day the
placement in step 2 already produced. Separately: three baseline mornings are
still owed; until they exist every threshold stays provisional and
`CHANGE_NOTHING` applies — no mid-block recalibration off a single reading.

### 7 · The pull-back condition, written before starting

Same idiom as `HRV_GARMIN_HOLD`: the exit is defined before the entry. The
cluster drops from 2× to 1×, or pauses entirely, when ANY of:

- a symptom-log entry attributable to cluster work — a new region, or a
  worsening trend; NOT DOMS-grade tightness ≤ 3 with pain 0;
- a readiness downtrend across a week-plus that coincides with the cluster
  addition and has no better explanation;
- sustained ACWR advisory flags in weeks containing cluster sessions.

Resume when the signal clears. A pause is a hold on evidence, not a deletion.

---

## What this protocol deliberately does not do

No engine wiring — flexibility is not a safety input and stays out of the
traffic light. No new `services/rules.py` entries — every movement named in the
three cluster documents already resolves. No automation of the physio's three
Day-28 decisions — those are theirs; this session is ours, and the only place
the two meet is the shared weekly capacity in steps 1–3.
