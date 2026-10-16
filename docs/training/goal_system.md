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

**The right shoulder's written limit — his question, 2026-10-15** (*"Where did
that safety limit come from ?"*, about "never turn the arm out at 90° to the
side"). It comes from the Cluster D shoulder documents (`Input_files/`, added
2026-08-06): a general precaution for a shoulder that dislocates forward, to
hold "until a physio clears" the position. It was copied into the safety rules
the same day ("external rotation" and "abduction", both "caution", right side)
and into the release protocol on 2026-08-10. Nothing in the record shows that
his surgeon or physiotherapist gave it, and no test of his shoulder produced
it; the physiotherapist was never asked, and the physio gate was retired on
2026-08-17. The one MEASURED right-shoulder limit is different: less range with
the arm behind the body (a face-down arm raise, 20 cm right against 40 cm left,
2026-08-13).
Evidence, checked 2026-10-15: the Latarjet is built to hold the shoulder in
that exact position (the moved tendon slings the front of the joint when the
arm is out and turned out); rehab protocols protect the position for the first
months only, and some keep presses and pulldowns behind the head, dips and the
wide-grip bench out on the return to the gym; about 9 in 10 people return to
sport, overhead sport included; and instability returns in more people the
longer they are followed (5-26% in studies of 10 years or more). His own risk
factors are real: hypermobility, a shallow socket, and a first repair that
failed.

