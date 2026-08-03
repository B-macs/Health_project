"""Our readiness score vs Oura's own, for the last 14 days.

READ-ONLY. Runs no sync and writes nothing — it reads the already-synced
Sheet tabs, so it can't disturb the day's numbers or spend write quota.

    .\\venv\\Scripts\\python.exe scripts\\compare_readiness_to_oura.py

Note the two figures are NOT meant to be identical. Under MODEL_VERSION 2
ours is built from Oura's eight contributors plus our own Sleep Debt, with
our weights and our composite — not Oura's score passed through. Measured
over a year that lands at r = 0.992, mean bias -0.9, sd 2.8. A gap of a
few points is the design; a gap of fifteen is the v1 regression returning.
"""

import sys
import tomllib
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.config import load_config          # noqa: E402
from services.repository import Repository       # noqa: E402
from services import readiness as R              # noqa: E402

with open(ROOT / ".streamlit" / "secrets.toml", "rb") as fh:
    secrets = tomllib.load(fh)

repository = Repository(load_config(secrets))

TODAY = date.today()

# 75 days: compute_readiness_trend walks a lookback window, and the sleep
# baseline behind Sleep Debt needs 56 days of its own.
bio = [asdict(r) for r in repository.get_biometric_rolling(days=75, today=TODAY)]
print(f"today = {TODAY}   biometric rows fetched: {len(bio)}")
if bio:
    print(f"rows span {bio[0]['date']} -> {bio[-1]['date']}")

# Oura's OWN daily readiness score, straight off the Oura Daily tab.
oura_rows = repository._read_records(repository._oura_daily_ws())
oura_own: dict[str, float] = {}
for row in oura_rows:
    day = str(row.get("date") or "")
    value = row.get("readiness_score")
    if day and value not in (None, ""):
        try:
            oura_own[day] = float(value)
        except (TypeError, ValueError):
            pass

print(f"Oura Daily rows: {len(oura_rows)}, with a readiness_score: {len(oura_own)}")
print()
print(f"{'date':<12} {'ours(raw)':>10} {'ours(trend)':>12} {'Oura':>7} {'diff':>7}")
print("-" * 52)

diffs: list[float] = []
for offset in range(13, -1, -1):
    day = TODAY - timedelta(days=offset)
    day_s = day.isoformat()
    raw = R.compute_readiness(day, bio)
    trend = R.compute_readiness_trend(day, bio)
    theirs = oura_own.get(day_s)

    raw_s = "—" if raw == R.NOT_COMPUTED else f"{raw:.1f}"
    trend_s = "—" if trend == R.NOT_COMPUTED else f"{trend:.1f}"
    theirs_s = "—" if theirs is None else f"{theirs:.0f}"
    if raw != R.NOT_COMPUTED and theirs is not None:
        diff = float(raw) - theirs
        diffs.append(diff)
        diff_s = f"{diff:+.1f}"
    else:
        diff_s = "—"
    print(f"{day_s:<12} {raw_s:>10} {trend_s:>12} {theirs_s:>7} {diff_s:>7}")

if diffs:
    print("-" * 52)
    print(f"paired days: {len(diffs)}   "
          f"mean diff (ours - Oura): {sum(diffs) / len(diffs):+.1f}")
    print(f"largest gap: {max(diffs, key=abs):+.1f}")

# Today's component breakdown — which components scored, and what each
# contributed after renormalisation over the ones that were measured.
print()
breakdown = R.readiness_breakdown(TODAY, bio)
print(f"TODAY breakdown  score={breakdown['score']}  "
      f"model_version={breakdown.get('model_version')}")
if breakdown["score"] != R.NOT_COMPUTED:
    for component in breakdown["components"]:
        score = "—" if component["score"] is None else f"{component['score']:.0f}"
        print(f"   {component['label']:<24} {score:>5}   "
              f"weight {component['weight']:.2f}   "
              f"effective {component['effective_weight']:.3f}")
else:
    print(f"   missing: {', '.join(breakdown['missing'])}")
