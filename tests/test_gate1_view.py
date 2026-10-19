"""The training page's gate-1 card, rendered alone in Streamlit's test
runtime (move TRN-13, 2026-10-19): it asks a short week's reason, stores the
one-tap answer through services/gate1.py, and stops asking. A fake
repository; no network and no secrets.
"""

from __future__ import annotations

import os

from streamlit.testing.v1 import AppTest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = '''
import sys
sys.path.insert(0, r"{root}")
from datetime import date, timedelta
import repo
import streamlit as st
from services import sessions as sess

today = date.today()
start = today - timedelta(days=today.weekday() + 14)       # today is in week 3
PHASE = sess.build_phase(5, start)


class _Repo:
    def get_config_value(self, key):
        return st.session_state.get("_raw")

    def set_config(self, key, value):
        st.session_state["_raw"] = value

    def get_logged_session_dates(self, s, t, include_supplementary=True):
        week1 = {{(start + timedelta(days=i)).isoformat() for i in (0, 1, 3)}}
        week2 = {{(start + timedelta(days=7 + i)).isoformat() for i in (0, 1)}}
        return week1 | week2

    def get_recent_session_sets(self, lift, limit=0):
        return []


repo.get_repository = lambda: _Repo()
from views import training
training._render_gate1(PHASE, False)
'''


def test_a_short_week_asks_its_reason_once_and_the_answer_is_stored():
    at = AppTest.from_string(_SCRIPT.format(root=_ROOT), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    assert any("ran 2 of 3 core sessions" in w.value for w in at.warning)
    at.button(key="g1_reason_travel_illness").click().run()
    assert not at.exception, at.exception
    assert "travel_illness" in at.session_state["_raw"]
    assert not any("core sessions" in w.value for w in at.warning), "it stops asking"
