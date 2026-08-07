"""
services/hr_load.py — heart-rate-derived training load (Edwards' TRIMP).

Pure functions, no I/O, no Streamlit — same contract as services/engine.py.
Turns a session's heart-rate record into an objective 0-21 strain value that
can stand in for the subjective RPE-derived one.


Why Edwards' summated heart-rate zones
──────────────────────────────────────
Edwards (1993): load = Σ over zones of (minutes in zone × zone weight),
with zones at 50-60/60-70/70-80/80-90/90-100 %HRmax weighted 1..5.

Chosen over the alternatives for three reasons:

  1. Gym training is intermittent. Banister's TRIMP (1975) collapses a
     session to its MEAN heart rate, so a session of heavy sets separated by
     full recoveries scores the same as steady-state work at the same
     average — systematically under-rating strength training, which is
     exactly the content this engine is scoring. Edwards' keeps the
     distribution, so "extended time in high zones" raises load
     proportionally, which is the behaviour actually wanted here.

  2. It needs the fewest estimated parameters. Edwards' needs HRmax alone.
     Banister additionally needs resting HR and a sex-specific exponential
     constant (0.64·e^1.92x / 0.86·e^1.67x); every extra estimated input is
     another way for a number feeding a training decision to be quietly
     wrong. banister_trimp() below is still provided, as a cross-check and
     because it costs nothing once average HR is known — but it is not what
     strain is derived from.

  3. Lucia's (2003) and Stagno's (2007) TRIMP variants weight zones by
     individually-measured ventilatory or blood-lactate thresholds. Those
     require lab testing that doesn't exist for this athlete, and guessing
     the thresholds would forfeit the precision that is their whole point.

Zone boundaries here are the canonical %HRmax ones recomputed from an
observed HRmax (see estimate_hr_max), NOT the zones configured in the Garmin
account — those are frequently left on a stale 220-age default, and silently
inheriting them would make every load figure depend on an unaudited device
setting. seconds_in_zone_from_garmin_zones() exists for the case where only
Garmin's own pre-bucketed summary is available.


Calibration against the existing RPE scale
──────────────────────────────────────────
hr_strain() deliberately reuses engine.load_to_strain WITHOUT stage CLF
scaling. CLF (0.04/0.40/1.00 by stage) exists because Foster AU over-states
rehab cardiovascular load — but Edwards' load already IS a direct measure of
cardiovascular load, so a session that barely raised heart rate already
scores low. Applying CLF on top would discount it twice.

The happy consequence is that the two scales land on top of each other for
Stage 2 without any fitted fudge factor, because CLF 0.40 was itself tuned to
approximate real cardiovascular load:

    session                     RPE strain    Edwards strain
    light rehab 30min RPE3          11.9            11.3
    moderate gym 45min RPE5         14.8            15.0
    hard gym 60min RPE6             16.3            16.3
    very hard 75min RPE8            18.0            17.6

That continuity is a requirement, not a curiosity: strain falls back to
RPE-only on any session with no matched Garmin activity, and the displayed
number must not visibly jump on those days.
"""

from __future__ import annotations

import math
from statistics import median

from services import engine as _engine

# ─── Edwards' zones ──────────────────────────────────────────────────────────

# Lower bound of each zone as a fraction of HRmax. Anything under Z1's floor
# contributes no load at all — at <50% HRmax the athlete is at or near rest.
ZONE_LOWER_PCT: dict[int, float] = {1: 0.50, 2: 0.60, 3: 0.70, 4: 0.80, 5: 0.90}

# Edwards' linear zone weights.
ZONE_WEIGHTS: dict[int, int] = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}

# ─── Strain source labels (surfaced in the UI so a fallback is visible) ──────

SOURCE_HR = "hr"            # matched Garmin activity, HR-derived only
SOURCE_BLENDED = "blended"  # matched activity AND an RPE rating — the normal case
SOURCE_RPE = "rpe"          # no matched activity — the pre-existing behaviour
SOURCE_NONE = "none"        # nothing logged at all

