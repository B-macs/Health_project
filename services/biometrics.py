"""
services/biometrics.py — DETERMINISTIC. Pure Oura+Garmin blending math, no
I/O, no Streamlit — same convention as readiness.py/stats.py. Column names
and raw JSON extraction stay in services/repository.py; this module only
ever sees already-extracted plain dicts keyed by engine field name
(hrv_ms, resting_heart_rate, sleep_duration_hours, steps).

Replaces Sheet1/Apple Health as the engine's live biometric source. Weights
below were chosen because Oura's official API is the more consistently
reliable of the two for recovery/sleep, while Garmin's on-wrist step
counting is more consistent than Oura's ring-based estimate. Fallback: if
one platform is missing a metric for a day, use 100% of the other rather
than dropping the day — `sources_missing` records which metric/source pairs
that happened for, so the UI can flag it without the deterministic math
itself ever branching on it.
"""

from __future__ import annotations

from datetime import datetime

from services import models

OURA_WEIGHT_RECOVERY_SLEEP = 0.70
GARMIN_WEIGHT_RECOVERY_SLEEP = 0.30
GARMIN_WEIGHT_STEPS = 0.80
OURA_WEIGHT_STEPS = 0.20

# (engine field name, oura weight, garmin weight)
_BLEND_FIELDS = (
    ("hrv_ms", OURA_WEIGHT_RECOVERY_SLEEP, GARMIN_WEIGHT_RECOVERY_SLEEP),
    ("resting_heart_rate", OURA_WEIGHT_RECOVERY_SLEEP, GARMIN_WEIGHT_RECOVERY_SLEEP),
    ("sleep_duration_hours", OURA_WEIGHT_RECOVERY_SLEEP, GARMIN_WEIGHT_RECOVERY_SLEEP),
    ("steps", OURA_WEIGHT_STEPS, GARMIN_WEIGHT_STEPS),
)


# ─── HRV hold — Oura-only until the two devices are measured against each
#     other ──────────────────────────────────────────────────────────────────
#
# The 70/30 HRV weighting above has never actually run. Garmin's HRV endpoint
# returns {} for this account (the Forerunner 645 has no HRV Status), so every
# blended hrv_ms in the app's entire history is 100% Oura. The moment a watch
# that DOES support HRV starts syncing, that flips to a real 70/30 — and the
# HRV series feeding readiness.py's rolling baselines would step, on the day
# the hardware changed, for reasons that are not physiological.
#
# Wrist PPG and finger PPG do not agree on HRV, and there is no reason to
# expect them to: HRV is derived from beat-to-beat intervals, where a few ms
# of beat-detection error swamps RMSSD, and the finger has far better
# perfusion than the wrist. Whatever the offset turns out to be, it is a
# device artefact, and folding it into the baseline unmeasured would make
# every readiness score across the changeover incomparable with every one
# before it.
#
# So HRV holds at Oura-only until the offset is MEASURED on paired nights —
# the same discipline sleep_movement.MIN_CALIBRATION_NIGHTS uses for the
# Garmin movement cut points, and for the same reason: two devices, one
# scale, no ground truth, so calibrate before combining. hrv_agreement()
# below is what makes lifting the hold an act of evidence rather than
# optimism. Today this is a NO-OP -- Garmin supplies nothing -- which is
# exactly the point: it keeps today's behaviour through the upgrade.
#
# To lift: confirm hrv_agreement(...)["ready"], look at the bias, then set
# HRV_GARMIN_HOLD = False. Nothing else changes.
HRV_GARMIN_HOLD = True

# Floor before the paired-night bias means anything. Matches
# sleep_movement.MIN_CALIBRATION_NIGHTS -- same n=14 judgement, same
# situation.
MIN_HRV_PAIRED_NIGHTS = 14

# sources_missing marker for a night where Garmin HAD an HRV reading and the
# hold discarded it. Deliberately distinct from the plain "hrv_ms:garmin"
# (Garmin genuinely had nothing): "we chose not to use it" and "there was
# nothing to use" are different facts, and only the first one is a decision
# anyone might want to revisit.
HRV_HELD_FLAG = "hrv_ms:garmin_held"


