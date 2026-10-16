# Exercise tier lists

*Started 2026-10-15 at the athlete's request: "I plan to do this with all major
exercises, so with chest, back, shoulders at some stage, but for now I'm just
going to do with abs."*

## One file per body area — and nothing outside them

Each area has ONE file with two parts:

1. **The ranked list** — a source's FULL list in its own order, with the
   source's tier and a short paraphrase of its reason, or the line "No ranked
   list yet".
2. **Unranked source advice** — what videos that rank nothing recommend for
   that area.

There are no separate notes files (athlete, 2026-10-15: *"I dont want to have
seperate md files that are just ignored when creating the plan"*). The
leg-workout notes of 2026-10-15 were merged into the area files the same day.
`tests/test_tier_lists_indexed.py` fails if a file in this folder is missing
from the index below, if the index names a file that does not exist, or if a
file lacks either part.

| File | Area | Ranked source | Recorded |
|---|---|---|---|
| [abs.md](abs.md) | Abs (front wall; the sides are his own picks) | Built With Science, "It's Weird, But Destroyed Every Ab Exercise I Tested" | 2026-10-15 |
| [quads.md](quads.md) | Quads | YouTube quad tier list (no URL given) | 2026-10-15 |
| [glutes.md](glutes.md) | Glutes | Jeff Nippard, glute tier list; and the glute rows of the hams-and-glutes list | 2026-10-15 |
| [hamstrings.md](hamstrings.md) | Hamstrings (the list also ranks glute and lower-back exercises) | A "hams and glutes" tier-list video (channel not named) | 2026-10-15 |
| [deep_back.md](deep_back.md) | Deep back muscles | No ranked list yet — the back-extension rows of two other lists | 2026-10-15 |
| [calves.md](calves.md) | Calves (an area from stage 2) | No ranked list yet | 2026-10-15 |
| [shoulders.md](shoulders.md) | Deltoids — front, side and rear | Jeff Nippard, shoulder tier list | 2026-10-15 |
| [back.md](back.md) | Back — lats and upper back | No source yet — the tier decider's list | 2026-10-16 |
| [chest.md](chest.md) | Chest | No source yet — the tier decider's list | 2026-10-16 |

## The reading rule — when these files are used

**Step 5 of the slot procedure (`docs/training/goal_system.md`) reads the file
of EVERY area every time a plan is built:**

1. The step-5 filters run first: the safety rules know the exercise and do not
   block it ("caution" is allowed, "unknown" needs a rule first); no finding or
   decision of the athlete blocks it; the equipment rule and his gym allow it;
   it can reach step 4's effort; the app can log and progress it.
2. **An area with a ranked list:** only S and A tiers; ranked tier first, then
   safety margin, then directness, known tolerance and time (approved
   2026-10-15: *"Tier then safety as safety will change with time"*).
3. **An area with no ranked list** (or no S/A exercise that passes): the
   candidates come from its unranked advice, ranked by safety margin first.
4. **Every pick records its file and its part** — the tier it came from, or
   "unranked advice".

At the build (step 8) the lists become data, and a check fails if a pick has
no source in its area's file.

**A list that ranks more than one area** is recorded IN FULL in the file of the
area it ranks most, and its rows for each other area are copied into that
area's file with the full list's numbers (the hams-and-glutes list, 2026-10-15).

**Two ranked lists for one area — APPROVED 2026-10-16** (the glutes): an
exercise qualifies if ANY list puts it in S or A; it ranks by its best tier; a
tier given without a named version counts for each version his rules allow; and
when a checked trial compared two exercises directly, the trial's winner ranks
first.

A tier is the SOURCE's judgement, not a trial result. Each file says what the
source measured and what it did not.

## The tier decider — for an area no source has ranked

`services/tier_decider.py` rates an exercise on five things every recorded list
ranks on (stretch, target, stability, load, comfort — the ratings and the rule
for each are in `exercise_features.py`) and turns the score into a tier with
cut points calibrated on the recorded lists. Approved 2026-10-16: *"use the same
script to create a tier list for back and chest ... go for that for now"*.

- **A decider list is used like a source list until a video for its area
  arrives**; then the source list replaces it.
- **How close it gets** (2026-10-16): on a list it was not calibrated on, the
  exact tier 41% of the time and within one tier 96% (guessing "A" for
  everything: 32% and 74%). `python scripts/tier_decider.py validate` re-runs it.
- **When a video arrives:** record its full list as usual, then
  `python scripts/tier_decider.py compare <file>` gives the decider's agreement
  with it.
- `tests/test_tier_decider.py` fails if a source row loses its rating, if the
  cut points stop being the calibration's answer, if the agreement drops, or if
  a decider list in this folder stops matching the decider.
