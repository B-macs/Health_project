"""Every exercise in the 12-week block ran through the workflow — none is copied.

The athlete, 2026-10-16: "Can you ensure that there is never copying, it needs
to run through the workflow. If I ask for a exercise there needs to be reasons
for to and goals attached, and even then it can be overwritten with a better
exercise to get the same goal quicker."

It followed the 90/90 hip lift, which reached the new week by being copied from
Block B's warm-up. goal_week.PICKS holds the record for every exercise; these
tests fail on an exercise without one, on a record without a goal, a reason or
a source, and on registering the block while any pick is unchecked against a
better exercise for the same goal.
"""
import ast
import re
from pathlib import Path

import goal_block as gb
import goal_week as gw
from services import placement as pl
from services import sessions

ROOT = Path(__file__).resolve().parent.parent
TIERS = ROOT / "docs" / "training" / "tier_lists"
WEEK = gw.week()


def _every_name() -> set[str]:
    """Every entry the sessions run, in their final order (ramp sets
    included), plus the home and off-gym items, every entry of the
    registered block (goal_block.py): its tests and its Sunday session, and
    every swap a session offers when equipment is in use (WP-28)."""
    names = {c.name for d in gw.DAYS for c in pl.order(WEEK[d])}
    names |= {c.name for c in gw.CARDS + gw.BONUS_ORDER}
    names |= {e["name"] for day in gb.PLAN_GOAL_BLOCK.values()
              for e in day["exercises"] + day.get("home", [])}
    names |= {e["name"] for alt in gb.ALTERNATIVES.values() for e in alt}
    return names | set(gw.HOME) | set(gw.OFF_GYM)


def test_every_exercise_in_the_week_has_a_workflow_record():
    missing = sorted(n for n in _every_name() if gw.pick_for(n) is None)
    assert not missing, f"no workflow record (goal, reason, source): {missing}"


def test_the_ramp_sets_are_in_the_sessions_and_read_their_own_record():
    ramps = sorted(n for n in _every_name() if n.endswith("(Ramp Set)"))
    assert ramps == ["Hack Squat (Ramp Set)", "Romanian Deadlift (Ramp Set)", "V Squat (Ramp Set)"]
    assert all(gw.pick_for(n) is gw.PICKS["Ramp set"] for n in ramps)


def test_no_record_is_left_over_from_an_exercise_that_is_gone():
    used = {("Ramp set" if n.endswith("(Ramp Set)") else
             "Timed plank test" if n.startswith("Bunkie — ") else n) for n in _every_name()}
    assert set(gw.PICKS) <= used, set(gw.PICKS) - used


def test_every_record_names_a_goal_an_area_a_job_a_reason_and_a_source():
    for name, p in gw.PICKS.items():
        goals = {g.strip() for g in p.goal.split(",")}
        assert goals and goals <= {"A", "B", "C", "warm-up"}, (name, p.goal)
        assert p.area and p.job and p.reason and p.source, name


def test_a_source_is_a_tier_list_or_dated_words():
    for name, p in gw.PICKS.items():
        assert "tier_lists/" in p.source or re.search(r"20\d\d-\d\d-\d\d", p.source), name


def test_a_tier_list_source_names_a_file_that_lists_the_exercise():
    for name, p in gw.PICKS.items():
        files = re.findall(r"tier_lists/([a-z_]+\.md)", p.source)
        if not files:
            continue
        assert p.listed_as, f"{name}: a tier-list source needs the name the list uses"
        texts = [(TIERS / f).read_text(encoding="utf-8").lower() for f in files]
        assert any(p.listed_as.lower() in t for t in texts), (name, files, p.listed_as)


def test_a_training_card_counts_for_the_area_its_record_names():
    for c in gw.CARDS + gw.BONUS_ORDER:
        if c.area:
            assert gw.PICKS[c.name].area == c.area, c.name


def test_the_new_week_copies_nothing_from_an_old_block():
    """Its cards are written in goal_week.py; nothing is taken from
    training_plan.py, where the old blocks live."""
    tree = ast.parse((ROOT / "goal_week.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "training_plan" not in imported


def test_the_open_checks_are_listed_and_nothing_else_is_open():
    unchecked = {n for n, p in gw.PICKS.items() if not p.better}
    assert unchecked == set(gw.BETTER_CHECK_OPEN)


def test_the_block_cannot_be_registered_with_an_unchecked_pick():
    """'even then it can be overwritten with a better exercise to get the same
    goal quicker': every pick, his own included, is checked against a better
    exercise for the same goal before the 12-week block (phase 5) exists."""
    registered = 5 in sessions.PHASE_META
    assert not (registered and gw.BETTER_CHECK_OPEN), gw.BETTER_CHECK_OPEN


def test_the_hip_lift_has_no_record():
    assert "90/90 Hip Lift" not in gw.PICKS
