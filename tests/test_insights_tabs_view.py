"""The whole Insights page rendered in Streamlit's test runtime with a stub
store (2026-10-19, after moves INS-5 and INS-6 rewired the Processing Queue,
Macro Trends, Sleep Architecture and Sync tabs to services). It renders every
tab on every run, so one run proves the tabs still draw. Made-up rows; no
network and no secrets.
"""

from __future__ import annotations

import os

from streamlit.testing.v1 import AppTest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = '''
import sys
sys.path.insert(0, r"{root}")
import repo


class _Stub:
    supabase_record = True

    def get_diagnostic_profile(self):
        return {{}}

    def get_current_stage(self):
        return 2

    def get_pain_free_streak(self, today=None):
        return 5

    def get_avg_tightness(self, days=14, today=None):
        return 2.0

    def hrv_trend_series(self, days=90, today=None):
        return {{"oura": {{}}}}

    def oura_configured(self):
        return False

    def garmin_configured(self):
        return False

    def get_unparsed_session_notes(self):
        return [{{"id": "n1", "raw_text": "hip tight"}}]

    def get_unparsed_readiness(self):
        return []

    def get_flagged_entries(self):
        return [{{"session_date": "2026-10-03", "warning_level": "flag",
                  "body_parts": '["Left hip"]', "summary": "tight", "source": "note"}}]

    def get_parsed_readiness(self, limit=90):
        return [{{"date": "2026-10-03", "tightness_score": 3, "ai_tightness_severity": 2,
                  "pain_score": 0, "ai_warning_level": "monitor",
                  "ai_body_parts": '["Left hip"]', "ai_sensation_type": '["tight"]'}}]

    def get_macro_trend_data(self, days=90):
        return {{"biometrics": [], "sessions": []}}

    def get_sleep_fusion_history(self):
        return [{{"date": "2026-10-10", "source": "fused", "phantom_wake_minutes": 12,
                  "master_sleep_hours": 7.1, "oura_hypnogram": "", "master_hypnogram": "",
                  "garmin_hypnogram": ""}},
                {{"date": "2026-10-11", "source": "garmin_only"}}]

    def __getattr__(self, name):
        return lambda *a, **k: []


repo.get_repository = lambda: _Stub()
from views import insights
insights.render()
'''


def test_every_insights_tab_still_draws():
    at = AppTest.from_string(_SCRIPT.format(root=_ROOT), default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics.get("Session notes pending") == "1"
    assert metrics.get("Oura only") == "0" and metrics.get("Watch only") == "1", "F12"
    assert metrics.get("Biometric days available") == "0"


def test_an_unreadable_stage_is_a_warning_not_a_broken_page():
    """Fault F23: the stage is refused rather than guessed, and Engine Data
    says so instead of taking the whole Insights page down."""
    old = "    def get_current_stage(self):\n        return 2\n"
    new = ("    def get_current_stage(self):\n"
           "        from services.repository import StageUnknownError\n"
           "        raise StageUnknownError('the stored stage is missing')\n")
    script = _SCRIPT.format(root=_ROOT)
    assert old in script and "insights.render()" in script
    # The first test's run cached a readable engine state in this process.
    script = script.replace(old, new).replace(
        "insights.render()", "insights._engine_state.clear()\ninsights.render()")
    at = AppTest.from_string(script, default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    assert any("could not be read" in w.value for w in at.warning)

