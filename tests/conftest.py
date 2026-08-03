"""Shared pytest fixtures.

The one thing here is filesystem isolation for the durable sync-throttle
markers. services/clients/local_cache.py writes .sync_state.json to the
project root by default, and Repository's throttle methods (sync_due /
mark_synced / mark_sync_attempted / in_sync_failure_cooldown, and everything
built on them: sync_oura_all_if_due, sync_biometric_blend_if_due,
sync_metrics_history_if_due, sync_sleep_fusion_if_due,
sync_session_hr_recent_if_due) both read and write it.

Without redirecting that path, running the suite would write a real
.sync_state.json into the working tree — and, worse, tests would see each
other's markers and pass or fail depending on execution order. Individual
tests may still monkeypatch local_cache._DEFAULT_PATH themselves (several do,
to point two Repository instances at one shared file); doing so inside the
test simply overrides this fixture for that test.
"""

import pytest

from services.clients import local_cache


@pytest.fixture(autouse=True)
def isolate_sync_state(tmp_path, monkeypatch):
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", tmp_path / "sync_state.json")
