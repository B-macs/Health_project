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
    for fn in ("_bellContinue", "_bellSwitch", "_bellFinish"):
        assert f"function {fn}()" in _SRC, f"{fn} missing from the shared audio block"


def _bell_pitches(fn_name: str) -> list[float]:
    """The root frequency of each _bellStrike inside `fn_name`, in order."""
    body = re.search(rf"function {fn_name}\(\)\s*{{(.*?)\n}}", _SRC, re.S)
    assert body, f"could not read {fn_name}"
    return [float(m) for m in re.findall(r"_bellStrike\(\s*([0-9.]+)", body.group(1))]


def test_the_endings_are_counted_one_two_three():
    """The primary signal is HOW MANY strikes, not which pitches: counting
    survives gym noise, one earbud and a half-heard first strike, where
    remembering whether a pair rose or fell does not."""
    assert len(_bell_pitches("_bellContinue")) == 1, "another rep = one strike"
    assert len(_bell_pitches("_bellSwitch")) == 2, "swap sides = two strikes"
    assert len(_bell_pitches("_bellFinish")) == 3, "set over = three strikes"


def test_both_stopping_signals_fall():
    """Reinforcement, not the signal itself — nothing depends on hearing it."""
    for fn in ("_bellSwitch", "_bellFinish"):
        p = _bell_pitches(fn)
        assert p == sorted(p, reverse=True), f"{fn} must descend"


def test_the_continue_bell_dies_before_the_next_rep_starts():
    """THE DEAD BUG DEFECT. The old completion bell rang 2.06s while the next
    rep auto-starts 0.7s later, so on a 3-second hold every bell was still
    sounding through the following rep's ticks — eight reps of one continuous
    smear, with nothing for the last bell to stand out against."""
    body = re.search(r"function _bellContinue\(\)\s*\{(.*?)\n\}", _SRC, re.S).group(1)
    strikes = re.findall(r"_bellStrike\(\s*[0-9.]+,\s*([0-9.]+),\s*[0-9.]+,\s*([0-9.]+)\)", body)
    assert strikes, "could not read the continue strike"
    gap = float(re.search(r"_AUTOSTART_GAP_S = ([0-9.]+)", _SRC).group(1))
    ring_out = max(float(off) + float(dur) for off, dur in strikes)
    assert ring_out <= gap, (
        f"continue bell rings {ring_out}s but the next rep starts in {gap}s — "
        f"it will bleed into the following rep and the count becomes unreadable"
    )


def test_the_stopping_bells_may_ring_on():
    """Both are followed by silence (the other side's timer, or rest), so the
    long ring-out that would smear a rep is exactly what makes them carry."""
    for fn in ("_bellSwitch", "_bellFinish"):
        body = re.search(rf"function {fn}\(\)\s*\{{(.*?)\n\}}", _SRC, re.S).group(1)
        longest = max(float(d) for d in re.findall(r",\s*([0-9.]+)\)\s*;", body))
        assert longest > 1.0, f"{fn} should ring on"


def test_the_rest_timers_go_signal_is_not_one_of_the_endings():
    """_bellDouble rises where both stopping signals fall, and never plays
    while a hold timer is running."""
    rest = _bell_pitches("_bellDouble")
    assert rest == sorted(rest), "the rest timer's signal rises"
    assert tuple(rest) != tuple(_bell_pitches("_bellSwitch"))


def test_all_three_are_distinct_sequences():
    seqs = [tuple(_bell_pitches(f)) for f in
            ("_bellContinue", "_bellSwitch", "_bellFinish")]
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
    for fn in ("_bellSwitch", "_bellFinish", "_bellContinue"):
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


# ─── future exercises get the same treatment ──────────────────────────────
#
# Athlete's rule, 2026-08-17: "make sure that future exercises that are added
# like this get the same treatment." A timed exercise whose end is not
# announced is one he has to open his eyes to find the end of, which is the
# whole complaint — so this is enforced against the authored content rather
# than left to whoever adds the next block remembering.

def test_every_authored_exercise_with_a_hold_is_a_routed_type():
    """The catch-all. A new exercise carrying hold_seconds under some new
    `type` would render with no hold timer and therefore no ending bell — and
    nothing else in the suite would notice, because the exercise would still
    log fine."""
    import training_plan as tp

    from views import training as V

    unrouted = []
    for plan_name in ("PLAN", "PLAN_STAGE2", "PLAN_STAGE2B"):
        for day, content in (getattr(tp, plan_name, None) or {}).items():
            for ex in (content.get("exercises") or []):
                if ex.get("hold_seconds") and ex.get("type") not in V.HOLD_TIMER_TYPES:
                    unrouted.append(f"{plan_name} day {day}: {ex['name']} (type={ex['type']!r})")
    assert not unrouted, (
        "these exercises are timed but their type gets no hold timer, so their "
        "end is never announced:\n  " + "\n  ".join(unrouted) +
        f"\nEither give them a type in {V.HOLD_TIMER_TYPES} or route the new "
        "type through _hold_timer with an `ending`."
    )


def test_the_routed_types_are_the_ones_the_view_actually_branches_on():
    """HOLD_TIMER_TYPES is only a guarantee while it matches reality. If a
    third timed branch is added to render() without joining the constant, the
    catch-all above silently stops covering it."""
    from views import training as V

    # AST, not a regex: the if/elif chain is long and a line-window match
    # happily reads a _hold_timer call out of a LATER branch, which is exactly
    # the false positive the first version of this test produced.
    tree = ast.parse(_SRC)

    def _calls_hold_timer(nodes) -> bool:
        return any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_hold_timer"
            for stmt in nodes for n in ast.walk(stmt)
        )

    def _ex_type_compared_to(test) -> str | None:
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == "ex_type" and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)):
            return test.comparators[0].value
        return None

    branched = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            name = _ex_type_compared_to(node.test)
            if name and _calls_hold_timer(node.body):
                branched.add(name)

    assert branched == set(V.HOLD_TIMER_TYPES), (
        f"render() calls _hold_timer under {sorted(branched)} but "
        f"HOLD_TIMER_TYPES says {sorted(V.HOLD_TIMER_TYPES)}"
    )


def test_a_new_unilateral_timed_exercise_would_signal_its_swap():
    """Simulates authoring one, rather than trusting that today's content
    happens to be covered."""
    from views import training as V

    for reps in (1, 3, 6, 12):
        endings = {_ending_for_hold_reps(r, reps, is_uni=True, side=s)
                   for r in range(1, reps + 1) for s in ("right", "left")}
        assert V.HOLD_ENDING_SWITCH in endings and V.HOLD_ENDING_FINISH in endings, reps


def test_a_single_rep_timed_exercise_finishes_rather_than_continuing():
    """The degenerate shape a new block is most likely to introduce: one rep,
    one set. It must announce the end, not promise another rep."""
    assert _ending_for_hold_reps(1, 1, is_uni=False, side="right") == "finish"


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
