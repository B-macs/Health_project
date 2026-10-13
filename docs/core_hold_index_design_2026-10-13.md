# Core score from timed holds — design for the athlete's OK (WP-15 step 6)

The athlete's direction (2026-10-13): score core from the Bunkie holds against
the 2025 log. This is the design. **Nothing is built yet**; four choices below
need the athlete's answer first.

## The answer

1. **Score core as hold time, not as estimated strength.** Each test hold runs
   until the form breaks. A line's index is the seconds now ÷ the 2025
   seconds × 100, and the worse side counts (the battery's rule: the worse side
   decides, never an average). Core's index is the mean of its lines.
2. **Two lines have a 2025 reference:** the Bunkie lateral line against the
   2025 side plank with march (15 s each side × 3), and the Bunkie medial line
   (a Copenhagen-type hold) against the 2025 Copenhagen plank (30 s × 3).
3. **Show core's number on its card from the first test, marked provisional,
   and keep it out of the headline.** Under the present confidence rule core
   could not leave calibration for about a year (see "Why core cannot meet the
   0.70 rule").
4. **Capture the seconds as numbers.** Today a timed hold always logs its
   prescribed time. The log holds no Bunkie test at all: the baseline set for
   2026-09-20 was never logged. So the first measurement is Block B day 28
   (2026-11-08), unless the athlete has the 20 Sep times elsewhere.

## What the number means

- Hold time in a position, held to form failure. It is endurance at a
  position, not maximal strength: twice the time is not twice the strength.
  The card says "hold time" for core, so it is not read as the 1RM-based
  index of the upper and lower body.
- 100 = the 2025 level, as for the other regions.
- The 2025 figures are training doses (3 sets of 15 s and of 30 s), not holds
  to failure. They are LOWER bounds on the 2025 best, so today's index reads
  HIGH against them. Comparability 0.6 is proposed: between
  `strength_baselines.py`'s 0.70 (same pattern, different implement) and 0.40
  (a figure that had to be assumed).
- The 2025 forms differ from the Bunkie forms (a floor side plank with a march
  against side support with the feet on a bench and the top leg lifted). That
  is the second reason for 0.6.

## Why core cannot meet the 0.70 rule

Confidence = quantity × comparability × consistency, and a region leaves
calibration at 0.70 (`strength.CALIBRATION_EXIT`).

- Comparability 0.6 caps core's confidence at 0.6, below the exit, for ever.
- Quantity needs 12 observations (`CONFIDENCE_N_TARGET`). Two lines tested
  once a block give 2 a block: six blocks, about six months, even at full
  comparability.

So under the present rule core would show the 50 placeholder for ever, which
is the problem the athlete asked about. The recommendation: core shows its
measured hold-time index on its card from the first test, marked
"provisional · hold time", and it stays OUT of the headline: the weekly model
reads the lifts only, and core's share of the headline stays on its stated
prior. The headline then moves only on what it can measure, and the card
shows what core did.

## The capture

- The day-28 test gets a "seconds held" number input for each side of each
  Bunkie line, filled in after the hold. It starts empty: the 40 s on the
  screen is a reference, not a target.
- Storage, two ways:
  - **A `tut_left` field** beside the existing `reps_left`/`weight_left`:
    `tut` holds the right side and `tut_left` the left. One Supabase column,
    which the athlete pastes into the SQL editor (PostgREST has no route to
    add a column): `ALTER TABLE training_sets ADD COLUMN IF NOT EXISTS
    tut_left DOUBLE PRECISION;` Recommended: one set record still covers both
    sides, as for every other exercise.
  - **Two set records per line** (right, then left): no SQL, but each line
    then counts as two sets wherever sets are counted.

## The choices

1. **Display**: core's hold-time index on its card from the first test,
   provisional, out of the headline (recommended); or keep "—" until the
   confidence rule is met (about a year at best, never at comparability 0.6).
2. **Lines**: the lateral and medial lines, which match the 2025 log
   (recommended); or add the anterior line (a front plank), which has no 2025
   figure and would need its first test as its 100.
3. **Storage**: a `tut_left` column (recommended), or two set records per
   line.
4. **The 20 Sep baseline**: if the lines were timed outside the app, the
   times become the first point; if not, the first point is 2026-11-08.

## What the build then touches

`strength_baselines.py` (a hold section for the two 2025 figures),
`services/strength.py` (a hold-time index for core, and its display rule),
`services/sessions.py` and `views/training.py` (the seconds input on test
holds, and storing it), `services/repository.py` and the two schema files
(`tut_left`), the Strength card's text, and tests for each. Rebuild rule 1
holds: the scoring rule lives in `services/`.
