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


def _real_supabase_url() -> str | None:
    """The checkout's real project URL, read only to compare against."""
    import tomllib
    from pathlib import Path
    secrets = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets.exists():
        return None
    try:
        url = tomllib.loads(secrets.read_text(encoding="utf-8")).get("SUPABASE_URL")
    except Exception:
        return None
    return url.rstrip("/") if isinstance(url, str) and url else None


@pytest.fixture(autouse=True, scope="session")
def no_real_supabase():
    """No test may reach the real Supabase project.

    Since 2026-10-09 Supabase is the system of record, so a request there
    from a test is a read of — or a write to — the athlete's real data. It
    happened that day: a test imported app.py, which rebuilt a copy of the
    real project and wrote a row into it. Tests use fake stores; one that
    reaches the real URL fails here, loudly, before it is sent."""
    from services import supabase_store

    real = _real_supabase_url()
    original = supabase_store.SupabaseStore._request

    def guarded(self, method, path, body=None, headers=None):
        if real and self.url.rstrip("/") == real:
            raise RuntimeError(
                f"a test tried to reach the real Supabase project ({method} "
                f"{path.split('?')[0]}); use a fake store")
        return original(self, method, path, body=body, headers=headers)

    supabase_store.SupabaseStore._request = guarded
    yield
    supabase_store.SupabaseStore._request = original
