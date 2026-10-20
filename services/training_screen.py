"""The Training screen, composed for the phone's API (rebuild Phase 2,
milestone 5): the week, one day, today's overview and the actions that
change the schedule.

views/training.py draws the same panels from the same services/ functions
(training_week, scheduling, week_repeat, gate1, decision, sessions,
flexibility). This module makes the reads for the caller's day (rule 3) and
returns what each panel shows as data. A sentence the page holds as fixed
text (a button's label, a panel's heading) stays in the phone's strings
file, keyed by the state returned here.

ASK-FIRST STAYS (the athlete's rule, 2026-08-07). A read never writes: a
proposal that would move a session (the missed-session carry, the readiness
shift) is returned as a prompt, and only apply_carry / apply_shift store it,
or store "declined" so the prompt never asks again. The records that move
nothing and the failed-week rule are the background writer's
(services/engine_sync.py), not a read's.

EVERY WRITE IS REBUILT FROM LIVE READS of the stored phases
(Repository.get_phases_live): it replaces the whole phase list, and two
processes (the Streamlit app and the engine) each keep a local copy, so a
list built from one copy could put an older schedule over a newer one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

from services import decision as _decision
from services import flexibility as fx
from services import gate1 as g1
from services import plan as _plan
from services import scheduling
from services import sessions as sess
from services import training_week, week_repeat
from services import yoga as yg
from services.models import Phase


class ActionRefused(ValueError):
    """A schedule action that was not stored: `code` names why, `details`
    carries the rule's own words (each refusal, each blocker)."""

    def __init__(self, code: str, details: list[str] | None = None):
        super().__init__(code if not details else f"{code}: {'; '.join(details)}")
        self.code = code
        self.details = list(details or [])


@dataclass
class Reads:
    """The phases and today's place in them. `phases_error` is set when the
    stored phases could not be read: the page then says so and offers
    nothing that writes (the + menu's yoga still works)."""
    today: date
    phases: list[Phase] = field(default_factory=list)
    phases_error: str = ""
    active: Phase | None = None
    day_num: int | None = None
    plan: dict = field(default_factory=dict)


def read(repo, today: date, *, live: bool = False) -> Reads:
    """The phases (from the store itself with `live`, for a write), the block
    active on the caller's day, today's day number in it and its calendar
    plan (sessions.calendar_plan: the authored plan read through any
    repeated or dropped weeks)."""
    try:
        phases = repo.get_phases_live() if live else repo.get_phases()
    except Exception as exc:
        return Reads(today, phases_error=type(exc).__name__)
    active = _plan.active_phase(phases, today)
    return Reads(today, list(phases), "", active,
                 _plan.day_number_in_phase(active, today) if active else None,
                 sess.calendar_plan(active) if active else {})


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _first_start(phases: list[Phase]) -> date | None:
    return min((date.fromisoformat(p.start_date) for p in phases), default=None)


def _try(read_, default):
    try:
        return read_()
    except Exception:
        return default


def _logged_since_first(repo, r: Reads) -> set[str]:
    first = _first_start(r.phases)
    return set(_try(lambda: repo.get_logged_session_dates(first, r.today), set())) if first else set()


def exercise_line(ex: dict) -> dict:
    """One exercise as a list shows it: its name, icon, prescription and
    how-to (sessions.prescription_label, type_icon). The reasoning fields
    (biomechanical_focus, progression, regression) are never shown (Key
    Rule 20), so they are not returned."""
    return {"name": ex["name"], "type": ex.get("type"), "icon": sess.type_icon(ex),
            "prescription": sess.prescription_label(ex),
            "laterality": ex.get("laterality"), "mechanics": ex.get("mechanics") or ""}


def phase_out(r: Reads) -> dict | None:
    if r.active is None:
        return None
    return {"number": r.active.phase_number, "name": r.active.name,
            "start_date": r.active.start_date, "length_days": r.active.length_days,
            "plan_days": len(r.plan), "day_num": r.day_num}


# ─── The prompts that ask before they move a session ─────────────────────────