SOURCE_LABELS: dict[str, str] = {
    SOURCE_HR: "Garmin HR",
    SOURCE_BLENDED: "Garmin HR + RPE",
    SOURCE_RPE: "RPE only (no Garmin activity)",
    SOURCE_NONE: "No session logged",
}

# How much the HR-derived value counts for when both signals exist. HR is
# weighted higher as the objective measurement; RPE is kept in the blend
# rather than dropped because it carries real information HR cannot see —
# perceived effort reflects mechanical/neural load, and heavy low-rep lifting
# can be genuinely hard while barely moving heart rate.
HR_BLEND_WEIGHT: float = 0.70

# A sample gap longer than this (seconds) is treated as a recording dropout
# and contributes only this much time, rather than crediting the whole gap at
# the preceding sample's intensity.
MAX_SAMPLE_GAP_SECONDS: float = 10.0

# Physiologically implausible readings — strap dropouts and contact glitches
# routinely emit 0 or spikes north of 230.
HR_PLAUSIBLE_MIN: float = 30.0
HR_PLAUSIBLE_MAX: float = 230.0

# Floor for a believable observed HRmax; below this, treat the observation as
# unusable rather than silently producing absurdly low zone boundaries.
HR_MAX_PLAUSIBLE_MIN: float = 120.0


def zone_for_hr(hr: float, hr_max: float) -> int | None:
    """Edwards' zone (1-5) for one heart-rate reading, or None when the
    reading is below Z1's floor (no load) or not physiologically plausible."""
    if hr_max <= 0 or not (HR_PLAUSIBLE_MIN <= hr <= HR_PLAUSIBLE_MAX):
        return None
    pct = hr / hr_max
    for z in (5, 4, 3, 2, 1):
        if pct >= ZONE_LOWER_PCT[z]:
            return z
    return None


def seconds_in_zone_from_samples(
    samples: list[tuple[float, float]], hr_max: float,
) -> dict[int, float]:
    """Bucket an HR time series into seconds per Edwards' zone.

    `samples`: (epoch_seconds, bpm) pairs, any order — sorted here. Each
    sample is credited with the time until the NEXT sample (the last one gets
    the series' median interval, since there's nothing after it to measure
    against). Gaps beyond MAX_SAMPLE_GAP_SECONDS are clamped: a watch that
    stopped recording for four minutes must not credit four minutes at
    whatever intensity preceded the dropout.

    Zones with no time in them are omitted rather than present as 0.0.
    """
    if not samples or hr_max <= 0:
        return {}

    ordered = sorted(samples, key=lambda s: s[0])
    if len(ordered) == 1:
        z = zone_for_hr(ordered[0][1], hr_max)
        return {z: MAX_SAMPLE_GAP_SECONDS} if z else {}

    deltas = [b[0] - a[0] for a, b in zip(ordered, ordered[1:]) if b[0] > a[0]]
    tail = min(median(deltas), MAX_SAMPLE_GAP_SECONDS) if deltas else MAX_SAMPLE_GAP_SECONDS

    out: dict[int, float] = {}
    for i, (ts, hr) in enumerate(ordered):
        span = tail if i == len(ordered) - 1 else min(
            max(0.0, ordered[i + 1][0] - ts), MAX_SAMPLE_GAP_SECONDS
        )
        z = zone_for_hr(hr, hr_max)
        if z is not None and span > 0:
            out[z] = out.get(z, 0.0) + span
    return out


def seconds_in_zone_from_garmin_zones(zone_rows: list[dict]) -> dict[int, float]:
    """Fallback path: adapt Garmin's own pre-bucketed per-activity zone
    summary (get_activity_hr_in_timezones) when the full sample series isn't
    available.

    Less trustworthy than seconds_in_zone_from_samples because the boundaries
    are whatever the Garmin account is configured with rather than the
    observed HRmax used everywhere else here — callers should prefer samples
    and record which path produced a figure.

    Accepts the raw rows and tolerates the key spellings garminconnect has
    used ("secsInZone"/"secsInZones", "zoneNumber"/"zoneNumer" — Garmin's own
    payload has shipped that typo).
    """
    out: dict[int, float] = {}
    for row in zone_rows or []:
        zone = row.get("zoneNumber", row.get("zoneNumer"))
        secs = row.get("secsInZone", row.get("secsInZones"))
        try:
            zone_i, secs_f = int(zone), float(secs)
        except (TypeError, ValueError):
            continue
        if zone_i in ZONE_WEIGHTS and secs_f > 0:
            out[zone_i] = out.get(zone_i, 0.0) + secs_f
    return out


