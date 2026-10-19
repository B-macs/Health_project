"""
services/insights.py — pure logic extracted from views/insights.py.

The Insights page mixed real computation (delta-arrow direction, chart
date-window construction that duplicated engine.acwr's acute/chronic split
concept ad-hoc, slope-to-direction sign interpretation that duplicated
stats.trend_slope's intent, body-region JSON aggregation) directly into
Streamlit rendering code. Pulled out here as pure, testable functions — see
REFACTOR_NOTES.md.

Chart/table rendering itself (st.bar_chart, st.dataframe, HTML card markup)
stays in the Streamlit layer.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from services import engine


def metric_delta_str(delta_pct: float | None) -> str:
    if not delta_pct:
        return ""
    arrow = "▲" if delta_pct > 0 else "▼"
    return f"{arrow} {abs(delta_pct):.1f}%"


# ─── Engine Data: the traffic light, its drift, and ACWR (moved 2026-10-19) ──

#: What a temperature reading's signal means, in words: it is scored against
#: fixed cut points, not a rolling baseline.
TEMPERATURE_WORDS = {"red": "Possible illness onset",
                     "yellow": "Elevated — re-check tomorrow",
                     "green": "Normal range"}


def metric_card(metric: dict) -> dict:
    """One traffic-light metric as the Engine Data card shows it: the value,
    the comparison line, the change line, and the signal that colours it.

    Temperature deviation is scored against fixed cut points, not a rolling
    baseline, so it says what it is compared with instead of "No baseline",
    which would read as missing data when it means this metric uses none."""
    val, unit = metric.get("value"), metric.get("unit", "")
    baseline, signal = metric.get("baseline_28d"), metric.get("signal", "grey")
    card = {
        "value": f"{val} {unit}" if val is not None else "—",
        "comparison": f"28d avg: {baseline} {unit}" if baseline else "No baseline",
        "change": metric_delta_str(metric.get("delta_pct")),
        "signal": signal,
    }
    thresholds = metric.get("absolute_thresholds")
    if thresholds:
        card.update(
            value=f"{val:+.2f} {unit}" if val is not None else "—",
            comparison=f"vs personal norm · red ≥ +{thresholds['red']:.2f}",
            change=TEMPERATURE_WORDS.get(signal, "No reading"),
        )
    return card


def missing_source(sources_missing, key: str) -> str | None:
    """The device with no reading for `key` on the day ("oura" or "garmin"),
    from the blend's sources_missing entries such as "hrv_ms:garmin"."""
    return next((s.split(":")[1] for s in (sources_missing or ())
                 if s.startswith(f"{key}:")), None)


def drift_lines(drift: dict, metrics: dict) -> list[str]:
    """One line per metric the baseline-drift guard compared: its last
    readings against the prior window, and whether the move is adverse."""
    lines = []
    for key, d in (drift.get("metrics") or {}).items():
        label = (metrics.get(key) or {}).get("label", key)
        lines.append(f"**{label}** — last {engine.DRIFT_RECENT_DAYS} readings "
                     f"{d['recent']} vs prior {drift['prior_days']} "
                     f"{d['prior']} ({d['delta_pct']:+.1f}%)"
                     + ("  ⚠ adverse" if d["adverse"] else ""))
    return lines


def acwr_status(acwr_result: dict) -> tuple[str, str] | None:
    """(kind, sentence) for the ACWR panel, or None when there is nothing to
    say. Kinds: "error" (hard lock), "info" (baseline still establishing),
    "warning" (above the ceiling while ACWR is advisory only)."""
    if acwr_result.get("hard_locked"):
        return "error", "Hard lock — do not increase volume."
    if not acwr_result.get("baseline_established", True):
        return "info", (f"Baseline establishing — {acwr_result.get('in_stage_days', 0)}"
                        f"/{engine.ACWR_MIN_IN_STAGE_DAYS} days into this stage. "
                        f"Ratio is not diagnostic yet.")
    if acwr_result.get("exceeds_ceiling"):
        return "warning", "Above ceiling — advisory only, volume is not capped."
    return None


def acwr_chronic_label(acwr_result: dict) -> tuple[str, str]:
    """(label, explanation) for the chronic average: over the current stage
    only, or a flat 28-day window during a reassessment gap."""
    if acwr_result.get("chronic_basis", "calendar") == "stage":
        return "Chronic avg", (
            f"Averaged over the {acwr_result.get('in_stage_days', 28)} days of the current "
            f"stage only — a window spanning a stage transition divides training load "
            f"by rehab load.")
    return "Chronic 28d avg", "Flat 28-day calendar window."


def acwr_chart_data(daily_au_28: list[float], today: date | None = None) -> dict:
    """28 calendar dates ending today, paired with each day's AU and whether
    it falls in the 21-day chronic window or the trailing 7-day acute window —
    the exact acute/chronic split concept engine.acwr already computes, now
    shared instead of being re-derived ad hoc in the view."""
    today = today or date.today()
    dates = [(today - timedelta(days=27 - i)).strftime("%Y-%m-%d") for i in range(28)]
    windows = ["Chronic (28d)"] * 21 + ["Acute (7d)"] * 7
    return {"dates": dates, "au": list(daily_au_28), "windows": windows}


def body_region_frequency(parsed_rows: list[dict]) -> dict[str, int]:
    """Count how often each body region appears across parsed readiness rows'
    ai_body_parts JSON field. Malformed JSON is skipped, not fabricated."""
    freq: dict[str, int] = {}
    for row in parsed_rows:
        raw = row.get("ai_body_parts") or "[]"
        try:
            parts = json.loads(raw)
        except Exception:
            parts = []
        for p in parts:
            freq[p] = freq.get(p, 0) + 1
    return freq


def slope_direction_rows(slopes: dict) -> list[dict]:
    """Table rows classifying each trend slope's direction. Pain/tightness:
    negative slope = improving (symptoms decreasing). Everything else
    (HRV, sleep, AU): positive slope = improving."""
    rows = []
    for k, v in slopes.items():
        if v is None:
            direction = "--"
        elif k in ("pain_slope", "tightness_slope"):
            direction = "improving" if v < 0 else "worsening"
        else:
            direction = "improving" if v > 0 else "--"
        rows.append({
            "Variable": k.replace("_slope", "").replace("_", " ").title(),
            "Slope / day": f"{v:+.5f}" if v is not None else "--",
            "Direction": direction,
        })
    return rows


# ─── The Sync tab's history tables (move INS-6, 2026-10-19) ──────────────────

def date_span(rows: list[dict]) -> tuple[date, date] | None:
    """The first and last date of rows sorted by their ISO "date", or None."""
    if not rows:
        return None
    return date.fromisoformat(str(rows[0]["date"])[:10]), date.fromisoformat(str(rows[-1]["date"])[:10])


def rows_between(rows: list[dict], start: date, end: date) -> list[dict]:
    """The rows dated from `start` to `end`, both included: the From and To
    filters of the Biometric Blend and Metrics History tables, as parameters
    the engine API takes too."""
    lo, hi = start.isoformat(), end.isoformat()
    return [r for r in rows if lo <= str(r["date"])[:10] <= hi]
