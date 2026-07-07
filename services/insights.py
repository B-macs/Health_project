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

_DIRECTIVE_LABELS = {
    "green":  "Train normally today.",
    "yellow": "Reduced load today — keep the session controlled, don't push to failure.",
    "orange": "Reduced load today — keep the session controlled, don't push to failure.",
    "red":    "Rest day — mobility and walking only. No loaded training.",
    "grey":   "Building baseline — train at comfortable effort.",
}

_DIRECTIVE_DETAIL_FIXED = {
    "yellow": (
        "Biometrics are slightly below your rolling average. "
        "Scale back total volume by around 20–25%. "
        "Hold intensity — just do fewer sets."
    ),
    "orange": (
        "Biometrics are slightly below your rolling average. "
        "Scale back total volume by around 20–25%. "
        "Hold intensity — just do fewer sets."
    ),
    "red": "Biometrics show significant systemic fatigue. Rest is the training stimulus today.",
}


def directive_copy(rec: dict) -> tuple[str, str]:
    """(label, detail) plain-language copy for today's engine directive.
    green/grey detail comes from the real directive's own action text —
    never fabricated; yellow/orange/red use fixed clinical copy."""
    sig = rec["signal_color"]
    label = _DIRECTIVE_LABELS.get(sig, rec["label"])
    detail = _DIRECTIVE_DETAIL_FIXED.get(sig, rec["action"])
    return label, detail


def metric_delta_str(delta_pct: float | None) -> str:
    if not delta_pct:
        return ""
    arrow = "▲" if delta_pct > 0 else "▼"
    return f"{arrow} {abs(delta_pct):.1f}%"


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
