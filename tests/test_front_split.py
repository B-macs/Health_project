"""The front split: the flexibility goal from 2026-11-11.

The athlete: "I want to change the mobility plan from the pancake to the front
split as the objective", then, to four questions, "Yes, all four": the front
split only; one cold test morning to find the weaker part first; the plan
written from the blueprint's method, the tier lists and his record, every
exercise with its workflow record; the adductor machine kept to the end of the
block.

These tests hold the front split's three layers to the rules Cluster A's are
held to (tests/test_cluster_a.py): the battery names no exercise and carries
no dose, the prescription defines nothing it names and refuses without a
pattern, the text read mid-test is plain English, and every exercise lands on
a safety rule. Then the decisions: which reading gives which pattern, the
evening session's stack, and where an assessment is stored.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta

import pytest

import front_split_battery as fb
import front_split_mechanics as fm
import front_split_prescription as fp
import goal_block as gb
import goal_week as gw
import training_constants as tc
from services import battery as b
from services import flexibility as fx
from services import flexibility_screen as fxs
from services import mobility_session as mob
from services import rules
from services import sessions
from tests.test_cluster_a import _HEDGES, _JARGON, _REPO_INTERNALS

TODAY = date(2026, 11, 13)
_PATIENT_FACING = ("label", "setup", "lock", "measurement", "safety", "input_hint",
                   "setup_input")
_HOW_FIELDS = ("position", "movement", "feel", "stop", "progress")


def _assessment(**values) -> b.Assessment:
    """A front split assessment: each test's value on both sides, or a
    (left, right) pair."""
    readings = []
    for key, v in values.items():
        left, right = v if isinstance(v, tuple) else (v, v)
        for side, value in (("left", left), ("right", right)):
            if value is not None:
                readings.append(b.Reading(test_key=key, value=float(value),
                                          unit=fb.TESTS[key].unit, side=side,
                                          setup_value=85.0 if key == "split_span" else None))
    return b.Assessment(cluster=fb.CLUSTER_KEY, taken_on=TODAY, readings=tuple(readings))


_FINE = dict(slr_active=85.0, slr_passive=95.0, hanging_thigh=5.0, hanging_shin=5.0,
             split_span=140.0)


def _pattern(**changes) -> str | None:
    return b.run(fb.CLUSTER_KEY, fb.SLOT_EVALUATORS, _assessment(**{**_FINE, **changes})).pattern


# ── the layers ───────────────────────────────────────────────────────────────

def test_the_battery_names_no_exercise_and_carries_no_dose():
    source = inspect.getsource(fb).lower()
    for e in fm.LIBRARY:
        assert e.name.lower() not in source, e.name
    for dose in (" × 8", " × 30 s", "3 x 8", "sets", "reps"):
        assert dose not in inspect.getsource(fb), dose


def test_every_prescribed_exercise_resolves_in_the_front_split_library():
    for pattern, stack in fp.STACKS.items():
        for item in stack.items:
            assert fm.exercise(item.exercise) is not None, (pattern, item.exercise)


def test_the_mechanics_and_prescription_stay_in_their_layers():
    assert not hasattr(fm, "PATTERNS") and not hasattr(fm, "STACKS")
    assert "def prescribe" not in inspect.getsource(fm)
    source = inspect.getsource(fp).lower()
    for banned in ("def evaluate_", "slotresult", "slot_evaluators", "def run("):
        assert banned not in source, banned


def test_a_prescription_without_a_pattern_refuses():
    for nothing in (None, "", "   ", "Z", "D"):
        with pytest.raises(fp.NoPatternError):
            fp.prescribe(nothing)
    empty = fx.assess(None, TODAY, cluster_key=fx.GOAL_CLUSTER)
    with pytest.raises(fp.NoPatternError):
        fx.prescribe(empty)


def test_the_goal_cluster_is_the_front_split():
    assert fx.GOAL_CLUSTER == "front_split"
    assert fx.cluster(fx.GOAL_CLUSTER)["label"] == "Front split"
    assert fx.DEFAULT_CLUSTER == "a", "an assessment stored without a cluster is Cluster A's"


# ── the test, as he reads it on the floor ────────────────────────────────────

def test_the_text_read_mid_test_is_plain_english():
    offences = [f"{key}.{field}: {word!r}"
                for key, test in fb.TESTS.items() for field in _PATIENT_FACING
                for word in _JARGON + _REPO_INTERNALS + _HEDGES
                if word.lower() in getattr(test, field).lower()]
    assert offences == [], offences


def test_every_exercise_says_how_in_plain_english():
    for ex in fm.LIBRARY:
        for field in _HOW_FIELDS:
            body = getattr(ex, field)
            assert body.strip(), f"{ex.key}.{field} is empty"
            for word in _JARGON + _REPO_INTERNALS + _HEDGES:
                assert word.lower() not in body.lower(), f"{ex.key}.{field}: {word!r}"
        assert len(ex.movement) >= 40, ex.key


def test_active_comes_before_passive_and_the_split_is_last():
    """Help and stretching flatter whatever is measured after them."""
    order = list(fb.TEST_ORDER)
    assert order.index("slr_active") < order.index("slr_passive")
    assert order[-1] == "split_span"
    assert all(fb.TESTS[k].bilateral for k in order), "both sides, every test"


def test_the_test_takes_about_ten_minutes_of_five_readings_a_side():
    assert len(fb.AVAILABLE_TESTS) == 5 and not fb.DEFERRED_TESTS


def test_the_split_asks_for_the_leg_length_once():
    assert fb.TESTS["split_span"].setup_input
    assert [k for k, t in fb.TESTS.items() if t.setup_input] == ["split_span"]


def test_the_nerve_is_a_finding_never_a_pattern():
    """rules.py 'nerve glide': no nerve work for a symptom no log records."""
    assert "stop" in fb.NERVE_CHECK.lower() and "record" in fb.NERVE_CHECK.lower()
    assert not any("nerve" in label.lower() for label in fb.PATTERNS.values())
    assert not any("nerve" in e.name.lower() for e in fm.LIBRARY)


# ── which reading gives which pattern ────────────────────────────────────────

def test_the_expected_pattern_is_written_down_and_is_the_front_leg():
    assert fb.EXPECTED_PATTERN == "H" and "89" in fb.EXPECTED_PATTERN_BASIS


def test_a_short_front_leg_alone_is_the_hamstrings():
    assert _pattern(slr_passive=70.0, slr_active=60.0) == "H"


def test_the_worse_side_decides():
    assert _pattern(slr_passive=(95.0, 80.0), slr_active=(85.0, 75.0)) == "H"


def test_both_legs_short_is_both():
    assert _pattern(slr_passive=70.0, slr_active=60.0, hanging_thigh=-5.0) == "B"
    assert _pattern(slr_passive=70.0, slr_active=60.0, hanging_shin=20.0) == "B"


def test_a_raised_thigh_is_the_deep_hip_flexors_and_hides_the_shin():
    """With the thigh held up, the knee angle reads the deep group, so the
    shin cannot name the front of the thigh."""
    assert _pattern(hanging_thigh=-5.0) == "P"
    assert _pattern(hanging_thigh=-5.0, hanging_shin=20.0) == "P"


def test_a_swinging_shin_with_the_thigh_down_is_the_front_of_the_thigh():
    assert _pattern(hanging_shin=20.0) == "R"


def test_long_enough_but_not_controlled_is_strength_at_length():
    assert _pattern(slr_active=75.0) == "A"


def test_long_enough_and_controlled_is_the_split_itself():
    assert _pattern() == "S"


def test_a_missing_side_is_not_a_pass():
    r = b.run(fb.CLUSTER_KEY, fb.SLOT_EVALUATORS,
              _assessment(**{**_FINE, "hanging_shin": (5.0, None)}))
    assert r.pattern is None and r.slots[-1].indeterminate
    missing = fb.missing_inputs(_assessment(**{**_FINE, "hanging_shin": (5.0, None)}), r)
    assert [(m.test_key, m.side) for m in missing] == [("hanging_shin", "right")]


def test_the_split_reading_decides_no_pattern():
    """It is the goal's proof; no slot waits on it."""
    without = {k: v for k, v in _FINE.items() if k != "split_span"}
    assert b.run(fb.CLUSTER_KEY, fb.SLOT_EVALUATORS, _assessment(**without)).pattern == "S"


