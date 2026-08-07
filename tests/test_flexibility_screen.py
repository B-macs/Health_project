"""End-to-end render of the Flexibility screen through Streamlit's own harness,
with the repository stubbed.

The pure logic lives in test_cluster_a.py. What this adds is the WIRING: that
the page runs at all, that each of its three states draws, and — the one that
matters — that the capture flow stops as soon as the battery has an answer.

That last one cannot be caught by a unit test on services/. The early exit is
the method rather than a convenience, and it lives in the view: the screen runs
the real battery against the draft after every step instead of re-implementing
the rule, so a bug here would silently ask the athlete for thirty minutes of
readings that cannot be interpreted.
"""

from __future__ import annotations

from datetime import date

import pytest

from streamlit.testing.v1 import AppTest

import cluster_a_battery as cba
from services import battery as sb

_ROOT = r"c:\Users\brian\Documents\1.Projects\AIProject\Health_project"

_SCRIPT = '''
import sys
sys.path.insert(0, r"{root}")
from datetime import date
import repo
from services import battery as b

_saved = []
_draft = {{"v": None}}

class _Stub:
    def get_flexibility_assessments(self):
        return tuple(_saved)
    def get_flexibility_draft(self):
        return _draft["v"]
    def save_flexibility_draft(self, a):
        _draft["v"] = a
    def clear_flexibility_draft(self):
        _draft["v"] = None
    def save_flexibility_assessment(self, a):
        _saved.append(a)

READINGS = {readings}
if READINGS:
    _saved.append(b.Assessment(cluster="a", taken_on=date(2026, 8, 6),
                               readings=tuple(b.Reading(**r) for r in READINGS)))

DRAFT = {draft}
if DRAFT is not None:
    _draft["v"] = b.Assessment(cluster="a", taken_on=date(2026, 8, 6),
                               readings=tuple(b.Reading(**r) for r in DRAFT))

repo.get_repository = lambda: _Stub()
import streamlit as st
st.session_state["fx_mode"] = {mode!r}
st.session_state["fx_step"] = {step}
from views import insights as V
V._flexibility_screen_data.clear()
V._render_flexibility_detail()
'''

# Gate 0 and the leverages pass; the tilt fails on both halves -> Pattern F,
# which is what this athlete's 2026-08-05 baseline predicts.
_PASS_TO_TILT = [
    {"test_key": "gate0_neutral", "value": 28.0, "unit": "cm"},
    {"test_key": "gate0_turned_out", "value": 25.0, "unit": "cm"},
    {"test_key": "leverage_bent", "value": 8.0, "unit": "cm", "side": "left"},
    {"test_key": "leverage_bent", "value": 9.0, "unit": "cm", "side": "right"},
    {"test_key": "leverage_straight", "value": 95.0, "unit": "cm", "side": "left"},
    {"test_key": "leverage_straight", "value": 94.0, "unit": "cm", "side": "right"},
]
_TILT_FAILS = _PASS_TO_TILT + [
    {"test_key": "tilt_range", "value": 8.0, "unit": "°"},
    {"test_key": "tilt_production", "value": 4.0, "unit": "°"},
]
# Gate 0 alone, failing on orientation -> Pattern B at the very first slot.
# The neutral reading must sit INSIDE the 15 cm relevance line — above it, bone
# is not a live question and slot 0 passes on the height alone.
_GATE0_FAILS = [
    {"test_key": "gate0_neutral", "value": 14.0, "unit": "cm"},
    {"test_key": "gate0_turned_out", "value": 3.0, "unit": "cm"},
]


def _as_assessment(readings) -> sb.Assessment:
    return sb.Assessment(cluster="a", taken_on=date(2026, 8, 6),
                         readings=tuple(sb.Reading(**r) for r in readings))


def _run(readings=(), draft=None, mode=None, step=0) -> AppTest:
    script = _SCRIPT.format(root=_ROOT, readings=list(readings),
                            draft=list(draft) if draft is not None else None,
                            mode=mode, step=step)
    return AppTest.from_string(script, default_timeout=90).run()


def _text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown]
    parts += [c.value for c in at.caption]
    parts += [w.value for w in at.warning]
    parts += [i.value for i in at.info]
    parts += [b.label for b in at.button]
    return " ".join(str(p) for p in parts)


def test_the_screen_renders_in_every_state_without_an_exception():
    for label, kwargs in (
        ("empty", {}),
        ("populated", {"readings": _TILT_FAILS}),
        ("cold gate", {"mode": "capture"}),
        ("mid-capture", {"draft": _PASS_TO_TILT, "mode": "capture"}),
    ):
        at = _run(**kwargs)
        assert not at.exception, f"{label}: {at.exception[0].message if at.exception else ''}"