def carry_proposal(repo, r: Reads) -> dict | None:
    """The missed-session carry for this week, or None (move TRN-6's reads).

    A block that runs its sessions in order (the 12-week block: A, B, C,
    then D) moves the rest along after a missed day
    (scheduling.in_order_reschedules, its "done" a logged PLAN session, so a
    yoga day is not session A); any other block carries a missed session onto
    a later day of lower priority (scheduling.missed_reschedules). `moves`
    is False for a proposal that only records drops: the calendar does not
    change, and the background writer stores it unasked."""
    if r.active is None:
        return None
    monday = _monday(r.today)
    in_order = scheduling.runs_in_order(r.plan)
    logged = repo.get_logged_session_dates(monday, monday + timedelta(days=6),
                                           include_supplementary=not in_order)
    if in_order:
        overrides, reasons = scheduling.in_order_reschedules(r.active, r.plan, logged, r.today)
    else:
        overrides, reasons = scheduling.missed_reschedules(r.active, r.plan, logged, r.today)
    if not overrides:
        return None
    return {
        "in_order": in_order,
        "moves": scheduling.has_real_move(r.active, overrides),
        "lines": (scheduling.in_order_summary(r.active, r.plan, overrides, r.today) if in_order
                  else [f"{d}: {why}" for d, why in sorted(reasons.items())]),
        "overrides": overrides,
        "reasons": reasons,
    }


def shift_proposal(repo, r: Reads) -> dict | None:
    """Today's readiness shift, or None: evaluated once a day on a gym day
    (scheduling.should_evaluate_shift, the guard that stops a recorded shift
    being proposed again), on the engine's 14 readiness rows, as the Training
    page reads them (fault F1). `moves` is False for a HELD record (a
    trailing day, a refusal), which moves nothing."""
    if r.active is None or r.day_num is None:
        return None
    content = r.plan.get(r.day_num)
    if not scheduling.should_evaluate_shift(bool(content and content.get("is_gym_session")),
                                            r.today.isoformat(), r.active.shift_reasons):
        return None
    rows = _decision.readiness_rows(repo, r.today)
    shift, reason = scheduling.should_shift_session(rows, rows, r.today)
    if not shift:
        return None
    overrides = scheduling.swap_pairs_for_shift(r.active, r.today, r.plan)
    return {"reason": reason, "moves": scheduling.has_real_move(r.active, overrides),
            "overrides": overrides,
            "reasons": scheduling.shift_reason_entries(overrides, reason, phase=r.active)}


def _prompt_out(proposal: dict | None) -> dict | None:
    """What a prompt shows; the overrides stay on the engine, which rebuilds
    them from live reads when the athlete answers."""
    if proposal is None or not proposal["moves"]:
        return None
    return {k: v for k, v in proposal.items() if k not in ("overrides", "reasons", "moves")}


# ─── The week ────────────────────────────────────────────────────────────────

def _redo(phases: list[Phase], logged: set[str], today: date) -> dict:
    """The Monday "redo this week" offer (week_repeat.redo_is_offered: after
    a week of 0-2 logged days, on the Monday only) with what it would move."""
    if not phases or not week_repeat.redo_is_offered(phases, logged, today):
        return {"offered": False, "consequences": []}
    after, _refusal = week_repeat.redo_this_week(phases, logged, today)
    if after is None:
        return {"offered": False, "consequences": []}
    return {"offered": True,
            "consequences": ["Next week runs this week's sessions again.",
                             *week_repeat.consequences(phases, after)]}


