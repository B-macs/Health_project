"""
services/sleep_score.py — Deterministic Sleep Score: Oura's own seven sleep
contributors (each 0-100, from Oura's daily sleep summary — total_sleep,
efficiency, restfulness, rem_sleep, deep_sleep, latency, timing; see
services/repository.py's _oura_readiness_contributors_by_date) combined with
this project's weights. The same shape as services/readiness.py since its
MODEL_VERSION 2: Oura scores each part against its own norms, this project
decides what each part is worth.

MODEL_VERSION 3 (2026-10-27, the athlete's choice of three measured options:
"rebuild the Sleep score on Oura's seven sleep parts with our weights, keep the
watch correction out of the score"). Version 2 scored the parts itself from the
raw night and read a short night far above both devices: 2026-10-27 read 91
against Oura's 63 and Garmin's 62, and over the 55 stored nights from
2026-08-28 it read 11 points above Oura on average (up to 23) and 25 above
Garmin; Oura scored 25 of those nights under 70, version 2 only 9. Three
causes, measured that morning:
  - Total Sleep was scored against his own 56-night average (6.9 h), where Oura
    scores against a fixed adult target: 5.85 h read 85 against Oura's 56.
  - REM and Deep were scored as a SHARE of the night, so a short night of normal
    proportions read 94 and 100 against Oura's 62 and 61; Efficiency was the
    plain percent (73 against Oura's 55).
  - The wake-time correction (the watch fusion's phantom wake, or the manual
    stepper) was added to Total Sleep and Efficiency: that night's 58 min moved
    85 to 91, and it lifted 23 of the 30 nights before it, by 1.7 on average.
NO CORRECTION REACHES THE SCORE NOW. Oura's parts are Oura's reading of its own
night, and a correction cannot be applied to a part Oura already scored. The
correction stays on the Sleep screen's night figures
(dashboard.sleep_night_figures), which say so.

MEASURED 2026-10-27 against Oura's own Sleep Score, on the 112 nights from
2026-07-01 to 2026-10-27 that carry one: r = 0.982, mean difference -0.8, sd
1.9, every night within 5 points (largest 4.5). 2026-10-27 reads 62.4 against
Oura's 63. Oura scored 26 of the 56 nights from 2026-08-28 under 70, and
version 3 reads all 26 under 70 (version 2: 9). The weights are this
project's, so the two still differ by a point or two where the parts disagree.

Earlier versions: 2 (2026-10-13) changed Restfulness alone to Oura's own
contributor, because the raw restless-period band of version 1 scored 0 on 426
of 427 nights (docs/restfulness_and_watch_movement_2026-10-13.md). Version 1
built all seven parts from the raw night. Every model change ships with a
re-derive of every stored row (MODEL_VERSION).

Weights (this project's; Oura does not publish its own)
-------
Total Sleep   25%
Efficiency    20%
REM Sleep     15%
Deep Sleep    15%
Restfulness   10%
Latency       10%
Timing         5%

NO RING, NO SCORE: a night the ring did not record is NOT_COMPUTED (WP-11). A
part Oura did not report is missing, and its weight renormalises away.

The breakdown still carries each part's RAW reading from Oura's own night
(hours asleep, efficiency %, REM/deep share, minutes to sleep, minutes off the
usual bedtime) for the screen's right-hand value. Nothing scores from it.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from services import readiness

NOT_COMPUTED = readiness.NOT_COMPUTED

_BEDTIME_WINDOWS = (7, 14, 28, 56)   # same progressive schedule as sleep_baseline

#: Which Sleep Score model produced a number. 3 (2026-10-27): every part is
#: Oura's own contributor and no wake-time correction reaches the score. 2
#: (2026-10-13): Restfulness alone was Oura's. Not stored per row — the
#: Supabase metrics_history table has no version column (readiness's stamp
#: reaches only the frozen Sheets copy) — so a change of model ships with a
#: re-derive of EVERY stored row, which keeps the stored series one version
#: throughout.
MODEL_VERSION = 3

_WEIGHTS = {
    "total_sleep": 0.25,
    "efficiency":  0.20,
    "rem":         0.15,
    "deep":        0.15,
    "restfulness": 0.10,
    "latency":     0.10,
    "timing":      0.05,
}

#: Each part -> the BiometricRecord field holding Oura's own 0-100 contributor.
OURA_PARTS = {
    "total_sleep": "oura_sleep_total_sleep_score",
    "efficiency":  "oura_sleep_efficiency_score",
    "restfulness": "oura_sleep_restfulness",
    "rem":         "oura_sleep_rem_score",
    "deep":        "oura_sleep_deep_score",
    "latency":     "oura_sleep_latency_score",
    "timing":      "oura_sleep_timing_score",
}

# Display order for the breakdown — Oura's own ordering on its sleep screen,
# which is not weight order. Deliberate: the UI should read the way the user's
# other sleep app reads, and weight is disclosed in the coverage caption
# rather than per row.
CONTRIBUTOR_ORDER = (
    "total_sleep", "efficiency", "restfulness", "rem", "deep", "latency", "timing",
)
CONTRIBUTOR_LABELS = {
    "total_sleep": "Total sleep",
    "efficiency":  "Efficiency",
    "restfulness": "Restfulness",
    "rem":         "REM sleep",
    "deep":        "Deep sleep",
    "latency":     "Latency",
    "timing":      "Timing",
}


def _interp(value: float, points: tuple[tuple[float, float], ...]) -> float:
    """Piecewise-linear interpolation over sorted (x, y) knots; clamps to
    the nearest endpoint's y outside the knots' x-range. No part scores with
    it since MODEL_VERSION 3; scripts/compare_restfulness_sources.py still
    re-runs version 1's restfulness band with it."""
    if value <= points[0][0]:
        return points[0][1]
    if value >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= value <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return points[-1][1]  # unreachable given the bounds checks above