def test_the_empty_state_offers_one_action_and_promises_a_label_not_a_score():
    at = _run()
    assert [b.label for b in at.button] == ["Start assessment"]
    body = _text(at)
    assert "Not measured" in body
    assert "pattern label" in body.lower()
    assert "/100" not in body, "a score has come back"


def test_the_populated_state_leads_with_the_pattern_and_the_limiter():
    at = _run(readings=_TILT_FAILS)
    body = _text(at)
    assert "What is stopping you" in body
    assert "Tilt range" in body
    assert "Prerequisite" in body           # the slot it stopped at
    assert "/100" not in body


def test_the_populated_state_says_a_single_session_is_a_hypothesis():
    """Three baseline mornings before a pattern is trusted. Showing a
    confident-looking label off one session is how a programme gets changed on
    measurement scatter."""
    at = _run(readings=_TILT_FAILS)
    body = _text(at).lower()
    assert "hypothesis" in body
    assert "not a verdict" in body


def test_the_mandatory_release_block_is_on_the_screen():
    """It comes from the clinical profile rather than the flexibility method,
    which is exactly why every source stack omitted it."""
    at = _run(readings=_TILT_FAILS)
    body = _text(at)
    assert "Before every session" in body
    assert "Upper glute" in body
    assert "inhibit" in body.lower()


def test_capture_stops_as_soon_as_the_battery_has_an_answer():
    """THE ONE THIS FILE EXISTS FOR. Gate 0 failing on orientation is a Pattern
    B at the very first slot — the remaining eight tests measure things below a
    failure and cannot be interpreted, so the screen must say stop rather than
    walk him through them."""
    at = _run(draft=_GATE0_FAILS, mode="capture")
    assert not at.exception
    body = _text(at)
    assert "stop here" in body.lower()
    assert "Pattern B" in body
    assert "Save assessment" in [b.label for b in at.button]
    assert "nothing more to collect" in body.lower()


def test_the_early_exit_can_be_overridden_but_is_not_the_default():
    """Offered, because a curious athlete taking extra readings is harmless and
    forbidding it would be paternalistic. Not the default, because the readings
    are uninterpretable and the time is real."""
    at = _run(draft=_GATE0_FAILS, mode="capture")
    labels = [b.label for b in at.button]
    assert "Keep going anyway" in labels
    assert labels.index("Save assessment") < labels.index("Keep going anyway")


def test_capture_shows_the_lock_and_its_tell_on_every_step():
    """A lost lock makes the reading BETTER, not worse, so nothing warns you.
    The tell has to be on the step, not buried in an expander."""
    at = _run(draft=[], mode="capture")          # a started draft, no readings yet
    assert not at.exception
    body = _text(at)
    assert "LOCK" in body
    assert "tell" in body.lower()
    assert "void" in body.lower()


def test_the_cold_gate_explains_the_three_measures_before_asking_for_any():
    """No draft at all means the gate, which is the first thing a session sees.
    The three measures are the whole model and were explained nowhere on screen
    in the version this replaced."""
    at = _run(mode="capture")                    # draft is None -> the cold gate
    body = _text(at)
    assert "Measure cold" in body
    for word in ("Passive", "Isometric", "Active"):
        assert word in body, word
    assert "flatter" in body.lower(), "the reason passive goes last must be stated"


def test_a_draft_is_offered_for_resume_rather_than_lost():
    at = _run(draft=_PASS_TO_TILT)
    body = _text(at)
    assert "Assessment in progress" in body
    assert "Resume assessment" in [b.label for b in at.button]


def test_the_screen_survives_a_repository_failure():
    """A read failure must render an error, not a stack trace."""
    script = _SCRIPT.format(root=_ROOT, readings=[], draft=None, mode=None, step=0).replace(
        "def get_flexibility_assessments(self):\n        return tuple(_saved)",
        "def get_flexibility_assessments(self):\n        raise RuntimeError('cache gone')")
    at = AppTest.from_string(script, default_timeout=90).run()
    assert not at.exception
    assert any("flexibility record" in e.value for e in at.error)


# ── parity with the prototype ────────────────────────────────────────────────
#
# The clickable mockup and the shipped screen are generated from the same
# modules, so their CONTENT cannot drift. What can drift is which of it each one
# chooses to show — and a mockup that shows more than the app is worse than no
# mockup, because it is the thing that got clicked through and agreed to.

def test_the_empty_state_shows_what_is_held_back_and_why():
    at = _run()
    body = _text(at)
    # Streamlit's harness exposes the CONTENTS of an expander but not its label,
    # so assert on what is inside rather than on the summary line.
    assert "condition rather than a date" in body.lower()
    assert "knees at 90 degrees" in body.lower(), "the held test is not named"
    assert "loaded squat work has run clean" in body.lower(), "the condition is not stated"


