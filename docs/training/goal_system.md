# Goal system

*Set by the athlete on 2026-10-14, while walking through the slot procedure one
step at a time ("Let's go through the procedure together, each step so I know it
works before approving"). This file is the input to the procedure's later steps:
body areas and jobs, weekly dose, exercise choice, placement, warm-up, checks.
Status of each part is marked: APPROVED, DRAFT or OPEN.*

---

## The rule for every goal — APPROVED (athlete, 2026-10-14)

- Every goal has a **proof**. The proof is the goal: a result that can be measured.
- To reach the proof, list the **blockers** and order them, **biggest first**.
  Work on the biggest blocker first, then go down the list.
- Each blocker has its own proof, so that it is known when to move to the next
  one — APPROVED 2026-10-14.
- **When two goals compete for time, goal A wins** — APPROVED 2026-10-14
  (*"goal A is more important, it is the current issue and the long term"*).

## The gym rule — APPROVED (athlete, 2026-10-14)

A gym session exists to build muscle, plus fatigue work and conditioning
(*"you don't go to the gym unless you want to maximize muscle growth and other
fatigue related exercises, cardio"*). This decides how every strength session is
built, in every stage. It is not a separate goal.

---

## Goal A — run 21 km — the MAIN goal

**Proof:** the 21 km run. The run is not the target in itself: it proves that
the hips and back can take regular training (*"It's a goal to a problem"*).
He calls it a marathon; the distance is 21 km.

**Blockers, biggest first** (athlete, 2026-10-14):

| # | Blocker | Proof that it is done |
|---|---|---|
| 1 | Hips and lower back — weakness and overuse | Gate 1, parts 1 and 2 |
| 2 | Muscle strength | Gate 1, part 3 |
| 3 | Cardio and running longevity | Stages 2 and 3, then the 21 km run |

**Stages** — five sessions a week in every stage, which matches the stage-2
safety limit (`services/rules.py`, `session_freq_max` 5):

| Stage | Week | Starts when |
|---|---|---|
| 1 | 4 strength + 1 flexibility, **no running** | 2026-10-14 |
| 2 | 3 strength + 1 run + 1 flexibility (a trial) | Gate 1 passes |
| 3 | 2 strength + 2 runs + 1 flexibility — the most running, ever | Gate 2 passes |

**Gate 1 (stage 1 → 2)** — APPROVED 2026-10-14. All must be true:

1. **Regular training:** 6 weeks in a row with all 4 strength sessions done.
   Six weeks is two times the gap between the recent flare-ups (2026-08-25,
   09-16, 10-05 — about three weeks apart). The record's longest run of regular
   training is 7 weeks, 2026-06-29 → 08-16, at 4-6 days a week, with no running.
2. **No flare-up in those 6 weeks.** A flare-up is a planned session missed,
   shortened or changed because of the hips or the back. A week lost to travel
   or illness PAUSES the count; a flare-up RESETS it to zero. Every missed
   session needs a reason (one tap); the count does not move until it has one.
   (On 2026-10-14 the app recorded only what happened to a missed session —
   moved, dropped, left — never why, and check-ins had fallen to 0-1 a week.)
3. **Strength:** each main lift's working weight 10% above its weight on
   stage 1 day 1. The lift weights, not the strength score: they are read
   directly, and the score is a model still settling.
4. **Test day before the first run** — APPROVED 2026-10-14: a 30-minute brisk
   walk, then single-leg calf raises and hops, all without pain. It replaces
   *"or we're in a position where we believe that we can start"*, which cannot
   be a gate, and checks the left groin muscle (Sartorius, strained twice by
   running volume) against impact before the first run.

**Gate 2 (stage 2 → 3)** — APPROVED: the same rules over 6 weeks of stage 2,
with the run counted as a session.

**Going back** — APPROVED: a flare-up in stage 2 or 3 sends him back one stage.

---

## Goal B — 20 kg overhead press — APPROVED 2026-10-14

**Proof:** a SEATED DUMBBELL press, **20 kg in each hand × 5 reps** — APPROVED
2026-10-14. His 2025 best was 15 kg × 9 in each hand, on 2025-06-28 (source:
`Input_files/2025-training-year.md`), about 19.5 kg for one rep by the Epley
estimate, so 20 kg × 5 is about 20% past it. The plan already runs a heavy set
of five, so the proof uses a format he knows.

**Blockers, biggest first:**

| # | Blocker | Proof that it is done |
|---|---|---|
| 1 | The right shoulder sits tilted inward — the front of the right shoulder, the shoulder-blade muscles on both sides, and the left side's extra work (APPROVED 2026-10-14) | **Lying on the back, BOTH shoulders touch the floor** (athlete: *"I want to be able to do a shoulder press straight, this means when I put my shoulders on the ground. Both shoulders touch the ground. Currently only the left touches the ground"*). The exact protocol is OPEN |
| 2 | Strength of the press muscles and the small muscles around the shoulder, over a long period | The goal's proof |

**His reading of blocker 1** (2026-10-14): *"a middle back problem I think with
over tight pecs."* The record supports the tight front of the right shoulder: a
cramp in shortened tissue next to the surgical scar, which the physiotherapist
read on 2026-08-10 as scar adhesion around pec minor, and prescribed release
plus active work for the front of the shoulder. The Latarjet moved the bone that
pec minor attaches to, and the record already holds one range the surgery
limits on the right (a face-down arm raise, 20 cm right against 40 cm left,
2026-08-13) — so part of the gap may not close, and the protocol needs a rule
for when it stops closing.

**The floor test is ONE QUESTION in the 12-week flexibility test** — APPROVED
2026-10-14 (*"floor test to be added to flexibility and can be a questionnaire,
I don't want to be doing a test often - every 12 weeks is ok"*). No photo, no
ruler, no extra mornings. The question: *lying on your back on a hard floor,
knees bent, arms by your sides, after a full breath out — does the back of each
shoulder touch the floor? Right: yes / almost / no. Left: yes / almost / no.*
**Pass:** both "yes". **Stall:** the right answer is the same at two tests in a
row — then the cause is reviewed before more of the same work.

**The press does not wait for blocker 1** (athlete, 2026-10-14: *"keep pressing
just work on that as well"*): the press weights rise by the normal load rule
(Key Rule 23) while blocker 1's work runs beside it.

**Blocker 1's work, decided 2026-10-15** (athlete: *"Release is good for the
shoulder only right side, then activation of the back muscles, like Y prone and
scapular exercises. Rotator cuff is not weak, I've trained them extensively over
the years. It needs to tackle the angle of my shoulder - it's not perfectly
straight but pointed inwards. Neck tension is also there."*):

- **The target is the shoulder's ANGLE** — the right shoulder points inward.
- **Release on the RIGHT side only**, then **activation of the back muscles**
  straight after it: the prone Y raise and the shoulder-blade exercises. This
  replaces the physiotherapist's "active work" half (an inward-press and
  outward-rotation drill, which is rotator-cuff work).
- **The rotator cuff is NOT a target** — he has trained it for years and it is
  not weak. Removed from the step-2 areas.
- **Neck tension is part of the problem** — RIGHT side, dragging the right
  shoulder up slightly (athlete, 2026-10-15). New: the record's earlier neck
  findings (2026-07-31, 2026-08-13) are all on the LEFT. It matches the 2025
  log's "right scapula elevated" early that year. Job: **strength at length**
  — his "working stretch" (2026-10-15).
  The safety rules read "neck side bend" as the LOWER-back side-bend rule
  (2026-10-15), so step 5 needs a neck rule of its own.
- **"Tender spots" were never observed.** The release technique's text says
  "pin one tender spot"; the record holds no tender spot on his shoulder, and
  the log holds no session of the release (checked 2026-10-15). A technique's
  wording is not a finding.

**Equipment, decided 2026-10-15** (athlete: *"barbells in most situations will
be out for now. RDL are okay but overhead press and squat lets do machine
only"*): the **squat and the overhead press are MACHINE-ONLY**; the Romanian
deadlift stays free weight (dumbbells); barbells are out in most cases. OPEN:
the proof is a seated DUMBBELL press — kept as the goal, with the machine as the
training tool until blocker 1 passes — APPROVED 2026-10-15: the proof stays the
seated dumbbell press, 20 kg × 5, and the training moves to dumbbells when both
shoulders touch the floor.
The safety rules return "unknown" for "machine shoulder press", "seated dumbbell
shoulder press" and "hip thrust machine" (2026-10-15) — "unknown" is not a
clearance, so step 5 adds a rule for every name it chooses.

## Goal C — flexibility that lasts — APPROVED 2026-10-14

A separate goal: to be more flexible, and to keep it. One session a week in
every stage. The skills are the side split and the pancake (Cluster A).

- **Proof:** the side split and the pancake at their targets, and still there at
  the next 12-week retest ("lasts").
- **Blockers:** the flexibility test's ladder, first failure first — the test
  already works by the blocker rule: it runs in a fixed order and STOPS AT THE
  FIRST FAILURE, and that failure is the biggest blocker. Each blocker's proof is
  its rung's target, confirmed at a retest.
- **Now:** its one stored assessment (2026-08-12) reads **pattern D**: the
  adductor group with the knees bent, 21.5 cm against a 10 cm target. That was
  one morning, so it is not yet trusted; **the next retest (due about
  2026-11-04, 84 days on) runs three mornings** to set the noise floor.

---

## Step 2 — body areas and jobs — APPROVED 2026-10-14

**Blockers inside one goal run SIDE BY SIDE**; the order decides which one gets
time first. Only a stage gate holds work back, as gate 1 holds the running
(athlete, 2026-10-14, confirming his *"keep pressing just work on that as
well"*).

**The five jobs.** Every area has exactly one; it sets the dose (step 3) and
the effort (step 4).

1. **Strength and size** — hard sets that make the muscle grow.
2. **Strength at length** — holds or slow reps with the muscle in its long
   position, for muscles that are tense but not short.
3. **Control** — position and timing, in short efforts, never to failure.
4. **Range** — making the tissue longer, in the flexibility session.
5. **Endurance** — heart and lungs.

**Goal A — hips and back, blockers 1 and 2:**

| Area | Job | Source |
|---|---|---|
| Glute max | Strength and size | Weak list (assessment 2026-06-28) |
| Abs, front and sides | Strength and size, to failure | Weak list; his decision 2026-10-14 |
| Deep back muscles | Strength and size | Weak list |
| Hamstrings | Strength and size, through full length | Tense at the sit bones (2026-10-05); normal length (Jan 2025) |
| Hip rotators (the pelvis twist) | Strength and size — hip airplane, 3 × max, not every day | Finding #7 (2026-10-05); his decision 2026-10-14 |
| Hip flexors | Strength at length | Tense, not short (Thomas test 2026-10-05); his rule 2026-08-24 |
| Left lower ribs | Control | Left ribs flare (2026-10-05) |
| Upper glutes and piriformis | Control — NO direct work; they settle when the weak muscles take their share | Tense list |
| Main lifts (legs, back, chest, shoulders) | Strength and size | Gate 1: +10% |
| Heart and lungs (blocker 3) | Endurance — none in stage 1 beyond the 15-minute walks to the gym (his choice); the running starts at gate 1 | Stage system |

**Goal B — the press, blockers 1 and 2:**

| Area | Job | Source |
|---|---|---|
| Front of the right shoulder (pec minor, scar) | Range — release, RIGHT side only, followed straight away by the back-muscle activation (changed 2026-10-15) | Physiotherapist 2026-08-10; his decision 2026-10-15 |
| Middle back | Range — to be tested | His reading 2026-10-14 |
| Neck tension, RIGHT side, pulling the right shoulder up | Strength at length — head tilted to the LEFT, then 10-second pushes into the hand or pulls away from it, 5 seconds' rest (his choice 2026-10-15) | His report 2026-10-15 |
| Shoulder-blade and back muscles, both sides | Strength and size — the prone Y raise and the shoulder-blade exercises come straight after the right-side release (his decision 2026-10-15) | Physiotherapist 2026-08-10: the right is weaker, the left works too much |
| ~~Rotator cuff~~ | REMOVED 2026-10-15 — not weak; he has trained it for years | His correction |
| Press muscles — shoulders, triceps, upper chest | Strength and size | The 20 kg × 5 proof |

**Rule for the left side (applies at step 5):** single-arm work where possible,
so that the left cannot do the right's work.

**Goal C — flexibility, the current blocker:**

| Area | Job | Source |
|---|---|---|
| Adductors, knees bent | Range, plus strength at length (the adductor ladder) | Flexibility test 2026-08-12: 21.5 cm against a 10 cm target |

**Overlaps:** glute max, the hamstrings and the deep back muscles serve goal
A's blocker 1 AND the main lifts — one exercise counts for both. The adductors
serve goal C and the hips in goal A. The shoulder-blade muscles serve goal B
and protect the right shoulder in every press and pull.

---

## Step 3 — the weekly dose — APPROVED 2026-10-14 (the shoulder row 2026-10-15)

**Nothing waits on the next flexibility retest** (athlete, 2026-10-14: *"don't
wait on that flexibility result I don't plan to do it soon"*). Goal C works from
the 2026-08-12 reading. When the retest happens it runs three mornings once, to
learn the day-to-day spread, then one morning every 12 weeks; the shoulder floor
question is answered at that same test.

**Counting rules:**

- A **hard set** ends 0-3 reps before failure. Ramp sets and warm-up sets do not
  count.
- A set counts **1** for the area it trains most and **0.5** for one second area
  (a Romanian deadlift: 1 hamstrings, 0.5 glute max).

**The table:**

| Job | Days a week | Hard sets a week (minimum) | Effort |
|---|---|---|---|
| Strength and size, priority 1 — glute max, abs, deep back muscles, hamstrings | 2 or more | 10 per area | 0-3 reps left; failure where step 4 allows |
| Strength and size, priority 2 — the main lifts (quads, chest, back) and goal B (shoulder-blade and back muscles, press muscles; the rotator cuff removed 2026-10-15) | 2 or more | 6 per area | 0-3 reps left |
| Hip airplane (his dose) | 2 | 3 × max each day | to failure |
| Strength at length — hip flexors, adductors | 2 or more | 6 per area | hard; stop before the position slips |
| Control — left lower ribs | every strength day | 1-2 short sets | easy, never to failure |
| Range — front of the right shoulder: release, right only | the upper-body days, straight before the back-muscle work (APPROVED 2026-10-15) | about 3 minutes | the release half of the physiotherapist's protocol |
| Range — middle back | 2 | 1-2 short items | easy |
| Range — the flexibility skills | 1 (the flexibility day) | the flexibility plan | — |
| Endurance | none in stage 1 | — | — |

**Why:** 10 hard sets a week per muscle gave more growth than 5-9, and 5-9 more
than under 5 (Schoenfeld, Ogborn & Krieger 2017, J Sports Sci, meta-analysis).
Twice a week gave more growth than once (Schoenfeld, Ogborn & Krieger 2016,
Sports Med). Sets close to failure give most of the growth and taking every set
to failure adds little (Refalo et al. 2023, Sports Med). Priority 1 gets 10
because goal A wins; the rest get 6 because time is limited.

**Fit (estimate, 2026-10-14):** the table needs about 85-90 hard sets a week
after the 0.5 counting. One 70-minute session holds about 20-22 hard sets with a
10-15-minute warm-up and the measured changeovers, so four hold about 80-90. It
fits only just, and NOT with the 18-25-minute warm-up of 2026-10-14 — the
warm-up limit (step 7) is a hard limit.

**The front of the right shoulder — partly decided 2026-10-15.** The two
exercises exist (`PEC_SCAR_RELEASE`, `ANTERIOR_SHOULDER_RECIPROCATION`), retired
from the accessory session on 2026-10-13 and never logged. His decision: the
release stays, RIGHT side only, and the active half is replaced by back-muscle
activation (prone Y raise, shoulder-blade exercises) straight after it. The
release's old dosing rule ("drop to twice a week when a week finds nothing
tender") is void: no tender spot was ever observed. How often: the upper-body
days (APPROVED 2026-10-15).

---

## Step 4 — effort per exercise type — APPROVED 2026-10-15

Working sets end **1-2 reps before failure** (the counting rule is unchanged: a
set within 3 reps of failure still counts as a hard set). The session's overall
rating stays at RPE 8 or below.

| Exercise type | Effort |
|---|---|
| Machines and cables — machine squat, machine shoulder press, pulldown, cable row, face pull, Pallof press | Working sets 1-2 reps short; the LAST set to failure |
| Dumbbell Romanian deadlift | 1-3 reps short; never to failure (his one squat injury came from overload and fatigue; failure causes the most fatigue) |
| Dumbbell incline press | 1-2 reps short; never to failure (the right shoulder's history) |
| Single-arm row, prone Y raise, shoulder-blade work | 1-2 reps short; the last set to failure |
| Abs, hip airplane, body-weight work | Every set to failure (his decision; light loads need it) |
| Strength at length — hip-flexor holds, adductor ladder | Hard, never to failure |
| Control and range items | Never to failure |

**Evidence, verified 2026-10-15:** stopping 1-2 reps short grew trained lifters'
thighs about as much as failure, with less fatigue (Refalo et al. 2024, J Sports
Sci 42(1):85-101, n = 18); across 15 studies failure was not clearly better
(Refalo et al. 2023, Sports Med 53(3):649-665); growth rises as sets end closer
to failure (Robinson et al. 2024, Sports Med 54(9):2209-2231); guesses of reps
left are less accurate further from failure and above 12 reps (Halperin et al.
2022, Sports Med 52(2):377-390); with light loads (30% of max) stopping short
gave about a third of failure's growth, at 80% no difference (Lasevicius et al.
2022, J Strength Cond Res 36(2):346-351, untrained men).

---

## Step 5 — exercise choice — IN PROGRESS (opened 2026-10-15)

**Proposed, not yet approved** — filters, in order: (1) the safety rules know
the exercise and do not block it at the stage ("unknown" fails until a rule is
added); (2) no observed finding or decision blocks it; (3) the equipment rule
and the gym's equipment allow it; (4) it can reach step 4's effort; (5) the app
can log and progress it. Ranking among those that pass: (1) safety margin for
his findings; (2) directness; (3) known tolerance; (4) time. The first that
passes is picked, and the next is added if the area needs more sets.

**Tier lists — APPROVED 2026-10-15:** train only from the **S and A** tiers of
a recorded list (`docs/training/tier_lists/`; abs first, then chest, back and
shoulders). For a listed group the ranking is **tier first, then safety
margin** (*"Tier then safety as safety will change with time"*). A list never
replaces the filters. **Caution in the safety rules means allowed** (*"Yes
caution but allowed"*). **Abs picks:** upper — the lat-pulldown cable crunch
facing away (S); lower — the reverse crunch on an ab mat (S); sides — the
heavier Pallof press and the side bridge to failure, outside the list until a
list covers them (approved). The weighted dead bug (C tier) is out.

**Corrected 2026-10-15:** the 2026-10-05 "no hollow hold, no leg raises"
exclusion was the choice of the session that picked his ab work, not a
decision he stated. His call on it is pending; it does not change the abs
picks above.

**Open from 2026-10-15:** the neck's job (proposed: range), approval of the
filters and the ranking, the gym's machines, the goal A picks, and the tier
rule above.

**Answers of 2026-10-15 (second round) — APPROVED:**

- **The leg-raise family stays out until gate 1 passes** (*"Yes out until gate
  1 passes"*); then it can come back.
- **The five step-5 filters** are approved.
- **His gym has:** leg press, hack squat, seated leg curl, lying leg curl, 45°
  back extension bench, hip thrust machine, machine shoulder press, machine
  chest press. **No belt squat.** **A Smith machine is NOT a barbell** under his
  rule (*"barbell is free moving weight"*). Not yet confirmed: Smith machine,
  leg extension, glute-ham raise, pendulum squat, calf machines.
- **Sides:** the high-to-low cable woodchop and the side plank with hip raises
  replace the Pallof press and the plain side bridge (see the abs tier file).
- **Neck:** job "strength at length" (above). Evidence, checked 2026-10-15:
  over weeks, contract-relax (PNF) and static stretching gain about the same
  range, and both gain more than dynamic stretching (Konrad et al. 2024, J Sport
  Health Sci 13(2):186-194, meta-analysis); for the neck itself, trials of this
  exact method (post-isometric relaxation of the upper trapezius) are small —
  both it and plain stretching help, one small trial favoured it. Not shown to
  be better in the long term; shown to be at least as good, with a strength
  part added. Effort and days: OPEN.
- **The plan is FULL BODY every strength session** (*"I want the plan to be a
  full body exercise plan for each day. not spilt into upper, lower etc"*) — a
  step-6 rule. It means the day before the flexibility session must be a rest
  day, because every strength day loads the legs.

**Picks from the new tier lists (tier first, then safety margin):**

- **Quads:** hack squat (S; his gym has it). The Bulgarian split squat (S) waits
  on whether his "squat machine only" rule covers it.
- **Glutes:** walking lunge (S+) and the 45° back extension (S), then the
  machine hip thrust (high A) and the Romanian deadlift (high A). The machine
  hip abduction (S) is OUT: no direct work for the upper glutes (step 2).
- **Hamstrings (no tier list):** the dumbbell Romanian deadlift and the seated
  leg curl, by the safety-first ranking.

**Answers of 2026-10-15 (third round) — APPROVED:**

- **Neck dose:** about half effort, 2 sets of 4 efforts (10 seconds on, 5 off),
  on 3 strength days a week.
- **The Bulgarian split squat is always allowed** — a dumbbell exercise, not a
  barbell one (*"Yes bulgarian squat are always allowed"*).
- **Gym:** the Smith machine, leg extension, glute-ham raise, pendulum squat and
  calf machines are taken as present until he finds one missing.
- **Areas with no ranked list** keep the safety-first picks until he sends a
  tier-list video for them.
- **Calves** become an area at stage 2.

**The reading rule — his question, *"when is this going to be reviewed"*:**
every area has ONE file in `docs/training/tier_lists/` with its ranked list and
the unranked advice from videos that rank nothing; there are no separate notes
files. Step 5 reads the file of every area each time a plan is built, and every
pick records its file and part. At the build (step 8) the lists become data,
and a check fails if a pick has no source in its area's file.
`tests/test_tier_lists_indexed.py` fails if a file drops out of the index.

**Shoulders (`docs/training/tier_lists/shoulders.md`):** front delts — the
machine shoulder press (A+, the list's best for the front delts, and his
machine-only rule). OPEN: whether the side and rear delts become areas; if they
do, the picks are the cable lateral raise (S+, to shoulder height, thumb not
turned up) and the reverse cable crossover (S, the right arm stopping at the
line of the body), both under the right shoulder's limits.