# ── the ladder ───────────────────────────────────────────────────────────────

def test_the_ladder_marks_the_rung_the_pattern_names():
    a = _assessment(**{**_FINE, "slr_passive": 70.0, "slr_active": 60.0})
    rungs = {r.key: r for r in fb.ladder(a, b.run(fb.CLUSTER_KEY, fb.SLOT_EVALUATORS, a))}
    assert rungs["front_leg"].state == b.RUNG_LIMITING
    assert rungs["deep_hip_flexors"].state == b.RUNG_PASSED
    assert rungs["control"].state == b.RUNG_CONTEXT, "slot 3 did not run"


def test_the_split_is_read_against_twice_the_leg_length():
    a = _assessment(**_FINE)
    split = next(r for r in fb.ladder(a, b.run(fb.CLUSTER_KEY, fb.SLOT_EVALUATORS, a))
                 if r.key == "split")
    assert split.target == 170.0 and split.fraction == pytest.approx(140.0 / 170.0)
    assert split.state == b.RUNG_LIMITING and not split.provisional


def test_an_unmeasured_rung_has_no_number():
    a = _assessment(slr_active=85.0)
    rungs = fb.ladder(a, b.run(fb.CLUSTER_KEY, fb.SLOT_EVALUATORS, a))
    split = next(r for r in rungs if r.key == "split")
    assert split.state == b.RUNG_UNMEASURED and split.measured is None and split.fraction is None


