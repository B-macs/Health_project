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
through Sunday (never past the phase end). A swap is refused when the
neighbor holds KNOWN day_type content the mover does not STRICTLY outrank
(a gym day never displaces a test day), when the neighbor resolves out of
the phase's range (forced rest stays rest), or when either date already
carries a shift_reasons entry — and every accepted landing is then
validated against the same _spacing_ok rules the carry uses, undoing swaps
that would put a main on the eve of a test or two mains back to back. A
held (unswapped) from_date self-maps with a HELD_REASON_PREFIX reason. See
swap_pairs_for_shift.

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
owns the actual Notion write via Repository.set_phases() — and, by the
athlete's rule (2026-08-07), the athlete owns the DECISION: a proposal that
would MOVE a session is never persisted without an explicit confirmation,
however loudly the readings argue for it. has_real_move draws the line —
only no-movement records (holds, drops, declines) may be written unasked —
and declined_entries turns a "no" into a ledger entry so the question is
never re-asked. shift_reasons is the shared evaluated-once ledger for BOTH
mechanisms: the auto-shift never re-evaluates a date already recorded there
(should_evaluate_shift), and missed_reschedules records every miss it
evaluates — moved, dropped or declined — and never touches a date already
in the ledger. Two deliberate consequences, both failing safe to the
pre-feature behaviour: a reschedule that claims TODAY suppresses today's
auto-shift, and an auto-shifted date that is later missed reads as already
handled and simply stays missed.
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

#: Reason-string prefix for a date whose auto-shift was evaluated but whose
#: session was KEPT IN PLACE (a refused or spacing-undone swap's no-op
#: self-map). The ledger entry must exist either way — it is what stops the
#: rewrite loop — but the banner renders these without the "Session moved"
#: framing, which would otherwise announce a move that never happened.
HELD_REASON_PREFIX = "Session kept in place: "

#: Reason-string prefix for a proposed move the ATHLETE declined. The engine
#: asked, the answer was no, and the ledger entry is what stops it asking
#: again — nothing about the schedule itself changes.
DECLINED_REASON_PREFIX = "Declined: "


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


def has_real_move(phase: Phase, overrides: dict[str, int]) -> bool:
    """DETERMINISTIC. Whether a proposed override set MOVES anything — any
    entry whose day-number differs from that date's current resolution. A
    proposal of pure self-maps (holds, drops) is a RECORD, not a move, and
    is the only kind the caller may persist without the athlete's explicit
    confirmation (the athlete's rule, 2026-08-07: never swapped without
    permission, even when the readings say it should be)."""
    return any(
        plan.day_number_in_phase(phase, date.fromisoformat(iso)) != num
        for iso, num in overrides.items()
    )


def declined_entries(phase: Phase, dates: list[date],
                     reason: str) -> tuple[dict[str, int], dict[str, str]]:
    """DETERMINISTIC. The ledger entries to persist when the athlete
    DECLINES a proposed move: a no-op self-map plus a DECLINED reason for
    each evaluated date, so the guards never propose it again and the
    banner tells the truth (nothing moved). Same (date_overrides,
    shift_reasons) delta shape as every other writer — merge, don't
    replace."""
    overrides = {d.isoformat(): plan.day_number_in_phase(phase, d) for d in dates}
    reasons = {iso: DECLINED_REASON_PREFIX + reason for iso in overrides}
    return overrides, reasons


# ─── Manual swap: a past missed day traded with today, by choice ────────────
# The user-initiated counterpart of missed_reschedules. Ask-first cuts both
# ways: the automatic machinery never moves a session without the athlete's
# button press, and the athlete's button press moves a session the automatic
# machinery never would — so the rules that HARD-gate the automatic carry
# (strict priority, spacing, the same-week horizon) demote to WARNINGS here.
# Only structural impossibilities block.