def week_view(repo, today: date, week_start: date | None = None) -> dict:
    """The week page: the rollup banner, the failed-week notices and the
    redo offer, gate 1, the flexibility retest notice, the day strip of the
    week asked for (clamped to the block's weeks), that week's stored
    verdict, the gap screen when no block covers today, and the prompts
    that ask before they move a session."""
    r = read(repo, today)
    if r.phases_error:
        return {"phases_readable": False, "phases_error": r.phases_error}
    logged = _logged_since_first(repo, r)
    history = training_week.read_week_history(repo, r.phases, today, logged_dates=logged)

    default_week = _monday(today)
    ws = _monday(week_start) if week_start else default_week
    lo = hi = None
    if r.active is not None:
        ws = _plan.clamp_week_start(ws, r.active)
        lo, hi = _plan.phase_week_bounds(r.active)
    week_logged = set(_try(lambda: repo.get_logged_session_dates(ws, ws + timedelta(days=6)),
                           set()))
    cells = training_week.week_strip(ws, r.active, week_logged, today)
    strip = []
    for cell in cells:
        note = (scheduling.shift_note(r.active.shift_reasons, cell.date.isoformat(),
                                      cell.date.isoformat() in week_logged)
                if r.active is not None else None)
        strip.append({"date": cell.date, "weekday_label": cell.weekday_label,
                      "marker": training_week.strip_marker(cell, today),
                      "state": cell.state, "day_num": cell.day_number_in_phase,
                      "note": None if not note else {"text": note,
                                                     "moved": scheduling.shift_note_moved(note)}})

    notice = (_try(lambda: week_repeat.repeat_notice(r.phases, today), None)
              if week_repeat.repeat_notice_is_due(today) else None)
    gate = None
    if g1.applies(r.active):
        gate = _try(lambda: g1.read_card(repo, r.active, today), None)
    retest = None
    stored = _try(repo.get_flexibility_assessments, ())
    if stored:
        notice_ = _try(lambda: fx.retest_notice(
            stored, repo.get_recent_sessions(days=3, today=today), today), None)
        if notice_:
            retest = {"kind": notice_[0], "status": notice_[1], "reason": notice_[2]}
    return {
        "phases_readable": True,
        "phases_error": "",
        "today": today,
        "phase": phase_out(r),
        "banner": training_week.banner(history, today),
        "repeat_notice": notice,
        "load_held": week_repeat.failed_week_holds_load(r.phases, today),
        "redo": _try(lambda: _redo(r.phases, logged, today),
                     {"offered": False, "consequences": []}),
        "gate1": None if gate is None else gate1_out(gate),
        "retest": retest,
        "week_start": ws,
        "is_current_week": ws == default_week,
        "can_go_back": lo is None or ws > lo,
        "can_go_forward": hi is None or ws < hi,
        "strip": strip,
        "viewed_week_status": training_week.viewed_week_status(history, ws, today),
        "gap": sess.phase_gap(r.phases, today) if r.active is None else None,
        "carry_prompt": _prompt_out(_try(lambda: carry_proposal(repo, r), None)),
        "shift_prompt": _prompt_out(_try(lambda: shift_proposal(repo, r), None)),
    }


def gate1_out(card: dict) -> dict:
    """Gate 1's card (gate1.read_card) as data: the 6-week count, the week
    waiting for its reason and the answers it takes, the four main lifts
    against their target, and this week's flare-up."""
    waiting = card.get("waiting")
    return {
        "count": card["count"],
        "lifts_met": card["lifts_met"],
        "rows": card["rows"],
        "waiting": None if waiting is None else {"monday": waiting["monday"],
                                                 "core_done": waiting["core_done"],
                                                 "core_required": g1.CORE_REQUIRED},
        "reasons": [{"key": k, "label": v} for k, v in g1.REASONS.items()],
        "flare_this_week": bool(card.get("flare_this_week")),
    }


# ─── One day ─────────────────────────────────────────────────────────────────

def swap_offer(repo, r: Reads, day: date) -> dict:
    """The swap-with-today offer on another day's view: blocked by a
    structural reason (today already trained, a date outside the block),
    else offered with the automatic path's rules as warnings, never as
    blocks (the button press is the permission)."""
    try:
        logged = repo.get_logged_session_dates(date.fromisoformat(r.active.start_date), r.today,
                                               include_supplementary=False)
    except Exception:
        return {"available": False, "check_failed": True, "blockers": [], "warnings": [],
                "today_objective": ""}
    blockers = scheduling.manual_swap_blockers(r.active, day, r.today, logged)
    if blockers:
        return {"available": False, "check_failed": False, "blockers": blockers,
                "warnings": [], "today_objective": ""}
    today_num = _plan.day_number_in_phase(r.active, r.today)
    content = r.plan.get(today_num)
    return {"available": True, "check_failed": False, "blockers": [],
            "warnings": scheduling.manual_swap_warnings(r.active, r.plan, day, r.today),
            "today_objective": content["objective"] if content else f"Day {today_num}"}