def blend_metric(
    oura_val: float | None, garmin_val: float | None,
    oura_weight: float, garmin_weight: float,
) -> tuple[float | None, str | None]:
    """DETERMINISTIC. Weighted average of the two sources for one metric on
    one day. Fallback (no fabricated fallback value, just re-normalized
    weight): if exactly one side is missing, returns the other value as-is
    and names which source was missing (for the UI to flag as "pending").
    Returns (None, None) when both are missing — nothing to blend or flag."""
    if oura_val is None and garmin_val is None:
        return None, None
    if oura_val is None:
        return float(garmin_val), "oura"
    if garmin_val is None:
        return float(oura_val), "garmin"
    total = oura_weight + garmin_weight
    return (float(oura_val) * oura_weight + float(garmin_val) * garmin_weight) / total, None


def blend_hrv(oura_val: float | None, garmin_val: float | None) -> tuple[float | None, str | None]:
    """DETERMINISTIC. HRV's blend, which is the ordinary weighted one EXCEPT
    while HRV_GARMIN_HOLD is set — see that constant for why.

    Under the hold, HRV is Oura's or it is nothing. Note what that second
    half means: a night where only Garmin has HRV yields None rather than
    Garmin's number. That is deliberate and is the harder half of the rule.
    Substituting a wrist reading into a series whose baseline was built from
    finger readings is precisely the discontinuity the hold exists to
    prevent — it would be worse than a gap, because a gap is visible and a
    silently-rescaled value is not. readiness.py already handles a missing
    hrv_ms (it has had to, for every night of this app's history)."""
    if not HRV_GARMIN_HOLD or garmin_val is None:
        return blend_metric(
            oura_val, garmin_val,
            OURA_WEIGHT_RECOVERY_SLEEP, GARMIN_WEIGHT_RECOVERY_SLEEP,
        )
    return (float(oura_val) if oura_val is not None else None), HRV_HELD_FLAG


def hrv_agreement(paired: list[tuple[float, float]]) -> dict:
    """DETERMINISTIC. Bias between the two devices' HRV over nights where
    BOTH reported, as (oura_ms, garmin_ms) pairs. This is the measurement
    that lifts HRV_GARMIN_HOLD.

    `bias` is garmin - oura, in ms, signed: negative means Garmin reads
    lower, which is the direction wrist PPG usually errs and the direction
    that would quietly depress readiness after the changeover.

    Explicitly NOT an accuracy test. Neither device is ground truth — that
    would need ECG — so this cannot say which one is right. It says how far
    apart they are and how consistently, which is the only thing a blend
    actually needs to know. Same stance as the fusion module's agreement_pct
    and cohen_kappa: measured, shown, never mistaken for truth.

    `ready` is a floor on n, not a verdict: a stable bias over 14 nights is
    grounds to look, not grounds to assume. A large `sd` means the offset is
    not a constant and no single weighting will fix it."""
    pairs = [(float(o), float(g)) for o, g in paired
             if o is not None and g is not None]
    n = len(pairs)
    if not n:
        return {"n": 0, "ready": False, "mean_bias": None, "median_bias": None,
                "sd_bias": None, "mean_abs_bias": None,
                "min_nights": MIN_HRV_PAIRED_NIGHTS}
    biases = sorted(g - o for o, g in pairs)
    mean_bias = sum(biases) / n
    mid = n // 2
    median_bias = biases[mid] if n % 2 else (biases[mid - 1] + biases[mid]) / 2
    variance = sum((b - mean_bias) ** 2 for b in biases) / n
    return {
        "n": n,
        "ready": n >= MIN_HRV_PAIRED_NIGHTS,
        "mean_bias": round(mean_bias, 2),
        "median_bias": round(median_bias, 2),
        "sd_bias": round(variance ** 0.5, 2),
        "mean_abs_bias": round(sum(abs(b) for b in biases) / n, 2),
        "min_nights": MIN_HRV_PAIRED_NIGHTS,
    }


