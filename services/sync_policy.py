"""When the engine syncs the devices, and which sync notice a screen shows.

THE OWNER'S RULE, 2026-10-19: "Lets reduce the sync to once a day in the
morning when the app is openned first, that is enough", and, on a morning the
first sync found nothing yet: "Retry the sync". So the first open of the
caller's day syncs; while last night's numbers are still missing after it, a
later open syncs again, at most once an hour; once they are in, nothing more
that day. Whatever screen opens first starts it (the Streamlit app synced only
when Home loaded to its end, so a morning that went straight to Training
synced nothing).

The Streamlit app keeps its own 2-hourly-on-open cadence until the
switch-over (Phase 9): one background writer at a time (rebuild rule 2), and
the owner asked for no change there. The day is always the CALLER's (rule 3).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from services import dashboard as dash

#: The least time between a retry and the sync before it, while last night
#: is missing.
RETRY_MINUTES = 60

#: Why a sync is due (sync_due).
FIRST_OPEN = "the first open of the day"
LAST_NIGHT_MISSING = "last night's numbers are still missing"


def last_night_in(today_metrics_row: dict | None) -> bool:
    """Last night's numbers are in when the caller's day has a Metrics History
    row carrying readiness and sleep (dashboard.snapshot_is_complete). Strain
    is not required: it changes later in the day through the app's own
    saves, not through a device sync."""
    return dash.snapshot_is_complete(today_metrics_row)


def sync_due(caller_today: date, now: datetime, last_run_day: date | None,
             last_run_at: datetime | None, night_in: bool) -> str | None:
    """Why a sync is due now (FIRST_OPEN or LAST_NIGHT_MISSING), or None.

    `last_run_day` is the caller's day the last sync ran for and
    `last_run_at` when it ran; `now` and `last_run_at` share one clock."""
    if last_run_day is None or last_run_day < caller_today:
        return FIRST_OPEN
    if night_in:
        return None
    if last_run_at is None or now - last_run_at >= timedelta(minutes=RETRY_MINUTES):
        return LAST_NIGHT_MISSING
    return None


# ─── The notices (move HOME-27) ─────────────────────────────────────────────

#: The notices a screen may show about the device sync (sync_notices).
OURA_UNAUTHORISED = "oura_unauthorised"
OURA_UNAVAILABLE = "oura_unavailable"
GARMIN_UNAVAILABLE = "garmin_unavailable"
SYNC_FAILED_TO_RUN = "sync_failed_to_run"


def sync_notices(oura_auth: dict | None, oura: tuple, garmin: tuple,
                 run_error) -> list[tuple[str, str]]:
    """(level, code) for each notice about the device sync, in the order a
    screen shows them; level is "error" or "caption".

    A DEAD CREDENTIAL AND A FLAKY NETWORK ARE NOT THE SAME NOTICE. Folding
    them into one grey "will retry" caption is what let the Oura token die on
    2026-08-12 and go unnoticed for five days, while readiness renormalised
    onto its one surviving component and went up. So an Oura login that
    needs authorising is an error, checked on its own rather than through
    this run's result (a throttled sync usually reports nothing at all), and
    a step that failed is a caption. A chain that failed before any step
    reported says so too, or every status would read fine.

    `oura` and `garmin` are each step's (ok, error) result."""
    notices: list[tuple[str, str]] = []
    oura_ok, oura_err = oura
    garmin_ok, garmin_err = garmin
    if (oura_auth or {}).get("needs_authorisation"):
        notices.append(("error", OURA_UNAUTHORISED))
    elif not oura_ok and oura_err:
        notices.append(("caption", OURA_UNAVAILABLE))
    if not garmin_ok and garmin_err:
        notices.append(("caption", GARMIN_UNAVAILABLE))
    if run_error:
        notices.append(("caption", SYNC_FAILED_TO_RUN))
    return notices
