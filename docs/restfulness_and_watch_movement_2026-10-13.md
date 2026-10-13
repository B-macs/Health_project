# Restfulness and watch movement — measured 2026-10-13 (WP-19)

The athlete's question: *"Restfulness — can we take into account Garmin
movements through the night?"* This document answers it, and records a
larger fault the measurement found. **The score was changed after the athlete's decision (option A).**
The decision was the athlete's (WP-19 step 3): option A, see below.

Every number below comes from `scripts/compare_restfulness_sources.py`, run
read-only on the 2026-10-09 backup. Re-run it before you change anything.

> **Decided 2026-10-13: option A.** The athlete chose Oura's own Restfulness
> part. It is built as Sleep Score `MODEL_VERSION` 2: on the same 95 nights the
> new score reads exactly option A's figures below (+5.4 on average, 9.3 above
> Oura's total). The stored history is re-computed once, after the Supabase
> switch, in the same run as the other stored-row corrections.

## The answer

1. **Do not add the watch's movement to Restfulness.** The watch's movement
   agrees only weakly with the ring's, and nothing can show which of the two
   is right.
2. **Restfulness itself is broken, and that is the larger fault.** Its scale
   gives 100 at 2 restless periods per hour and 0 at 12. The real input is
   29 to 59 per hour on the 265 nights, and 1 of 427 ring nights since 2023
   is below 12. So Restfulness has read 0 on 426 of 427 nights. It carries
   no information, and it takes a fixed 10 % of the weight from every score.
3. **The zero hides two generous parts.** In 2026, against Oura's own parts,
   our Total Sleep reads 22.7 points higher and our Deep 17.8 higher. These
   add about 8 points to the total; the Restfulness zero takes about 5 away.
4. **The decision for the athlete**: what Restfulness reads (options A–D
   below). The recommendation is A: use Oura's own Restfulness part.

## Why the watch does not help

Measured on the 53 nights since 2026-08-06 that both devices recorded, with
the watch's movement mapped through the one-watch cut points (WP-19 step 1).
Each number is a rank correlation with Oura's restless periods per hour —
the input the score uses — with its 95 % interval over nights.

| Measure, inside sleep minutes only | Rank correlation |
|---|---|
| The same count on the ring's own movement (the yardstick) | 0.87 |
| Watch: runs of movement per hour | 0.35 [0.09, 0.56] |
| Watch: share of minutes with movement | 0.46 [0.19, 0.68] |
| Watch: large movements per hour | 0.29 [0.02, 0.53] |
| Fused series: runs of movement per hour | 0.89 [0.78, 0.94] |
| Ring against watch, the same count on both | 0.32 [0.04, 0.55] |
| Ring against watch, large movements only | −0.07 |

- The count works on the ring's own series (0.87). So the low numbers for the
  watch are about the watch, not about the count.
- The watch sees few small movements: a median of 1.4 runs per hour against
  12.3 on the ring. A wrist does not feel what a finger feels. This is what
  `services/sleep_movement.py` predicts for low amplitude.
- On large movements, where the watch should be the better witness, the two
  devices do not agree at all (−0.07). There is no third reference (a sleep
  laboratory) to say which one is right.
- The fused series agrees well (0.89) only because it is mostly the ring's
  series: at low amplitude it weights the ring 75 %.
- A night only the watch recorded has no Sleep Score (WP-11). So a watch
  number could only replace a ring number on a night that already has one.

## Why Restfulness reads 0

Oura does not publish what one "restless period" is. The score's band
(`sleep_score._RESTLESS_BAND`, 2 to 12 per hour) was a first guess, and its
docstring said so: confirm it against real nights before you trust it.

| Measure | Value |
|---|---|
| Ring nights with the input, 2023-07 to 2026-10 | 427 |
| Restless periods per hour of sleep | median 46.7, range 3.6–120 |
| Nights under 12 per hour | 1 |
| Nights Restfulness scored above 0 | 1 |
| Oura's own Restfulness part, same nights | median 54, range 17–98 |
| Rank correlation, the count against Oura's own part | −0.54 |

The count carries only part of what Oura's own Restfulness reads (−0.54).
Oura uses more than this one count.

## Our parts against Oura's (95 nights, 2026)

| Part | Weight | Ours minus Oura's | Points on the total |
|---|---|---|---|
| Total Sleep | 25 % | +22.7 | +5.7 |
| Efficiency | 20 % | +8.8 | +1.8 |
| REM | 15 % | +2.8 | +0.4 |
| Deep | 15 % | +17.8 | +2.7 |
| Restfulness | 10 % | −54.1 | −5.4 |
| Latency | 10 % | −2.2 | −0.2 |
| Timing | 5 % | −6.2 | −0.3 |
| **Total score** | | **+3.9 (sd 6.4)** | |

Our Total Sleep is scored against the athlete's own usual length and stops at
100, so a night of that usual length reads 100. Oura's own Total Sleep part reads 22.7
points lower on the same nights. That is the largest single difference, and
it is a design choice of this project (`sleep_score.py`, Total Sleep), not a
fault. It is recorded here because a Restfulness fix alone moves the total
up, away from Oura's.

## The options

Each option is measured over the same 95 nights through the score's own
composite. "Gap" is our total minus Oura's total.

| Option | Mean change of the score | Gap (sd) |
|---|---|---|
| **A. Use Oura's own Restfulness part (0–100)** — recommended | +5.4 | +9.3 (6.3) |
| B. Keep the count, re-base the band on the athlete's own nights (100 at 36.2 per hour, 0 at 56.0) | +5.7 | +9.5 (7.2) |
| C. No change | 0 | +3.9 (6.4) |
| D. Remove the part, share its weight among the other six | +8.0 | +11.9 (6.8) |

**Why A.** It is the only reading of restfulness whose scale fits the input,
because Oura made both. It moves night to night (17–98). It needs no new
guess. Readiness already works this way: since `MODEL_VERSION 2` it scores
from Oura's contributors with this project's own weights.

**Why not B.** The band is a new guess, and the count carries only part of
what Oura reads (−0.54).

**Why not C.** A part that reads 0 on every night tells nothing. A restless
night and a calm night score the same on it.

**Why not D.** It moves the score most, and it removes the only part about
how still the night was.

## What a change moves

- **No training decision reads the Sleep Score.** The engine, the load
  verdict, readiness and the scheduling do not read it. A change moves the
  Home Sleep card, the Sleep breakdown and the stored `sleep_score` column of
  Metrics History only.
- **Every option except C moves the stored history**, so it needs a version
  stamp on the score and a re-derive of the stored rows, in one step, so that
  the trend stays comparable.
- If the athlete also wants Total Sleep looked at, do both in the same
  version, so that the history moves once.

## The calibration fix (WP-19 step 1, done)

The movement cut points are now fitted on the 265's nights only (from
2026-08-06; `sleep_movement.CALIBRATION_WATCH_FIRST_NIGHT`).

| Fit | Cut points |
|---|---|
| Both watches pooled (before) | 1.45, 2.52, 4.73 |
| The 265 only (now) | 1.44, 2.55, 4.63 |

0.7 % of the watch's slots inside the ring's sleep period change class. Each stored night keeps
the cut points it was made with (`movement_cutpoints`), and the routine
fusion sync re-makes the last 14 nights with the new fit. A full re-derive
of older nights is not necessary for a change this small.
