"""
services/scheduling.py — Dynamic training day scheduling (readiness-based
auto-shift).

Deterministic, no I/O, no Streamlit — same idiom as services/readiness.py:
"today" is always an explicit param, and every threshold below is a named
module-level constant rather than a UI settings screen (copy the idiom, not
the literals, if a future trigger condition needs its own knob).

Design (approved, matches the user's own example: "Mon/Wed/Fri becomes
Tue/Thu/Sat"): when a trigger condition fires on a scheduled gym-session day,
that day's resolved day-number swaps with tomorrow's; the NEXT remaining
gym-session day that calendar week swaps with the day after IT; and so on
through Sunday. This is pairwise-adjacent-day swapping, not drift absorption
— every date within the affected week either keeps its original day-number or
trades with its immediate neighbor. Nothing outside that week, and neither
Phase.start_date nor Phase.length_days, is ever touched — the same
data-loss-safety invariant the manual date_overrides reschedule mechanism
already relies on (see services/plan.py's day_number_in_phase and
services/models.py's Phase docstring).

This module is pure: it computes what SHOULD happen and the date_overrides/
shift_reasons entries needed to make it so. The caller (views/training.py)
owns the idempotency guard (never re-evaluate a date that already has a
shift_reasons entry) and the actual Notion write via
Repository.set_phases().
"""

from __future__ import annotations

from datetime import date, timedelta

from services import plan
from services import readiness as rd
from services.models import Phase

# ─── Configurable thresholds ────────────────────────────────────────────────
# Sleep-debt threshold/window now live on services.readiness (SLEEP_DEBT_
# THRESHOLD_HOURS / SLEEP_DEBT_WINDOW_DAYS), alongside sleep_debt_hours
# itself — moved there 2026-07-30 so compute_readiness could use the same
# function as its own sleep_debt component without a circular import
# (this module already imports readiness for sleep_baseline). Referenced
# here via rd.SLEEP_DEBT_THRESHOLD_HOURS / rd.sleep_debt_hours below.

# Single-night sleep, absolute (not baseline-relative) — a genuinely short
# night on its own triggers a shift regardless of the trailing-week picture.
SHORT_SLEEP_THRESHOLD_HOURS = 5.0
# Alcohol logged on this many consecutive days ending yesterday triggers a
# shift (today's own alcohol entry, if any, isn't relevant here — it's
# yesterday-and-earlier that predicts today's recovery state).
CONSECUTIVE_ALCOHOL_DAYS = 2


def should_evaluate_shift(is_gym_session: bool, today_iso: str, shift_reasons: dict[str, str]) -> bool:
    """The idempotency guard: whether the caller should even bother calling
    should_shift_session for today, let alone write anything. False on any
    non-gym day (nothing to shift), and False once today already has a
    shift_reasons entry — the single check that stops every subsequent
    render this same day from re-evaluating and re-writing once a shift
    has already been recorded for today. Extracted from views/training.py
    as a pure function so this guard — previously untested despite gating
    a live Notion write — has direct test coverage."""
    return is_gym_session and today_iso not in shift_reasons