# ── the stacks ───────────────────────────────────────────────────────────────

def test_every_pattern_has_a_stack_of_three_to_five():
    assert set(fp.STACKS) == set(fb.PATTERNS)
    for stack in fp.STACKS.values():
        assert 3 <= len(stack.live_items) <= 5, stack.pattern


def test_the_skill_comes_last():
    for stack in fp.STACKS.values():
        assert stack.live_items[-1].exercise in (
            fm.LIBRARY_BY_KEY["split_on_blocks"].name,
            fm.LIBRARY_BY_KEY["split_heel_press"].name), stack.pattern


def test_range_he_cannot_control_gets_no_passive_split_hold():
    """The blueprint: passive high, active low, 'More stretching makes this worse'."""
    names = [i.exercise for i in fp.prescribe("A").live_items]
    assert fm.LIBRARY_BY_KEY["split_on_blocks"].name not in names
    assert fm.LIBRARY_BY_KEY["half_split_pir"].name not in names


def test_every_stack_runs_as_an_evening_inside_the_flexibility_limits():
    for pattern in fp.STACKS:
        day = gb.evening_mobility_day(pattern)
        assert sessions.session_shape_violations(day) == [], pattern
        assert sessions.session_seconds(day["exercises"]) <= 30 * 60, pattern
        assert all(e["laterality"] == "unilateral" for e in day["exercises"]), \
            "every item runs on both sides"


def test_every_exercise_lands_on_a_rule_and_none_is_blocked():
    for e in fm.LIBRARY:
        verdict = rules.check_movement(e.name, 2)["severity"]
        assert verdict == "caution", (e.name, verdict)


def test_the_front_split_rule_says_hips_square_and_no_arch():
    rule = next(r for r in rules.MOVEMENT_RULES if r.movement == "front split")
    assert "HIPS SQUARE" in rule.reason and "arch" in rule.reason


def test_every_exercise_is_in_the_load_maps():
    for e in fm.LIBRARY:
        assert tc.EXERCISE_BODY_REGION.get(e.name) == "lower_body", e.name
        assert e.name in tc.EXERCISE_REGION_SHARES, e.name
        assert e.name in tc.EXERCISE_MOVEMENT_WEIGHT, e.name


def test_an_evening_of_the_stack_is_a_leg_day_for_the_next_test():
    from services import models as m
    session = m.SessionRecord(session_date="2026-11-14", session_duration_minutes=20.0,
                              session_rpe=4.0, session_au=80.0,
                              exercises=[m.ExerciseEntry(name=e["name"], movement_type="Mobility")
                                         for e in gb.FRONT_SPLIT_STACKS["H"]])
    assert fx.leg_loading_days([session]) == {date(2026, 11, 14)}


def test_every_exercise_has_its_workflow_record():
    for e in fm.LIBRARY:
        pick = gw.pick_for(e.name)
        assert pick is not None and pick.goal == "C" and pick.better, e.name


def test_the_adductor_machine_stays_with_its_new_reason():
    pick = gw.pick_for("Adductor Machine (Seated)")
    assert "front split" in pick.reason and "2026-11-11" in pick.source


# ── the evening session ──────────────────────────────────────────────────────

class _Repo:
    def __init__(self, assessments=(), broken=False):
        self._a, self._broken = tuple(assessments), broken

    def get_flexibility_assessments(self):
        if self._broken:
            raise RuntimeError("store unreachable")
        return self._a


