"""GET /api/today: Home's three cards for one day (services/home.py:cards),
and GET /api/today/week: the week strip above them (home.week_strip).

The day is the `date` query parameter, or the caller's day without one, and
never a day after the caller's day (home.day_bounds). With `picked_on` (the
day the phone's user picked that date) the engine decides the day to open on
(home.opening_day, H7): a past day picked today, else today. Every number,
band and word comes from services/; this module only checks the request and
hands the answer to the model.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from services import home
from services.repository import Repository

from ..deps import get_repository, local_today
from ..schemas import TodayOut, TodayWeekOut

router = APIRouter()


@router.get("/api/today", response_model=TodayOut)
def get_today(
    day: date | None = Query(default=None, alias="date"),
    picked_on: date | None = Query(default=None),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return home.cards(repo, home.opening_day(day, picked_on, today), today)


@router.get("/api/today/week", response_model=TodayWeekOut)
def get_today_week(
    day: date | None = Query(default=None, alias="date"),
    picked_on: date | None = Query(default=None),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return home.week_strip(repo, home.opening_day(day, picked_on, today), today)
