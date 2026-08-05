"""
services/flexibility.py — the Flexibility score: Range x Control.

Pure functions only. No I/O, no Streamlit, no hidden clock reads — every
date-dependent function takes an explicit `today`, same convention as
services/engine.py, services/strength.py and services/body_composition.py.

THE ONE IDEA
------------
A perfect flexible body is TWO things, not one: the range to reach a position,
and the control to hold it correctly. Either alone is worthless — range without
control is hanging on a ligament, control without range is a position never
reached. So a region scores

    region = sqrt(RANGE x CONTROL)

and the geometric mean is the point, not an implementation detail. An arithmetic
mean lets a 100 on one axis carry a 20 on the other to a respectable 60; the
geometric mean gives 45, and a zero on either axis correctly annihilates the
region. Both axes are also kept VISIBLE all the way to the screen, because
"Range 90, Control 40" says something the single number 60 does not.

WHY CONTROL PENALISES THE TOP OF THE SCALE
------------------------------------------
This is the part that differs from every commercial flexibility app, and it is
here because patient_profile.PROFILE["hypermobility"] instructs it: Beighton
6/9, so stability is muscular rather than ligamentous, and the standing training
implication is to favour "controlled-range strength/stability work over passive
end-range stretching".

The athlete's own depth scale runs 1 = can barely enter the position to
100 = at the physical limit with no stretch sensation left. On 2026-08-05 six of
his 22 poses scored 80-88 — supine twists, knee-to-chest, happy baby — every one
a position entered with no muscular endpoint. Under a more-is-better model those
six are his best results. They are in fact the hazard the profile names.

So CONTROL_BAND is two-sided: full marks inside it, penalised below (cannot
enter the position) AND above (no stop at the end of it). 100 on this axis means
IDEAL, never MAXIMUM. Confirmed as the intended semantics by the athlete,
2026-08-05.

SCORE FIRST, THEN AVERAGE. NEVER AVERAGE THEN SCORE.
----------------------------------------------------
The hamstring region sees three poses: straddle 25, Walk the Dog 76, Down Dog
64. Averaging the RATINGS gives 55, which lands inside the ideal band and scores
100 — erasing the 25, the single most informative reading in the whole
assessment. Scoring each pose first and averaging the SCORES gives 65.5 and
keeps it. Same class of error as summing Oura sleep periods before deduplicating
them (see services/biometrics.dedupe_sleep_periods).

STALENESS DECAYS WEIGHT, NEVER VALUE
------------------------------------
The goniometry is from 2025-01-17 and the depth ratings from 2026-08-05 — 566
days apart. A combined number that weights them equally pretends they are
contemporaneous. But decaying the stale VALUE would invent a decline that was
never measured, which is the error services/strength.py's asymmetry rule exists
to prevent. So staleness reduces an axis's CONFIDENCE, and confidence sets how
much a region moves the overall. The score itself is whatever was measured.

WHAT THIS MODULE REFUSES TO DO
------------------------------
No flexibility age in years. The vendor screen ships one — 28 against a "real
age" of 31 — and it is computed from a Jan-2025 measurement against a LIVE
chronological age, so it was -2 at measurement, displays as -3, and widens every
birthday without anybody moving. Same refusal, and the same reason, as
services/body_composition.py's.

No scoring the vendor's own Low/Normal verdicts. They are kept verbatim as
provenance and nothing computes from them: the norm tables behind them are
undisclosed, so converting a verdict into a score would import the vendor's
reference into ours and then double-count it against our own band.

No filling an empty region from the other instrument, or from a training note.
Squat Depth reads "No data yet" on the device and has no pose in the yoga flow;
it stays uncovered and is REPORTED as uncovered rather than imputed.

No scoring a region whose reference band is None. `lat_flex` is the live case —
the vendor calls 20-21 deg "Normal", which contradicts the obvious reading of
its label, and a band guessed out of a contradiction is worse than no band.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import flexibility_baselines as _fb

# ── tunable parameters, all in one place ─────────────────────────────────────
#
# Calibrated 2026-08-05 against the athlete's own 22 ratings so that: his worst
# pose (straddle, 25) scores ~25; a pose at the physical limit with no muscular
# stop (88) scores below 50; and the ideal band matches "deep enough to be a
# real position, with a felt endpoint". These are a documented starting point,
# not a fit — there is one rating date, so nothing could be fitted. Change them
# deliberately and record why; every score in the app moves when they do.

#: Depth ratings inside this band are ideal and score 100.
CONTROL_BAND: tuple[float, float] = (50.0, 70.0)

#: Below the band the falloff is (v/lo)**this — quadratic, so failing to enter a
#: position at all is punished hard.
UNDERSHOOT_EXPONENT: float = 2.0

#: Above the band the falloff is linear at this many points per rating point.
#: 3.0 puts a rating of 88 ("no sensation left") at 46.
OVERSHOOT_SLOPE: float = 3.0

#: Same shape as CONTROL_BAND, applied to degrees against a region's reference.
RANGE_UNDERSHOOT_EXPONENT: float = 1.5
RANGE_OVERSHOOT_SLOPE_PER_DEG: float = 1.5

#: An axis's confidence halves every this-many days. ROM does not change fast,
#: so a year is generous rather than punitive; the 566-day-old goniometry still
#: lands near 0.34 rather than at zero.
CONFIDENCE_HALFLIFE_DAYS: float = 365.0

#: Multiplier applied while a reading's protocol is unrecorded and its reference
#: band is therefore assumed. Removed automatically the moment `protocol` is set.
PROVISIONAL_PROTOCOL_PENALTY: float = 0.6

#: A region's confidence is (sum of its present axes' confidences) / this. Two,
#: because two axes is the complete evidence for a region — so a region with one
#: fresh perfect axis tops out at 0.5, and that is the intended message.
IDEAL_AXIS_COUNT: float = 2.0

#: A region's Control axis needs at least this much summed pose weight before it
#: is computed at all. Without it, `neck` would take its entire Control score
#: from one pose contributing 0.1 — a number that looks like evidence and isn't.
MIN_CONTROL_EVIDENCE: float = 0.5

DIRECTION_RESTRICTED = "restricted"
DIRECTION_IDEAL      = "ideal"
DIRECTION_UNSTABLE   = "unstable"


# ── results ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AxisScore:
    """One axis of one region. `value` is the raw measurement in its own units;
    `score` is 0-100 where 100 is IDEAL. `direction` says which side of ideal a
    sub-100 score fell on, because 65 restricted and 65 unstable call for
    opposite responses and the number alone cannot distinguish them."""
    name: str                    # "range" | "control"
    score: float
    direction: str
    confidence: float
    value: float | None = None
    unit: str = ""
    provisional: bool = False
    measured_on: date | None = None
    detail: str = ""


@dataclass(frozen=True)
class RegionScore:
    key: str
    label: str
    score: float | None          # None = not scoreable on any axis
    range_axis: AxisScore | None
    control_axis: AxisScore | None
    confidence: float
    weight: float
    unscoreable_reason: str = ""

    @property
    def axes_present(self) -> int:
        return sum(1 for a in (self.range_axis, self.control_axis) if a is not None)

    @property
    def direction(self) -> str:
        """The worse axis decides how the region reads — a region held back by
        an unstable axis and one held back by a restricted axis need different
        work, and the region-level label should say which."""
        axes = [a for a in (self.range_axis, self.control_axis) if a is not None]
        if not axes:
            return ""
        worst = min(axes, key=lambda a: a.score)
        return worst.direction


@dataclass(frozen=True)
class FlexibilityScore:
    overall: float | None
    regions: list[RegionScore]
    unmapped_poses: list[str] = field(default_factory=list)
    uncovered_regions: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        """Fraction of the ideal evidence actually held: confidence-weighted by
        region weight. This is the honest headline beside the score."""
        total = sum(r.weight for r in self.regions)
        if total <= 0:
            return 0.0
        return sum(r.weight * r.confidence for r in self.regions) / total


# ── scoring primitives ───────────────────────────────────────────────────────

def band_score(
    value: float,
    lo: float,
    hi: float,
    undershoot_exponent: float,
    overshoot_slope: float,
) -> tuple[float, str]:
    """Two-sided band score, 0-100, plus which side of ideal it fell on.

    100 anywhere inside [lo, hi]. Below lo it decays as (value/lo)**exponent —
    quadratic by default, so a value at half the floor scores 25 rather than 50.
    Above hi it falls linearly. Clamped to [0, 100].

    The two-sidedness is the whole design: for this athlete, exceeding the ideal
    range is a finding, not an achievement. See the module docstring.
    """
    if lo <= 0 or hi < lo:
        raise ValueError(f"invalid band ({lo}, {hi})")
    if value < lo:
        return max(0.0, min(100.0, 100.0 * (value / lo) ** undershoot_exponent)), DIRECTION_RESTRICTED
    if value > hi:
        return max(0.0, min(100.0, 100.0 - overshoot_slope * (value - hi))), DIRECTION_UNSTABLE
    return 100.0, DIRECTION_IDEAL


def control_score(depth_rating: float) -> tuple[float, str]:
    """Transform the athlete's 1-100 depth rating into a 0-100 CONTROL score.

    These are different scales and conflating them is the single easiest mistake
    to make here. On the depth rating 100 means "at the limit of what is
    physically possible, no sensation left". On the control score 100 means
    "ideal". A depth rating of 88 is therefore a control score of 46.
    """
    return band_score(depth_rating, *CONTROL_BAND, UNDERSHOOT_EXPONENT, OVERSHOOT_SLOPE)


def range_score(degrees: float, band: tuple[float, float]) -> tuple[float, str]:
    """Degrees against a region's ideal reference band."""
    return band_score(degrees, band[0], band[1],
                      RANGE_UNDERSHOOT_EXPONENT, RANGE_OVERSHOOT_SLOPE_PER_DEG)


