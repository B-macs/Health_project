"""Fault F14 (rebuild Phase 2, fixed 2026-10-19): "Sync Garmin Activities" was
the only writer of the garmin_activities table and nothing ran it by itself,
so the heart-rate maximum behind session heart rate went stale unless the
button was pressed. The automatic chain now runs it, before session heart
rate. Fakes only; no network.
"""

from __future__ import annotations

from datetime import date, datetime

from services.repository import Repository

STEPS = ("sync_oura_all_if_due", "_garmin_daily_if_due_safe", "sync_garmin_activities_if_due",
         "sync_biometric_blend_if_due", "sync_session_hr_recent_if_due",
         "sync_metrics_history_if_due", "sync_sleep_fusion_if_due", "backup_supabase_if_due")


class _Chain:
    mirror_last_error = None

    def __init__(self):
        self.order: list[str] = []
        for name in STEPS:
            setattr(self, name, self._step(name))

    def _step(self, name):
        def run(*a, **k):
            self.order.append(name)
            return True, None
        return run

    def flush_supabase_mirror(self):
        return 0

    def garmin_sign_in_result(self, now=None):
        return None     # Garmin signed in: no line of its own

    run_home_syncs = Repository.run_home_syncs


def test_the_chain_syncs_the_activities_before_session_heart_rate():
    chain = _Chain()
    results = chain.run_home_syncs(today=date(2026, 10, 19), now=datetime(2026, 10, 19, 8, 0))
    assert "garmin_activities" in results
    assert chain.order.index("_garmin_daily_if_due_safe") < chain.order.index(
        "sync_garmin_activities_if_due") < chain.order.index("sync_session_hr_recent_if_due")


class _Garmin:
    def __init__(self, configured=True, limited=False):
        self.configured, self.limited = configured, limited
        self.synced: list[int] = []
        self.keys: list[str] = []

    def garmin_configured(self):
        return self.configured

    def garmin_rate_limited(self, now=None):
        return self.limited

    def sync_garmin_activities(self, limit=20):
        self.synced.append(limit)
        return limit

    def run_sync_if_due(self, key, work, hours=2, now=None):
        self.keys.append(key)
        work()
        return True, None

    sync_garmin_activities_if_due = Repository.sync_garmin_activities_if_due


def test_the_step_runs_throttled_and_never_without_garmin():
    on = _Garmin()
    assert on.sync_garmin_activities_if_due(now=datetime(2026, 10, 19, 8, 0)) == (True, None)
    assert on.synced == [20] and on.keys == ["garmin_activities"]
    off = _Garmin(configured=False)
    assert off.sync_garmin_activities_if_due() == (True, None) and off.synced == []
    limited = _Garmin(limited=True)
    assert limited.sync_garmin_activities_if_due() == (True, None) and limited.synced == []
