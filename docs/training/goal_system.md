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
- PROPOSED (2026-10-14, not yet confirmed): each blocker has its own proof, so
  that it is known when to move to the next one.

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
4. **Test day before the first run** — RECOMMENDED, NOT YET CONFIRMED: a
   30-minute brisk walk, then single-leg calf raises and hops, all without pain.
   It replaces *"or we're in a position where we believe that we can start"*,
   which cannot be a gate.

**Gate 2 (stage 2 → 3)** — APPROVED: the same rules over 6 weeks of stage 2,
with the run counted as a session.

**Going back** — APPROVED: a flare-up in stage 2 or 3 sends him back one stage.

---

## Goal B — 20 kg overhead press — DRAFT (athlete, 2026-10-14)

**Proof:** a 20 kg overhead press. OPEN: dumbbells (20 kg in each hand) or a
barbell; seated or standing; how many reps. His 2025 best was 15 kg × 9 in each
hand with dumbbells, on 2025-06-28 (source: `Input_files/2025-training-year.md`).

**Blockers, biggest first** (athlete, 2026-10-14):

| # | Blocker | Proof that it is done |
|---|---|---|
| 1 | The right shoulder sits tilted inward | OPEN — no test exists |
| 2 | Strength of the press muscles and the small muscles around the shoulder, over a long period | OPEN |

OPEN: how blocker 1 is measured; whether the small shoulder-blade muscles start
in blocker 1; where the left side goes (it overcompensates, and it strained
under the overhead press in 2025); and the priority of goal B against goal A
when they compete for time.

## Goal C — flexibility that lasts — OPEN

A separate goal: to be more flexible, and to keep it. One session a week in
every stage. Proof and blockers are not yet defined.