def edwards_load(seconds_in_zone: dict[int, float]) -> float:
    """Edwards' summated heart-rate-zone load: Σ (minutes in zone × weight).

    Units are "zone-weighted minutes" — a 60-minute session held entirely in
    zone 5 scores 300, which is the practical ceiling for a single session.
    """
    total = 0.0
    for zone, seconds in (seconds_in_zone or {}).items():
        weight = ZONE_WEIGHTS.get(zone)
        if weight and seconds > 0:
            total += (seconds / 60.0) * weight
    return round(total, 1)


def banister_trimp(
    avg_hr: float | None, hr_rest: float | None, hr_max: float | None,
    duration_minutes: float, male: bool = True,
) -> float | None:
    """Banister TRIMP — a cross-check figure, NOT what strain derives from.

        TRIMP = duration × ΔHR × 0.64·e^(1.92·ΔHR)      (male)
                                 0.86·e^(1.67·ΔHR)      (female)
        ΔHR   = (HRavg − HRrest) / (HRmax − HRrest)      [heart-rate reserve]

    Reported alongside Edwards' load so the two can be compared over time; if
    they ever diverge sharply it usually means the session was unusually
    interval-heavy (which is precisely the case Edwards' handles and this
    doesn't — see the module docstring).

    None when any input is missing or the heart-rate reserve is degenerate.
    """
    if avg_hr is None or hr_rest is None or hr_max is None or duration_minutes <= 0:
        return None
    reserve = hr_max - hr_rest
    if reserve <= 0:
        return None
    frac = (avg_hr - hr_rest) / reserve
    if frac <= 0:
        return 0.0
    frac = min(frac, 1.0)
    coeff, exponent = (0.64, 1.92) if male else (0.86, 1.67)
    return round(duration_minutes * frac * coeff * math.exp(exponent * frac), 1)


def hr_strain(load: float) -> float:
    """Edwards' load → the same 0-21 strain curve Foster AU uses.

    No stage CLF is applied, deliberately — see the module docstring's
    calibration note.
    """
    return _engine.load_to_strain(load)


def blend_strain(
    hr_value: float | None, rpe_value: float | None,
    hr_weight: float = HR_BLEND_WEIGHT,
) -> tuple[float | None, str]:
    """Combine the two strain estimates into (value, source_label).

    Both present  → weighted mean, HR weighted at `hr_weight`  → SOURCE_BLENDED
    HR only       → the HR value                               → SOURCE_HR
    RPE only      → the RPE value (the pre-existing behaviour) → SOURCE_RPE
    Neither       → (None, SOURCE_NONE)

    The fallback chain is the point of this function: a session with no
    matched Garmin activity must still produce exactly the number it would
    have produced before any of this existed.
    """
    if hr_value is not None and rpe_value is not None:
        w = min(max(hr_weight, 0.0), 1.0)
        return round(hr_value * w + rpe_value * (1.0 - w), 1), SOURCE_BLENDED
    if hr_value is not None:
        return round(hr_value, 1), SOURCE_HR
    if rpe_value is not None:
        return round(rpe_value, 1), SOURCE_RPE
    return None, SOURCE_NONE


def estimate_hr_max(observed_max_hrs: list[float | None]) -> float | None:
    """Highest plausible HR ever observed, used as HRmax for zone boundaries.

    Observed-max rather than an age formula (220−age, Tanaka) because no date
    of birth is recorded anywhere in this system, and because a measured
    personal maximum beats a population regression with a ±10-12 bpm standard
    error in any case.

    Known bias: this UNDER-estimates until a genuinely maximal effort has been
    recorded, which compresses the zone boundaries downward and therefore
    over-states load. It self-corrects upward as harder sessions land. Callers
    should treat early figures as provisional.
    """
    plausible = [
        float(h) for h in (observed_max_hrs or [])
        if h is not None and HR_MAX_PLAUSIBLE_MIN <= float(h) <= HR_PLAUSIBLE_MAX
    ]
    return max(plausible) if plausible else None