def should_shift_session(bio_rows: list[dict], checkin_rows: list[dict],
                          for_date: date) -> tuple[bool, str | None]:
    """Whether today's gym session should auto-shift, and why.

    checkin_rows: date-keyed rows with an "alcohol_units" field per date —
    the same shape services.readiness.compute_readiness consumes for its
    alcohol penalty (there, embedded in bio_rows via
    Repository.get_biometric_rolling's merge of the Readiness DB; here,
    passed separately so a caller can supply either the same bio_rows list
    reused, or Repository.get_recent_readiness's raw rows — both carry
    "date" + "alcohol_units" per entry).

    Checks, in order (first match wins): cumulative sleep debt, single-night
    short sleep, then consecutive-day alcohol. Returns (False, None) if none
    trigger.
    """
    debt = rd.sleep_debt_hours(bio_rows, for_date)
    if debt is not None and debt >= rd.SLEEP_DEBT_THRESHOLD_HOURS:
        return True, (
            f"Sleep debt of {debt:.1f}h over the last {rd.SLEEP_DEBT_WINDOW_DAYS} nights"
        )

    bio_by_date = {r["date"]: r for r in bio_rows if r.get("date")}
    today_row = bio_by_date.get(for_date.isoformat())
    today_sleep = today_row.get("sleep_duration_hours") if today_row else None
    if today_sleep is not None and float(today_sleep) < SHORT_SLEEP_THRESHOLD_HOURS:
        return True, f"Only {float(today_sleep):.1f}h slept last night"

    checkin_by_date = {r["date"]: r for r in checkin_rows if r.get("date")}
    consecutive = 0
    for delta in range(1, CONSECUTIVE_ALCOHOL_DAYS + 1):
        d = for_date - timedelta(days=delta)
        row = checkin_by_date.get(d.isoformat())
        units = row.get("alcohol_units") if row else None
        if units is not None and float(units) > 0:
            consecutive += 1
        else:
            break
    if consecutive >= CONSECUTIVE_ALCOHOL_DAYS:
        return True, f"Alcohol logged {CONSECUTIVE_ALCOHOL_DAYS} days in a row"

    return False, None


def swap_pairs_for_shift(phase: Phase, from_date: date, plan_dict: dict) -> dict[str, int]:
    """Pairwise-adjacent-day swap of day-numbers, from_date through the end
    of its calendar week (Sunday), for the REMAINDER of that week only.

    Walks day by day starting at from_date. At each not-yet-touched date,
    resolves its CURRENT day-number via plan.day_number_in_phase(phase, d)
    (i.e. against phase's own existing date_overrides — this function never
    accumulates its own overrides mid-walk, since every date it touches is
    only ever visited once). If that day-number's plan_dict content is a gym
    session, it swaps with the immediately following date and the walk jumps
    past both; otherwise it advances one date at a time. A trailing gym day
    with no remaining day that week to pair with (i.e. Sunday itself) is left
    untouched — no drift outside the week is ever introduced.

    Returns only the dates whose day-number actually changed, in
    date_overrides' own {"YYYY-MM-DD": day_number} shape — merge into the
    caller's existing date_overrides, don't replace it. GUARANTEED to
    always include an entry for from_date itself (even a no-op
    self-mapping when from_date is a trailing gym day with no same-week
    partner — see the inline comment below) so the caller's idempotency
    guard (never re-evaluate a date already recorded in shift_reasons)
    always has something to key off. Omitting from_date here caused an
    unbounded re-trigger-and-rewrite loop against Notion on any date where
    this was the trailing case — confirmed by adversarial review.
    """
    week_end = from_date + timedelta(days=6 - from_date.weekday())
    overrides: dict[str, int] = {}

    d = from_date
    while d <= week_end:
        day_num = plan.day_number_in_phase(phase, d)
        content = plan_dict.get(day_num)
        if content and content.get("is_gym_session"):
            partner = d + timedelta(days=1)
            if partner > week_end:
                # Trailing gym day with no same-week neighbor to swap with
                # (from_date itself can only ever be this date, since every
                # later date reached by the walk already consumed its pair
                # -- see docstring). Record a no-op self-mapping so from_date
                # still gets a date_overrides/shift_reasons entry.
                if d == from_date:
                    overrides[d.isoformat()] = day_num
                break  # no same-week neighbor to pair with — leave untouched
            partner_num = plan.day_number_in_phase(phase, partner)
            overrides[d.isoformat()] = partner_num
            overrides[partner.isoformat()] = day_num
            d = partner + timedelta(days=1)
        else:
            d += timedelta(days=1)

    return overrides


def shift_reason_entries(overrides: dict[str, int], reason: str) -> dict[str, str]:
    """The shift_reasons entries to merge alongside swap_pairs_for_shift's
    date_overrides — every date the swap touched gets the same trigger
    reason, so the "Session moved" banner explains why on whichever of the
    swapped dates the user is actually looking at."""
    return {d: reason for d in overrides}