def manual_swap_blockers(phase: Phase, missed_date: date, today: date,
                         logged_dates: set[str]) -> list[str]:
    """DETERMINISTIC. Why a user-requested swap of a past missed day with
    today CANNOT happen — empty means it can. Blockers are structural
    impossibilities only (a day that isn't missed, a today that already
    trained, a date the plan doesn't cover); judgement calls belong to
    manual_swap_warnings, because the explicit choice IS the permission.
    A forced-rest today (0 override) is deliberately NOT a blocker — the
    athlete's own rest record yields to the athlete's own click (it warned
    the live 2026-08-09 swap attempt into a dead end when it blocked)."""
    blockers: list[str] = []
    if missed_date >= today:
        blockers.append("Only a past day can be swapped with today.")
    if missed_date.isoformat() in logged_dates:
        blockers.append("That day has a logged session — it was not missed.")
    if today.isoformat() in logged_dates:
        blockers.append("Today already has a logged session — nothing can move onto it.")
    if not (1 <= plan.day_number_in_phase(phase, missed_date) <= phase.length_days):
        blockers.append("That day is outside the current plan.")
    today_num = plan.day_number_in_phase(phase, today)
    if not (1 <= today_num <= phase.length_days) \
            and phase.date_overrides.get(today.isoformat()) != 0:
        blockers.append("Today is outside the current plan.")
    return blockers


def manual_swap_warnings(phase: Phase, plan_dict: dict | None,
                         missed_date: date, today: date) -> list[str]:
    """DETERMINISTIC. Advisory cautions for a user-requested swap — shown
    beside the button, never blocking it. These are the exact rules the
    automatic carry enforces hard (strict priority, main/test spacing),
    restated as consequences so the athlete decides with them in view."""
    warnings: list[str] = []
    plan_dict = plan_dict or {}

    def _type_at(d: date) -> str | None:
        return day_type(plan_dict.get(plan.day_number_in_phase(phase, d)))

    incoming = _type_at(missed_date)   # what the swap brings to today
    outgoing = _type_at(today)         # what it sends into the past as missed
    if phase.date_overrides.get(today.isoformat()) == 0:
        warnings.append(
            "Today is set as a forced rest day — the swap replaces it, and "
            "the rest day moves onto the missed date instead."
        )
    if incoming is not None and outgoing is not None \
            and not can_overwrite(incoming, outgoing):
        warnings.append(
            "Today's session is not lower priority than the missed one — "
            "the swap records today's session as the one that was missed."
        )
    prev_t = _type_at(today - timedelta(days=1))
    next_t = _type_at(today + timedelta(days=1))
    if incoming == "main" and ("main" in (prev_t, next_t)):
        warnings.append(
            "This puts two hard training days back to back — the plan keeps them apart."
        )
    if incoming == "main" and next_t == "test":
        warnings.append(
            "This puts hard leg work the day before a test — the reading "
            "would measure the training, not the baseline."
        )
    if incoming == "test" and prev_t == "main":
        warnings.append(
            "This puts the test the morning after hard training — the "
            "reading would measure the training, not the baseline."
        )
    return warnings


def manual_swap_entries(phase: Phase, missed_date: date,
                        today: date) -> tuple[dict[str, int], dict[str, str]]:
    """DETERMINISTIC. The swap the athlete asked for: the past missed date
    and today trade day-numbers — the same honest-accounting swap the
    automatic carry uses, so the displaced session becomes the one that
    reads as missed. A forced-rest today trades its 0 onto the missed date:
    the rest day moves to where the rest actually happened. The reasons on
    both dates carry no no-movement prefix (this IS a move, the banner
    should say so) and close both automatic schedulers' guards, so neither
    ever re-proposes either date."""
    miss_num = plan.day_number_in_phase(phase, missed_date)
    today_num = plan.day_number_in_phase(phase, today)
    overrides = {missed_date.isoformat(): today_num, today.isoformat(): miss_num}
    reasons = {
        missed_date.isoformat(): f"Swapped with {today.isoformat()} by choice",
        today.isoformat(): f"Swapped with {missed_date.isoformat()} by choice",
    }
    return overrides, reasons