# ─── HR-derived RPE, per exercise ────────────────────────────────────────────
#
# WHAT THIS IS AND IS NOT. This produces a CARDIOVASCULAR RPE: how hard an
# exercise was metabolically. It is NOT a substitute for the athlete's own
# set RPE, which measures proximity to failure, and the two genuinely differ.
# A heavy triple at RPE 9 barely moves heart rate; a lighter set taken close
# to failure with short rests pins it. Both numbers are real and they answer
# different questions -- which is exactly why HR_BLEND_WEIGHT above keeps RPE
# in the strain blend rather than replacing it with HR.
#
# The 2026-08-06 session is the worked example. Lat Pulldown and Single-Arm
# DB Row peaked higher (159, 163) than a heavier Hip Thrust (149), and the
# athlete's own explanation is the correct one: he works closer to true max
# on the pulls he trusts, the single-arm row is right-then-left inside one
# logged set with a single minute of rest after BOTH sides, and the pulls
# come later when fatigue has accumulated. Relative effort and rest density
# drive heart rate. Absolute load does not.
#
# BASIS: %HRR (Karvonen), not %HRmax. Heart-rate reserve subtracts resting
# HR, so it measures how far into the athlete's OWN usable range a reading
# sits. At a resting HR near 50 the two disagree by roughly 15 points at the
# bottom of the range, which is the difference between "easy" and "moderate".
# The Edwards zones above deliberately stay on %HRmax -- they implement a
# published formula and must not be redefined -- so this is an addition
# beside them, never a replacement.

# %HRR -> RPE anchors, CR-10. From the ACSM intensity bands: <30% very light,
# 30-39% light, 40-59% moderate, 60-89% vigorous, >=90% near-maximal.
# Interpolated linearly between anchors rather than stepped, so a one-bpm
# change never jumps an RPE point.
_HRR_RPE_ANCHORS: tuple[tuple[float, float], ...] = (
    (0.00, 0.0), (0.30, 2.0), (0.40, 3.0), (0.60, 5.0),
    (0.75, 7.0), (0.90, 9.0), (1.00, 10.0),
)


def hr_reserve_fraction(hr: float, hr_rest: float, hr_max: float) -> float | None:
    """(HR - rest) / (max - rest), clamped to 0..1. None when the inputs
    cannot support the calculation -- an implausible reading, or a reserve
    that is zero or inverted because hr_max was never properly observed."""
    if hr is None or hr_rest is None or hr_max is None:
        return None
    if not (HR_PLAUSIBLE_MIN <= hr <= HR_PLAUSIBLE_MAX):
        return None
    reserve = float(hr_max) - float(hr_rest)
    if reserve <= 0:
        return None
    return max(0.0, min(1.0, (float(hr) - float(hr_rest)) / reserve))


def rpe_from_hr_reserve(hrr: float | None) -> float | None:
    """CR-10 RPE for a heart-rate-reserve fraction, linearly interpolated
    between the ACSM anchors. Returns None for None, so a missing reading
    stays missing rather than becoming a confident 0."""
    if hrr is None:
        return None
    x = max(0.0, min(1.0, float(hrr)))
    pts = _HRR_RPE_ANCHORS
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            span = x1 - x0
            return round(y0 + (y1 - y0) * ((x - x0) / span if span else 0.0), 1)
    return float(pts[-1][1])


