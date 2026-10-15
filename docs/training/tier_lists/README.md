# Exercise tier lists

*Started 2026-10-15 at the athlete's request: "I plan to do this with all major
exercises, so with chest, back, shoulders at some stage, but for now I'm just
going to do with abs."*

One file per muscle group. Each file records a source's FULL ranked list, in
the source's own order, with the source's tier for every exercise and a short
paraphrase of its reason. Nothing is dropped, so the list can be re-used when
the rules or the athlete's findings change.

| File | Muscle group | Source | Recorded |
|---|---|---|---|
| [abs.md](abs.md) | Abs (front wall) | Built With Science, YouTube, "It's Weird, But Destroyed Every Ab Exercise I Tested" | 2026-10-15 |
| [quads.md](quads.md) | Quads | YouTube quad tier list (video 2 of the 2026-10-15 set) | 2026-10-15 |
| [glutes.md](glutes.md) | Glutes | Jeff Nippard, YouTube glute tier list (video 3) | 2026-10-15 |
| [workout_video_notes.md](workout_video_notes.md) | Hamstrings, quads, glutes, calves, abs — recommendations WITHOUT tiers | Videos 1, 4 and 5 (workouts, not rankings) | 2026-10-15 |

## How a tier list is used

A tier list is an INPUT to step 5 of the slot procedure (exercise choice,
`docs/training/goal_system.md`). It never overrides the step-5 filters:

1. The safety rules (`services/rules.py`) must know the exercise and not block
   it at the current stage. "Unknown" is not a clearance.
2. No observed finding or decision of the athlete blocks it. (The 2026-10-05
   "no leg raises" exclusion was a session's choice, not his decision —
   corrected 2026-10-15; his call on it is pending.)
3. The equipment rule and the gym's equipment allow it.
4. It can reach the effort step 4 sets for it.
5. The app can log and progress it.

**The athlete's tier rule — APPROVED 2026-10-15:** train only from the **S and
A** tiers of a list. Ranking among those that pass the filters: **tier first,
then safety margin** (*"Tier then safety as safety will change with time"*),
then directness, known tolerance and time. Caution in the safety rules means
allowed. Areas without a list keep the step-5 ranking (safety margin first).

A tier is the SOURCE's judgement, not a trial result. Each file says what the
source measured and what it did not.