def _bedtime_minutes_since_noon(bedtime_start: str | None) -> float | None:
    """Expresses a bedtime as minutes since noon on the evening it belongs
    to, so realistic bedtimes (evening through the following early morning)
    increase monotonically with no midnight-wraparound discontinuity — e.g.
    11:15 PM -> 675, 1:00 AM the same night -> 780."""
    if not bedtime_start:
        return None
    try:
        bedtime = datetime.fromisoformat(bedtime_start)
    except ValueError:
        return None
    anchor_date = bedtime.date() if bedtime.hour >= 12 else bedtime.date() - timedelta(days=1)
    anchor = datetime.combine(anchor_date, time(12, 0), tzinfo=bedtime.tzinfo)
    return (bedtime - anchor).total_seconds() / 60.0


def bedtime_baseline(rows: list[dict]) -> tuple[float | None, int]:
    """Progressive personal bedtime baseline (minutes since noon — see
    _bedtime_minutes_since_noon), same 7->14->28->56-night schedule as
    services.readiness.sleep_baseline. Returns (baseline_minutes,
    window_nights_used) — (None, 0) when insufficient data. Feeds the Timing
    row's "minutes off usual", not the score."""
    clean = [
        m for r in rows
        for m in [_bedtime_minutes_since_noon(r.get("oura_sleep_bedtime_start"))]
        if m is not None
    ]
    n = len(clean)
    for window in reversed(_BEDTIME_WINDOWS):
        if n >= window:
            return round(sum(clean[-window:]) / window, 1), window
    return None, 0


def compute_sleep_score(
    for_date: date | None = None,
    bio_rows: list[dict] | None = None,
) -> float | str:
    """
    Compute a 0-100 Sleep Score for for_date: the weighted mean of Oura's
    seven sleep contributors on that night (see the module docstring).

    No wake-time correction is a parameter any more (MODEL_VERSION 3): the
    correction belongs to the night figures, never to the score.

    Returns:
        float        — sleep score 0-100
        NOT_COMPUTED — the ring did not record the night, or Oura reported
                       none of the seven parts
    """
    scored = _contributor_scores(for_date, bio_rows)
    if scored is None:
        return NOT_COMPUTED
    return _composite([
        (c["score"], c["weight"]) for c in scored["contributors"].values()
        if c["score"] is not None
    ])


def _composite(available: list[tuple[float, float]]) -> float | str:
    """Weighted mean of the contributors that could be scored, with the
    missing ones' weights renormalised away.

    The expression below is deliberately `sum(s * (w / total_w))` and NOT the
    algebraically-equal `sum(s * w) / total_w`. Those differ in IEEE 754, and
    the round(..., 1) at the end occasionally exposes the difference — which
    would silently move a user-visible score. Moved verbatim out of
    compute_sleep_score; see the bit-identity tests in tests/test_sleep_score.py.
    """
    if not available:
        return NOT_COMPUTED
    total_w = sum(w for _, w in available)
    weighted_sum = sum(s * (w / total_w) for s, w in available)
    return round(weighted_sum, 1)


#: The ring's own readings of the night: the sleep period's raw fields, or
#: Oura's own parts. A row with none of them is a night the ring did not
#: record, whatever the watch saw.
_RING_SLEEP_FIELDS = (
    "oura_sleep_total_seconds", "oura_sleep_efficiency", "oura_sleep_rem_seconds",
    "oura_sleep_deep_seconds", "oura_sleep_restless_periods", "oura_sleep_latency_seconds",
) + tuple(OURA_PARTS.values())


def _has_ring_reading(row: dict | None) -> bool:
    return bool(row) and any(row.get(k) is not None for k in _RING_SLEEP_FIELDS)


