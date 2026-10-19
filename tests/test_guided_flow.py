"""The guided training flow as one pure step (services/guided_flow.py, move
TRN-9, 2026-10-19), and three faults fixed with it:

- F18: the "+" menu (yoga, hike, accessory) was drawn during a session.
- F20: the overview, the time estimate and the save screen's review showed
  the plan's values while the flow ran today's dosed ones.
- F26: after a save, choosing the watch activity for the heart-rate match
  read a length defined only before the save; the error was caught and the
  choice vanished without a match.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import goal_block as gb
from services import guided_flow as gf
from services import sessions as sess

ROOT = Path(__file__).resolve().parents[1]
FIRST, SECOND = "left", "right"


def _ex(ex_type="reps", sets=2, uni=False, reps_in_set=3):
    ex = {"name": "X", "type": ex_type, "sets": sets}
    if uni:
        ex["laterality"] = "unilateral"
    if ex_type == "hold_reps":
        ex["reps_in_set"] = reps_in_set
    if ex_type == "duration":
        ex["duration_minutes"] = 15
    return ex


def _go(pos, ex, event):
    return gf.step(pos, ex, event, first=FIRST)


def test_a_two_set_lift_records_each_set_once_and_rests_between():
    ex, pos = _ex(), gf.start(FIRST)
    one = _go(pos, ex, gf.COMPLETE)
    assert one.record_set == 1 and one.rest_begins
    assert one.position == gf.Position(0, 2, 1, gf.RESTING, FIRST)
    back = _go(one.position, ex, gf.NEXT_SET)
    assert back.rest_ends and back.record_set is None
    assert back.position == gf.Position(0, 2, 1, gf.INTRO, FIRST)
    two = _go(back.position, ex, gf.COMPLETE)
    assert two.record_set == 2 and not two.rest_begins
    assert two.position == gf.Position(1, 1, 1, gf.INTRO, FIRST), "on to the next exercise"


def test_a_one_side_set_is_recorded_after_both_sides():
    ex = _ex(uni=True, sets=1)
    first = _go(gf.start(FIRST), ex, gf.COMPLETE)
    assert first.record_set is None and first.position.side == SECOND
    second = _go(first.position, ex, gf.COMPLETE)
    assert second.record_set == 1 and second.position.ex_idx == 1
    assert second.position.side == FIRST, "the next exercise starts on the day's first side"


def test_held_reps_count_up_then_switch_side_then_end_the_set():
    ex, pos = _ex("hold_reps", sets=2, uni=True, reps_in_set=2), gf.start(FIRST)
    pos = _go(pos, ex, gf.COMPLETE).position
    assert (pos.rep, pos.side) == (2, FIRST)
    pos = _go(pos, ex, gf.COMPLETE).position
    assert (pos.rep, pos.side) == (1, SECOND)
    pos = _go(pos, ex, gf.COMPLETE).position
    end = _go(pos, ex, gf.COMPLETE)
    assert end.record_set == 1 and end.rest_begins
    assert end.position == gf.Position(0, 2, 1, gf.RESTING, FIRST)


def test_an_activity_and_a_skip_move_straight_on():
    assert _go(gf.start(FIRST), _ex("duration"), gf.COMPLETE) == gf.Step(
        gf.Position(1, 1, 1, gf.INTRO, FIRST), record_set=1)
    mid = gf.Position(3, 2, 2, gf.RESTING, SECOND)
    assert _go(mid, _ex(), gf.SKIP) == gf.Step(gf.Position(4, 1, 1, gf.INTRO, FIRST))


def test_an_event_the_position_does_not_take_is_refused():
    with pytest.raises(ValueError):
        _go(gf.start(FIRST), _ex(), gf.NEXT_SET)
    with pytest.raises(ValueError):
        _go(gf.Position(0, 2, 1, gf.RESTING, FIRST), _ex(), gf.COMPLETE)
    with pytest.raises(ValueError):
        _go(gf.start(FIRST), _ex(), "jump")


@pytest.mark.parametrize("ex_type", ["hold", "hold_reps"])
@pytest.mark.parametrize("uni", [False, True])
def test_the_bell_announces_what_the_tap_then_does(ex_type, uni):
    """sessions.hold_ending is the hold timer's bell. In every position it
    must name what the next "complete" does."""
    total, reps = 3, 2
    ex = _ex(ex_type, sets=total, uni=uni, reps_in_set=reps)
    for set_num in range(1, total + 1):
        for side in ((FIRST, SECOND) if uni else (FIRST,)):
            for rep in range(1, (reps if ex_type == "hold_reps" else 1) + 1):
                pos = gf.Position(0, set_num, rep, gf.INTRO, side)
                ending = sess.hold_ending(ex_type, is_uni=uni, side=side, cur_set=set_num,
                                          total_sets=total, cur_rep=rep, reps_per_set=reps,
                                          first=FIRST)
                nxt = _go(pos, ex, gf.COMPLETE)
                where = (ex_type, uni, set_num, side, rep, ending)
                if ending == sess.HOLD_ENDING_CONTINUE:
                    assert nxt.position.rep == rep + 1 and nxt.record_set is None, where
                elif ending == sess.HOLD_ENDING_SWITCH:
                    assert nxt.position.side == SECOND and nxt.record_set is None, where
                elif ending == sess.HOLD_ENDING_FINISH:
                    assert nxt.record_set == set_num and nxt.rest_begins, where
                    assert nxt.position.ex_idx == 0, where
                else:
                    assert ending == sess.HOLD_ENDING_DONE, where
                    assert nxt.record_set == set_num and nxt.position.ex_idx == 1, where


def test_a_whole_day_records_every_set_exactly_once():
    """Walk the 12-week block's day 1 from start to finish with taps only."""
    block = sess.calendar_plan(sess.build_phase(5, gb.START))
    exercises = [sess.readiness_dose(ex, 1.0) for ex in block[1]["exercises"]]
    assert len(exercises) > 5
    pos, recorded, taps = gf.start(FIRST), {}, 0
    while not gf.finished(pos, len(exercises)):
        event = gf.NEXT_SET if pos.phase == gf.RESTING else gf.COMPLETE
        nxt = gf.step(pos, exercises[pos.ex_idx], event, first=FIRST)
        if nxt.record_set is not None:
            recorded.setdefault(pos.ex_idx, []).append(nxt.record_set)
        pos, taps = nxt.position, taps + 1
        assert taps < 2000, "the walk never ends"
    for i, ex in enumerate(exercises):
        expected = [1] if ex["type"] == "duration" else list(range(1, ex.get("sets", 1) + 1))
        assert recorded.get(i) == expected, (i, ex["name"])