def _planned(r: Reads, day: date) -> dict:
    day_num = _plan.day_number_in_phase(r.active, day)
    content = r.plan.get(day_num)
    return {"day_num": day_num, "plan_days": r.active.length_days,
            "objective": content["objective"] if content else None,
            "rpe_target": content.get("session_rpe_target") if content else None,
            "exercises": [exercise_line(ex) for ex in (content or {}).get("exercises", [])],
            "home": [exercise_line(ex) for ex in (content or {}).get("home") or []]}


def _logged_session(repo, day: date, today: date) -> dict | None:
    sessions = _try(lambda: repo.get_recent_sessions(days=sess.days_back_to(day, today),
                                                     today=today), [])
    found = next((s for s in sessions if s.session_date == day.isoformat()), None)
    if not found or not found.exercises:
        return None      # logged by the strip's check, but no detail could be read
    return {"rpe": found.session_rpe, "minutes": found.session_duration_minutes,
            "au": found.session_au,
            "exercises": [{"name": e.name, "movement_type": e.movement_type,
                           "planned_sets": e.planned_sets} for e in found.exercises]}


def rest_view(day: date, today: date) -> dict:
    suggestion = yg.suggest_for_day("rest_day")
    return {"is_today": day == today,
            "yoga_suggestion": None if not suggestion else {
                "slug": suggestion.slug, "name": suggestion.name,
                "minutes": suggestion.total_duration_minutes}}


def day_view(repo, day: date, today: date) -> dict:
    """One day of the strip (sessions.day_route): "rest" (with an optional
    yoga flow), "past_completed" (the logged session), "past_missed" (what
    was planned, and the swap onto today), "future" (the preview, the at-home
    items and "do this session today"), "today" (today's overview), or
    "no_phase" (the gap screen). The schedule note for the day rides along,
    "moved" only when the session really moved."""
    r = read(repo, today)
    if r.phases_error:
        return {"date": day, "route": "phases_unreadable", "phases_error": r.phases_error}
    if r.active is None:
        return {"date": day, "route": "no_phase", "gap": sess.phase_gap(r.phases, today)}
    logged = bool(_try(lambda: repo.has_logged_session(day), False))
    route = sess.day_route(day, today, r.active, logged)
    if route == "today" and sess.today_is_rest(r.active, today):
        route = "rest"
    note = scheduling.shift_note(r.active.shift_reasons, day.isoformat(), logged)
    out = {"date": day, "route": route, "phase": phase_out(r),
           "note": None if not note else {"text": note, "moved": scheduling.shift_note_moved(note)}}
    if route == "rest":
        out["rest"] = rest_view(day, today)
    elif route == "past_completed":
        out["logged"] = _logged_session(repo, day, today)
    elif route == "past_missed":
        out["planned"] = _planned(r, day)
        out["swap"] = swap_offer(repo, r, day)
    elif route == "future":
        out["planned"] = _planned(r, day)
        out["swap"] = swap_offer(repo, r, day)
    elif route == "today":
        out["overview"] = today_overview(repo, r)
    return out


# ─── Today's overview (before Start) ─────────────────────────────────────────

def todays_decision(repo, phases: list[Phase], today: date) -> dict:
    """Today's ONE load decision, as both screens read it: the verdict
    (decision.day_verdict), its policy with the failed-week hold folded in
    (decision.training_policy), the directive and the readiness modifier."""
    verdict = _decision.day_verdict(repo, today)
    return {"verdict": verdict,
            "policy": _decision.training_policy(verdict.policy, phases, today),
            "directive": _decision.directive(repo, today),
            "modifier": _decision.readiness_modifier(_decision.readiness_rows(repo, today))}


