"""
services/scheduling.py — Dynamic training day scheduling: the readiness-based
auto-shift, and session-priority rescheduling of missed sessions.

Deterministic, no I/O, no Streamlit — same idiom as services/readiness.py:
"today" is always an explicit param, and every threshold below is a named
module-level constant rather than a UI settings screen (copy the idiom, not
the literals, if a future trigger condition needs its own knob).

Two mechanisms, one week boundary, one ledger:

AUTO-SHIFT (approved, matches the user's own example: "Mon/Wed/Fri becomes
Tue/Thu/Sat"): when a trigger condition fires on a scheduled gym-session day,
that day's resolved day-number swaps with tomorrow's; the NEXT remaining
gym-session day that calendar week swaps with the day after IT; and so on
through Sunday — except that a swap is refused when the neighbor holds KNOWN
equal-or-higher SESSION_PRIORITY content (a gym day never displaces a test
day; see swap_pairs_for_shift).

MISSED-SESSION RESCHEDULING (missed_reschedules): a session missed earlier
THIS calendar week may be carried onto a later day of the same week that
holds strictly lower-priority content. The two dates TRADE day-numbers, so
the displaced lower-priority session lands on the past missed date and
becomes the one that reads as missed — honest accounting, and the weekly
rollup's scheduled count never moves. Non-adjacent intra-week swaps are
therefore possible now; what has NOT changed is the boundary: nothing
outside the affected Mon-Sun week, and neither Phase.start_date nor
Phase.length_days, is ever touched — the same data-loss-safety invariant
the manual date_overrides reschedule mechanism already relies on (see
services/plan.py's day_number_in_phase and services/models.py's Phase
docstring).

This module is pure: it computes what SHOULD happen and the date_overrides/
shift_reasons entries needed to make it so. The caller (views/training.py)
owns the actual Notion write via Repository.set_phases(). shift_reasons is
the shared evaluated-once ledger for BOTH mechanisms: the auto-shift never
re-evaluates a date already recorded there (should_evaluate_shift), and
missed_reschedules records every miss it evaluates — moved or dropped — and
never touches a date already in the ledger. Two deliberate consequences,
both failing safe to the pre-feature behaviour: a reschedule that claims
TODAY suppresses today's auto-shift, and an auto-shifted date that is later
missed reads as already handled and simply stays missed.
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

#: Session-type priority, highest wins. A missed session may be carried onto
#: a later day only if that day's type is STRICTLY lower — nothing ever
#: overwrites an equal or higher priority session. Single source of truth
#: for the ranking (the _INTENSITY_RANK / RESAMPLE_PRIORITY idiom): rank
#: through this table, never compare day_type strings anywhere else.
SESSION_PRIORITY: dict[str, int] = {"test": 3, "main": 2, "stretch": 1, "rest": 0}

#: Reason-string prefix for a miss that could NOT be carried anywhere this
#: week — the shift banner renders these without its "Session moved" framing.
DROPPED_REASON_PREFIX = "Not rescheduled: "


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


def day_type(content: dict | None) -> str | None:
    """DETERMINISTIC. The validated session type of a plan-day dict, or None
    when the day carries no usable type: content is None (a date outside the
    plan), the "day_type" key is absent (every Stage 1 day — the priority
    machinery is inert for a plan that has not authored the key), or the
    value is not in SESSION_PRIORITY. None means "no priority information":
    such a day is neither carried when missed nor eligible as a target."""
    if not content:
        return None
    value = content.get("day_type")
    return value if value in SESSION_PRIORITY else None


def can_overwrite(missed_type: str | None, target_type: str | None) -> bool:
    """DETERMINISTIC. Whether a session of missed_type may overwrite a day
    of target_type: True only when BOTH types are known and the miss
    STRICTLY outranks the target — you cannot rank what you cannot see.
    (swap_pairs_for_shift wants unknown-PARTNER-permissive behaviour
    instead, so it checks the partner for None itself before asking.)"""
    if missed_type not in SESSION_PRIORITY or target_type not in SESSION_PRIORITY:
        return False
    return SESSION_PRIORITY[missed_type] > SESSION_PRIORITY[target_type]


def _week_sunday(d: date) -> date:
    """DETERMINISTIC. Sunday of d's Mon-Sun calendar week — the hard
    boundary no scheduling move ever crosses, shared by
    swap_pairs_for_shift and missed_reschedules."""
    return d + timedelta(days=6 - d.weekday())


def swap_pairs_for_shift(phase: Phase, from_date: date, plan_dict: dict) -> dict[str, int]:
    """Pairwise-adjacent-day swap of day-numbers, from_date through the end
    of its calendar week (Sunday), for the REMAINDER of that week only.

    Walks day by day starting at from_date. At each date, resolves its
    CURRENT day-number via plan.day_number_in_phase(phase, d) (i.e. against
    phase's own existing date_overrides — this function never accumulates
    its own overrides mid-walk). If that day-number's plan_dict content is a
    gym session, it swaps with the immediately following date and the walk
    jumps past both — UNLESS the neighbor holds KNOWN content of equal or
    higher SESSION_PRIORITY ("nothing overwrites an equal or higher priority
    session": a gym day never displaces a test day), in which case nothing
    is swapped and the walk advances one date. A neighbor with no day_type
    at all (every Stage 1 day) permits the swap: you cannot rank what the
    plan has not typed, and refusing would silently kill the auto-shift for
    every untyped plan. A trailing gym day with no remaining day that week
    to pair with (i.e. Sunday itself) is left untouched — no drift outside
    the week is ever introduced.

    Walk safety invariant (weaker than the pre-priority "every date is
    visited exactly once", still sufficient): d strictly increases every
    iteration, and no date that has received an accumulated override is
    ever re-resolved — a swap jumps past both its dates, and the refused-
    swap branch writes at most from_date's own self-map, which the
    strictly-forward walk never revisits.

    Returns only the dates whose day-number actually changed, in
    date_overrides' own {"YYYY-MM-DD": day_number} shape — merge into the
    caller's existing date_overrides, don't replace it. GUARANTEED to
    always include an entry for from_date itself — even a no-op
    self-mapping, both when from_date is a trailing gym day with no
    same-week partner AND when its swap is refused on priority — so the
    caller's idempotency guard (never re-evaluate a date already recorded
    in shift_reasons) always has something to key off. Omitting from_date
    here caused an unbounded re-trigger-and-rewrite loop against Notion on
    any date where this was the trailing case — confirmed by adversarial
    review — and the refused-swap branch would recreate it identically.
    """
    week_end = _week_sunday(from_date)
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
            partner_type = day_type(plan_dict.get(partner_num))
            if partner_type is not None and not can_overwrite(day_type(content), partner_type):
                # Priority refusal: the neighbor holds known equal-or-higher
                # content (e.g. a test day). from_date still needs its entry
                # (see docstring — the Notion rewrite loop), then advance one.
                if d == from_date:
                    overrides[d.isoformat()] = day_num
                d += timedelta(days=1)
                continue
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


# ─── Missed-session rescheduling ────────────────────────────────────────────

def _spacing_ok(prev_type: str | None, new_type: str | None,
                next_type: str | None) -> bool:
    """DETERMINISTIC. Recovery-spacing rules for a candidate landing,
    evaluated on the post-swap mapping: a "main" day never lands adjacent to
    another "main" (two hard sessions never stack back to back) and never
    the day before a "test"; a "test" never lands the day after a "main" —
    the athlete's retest-contamination rule (leg work the day before a test
    reads as extra tightness in exactly the tested areas), applied to
    placement in both directions."""
    if new_type == "main":
        return prev_type != "main" and next_type not in ("main", "test")
    if new_type == "test":
        return prev_type != "main"
    return True


def missed_reschedules(
    phase: Phase,
    plan_dict: dict | None,
    logged_dates: set[str],
    today: date,
) -> tuple[dict[str, int], dict[str, str]]:
    """DETERMINISTIC. Priority-based carry of THIS week's missed sessions:
    the (date_overrides deltas, shift_reasons deltas) to merge — both empty
    when there is nothing to do.

    A miss is a date from Monday of today's week through yesterday whose
    resolved plan day is typed above "rest" in SESSION_PRIORITY (a missed
    rest day has nowhere to go and is not worth a write), was never logged
    (logged_dates must be the day strip's own yoga-inclusive source, so the
    engine's "missed" agrees with what the screen shows), and has no
    shift_reasons entry yet — the durable evaluated-once ledger shared with
    the auto-shift. Misses resolve highest priority first (earlier date
    first within a priority); each claims the EARLIEST eligible later day
    of the same Mon-Sun week, capped at the phase end — an override on a
    date beyond the phase would ADD a scheduled day to a later week's
    rollup, so the cap is correctness, not tidiness. Eligible: not logged,
    carrying no existing override or reason, unclaimed this pass, holding
    STRICTLY lower-priority content (can_overwrite), and passing
    _spacing_ok on the mapping as modified by every pending swap.

    The reschedule is a SWAP of day-numbers: the displaced lower-priority
    session lands on the past missed date and becomes the one that reads as
    missed — honest accounting, a date↔day-number bijection, and the weekly
    rollup's scheduled count never moves. A miss with nowhere left to go
    self-maps with a DROPPED_REASON_PREFIX reason: visible, final. Every
    evaluated miss therefore leaves a shift_reasons entry, which is the
    property that terminates the caller's evaluate→write→rerun cycle.
    """
    if not plan_dict:
        return {}, {}

    overrides: dict[str, int] = {}
    reasons: dict[str, str] = {}
    pending: dict[str, int] = {}  # this pass's swaps: date iso -> day-number

    def _type_at(d: date, trial: dict[str, int]) -> str | None:
        iso = d.isoformat()
        num = trial.get(iso)
        if num is None:
            num = pending.get(iso)
        if num is None:
            num = plan.day_number_in_phase(phase, d)
        return day_type(plan_dict.get(num))

    monday = today - timedelta(days=today.weekday())
    misses: list[tuple[date, int, str]] = []
    d = monday
    while d < today:
        iso = d.isoformat()
        if iso not in phase.shift_reasons and iso not in logged_dates:
            num = plan.day_number_in_phase(phase, d)
            if 1 <= num <= phase.length_days:
                mtype = day_type(plan_dict.get(num))
                if mtype is not None and SESSION_PRIORITY[mtype] > SESSION_PRIORITY["rest"]:
                    misses.append((d, num, mtype))
        d += timedelta(days=1)

    misses.sort(key=lambda m: (-SESSION_PRIORITY[m[2]], m[0]))

    phase_end = plan.phase_end_date(phase)
    for miss_date, miss_num, miss_type in misses:
        miss_iso = miss_date.isoformat()
        horizon = min(_week_sunday(miss_date), phase_end)
        target: date | None = None
        target_num = 0
        t = today
        while t <= horizon:
            iso = t.isoformat()
            if (iso not in logged_dates and iso not in phase.date_overrides
                    and iso not in phase.shift_reasons and iso not in pending):
                num = plan.day_number_in_phase(phase, t)
                if 1 <= num <= phase.length_days and can_overwrite(
                        miss_type, day_type(plan_dict.get(num))):
                    trial = {iso: miss_num, miss_iso: num}
                    if _spacing_ok(_type_at(t - timedelta(days=1), trial),
                                   miss_type,
                                   _type_at(t + timedelta(days=1), trial)):
                        target, target_num = t, num
                        break
            t += timedelta(days=1)

        if target is None:
            overrides[miss_iso] = miss_num  # no-op self-map: the ledger entry
            reasons[miss_iso] = DROPPED_REASON_PREFIX + "no free lower-priority day this week"
        else:
            t_iso = target.isoformat()
            overrides[miss_iso] = target_num
            overrides[t_iso] = miss_num
            reasons[miss_iso] = f"Missed → moved to {t_iso}"
            reasons[t_iso] = f"Moved from {miss_iso} (missed)"
            pending[t_iso] = miss_num
            pending[miss_iso] = target_num

    return overrides, reasons
