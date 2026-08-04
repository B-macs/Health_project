"""
services/strength.py — the Overall Strength Score and its regional split.

Pure functions only. No I/O, no Streamlit, no hidden clock reads — every
date-dependent function takes an explicit `today`, same convention as
services/engine.py and services/bioage.py.

WHAT THIS REPLACES, AND WHY
---------------------------
services/bioage.py's Stage-Adjusted Recovery Score is
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

THE ASYMMETRY THAT MAKES IT SAFE
--------------------------------
Measured performance can only push the level UP. The only downward force is
detraining decay from absent stimulus. One rule covers every case where a
number falls for a reason that is not strength loss: pain, a substituted
movement, a rehab restriction, a deliberately lighter week, a bad night's sleep.
None of them can read as getting weaker, because nothing except an actual
absence of training is allowed to subtract.

Measured 2026-08-04 on the real log, which is why the rule exists: between 22
and 30 July estimated 1RM moved +291% (RDL), +96% (Hip Thrust) and +76% (Lat
Pulldown) while RPE went 5 -> 6. That is load-finding after a layoff, not a
tripling of strength. Over the same window Face Pull fell 26% and Pallof 35% —
deliberate de-loads. Both directions are protected by the same asymmetry.

TONNAGE IS A SEPARATE METRIC AND SHARES NO TERM WITH THIS ONE
-------------------------------------------------------------
See services/tonnage.py. Tonnage is sum(load * reps) over completed loaded
sets in one week. This module never reads it. A fourth set at an easy weight
raises tonnage and leaves estimated 1RM untouched, which is the whole point.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
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

# ── the weekly model ────────────────────────────────────────────────────────
DEADBAND: float = 1.0        # points the trend must clear before the level moves
ALPHA: float = 0.35          # fraction of the confirmed gap taken per week
GAIN_CAP_POINTS: float = 1.5
GAIN_CAP_PCT: float = 0.03
TREND_WEEKS: int = 3         # width of the CALENDAR window the median is taken over
TREND_MIN_WEEKS: int = 2     # weeks with data needed inside it before a trend exists
GRACE_WEEKS: int = 1         # first week without stimulus costs nothing
DECAY_EARLY: float = 0.0075  # weeks 2-3 without stimulus
DECAY_LATE: float = 0.015    # week 4 onward

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
    displayed_index: float       # what the card shows (held at 50 while calibrating)
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


def best_observations(
    rows: list[dict],
    today: date | None = None,
) -> dict[str, Observation]:
    """The most recent qualifying observation per exercise.

    `rows` is Repository.get_all_training_exercises_raw()'s shape: dicts with
    `movement_name`, `session_date`, `sets` (a list of {reps, weight, ...}),
    `exercise_rpe` and `session_rpe`. A set only qualifies if it carries both
    reps and a real external load — an unloaded rehab drill has no 1RM to
    estimate and must not be invented one.

    Rows dated after `today` are ignored, so a caller can replay history."""
    today = today or date.today()
    latest: dict[str, Observation] = {}
    for row in rows:
        name = row.get("movement_name")
        raw_date = row.get("session_date")
        if not name or not raw_date:
            continue
        try:
            session_date = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            continue
        if session_date > today:
            continue
        loaded = [
            s for s in (row.get("sets") or [])
            if (s.get("reps") or 0) and (s.get("weight") or 0)
        ]
        if not loaded:
            continue
        rpe = row.get("exercise_rpe")
        if rpe is None:
            rpe = row.get("session_rpe")
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
        if prior is None or best.session_date >= prior.session_date:
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


# ── the weekly model ────────────────────────────────────────────────────────

def model_step(
    previous_level: float,
    trend: float | None,
    has_stimulus: bool,
    inactive_weeks: int,
    decay_suspended: bool = False,
) -> tuple[float, str]:
    """One week of the Overall Strength Score.

    Measured performance can only push the level UP; the only downward force
    is detraining decay. See the module docstring for why that asymmetry is
    the safety property and not a modelling shortcut.

    `decay_suspended` holds the level flat through inactivity — used while the
    regional split is still calibrating, because a number that has not yet
    earned trust should not be allowed to fall on its own."""
    if not has_stimulus:
        if decay_suspended:
            return previous_level, "calibrating — decay suspended"
        if inactive_weeks <= GRACE_WEEKS:
            return previous_level, "grace"
        rate = DECAY_EARLY if inactive_weeks <= 3 else DECAY_LATE
        return previous_level * (1.0 - rate), f"decay {rate * 100:.2f}%"
    if trend is None:
        return previous_level, "no trend yet"
    gap = trend - previous_level
    if gap <= DEADBAND:
        return previous_level, "flat"
    gain = min(ALPHA * gap, GAIN_CAP_POINTS, GAIN_CAP_PCT * previous_level)
    return previous_level + gain, f"+{gain:.2f}"


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def run_model(
    weekly_measured: list[tuple[date, float | None]],
    seed: float,
    decay_suspended: bool = False,
) -> list[tuple[date, float | None, float, str]]:
    """Replay the weekly model over CONSECUTIVE calendar weeks.

    The trend window is calendar-indexed, not "the last N weeks that happen to
    have data". Indexing by position let a six-week layoff sit invisibly
    between two entries, so the week you came back compared fresh numbers
    against a median built from before the break and awarded a gain the
    session did not support — caught by simulation, at +1.50 on a week whose
    measured value was 54 against a level of 57.72. A calendar window empties
    across a gap, so returning starts from no trend and has to re-earn it."""
    out: list[tuple[date, float | None, float, str]] = []
    level, inactive = seed, 0
    seen: dict[int, float] = {}
    for i, (label, measured) in enumerate(weekly_measured):
        if measured is None:
            inactive += 1
            level, why = model_step(level, None, False, inactive, decay_suspended)
        else:
            inactive = 0
            seen[i] = measured
            window = [seen[j] for j in range(i - TREND_WEEKS + 1, i + 1) if j in seen]
            trend = statistics.median(window) if len(window) >= TREND_MIN_WEEKS else None
            level, why = model_step(level, trend, True, 0, decay_suspended)
        out.append((label, measured, round(level, 2), why))
    return out


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
                  if (s.get("reps") or 0) and (s.get("weight") or 0)]
        if not loaded:
            continue
        rpe = row.get("exercise_rpe")
        if rpe is None:
            rpe = row.get("session_rpe")
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
    anchor_date: date,
    anchor_value: float,
    today: date | None = None,
    weeks: int = 8,
    calibrating: bool = True,
) -> list[dict]:
    """The Overall Strength Score, week by week, ready to plot.

    Weeks before the anchor carry a measured value but no modelled level —
    there was no level yet. The model is seeded at the anchor and replayed
    forward from there, with decay suspended while calibrating."""
    today = today or date.today()
    measured = weekly_measured_index(rows, peaks, movement_weights, pr_rir,
                                     today=today, weeks=weeks)
    anchor_week = week_start(anchor_date)
    pre = [(w, m) for w, m in measured if w < anchor_week]
    post = [(w, m) for w, m in measured if w >= anchor_week]
    modelled = run_model(post, seed=anchor_value, decay_suspended=calibrating)
    levels = {w: level for w, _m, level, _why in modelled}
    reasons = {w: why for w, _m, _level, why in modelled}
    return (
        [{"week": w, "measured": m, "level": None, "why": "before the anchor"} for w, m in pre]
        + [{"week": w, "measured": m, "level": levels[w], "why": reasons[w]} for w, m in post]
    )


# ── the whole picture, in one call ──────────────────────────────────────────

def snapshot(
    rows: list[dict],
    peaks: dict[str, tuple[float, int, float, str]],
    region_map: dict[str, str],
    movement_weights: dict[str, float],
    prior: dict[str, float],
    pr_rir: float,
    overall: float,
    today: date | None = None,
    calibrating: bool = True,
) -> dict:
    """Everything the Strength screen needs, from the raw exercise rows.

    While `calibrating` is True the overall is held at `overall` and every
    regional index is displayed as CALIBRATION_INDEX — the measured index is
    still computed and returned as `index`, it is simply not what the card
    shows. Contributions are computed from the DISPLAYED index so that the
    three always total the overall on screen."""
    today = today or date.today()
    observed = best_observations(rows, today=today)

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

    # counted per exercise-day, so two sessions of a lift count twice
    counts: dict[str, int] = {}
    for row in rows:
        name = row.get("movement_name")
        if name not in per_exercise:
            continue
        if any((s.get("reps") or 0) and (s.get("weight") or 0) for s in (row.get("sets") or [])):
            counts[name] = counts.get(name, 0) + 1

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

    displayed_index = CALIBRATION_INDEX if calibrating else None
    points = split_parts(shares, overall)
    percents = split_parts(shares, 100.0)

    states = []
    for region in REGIONS:
        shown = displayed_index if displayed_index is not None else (measured_index[region] or 0.0)
        states.append(RegionState(
            region=region,
            index=measured_index[region],
            displayed_index=shown,
            confidence=confidence[region],
            share=shares[region],
            contribution_points=points[region],
            contribution_pct=percents[region],
            observations=observation_counts[region],
            calibrating=confidence[region] < CALIBRATION_EXIT,
            components=components[region],
        ))

    return {
        "overall": overall,
        "calibrating": calibrating,
        "regions": states,
        "exercises": per_exercise,
        "observation_dates": sorted({o.session_date for o in observed.values()}),
    }
