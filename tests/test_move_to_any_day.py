"""A session moved to any later day of its week (2026-11-11).

The athlete: "if I move Friday training of this week C to tomorrow, the Friday
becomes the rest day and mobility goes to tomorrow evening instead of tonight,
and D training stays on Saturday morning ... It needs to be able to handle
it." The app could swap a day only with today. The two days now trade their
plan days whatever the target, so the day left behind gets what the target
held, and every rule that reads the stored week (the evening mobility session
among them) follows the move. The week check stays at the write (Key Rule 18b).
"""
from datetime import date, timedelta

from services import plan as ph
from services import scheduling as sch
from services import sessions as sess

MONDAY = date(2026, 10, 19)
TUE, WED, THU, FRI, SAT, SUN = (MONDAY + timedelta(days=i) for i in range(1, 7))
PHASE = sess.build_phase(5, MONDAY)
PLAN = sess.calendar_plan(PHASE)


def test_the_targets_are_the_later_days_of_the_same_week():
    assert sch.manual_move_targets(PHASE, THU, TUE) == [WED, FRI, SAT, SUN]
    assert sch.manual_move_targets(PHASE, THU, SAT) == [SUN]
    assert sch.manual_move_targets(PHASE, SUN, SUN) == []
    # A day of next week moves inside next week only.
    next_thu = THU + timedelta(days=7)
    targets = sch.manual_move_targets(PHASE, next_thu, TUE)
    assert targets and all(MONDAY + timedelta(days=7) <= d <= SUN + timedelta(days=7)
                           for d in targets)


def test_the_two_days_trade_their_plan_days_and_today_is_untouched():
    overrides, reasons = sch.manual_swap_entries(PHASE, THU, TUE, target=WED)
    assert overrides == {THU.isoformat(): 3, WED.isoformat(): 4}
    assert reasons == {THU.isoformat(): f"Swapped with {WED.isoformat()} by choice",
                       WED.isoformat(): f"Swapped with {THU.isoformat()} by choice"}
    kept, rejected = ph.reject_violating_overrides(PHASE, overrides)
    assert not rejected and kept == overrides


def test_without_a_target_it_is_the_swap_with_today():
    assert sch.manual_swap_entries(PHASE, THU, TUE) == sch.manual_swap_entries(
        PHASE, THU, TUE, target=TUE)
    assert sch.manual_swap_blockers(PHASE, THU, TUE, set()) == []


def test_what_blocks_a_move():
    assert sch.manual_swap_blockers(PHASE, THU, WED, set(), target=TUE) == [
        "A session can move only to today or a later day."]
    assert sch.manual_swap_blockers(PHASE, THU, TUE, set(), target=THU) == [
        "Pick a different day to move the session to."]
    assert sch.manual_swap_blockers(PHASE, THU, TUE, {THU.isoformat()}, target=WED) == [
        "That day already has a logged session — there is nothing to move."]
    assert sch.manual_swap_blockers(PHASE, THU, TUE, set(), target=WED) == []


def test_the_warnings_read_the_week_after_the_move():
    """C on Wednesday sits the day after Tuesday's B: two hard days back to
    back, said and never blocked. C on Saturday sits after Friday's D."""
    back_to_back = "This puts two hard training days back to back — the plan keeps them apart."
    assert back_to_back in sch.manual_swap_warnings(PHASE, PLAN, THU, TUE, target=WED)
    assert back_to_back in sch.manual_swap_warnings(PHASE, PLAN, THU, TUE, target=SAT)


def test_the_names_of_what_a_day_holds():
    assert sch.day_name(PLAN[4]) == "session C"
    assert sch.day_name(PLAN[3]) == "rest day"
    assert sch.day_name(None) == "rest day"
    assert sch.day_name(PLAN[7]) == "the flexibility session"
