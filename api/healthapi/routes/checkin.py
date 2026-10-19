"""GET and PUT /api/checkin: the morning check-in (services/checkin_form.py).

GET answers the form for a day the check-in can be saved for (the caller's
today and the three days before), filled with the day's entry when it has
one. PUT validates every field against the same limits and stores one row
per date; a refusal names every problem at once (422). The caller's day
comes from X-Local-Date, so a backfill window never shifts at midnight UTC.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from services import checkin_form as cf
from services.repository import Repository

from ..deps import get_repository, local_today
from ..schemas import CheckInFormOut, CheckInIn

router = APIRouter()


def _refused(exc: cf.CheckInError) -> HTTPException:
    return HTTPException(status_code=422, detail="invalid_check_in: " + "; ".join(exc.errors))


@router.get("/api/checkin", response_model=CheckInFormOut)
def get_checkin(
    day: date | None = Query(default=None, alias="date"),
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    try:
        return cf.form_state(repo, day, today)
    except cf.CheckInError as exc:
        raise _refused(exc) from None


@router.put("/api/checkin", response_model=CheckInFormOut)
def put_checkin(
    body: CheckInIn,
    today: date = Depends(local_today),
    repo: Repository = Depends(get_repository),
) -> dict:
    try:
        return cf.submit(repo, body.date, today, body.values, body.opened_entry)
    except cf.CheckInError as exc:
        raise _refused(exc) from None
