"""GET /api/today: Home's three cards for one day (services/home.py:cards).

The day is the `date` query parameter, or the caller's day without one, and
never a day after the caller's day (home.day_bounds). Every number, band and
word comes from services/; this module only checks the request and hands the
answer to the model.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from services import home
from services.repository import Repository

from ..deps import get_repository, local_today
from ..schemas import TodayOut

router = APIRouter()


@router.get("/api/today", response_model=TodayOut)
def get_today(
    day: date | None = Query(default=None, alias="date"),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return home.cards(repo, day, today)