def staleness_confidence(measured_on: date, today: date) -> float:
    """Confidence multiplier from age alone. Halves every CONFIDENCE_HALFLIFE_DAYS.

    A future date yields 1.0 rather than >1.0 — a clock skew must not manufacture
    extra confidence.
    """
    days = max(0, (today - measured_on).days)
    return 0.5 ** (days / CONFIDENCE_HALFLIFE_DAYS)


# ── axes ─────────────────────────────────────────────────────────────────────

def range_axis(baseline: _fb.RegionBaseline, today: date) -> AxisScore | None:
    """The instrumented degrees axis. None when the region has no reading, or
    has one whose reference band is deliberately absent (see lat_flex)."""
    mean = baseline.mean_deg
    if mean is None or baseline.reference_band is None:
        return None

    score, direction = range_score(mean, baseline.reference_band)
    confidence = staleness_confidence(_fb.SCAN_DATE, today)
    if baseline.provisional:
        confidence *= PROVISIONAL_PROTOCOL_PENALTY

    lo, hi = baseline.reference_band
    detail = f"{mean:.1f}° vs ideal {lo:.0f}-{hi:.0f}°"
    if baseline.provisional:
        detail += f" (band assumed for {baseline.assumed_protocol}; protocol unrecorded)"

    return AxisScore(
        name="range", score=score, direction=direction, confidence=confidence,
        value=mean, unit="°", provisional=baseline.provisional,
        measured_on=_fb.SCAN_DATE, detail=detail,
    )


