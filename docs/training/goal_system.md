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

## Goal B — 20 kg overhead press — APPROVED 2026-10-14, except the floor test's pass and stall rules

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

**The floor test runs WITH THE 12-WEEK FLEXIBILITY TEST** (athlete,
2026-10-14: *"we can add it to the flexibility test that's every 12 weeks"*),
on each of its three mornings, together with the pelvis test (finding #7, the
same lying position). Protocol: lie on the back on a hard floor, knees bent,
feet flat, arms by the sides, palms down; breathe out fully and relax for three
breaths; check by feel whether the back of each shoulder touches the floor; for
a number, a timed phone photo from the side, the phone on the floor about 1 m
away, with a ruler leaned upright against a book beside the right shoulder — the
gap in cm. PROPOSED to fit the 12-week rhythm, not yet confirmed: **pass** when
both shoulders touch on all three mornings of one retest; **stall** when the
right gap is not smaller than at the retest before — then the cause is reviewed
before more of the same work.

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