def test_before_the_first_test_the_evening_keeps_the_last_measured_stack():
    assert mob.front_split_pattern(_Repo(), TODAY) is None
    day = mob.build_day(None)
    assert [e["name"] for e in day["exercises"]] == [e["name"] for e in gb.FLEX_STACK]
    assert mob.note(None) == mob.NOTE_BEFORE_TEST and "front split" in mob.NOTE_BEFORE_TEST


def test_an_unreadable_store_runs_the_last_stack_never_a_guess():
    assert mob.front_split_pattern(_Repo(broken=True), TODAY) is None


def test_after_the_test_the_evening_runs_the_stack_for_its_pattern():
    cluster_a = b.Assessment(cluster="a", taken_on=TODAY + timedelta(days=1))
    short_front = _assessment(**{**_FINE, "slr_passive": 70.0, "slr_active": 60.0})
    assert mob.front_split_pattern(_Repo([short_front, cluster_a]), TODAY) == "H", \
        "a later Cluster A assessment does not hide the front split's"
    day = mob.build_day("H")
    assert day["objective"] == "Evening mobility — Front split: Front leg — hamstrings"
    assert [e["name"] for e in day["exercises"]] == [
        i.exercise for i in fp.prescribe("H").live_items]
    assert mob.note("H") == mob.NOTE


# ── where it is stored and how the screen reads it ──────────────────────────

def test_an_assessment_keeps_its_cluster_through_the_store():
    a = _assessment(**_FINE)
    back = fx.assessment_from_dict(fx.assessment_to_dict(a))
    assert back.cluster == "front_split" and len(back.readings) == len(a.readings)


def test_one_morning_can_hold_both_clusters(monkeypatch):
    """Same date replaced the stored assessment; from 2026-11-11 only the same
    date AND the same cluster does."""
    from services import repository
    store: dict = {}

    class _Cache:
        @staticmethod
        def mutate(key, fn):
            store[key] = fn(store.get(key))
            return store[key]

    monkeypatch.setattr(repository, "local_cache", _Cache)

    class _Self:
        def set_config(self, key, value):
            pass

    cluster_a = b.Assessment(cluster="a", taken_on=TODAY)
    for assessment in (cluster_a, _assessment(**_FINE), _assessment(**_FINE)):
        repository.Repository.save_flexibility_assessment(_Self(), assessment)
    (saved,) = store.values()
    assert sorted(d["cluster"] for d in saved) == ["a", "front_split"]


def test_the_screen_reads_the_goal_and_the_old_page_reads_cluster_a():
    class _Screen(_Repo):
        def get_recent_sessions(self, days=3, today=None):
            return []

    repo = _Screen([b.Assessment(cluster="a", taken_on=TODAY - timedelta(days=90)),
                    _assessment(**_FINE)])
    assert fxs.read_data(repo, TODAY)["report"].cluster == "front_split"
    assert fxs.read_data(repo, TODAY)["count"] == 1
    assert fxs.read_data(repo, TODAY, cluster="a")["report"].cluster == "a"
    guide = fxs.guide()
    assert guide["cluster_label"] == "Front split" and guide["test_count"] == 5
    assert guide["medial_knee_note"] == fb.FRONT_HIP_NOTE and guide["second_note"] == "front_hip"
    assert fxs.guide("a")["second_note"] == "inner_knee"
    assert [s["slot"] for s in guide["slots"]] == [b.SLOT_REGRESSED, b.SLOT_SPECTRUM]
    assert {f["name"] for f in guide["frozen"]} == {n for n, _ in fb.FROZEN_CONSTANTS}


def test_a_new_capture_is_the_front_split_test():
    class _Draft(_Repo):
        draft = None

        def get_flexibility_draft(self):
            return self.draft

        def save_flexibility_draft(self, a):
            self.draft = a

        def get_recent_sessions(self, days=3, today=None):
            return []

    out = fxs.start_capture(_Draft(), TODAY, cold=True)
    assert out["cluster"] == "front_split"
    assert [t["key"] for t in out["order"]] == list(fb.TEST_ORDER)


def test_the_next_test_falls_after_the_block():
    """His rule of 2026-11-08: no test inside the block after this one."""
    block_end = gb.START + timedelta(days=gb.WEEKS * 7 - 1)
    assert fx.retest_due_on(TODAY, fx.GOAL_CLUSTER) > block_end