**REMOVED 2026-10-16 — his decision** (*"remove it, I don't have any problems
with this and have been doing shoulder presses for years without issue.
Although I avoid pull downs that go behind the back, other than that the rest I
have been able to do during this time without issues. But I guess getting rid
of them makes sense as I get older and don't want any issues"*):

- **The 90° limit is gone** from every plan rule. The source documents are
  annotated in place (`Input_files/cluster_d_prescription.md`, with a backup in
  `Input_files/backups/`; `docs/training/release_protocols_2026-08-10.md`).
- **Pulldowns behind the head stay out** — he already avoids them.
- **Also out, as a precaution with age — CONFIRMED 2026-10-16** (*"Yes that is
  correct agree"*): the other end-range lifts with the arm behind the body —
  presses behind the head, dips, and the deep wide-grip bench.
- **The MEASURED limit stays:** the right arm stops at the line of the body in
  flyes, the reverse cable crossover and the face pull.
- **Revert condition — CONFIRMED 2026-10-16:** the 90° limit comes back if the
  right shoulder ever feels unstable — the feeling that it may slip forward.
- **The old wording is DELETED, 2026-10-16** (*"Delete the wording from there
  too"*): from the 16-minute shoulder yoga flow (the wall press is now
  "cleared"; the prone hold and the chest opener keep their positions, the
  prone hold's caution now resting on the measured limit), the deep-lunge
  note of the hip flow, the retired anterior-shoulder reciprocation drill
  (`training_plan.py` and its rule), the Stage 2B band chest press warning,
  and the "abduction" and "external rotation" rule texts.
  `tests/test_shoulder_limit_removed.py` fails if the wording comes back. Dated
  records keep it, annotated or untouched: the Cluster D prescription and the
  release protocol (annotated), and an August design mockup
  (`mockups/flexibility_v2_architecture.html`, a deleted model).

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
| Left lower ribs | Covered by the abs work (changed 2026-10-16, when the 90/90 hip lift came out of the new block); it was "Control" | Left ribs flare (2026-10-05) |
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
| Side delts | Strength and size | His decision 2026-10-15 (*"side and rear delts are nearly more important for me"*) |
| Rear delts | Strength and size | His decision 2026-10-15 |

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
| Strength and size — side delts, rear delts (areas from 2026-10-15) | 2 or more | 6 per area — priority 2 (his decision 2026-10-16: *"yes 6 sets"*) | 0-3 reps left |
| Hip airplane (his dose) | 2 | 3 × max each day | to failure |
| Strength at length — hip flexors, adductors | 2 or more | 6 per area | hard; stop before the position slips |
| Control — left lower ribs | every strength day | 1-2 short sets | easy, never to failure |
| Range — front of the right shoulder: release, right only | the upper-body days, straight before the back-muscle work (APPROVED 2026-10-15; every day is full body now — the days are decided at step 6) | about 3 minutes | the release half of the physiotherapist's protocol |
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

**APPROVED 2026-10-16 — a lower REQUIRED dose that three sessions meet, with
the fourth session a bonus** (*"Approved with all recommendations"*) (*"Then our goal is too high for sets per week,
Research and find out what is the minimum. I'd like to aim for a 3 day week
meets the required goal and a 4th day is a bonus"*). The evidence is in
`docs/training/weekly_volume_minimum_2026-10-16.md`: 10 sets a week is the figure
for the most growth, about 4 hard sets the practical floor, and strength needs
less. Proposed: priority-1 areas 6 hard sets a week on 2 days; priority-2 areas
4, counting half-sets; the hip flexors' strength-at-length work 3; the hip
airplane and the adductor ladder unchanged. Placed by the rules: three core
sessions of 54, 57 and 59 minutes meet it; the bonus session (60 minutes) lifts
the priority-1 areas to 9-16.

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

## Step 5 — exercise choice — COMPLETE 2026-10-16 (opened 2026-10-15)

**Every pick is approved.** The marks below that still read "proposed" or
"OPEN" were settled later in this file: the five filters (2026-10-15), the neck
dose (2026-10-15) and its place at home (2026-10-16), the side and rear delt
dose (2026-10-16), and the back and chest picks (2026-10-16).

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
  leg curl, by the safety-first ranking. *A ranked list arrived later the same
  day — see the fourth round: the Romanian deadlift is S there, and the curl
  depends on the open two-list rule.*

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
machine-only rule).

**Answers of 2026-10-15 (fourth round) — APPROVED:**

- **The side and rear delts are areas** (*"Yes side and rear delts are nearly
  more important for me"*). Picks: side — the cable lateral raise (S+); rear —
  the reverse cable crossover (S). The dose is OPEN (step 3).
- **The right shoulder's limits on the picks** (*"Yes agree"*): the lateral
  raise to shoulder height, thumb not turned up; the crossover's right arm
  stops at the line of the body; the face pull without the turned-out finish.
  Agreed before he learned where the 90° limit came from (goal B). **Changed
  2026-10-16, when he removed that limit:** the lateral raise is done as the
  source describes it (no thumb rule); the face pull keeps its turned-out
  finish, with the right elbow stopping at the line of the body; the
  crossover's right arm still stops at the line of the body (the measured
  limit). The cable Y raise (S) is a candidate on the right again.
- **A cap for step 6** (*"Yes agree to rule"*): about 6-8 hard sets per muscle
  per session. It is Jeff Nippard's rule of thumb (beyond it, more adds
  little), not a tested limit.

**New lists, 2026-10-15 (six videos):**

- **Hamstrings now have a ranked list** (`tier_lists/hamstrings.md`, a "hams
  and glutes" list). It also ranks glute and lower-back exercises: its glute
  rows are copied into `glutes.md` and its lower-back rows into the new
  `deep_back.md`.
- **Duplicates:** video 2 (Jeff Nippard's glute list) and video 4 (Built With
  Science's leg workout) were already recorded — checked, nothing changed.
- **Advice** from videos 1, 5 and 6 is in the hamstring, glute, quad and
  deep-back files.
- **One cited trial is under data doubt:** the 12-week squat-against-hip-thrust
  trial (Barbalho et al. 2020), cited by two of the videos; see `glutes.md`.

**APPROVED 2026-10-16 — two ranked lists for one area** (*"2 agree"*): an
exercise qualifies if ANY list puts it in S or A; it ranks by its best tier; a
tier given without a named version counts for each version his rules allow;
and when a checked trial compared two exercises directly, the trial's winner
ranks first. Consequences: the seated leg curl stays ahead of the lying curl
(Maeo et al. 2021), although the hamstring list rates lying S and seated A; the
step-up qualifies through Nippard's low A, although the second list rates it D;
the reverse lunge (S) joins the glute candidates.

**The deep back pick — APPROVED 2026-10-16** (*"yes agreed"*): the 45° back
extension, back straight, up to a straight line — it counts 1 for the deep back
muscles and 0.5 for glute max. It was listed as a glute pick (S); the glutes
keep the walking lunge, the machine hip thrust and the Romanian deadlift.

**His question of 2026-10-16 on the two-list rule** (*"is step up a A or D
so?"*): under the proposed rule, the step-up onto a box at or above knee height
is **A** (Jeff Nippard's low A — the list names that version); a step-up onto a
lower box is **D** (only the second list covers it). Either way it is not
picked now: six S-tier glute exercises rank above it (walking lunge, Smith
lunge with the front foot raised, machine hip thrust, reverse lunge, Romanian
deadlift, 45° back extension). He chose the rule above over the stricter
"when lists disagree, the LOWER tier counts". **The hamstring curl pick is the
seated leg curl** (the trial clause: Maeo et al. 2021).

**Safety rules for the picks — AGREED 2026-10-16** (*"3 agree"*): write a rule
for every picked exercise the safety check calls "unknown", and show him the
list (exercise, result, one-line reason) before it goes into
`services/rules.py`.

**The list — APPROVED 2026-10-16** (*"yes"*), now in `services/rules.py` and
pinned by `tests/test_goal_system_pick_rules.py`. One change in the building: the
lunge rule's keyword is "lunge (db)", not "walking lunge" — a caution keyword
also matches any name it contains, so "walking lunge" would have turned plain
walking into a caution. Already known:
the crunches, Romanian deadlift, back extension, hack squat, Bulgarian split
squat, hip airplane and psoas march are "caution" (allowed); the face pull and
the prone Y raise are "cleared". New rules:

| Exercise | Result | Reason (one line) |
|---|---|---|
| Walking lunge | caution, right | The "walking" rule cleared it by mistake. Right hip bent past 60° at the bottom: knee and toes point straight ahead (Key Rule 7). Keyword "walking lunge", so the yoga lunges are not caught |
| High-to-low cable woodchop | caution | Turning under load: the turn comes from the hips and upper back, the lower back stays still |
| Side plank with hip raises | caution | Lowering and raising the hips is a side bend under body weight (the side-bend rule) |
| Machine hip thrust | caution | Stop at a straight line at the top, pelvis tucked (the L5/S1 extension rule) |
| Seated leg curl | cleared | A knee bend with the back supported; no load on the spine |
| Machine shoulder press | cleared | Back supported; the press goes up in front of the head, never behind it |
| Seated dumbbell shoulder press (the goal-B proof) | cleared | The same |
| Cable lateral raise | caution, right | On the right, the cable starts in front of the body (the measured limit) |
| Reverse cable crossover | caution, right | The right arm stops at the line of the body (the measured limit) |
| Neck working stretch (right) | caution | The hand only resists the push; it never pulls the head further (no pressure into range at Beighton 6/9) |

The chest and back picks get their rules when he approves them.

**The tier decider — BUILT 2026-10-16** (*"I want you to take the deterministic
decider for tiers and use the same script to create a tier list for back and
chest, I can copy in later videos to see if you're correct but go for that for
now"*). `services/tier_decider.py` rates each exercise 0-2 on five things every
recorded list ranks on (stretch, target, stability, load, comfort; the ratings
and their rules are in `exercise_features.py`), scores them (stretch counts
three times), and turns the score into a tier with cut points calibrated on the
five recorded lists. On a list it was not calibrated on it gives the exact tier
41% of the time and comes within one tier 96% (guessing "A": 32% and 74%).
Its back and chest lists are in `tier_lists/back.md` and `tier_lists/chest.md`
and are used like source lists until his videos arrive.

**Picks from the decider, for his approval:** back — the single-arm dumbbell
row (S; his single-arm rule and known tolerance break the tie); chest — the
machine chest press (S; the chest is a gate-1 main lift, so its pick is a press,
and this is the S press confirmed in his gym).

---

## Step 6 — placement — APPROVED 2026-10-16

**Approved in parts the same day** (the rules, the four sessions A to D, the
three-core-plus-bonus week, the drop order, the neck at home, Tuesday's 61
minutes); `goal_week.py` and `services/placement.py` hold it, and
`tests/test_placement.py` checks it.

His request (2026-10-16): *"Can you bring understand each the exercise and
create a deterministic test to put them automatically in their correct
position?"* The answer: every exercise gets a CARD of facts; a fixed list of
rules places each card on a day and in a place in the session; tests fail when
a rule is broken. Nothing is placed by hand.

**Already decided:**

- **Every strength session is full body** (APPROVED 2026-10-15).
- **The day before the flexibility session is a rest day** — it follows from
  full body, because every strength day loads the legs.
- **About 6-8 hard sets per muscle per session** (APPROVED 2026-10-15).
- **OPEN:** the right-shoulder release was set for "the upper-body days"
  (step 3); those days no longer exist, so its days are decided here.

**The card — what the method knows about each exercise:**

1. Main area (counts 1) and second area (counts 0.5) — step 3.
2. Job — step 2.
3. Kind — compound (several joints), isolation (one joint), or preparation.
4. Pattern — knee bend, hip hinge or extension, push, pull, side delt, rear
   delt, trunk.
5. Demand — high (heavy, free weight or balance), medium or low.
6. Station — the machine, cable, bench or mat. It sets the changeover time
   (measured: 74 s to a mat, 117 s to a station, 158 s to a band set-up).
7. Sides — both together, one at a time, or right only.
8. Effort — step 4.
9. Dose — sets, reps or seconds, and rest.
10. Day rule, where one exists — e.g. the hip airplane on two days that are
    not in a row, the neck on three days.
11. Safety result and tier source — step 5.

**Week rules:**

- W1. 4 strength days, 1 flexibility day, 2 rest days. The day before the
  flexibility day is rest. Never 3 strength days in a row.
- W2. Two full-body sessions, A and B, in the order A, B, A, B.
- W3. Two exercises with the same pattern go one to A and one to B. An
  exercise with no partner follows its day rule, or goes into both sessions
  when its area needs the sets.
- W4. Every area reaches its weekly minimum (step 3), on 2 or more days.

**Session rules (the order):**

- S1. Preparation first (step 7 sets its content; limit 10-15 minutes).
- S2. Then the lifts, sorted by: compound before isolation; higher demand
  first; priority-1 areas before priority 2; the same station together; the
  name last, so a tie always breaks the same way.
- S3. A ramp set straight before its own lift (Key Rule 21).
- S4. Trunk work to failure, the hip airplane and the strength-at-length holds
  come last, so a tired trunk never comes before a heavy lift.
- S5. The right-shoulder release, then the prone Y raise, come straight before
  a chest or shoulder press (2026-10-16).
- S6. When an area has more picks than sessions need (the abs: four picks, one
  exercise a session), the slot rotates through them in rank order.

**Limits:**

- L1. At most 8 hard sets per area in one session.
- L2. At most 70 modelled minutes per session (Key Rule 21), measured with the
  app's own time model.
- L3. A session over the limit loses a WHOLE exercise — the lowest-ranked one
  whose areas all stay at their weekly minimum without it; sets are never cut
  below 3 (changed 2026-10-16, his fewer-exercises rule). If it is still over,
  stop and ask.
- L4. Every training exercise has 3 working sets (2026-10-16).

**The checks (tests):** the same cards always give the same week; every area
reaches its minimum; no area goes over 8 sets in a session; no session goes
over 70 minutes; preparation stays inside its limit; the order rules and the
day rules hold; every exercise has a known safety rule and a tier source.

**His answers, 2026-10-16 — APPROVED:**

- **Key Rule 21's six-exercise cap is REPLACED for full-body sessions** (*"yes
  replace it"*) by L1 and L2: at most 8 hard sets per area in one session and
  at most 70 modelled minutes. The code (`sessions.SESSION_SHAPE`) changes with
  the first full-body block.
- **Fewer exercises with 3 sets each, not more exercises with fewer sets**
  (*"I'd rather less exercises with 3 sets than less sets and more
  exercises"*). Two rules follow: every training exercise has 3 working sets;
  and L3 changes — a session over its limit loses a WHOLE exercise (the
  lowest-ranked one whose areas all stay at their minimum without it), never
  sets below 3.
- **The right-shoulder release comes straight before a chest or shoulder
  press, and only then** (*"The shoulder release is only needed when doing
  chest presses or shoulder press. It's to release the area before working on
  it"*). The prone Y raise follows the release, as approved on 2026-10-15.
- **Training days:** strength Monday, Tuesday, Thursday and Friday; rest
  Wednesday and Saturday; flexibility Sunday (*"yes agreed"*).

**Four sessions, A to D — his request, 2026-10-16** (*"Make a session C and D
and balance it out or make a session C to balance it and we can hold D as a
every week changing between AB and C"*). Four fixed sessions were chosen over
a rotating fourth day: with a rotation each week has a different set of
sessions, so an area can fall under its weekly minimum in some weeks; with four
fixed sessions the minimums hold every week.

**60 minutes is the target, 70 the maximum** (*"Also 70min is the Max, 60min is
the target Not 70 the target"*): a session over 70 breaks the week; a session
over 60 is reported.

**The rules are now code** — `services/placement.py` (P1-P7: fixed items, the
abs rotation, one knee and one hip lift a day, no two-day exercise on two days
in a row, least-time placement, a balancing pass, the order inside a day), the
draft cards in `goal_week.py`, `python scripts/draft_week.py` to print the week,
and `tests/test_placement.py`, which checks the week the rules produce and that
the checker catches a broken one. The same cards always give the same week.

**Draft 3, placed by the rules** (2026-10-16; the adductor ladder at home on
Wednesday and Sunday, as proposed — kept in the gym it puts two sessions 2-3
minutes over 70):

- **A, Monday — 67 min:** psoas march, 90/90 hip lift, neck; walking lunge,
  45° back extension; the release, prone Y raise, machine chest press, machine
  shoulder press; seated leg curl; lat-pulldown cable crunch; hip airplane.
- **B, Tuesday — 70 min:** psoas march, 90/90 hip lift, neck; Romanian deadlift
  and hack squat (each with a ramp set), 45° back extension, single-arm dumbbell
  row, cable lateral raise, reverse cable crossover; reverse crunch; psoas
  isometric.
- **C, Thursday — 69 min:** as A, with the woodchop for the abs and the psoas
  isometric for the hold.
- **D, Friday — 69 min:** as B without the neck, with the side plank with hip
  raises for the abs and the hip airplane for the hold.
- **Weekly hard sets:** every area at or above its minimum (glutes 18, abs 12,
  deep back 12, hamstrings 12, quads 9, press 9, shoulder blades 9, side delts
  9; chest, back, rear delts, hip rotators, hip flexors and adductors 6).

**Reaching 60 — measured with the same rules** (Monday, Tuesday, Thursday,
Friday): no ramp sets and the neck at home: 64, 63, 65, 65. Add each hold once
at home on Wednesday: 64, 63, 60, 59. Everything that needs no gym at home
(the three holds and the neck, on Wednesday and Sunday, about 20 minutes each
day) and no ramp sets: 58, 57, 60, 59. Removing exercises does not get there:
by L3 the only removable exercise is the walking lunge, which shortens only
Monday and Thursday. Ramp sets: the warm-up review found a ramp set adds about
nothing at loads near a 10-rep maximum, and this plan has no heavy top set.
**OPEN, his choice.**

**Four sessions a week — his decision, 2026-10-16** (*"Ok let's try 4 a week but
if I start missing and only going to three sessions then we can relook at it
after 12 weeks. We need to think of this deterministicly"*). Measured the same
day with the placement rules on the draft cards:

- **Why no exercise can go.** The weekly minimums (step 3) set the work, and
  each exercise carries part of an area's minimum. Taken out one at a time, every
  exercise but the walking lunge puts an area under its minimum: the back
  extension takes the deep back to 0 of 10; the Romanian deadlift or the leg curl
  the hamstrings to 6 of 10; the hack squat the quads to 3 of 6; the row, the
  chest press and the reverse crossover their areas to 0 of 6; any abs exercise
  the abs to 9 of 10; the hip airplane and the psoas isometric their areas to 0
  of 6. About 100 hard sets a week over four sessions is about 25 sets a session,
  which is where the 65-70 minutes come from: the time is set by the dose, not by
  the list of exercises.
- **One missed session, as the rules stand:** nothing can move — Wednesday would
  make three strength days in a row, and Saturday stays rest before Sunday's
  flexibility day — so the session is lost for that week. Five or six areas then
  end the week one session short (Monday missed: abs, deep back and hamstrings 9
  of 10; chest 3 and press 4.5 of 6; hip rotators 3 of 6).
- **A planned 3-day week** (Monday, Wednesday, Friday), every exercise kept: 85,
  82 and 86 minutes. Fitted to 70 by taking out the lowest-priority exercise of
  the longest session until each fits (the draft order below): 67, 70, 70 — the
  lateral raises, the reverse crossovers, one psoas isometric and one Y raise go;
  side delts 3 and rear delts 0 of 6, hip flexors 3 of 6, abs and deep back 9 of
  10. Fitted to 60, the chest, back, hack squat and more go too. The exercise
  choice does not change with the number of days; what changes is how often each
  exercise runs, and which areas give way is set by the drop order.

**PROPOSED, for his approval:**

- **Drop order** (highest priority first): goal A's priority areas (Romanian
  deadlift, back extension, walking lunge, seated leg curl, the abs); the hip
  airplane and the psoas isometric; the gate-1 main lifts (hack squat, shoulder
  press, chest press, row); goal B (the release with the Y raise, the reverse
  crossover, the lateral raise). It decides what a 3-day week, or any session
  over 70 minutes, gives up first.
- **A missed Monday or Tuesday session moves to Wednesday**, accepting three
  strength days in a row that week, so the week stays 4 of 4 for gate 1. A
  missed Thursday or Friday session cannot move (Saturday stays rest).
- **The 12-week review:** if 4 or more of the 12 weeks had 3 or fewer sessions
  (travel and illness weeks not counted), the plan is placed again for 3 days.

**Approved 2026-10-16** (*"Approved with all recommendations"*):

1. **The required dose** above (step 3).
2. **The sessions run in order, A, B, C, then D.** A missed day moves the rest
   along; three sessions in a week meet the dose. **Gate 1 now counts the 3
   core sessions** (3 of 3), not 4 of 4.
3. **The bonus rule and the drop order** (goal A's priority areas; the hip
   airplane and the psoas isometric; the gate-1 main lifts; goal B).
4. **No area is dropped**; the areas are reviewed at 12 weeks.
5. **The back and chest picks:** the single-arm dumbbell row and the machine
   chest press, both "caution" on the right (the measured limit) in
   `services/rules.py`.
6. **The prone Y raise before a press stops 1-2 reps short of failure** (a
   change to step 4 for that one position).

**Built the same day** (`goal_week.py`, `services/placement.py`): three core
sessions — Monday 59, Tuesday 64, Thursday 62 modelled minutes — meet every
required number with no rule broken; the bonus Friday (60 minutes) adds the
walking lunge, the hack squat, the back extension, the leg curl, the two side-ab
exercises and the psoas isometric. Two fixes on the way: the Y raise follows
EVERY release (his 2026-10-15 rule), which is what lifted the core from the
54-59 of the scratch draft; and the placement now spreads each area over days
(an area met on one day with a half-set credit on the same day had read as two).
**Approved 2026-10-16, second round** (*"Approved all recommendations"*):

1. **Load progression** — his double-progression proposal (*"it should be a
   range and a weight ... If the last reps of the last set are outside the range
   we increase the first set of the next week automatically"*) as the 7-point
   rule in `docs/training/load_progression_evidence_review_2026-09-16.md` §10.
   Built in `services/engine.py::range_progression` and used by the training
   page for every loaded lift with a rep range: one weight, the range and
   today's aim on screen; the weight goes up when the last set reached the top
   in every session of the lift within 7 days; back one step when the last set
   was under the range twice in a row. A session cut short (fewer sets than
   prescribed) never counts toward a step.
2. **Default ranges: 8-12 for a compound lift, 10-15 for an isolation or core
   item.** Applied to Block B's six lifts that had 10-12 or 12-15 (hip thrust,
   incline press, lat pulldown, row → 8-12; Pallof press, face pull → 10-15).
   Where one weight step is still larger than the range allows, the reps climb
   past the top first (rule 5). At his logged weights (2026-10-10 and 10-12)
   that is the face pull (17 reps at 6 units, a step of +17%) and the incline
   press (15 reps at 15 kg with 2.5 kg steps). **Corrected 2026-10-16:** a first
   count also named the Pallof press (18 reps), read at the plan's starting
   weight of 5 units; at his logged 9-10 units the step is +10-11% and the
   weight goes up at 15, the top of its range.
   **His answers, 2026-10-16:** the dumbbells go up in **2.25 kg** (*"Incline
   press goes up by the DB available which are in 2.25 increments"*) — the app
   has logged every dumbbell lift in 2.5 kg steps, so the dumbbell series is
   asked before the step changes; the cable machines' **units are fine as
   long as it is the same machine, and 1 unit is about 0.5 kg** (*"this doesnt
   matter as long as its the same machine"*). The rule reads a step as a share
   of the weight, so the unit's size in kg does not change it.
3. **The hip flexors' second day comes from the bonus** (`goal_week.MIN_DAYS`).
4. **The neck working stretch is done at home** on the three core days
   (`goal_week.HOME`). Placed again without it, the core sessions model at
   Monday 56, Tuesday 61 and Thursday 59 minutes, with no rule broken; Tuesday
   is 1 minute over the 60-minute target — **ACCEPTED 2026-10-16** (*"Accepted"*).

**The first side alternates by the day — his request, 2026-10-16** (*"We need
to switch the right and left so that some days I start with left and others
right side to balance out which arm goes first"*): `services/sessions.first_side`.
It changes every day, so each weekday starts on the other side the next week,
and in his usual week two days start on each side. The training page fixes the
side when Start is tapped and names it on the day overview. What a set record
stores does not change: its reps and weight are the right side's, and the left
side's own numbers are added only when they differ.

---

## Step 7 — the warm-up — APPROVED 2026-10-16

**Every strength day, before the first lift:**

1. The 15-minute walk to the gym — the raise; nothing to log.
2. The standing psoas march, 2 × 20 a side (his decision, 2026-10-14).
3. One light ramp set (6 reps) straight before the Romanian deadlift and the
   hack squat only (Key Rule 21).

**Before the first press** (Monday, Thursday): the right-shoulder release
(about 4 minutes), then the prone Y raise — a training exercise, counted in the
shoulder-blade sets. In the gym the warm-up takes 7 minutes on Monday and
Friday and 10 on Tuesday and Thursday, under the 15-minute limit.

**Not carried over from Block B:** the forearm plank and the side bridge at
the start — **his answer, 2026-10-16: *"Choice of planks was only to
incorporate abs workout, remove that rule choice"*** (his 2026-09-22 choice is
retired; the abs are trained to failure at the end of each session); the
incline walk; the hip airplane in the warm-up (3 × max at the end of two
sessions).

**The 90/90 hip lift — REMOVED 2026-10-16.** His question: *"What is the objective of the
90/90 hip lift and how effective is it and required for the training? or is
this more of a daily thing to do ... outside of warming up for training? does
this warm up a certain muscle that without it i could have issues?"* The facts
given to him:

- **Its job:** control of the left lower ribs (step 2), from his own
  observation of 2026-10-05 (finding #7). The heel press switches on the backs
  of the thighs, which tilt the pelvis back; the long breath out switches on
  the abs, which pull the lower ribs down. It is not the fix for the pelvis
  twist — the hip airplane trains that.
- **It warms up no muscle a lift depends on.** The walk warms in general, and
  the ramp set warms the backs of the thighs before the Romanian deadlift.
- **The evidence is weak** (searched 2026-10-16): the method comes from the
  Postural Restoration Institute; the source article describes it without a
  trial (Boyle et al. 2010); a shoulder trial is registered without a result;
  small back-pain trials report less pain, at about the level of other
  exercise (a 2025 thesis review asks for better trials); and no trial shows a
  breathing drill changes rib or pelvis position for weeks. Reviews of exercise
  for posture find the trials mostly at high risk of bias (2020, 22 trials).
- **His own record does not answer it:** five logged sessions (2026-10-06 to
  10-12), and finding #7's test has never been graded.
- **Without it** every session is about 2 minutes shorter: Monday 53, Tuesday
  59, Thursday 56, Friday 57 modelled minutes — every session under 60.

**His follow-up, and the answer recorded as given:** *"Why was it in the new
training block is what Id like to know? It doesnt warm up anything and the
evidence it fixes the issue is weak?"* There was no good reason. On 2026-10-05
he asked for posture and abs work after noticing the rib and pelvis pattern,
and the hip lift was picked then for the ribs — its own text already said no
trial shows an exercise moves a resting pelvic position. On 2026-10-14 he
questioned it, and the record agreed it is a breathing drill, not the fix for
the twist. On 2026-10-16 the new week's warm-up was copied from Block B's
without checking it against that question, and step 7 then gave it a reason
from step 2's "left lower ribs — control" instead of asking whether it works.
**Rule taken from it: a carried-over exercise is checked like a new pick —
its job, its evidence and its cost — before it enters a new block.** The left
lower ribs are now covered by the abs work, trained to failure, which trains
the muscles that pull the lower ribs down.

---

## The 12-week block — his decisions, 2026-10-16

*"When we push this new session block that will be 12 weeks long, it will
overwrite all of the current block, so just wait till we have all steps
finished. Starts once we complete all steps and push and it starts on the next
monday. lets complete all other steps and then push."*

- **12 weeks long.** A failed week still runs again (Key Rule 22), so the
  block can grow past 12 weeks; it has no fixed last date.
- **It replaces all of the current block** (Block B): nothing more is changed
  in Block B — its runs and its dumbbell step stay as they are until then.
- **Nothing is pushed until every step is done** (steps 7 and 8 and the
  checks). The block starts on the Monday after the push.
- **One progression rule for every lift** (his words: *"I dont want anything
  going over the max as the target to increase weight, the same rule applies
  to all, if I go over the range or have all sets at the range, the weight goes
  up and the range target gets reset to the middle bottom"*): the weight goes
  up when every set reached the top of the range or one set went past it; then
  the aim is the middle-bottom of the range (9 on 8-12, 11 on 10-15). Built in
  `engine.range_progression`; see the load-progression review, §10.
- **His answers of 2026-10-16 to the step-8 inputs:** the rule as built is his
  (*"Yes built correct"*); the machine steps are confirmed (*"Yes all are
  correct"*) — hack squat 5 kg (2.5 kg a side), chest press, shoulder press and
  leg curl 5 kg, cable lateral raise and crossover 1 unit, back extension
  2.5 kg (a plate held), dumbbells 2.25 kg (one real dumbbell number is still
  asked, so the + and − buttons land on his dumbbells); **starting weights:**
  the app shows a light weight, he sets the real one in the first session, and
  the rule takes over from the second (option a); **the timed plank test:** in
  week 1 and week 12, at the end of session A in place of that day's abs work,
  with the core hold score built before week 1 (option a).
- **His dumbbells, 2026-10-16:** *"22.5kg is the number I rowed with this
  morning and all Dumbells go from 2.25 - 40kg in increments of 2.25kg."* So a
  dumbbell is a multiple of 2.25 kg, and the + and − buttons move one dumbbell
  size. A lift with a dumbbell in each hand is logged as the total of both, as
  his log already is — the Romanian deadlift at 45 kg cannot be one dumbbell
  when the heaviest is 40 — so one step there is both dumbbells one size up
  (4.5 kg). Logged weights that are not real dumbbells (for example 42.5 or
  25) are read as the nearest real one when the block starts.

---

## Step 8 — the build — rules and answers, 2026-10-16

**No copying — every exercise runs through the workflow** (CLAUDE.md Key Rule
25): *"Can you ensure that there is never copying, it needs to run through the
workflow. If I ask for a exercise there needs to be reasons for to and goals
attached, and even then it can be overwritten with a better exercise to get the
same goal quicker."* Every exercise has a record in `goal_week.PICKS` (goal,
area, job, reason, source, the better-exercise check), and
`tests/test_workflow_picks.py` enforces it. **Eight picks are not yet checked
against a better exercise for the same goal** (`goal_week.BETTER_CHECK_OPEN`):
the psoas march, the shoulder release, the prone Y raise, the woodchop, the
side plank with hip raises, the hip airplane, the psoas isometric and the
adductor ladder. Step 8 checks each and shows him the result; the block cannot
be registered before.

**His answers:**

- **Ramp sets — KEPT** (*"Let's keep the ramp set it, I think it will help with
  injury prevention"*): one before the Romanian deadlift and one before the hack
  squat. Recorded with the facts given to him: no trial shows a warm-up set
  prevents injury in weight training, and at 8-12 reps it adds nothing to the
  working sets; it costs about 2-4 minutes.
- **No planned easier weeks** (*"follow the recommendation A for the no
  planned easy weeks. We can do an easy week at the end of 12 weeks if we want.
  We can decide that at a later point"*): an easier week after week 12 is
  decided then.
- **A missed session asks for its reason** (*"if there is a missed session ...
  let's ask for a question ... And then we can decide at that point what was the
  reason"*): if a week ends with fewer than 3 core sessions, one tap — hips or
  back (a flare-up; the 6-week count resets), travel or illness (the count
  pauses), other (the week does not count; the count resets).
- **Test mornings — Sunday, before the flexibility session** (*"Sunday morning
  before"*): Monday morning follows Sunday's adductor ladder and flexibility
  session, and his rule of 2026-08-07 is that a retest is never the morning
  after leg work; Sunday morning follows Saturday's rest. The 12-week
  flexibility retest runs on three Sunday mornings (three mornings before a
  number counts).
- **The rib and pelvis test** (finding #7's test from 2026-10-05, never scored):
  in week 1 and week 12, on the test Sunday morning (*"Yes"* — his answer read
  "Yes skip", taken as yes and flagged to him).

**The better-exercise checks — done 2026-10-16** with the tier decider for the
five areas without a ranked list (`docs/training/tier_lists/abs_sides.md`,
`hip_rotators.md`, `shoulder_blades.md`, `hip_flexors.md`, `adductors.md`), his
filters applied after the ranking:

| Pick | Result | Why |
|---|---|---|
| Standing psoas march | KEEP | No warm-up drill is shown better; a swing or a held stretch is out by his hypermobility rule |
| Right-shoulder release | KEEP | The chest stretches take the right arm past its measured limit; the release passes, and he uses its short-lived effect |
| High-to-low woodchop | KEEP | A, the sides' best tier; the best safety margin in it |
| Side plank with hip raises | KEEP | A, the sides' best tier; the best safety margin in it |
| Prone Y raise (B) | ASKED: the single-arm cable Y raise (A) | The S rows and pulldowns fail his right-arm limit or load pec minor; the Y raise is hardest where the muscle is shortest, and 2.25 → 4.5 kg is a 100% step |
| Hip airplane (A) | ASKED: the prone cable hip rotation (S) | Load in small steps, hips straight (no click); gives up the only exercise that turns the pelvis on a standing leg; about 5 more minutes on two days |
| End-range psoas isometric (B) | ASKED: the cable hip flexion from behind the body (S) | The isometric works the psoas at its shortest — not the area's job of strength at length; the bench-edge version is the Thomas-test position, where the right hip clicks |
| Adductor ladder | ASKED: the adductor machine (S), if his gym has one | Knees bent, starting wide under load; about 5 minutes on two sessions instead of at home; without one, the ladder stays |

**His answers, 2026-10-16:** *"1 yes 2 No - we can add weight to this by
holding it around the back but I like the balance part of this as well as the
rotation 3 yes - but is lying or standing better ? 4 yes the gym has the
machine alos a seated abductor machine if needed"*

1. **The single-arm cable Y raise** replaces the prone Y raise.
2. **The hip airplane is kept by his choice**, for the balance and the rotation,
   with a weight held behind the back in both hands (no wall) and the
   compound range, 8-12, so the one progression rule adds weight to it.
3. **The standing cable hip flexion** replaces the end-range psoas isometric.
   Standing, not lying: lying on his back is where the right hip clicked.
4. **The adductor machine** replaces the ladder; the abductor machine is not
   used (step 2: no direct work for the upper glutes).

**What the four changes cost in time — given to him after the answers.** The
adductor machine adds about 6 minutes on Monday and Thursday; the cable Y raise,
one arm at a time, about 3 (not stated when he was asked); the weighted hip
airplane at 10 reps about 2; the cable hip flexion, one leg at a time, about 2
on Tuesday. The core sessions now model at Monday 67, Tuesday 61 and Thursday
69 minutes: no rule broken, all three over the 60-minute target. Options put to
him: keep them; trim (the hip airplane's range 6-10 and 45 seconds' rest on the
adductor machine: 65, 61, 67); or the adductor ladder back at home (60, 61, 62).
