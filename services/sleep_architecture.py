"""Insights › Sleep Architecture's rules (move INS-6, rebuild Phase 2,
2026-10-19), so the phone's screen reads the same counts as the Streamlit tab.

Fault F12: the "Oura only" count was every stored night that was not fused,
so it counted the watch-only nights too (services/sleep_fusion.py emits a
night the ring did not record as SOURCE_GARMIN_ONLY). Each source now has its
own count.
"""

from __future__ import annotations

from services import sleep_fusion


def summary(rows: list[dict]) -> dict:
    """The tab's counts: {"fused", "oura_only", "watch_only", "fused_rows",
    "median_phantom_wake"}. The median is the upper middle of the fused nights'
    phantom-wake minutes (the value the tab has always shown), None without a
    fused night."""
    def of(source: str) -> list[dict]:
        return [r for r in rows if r.get("source") == source]

    fused = of(sleep_fusion.SOURCE_FUSED)
    phantom = sorted(float(r.get("phantom_wake_minutes") or 0) for r in fused)
    return {
        "fused": len(fused),
        "oura_only": len(of(sleep_fusion.SOURCE_OURA_ONLY)),
        "watch_only": len(of(sleep_fusion.SOURCE_GARMIN_ONLY)),
        "fused_rows": fused,
        "median_phantom_wake": phantom[len(phantom) // 2] if phantom else None,
    }


def fused_hours(rows: list[dict]) -> dict[str, float]:
    """{date: fused sleep hours} of the fused nights, for the shadow report."""
    return {r["date"]: float(r["master_sleep_hours"])
            for r in rows
            if r.get("source") == sleep_fusion.SOURCE_FUSED
            and str(r.get("master_sleep_hours") or "").strip() != ""}