def verdict_banner(verdict, directive: dict) -> dict:
    """The banner over the session: the verdict's kind and text (nothing on a
    green or grey day) and the ACWR advisory, which annotates and never
    decides while ACWR is advisory."""
    return {"kind": verdict.banner_kind, "text": verdict.banner_text, "cause": verdict.cause,
            "acwr_advisory": directive.get("acwr_advisory") or ""}


def adaptation(policy: dict) -> dict:
    """The "Adapt session" dialog and the SESSION ADAPTED badge, from the
    RESOLVED policy, never readiness's raw proposal."""
    factor = policy.get("volume_factor", 1.0)
    return {"volume_factor": factor, "reduced": bool(policy.get("reduced")),
            "banner_kind": policy.get("banner_kind") or "",
            "volume_note": policy.get("volume_note") or "",
            "badge_shown": factor != 1.0 or bool(policy.get("volume_note"))}


def today_overview(repo, r: Reads, decided: dict | None = None) -> dict:
    """Today's overview before Start: the banner, the coach's headline, the
    workout card, the release and workout lists AS DOSED TODAY (fault F20),
    the at-home items, the first side of today's one-sided exercises and
    the adaptation. `screen` is sessions.today_screen's answer for a day
    with nothing started: "overview", "not_started" (before the block's
    first day) or "complete" (after its last), and "logged" when today's
    plan session is already logged."""
    decided = decided or todays_decision(repo, r.phases, r.today)
    plan_days = len(r.plan)
    logged = bool(_try(lambda: sess.logged_today(repo, r.today), False))
    screen = "logged" if logged else sess.today_screen(r.day_num, plan_days, False, False)
    out = {"screen": screen, "day_num": r.day_num, "plan_days": plan_days,
           "phase_name": r.active.name}
    if screen != "overview":
        return out
    content = r.plan[r.day_num]
    policy = decided["policy"]
    exercises = sess.dosed_day(content["exercises"], policy["volume_factor"],
                               content.get("day_type"))
    headline, subtitle = sess.coach_message(decided["directive"], content, policy)
    release, main = sess.split_release_and_main(exercises)
    return {
        **out,
        "objective": content["objective"],
        "banner": verdict_banner(decided["verdict"], decided["directive"]),
        "headline": headline,
        "subtitle": subtitle,
        "card": {"minutes": sess.estimate_duration(exercises),
                 "rpe_target": content["session_rpe_target"],
                 "focus": sess.focus_areas(exercises) or ["Full Body"],
                 "loaded": sess.is_loaded_session(exercises),
                 "exercise_count": len(exercises)},
        "release": [exercise_line(ex) for ex in release],
        "main": [exercise_line(ex) for ex in main],
        "home": [exercise_line(ex) for ex in content.get("home") or []],
        "first_side": sess.first_side(r.today),
        "first_side_note": sess.first_side_note(exercises, r.today),
        "adaptation": adaptation(policy),
    }


# ─── The actions ─────────────────────────────────────────────────────────────

#: The schedule answers the phone sent, by the id it minted (rebuild rule 4): its outbox
#: sends an answer again when the first answer was lost on the way back, and a swap applied
#: twice puts the two days back where they were. An id already applied is answered as
#: stored and changes nothing. The newest ACTIONS_KEPT ids are kept, in config.
APPLIED_ACTIONS_KEY = "applied_actions"
ACTIONS_KEPT = 200


def applied_actions(repo) -> list[str]:
    """The ids already applied, read from the store itself (another process may have
    applied one since this one built its copy). A read that fails raises: answering
    "not applied" then could apply a move twice."""
    raw = repo.get_config_value_live(APPLIED_ACTIONS_KEY)
    try:
        ids = json.loads(raw) if raw else []
    except ValueError:
        ids = []
    return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []


def once(repo, action_id: str | None, today: date, run) -> dict:
    """Run a schedule answer once per id. Without an id it runs as before."""
    if not action_id:
        return run()
    done = applied_actions(repo)
    if action_id in done:
        return {"stored": True}
    out = run()
    repo.set_config(APPLIED_ACTIONS_KEY, json.dumps((done + [action_id])[-ACTIONS_KEPT:]), today)
    return out

