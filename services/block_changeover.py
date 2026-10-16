"""The 12-week block replaces Block B — the changeover, stored once.

The athlete, 2026-10-16: "When we push this new session block that will be 12
weeks long, it will overwrite all of the current block, so just wait till we
have all steps finished. Starts once we complete all steps and push and it
starts on the next monday."

So on START (goal_block.START, the Monday after the push) the stored phases
change in one step:

  * Block B (phase 4) is shortened to end on the Sunday before START. Its
    days from START on are dropped with their moves; the weeks it ran stay
    exactly as they were, so every logged session keeps its day number.
  * Its last week is recorded as not judged. Otherwise the failed-week rule
    (Key Rule 22) could judge it failed and repeat it, which moves every later
    block a week — the new block would not start on START.
  * The 12-week block (phase 5) is placed on START, "upcoming" until then.

Not ask-first: the athlete decided it, and the push is his go. It returns None
once phase 5 is stored, so the training page that runs it writes it once.
No I/O and no Streamlit.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import goal_block as gb
from services import plan
from services import sessions as sess
from services.models import Phase

OLD_PHASE = 4
NEW_PHASE = 5
#: What Block B's last week records instead of a verdict.
REPLACED_OUTCOME = ("Not judged — Block B ends here; the 12-week block starts the "
                    "Monday after (athlete, 2026-10-16)")


def changeover(phases: list[Phase], start: date) -> list[Phase] | None:
    """The phase list with Block B shortened to end the day before `start`
    and the 12-week block placed on `start`; None when there is nothing to do
    (the block is stored already, or there is no Block B to replace)."""
    if start.weekday() != 0:
        raise ValueError(f"the 12-week block starts on a Monday, not {start:%A %Y-%m-%d}")
    if any(p.phase_number == NEW_PHASE for p in phases):
        return None
    old = next((p for p in phases if p.phase_number == OLD_PHASE), None)
    if old is None:
        return None
    old_start = date.fromisoformat(old.start_date)
    keep = (start - old_start).days
    if keep <= 0 or keep % 7:
        raise ValueError(f"Block B starts {old_start}; the 12-week block cannot start {start}")

    end = start - timedelta(days=1)
    if keep < old.length_days:
        weeks = keep // 7
        old = replace(
            old,
            length_days=keep,
            week_plan=None if old.week_plan is None else list(old.week_plan[:weeks]),
            date_overrides={d: n for d, n in old.date_overrides.items()
                            if date.fromisoformat(d) <= end},
            shift_reasons={d: r for d, r in old.shift_reasons.items()
                           if date.fromisoformat(d) <= end},
        )
    last_monday = end - timedelta(days=6)
    if plan.phase_end_date(old) == end and last_monday.isoformat() not in old.week_results:
        old = replace(old, week_results={**old.week_results,
                                         last_monday.isoformat(): REPLACED_OUTCOME})
    kept = [old if p.phase_number == OLD_PHASE else p for p in phases]
    new = sess.build_phase(NEW_PHASE, start, status="upcoming")
    return sess.begin_new_phase(kept, new)


def due(phases: list[Phase]) -> list[Phase] | None:
    """The changeover on the block's own start date (goal_block.START)."""
    return changeover(phases, gb.START)