def test_the_cold_gate_carries_the_two_record_but_never_chase_notes():
    at = _run(mode="capture")
    body = _text(at)
    assert "nerve check" in body.lower()
    assert "medial knee" in body.lower()
    assert "differentiator, not a provocation" in body.lower()
    assert "finding, not a training sensation" in body.lower()


def test_the_capture_step_asks_for_the_setup_number_where_a_test_has_one():
    """The bent-knee leverage needs its heel distance, and that number decides
    which pattern comes out."""
    started = [{"test_key": "gate0_neutral", "value": 28.0, "unit": "cm"},
               {"test_key": "gate0_turned_out", "value": 25.0, "unit": "cm"}]
    # The step index comes from the LIVE order: a 28 cm neutral reading puts
    # the turned-out comparison out of scope, which shifts every later step.
    step = list(cba.applicable_tests(_as_assessment(started))).index("leverage_bent")
    at = _run(draft=started, mode="capture", step=step)
    labels = " ".join(str(n.label) for n in at.number_input)
    assert "heel" in labels.lower(), labels


def test_a_neutral_reading_off_the_floor_skips_the_turned_out_step():
    """The athlete's call (2026-08-07): bone only engages in the last few
    centimetres of a full split. After a 28 cm neutral reading the turned-out
    comparison is out of scope — the flow must move straight to the bent-knee
    leverage and say why, not walk him through a comparison that answers
    nothing."""
    started = [{"test_key": "gate0_neutral", "value": 28.0, "unit": "cm"}]
    at = _run(draft=started, mode="capture", step=1)
    body = _text(at)
    assert "Knees fully bent" in body
    assert "not yet a factor" in body.lower()


def test_the_tilt_asks_for_one_number_in_degrees_plus_the_straddle_width():
    """The old protocol asked for two measurements and offered one box. The
    angle protocol asks for exactly one number — degrees at the pelvis — and
    the width it was taken at, and the input says so at the field."""
    step = list(cba.applicable_tests(_as_assessment(_PASS_TO_TILT))).index("tilt_production")
    at = _run(draft=_PASS_TO_TILT, mode="capture", step=step)
    body = _text(at)
    assert "degrees" in body.lower()
    # The old instruction must be gone; mentioning forehead height while
    # explaining WHY the angle replaced it is fine.
    assert "floor up to your forehead" not in body.lower()
    assert "two numbers" not in body.lower()
    labels = " ".join(str(n.label) for n in at.number_input)
    assert "straddle width" in labels.lower(), labels
    assert len(at.number_input) == 2, "one measurement box and one width box"


def test_a_recorded_setup_number_is_offered_back_the_next_time():
    """THE NUMBER IS THE RECORD. A straddle width recorded last session is the
    width this session must use, so the screen says so instead of trusting
    memory."""
    prior = [dict(r) for r in _TILT_FAILS]
    for r in prior:
        if r["test_key"] == "tilt_production":
            r["setup_value"] = 92.0
    step = list(cba.applicable_tests(_as_assessment(_PASS_TO_TILT))).index("tilt_production")
    at = _run(readings=prior, draft=_PASS_TO_TILT, mode="capture", step=step)
    body = _text(at)
    assert "Last time you used" in body
    assert "92" in body


def test_stack_items_lead_with_how_not_why():
    """The athlete's direction (2026-08-07): the why is background; the how is
    what the user needs. Each stack item must show position, movement, feel,
    stop rule and progress — the why demoted to a caption underneath."""
    at = _run(readings=_TILT_FAILS)
    body = _text(at)
    for label in ("Position", "The movement", "You should feel",
                  "Stop rule", "Progress is"):
        assert label in body, label


def test_the_expected_outcome_is_no_longer_advertised_on_the_screen():
    """Removed on the athlete's request (2026-08-07). The prediction stays in
    the code — its job is to exist BEFORE measuring, not to prime the person
    about to measure."""
    at = _run()
    body = _text(at)
    assert "worth watching rather than resolving in advance" not in body
    assert f"Pattern {cba.EXPECTED_PATTERN}" not in body


def test_a_pattern_from_an_invented_cut_point_says_so_on_the_screen():
    """Pattern E is what actually came out of the first real run, off a 90 cm
    line nobody had validated. The screen has to distinguish 'your gracilis is
    short' from 'your straddle fell below a number we chose'."""
    gracilis = [
        {"test_key": "gate0_neutral", "value": 28.0, "unit": "cm"},
        {"test_key": "gate0_turned_out", "value": 25.0, "unit": "cm"},
        {"test_key": "leverage_bent", "value": 8.0, "unit": "cm"},
        {"test_key": "leverage_straight", "value": 40.0, "unit": "cm"},
    ]
    at = _run(readings=gracilis)
    body = _text(at) + " ".join(e.value for e in at.error)
    assert "Gracilis" in body
    assert "cut point we invented" in body.lower()
    # And the two reasons stay separate on screen, not merged into one caveat.
    assert "hypothesis" in body.lower()
