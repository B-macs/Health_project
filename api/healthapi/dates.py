"""The caller's day. The server never decides "today" (rebuild rule 3).

Cloud Run runs on UTC; the owner's day is in HEALTH_TIMEZONE. Between midnight
and 01:00 or 02:00 local time the two disagree, so any route whose answer
depends on "today" takes the phone's local date from the `X-Local-Date`
header and refuses without it. The container's TZ setting is a safety net for
the services/ code that still reads date.today(), not the source of the day.
"""

from __future__ import annotations

from datetime import date

from fastapi import Header, HTTPException


def caller_local_date(x_local_date: str | None = Header(default=None)) -> date:
    if not x_local_date:
        raise HTTPException(status_code=400, detail="x_local_date_missing")
    try:
        return date.fromisoformat(x_local_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="x_local_date_invalid") from None