def exercise_hr_rpe(
    working_hrs: list[float], hr_rest: float | None, hr_max: float | None,
    peak_hr: float | None = None, peak_weight: float = 0.5,
) -> dict:
    """HR-derived RPE for ONE exercise, from the heart-rate samples recorded
    during its working sets.

    Blends the exercise's MEAN working HR with its PEAK, because neither
    alone describes a set. Mean alone under-rates a true top set that is over
    in fifteen seconds; peak alone over-rates an exercise whose single
    highest reading came during a transition. peak_weight is the peak's share.

    Returns mean/peak HR, their reserve fractions, the blended RPE, and
    `confident` -- False when hr_max is not trustworthy, which callers should
    surface rather than silently presenting a number. estimate_hr_max's own
    docstring is the reason: an observed max UNDER-estimates until a maximal
    effort has actually been recorded, which inflates every intensity derived
    from it. On 2026-08-06 the session's own peak WAS the observed max, so
    every reading that day sits against a ceiling the athlete has probably
    not truly reached.
    """
    samples = [
        float(h) for h in (working_hrs or [])
        if h is not None and HR_PLAUSIBLE_MIN <= float(h) <= HR_PLAUSIBLE_MAX
    ]
    if not samples or hr_rest is None or hr_max is None:
        return {"mean_hr": None, "peak_hr": None, "mean_hrr": None,
                "peak_hrr": None, "rpe": None, "confident": False,
                "sample_count": len(samples)}
    mean_hr = sum(samples) / len(samples)
    pk = float(peak_hr) if peak_hr is not None else max(samples)
    mean_hrr = hr_reserve_fraction(mean_hr, hr_rest, hr_max)
    peak_hrr = hr_reserve_fraction(pk, hr_rest, hr_max)
    w = min(max(peak_weight, 0.0), 1.0)
    parts = [v for v in (mean_hrr, peak_hrr) if v is not None]
    blended = (
        (peak_hrr * w + mean_hrr * (1.0 - w))
        if (mean_hrr is not None and peak_hrr is not None)
        else (parts[0] if parts else None)
    )
    return {
        "mean_hr": round(mean_hr, 1),
        "peak_hr": round(pk, 1),
        "mean_hrr": round(mean_hrr, 3) if mean_hrr is not None else None,
        "peak_hrr": round(peak_hrr, 3) if peak_hrr is not None else None,
        "rpe": rpe_from_hr_reserve(blended),
        "confident": bool(hr_max and hr_max > HR_MAX_PLAUSIBLE_MIN and pk < hr_max),
        "sample_count": len(samples),
    }


def covered_seconds(samples: list[tuple[float, float]]) -> float:
    """Seconds of REAL recording in a sample series — pauses excluded.

    This is the pause-handling primitive, and it is why the session AU below
    is not simply RPE x wall-clock. A Garmin workout can be paused mid-session
    (a phone call, a queue for the rack, a set moved to another machine) and
    resumed. Wall clock keeps running; the recording does not. Crediting the
    gap would inflate AU by exactly the time the athlete spent NOT training,
    and would do so invisibly.

    Each sample is credited with the interval to the next one, clamped to
    MAX_SAMPLE_GAP_SECONDS — the same rule seconds_in_zone_from_samples
    applies, so covered time and zone time can never disagree. A four-minute
    pause therefore contributes ten seconds, not four minutes.
    """
    ordered = sorted(samples or [], key=lambda s: s[0])
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return MAX_SAMPLE_GAP_SECONDS
    deltas = [b[0] - a[0] for a, b in zip(ordered, ordered[1:]) if b[0] > a[0]]
    tail = min(median(deltas), MAX_SAMPLE_GAP_SECONDS) if deltas else MAX_SAMPLE_GAP_SECONDS
    total = sum(
        min(max(0.0, ordered[i + 1][0] - ts), MAX_SAMPLE_GAP_SECONDS)
        for i, (ts, _) in enumerate(ordered[:-1])
    )
    return round(total + tail, 1)


