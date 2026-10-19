"""GET /api/readiness: the readiness card's figures for one day.

services/home.py:readiness_figures computes them, as the Streamlit Home card
does (DAILY from the engine's 14 rows on the caller's day, the 60 ending on
the day otherwise; TREND over those 60; the headline is DAILY, else TREND),
and dashboard.readiness_meta gives the band words. The Phase 0 proof route,
kept beside GET /api/today, which carries the same figures with the rest of
the card.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from services import dashboard, home, readiness
from services.repository import Repository

from ..deps import get_repository, local_today
from ..schemas import ReadinessBand, ReadinessOut

router = APIRouter()


@router.get("/api/readiness", response_model=ReadinessOut)
def get_readiness(
    day: date = Query(alias="date"),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> ReadinessOut:
    figures = home.readiness_figures(repo, day, today)
    _colour, _value, label, header, description, _ = dashboard.readiness_meta(figures["headline"])
    return ReadinessOut(
        date=day, daily=figures["daily"], trend=figures["trend"], headline=figures["headline"],
        band=ReadinessBand(label=label, header=header, description=description),
        model_version=readiness.MODEL_VERSION, window_days=figures["window_days"],
    )
