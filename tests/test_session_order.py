"""Which exercises may change places when equipment is in use (WP-27, 2026-10-22).

The owner's note: "Ability to switch the order of the exercises if the machine
isn't available". services/session_order.move_groups reads the order rule's
own sections (placement.order over goal_week's cards); the phone moves whole
groups of the walked steps and decides no order itself.
"""

from __future__ import annotations

import goal_block as gb
from services import session_order as so


def _by_name(letter: str, exercises=None) -> dict[str, dict]:
    exercises = exercises if exercises is not None else gb.SESSIONS[letter]
    return {e["name"]: m for e, m in zip(exercises, so.move_groups(exercises))}


def test_a_ramp_set_moves_with_its_lift():
    for letter in ("B", "C", "D"):
        moves = _by_name(letter)
        for ramp, lift in (("Romanian Deadlift (Ramp Set)", "Romanian Deadlift (DB)"),
                           ("Hack Squat (Ramp Set)", "Hack Squat")):
            if ramp in moves:
                assert moves[ramp]["group"] == moves[lift]["group"], (letter, ramp)
                assert moves[ramp]["movable"] and moves[lift]["movable"]


def test_the_warm_up_and_the_press_lead_in_never_move():
    a = _by_name("A")
    for name in ("Standing Psoas March", "Pec & Scar Release (Right)", "Single-Arm Cable Y Raise"):
        assert not a[name]["movable"], name
    for name in ("Walking Lunge (DB)", "Machine Chest Press", "Machine Shoulder Press",
                 "Reverse Cable Crossover", "Adductor Machine (Seated)"):
        assert a[name]["movable"], name


def test_the_end_items_keep_their_place_and_may_run_earlier_when_picked():
    """2026-11-19 (WP-49), his note from the adductor machine on 11-17: "All I wanted
    was to change the adductor machine with the cable crunch ? but I couldnt". Every
    item at the end (the abs, the hip work, the farmer walk) keeps its place and may
    run earlier; from 2026-11-07 only the farmer walk could ("there was no option to
    go to farmer walk")."""
    import goal_week as gw
    end = {c.name for c in list(gw.CARDS) + list(gw.BONUS_ORDER) if c.section == "last"}
    assert {"Lat-Pulldown Cable Crunch (Facing Away)", "Hip Airplane (Weighted)",
            "Farmer Walk (DB)", "Reverse Crunch (Ab Mat)"} <= end
    for letter in "ABCD":
        moves = _by_name(letter)
        order = list(moves)
        last_main = max(i for i, n in enumerate(order) if n not in end and moves[n]["movable"])
        for name in end & set(moves):
            # Still at the end of the session, after every other lift ...
            assert order.index(name) > last_main, (letter, name)
            # ... and offered when a machine is in use: it waits for nothing.
            assert moves[name]["movable"] and moves[name]["after"] == [], (letter, name)
    a = _by_name("A")
    assert list(a).index("Adductor Machine (Seated)") < list(a).index("Lat-Pulldown Cable Crunch (Facing Away)")


def test_a_press_runs_only_after_the_release_and_the_y_raise():
    for letter in ("A", "C"):
        moves = _by_name(letter)
        lead_in = {moves["Pec & Scar Release (Right)"]["group"], moves["Single-Arm Cable Y Raise"]["group"]}
        for press in ("Machine Chest Press", "Machine Shoulder Press"):
            if press in moves:
                assert set(moves[press]["after"]) == lead_in, (letter, press)
    # The crossover is no press: it waits for nothing (Monday and Friday since
    # WP-47, his choice of 2026-11-03: "Move crossover to D").
    for letter in ("A", "D"):
        assert _by_name(letter)["Reverse Cable Crossover"]["after"] == [], letter


def test_the_timed_plank_test_never_moves():
    moves = _by_name("A", gb._with_plank_test(gb.SESSIONS["A"]))
    timed = [n for n in moves if n.endswith("(Timed)")]
    assert len(timed) == 5 and not any(moves[n]["movable"] for n in timed)


def test_an_exercise_no_card_names_never_moves():
    exercises = [{"name": "Made-up lift", "type": "reps"}, {"name": "Another one", "type": "reps"}]
    assert [m["movable"] for m in so.move_groups(exercises)] == [False, False]


def test_the_session_plan_carries_the_groups_and_the_accessory_session_none():
    """compose() puts each exercise's group in the answer; the accessory session's
    items are not the block's cards, so it sends none."""
    import inspect

    from services import training_session as tsession
    src = inspect.getsource(tsession.compose)
    assert "session_order.move_groups(dosed) if kind == PLAN" in src
    assert '"move": move' in inspect.getsource(tsession.exercise_out)