def _contributor_scores(
    for_date: date | None,
    bio_rows: list[dict] | None,
) -> dict | None:
    """Every part's score (Oura's own), plus the raw reading the screen shows
    beside it. None when there is no usable row at all.

    Split out of compute_sleep_score so sleep_score_breakdown can show the
    seven contributors without that function's public float changing.
    """
    if not bio_rows:
        return None

    for_date = for_date or date.today()
    date_str = str(for_date)
    rows_to_date = [r for r in bio_rows if r.get("date") and r["date"] <= date_str]
    if not rows_to_date:
        return None

    today_row = next((r for r in rows_to_date if r["date"] == date_str), None)

    # NO RING, NO SCORE (2026-10-13, the athlete's approval of WP-11). A night
    # only the watch recorded has no Oura part to score; the Sleep screen keeps
    # its timeline and says there is no score.
    if not _has_ring_reading(today_row):
        return None

    def _get(key):
        if today_row is None or today_row.get(key) is None:
            return None
        return float(today_row[key])

    def _part(key):
        """Oura's own 0-100 reading for one part, kept inside 0-100."""
        value = _get(OURA_PARTS[key])
        return None if value is None else max(0.0, min(100.0, value))

    # The raw readings of Oura's own night, for the screen only — the
    # uncorrected night the parts were scored on.
    total_s = _get("oura_sleep_total_seconds")
    rem_raw = _get("oura_sleep_rem_seconds")
    deep_raw = _get("oura_sleep_deep_seconds")
    latency_raw = _get("oura_sleep_latency_seconds")
    restless_raw = _get("oura_sleep_restless_periods")
    rem_pct = rem_raw / total_s * 100.0 if rem_raw is not None and total_s else None
    deep_pct = deep_raw / total_s * 100.0 if deep_raw is not None and total_s else None
    bedtime_base, bed_window = bedtime_baseline(rows_to_date)
    today_bedtime = _bedtime_minutes_since_noon(today_row.get("oura_sleep_bedtime_start"))
    off_usual = (abs(today_bedtime - bedtime_base)
                 if today_bedtime is not None and bedtime_base is not None else None)

    # (score, raw, reference, reference_window): reference is what a raw
    # reading is shown against, where it has one.
    built = {
        "total_sleep": (_part("total_sleep"), total_s / 3600.0 if total_s else None, None, 0),
        "efficiency":  (_part("efficiency"), _get("oura_sleep_efficiency"), None, 0),
        "restfulness": (_part("restfulness"),
                        restless_raw / (total_s / 3600.0)
                        if restless_raw is not None and total_s else None, None, 0),
        "rem":         (_part("rem"), rem_pct, None, 0),
        "deep":        (_part("deep"), deep_pct, None, 0),
        "latency":     (_part("latency"),
                        latency_raw / 60.0 if latency_raw is not None else None, None, 0),
        "timing":      (_part("timing"), off_usual,
                        bedtime_base if off_usual is not None else None,
                        bed_window if off_usual is not None else 0),
    }
    if all(v[0] is None for v in built.values()):
        return None

    contributors = {
        key: {
            "key": key,
            "label": CONTRIBUTOR_LABELS[key],
            "score": built[key][0],
            "weight": _WEIGHTS[key],
            "raw": built[key][1],
            "reference": built[key][2],
            "reference_window": built[key][3],
        }
        for key in CONTRIBUTOR_ORDER
    }
    return {"contributors": contributors, "total_seconds": total_s}


def sleep_score_breakdown(
    for_date: date | None = None,
    bio_rows: list[dict] | None = None,
) -> dict:
    """The composite plus the seven sub-scores that produced it.

    `score` is identical to compute_sleep_score(...) for the same inputs —
    both go through _composite over the same contributor set. Exists because
    services/dashboard.py::sleep_meta's own copy has always told the user to
    "check the breakdown for what's holding it back", while no breakdown was
    exposed anywhere.

    Contributors are always all seven, in CONTRIBUTOR_ORDER, so the UI can
    show what is MISSING as readily as what scored. A contributor that could
    not be computed has score None and effective_weight 0.0 — it cannot
    silently contribute.

    `contribution` is that contributor's share of the composite after
    renormalisation. The contributions will not sum exactly to `score` (the
    composite is rounded once, the parts are not), so present it as a
    contribution, never as exact arithmetic.
    """
    scored = _contributor_scores(for_date, bio_rows)
    if scored is None:
        return {
            "score": NOT_COMPUTED,
            "contributors": [
                {"key": k, "label": CONTRIBUTOR_LABELS[k], "score": None,
                 "weight": _WEIGHTS[k], "effective_weight": 0.0, "contribution": None,
                 "raw": None, "reference": None, "reference_window": 0}
                for k in CONTRIBUTOR_ORDER
            ],
            "available_weight": 0.0,
            "missing": list(CONTRIBUTOR_ORDER),
        }

    by_key = scored["contributors"]
    available = [(c["score"], c["weight"]) for c in by_key.values() if c["score"] is not None]
    total_w = sum(w for _, w in available) or 1.0

    contributors = []
    for key in CONTRIBUTOR_ORDER:
        c = by_key[key]
        scored_ok = c["score"] is not None
        eff = (c["weight"] / total_w) if scored_ok else 0.0
        contributors.append({
            **c,
            "effective_weight": round(eff, 4),
            "contribution": round(c["score"] * eff, 2) if scored_ok else None,
        })

    return {
        "score": _composite(available),
        "contributors": contributors,
        "available_weight": round(sum(w for _, w in available), 4),
        "missing": [c["key"] for c in contributors if c["score"] is None],
        # Lets a formatter turn REM/deep's percentage back into a duration
        # ("1h 24m, 23 %") without re-reading the row and risking a different
        # rounding than the one the score used.
        "total_seconds": scored["total_seconds"],
    }