def control_axis(
    region_key: str,
    ratings: dict[str, int],
    measured_on: date,
    today: date,
) -> AxisScore | None:
    """The self-rated depth axis for one region.

    Scores every contributing pose FIRST, then takes the pose-weighted mean of
    those scores — never the mean of the ratings. Returns None when the region's
    summed pose weight is below MIN_CONTROL_EVIDENCE.
    """
    total_weight = 0.0
    weighted = 0.0
    deficit = {DIRECTION_RESTRICTED: 0.0, DIRECTION_UNSTABLE: 0.0}
    for pose, rating in ratings.items():
        weight = _fb.POSE_REGION_WEIGHT.get(pose, {}).get(region_key)
        if not weight:
            continue
        score, pose_direction = control_score(rating)
        weighted += weight * score
        total_weight += weight
        if pose_direction != DIRECTION_IDEAL:
            deficit[pose_direction] += weight * (100.0 - score)

    if total_weight < MIN_CONTROL_EVIDENCE:
        return None

    mean_score = weighted / total_weight

    # Direction is decided by WHERE THE LOST POINTS CAME FROM, not by the mean
    # rating. Averaging the ratings and scoring once is the exact trap this
    # module forbids, and it bites hardest here: the hamstring region's ratings
    # are 25, 76 and 64, whose weighted mean is ~55 — inside the ideal band. So
    # a rating-mean would label the region "ideal" while its score sits at 65,
    # dragged down by a straddle fold he can barely enter. Attributing the
    # deficit instead correctly returns "restricted".
    if mean_score >= 99.5:
        direction = DIRECTION_IDEAL
    elif deficit[DIRECTION_RESTRICTED] >= deficit[DIRECTION_UNSTABLE]:
        direction = DIRECTION_RESTRICTED
    else:
        direction = DIRECTION_UNSTABLE

    return AxisScore(
        name="control", score=mean_score, direction=direction,
        confidence=staleness_confidence(measured_on, today),
        value=mean_score, unit="/100", provisional=False,
        measured_on=measured_on,
        detail=(
            f"{total_weight:.1f} pose-weight · lost points "
            f"{deficit[DIRECTION_RESTRICTED]:.0f} restricted / "
            f"{deficit[DIRECTION_UNSTABLE]:.0f} unstable"
        ),
    )