def test_a_rest_is_measured_and_put_on_the_set_it_followed():
    assert gf.rest_taken(1000.0, 1090.0) == 90
    assert gf.rest_taken(0, 1090.0) is None, "no rest was timed"
    assert gf.rest_taken(1000.0, 1000.0 + gf.REST_TAKEN_MAX_SECONDS + 1) is None
    rows = [{"set_num": 1}, {"set_num": 2}]
    gf.attach_rest(rows, 75)
    assert rows == [{"set_num": 1}, {"set_num": 2, "rest_taken_seconds": 75}]
    gf.attach_rest(rows, None)
    gf.attach_rest([], 60)
    assert rows[1]["rest_taken_seconds"] == 75


def test_no_add_menu_during_a_session():
    assert sess.add_menu_shown(started=False, logged=False, accessory_running=False)
    assert not sess.add_menu_shown(started=True, logged=False, accessory_running=False), "F18"
    assert sess.add_menu_shown(started=True, logged=True, accessory_running=False)
    assert not sess.add_menu_shown(started=False, logged=False, accessory_running=True)
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "if _menu_ok:\n        _render_add_training_fab()" in src


def test_the_overview_and_the_review_show_today_s_dose():
    ex = {"name": "Goblet Squat", "type": "reps", "sets": 3, "reps": 10, "weight_kg": 22.5}
    dosed = sess.dosed_day([ex], 0.67)
    assert dosed == [sess.readiness_dose(ex, 0.67)]
    rows = [{"set_num": 1, "weight": 10.0, "is_warmup": True}, {"set_num": 2, "weight": 25.0}]
    review = sess.review_figures(dosed[0], rows, None)
    assert review["weight_kg"] == 25.0, "the weight done, not the plan's"
    assert review["sets"] == dosed[0]["sets"] and review["time_label"] == "Time (estimated)"
    assert sess.review_figures(dosed[0], [], 31.6)["minutes"] == 32
    assert sess.review_figures({"type": "hold", "sets": 2}, [], None)["weight_kg"] is None


