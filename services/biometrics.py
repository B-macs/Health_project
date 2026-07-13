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


def pick_main_sleep_period(entries: list[dict]) -> dict | None:
    """DETERMINISTIC. Oura returns 0-N sleep periods per day (naps + main
    sleep). Prefers the entry typed "long_sleep"; falls back to whichever
    entry has the longest total_sleep_duration if none is so typed (or
    multiple naps only). None if the list is empty."""
    if not entries:
        return None
    long_sleep = next((e for e in entries if e.get("type") == "long_sleep"), None)
    if long_sleep is not None:
        return long_sleep
    return max(entries, key=lambda e: e.get("total_sleep_duration") or 0)


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