# ── composition ──────────────────────────────────────────────────────────────

def score_region(
    region_key: str,
    ratings: dict[str, int],
    ratings_date: date,
    today: date,
) -> RegionScore:
    baseline = _fb.REGION_BASELINES[region_key]
    weight = _fb.REGION_WEIGHT[region_key]

    r_axis = range_axis(baseline, today)
    c_axis = control_axis(region_key, ratings, ratings_date, today)

    present = [a for a in (r_axis, c_axis) if a is not None]
    if not present:
        reason = (
            "no instrumented reading and no yoga pose maps to this region"
            if baseline.mean_deg is None
            else "reference band deliberately absent — see flexibility_baselines"
        )
        return RegionScore(
            key=region_key, label=baseline.label, score=None,
            range_axis=r_axis, control_axis=c_axis, confidence=0.0,
            weight=weight, unscoreable_reason=reason,
        )

    if len(present) == 2:
        # Geometric mean — a zero on either axis annihilates the region, which
        # is the intended behaviour and what an arithmetic mean would hide.
        score = (r_axis.score * c_axis.score) ** 0.5
    else:
        score = present[0].score

    confidence = sum(a.confidence for a in present) / IDEAL_AXIS_COUNT

    return RegionScore(
        key=region_key, label=baseline.label, score=score,
        range_axis=r_axis, control_axis=c_axis,
        confidence=confidence, weight=weight,
    )


def overall_score(
    ratings: dict[str, int] | None = None,
    ratings_date: date | None = None,
    today: date | None = None,
) -> FlexibilityScore:
    """The whole sector. `today` is required in spirit — it defaults only so
    callers with no clock of their own are not forced to invent one, and every
    date-dependent term below reads it explicitly.

    Overall is the confidence-weighted mean of scoreable regions:

        overall = sum(weight_r * confidence_r * score_r)
                / sum(weight_r * confidence_r)

    which is what makes "adding either metric changes the overall" true, and
    makes the SIZE of the change proportional to the evidence behind it. Adding
    a Range reading to a Control-only region changes both the score (single axis
    -> geometric mean) and the confidence (0.5 -> up to 1.0), so it moves the
    numerator and the denominator together.
    """
    if ratings is None:
        ratings = _fb.POSE_DEPTH_RATING_2026_08_05
    if ratings_date is None:
        ratings_date = _fb.DEPTH_RATING_DATE
    if today is None:
        today = date.today()

    regions = [
        score_region(key, ratings, ratings_date, today)
        for key in _fb.REGION_WEIGHT
    ]

    numerator = 0.0
    denominator = 0.0
    for r in regions:
        if r.score is None:
            continue
        w = r.weight * r.confidence
        numerator += w * r.score
        denominator += w

    overall = numerator / denominator if denominator > 0 else None

    unmapped = sorted(
        p for p in ratings
        if p not in _fb.POSE_REGION_WEIGHT and p not in _fb.UNMAPPED_POSES
    )

    return FlexibilityScore(
        overall=overall,
        regions=sorted(regions, key=lambda r: (-r.weight, r.key)),
        unmapped_poses=unmapped,
        uncovered_regions=[r.key for r in regions if r.score is None],
    )
