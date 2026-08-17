"""
tests/test_hold_timer_endings.py — the last timer of a run must not sound
like the ones before it.

Athlete's request, 2026-08-17: on the McGill Curl-Up, the Dead Bug and the
side bridge, the LAST timer of the set should ring differently so he knows the
set is over and rest has begun; on the Single-Leg Glute Bridge, the last timer
of the RIGHT side should ring differently so he knows to swap. "This goes for
all timers where they are the exercise."

WHY IT IS A CORRECTNESS PROBLEM AND NOT A PREFERENCE. He is holding a side
bridge with his eyes shut; the bell is the only channel telling him what
happens next. One bell for "another rep", "swap sides" and "that's the set"
makes all three the same instruction, so the only way to find out is to open
his eyes and look — mid-hold, which is when the position is hardest to keep.

The bell therefore has to agree with what the completion handler actually
does next. These tests pin that agreement, because the two are computed in
different places and a bell that promises the wrong thing is worse than one
that says nothing.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "views" / "training.py"
_SRC = _PATH.read_text(encoding="utf-8")


# ─── the three signals exist and are distinguishable ──────────────────────

def test_the_three_endings_are_named_constants():
    from views import training as V

    assert V.HOLD_ENDINGS == ("continue", "switch", "finish")


def test_each_ending_has_its_own_bell():
    for fn in ("_bellDouble", "_bellSwitch", "_bellFinish"):
        assert f"function {fn}()" in _SRC, f"{fn} missing from the shared audio block"


def _bell_pitches(fn_name: str) -> list[float]:
    """The root frequency of each _bellStrike inside `fn_name`, in order."""
    body = re.search(rf"function {fn_name}\(\)\s*{{(.*?)\n}}", _SRC, re.S)
    assert body, f"could not read {fn_name}"
    return [float(m) for m in re.findall(r"_bellStrike\(\s*([0-9.]+)", body.group(1))]


def test_continue_rises_and_switch_falls():
    """Contour is what carries the message over gym noise — the two are the
    same interval in opposite directions, so they are told apart by direction
    rather than by remembering two unrelated jingles."""
    rising = _bell_pitches("_bellDouble")
    falling = _bell_pitches("_bellSwitch")
    assert rising == sorted(rising), "continue must ascend"
    assert falling == sorted(falling, reverse=True), "switch must descend"
    assert set(rising) == set(falling), "same two notes, reversed"


def test_finish_is_three_strikes_and_descends_furthest():
    """Three-and-descending cannot be mistaken for either pair, even if the
    first strike is missed."""
    finish = _bell_pitches("_bellFinish")
    assert len(finish) == 3, "finish is three strikes"
    assert finish == sorted(finish, reverse=True), "finish must descend"
    assert finish[-1] < min(_bell_pitches("_bellSwitch")), (
        "finish must end lower than the switch pair, so the end of a set is "
        "unmistakably the lowest thing you hear"
    )


def test_all_three_are_distinct_sequences():
    seqs = [tuple(_bell_pitches(f)) for f in
            ("_bellDouble", "_bellSwitch", "_bellFinish")]
    assert len(set(seqs)) == 3, f"two endings sound identical: {seqs}"


# ─── the timer dispatches on the ending ───────────────────────────────────

def test_the_timer_rejects_an_unknown_ending():
    """A typo must not silently fall through to a bell that means something
    else."""
    from views import training as V

    with pytest.raises(ValueError, match="unknown hold ending"):
        V._hold_timer(30, ending="nearly-done")


def test_the_default_ending_promises_nothing():
    """A caller that forgets to pass one gets 'another rep follows', and the
    athlete looks at the screen. Defaulting to FINISH would announce a set was
    over when it was not — the mistake that actually costs a rep."""
    import inspect

    from views import training as V

    default = inspect.signature(V._hold_timer).parameters["ending"].default
    assert default == V.HOLD_ENDING_CONTINUE


def test_done_beep_branches_on_all_three():
    beep = re.search(r"function _doneBeep\(\)\s*\{\{(.*?)\n\}\}", _SRC, re.S)
    assert beep, "could not read _doneBeep"
    body = beep.group(1)
    for fn in ("_bellSwitch", "_bellFinish", "_bellDouble"):
        assert fn in body, f"_doneBeep never plays {fn}"


def test_the_notification_text_tracks_the_bell():
    """A phone that DID surface the notification must say the same thing the
    ear was told."""
    beep = re.search(r"function _doneBeep\(\)\s*\{\{(.*?)\n\}\}", _SRC, re.S)
    notes = re.findall(r"_notify\('([^']+)'", beep.group(1))
    assert len(notes) == 3 and len(set(notes)) == 3, (
        f"each ending needs its own notification, got {notes}"
    )


# ─── the bell agrees with what happens next ───────────────────────────────

def _ending_for_hold(is_uni: bool, side: str) -> str:
    """Mirror of the `hold` branch: one hold IS one set, so the only
    mid-exercise ending is the side swap."""
    from views import training as V

    return (V.HOLD_ENDING_SWITCH if (is_uni and side == "right")
            else V.HOLD_ENDING_FINISH)


def _ending_for_hold_reps(cur_rep: int, reps: int, is_uni: bool, side: str) -> str:
    from views import training as V

    if cur_rep < reps:
        return V.HOLD_ENDING_CONTINUE
    if is_uni and side == "right":
        return V.HOLD_ENDING_SWITCH
    return V.HOLD_ENDING_FINISH


@pytest.mark.parametrize("cur_rep,expected", [
    (1, "continue"), (7, "continue"), (8, "finish"),
])
def test_mcgill_curl_up_ends_the_set_on_rep_8(cur_rep, expected):
    """8 reps, bilateral — the case named in the request."""
    assert _ending_for_hold_reps(cur_rep, 8, is_uni=False, side="right") == expected


@pytest.mark.parametrize("cur_rep,side,expected", [
    (7, "right", "continue"),
    (8, "right", "switch"),     # <- "the right side last set"
    (7, "left", "continue"),
    (8, "left", "finish"),
])
def test_single_leg_glute_bridge_swaps_after_the_right_side(cur_rep, side, expected):
    """8 reps, unilateral. Rep 8 on the RIGHT means swap, NOT stop — getting
    this one backwards would end the exercise halfway through."""
    assert _ending_for_hold_reps(cur_rep, 8, is_uni=True, side=side) == expected


@pytest.mark.parametrize("side,expected", [("right", "switch"), ("left", "finish")])
def test_full_side_bridge_is_one_hold_per_side(side, expected):
    """type='hold', unilateral: the hold IS the set, so right swaps and left
    finishes."""
    assert _ending_for_hold(is_uni=True, side=side) == expected


def test_a_bilateral_hold_always_finishes():
    assert _ending_for_hold(is_uni=False, side="right") == "finish"


def test_an_alternating_exercise_never_signals_a_side_swap():
    """Dead Bug is laterality='alternating', not 'unilateral' — is_uni is
    False, so it alternates within the rep rather than running a side block.
    A swap bell there would be an instruction to do something the flow does
    not offer."""
    for rep in (1, 4, 8):
        assert _ending_for_hold_reps(rep, 8, is_uni=False, side="right") != "switch"


# ─── the real plan content routes correctly ───────────────────────────────

def test_every_timed_exercise_in_the_live_plans_gets_a_reachable_ending():
    """Walks the authored blocks rather than a fixture, so a future exercise
    with a new shape cannot quietly land on the wrong bell."""
    import training_plan as tp

    from views import training as V

    seen = set()
    for plan_name in ("PLAN", "PLAN_STAGE2", "PLAN_STAGE2B"):
        for content in (getattr(tp, plan_name, None) or {}).values():
            for ex in (content.get("exercises") or []):
                if ex.get("type") not in ("hold", "hold_reps"):
                    continue
                is_uni = ex.get("laterality") == "unilateral"
                if ex["type"] == "hold":
                    endings = {_ending_for_hold(is_uni, s) for s in ("right", "left")}
                else:
                    reps = ex.get("reps_in_set", 5)
                    endings = {_ending_for_hold_reps(r, reps, is_uni, s)
                               for r in range(1, reps + 1) for s in ("right", "left")}
                assert endings <= set(V.HOLD_ENDINGS), ex["name"]
                # Every timed exercise must have exactly one way to END, or the
                # athlete never learns that the set is over.
                assert V.HOLD_ENDING_FINISH in endings, ex["name"]
                if is_uni:
                    assert V.HOLD_ENDING_SWITCH in endings, (
                        f"{ex['name']} is unilateral and must signal the swap")
                seen.add(ex["name"])
    assert len(seen) >= 8, f"expected the timed catalogue, walked only {len(seen)}"


def test_both_hold_timer_call_sites_pass_an_ending():
    """The default is safe but silent; a call site that forgets one would
    never announce the end of its set."""
    tree = ast.parse(_SRC)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_hold_timer"]
    assert len(calls) == 2, f"expected 2 call sites, found {len(calls)}"
    for c in calls:
        assert any(kw.arg == "ending" for kw in c.keywords), (
            "every _hold_timer call must state which bell it ends on")
