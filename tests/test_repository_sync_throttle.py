"""
Tests for Repository's durable sync throttles — sync_due / mark_synced /
mark_sync_attempted / in_sync_failure_cooldown / run_sync_if_due, and the
five *_if_due wrappers built on them.

The bug these exist for: every one of these syncs recorded only its SUCCESS,
and recorded it after the work finished. A sync that raised partway therefore
left no marker at all, so the next page load ran the identical heavy sync
again and failed the same way — the throttle never engaged, and every app
open paid a full failing sync. sync_oura_all is the one that hits this in
practice: it spends two Sheets writes per row across five tabs, which for a
7-day window runs into the 60-operations-per-minute quota that app.py's own
_run_startup_sync note describes hitting.

Recording the ATTEMPT before starting is what fixes it, which is why most of
what's asserted here is failure behaviour rather than the happy path.

Three of these syncs (blend, metrics history, sleep fusion) previously had no
durable throttle of any kind — only st.cache_data's in-memory TTL, which dies
with the process and is wiped by the blanket clear() on every check-in save.

tests/conftest.py points local_cache._DEFAULT_PATH at a tmp_path for every
test, so none of this touches the real .sync_state.json.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from services.config import Config
from services.repository import Repository


def _config(**overrides) -> Config:
    base = dict(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_biometrics="db-biometrics",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )
    base.update(overrides)
    return Config(**base)


NOW = datetime(2026, 8, 1, 8, 0, 0)


# ─── sync_due / mark_synced ──────────────────────────────────────────────────

def test_due_when_never_synced():
    assert Repository(_config()).sync_due("thing", hours=2, now=NOW) is True


def test_not_due_immediately_after_a_success():
    repo = Repository(_config())
    repo.mark_synced("thing", when=NOW)
    assert repo.sync_due("thing", hours=2, now=NOW + timedelta(minutes=90)) is False


def test_due_again_once_the_window_elapses():
    repo = Repository(_config())
    repo.mark_synced("thing", when=NOW)
    assert repo.sync_due("thing", hours=2, now=NOW + timedelta(hours=2, seconds=1)) is True


def test_markers_are_namespaced_per_key():
    repo = Repository(_config())
    repo.mark_synced("oura", when=NOW)
    assert repo.sync_due("oura", hours=2, now=NOW) is False
    assert repo.sync_due("sleep_fusion", hours=2, now=NOW) is True


def test_markers_survive_a_new_repository_instance(tmp_path, monkeypatch):
    """A Streamlit process restart, or a st.cache_data.clear() elsewhere in
    the app — neither of which an in-memory cache survives."""
    from services.clients import local_cache
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", tmp_path / "state.json")

    Repository(_config()).mark_synced("thing", when=NOW)
    assert Repository(_config()).sync_due("thing", hours=2, now=NOW + timedelta(minutes=5)) is False


# ─── Failure cooldown — the actual regression ────────────────────────────────

def test_a_failed_sync_is_not_retried_on_the_very_next_load():
    repo = Repository(_config())

    def _boom():
        raise RuntimeError("429 quota exceeded")

    ok, err = repo.run_sync_if_due("oura", _boom, hours=2, now=NOW)
    assert ok is False
    assert "429" in err
    # Old behaviour: no marker written, so this was True and the whole
    # failing sync ran again immediately, forever.
    assert repo.sync_due("oura", hours=2, now=NOW + timedelta(seconds=30)) is False


def test_a_failed_sync_retries_after_the_cooldown():
    repo = Repository(_config())
    repo.mark_sync_attempted("oura", when=NOW)
    assert repo.sync_due("oura", hours=2, now=NOW + timedelta(minutes=14)) is False
    assert repo.sync_due("oura", hours=2, now=NOW + timedelta(minutes=16)) is True


def test_failure_cooldown_is_far_shorter_than_the_success_interval():
    """A transient failure must recover in minutes, not wait out the full
    success window."""
    repo = Repository(_config())
    repo.mark_sync_attempted("oura", when=NOW)
    assert repo.in_sync_failure_cooldown("oura", now=NOW + timedelta(minutes=20)) is False
    assert repo.sync_due("oura", hours=2, now=NOW + timedelta(minutes=20)) is True


def test_a_success_clears_the_attempt_marker():
    """Otherwise every successful sync leaves a cooldown behind it, and
    in_sync_failure_cooldown stops meaning 'recently failed'."""
    repo = Repository(_config())
    repo.mark_sync_attempted("oura", when=NOW)
    repo.mark_synced("oura", when=NOW)
    assert repo.last_sync_attempted("oura") is None
    assert repo.in_sync_failure_cooldown("oura", now=NOW + timedelta(minutes=1)) is False


def test_failed_run_does_not_write_a_success_marker():
    repo = Repository(_config())
    repo.run_sync_if_due("oura", lambda: (_ for _ in ()).throw(RuntimeError("nope")),
                         hours=2, now=NOW)
    assert repo.last_synced("oura") is None


def test_successful_run_writes_the_success_marker():
    repo = Repository(_config())
    ok, err = repo.run_sync_if_due("oura", lambda: None, hours=2, now=NOW)
    assert (ok, err) == (True, None)
    assert repo.last_synced("oura") == NOW


def test_run_sync_if_due_skips_work_entirely_when_not_due():
    repo = Repository(_config())
    repo.mark_synced("oura", when=NOW)
    calls = []
    ok, err = repo.run_sync_if_due("oura", lambda: calls.append(1),
                                   hours=2, now=NOW + timedelta(minutes=5))
    assert (ok, err) == (True, None)   # "nothing to do" is not an error
    assert calls == []


# ─── Clock skew ──────────────────────────────────────────────────────────────

def test_a_future_dated_attempt_marker_does_not_disable_the_sync():
    """Only reachable via clock skew or a hand-edited state file. Silently
    disabling a sync for hours is far worse than one extra attempt."""
    repo = Repository(_config())
    repo.mark_sync_attempted("oura", when=NOW + timedelta(hours=5))
    assert repo.in_sync_failure_cooldown("oura", now=NOW) is False
    assert repo.sync_due("oura", hours=2, now=NOW) is True


def test_a_future_dated_success_marker_does_not_disable_the_sync():
    repo = Repository(_config())
    repo.mark_synced("oura", when=NOW + timedelta(days=3))
    assert repo.sync_due("oura", hours=2, now=NOW) is True


def test_corrupted_marker_is_ignored_rather_than_raising(tmp_path, monkeypatch):
    from services.clients import local_cache
    path = tmp_path / "state.json"
    monkeypatch.setattr(local_cache, "_DEFAULT_PATH", path)
    path.write_text('{"oura_last_synced": "not-a-timestamp"}')
    repo = Repository(_config())
    assert repo.last_synced("oura") is None
    assert repo.sync_due("oura", hours=2, now=NOW) is True


# ─── Back-compat: the old oura_* names still work ────────────────────────────
# views/insights.py and the Sync page still call these.

def test_oura_last_synced_and_mark_oura_synced_round_trip():
    repo = Repository(_config())
    repo.mark_oura_synced(when=NOW)
    assert repo.oura_last_synced() == NOW
    assert repo.oura_sync_due(hours=2, now=NOW + timedelta(minutes=30)) is False
    assert repo.oura_sync_due(hours=2, now=NOW + timedelta(hours=3)) is True


# ─── The *_if_due wrappers ───────────────────────────────────────────────────

def test_oura_sync_skipped_when_not_configured():
    repo = Repository(_config())
    calls = []
    repo.sync_oura_all = lambda **kw: calls.append(kw)
    assert repo.sync_oura_all_if_due(days=7, now=NOW) == (True, None)
    assert calls == []


def test_oura_sync_runs_and_marks_when_configured():
    repo = Repository(_config(oura_token="tok"))
    calls = []
    repo.sync_oura_all = lambda **kw: calls.append(kw)
    assert repo.sync_oura_all_if_due(days=7, now=NOW) == (True, None)
    assert calls == [{"days": 7, "today": None}]
    assert repo.last_synced("oura") == NOW


def test_oura_sync_is_throttled_on_the_second_call():
    repo = Repository(_config(oura_token="tok"))
    calls = []
    repo.sync_oura_all = lambda **kw: calls.append(kw)
    repo.sync_oura_all_if_due(days=7, now=NOW)
    repo.sync_oura_all_if_due(days=7, now=NOW + timedelta(minutes=30))
    assert len(calls) == 1


def test_oura_sync_failure_surfaces_and_then_backs_off():
    """The whole point: a quota failure must not re-run on the next open."""
    repo = Repository(_config(oura_token="tok"))
    attempts = []

    def _boom(**kw):
        attempts.append(kw)
        raise RuntimeError("quota")

    repo.sync_oura_all = _boom
    ok, err = repo.sync_oura_all_if_due(days=7, now=NOW)
    assert ok is False and "quota" in err
    repo.sync_oura_all_if_due(days=7, now=NOW + timedelta(minutes=1))
    assert len(attempts) == 1


def test_biometric_blend_sync_is_throttled():
    repo = Repository(_config())
    calls = []
    repo.sync_biometric_blend = lambda days=7, today=None: calls.append(days)
    assert repo.sync_biometric_blend_if_due(days=7, now=NOW) == (True, None)
    repo.sync_biometric_blend_if_due(days=7, now=NOW + timedelta(minutes=45))
    assert calls == [7]


def test_metrics_history_sync_is_throttled():
    repo = Repository(_config())
    calls = []
    repo.sync_metrics_history = lambda days=7, today=None: calls.append(days)
    assert repo.sync_metrics_history_if_due(days=7, now=NOW) == (True, None)
    repo.sync_metrics_history_if_due(days=7, now=NOW + timedelta(minutes=45))
    assert calls == [7]


def test_metrics_history_sync_runs_again_after_two_hours():
    repo = Repository(_config())
    calls = []
    repo.sync_metrics_history = lambda days=7, today=None: calls.append(days)
    repo.sync_metrics_history_if_due(days=7, now=NOW)
    repo.sync_metrics_history_if_due(days=7, now=NOW + timedelta(hours=2, minutes=1))
    assert calls == [7, 7]


def test_sleep_fusion_sync_is_throttled():
    """Cheap per call (no device APIs) but not free — it re-derives 14 nights
    and rewrites the whole tab."""
    repo = Repository(_config())
    calls = []
    repo.sync_sleep_fusion = lambda days=7, today=None: calls.append(days)
    assert repo.sync_sleep_fusion_if_due(days=14, now=NOW) == (True, None)
    repo.sync_sleep_fusion_if_due(days=14, now=NOW + timedelta(minutes=45))
    assert calls == [14]


def test_session_hr_sync_skipped_when_garmin_not_configured():
    repo = Repository(_config())
    calls = []
    repo.sync_session_hr_for_date = lambda d, hr_rest=None: calls.append(d)
    assert repo.sync_session_hr_recent_if_due(days=2, now=NOW) == (True, None)
    assert calls == []


def test_session_hr_sync_covers_the_requested_window():
    repo = Repository(_config(garmin_email="a@b.c", garmin_password="pw"))
    calls = []
    repo.sync_session_hr_for_date = lambda d, hr_rest=None: calls.append(d)
    ok, err = repo.sync_session_hr_recent_if_due(
        days=2, today=date(2026, 8, 1), now=NOW,
    )
    assert (ok, err) == (True, None)
    assert calls == [date(2026, 8, 1), date(2026, 7, 31)]


def test_session_hr_sync_is_throttled():
    repo = Repository(_config(garmin_email="a@b.c", garmin_password="pw"))
    calls = []
    repo.sync_session_hr_for_date = lambda d, hr_rest=None: calls.append(d)
    repo.sync_session_hr_recent_if_due(days=2, today=date(2026, 8, 1), now=NOW)
    repo.sync_session_hr_recent_if_due(
        days=2, today=date(2026, 8, 1), now=NOW + timedelta(minutes=30),
    )
    assert len(calls) == 2   # one window only, not two
