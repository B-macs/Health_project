"""GET /api/readiness: the Home card's readiness for one day.

The same computation the Streamlit Home card makes (app.py:2378-2400 and
today.py:today_readiness_raw), with the caller's day in place of the server
clock:
- DAILY: compute_readiness over the 14-day rows when the day asked for IS the
  caller's today (today.py's window), over the 60-day rows for any other day;
- TREND: compute_readiness_trend over the 60-day rows;
- the headline is DAILY when it was computed, otherwise TREND;
- the band words come from dashboard.readiness_meta.

⚠ The choice of window is Home-card logic that still lives in app.py and
today.py. It is repeated here for the Phase 0 proof only; rebuild Phase 2
moves it into services/ and makes app.py call the same function
(docs/rebuild/state.md, open items).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, Query

from services import dashboard, readiness
from services.repository import Repository

from .. import engine
from ..dates import caller_local_date
from ..schemas import ReadinessBand, ReadinessOut

router = APIRouter()

TODAY_WINDOW_DAYS = 14     # today.py:_bio_for_readiness
OTHER_WINDOW_DAYS = 60     # app.py:_bio_rolling


def get_repository() -> Repository:
    return engine.new_repository()


def _score(value) -> float | None:
    return None if value is None or isinstance(value, str) else float(value)


@router.get("/api/readiness", response_model=ReadinessOut)
def get_readiness(
    day: date = Query(alias="date"),
    local_today: date = Depends(caller_local_date),
    repo: Repository = Depends(get_repository),
) -> ReadinessOut:
    rows_60 = [asdict(r) for r in repo.get_biometric_rolling(days=OTHER_WINDOW_DAYS,
                                                             today=local_today)]
    if day == local_today:
        rows_14 = [asdict(r) for r in repo.get_biometric_rolling(days=TODAY_WINDOW_DAYS,
                                                                 today=local_today)]
        daily_rows, window = rows_14, TODAY_WINDOW_DAYS
    else:
        daily_rows, window = rows_60, OTHER_WINDOW_DAYS
    daily = _score(readiness.compute_readiness(for_date=day, bio_rows=daily_rows))
    trend = _score(readiness.compute_readiness_trend(day, rows_60))
    headline = daily if daily is not None else trend
    _colour, _value, label, header, description, _ = dashboard.readiness_meta(headline)
    return ReadinessOut(
        date=day, daily=daily, trend=trend, headline=headline,
        band=ReadinessBand(label=label, header=header, description=description),
        model_version=readiness.MODEL_VERSION, window_days=window,
    )
