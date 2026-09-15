"""
services/week_repeat.py — THE FAILED-WEEK RULE. Pure: no I/O, no Streamlit, no
clock reads (`today` is always a parameter).

The athlete's rule, 2026-09-15: "if I fail a week it gets repeated and pushes
out the block by one week."

  * A week FAILS with 0-2 logged days — metrics_logic.FAILED_WEEK_MAX_DAYS, the
    same line the "Failed week" label draws, so the label and the consequence
    cannot disagree. Every logged session counts toward a day, and all seven
    days of the week count, rest days included, exactly as the label counts.
  * A failed week repeats BY ITSELF, from the Monday after it ends ("make it
    automatic for 0-2 days"). There is no button on this path: the rule is a
    consequence he set for himself, and a consequence that asks permission is
    a suggestion.
  * A week with 3 or more days is not failed, and can still be REDONE BY
    CHOICE ("also give me the option to redo the week") — the same repeat,
    started by a button press instead of by the count.
  * Repeating a week inserts it into its block's week_plan, so the block gets
    seven days longer and every later block starts one week later. A block
    with a fixed last date (Block B ends on race day) cannot end later, so it
    LOSES its next droppable week instead (sessions.PHASE_META "drop_weeks").
    When nothing droppable is left the repeat is REFUSED and the refusal is
    recorded — the race never moves and the decision run never disappears.
  * Every week is judged ONCE, pass or fail, and the verdict is stored on the
    phase (Phase.week_results). A session deleted weeks later can never repeat
    a week after the fact, and a week already redone by choice is not
    repeated a second time when it ends.
  * Weeks starting before RULE_FROM are never judged. The rule began with the
    week of 2026-09-07; the two weeks before it would also have failed, and
    the athlete asked to repeat only last week.

WHAT A REPEAT DOES NOT TOUCH: day numbers stay calendar positions, so
date_overrides, key rule 18b's week check, the day strip and the missed-session
carry all work unchanged inside a repeated week. Only the content a position
shows changes, and only through sessions.calendar_plan.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, timedelta

from services import metrics_logic as _ml
from services import plan as _plan
from services import sessions as _sess
from services.models import Phase

#: The Monday of the first week the rule judges. Athlete, 2026-09-15: "repeat
#: last week as it was a failed week" — that week, and no earlier one.
RULE_FROM = date(2026, 9, 7)

FAILED_PREFIX = "Failed"
PASSED_PREFIX = "Passed"
REDONE_PREFIX = "Redone by choice"

_DAYS_RE = re.compile(r"(\d+) of 7 days")


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _start(phase: Phase) -> date:
    return date.fromisoformat(phase.start_date)


def _meta_for(phase: Phase, meta: dict) -> dict:
    return meta.get(phase.phase_number) or {}


def _long_date(d: date) -> str:
    """"21 September" — built by hand because %-d does not exist on Windows."""
    return f"{d.day} {d:%B}"


def covering_phase(phases: list[Phase], d: date) -> Phase | None:
    """The live (not completed) block whose calendar holds `d`.

    Completed blocks are never judged and never repeated: 'completed' is how a
    block is ended before its calendar runs out (plan.active_phase), so its
    remaining weeks were deliberately abandoned, not failed.
    """
    for phase in phases:
        if phase.status != "completed" and _start(phase) <= d <= _plan.phase_end_date(phase):
            return phase
    return None


def days_logged(logged_dates, monday: date) -> int:
    """Logged days in the Monday-to-Sunday week starting `monday`."""
    logged = {d if isinstance(d, str) else d.isoformat() for d in logged_dates}
    return sum(1 for i in range(7) if (monday + timedelta(days=i)).isoformat() in logged)


def _move_dated(entries: dict, old_start: date, new_start: date, new_index_of,
                *, positions: bool) -> dict:
    """Carry a phase's date-keyed entries onto the calendar weeks their content
    now occupies.

    `new_index_of(old_week_index)` gives the week's new index, counted from
    `new_start`, or None when that week's content no longer runs — its entries
    go with it. With `positions`, a non-zero value is a day number and moves by
    the same number of weeks as its date, so a swap stays inside its own week
    (key rule 18b). A 0 is a forced rest and stays 0.
    """
    out = {}
    for iso, value in entries.items():
        d = date.fromisoformat(iso)
        days = (d - old_start).days
        if days < 0:
            out[iso] = value
            continue
        old_index, offset = divmod(days, 7)
        new_index = new_index_of(old_index)
        if new_index is None:
            continue
        if positions and value:
            value = value + (new_index - old_index) * 7
        out[(new_start + timedelta(days=new_index * 7 + offset)).isoformat()] = value
    return out


def _removed_index(longer: list[int], shorter: list[int]) -> int:
    for index, week in enumerate(shorter):
        if longer[index] != week:
            return index
    return len(shorter)


def _alignment_problem(phases: list[Phase]) -> str | None:
    """The same two refusals Repository.set_phases makes, checked before a
    result is handed back, so a repeat that would be refused on write is
    refused here with a reason instead."""
    live = sorted((p for p in phases if p.status != "completed"), key=_start)
    for phase in live:
        errors = _plan.week_alignment_errors(_start(phase), phase.length_days)
        if errors:
            return f"{phase.name}: " + "; ".join(errors)
    for a, b in zip(live, live[1:]):
        if _start(b) <= _plan.phase_end_date(a):
            return f"{a.name} would overlap {b.name}"
    return None


def repeat_week(phases: list[Phase], monday: date, outcome: str, *,
                meta: dict | None = None) -> tuple[list[Phase] | None, str | None]:
    """Run the calendar week starting `monday` again, in the week after it.

    Returns (the new phase list, None), or (None, why not). `outcome` is
    recorded against `monday` in the block's week_results on success; a caller
    that is refused records its own outcome.

    The block that holds the week gains the repeat. If its last date is fixed,
    it drops its next droppable week AFTER the repeat instead of growing, and
    nothing later moves. Otherwise it grows by seven days and every later live
    block starts seven days later — and a later block with a fixed last date
    absorbs the week by dropping one of its own, which stops the push there.
    """
    meta = _sess.PHASE_META if meta is None else meta
    target = covering_phase(phases, monday)
    if target is None:
        return None, "no block covers that week"
    start = _start(target)
    index = (monday - start).days // 7
    weeks = _plan.plan_weeks(target)
    grown = weeks[:index + 1] + [weeks[index]] + weeks[index + 1:]
    final, dropped_at = grown, None
    ends_on = _meta_for(target, meta).get("ends_on")
    if ends_on is not None and start + timedelta(days=len(grown) * 7 - 1) > ends_on:
        fewer = _plan.drop_week(grown, _meta_for(target, meta).get("drop_weeks", ()),
                                after=index + 1)
        if fewer is None:
            return None, (f"{target.name} has to end on {_long_date(ends_on)} and has no "
                          f"week left that it may lose")
        final, dropped_at = fewer, _removed_index(grown, fewer)

    def target_index(old: int) -> int | None:
        if old <= index:
            return old
        moved = old + 1
        if dropped_at is None:
            return moved
        if moved == dropped_at:
            return None
        return moved - 1 if moved > dropped_at else moved

    replaced: dict[int, Phase] = {
        target.phase_number: replace(
            target,
            length_days=len(final) * 7,
            week_plan=final,
            date_overrides=_move_dated(target.date_overrides, start, start,
                                       target_index, positions=True),
            shift_reasons=_move_dated(target.shift_reasons, start, start,
                                      target_index, positions=False),
            week_results={**target.week_results, monday.isoformat(): outcome},
        )
    }

    if dropped_at is None:
        old_end = _plan.phase_end_date(target)
        later = sorted((p for p in phases if p.status != "completed"
                        and _start(p) > old_end), key=_start)
        for block in later:
            block_start = _start(block)
            new_start = block_start + timedelta(days=7)
            block_ends_on = _meta_for(block, meta).get("ends_on")
            if (block_ends_on is not None
                    and _plan.phase_end_date(block) + timedelta(days=7) > block_ends_on):
                block_weeks = _plan.plan_weeks(block)
                fewer = _plan.drop_week(block_weeks, _meta_for(block, meta).get("drop_weeks", ()))
                if fewer is None:
                    return None, (f"{block.name} has to end on {_long_date(block_ends_on)} "
                                  f"and has no week left that it may lose")
                gone = _removed_index(block_weeks, fewer)

                def block_index(old: int, gone: int = gone) -> int | None:
                    if old < gone:
                        return old
                    return None if old == gone else old - 1

                replaced[block.phase_number] = replace(
                    block, start_date=new_start.isoformat(),
                    length_days=len(fewer) * 7, week_plan=fewer,
                    date_overrides=_move_dated(block.date_overrides, block_start, new_start,
                                               block_index, positions=True),
                    shift_reasons=_move_dated(block.shift_reasons, block_start, new_start,
                                              block_index, positions=False),
                )
                break  # its last date did not move, so nothing after it moves
            replaced[block.phase_number] = replace(
                block, start_date=new_start.isoformat(),
                date_overrides=_move_dated(block.date_overrides, block_start, new_start,
                                           lambda old: old, positions=True),
                shift_reasons=_move_dated(block.shift_reasons, block_start, new_start,
                                          lambda old: old, positions=False),
            )

    result = [replaced.get(p.phase_number, p) for p in phases]
    problem = _alignment_problem(result)
    if problem:
        return None, problem
    return result, None


def _next_unjudged_week(phases: list[Phase], this_monday: date) -> tuple[date, Phase] | None:
    """The earliest ENDED week, on or after RULE_FROM, that no block has judged."""
    best: tuple[date, Phase] | None = None
    for phase in phases:
        if phase.status == "completed":
            continue
        start = _start(phase)
        for index in range(phase.length_days // 7):
            monday = start + timedelta(days=7 * index)
            if monday < RULE_FROM or monday >= this_monday:
                continue
            if monday.isoformat() in phase.week_results:
                continue
            if best is None or monday < best[0]:
                best = (monday, phase)
            break
    return best


def _record(phases: list[Phase], phase_number: int, monday: date, outcome: str) -> list[Phase]:
    return [replace(p, week_results={**p.week_results, monday.isoformat(): outcome})
            if p.phase_number == phase_number else p for p in phases]


def apply_failed_week_rule(phases: list[Phase], logged_dates, today: date, *,
                           meta: dict | None = None) -> tuple[list[Phase], list[tuple[str, str]]]:
    """Judge every ended, unjudged week from RULE_FROM on, oldest first, and
    repeat each failed one.

    Returns (phases, [(week Monday, outcome), ...]). When nothing was due the
    list handed in comes back as the same object, so a caller can tell that
    nothing needs writing without comparing.

    Oldest first matters when weeks pile up unjudged (the app not opened for a
    fortnight): a repeat moves every later week, so the week after a failed
    one is only known once the failure has been applied.
    """
    this_monday = _monday(today)
    current = phases
    events: list[tuple[str, str]] = []
    while True:
        due = _next_unjudged_week(current, this_monday)
        if due is None:
            break
        monday, phase = due
        count = days_logged(logged_dates, monday)
        if count > _ml.FAILED_WEEK_MAX_DAYS:
            outcome = f"{PASSED_PREFIX} — {count} of 7 days logged"
            current = _record(current, phase.phase_number, monday, outcome)
        else:
            outcome = f"{FAILED_PREFIX} — {count} of 7 days logged, repeated the week after"
            repeated, refusal = repeat_week(current, monday, outcome, meta=meta)
            if repeated is None:
                outcome = (f"{FAILED_PREFIX} — {count} of 7 days logged, not repeated: "
                           f"{refusal}")
                current = _record(current, phase.phase_number, monday, outcome)
            else:
                current = repeated
        events.append((monday.isoformat(), outcome))
    return current, events


def redo_this_week(phases: list[Phase], logged_dates, today: date, *,
                   meta: dict | None = None) -> tuple[list[Phase] | None, str | None]:
    """The athlete's own redo: next week runs THIS week again.

    Recorded against this week as redone by choice, so when the week ends the
    automatic rule sees it already judged and does not repeat it a second time,
    however few days it ends with.
    """
    monday = _monday(today)
    block = covering_phase(phases, monday)
    if block is not None and monday.isoformat() in block.week_results:
        return None, "this week is already set to run again"
    count = days_logged(logged_dates, monday)
    return repeat_week(phases, monday,
                       f"{REDONE_PREFIX} — {count} of 7 days logged when chosen",
                       meta=meta)


def consequences(before: list[Phase], after: list[Phase]) -> list[str]:
    """What a repeat changes, in plain sentences for the confirm step: which
    block moves, to when, and what a fixed-end block gives up to stay put."""
    lines = []
    old = {p.phase_number: p for p in before}
    for phase in after:
        was = old.get(phase.phase_number)
        if was is None or was == replace(phase, week_results=was.week_results):
            continue
        if phase.start_date != was.start_date:
            lines.append(f"{phase.name} starts {_long_date(_start(phase))} instead of "
                         f"{_long_date(_start(was))}.")
        if phase.length_days < was.length_days:
            lines.append(f"{phase.name} still ends on "
                         f"{_long_date(_plan.phase_end_date(phase))}, so it has "
                         f"{phase.length_days // 7} weeks instead of {was.length_days // 7}.")
        elif phase.length_days > was.length_days:
            lines.append(f"{phase.name} runs to {_long_date(_plan.phase_end_date(phase))} "
                         f"instead of {_long_date(_plan.phase_end_date(was))}.")
    return lines


def repeat_notice(phases: list[Phase], today: date) -> str | None:
    """The line that explains a repeated week on the week it runs — why it
    repeats, and when the next block now starts. None in an ordinary week."""
    block = covering_phase(phases, today)
    if block is None or not _plan.is_repeat_week(block, today):
        return None
    last_week = (_monday(today) - timedelta(days=7)).isoformat()
    outcome = block.week_results.get(last_week, "")
    found = _DAYS_RE.search(outcome)
    if outcome.startswith(FAILED_PREFIX) and found:
        days = int(found.group(1))
        text = (f"Last week had {days} of 7 days logged, so it failed. "
                f"This week runs it again.")
    elif outcome.startswith(REDONE_PREFIX):
        text = "This week runs last week again, as you chose."
    else:
        text = "This week runs an earlier week again."
    end = _plan.phase_end_date(block)
    following = sorted((p for p in phases if p.status != "completed"
                        and _start(p) > end), key=_start)
    if following:
        nxt = following[0]
        text += f" {nxt.name} starts Monday {_long_date(_start(nxt))}."
    return text