def swap_pairs_for_shift(phase: Phase, from_date: date, plan_dict: dict) -> dict[str, int]:
    """Pairwise-adjacent-day swap of day-numbers, from_date through the end
    of its calendar week (Sunday), for the REMAINDER of that week only.

    Walks day by day starting at from_date, never past the week's Sunday
    NOR the phase end — a swap onto a date outside the phase would map a
    session where nothing ever renders or counts it, the same reason
    missed_reschedules caps its carry at the phase end. At each date,
    resolves its CURRENT day-number via plan.day_number_in_phase(phase, d)
    (i.e. against phase's own existing date_overrides — this function never
    accumulates its own overrides mid-walk). If that day-number's plan_dict
    content is a gym session, it swaps with the immediately following date
    and the walk jumps past both — UNLESS the swap is refused, in which
    case nothing is swapped and the walk advances one date. Refusals:
      * the partner holds KNOWN day_type content the mover does not
        STRICTLY outrank ("nothing overwrites an equal or higher priority
        session" — note an untyped mover next to any typed partner is
        refused too: you cannot rank what you cannot see);
      * the partner's resolved day-number is out of the phase's range — a
        forced-rest 0 override (the athlete's explicit rest stays rest,
        especially when readiness demanded MORE recovery) or a date beyond
        the plan;
      * the partner OR the mover (mid-walk) already carries a shift_reasons
        entry — a date is scheduled at most once, so a session carried in
        by missed_reschedules is never re-shifted and its reason never
        overwritten.
    A partner with no day_type at all (every Stage 1 day) permits the swap:
    refusing would silently kill the auto-shift for every untyped plan. A
    trailing gym day with no remaining day to pair with is left untouched —
    no drift outside the week or phase is ever introduced.

    After the walk, every accepted swap's LANDING is validated against
    _spacing_ok on the final mapping, and violating swaps are undone to a
    fixed point. This is what keeps a main off the eve of a test — on the
    live plan, a Friday trigger in week 4 must NOT push Session C onto the
    Saturday before the day-28 reassessment — and what stops a mid-walk
    refusal from leaving two mains adjacent. The check runs post-walk, not
    mid-walk, because mid-walk adjacency is transient (the canonical
    Mon/Wed/Fri -> Tue/Thu/Sat cascade briefly reads adjacent until the
    next pair also moves). The undo loop can legitimately collapse the
    WHOLE cascade — a week-4 Monday trigger shifts nothing, because with
    Friday pinned off the test's eve every partial shift stacks two mains —
    in which case the session is held in place (the volume modifier still
    protects the athlete) and the banner says so via HELD_REASON_PREFIX.

    Walk safety invariant (weaker than the pre-priority "every date is
    visited exactly once", still sufficient): d strictly increases every
    iteration, and no date that has received an accumulated override is
    ever re-resolved mid-walk — a swap jumps past both its dates, and the
    refused-swap branch writes at most from_date's own self-map, which the
    strictly-forward walk never revisits. The post-walk validation only
    deletes accepted pairs or restores from_date's self-map, so the
    guarantee below survives it.

    Returns only the dates whose day-number actually changed, in
    date_overrides' own {"YYYY-MM-DD": day_number} shape — merge into the
    caller's existing date_overrides, don't replace it. GUARANTEED to
    always include an entry for from_date itself — even a no-op
    self-mapping, whether from_date is a trailing gym day with no partner,
    its swap was refused, or its swap was undone by spacing validation — so
    the caller's idempotency guard (never re-evaluate a date already
    recorded in shift_reasons) always has something to key off. Omitting
    from_date here caused an unbounded re-trigger-and-rewrite loop against
    Notion on any date where this was the trailing case — confirmed by
    adversarial review — and every refusal path would recreate it
    identically.
    """
    week_end = min(_week_sunday(from_date), plan.phase_end_date(phase))
    overrides: dict[str, int] = {}
    swapped: list[tuple[str, str]] = []  # (mover iso, landing iso) per accepted swap

    d = from_date
    while d <= week_end:
        day_num = plan.day_number_in_phase(phase, d)
        content = plan_dict.get(day_num)
        if content and content.get("is_gym_session"):
            if d != from_date and d.isoformat() in phase.shift_reasons:
                # Already scheduled once (e.g. a session carried in by
                # missed_reschedules) — never rescheduled. from_date itself
                # is exempt: the caller's guard already vouches for it.
                d += timedelta(days=1)
                continue
            partner = d + timedelta(days=1)
            if partner > week_end:
                # Trailing gym day with no same-week/in-phase neighbor to
                # swap with. Record a no-op self-mapping so from_date still
                # gets a date_overrides/shift_reasons entry.
                if d == from_date:
                    overrides[d.isoformat()] = day_num
                break  # nothing to pair with — leave untouched
            partner_num = plan.day_number_in_phase(phase, partner)
            partner_type = day_type(plan_dict.get(partner_num))
            refused = (
                (partner_type is not None
                 and not can_overwrite(day_type(content), partner_type))
                or not (1 <= partner_num <= phase.length_days)
                or partner.isoformat() in phase.shift_reasons
            )
            if refused:
                # from_date still needs its entry (see docstring — the
                # Notion rewrite loop), then advance one.
                if d == from_date:
                    overrides[d.isoformat()] = day_num
                d += timedelta(days=1)
                continue
            overrides[d.isoformat()] = partner_num
            overrides[partner.isoformat()] = day_num
            swapped.append((d.isoformat(), partner.isoformat()))
            d = partner + timedelta(days=1)
        else:
            d += timedelta(days=1)

    # Post-walk spacing validation on the FINAL mapping, undone to a fixed
    # point: undoing one pair can re-expose a neighbor for an earlier pair
    # (restoring Friday's main makes Thursday's landing adjacent), so loop
    # until a full pass deletes nothing. Terminates: each pass either
    # removes a pair or breaks, and pairs only ever shrink.
    def _final_type(x: date) -> str | None:
        num = overrides.get(x.isoformat())
        if num is None:
            num = plan.day_number_in_phase(phase, x)
        return day_type(plan_dict.get(num))

    undone = True
    while undone:
        undone = False
        for pair in list(swapped):
            mover_iso, landing_iso = pair
            landing = date.fromisoformat(landing_iso)
            mover_type = day_type(plan_dict.get(overrides[landing_iso]))
            if not _spacing_ok(_final_type(landing - timedelta(days=1)),
                               mover_type,
                               _final_type(landing + timedelta(days=1))):
                del overrides[mover_iso]
                del overrides[landing_iso]
                swapped.remove(pair)
                if mover_iso == from_date.isoformat():
                    overrides[mover_iso] = plan.day_number_in_phase(phase, from_date)
                undone = True

    return overrides


def shift_reason_entries(overrides: dict[str, int], reason: str,
                          phase: Phase | None = None) -> dict[str, str]:
    """The shift_reasons entries to merge alongside swap_pairs_for_shift's
    date_overrides — every date the swap touched gets the same trigger
    reason, so the shift banner explains why on whichever of the touched
    dates the user is actually looking at.

    Pass the phase to distinguish a no-op self-map (an entry whose
    day-number equals the date's pre-merge resolution — a refused, undone
    or trailing swap) from a real move: self-maps get HELD_REASON_PREFIX so
    the banner never announces "Session moved" over a session that did not
    move. The ledger semantics are identical either way — the caller's
    guard keys on the entry existing, never on its wording."""
    if phase is None:
        return {d: reason for d in overrides}
    entries: dict[str, str] = {}
    for iso, num in overrides.items():
        held = plan.day_number_in_phase(phase, date.fromisoformat(iso)) == num
        entries[iso] = (HELD_REASON_PREFIX + reason) if held else reason
    return entries


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
