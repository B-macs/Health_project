"""The training page's guided flow, tapped through in Streamlit's test runtime
(move TRN-9, 2026-10-19): every tap goes through services/guided_flow.step,
and the page must land where the step says — sets recorded once, a rest
between sets, a one-side hold done on both sides, then the save screen. A
stub store; no network and no secrets.
"""

from __future__ import annotations

import os

from streamlit.testing.v1 import AppTest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = '''
import sys
sys.path.insert(0, r"{root}")
import repo
import streamlit as st
from services import sessions as sess


class _Cfg:
    timezone = "Europe/Berlin"


class _Repo:
    config = _Cfg()

    def garmin_configured(self):
        return False

    def get_last_performance(self, name):
        return None

    def get_last_session_all_sets(self, name):
        return []

    def get_recent_session_sets(self, name, limit=0):
        return []

    def get_recent_readiness(self, days=1, today=None):
        return []

    def get_daily_region_au(self, days=31, today=None):
        return {{"rows": []}}

    def get_current_stage(self):
        return 2

    def __getattr__(self, name):
        return lambda *a, **k: None


repo.get_repository = lambda: _Repo()
from views import training

training._init_state()
st.session_state.tp_started = True
import goal_block as gb
_day = sess.calendar_plan(sess.build_phase(5, gb.START))[1]["exercises"]
EXERCISES = [next(e for e in _day if e["name"] == "Machine Chest Press"),
             next(e for e in _day if e["name"] == "Single-Arm Cable Y Raise")]
# The page shows the save screen once every exercise is done, as render() does.
if not st.session_state.tp_done_today:
    training._render_guided_flow(1, EXERCISES, len(EXERCISES), sess.load_policy(None, None),
                                 {{"streak_label": "unknown"}}, 1.0, None)
'''


def _tap(at: AppTest, label: str) -> AppTest:
    button = next(b for b in at.button if b.label.startswith(label))
    button.click().run()
    assert not at.exception, at.exception
    return at


def test_a_session_taps_through_to_the_save_screen():
    """Two real exercises of the 12-week block's day 1: a two-sided lift of
    three sets, then a one-sided lift of three sets."""
    at = AppTest.from_string(_SCRIPT.format(root=_ROOT), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    state = at.session_state

    _tap(at, "✓ Set 1 Complete")
    assert (state.tp_ex_idx, state.tp_set, state.tp_phase) == (0, 2, "resting")
    assert [r["set_num"] for r in state.tp_set_log[0]] == [1]
    assert state.tp_rest_started_at > 0, "the rest is stamped"
    _tap(at, "→ Next Set")
    assert (state.tp_set, state.tp_phase) == (2, "intro")
    for label in ("✓ Set 2 Complete", "→ Next Set", "✓ Set 3 Complete"):
        _tap(at, label)
    assert (state.tp_ex_idx, state.tp_set, state.tp_phase) == (1, 1, "intro")
    assert [r["set_num"] for r in state.tp_set_log[0]] == [1, 2, 3]

    first = state.tp_first_side
    for set_num in (1, 2, 3):
        _tap(at, f"✓ {first.capitalize()} Side Done")
        assert state.tp_side == sess_other(first) and len(state.tp_set_log.get(1, [])) == set_num - 1
        _tap(at, f"✓ Set {set_num} Complete")
        if set_num < 3:
            _tap(at, "→ Next Set")
    assert [r["set_num"] for r in state.tp_set_log[1]] == [1, 2, 3]
    assert state.tp_done_today, "every exercise done: the save screen is next"


def sess_other(side: str) -> str:
    from services import sessions
    return sessions.other_side(side)