def session_hr_rpe(
    blocks: list[dict], hr_rest: float | None, hr_max: float | None,
    session_minutes: float = 0.0,
) -> dict:
    """Session-level HR-derived RPE and AU, aggregated from per-exercise blocks.

    `blocks`: [{"name": str, "samples": [(epoch, bpm), ...]}] — one per
    exercise, built by hr_matching.exercise_blocks + samples_for_block, so a
    block only ever contains samples whose timestamps actually fall inside
    that exercise. Nothing is inferred from ordering or assumed to be
    contiguous: an exercise performed while the watch was paused simply has
    no samples and is reported as uncovered rather than estimated.

    The session RPE is the ACTIVE-TIME-WEIGHTED mean of the per-exercise
    RPEs, not a plain average. A three-minute Pallof hold and a
    twelve-minute pulldown block must not count equally, and weighting by
    covered seconds rather than by set count also stops a paused block from
    pulling the session figure toward an intensity that was never recorded.

    AU follows Foster's form -- RPE x minutes -- so it is directly comparable
    with the self-reported AU, but on ACTIVE minutes only.

    `coverage` is the fraction of the session's block time that carries real
    samples, and is the number to look at before trusting the rest: a session
    where the watch was stopped halfway produces a perfectly plausible AU
    from half a session unless coverage is checked.
    """
    per_ex, weighted, total_active = [], 0.0, 0.0
    for b in blocks or []:
        samples = b.get("samples") or []
        active = covered_seconds(samples)
        res = exercise_hr_rpe([hr for _, hr in samples], hr_rest, hr_max)
        res["name"] = b.get("name")
        res["active_seconds"] = active
        per_ex.append(res)
        if res["rpe"] is not None and active > 0:
            weighted += res["rpe"] * active
            total_active += active

    span = 0.0
    for b in blocks or []:
        s = sorted(b.get("samples") or [], key=lambda x: x[0])
        if len(s) >= 2:
            span += s[-1][0] - s[0][0]

    rpe = round(weighted / total_active, 1) if total_active > 0 else None
    active_minutes = round(total_active / 60.0, 1)
    # Clamped: covered_seconds credits the final sample a tail interval that
    # the raw first-to-last span does not contain, so an unbroken block can
    # compute marginally over 1.0. Coverage is a fraction by definition.
    coverage = min(1.0, total_active / span) if span > 0 else (1.0 if total_active else 0.0)
    return {
        "exercises": per_ex,
        "session_rpe": rpe,
        "active_minutes": active_minutes,
        # TWO AU figures, because they answer different questions and
        # conflating them would misreport the session either way.
        #
        # au_active = RPE x RECORDED WORK minutes. Excludes rests between
        # exercises and any stretch the watch was paused for. The honest
        # measure of work actually done, and NOT comparable with the stored
        # Foster AU, which counts the whole session.
        #
        # au_session = RPE x TOTAL session minutes — Foster's own basis, so
        # it can sit directly beside the self-reported AU and be compared
        # like for like. This is the one that answers "what would the AU
        # have been with a measured RPE instead of a guessed one".
        "au_active": round(rpe * active_minutes, 1) if rpe is not None else None,
        "au_session": (round(rpe * session_minutes, 1)
                       if rpe is not None and session_minutes > 0 else None),
        "coverage": round(coverage, 3),
        "covered_exercises": sum(1 for e in per_ex if e["rpe"] is not None),
        "total_exercises": len(per_ex),
    }


def session_hr_summary(
    seconds_in_zone: dict[int, float], avg_hr: float | None = None,
    max_hr: float | None = None, hr_rest: float | None = None,
    hr_max: float | None = None, duration_minutes: float = 0.0,
) -> dict:
    """Everything derived from one session's heart-rate record, in one dict:
    Edwards' load and its strain, the Banister cross-check, per-zone minutes,
    and the avg/max the caller supplied. Shape is stable so it can be
    persisted and re-read without recomputation."""
    load = edwards_load(seconds_in_zone)
    return {
        "edwards_load": load,
        "hr_strain": hr_strain(load),
        "banister_trimp": banister_trimp(
            avg_hr, hr_rest, hr_max, duration_minutes,
        ),
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "hr_max_used": hr_max,
        "zone_minutes": {
            z: round(s / 60.0, 1) for z, s in sorted((seconds_in_zone or {}).items())
        },
        "total_minutes": round(sum((seconds_in_zone or {}).values()) / 60.0, 1),
    }
