"""Insights › Engine Data, rendered in Streamlit's test runtime.

The tab reads decision.engine_state and today.py's shared verdict since
2026-10-19 (move INS-4, fault F4). This renders it alone against a fake
repository holding a week of readings and a session, so the new reads and
the moved texts are exercised end to end. No network and no secrets.
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
from services.models import BiometricRecord, ExerciseEntry, SessionRecord

TODAY = date.today()


class _Repo:
    def get_biometric_rolling(self, days=28, today=None):
        end = today or TODAY
        return [BiometricRecord(date=(end - timedelta(days=n)).isoformat(), hrv_ms=45.0 + n % 3,
                                resting_heart_rate=55.0, sleep_duration_hours=7.2)
                for n in range(min(days, 30))]
    def get_daily_session_au_weighted(self, days=28, today=None):
        return [{{"date": (TODAY - timedelta(days=n)).isoformat(), "total_au": 300.0}}
                for n in range(0, days, 3)]
    def get_diagnostic_profile(self):
        return {{}}
    def get_current_stage(self):
        return 2
    def get_pain_free_streak(self, today=None):
        return 5
    def get_phases(self):
        return []
    def get_avg_tightness(self, days=14, today=None):
        return 2.0
    def hrv_trend_series(self, days=90, today=None):
        return {{"oura": {{}}}}
    def get_recent_sessions(self, days=60):
        return [SessionRecord(TODAY.isoformat(), 50, 6, 300.0,
                              [ExerciseEntry("Goblet Squat", "Squat", total_volume_kg=675.0)])]


repo.get_repository = lambda: _Repo()
from views import insights
insights._render_engine_data()
'''


def test_the_engine_data_tab_renders_from_the_moved_services():
    at = AppTest.from_string(_SCRIPT.format(root=_ROOT), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    page = "\n".join(m.value for m in at.markdown)
    assert "DIRECTIVE" in page
    assert "Stage Progression" in [h.value for h in at.subheader]
    assert any("ACWR" == metric.label for metric in at.metric)
