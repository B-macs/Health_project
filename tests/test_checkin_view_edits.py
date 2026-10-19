"""The check-in page opens a day's saved entry and stores exactly what it shows.

Fault F3 (rebuild Phase 2, 2026-10-19): the form always opened at its defaults
and a second save the same day merged field by field, so pain could not be
corrected from 4 back to 0 and the pain gate kept reading 4. The page now
fills itself from Repository.get_check_in and saves with replace=True when the
day had an entry. Runs views/checkin.py with the repository stubbed; no
network and no secrets.
"""

from __future__ import annotations

import os
from datetime import date

from streamlit.testing.v1 import AppTest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = '''
import sys
sys.path.insert(0, r"{root}")
from datetime import date
import repo
import streamlit as st
from services.models import CheckInRecord

EXISTING = {existing}

class _Stub:
    def get_check_in(self, iso):
        if EXISTING and iso == date.today().isoformat():
            return CheckInRecord(date=iso, current_condition="Good", tightness_score=3.0,
                                 pain_score=4.0, subjective_tightness="sore")
        return None
    def save_check_in(self, record, replace=False):
        st.session_state["_saved"] = (record.pain_score, record.subjective_tightness, replace)
    def send_mirror_now(self):
        return None

repo.get_repository = lambda: _Stub()
from views import checkin
checkin.render()
'''


def _run(existing: bool) -> AppTest:
    at = AppTest.from_string(_SCRIPT.format(root=_ROOT, existing=existing), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def _key(name: str) -> str:
    return f"checkin_{name}_{date.today().isoformat()}"


def test_a_saved_day_opens_filled_in_and_a_pain_of_zero_is_stored():
    at = _run(existing=True)
    assert any("already saved a check-in" in i.value for i in at.info)
    assert at.slider(key=_key("pain")).value == 4
    assert at.text_input(key=_key("note")).value == "sore"
    at.slider(key=_key("pain")).set_value(0)
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert at.session_state["_saved"] == (0, "sore", True)


def test_a_new_day_opens_at_the_defaults_and_merges_as_before():
    at = _run(existing=False)
    assert not any("already saved a check-in" in i.value for i in at.info)
    assert at.slider(key=_key("pain")).value == 0
    at.slider(key=_key("pain")).set_value(2)
    at.button[0].click().run()
    assert at.session_state["_saved"] == (2, "", False)