# ─── Sleep periods — the day's main night, and its naps ──────────────────────
#
# Oura reports 0-N sleep periods per day. Normally one is the night (typed
# "long_sleep"); the rest are naps, typed "sleep" (a period under 3 h) or
# "late_nap". Two properties of that list drive everything below, and both
# were measured against three years of this athlete's own history rather
# than assumed.
#
# 1. PERIODS CAN BE DUPLICATED. Eight nights in April 2024 carry the same
#    physical sleep twice under different sleep_ids — identical bedtime
#    window and time_in_bed, total_sleep_duration differing by a minute or
#    two, and one of each pair often carrying a sentinel lowest_heart_rate
#    of 255. Picking a single period hid this entirely; summing does not.
#    Un-deduplicated, 2024-04-19 reads 14.78 h of sleep instead of 7.42 h.
#    So overlapping windows collapse to their longest member BEFORE any
#    total is taken. This is also why the main-period pick below is written
#    as a max() rather than a first-match: it must not depend on the order
#    rows happen to sit in the sheet.
#
# 2. MOST NAPS ARE NOT NAPS. Of 57 non-main periods across the history,
#    more than half run 1-13 minutes at 2-38% efficiency — the ring
#    registering stillness, not sleep. Counting those would add 11 days of
#    movement for 2.8 h of "sleep". NAP_MIN_SECONDS is the floor that keeps
#    them out; at 15 minutes, 22 days move and 14.6 h of real napping is
#    recovered.
#
# The split this module draws is duration vs architecture, and it is the
# whole design. A nap adds to the day's total SLEEP TIME, which is what
# readiness, Sleep Debt and the Sleep Score's Total Sleep contributor read.
# It does not touch the night's ARCHITECTURE — efficiency, REM/deep shares,
# latency, restless periods, HRV and resting HR all stay main-period-only,
# because those describe one continuous sleep and a nap's own figures are
# both differently-shaped and (see the efficiency values above) frequently
# garbage. services/sleep_score.py depends on exactly this: it divides REM
# and deep seconds by oura_sleep_total_seconds, which must therefore remain
# the main night's total and never the day's.

NAP_MIN_SECONDS = 900


def _duration_seconds(entry: dict | None) -> float:
    """total_sleep_duration as a float, 0.0 when absent or unparseable."""
    if not entry:
        return 0.0
    try:
        return float(entry.get("total_sleep_duration") or 0)
    except (TypeError, ValueError):
        return 0.0


