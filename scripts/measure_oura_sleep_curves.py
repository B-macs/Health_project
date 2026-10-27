# -*- coding: utf-8 -*-
"""Measure Oura's own curves for two sleep parts, from his own nights (read-only).

    python scripts/measure_oura_sleep_curves.py

Sleep Score MODEL_VERSION 4 (2026-10-27) moves the Total Sleep and Efficiency
parts along Oura's own curve when a wake-time correction adds minutes of sleep
(services/sleep_score.py). Oura does not publish the curves, so they are the
median of Oura's own part in each half hour of sleep (and each 5 % of
efficiency) with at least 5 nights, never falling as the reading rises. This
prints both curves in the form sleep_score.py holds them, how closely Oura's
part sits to each, and whether the stored constants still match. Re-measure,
never hand-tune: paste a changed curve into OURA_TOTAL_SLEEP_CURVE /
OURA_EFFICIENCY_CURVE and re-derive the stored history.

Reads a copy of the store rebuilt for this run only; writes nothing.
"""

from __future__ import annotations

import statistics
import sys
import tempfile
import tomllib
from dataclasses import asdict
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import sleep_score  # noqa: E402

#: The fewest nights a step needs before its median counts.
MIN_NIGHTS = 5


def curve(pairs: list[tuple[float, float]], lo: float, hi: float, step: float) -> tuple:
    """(reading, part) knots: the median part of each step with MIN_NIGHTS
    nights, at the step's middle, never falling as the reading rises."""
    knots: list[tuple[float, float]] = []
    x = lo
    while x < hi:
        parts = [p for v, p in pairs if x <= v < x + step]
        if len(parts) >= MIN_NIGHTS:
            median = float(statistics.median(parts))
            knots.append((round(x + step / 2, 2), max(median, knots[-1][1]) if knots else median))
        x += step
    return tuple(knots)


def fit(pairs: list[tuple[float, float]], knots: tuple) -> dict:
    """How far Oura's own part sits from the curve, night by night."""
    errors = [abs(sleep_score._interp(v, knots) - p) for v, p in pairs]
    return {"nights": len(errors), "mean": statistics.mean(errors),
            "within_3": sum(e <= 3 for e in errors) / len(errors)}


def pairs_from(rows: list[dict]) -> tuple[list, list]:
    total = [(r["oura_sleep_total_seconds"] / 3600.0, float(r["oura_sleep_total_sleep_score"]))
             for r in rows if r.get("oura_sleep_total_seconds")
             and r.get("oura_sleep_total_sleep_score") is not None]
    eff = [(float(r["oura_sleep_efficiency"]), float(r["oura_sleep_efficiency_score"]))
           for r in rows if r.get("oura_sleep_efficiency") is not None
           and r.get("oura_sleep_efficiency_score") is not None]
    return total, eff


def _repository():
    from services.config import load_config
    from services.repository import Repository
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    copy = Path(tempfile.mkdtemp(prefix="oura_curves_")) / "record.db"
    return Repository(load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase",
                                   "HEALTH_DATASTORE_MODE": "cache",
                                   "HEALTH_DATASTORE_PATH": str(copy)}))


def main() -> int:
    rows = [asdict(r) for r in _repository().get_biometric_rolling(days=3000, today=date.today())]
    total, eff = pairs_from(rows)
    for name, pairs, knots, stored in (
        ("OURA_TOTAL_SLEEP_CURVE", total, curve(total, 3.0, 10.0, 0.5),
         sleep_score.OURA_TOTAL_SLEEP_CURVE),
        ("OURA_EFFICIENCY_CURVE", eff, curve(eff, 50.0, 100.0, 5.0),
         sleep_score.OURA_EFFICIENCY_CURVE),
    ):
        f = fit(pairs, knots)
        print(f"{name} = {knots!r}")
        print(f"  {f['nights']} nights; Oura's part is {f['mean']:.1f} points from the curve "
              f"on average, within 3 points on {100 * f['within_3']:.0f}% of nights.")
        print("  matches the stored curve." if knots == stored
              else "  DIFFERS from the stored curve: paste it in and re-derive the history.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
