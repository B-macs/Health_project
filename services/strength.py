"""
services/strength.py — the Overall Strength Score and its regional split.

Pure functions only. No I/O, no Streamlit, no hidden clock reads — every
date-dependent function takes an explicit `today`, same convention as
services/engine.py.

WHAT THIS REPLACES, AND WHY
---------------------------
The Stage-Adjusted Recovery Score this replaces (deleted from
services/bioage.py on 2026-08-04) was
`min(100, current_28d / (best_ever_28d * volume_cap) * 100)`, where
`best_ever_28d` is maximised over every trailing window INCLUDING today's. The
current window is therefore inside the set its own denominator maximises over,
so the ratio can never exceed 1 and the score reads a flat 100 for the whole
first 28 days of any block and at every new peak. Measured on 2026-08-04 it had
returned exactly one distinct value — 100.0 — on all 16 days it had existed.
That is the same one-sided saturating ratio readiness MODEL_VERSION 2 removed.

It also measured the wrong thing: tonnage-in-a-window is training volume, and
volume is not strength. A deload lowers it; a heavier month raises numerator and
denominator together and changes nothing.

THE IDENTITY EVERYTHING RESTS ON
--------------------------------
    overall        = sum over r of (share[r] * index[r])      (sum of share = 1)
    contribution[r] = share[r] * index[r]   -> sums to overall by construction
    percent[r]      = contribution[r] / overall

With every regional index starting at CALIBRATION_INDEX (50), the overall is 50
*whatever the shares turn out to be*. That is why calibration can run for months
without the headline moving, and why nothing jumps the day it completes.

⚠ SINCE 2026-10-20 THE HEADLINE IS THE MEASURED INDEX (the owner's choice A:
"your lifts as a % of 2025, measured"). It is the middle (median) of the
weekly measured index over the last HEADLINE_WEEKS weeks that have a lift,
looking back at most HEADLINE_LOOKBACK_WEEKS; the chart draws the same line,
so the headline is the chart's last point. Each region still leaves
calibration on its own confidence, and the regions divide the headline by
their shares — see snapshot() and screen().

WHAT IT REPLACED, AND WHY. From 2026-08-04 the headline was a weekly model
seeded at an assumed 50 on the anchor date that measured performance could
only push UP, by at most 1.5 points a week (with decay the only downward
force). The asymmetry was meant to stop a light week or a substitution from
reading as strength loss — and it did — but the cap made the number count
lifting weeks: a review on 2026-10-20 found it rising by exactly the cap every
week with a lift, far below the measured index, and rising in a week the lifts
fell. The median of three lifting weeks is the guard against one light week
now; a lighter month reads as one, which is what a measurement does.

TONNAGE IS A SEPARATE METRIC AND SHARES NO TERM WITH THIS ONE
-------------------------------------------------------------
See services/tonnage.py. Tonnage is sum(load * reps) over completed loaded
sets in one week. This module never reads it. A fourth set at an easy weight
raises tonnage and leaves estimated 1RM untouched, which is the whole point.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

REGIONS: tuple[str, ...] = ("upper_body", "core", "lower_body")

# ── estimation ──────────────────────────────────────────────────────────────
EPLEY_DIVISOR: float = 30.0
# Epley is validated to roughly 10 reps. Beyond that the estimate degrades
# fast, so an observation is flagged rather than silently trusted. Measured on
# the current log: 0 of 17 estimates fall inside this range, because the sets
# are 10-12 reps at RPE 5-6 (i.e. 14-18 effective reps). The fix is a periodic
# ~5-rep set at RPE 8, not a change to this constant.
MAX_VALID_EFFECTIVE_REPS: float = 12.0

# ── the headline (the owner, 2026-10-20) ────────────────────────────────────
HEADLINE_WEEKS: int = 3            # lifting weeks the median is taken over
HEADLINE_LOOKBACK_WEEKS: int = 8   # how far back a lifting week may be

# ── calibration ─────────────────────────────────────────────────────────────
CALIBRATION_INDEX: float = 50.0
CALIBRATION_EXIT: float = 0.70   # confidence a region needs to stop being provisional
CONFIDENCE_N_TARGET: float = 12.0  # observations for full quantity confidence


@dataclass(frozen=True)
class Observation:
    """One exercise on one day, reduced to its best working set."""
    exercise: str
    session_date: date
    weight_kg: float
    reps: float
    rpe: float
    effective_reps: float
    e1rm: float
    within_epley_range: bool


@dataclass(frozen=True)
class RegionState:
    region: str
    index: float | None          # measured index, None when nothing is comparable
    # What the card shows: the measured index once confidence reaches
    # CALIBRATION_EXIT, CALIBRATION_INDEX below it, None with nothing measured.
    displayed_index: float | None
    confidence: float
    share: float
    contribution_points: float
    contribution_pct: float
    observations: int
    calibrating: bool
    components: dict[str, float] = field(default_factory=dict)


def estimated_1rm(weight_kg: float, reps: float, rpe: float | None) -> tuple[float, float, bool]:
    """Epley on reps-to-failure. A submaximal set is first converted to the
    all-out set it is equivalent to: RIR = 10 - RPE, so 10 reps at RPE 6
    behaves like a 14-rep max. Returns (e1RM, effective_reps, within_range).

    `rpe` of None is treated as RPE 10 (RIR 0) — the conservative reading,
    since assuming a set was easy would inflate the estimate."""
    rir = 0.0 if rpe is None else max(0.0, 10.0 - float(rpe))
    effective = float(reps) + rir
    e1rm = float(weight_kg) * (1.0 + effective / EPLEY_DIVISOR)
    return e1rm, effective, effective <= MAX_VALID_EFFECTIVE_REPS


def baseline_e1rm(peak_kg: float, peak_reps: float, pr_rir: float) -> float:
    """The 2025 peak set expressed as an e1RM, so today and last year are
    compared on the same scale rather than as raw kilograms."""
    return float(peak_kg) * (1.0 + (float(peak_reps) + pr_rir) / EPLEY_DIVISOR)


def exercise_index(e1rm_now: float, e1rm_2025: float) -> float | None:
    """This exercise as a percentage of its own 2025 self. None when there is
    no 2025 baseline. **Kilograms never cross exercises** — a hip thrust and a
    face pull meet only after both have become percentages of themselves."""
    if e1rm_2025 <= 0:
        return None
    return e1rm_now / e1rm_2025 * 100.0


def qualifying_rows(rows: list[dict], today: date, pr_rir: float = 1.0):
    """Every row that can produce an estimate, as (name, day, loaded_sets, rpe).

    ONE gate, used by everything that counts or measures. A set only qualifies
    if it carries both reps and a real external load — an unloaded rehab drill
    has no 1RM to estimate and must not be invented one. Rows with no name, no
    date, an unparseable date, or a date after `today` are dropped, so a caller
    can replay history.

    This exists as a shared generator rather than being written out at each
    call site because it already diverged once: the observation COUNT that
    feeds confidence was filtering on neither the date nor `today`, so a
    future-dated or malformed row inflated `quantity`, and confidence is the
    shrinkage weight that decides the displayed split.

    `rows` is Repository.get_all_training_exercises_raw()'s shape: dicts with
    `movement_name`, `session_date`, `sets` (a list of {reps, weight, ...}),
    `exercise_rpe` and `session_rpe`."""
    for row in rows:
        name = row.get("movement_name")
        raw_date = row.get("session_date")
        if not name or not raw_date:
            continue
        try:
            day = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            continue
        if day > today:
            continue
        # `not s.get("is_warmup")`: a ramp set is six reps at ~62% and would
        # drag every 1RM estimate down as though it were a failed working set.
        # Absent key = working, which is all history before 2026-08.
        loaded = [
            s for s in (row.get("sets") or [])
            if (s.get("reps") or 0) and (s.get("weight") or 0) and not s.get("is_warmup")
        ]
        if not loaded:
            continue
        yield name, day, loaded, estimate_rpe(row, pr_rir)


def estimate_rpe(row: dict, pr_rir: float = 1.0) -> float:
    """The RPE a strength estimate reads for every working set: the same reps
    left the 2025 best is given (strength_baselines.PR_RIR, `pr_rir`), so both
    years are estimated the same way (WP-38, the athlete, 2026-10-26: "take my
    2025 lifts and extrapolate what would be my ONE REP MAX and then compare
    that against my ORM this year if you extrapolated it as well").

    Until 2026-10-26 it was the SESSION rating (WP-15, 2026-10-13): a session
    rated 6 read every set as 4 reps short of failure, sets taken to failure
    included, while the 2025 best was read as 1 short, which lifted today's
    estimates about 6-10% against last year's. Never `exercise_rpe` either:
    since 2026-08-14 it is filled from heart rate, which is not reps in reserve
    (Key Rule 23). `row` is kept for the call sites; nothing in it is read."""
    return 10.0 - float(pr_rir)


def observation_days(rows: list[dict], today: date | None = None) -> dict[str, set[date]]:
    """The distinct DAYS each exercise was measured on, past the same gate the
    estimates use. Days, not rows — two rows for one lift in one session are
    one observation of it, not two."""
    today = today or date.today()
    out: dict[str, set[date]] = {}
    for name, day, _loaded, _rpe in qualifying_rows(rows, today):
        out.setdefault(name, set()).add(day)
    return out


def best_observations(
    rows: list[dict],
    today: date | None = None,
    pr_rir: float = 1.0,
) -> dict[str, Observation]:
    """The most recent qualifying observation per exercise, each set read with
    the 2025 best's reps left (`pr_rir`, estimate_rpe)."""
    today = today or date.today()
    latest: dict[str, Observation] = {}
    for name, session_date, loaded, rpe in qualifying_rows(rows, today, pr_rir):
        best: Observation | None = None
        for s in loaded:
            e1rm, eff, ok = estimated_1rm(float(s["weight"]), float(s["reps"]), rpe)
            if best is None or e1rm > best.e1rm:
                best = Observation(
                    exercise=name, session_date=session_date,
                    weight_kg=float(s["weight"]), reps=float(s["reps"]),
                    rpe=float(rpe) if rpe is not None else 10.0,
                    effective_reps=eff, e1rm=e1rm, within_epley_range=ok,
                )
        if best is None:
            continue
        prior = latest.get(name)
        # Later day wins outright. On the SAME day the heavier estimate wins —
        # an exercise can occupy two rows in one session (a top set logged
        # apart from the back-offs, or a re-log), and plain ">=" would let
        # whichever happened to come last in query order overwrite the best
        # set of the day and understate the index.
        if (prior is None
                or best.session_date > prior.session_date
                or (best.session_date == prior.session_date and best.e1rm > prior.e1rm)):
            latest[name] = best
    return latest


def region_index(
    indices: dict[str, float],
    weights: dict[str, float],
) -> float | None:
    """Movement-weighted mean of the per-exercise indices in one region.
    `weights` is the exercise's movement weight (a barbell hinge counts for
    more than a cable face pull). None when the region has no comparable
    exercise at all — which is core's situation today."""
    if not indices:
        return None
    num = sum(weights.get(name, 1.0) * value for name, value in indices.items())
    den = sum(weights.get(name, 1.0) for name in indices)
    if den <= 0:
        return None
    return num / den


def region_confidence(
    indices: dict[str, float],
    weights: dict[str, float],
    comparabilities: dict[str, float],
    observation_count: int,
    n_target: float = CONFIDENCE_N_TARGET,
) -> tuple[float, dict[str, float]]:
    """How much this region's index deserves to be believed, as a product of
    three independent ways it can be untrustworthy:

      quantity      — too few observations
      comparability — the 2025 baselines are not really the same lift
      consistency   — the exercises inside the region disagree with each other

    A product, not a mean, deliberately: any one of the three being zero
    should zero the result. Core has no comparable baseline, so its
    comparability is 0 and its confidence is 0 no matter how many Pallof
    Presses get logged.

    Returns (confidence, components) so the components can be shown."""
    if not indices:
        return 0.0, {"quantity": 0.0, "comparability": 0.0, "consistency": 0.0}
    den = sum(weights.get(name, 1.0) for name in indices)
    if den <= 0:
        return 0.0, {"quantity": 0.0, "comparability": 0.0, "consistency": 0.0}

    quantity = min(1.0, observation_count / n_target) if n_target > 0 else 0.0
    comparability = sum(
        weights.get(name, 1.0) * comparabilities.get(name, 0.0) for name in indices
    ) / den
    values = list(indices.values())
    if len(values) > 1 and statistics.mean(values) > 0:
        cv = statistics.pstdev(values) / statistics.mean(values)
        consistency = max(0.0, 1.0 - min(1.0, cv))
    else:
        # A single exercise cannot corroborate itself. Treated as maximally
        # inconsistent rather than as perfect agreement, which is what a
        # naive "no spread => consistency 1" would wrongly conclude.
        consistency = 0.0
    components = {
        "quantity": quantity,
        "comparability": comparability,
        "consistency": consistency,
    }
    return quantity * comparability * consistency, components


def region_shares(
    confidence: dict[str, float],
    evidence: dict[str, float],
    prior: dict[str, float],
) -> dict[str, float]:
    """How the overall divides across the three sectors.

    A shrinkage estimator: `(1 - k) * prior + k * evidence`, normalised. With
    no confidence the split is the stated prior; as confidence grows the
    evidence takes over. This is what makes the allocation refine *gradually* —
    one session moves `evidence` a little and `k` a little, so the share moves
    a little. Nothing here can swing after a single workout.

    `evidence` is each region's share of the total movement-weight mass, i.e.
    COVERAGE, not physiology. Left to itself it would hand core 4% purely
    because core has one loaded exercise against upper body's four — which is
    exactly why it is held back by confidence rather than used directly."""
    raw: dict[str, float] = {}
    for region in REGIONS:
        k = max(0.0, min(1.0, confidence.get(region, 0.0)))
        raw[region] = (1.0 - k) * prior.get(region, 0.0) + k * evidence.get(region, 0.0)
    total = sum(raw.values())
    if total <= 0:
        # Degenerate only if the prior itself is empty; fall back to even.
        return {region: 1.0 / len(REGIONS) for region in REGIONS}
    return {region: raw[region] / total for region in REGIONS}


def split_parts(shares: dict[str, float], total: float, dp: int = 1) -> dict[str, float]:
    """`shares` scaled to `total`, rounded so the parts still sum to `total`
    EXACTLY.

    Naive rounding breaks the one rule this whole model is built on:
    0.323/0.186/0.491 x 50 rounds to 16.2 + 9.3 + 24.6 = 50.1. Every part but
    the last is rounded, then the last absorbs the remainder."""
    parts: dict[str, float] = {}
    running = 0.0
    ordered = list(REGIONS)
    for region in ordered[:-1]:
        value = round(shares.get(region, 0.0) * total, dp)
        parts[region] = value
        running += value
    parts[ordered[-1]] = round(total - running, dp)
    return parts


# ── the headline over time ──────────────────────────────────────────────────

def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_measured_index(
    rows: list[dict],
    peaks: dict[str, tuple[float, int, float, str]],
    movement_weights: dict[str, float],
    pr_rir: float,
    today: date | None = None,
    weeks: int = 8,
) -> list[tuple[date, float | None]]:
    """One measured index per calendar week — the movement-weighted mean of
    every exercise observed that week, each already normalised against its own
    2025 peak.

    None means "no qualifying observation", which is different from zero: a
    week of unloaded rehab produces no estimate rather than an estimate of
    nothing. The model reads None as absent stimulus, not as a bad week."""
    today = today or date.today()
    last = week_start(today)
    span = [last - timedelta(weeks=n) for n in range(weeks - 1, -1, -1)]
    first = span[0]

    best: dict[date, dict[str, float]] = {w: {} for w in span}
    for row in rows:
        name = row.get("movement_name")
        raw_date = row.get("session_date")
        if name not in peaks or not raw_date:
            continue
        try:
            day = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            continue
        if day > today:
            continue
        wk = week_start(day)
        if wk < first or wk > last:
            continue
        loaded = [s for s in (row.get("sets") or [])
                  if (s.get("reps") or 0) and (s.get("weight") or 0)
                  and not s.get("is_warmup")]
        if not loaded:
            continue
        rpe = estimate_rpe(row, pr_rir)
        peak_kg, peak_reps, _comparability, _why = peaks[name]
        base = baseline_e1rm(peak_kg, peak_reps, pr_rir)
        top = max(estimated_1rm(float(s["weight"]), float(s["reps"]), rpe)[0] for s in loaded)
        index = exercise_index(top, base)
        if index is None:
            continue
        best[wk][name] = max(best[wk].get(name, 0.0), index)

    out: list[tuple[date, float | None]] = []
    for wk in span:
        found = best[wk]
        out.append((wk, region_index(found, movement_weights) if found else None))
    return out


def score_series(
    rows: list[dict],
    peaks: dict[str, tuple[float, int, float, str]],
    movement_weights: dict[str, float],
    pr_rir: float,
    today: date | None = None,
    weeks: int = 8,
) -> list[dict]:
    """The Overall Strength Score, week by week, ready to plot: the last
    `weeks` weeks, each {"week", "measured", "level", "why"}.

    `measured` is that week's measured index (weekly_measured_index; None with
    no lift). `level` is the headline as it read that week: the median of the
    last HEADLINE_WEEKS weeks with a lift, up to and including it, among the
    HEADLINE_LOOKBACK_WEEKS before it; None when none of them had a lift."""
    today = today or date.today()
    measured = weekly_measured_index(rows, peaks, movement_weights, pr_rir, today=today,
                                     weeks=weeks + HEADLINE_LOOKBACK_WEEKS - 1)
    points = []
    for i in range(HEADLINE_LOOKBACK_WEEKS - 1, len(measured)):
        window = [m for _w, m in measured[i - HEADLINE_LOOKBACK_WEEKS + 1:i + 1] if m is not None]
        used = window[-HEADLINE_WEEKS:]
        # One decimal, as shown: the regions divide it at one decimal and must total it.
        level = round(statistics.median(used), 1) if used else None
        why = (f"middle of {len(used)} lifting week{'' if len(used) == 1 else 's'}" if used
               else f"no lift in {HEADLINE_LOOKBACK_WEEKS} weeks")
        week, value = measured[i]
        points.append({"week": week, "measured": value, "level": level, "why": why})
    return points


def headline(points: list[dict]) -> float | None:
    """The headline: the series' last level, the number the chart ends on
    (None when there is no lift in the look-back)."""
    return points[-1]["level"] if points else None


# ── the whole picture, in one call# ── the whole picture, in one call ──────────────────────────────────────────

def snapshot(
    rows: list[dict],
    peaks: dict[str, tuple[float, int, float, str]],
    region_map: dict[str, str],
    movement_weights: dict[str, float],
    prior: dict[str, float],
    pr_rir: float,
    overall: float,
    today: date | None = None,
) -> dict:
    """The regional half of the Strength screen, from the raw exercise rows.
    `overall` is the headline the three regions divide; screen() passes the
    measured headline (0.0 when there is none).

    CALIBRATION IS PER REGION (2026-10-13, WP-15). A region shows its measured
    index once its confidence reaches CALIBRATION_EXIT; below that it shows
    CALIBRATION_INDEX, a stated placeholder; with nothing measured it shows
    None, which the screen prints as "—" — never 0, which would claim a
    measurement of nothing, and never 50, which would claim a calibration
    that cannot happen. It used to be one flag the view always set, so every
    region showed 50 whatever was logged.

    The snapshot's own `calibrating` is True while any MEASURED region is
    still below the exit, or while nothing is measured at all. A region that
    cannot be measured (core: no 2025 kilogram baseline) does not hold the
    others in calibration for ever.

    Contributions divide `overall` by the shares, so the three always total
    the headline on screen."""
    today = today or date.today()
    observed = best_observations(rows, today=today, pr_rir=pr_rir)

    per_exercise: dict[str, dict] = {}
    for name, obs in observed.items():
        peak = peaks.get(name)
        if peak is None:
            continue
        peak_kg, peak_reps, comparability, why = peak
        base = baseline_e1rm(peak_kg, peak_reps, pr_rir)
        index = exercise_index(obs.e1rm, base)
        if index is None:
            continue
        per_exercise[name] = {
            "index": index, "e1rm_now": obs.e1rm, "e1rm_2025": base,
            "comparability": comparability, "why": why,
            "region": region_map.get(name), "observation": obs,
        }

    # Distinct measured DAYS per exercise, past the same gate the estimates
    # use — so a future-dated or malformed row cannot inflate confidence, and
    # two rows for one lift in one session count once.
    counts = {name: len(days) for name, days in observation_days(rows, today).items()
              if name in per_exercise}

    indices_by_region: dict[str, dict[str, float]] = {r: {} for r in REGIONS}
    comparability_by_region: dict[str, dict[str, float]] = {r: {} for r in REGIONS}
    for name, data in per_exercise.items():
        region = data["region"]
        if region in indices_by_region:
            indices_by_region[region][name] = data["index"]
            comparability_by_region[region][name] = data["comparability"]

    measured_index, confidence, components, observation_counts = {}, {}, {}, {}
    evidence_mass: dict[str, float] = {}
    for region in REGIONS:
        idx = indices_by_region[region]
        measured_index[region] = region_index(idx, movement_weights)
        n_obs = sum(counts.get(name, 0) for name in idx)
        observation_counts[region] = n_obs
        confidence[region], components[region] = region_confidence(
            idx, movement_weights, comparability_by_region[region], n_obs,
        )
        evidence_mass[region] = sum(movement_weights.get(name, 1.0) for name in idx)

    mass_total = sum(evidence_mass.values())
    evidence = {
        r: (evidence_mass[r] / mass_total if mass_total > 0 else 0.0) for r in REGIONS
    }
    shares = region_shares(confidence, evidence, prior)

    points = split_parts(shares, overall)
    percents = split_parts(shares, 100.0)

    states = []
    for region in REGIONS:
        exited = confidence[region] >= CALIBRATION_EXIT
        states.append(RegionState(
            region=region,
            index=measured_index[region],
            displayed_index=displayed_index(measured_index[region], confidence[region]),
            confidence=confidence[region],
            share=shares[region],
            contribution_points=points[region],
            contribution_pct=percents[region],
            observations=observation_counts[region],
            calibrating=not exited,
            components=components[region],
        ))
    measured_states = [s for s in states if s.index is not None]

    return {
        "overall": overall,
        "calibrating": not measured_states or any(s.calibrating for s in measured_states),
        "regions": states,
        "exercises": per_exercise,
        "observation_dates": sorted({o.session_date for o in observed.values()}),
    }


def displayed_index(measured: float | None, confidence: float) -> float | None:
    """What one region's card shows: the measured index once trusted, the
    placeholder while calibrating, nothing without a measurement."""
    if measured is None:
        return None
    return measured if confidence >= CALIBRATION_EXIT else CALIBRATION_INDEX


def screen(
    rows: list[dict],
    peaks: dict[str, tuple[float, int, float, str]],
    region_map: dict[str, str],
    movement_weights: dict[str, float],
    prior: dict[str, float],
    pr_rir: float,
    today: date | None = None,
    weeks: int = 8,
    hold_baselines: dict[str, tuple[float, str]] | None = None,
) -> dict:
    """The whole Strength screen in one call: the measured headline (headline
    of score_series), the regions dividing it, and calibration per region.
    snapshot()'s keys plus `score_series`; `overall` is the chart's last level,
    None with no lift in the look-back. `core_hold` is core's hold-time index
    (core_hold_index) when `hold_baselines` is given — shown on core's card
    only, never part of `overall`."""
    today = today or date.today()
    points = score_series(rows, peaks, movement_weights, pr_rir, today=today, weeks=weeks)
    level = headline(points)
    regional = snapshot(rows, peaks, region_map, movement_weights, prior, pr_rir,
                        level or 0.0, today=today)
    divided = split_parts({s.region: s.share for s in regional["regions"]}, level or 0.0)
    return {
        **regional,
        "overall": level,
        "regions": [replace(s, contribution_points=divided[s.region])
                    for s in regional["regions"]],
        "score_series": points,
        "core_hold": core_hold_index(rows, hold_baselines, today) if hold_baselines else None,
    }


# ─── Core: hold time (WP-15 step 6, decided 2026-10-13) ─────────────────────
# Core cannot be scored on the kilogram scale (its 2025 peak is a band), so it
# gets its own index from the timed plank test: each line's latest test, the
# WORSE side (the battery's rule: the worse side decides, never an average),
# as a share of the 2025 hold in seconds, × 100; core's index is the mean of
# its lines. It is shown on core's own card from the first test, marked
# provisional, and it stays OUT of the headline: the weekly model reads the
# lifts only. docs/core_hold_index_design_2026-10-13.md.

def hold_seconds(sets: list[dict]) -> tuple[float, float] | None:
    """(right, left) seconds of a timed test hold's first set: `tut` is the
    right side, `tut_left` the left (absent when the sides were equal)."""
    for s in sets or []:
        right = s.get("tut")
        if right is None:
            continue
        left = s.get("tut_left")
        return float(right), float(right if left is None else left)
    return None


def core_hold_index(rows: list[dict], baselines: dict[str, tuple[float, str]],
                    today: date | None = None) -> dict | None:
    """Core's hold-time index, or None before any line has been timed.

    Returns {"index", "date", "lines"}: each line's latest test as
    {"name", "date", "right", "left", "worse", "baseline", "index"}. `rows` is
    get_all_training_exercises_raw()'s shape."""
    today = today or date.today()
    latest: dict[str, tuple[date, tuple[float, float]]] = {}
    for row in rows:
        name = row.get("movement_name")
        if name not in baselines:
            continue
        try:
            day = date.fromisoformat(str(row.get("session_date"))[:10])
        except (TypeError, ValueError):
            continue
        held = hold_seconds(row.get("sets"))
        if day > today or held is None:
            continue
        if name not in latest or day > latest[name][0]:
            latest[name] = (day, held)
    if not latest:
        return None
    lines = []
    for name, (day, (right, left)) in sorted(latest.items()):
        base = baselines[name][0]
        worse = min(right, left)
        lines.append({"name": name, "date": day, "right": right, "left": left, "worse": worse,
                      "baseline": base, "index": round(worse / base * 100, 1)})
    return {"index": round(sum(l["index"] for l in lines) / len(lines), 1),
            "date": max(l["date"] for l in lines), "lines": lines}
