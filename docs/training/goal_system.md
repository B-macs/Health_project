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
| Front of the right shoulder (pec minor, scar) | Range — release plus active work | Physiotherapist 2026-08-10; `docs/training/release_protocols_2026-08-10.md` |
| Middle back | Range — to be tested | His reading 2026-10-14 |
| Shoulder-blade muscles, both sides | Strength and size | Physiotherapist 2026-08-10: the right is weaker, the left works too much |
| Rotator cuff | Strength and size | Finding #6: the right shoulder is held by muscle, not ligament |
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

## Step 3 — the weekly dose — APPROVED 2026-10-14, one row open

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
| Strength and size, priority 2 — the main lifts (quads, chest, back) and goal B (shoulder-blade muscles, rotator cuff, press muscles) | 2 or more | 6 per area | 0-3 reps left |
| Hip airplane (his dose) | 2 | 3 × max each day | to failure |
| Strength at length — hip flexors, adductors | 2 or more | 6 per area | hard; stop before the position slips |
| Control — left lower ribs | every strength day | 1-2 short sets | easy, never to failure |
| Range — front of the right shoulder | OPEN (see below) | about 8 minutes | the physiotherapist's protocol |
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

**Open — the front of the right shoulder.** The two exercises exist
(`PEC_SCAR_RELEASE`, `ANTERIOR_SHOULDER_RECIPROCATION`, in the accessory
session), but neither has ever been logged, and the release half is dosed by
"tender spots" — points that are sore under a ball — which the record has never
observed.
