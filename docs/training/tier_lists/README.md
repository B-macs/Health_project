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
| [glutes.md](glutes.md) | Glutes | Jeff Nippard, glute tier list | 2026-10-15 |
| [hamstrings.md](hamstrings.md) | Hamstrings | No ranked list yet | 2026-10-15 |
| [calves.md](calves.md) | Calves (an area from stage 2) | No ranked list yet | 2026-10-15 |
| [shoulders.md](shoulders.md) | Deltoids — front, side and rear | Jeff Nippard, shoulder tier list | 2026-10-15 |

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

A tier is the SOURCE's judgement, not a trial result. Each file says what the
source measured and what it did not.