def _period_span(entry: dict) -> tuple[float, float] | None:
    """(start, end) as epoch seconds, or None when the period cannot be
    placed on a timeline — a missing, unparseable or timezone-naive bound.
    Unplaceable periods are never merged with anything: a wrong merge
    silently deletes real sleep, while a missed merge only leaves a
    duplicate that the nap floor and the main-period pick already tolerate.

    Epoch seconds rather than datetimes because Oura stamps each period in
    the local offset in force at the time (the same night appears as
    +01:00 and +02:00 across a DST change), and only an absolute instant
    compares correctly across those."""
    bounds = []
    for key in ("bedtime_start", "bedtime_end"):
        raw = str(entry.get(key) or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        bounds.append(parsed.timestamp())
    start, end = bounds
    return (start, end) if end > start else None


def dedupe_sleep_periods(entries: list[dict]) -> list[dict]:
    """DETERMINISTIC. Collapses periods whose bedtime windows overlap down to
    the longest member of each overlapping group — Oura's re-analysis of a
    night arrives as a second row rather than an update to the first (see
    this section's note 1). Idempotent, so it is safe to call on a list that
    has already been through it. Input order of the surviving periods is
    preserved."""
    groups: list[dict] = []
    for entry in entries:
        span = _period_span(entry)
        merged_into = None
        if span is not None:
            for group in groups:
                gs = group["span"]
                if gs is not None and span[0] < gs[1] and gs[0] < span[1]:
                    group["span"] = (min(gs[0], span[0]), max(gs[1], span[1]))
                    group["members"].append(entry)
                    merged_into = group
                    break
        if merged_into is None:
            groups.append({"span": span, "members": [entry]})
    return [max(g["members"], key=_duration_seconds) for g in groups]


def split_sleep_periods(
    entries: list[dict], nap_min_seconds: float = NAP_MIN_SECONDS,
) -> tuple[dict | None, list[dict]]:
    """DETERMINISTIC. (main sleep period, qualifying naps) for one day.

    The main period is the longest one typed "long_sleep", or — on the 11
    days in this history where Oura recorded no long_sleep at all, because
    the whole night ran under 3 h — simply the longest period there is.
    That fallback is why a nap-only day still reports a night rather than
    nothing. Naps are every other surviving period reaching
    `nap_min_seconds`; ordering is by when they started, so a caller can
    list them down the day.

    (None, []) when there are no periods."""
    unique = dedupe_sleep_periods(entries)
    if not unique:
        return None, []
    long_sleeps = [e for e in unique if e.get("type") == "long_sleep"]
    main = max(long_sleeps or unique, key=_duration_seconds)
    naps = [e for e in unique
            if e is not main and _duration_seconds(e) >= nap_min_seconds]
    naps.sort(key=lambda e: (_period_span(e) or (float("inf"), 0))[0])
    return main, naps


def day_total_sleep_seconds(main: dict | None, naps: list[dict]) -> float:
    """The day's total sleep — main night plus qualifying naps — in seconds.
    0.0 when there is nothing; callers turn that into None, matching how a
    zero-duration period has always been treated as no reading."""
    return _duration_seconds(main) + sum(_duration_seconds(n) for n in naps)


def pick_main_sleep_period(entries: list[dict]) -> dict | None:
    """DETERMINISTIC. The day's main sleep period — see split_sleep_periods,
    which this delegates to. Kept as its own name because the hypnogram and
    drill-down readers want only the night, never the naps."""
    return split_sleep_periods(entries)[0]


def blend_biometric_day(date_str: str, oura: dict, garmin: dict) -> models.BiometricRecord:
    """DETERMINISTIC. `oura`/`garmin` are plain dicts already mapped to engine
    field names (hrv_ms, resting_heart_rate, sleep_duration_hours, steps) —
    repository.py owns extracting those from each platform's raw JSON/sheet
    row. Builds one BiometricRecord for `date_str` with every blend field
    weighted per _BLEND_FIELDS, and sources_missing populated for any field
    where only one source had data."""
    values: dict[str, float | None] = {}
    missing: list[str] = []
    for field_name, oura_weight, garmin_weight in _BLEND_FIELDS:
        if field_name == "hrv_ms":
            # Routed through blend_hrv, not blend_metric — see HRV_GARMIN_HOLD.
            # Its flag is already fully-qualified, so it is appended as-is
            # rather than prefixed with the field name again.
            value, flag = blend_hrv(oura.get(field_name), garmin.get(field_name))
            values[field_name] = value
            if flag == HRV_HELD_FLAG:
                missing.append(flag)
            elif flag is not None:
                missing.append(f"{field_name}:{flag}")
            continue
        value, missing_source = blend_metric(
            oura.get(field_name), garmin.get(field_name), oura_weight, garmin_weight,
        )
        values[field_name] = value
        if missing_source is not None:
            missing.append(f"{field_name}:{missing_source}")

    steps = values["steps"]
    return models.BiometricRecord(
        date=date_str,
        hrv_ms=values["hrv_ms"],
        resting_heart_rate=values["resting_heart_rate"],
        sleep_duration_hours=values["sleep_duration_hours"],
        steps=int(round(steps)) if steps is not None else None,
        sources_missing=tuple(missing),
    )


def sheet1_row_to_garmin_daily_row(record: models.BiometricRecord) -> dict:
    """DETERMINISTIC. One-time-backfill mapping (scripts/backfill_garmin_from_
    sheet1.py): legacy Apple Health/Sheet1 fields -> the Garmin Daily sheet
    tab's row shape, so pre-wearable history still has *something* in the
    Garmin Daily tab for readiness.py's rolling baselines to find. Fields
    Sheet1 never captured (sleep_score, avg_stress, calories_total, min_hr,
    max_hr) are left as blank strings, matching how _garmin_daily_row leaves
    genuinely-missing Garmin fields blank."""
    return {
        "date": record.date,
        "steps": record.steps if record.steps is not None else "",
        "resting_hr": record.resting_heart_rate if record.resting_heart_rate is not None else "",
        "avg_stress": "",
        "sleep_score": "",
        "sleep_hours": record.sleep_duration_hours if record.sleep_duration_hours is not None else "",
        "calories_total": "",
        "min_hr": "",
        "max_hr": "",
        "hrv_ms": record.hrv_ms if record.hrv_ms is not None else "",
    }