def test_the_heart_rate_rematch_reads_the_saved_minutes():
    assert "tp_saved_minutes" in sess.CHECKPOINT_FIELDS
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "st.session_state.tp_saved_minutes = elapsed_minutes" in src
    assert 'duration_minutes=st.session_state.get("tp_saved_minutes")' in src


# ─── walk: the session's positions, precomputed for the phone ────────────────

def test_the_walk_is_the_step_function_applied_in_order():
    """Every entry's event, applied with step(), leads to the next entry's
    position, and the last entry's event finishes the session: the phone
    walking the list does exactly what the page's taps do."""
    block = sess.calendar_plan(sess.build_phase(5, gb.START))
    exercises = [sess.readiness_dose(ex, 1.0) for ex in block[1]["exercises"]]
    entries = gf.walk(exercises, FIRST)
    positions = [gf.Position(e["ex_idx"], e["set_num"], e["rep"], e["phase"], e["side"])
                 for e in entries]
    assert positions[0] == gf.start(FIRST)
    for i, (pos, entry) in enumerate(zip(positions, entries)):
        nxt = gf.step(pos, exercises[pos.ex_idx], entry["event"], first=FIRST)
        assert (entry["record_set"], entry["rest_begins"], entry["rest_ends"]) == (
            nxt.record_set, nxt.rest_begins, nxt.rest_ends), i
        if i + 1 < len(entries):
            assert nxt.position == positions[i + 1], i
        else:
            assert gf.finished(nxt.position, len(exercises))


def test_skip_leads_to_the_next_exercise_first_entry():
    exercises = [_ex("reps", sets=2), _ex("hold", sets=1, uni=True), _ex("duration")]
    entries = gf.walk(exercises, FIRST)
    for entry in entries:
        skipped = gf.step(gf.Position(entry["ex_idx"], entry["set_num"], entry["rep"],
                                      entry["phase"], entry["side"]),
                          exercises[entry["ex_idx"]], gf.SKIP, first=FIRST).position
        if entry["skip_to"] < len(entries):
            target = entries[entry["skip_to"]]
            assert (target["ex_idx"], target["set_num"], target["rep"], target["phase"],
                    target["side"]) == (skipped.ex_idx, 1, 1, gf.INTRO, FIRST)
        else:
            assert gf.finished(skipped, len(exercises))


def test_each_hold_entry_carries_the_bell_its_tap_then_keeps():
    exercises = [_ex("hold_reps", sets=2, uni=True, reps_in_set=2)]
    for entry in gf.walk(exercises, FIRST):
        if entry["phase"] == gf.RESTING:
            assert entry["ending"] is None and entry["event"] == gf.NEXT_SET
            continue
        assert entry["ending"] == sess.hold_ending(
            "hold_reps", is_uni=True, side=entry["side"], cur_set=entry["set_num"],
            total_sets=2, cur_rep=entry["rep"], reps_per_set=2, first=FIRST)
