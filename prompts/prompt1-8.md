# Prompt - Fixes

## P1 — Remove the trial forward fold and clear dependent blocks

Remove the **trial forward fold** from the programme. I have never experienced clicks or cracks while performing it, so the associated warning and check are not relevant. Treat this screen as passed and identify anything else currently blocked by it so those dependencies can be cleared. Do not add a replacement exercise unless a separate assessment shows one 

---

---

---

---

## P2 — Assess left-shoulder alignment and upper-chest burning

Review the observation that my right shoulder appears relatively straight while my left shoulder has an inward inflection. Propose a cautious assessment and corrective plan for the left side.

Include this symptom in the assessment: crossing my arms and pulling an elbow down, away from the shoulder but close to the body, creates a burning sensation in the right upper chest leading toward the shoulder.

Deliverables: observation checklist, relevant range-of-motion and control comparisons, likely movement-pattern hypotheses without diagnosis, safe corrective options, stop criteria, and guidance on when professional assessment is warranted. Do not prescribe an exercise that reproduces the burning sensation..

### Facts and context (2026-08-24)

1. **The burning is on the RIGHT** (athlete's own correction to this prompt). The shoulder that LOOKS wrong is the LEFT. **These are two separate findings and must not be written as one.**
2. **The right is the surgical side** — three anterior dislocations, a failed capsular wrap, and a Latarjet on a shallow glenoid.
3. **The right-sided burning is already in the record**, described as burning in the upper chest toward the shoulder with the muscle locking out, in a different position. So this is most likely a KNOWN finding appearing in a second position, not a new one.
4. **It is probably verdict data, not a new topic.** The right pec/scar release protocol started 2026-08-10 as a pre-registered trial with its verdict due at about two weeks — i.e. now — and no verdict is recorded. A fresh right anterior-chest report landing at the two-week mark reads on that trial.
5. **The left appearance is the separate question**, and the record runs the other way: it notes a visible sag of the RIGHT shoulder relative to the left. There is also a left clavicle dislocation at age 14 with residual elevation — settled anatomy, not something to correct.
6. **No referral.** The prompt asks for "when professional assessment is warranted", which runs against the standing decision of 2026-08-17. Write stop criteria that end in an action he can take himself.
7. **Never a held corrected posture.** Chasing how a shoulder LOOKS is the exact route that produced the 2026-07-06 left iliocostalis/QL strain. And on the left shoulder girdle specifically, sustained low-level contraction is the provocative mechanism — short efforts, not long holds.

### Still open

- What "inward inflection" describes physically: a visible step in the collarbone line, the shoulder rolled forward, or the shoulder sitting lower. It selects between settled anatomy and a trainable pattern.
- Whether the appearance is new, or long-standing and only recently noticed.
- Where the deliverable should land: chat, a `docs/training/` protocol, a `symptom_log` entry, or a new finding. Note a new finding with an unrun test FAILS the deterministic gate.

---

---

---

---

---

## P3 — Fix Garmin activity-to-session linking

Session Garmin timers are not linking to the correct training sessions. The time difference is not aligning, it thinks I’m an hour a head I believe but I’m not sure, 

### Diagnosis (measured, 2026-08-24)

Per-set timestamps carry a UTC offset; Garmin returns the activity start as a naive local string. `hr_matching._comparable` cannot order an aware datetime against a naive one, so it drops to WALL CLOCK — correct only while the stored timestamp is rendered in the zone the athlete is standing in.

Offsets actually stored, from `training_sets`:

| Session | Offset | Result |
|---|---|---|
| ≤ 2026-08-06 | none (naive) | the earlier bug, since fixed |
| 2026-08-10 | `+02:00` | matched cleanly, every exercise covered |
| 2026-08-16 onward | `+00:00` | broken |

`HEALTH_TIMEZONE` is unset and `config.timezone` defaults to `""`, which falls back to the host's own zone — UTC on the server. **This is a deployment regression, not travel.** It is two hours wrong at his CEST base and one hour wrong in Ireland, which is the hour he reported.

**The failure is a confident wrong match, not a missing one.** On 2026-08-21 the 15-minute `MATCH_TOLERANCE_SECONDS` padding let a window an hour late still overlap: 860 s of a 930 s activity, quality 0.93 against a 0.5 threshold. Correct alignment scores 1.00. The visible symptom is that the run itself came back with null HR while the release work took heart rate from the wrong fourteen minutes.

### Decisions (athlete, 2026-08-24)

1. **Fix the matching in code, not by configuration.** Setting `HEALTH_TIMEZONE` is wrong again the moment he travels: pointed at his base it renders sets in CEST while the watch stamps Irish local, still an hour out. `hr_matching._comparable`'s own docstring names that case.
2. **Leave 2026-08-21 alone.** Its HR-derived per-exercise RPE values stay as they are. No backfill — which also avoids the three incompatible regimes across the four recent sessions (08-16 carries 5.0 on every exercise from the old slider spill, 08-18 and 08-20 are null, 08-21 is populated but wrong).

### Fix (implemented)

`hr_matching.device_start_iso(start_local, start_gmt)` derives the WATCH's own UTC offset from the difference between Garmin's two clocks and stamps it onto the local time, so `_garmin_activity_row` emits an offset-aware `start_time_local`. `_comparable` then takes its all-aware branch and both sides are compared as instants — no host configuration, immune to travel and DST.

Degrades to the bare local string whenever the offset cannot be established (GMT missing, either side unparseable, or a difference too large to be a real zone), so every already-stored row behaves exactly as before. `tests/test_activity_clock_offset.py` pins both directions, including the real 08-21 numbers.

### One thing left to confirm

**That `startTimeGMT` is actually present on the activity payload for this account.** Every archived Garmin payload here pairs a GMT timestamp with a local one, but those are wellness endpoints — no activity payload has ever been archived, and `garmin_activities` is empty in the local cache. If the field is absent or named differently the fix degrades silently to today's behaviour, so it needs one live call to verify.

---

## P4 — Reconcile inconsistent sleep durations

The sleep summary shows **7 h 19 min** at the top but **6 h 46 min** in the details. Identify whether the discrepancy comes from different definitions, source records, rounding, awake-time handling, timezone handling, or stale data.

If there is no data for that day there should be no data for that day presented. Until the correct data is there 

Use one clearly labelled source of truth. If both values are valid, label each definition explicitly and explain the difference instead of presenting them as the same metric.

Deliverables: root cause, calculation and labelling rules, stale-data handling, reconciliation tests, and corrected user-facing. 

---

---



---

---

## P6 — Add recurring voice training to the front page

Add a recurring, visible to-do on the front page for completing my voice training. Define the task label, recurrence, completion behaviour, and placement. Preserve completion history and avoid duplicate tasks. If recurrence cannot be inferred from existing voice-training content, leave it configurable rather than inventing a schedule.

## P7 — Bands

I have two sets of bands one that are small and can go around my knees, it’s about that size, good for the lateral band walk, they work on the current colour band colour system, but I also have a bigger bands that go from 10lbs up to 50lbs but I can also put them together, you can check the messages in my last week of training. You can see the front squat was done with these bands which are a different set of bands, thus the weight rep system must be changed from the colour band system to 10 lbs increments 


### Facts (athlete, 2026-08-24)

1. **Two separate band sets, and they are not one ladder.**
   - **Small loop bands** — knee-sized, go around the legs. These stay on the existing COLOUR system.
   - **Large bands** — rated **10 lb to 50 lb in 10 lb increments**, and they can be **combined**, reaching **up to 150 lb**. These move to a numeric pounds axis.
2. **Band Front Squat, 2026-08-20, was 40 lb / 40 lb / 50 lb.** The logged colour tiers for that session (Yellow / Yellow / Black) are not recoverable to pounds and should not be trusted.
3. **Rewrite the Band Front Squat in the notes for that session. Leave the rest of the history alone.**

### Which band set an exercise uses — the rule (validated with the athlete, 2026-08-24, 12/12 correct)

The deciding question is **what the band is doing**, not the muscle or the body part.

- **Pounds bands (10–150 lb).** The band IS the load. It stands in for a weight that would otherwise be on the bar, the dumbbell or the cable stack, through a full-range pattern. The number is the training load and it progresses. Usually anchored to something external — door, foot, rig — but not always (a pull-apart is held in both hands and is still the pounds set).
- **Colour loops (small, knee-sized).** Closed around the legs, short range, making the glute medius and external rotators switch on. The point is that the muscle fires, not what it carries. There is nothing meaningful to progress, so no pounds figure belongs on it.
- **Third role: a big band used as a JOINT DISTRACTION** (e.g. anchored low and looped round the thigh to pull the femur in the socket). Physically a pounds band, but it is not resistance — nothing progresses and a stiffer band is only more distraction force. **It must not carry a weight field or a progression.**

The clearest illustration is one movement with both: a **loop above the knees during a bodyweight squat** resists the knees collapsing in (colour, a cue), while a **Band Front Squat** loads the pattern (pounds, a load).

**Consequence for the live block: every one of the nine band exercises in Stage 2B is a POUNDS band** — Front Squat, Hip Thrust, Romanian Deadlift, Pallof Press, Chest Press, Face Pull, Lat Pulldown, Single-Arm Row. Face Pull sits at the lightest (10 lb). The colour system has no exercise in Stage 2B at all; its only user, Lateral Band Walk, was a Stage 2A item.

### CONFIRMED (athlete, 2026-08-24): band pounds are NOT tonnage

Confirmed — band pounds do NOT count as tonnage. Treat them the way the repo already treats machine units: a real, steppable number that drives progression and reads as plain weight on screen, but **never converted to kilograms and never entering tonnage**. This keeps "a band is not a kilogram" intact in all four places it is written and does not collide with the two tests that enforce it. The alternative — counting band pounds as real tonnage — would rewrite the travel fortnight from 0 kg to the block's highest tonnage.

### Still open

- Band force rises with elongation, so a rated poundage is not the force at working length — his own note reads *"the bands are médium sized so it's already in the stretch position"*. Fine as a progression axis; the reason it stays out of kilograms.
- **Lateral Band Walk — the exercise named for the small bands — is not in Stage 2B at all.** It ran in Stage 2A on days 5, 12, 19 and 26. The colour system currently has nothing to do in the live block.

## P8 — Home incline-walking constraint

Can’t do incline walking when at home

### Facts (athlete, 2026-08-24)

1. **"At home" meant where he is staying in Ireland, not his usual base.** The originating session note was logged 2026-08-21 in Ireland.
2. **The constraint applies ONLY while travelling in Ireland.** It is not a permanent change to the block, and no gym-versus-home concept is needed anywhere in the app.
3. **What he has there: STAIRS and a BOX.**

### Already done (committed 2026-08-24, before this prompt was read)

`PREP_RAISE` was cut from four minutes to three, and its instruction already reads *"treadmill at a real gradient, a hill outdoors, or a flight of stairs walked up and down if there is no treadmill"*. The session note that produced this prompt had already been actioned.

### What is left

**Name the box.** Add step-ups onto a box to the same `mechanics` text as a third option.

Do it as instruction text on the EXISTING exercise, NOT as a new exercise name. `Walking Raise (Incline)` carries movement weight **0.25**; the repo's existing step-up names (`Forward Step-Up (Stair)`, `Lateral Step-Up (Single Stair)`) carry **0.5**. Authoring a new step-up raise, or swapping one of those in, would **double the movement weight of a three-minute item on eighteen days**, flowing into Foster AU, strain and the stage-scoped ACWR window — a metric shift caused by a warm-up modality change rather than by training, with every test still green. Keeping it inside the existing instruction costs nothing and changes no accounting.

Constraints that still bind: phase 2 stays mandatory, cycling stays excluded (test-enforced), preparation stays inside the 10–15 minute ceiling, and `mechanics` must read as instructions only.

## P9 — Ireland training-plan update

staying here in Ireland until Thursday so I need to update to change the plan to Thursday 3rd Sept to only band and body weight training

### Facts (athlete, 2026-08-24)

1. **In Ireland until Thursday 3 September.** Plan days 15–18 (Mon 31 Aug – Thu 3 Sep).
2. **In Ireland the only equipment available is BANDS.** No dumbbells, no plates, no cable, no machine — bands and bodyweight only.
3. **No gym access until 4 September.**
4. **Travelling through Berlin 4–6 September — no training.** Plan days 19–21 (Fri 4 – Sun 6 Sep).
   - **The release work STAYS on those days.** He would rather have it there and get it done if he can than not have it at all. Only the loaded/gym and running content comes out.
5. **First day back in the gym is Monday 7 September** — plan day 22.
6. **Run 5 (day 20, Sat 5 Sep) is dropped**, not rescheduled.
7. **The block still ends Sunday 13 September** (day 28, the reassessment). It is Block B's job to establish whether the 10 km on 11 October is realistic; that question is not settled here.

### What follows from the facts

- Only day 15 currently needs a gym in the Ireland window; days 16–18 (run, mobility, Cluster A flexibility) already need none. Day 15 is the deliberately stepped-down lower-body re-entry (Goblet 17.5 / RDL 40 / Hip Thrust 40) and becomes band work.
- Day 19's gym content and day 20's run come out; the releases on both days stay.
- **Day 22 (Mon 7 Sep) is now the first loaded session after three weeks of bands and three days of nothing**, and as authored it is the block's heaviest day — ramp sets plus a 25 kg Goblet top set and a 52.5 kg RDL top set.
- Week 3 ends with no gym session at all; week 4 carries the only two remaining (days 22 and 26).

### Open decision

Day 22's load. Recommendation: **day 22 runs the stepped-down day-15 content** (Goblet 17.5, RDL 40, Thrust 40) and the heavy top sets do not run this block. Cost: those top sets were what produced the final working loads Block B is built on — but a top set on a body three weeks unloaded produces a number that is not honest anyway. The 2025 log names weight increased too quickly as what broke the squat, and the step-down was authored for a two-week gap; this gap is longer.