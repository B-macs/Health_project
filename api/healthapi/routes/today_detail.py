"""Today's three drill-downs and the wake-time correction
(services/home_detail.py).

GET /api/today/readiness, /api/today/sleep and /api/today/strain answer for
the `date` query parameter, or the caller's day without one, never a day
after the caller's day. PUT /api/sleep/wake-adjustment stores one night's
correction (Key Rule 4's one manual correction) under the rules the
Streamlit stepper keeps; the value is absolute, so a repeated request
stores one correction.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from services import home_detail
from services.repository import Repository

from ..deps import get_repository, local_today
from ..schemas import (ReadinessDetailOut, SleepDetailOut, StrainDetailOut, WakeAdjustmentIn,
                       WakeControl)

router = APIRouter()

#: How each refusal of a wake-time correction answers.
_WAKE_STATUS = {"future_day": 422, "minutes_invalid": 422,
                "night_not_scored": 409, "fusion_applies": 409}


@router.get("/api/today/readiness", response_model=ReadinessDetailOut)
def get_readiness_detail(
    day: date | None = Query(default=None, alias="date"),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return home_detail.readiness_detail(repo, day, today)


@router.get("/api/today/sleep", response_model=SleepDetailOut)
def get_sleep_detail(
    day: date | None = Query(default=None, alias="date"),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return home_detail.sleep_detail(repo, day, today)


@router.get("/api/today/strain", response_model=StrainDetailOut)
def get_strain_detail(
    day: date | None = Query(default=None, alias="date"),
    week: bool = Query(default=False),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    return home_detail.strain_detail(repo, day, today, show_week=week)


@router.put("/api/sleep/wake-adjustment", response_model=WakeControl)
def put_wake_adjustment(
    body: WakeAdjustmentIn,
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    try:
        return home_detail.set_wake_adjustment(repo, body.date, today, body.minutes)
    except home_detail.WakeAdjustmentError as exc:
        raise HTTPException(status_code=_WAKE_STATUS[exc.code], detail=exc.code) from None