def _store(repo, r: Reads, overrides: dict, reasons: dict) -> list[Phase]:
    """One schedule change through scheduling.apply_schedule_change (Key Rule
    18b: refused whole, never clamped), over the LIVE phases in `r`."""
    new_phases, rejected = scheduling.apply_schedule_change(r.phases, r.active, overrides, reasons)
    if rejected:
        raise ActionRefused("refused", [x["detail"] for x in rejected])
    repo.set_phases(new_phases)
    return new_phases


def _live(repo, today: date) -> Reads:
    r = read(repo, today, live=True)
    if r.phases_error:
        raise ActionRefused("phases_unreadable", [r.phases_error])
    if r.active is None:
        raise ActionRefused("no_active_block")
    return r


def apply_carry(repo, today: date, accept: bool) -> dict:
    """The athlete's answer to the carry prompt, rebuilt from live reads:
    "apply" stores the proposal, "decline" records the missed days as left
    as missed so the prompt does not ask again."""
    r = _live(repo, today)
    proposal = carry_proposal(repo, r)
    if proposal is None or not proposal["moves"]:
        raise ActionRefused("nothing_to_carry")
    if accept:
        _store(repo, r, proposal["overrides"], proposal["reasons"])
    else:
        missed = [date.fromisoformat(iso) for iso in proposal["overrides"]
                  if date.fromisoformat(iso) < today]
        if not missed:
            raise ActionRefused("nothing_to_carry")
        _store(repo, r, *scheduling.declined_entries(r.active, missed, scheduling.LEFT_AS_MISSED))
    return {"stored": True}


def apply_shift(repo, today: date, accept: bool) -> dict:
    """The athlete's answer to the readiness shift: "move" stores it,
    "keep" records the decline so it is not proposed again today."""
    r = _live(repo, today)
    proposal = shift_proposal(repo, r)
    if proposal is None or not proposal["moves"]:
        raise ActionRefused("nothing_to_shift")
    if accept:
        _store(repo, r, proposal["overrides"], proposal["reasons"])
    else:
        _store(repo, r, *scheduling.declined_entries(r.active, [today], proposal["reason"]))
    return {"stored": True}


def swap_with_today(repo, today: date, other: date) -> dict:
    """Swap another day's session onto today (a missed day carried forward,
    or a future day pulled in), the blockers re-checked against a fresh read
    of what is logged before the one permanent write."""
    r = _live(repo, today)
    logged = repo.get_logged_session_dates(min(other, today), max(other, today),
                                           include_supplementary=False)
    blockers = scheduling.manual_swap_blockers(r.active, other, today, logged)
    if blockers:
        raise ActionRefused("swap_blocked", blockers)
    _store(repo, r, *scheduling.manual_swap_entries(r.active, other, today))
    return {"stored": True}


def redo_week(repo, today: date) -> dict:
    """The athlete's "Yes, redo this week" (week_repeat.store_redo, rebuilt
    from live reads), offered on a Monday after a week of 0-2 logged days."""
    fresh, why = week_repeat.store_redo(repo, today)
    if fresh is None:
        raise ActionRefused("not_repeated", [why] if why else [])
    return {"stored": True}


def record_gate1_reason(repo, today: date, monday: date, reason: str) -> dict:
    """The one-tap reason for a gate-1 week with fewer than 3 core sessions."""
    r = _live(repo, today)
    if not g1.applies(r.active):
        raise ActionRefused("gate1_not_running")
    if reason not in g1.REASONS:
        raise ActionRefused("unknown_reason", [reason])
    try:
        g1.record_reason(repo, r.active, today, monday, reason)
    except ValueError as exc:
        raise ActionRefused("refused", [str(exc)]) from None
    return {"stored": True}


def record_gate1_flare(repo, today: date) -> dict:
    """A flare-up this week (it resets the 6-week count)."""
    r = _live(repo, today)
    if not g1.applies(r.active):
        raise ActionRefused("gate1_not_running")
    g1.record_flare(repo, r.active, today)
    return {"stored": True}
