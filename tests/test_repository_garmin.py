"""
Tests for services/repository.py's Garmin sync methods — field mapping,
graceful "not configured" behavior, and the activity-window filter used by
the training page's run/walk Complete button. No real network/login: a fake
Garmin client stub is injected directly (mirrors _FakeNotionClient/
_FakeSheetsClient in tests/test_repository.py), since garminconnect.Garmin
would otherwise attempt a real SSO login.
"""

from __future__ import annotations

from datetime import date, datetime

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


class _FakeGarminClient:
    def __init__(self, stats=None, sleep=None, stress=None, activities=None):
        self._stats = stats or {}
        self._sleep = sleep or {}
        self._stress = stress or {}
        self._activities = activities or []

    def get_stats(self, cdate):
        return self._stats

    def get_sleep_data(self, cdate):
        return self._sleep

    def get_stress_data(self, cdate):
        return self._stress

    def get_activities(self, start, limit):
        return self._activities[:limit]


def _repo_with_garmin(client: _FakeGarminClient) -> Repository:
    repo = Repository(_config(garmin_email="a@b.com", garmin_password="secret"))
    repo._garmin_client_obj = client
    repo._garmin_login_attempted = True
    return repo


# ─── garmin_configured ───────────────────────────────────────────────────────

def test_garmin_not_configured_by_default():
    repo = Repository(_config())
    assert repo.garmin_configured() is False
    assert repo._gc is None


def test_garmin_configured_when_credentials_present():
    repo = Repository(_config(garmin_email="a@b.com", garmin_password="secret"))
    assert repo.garmin_configured() is True


# ─── _garmin_daily_row ───────────────────────────────────────────────────────

def test_garmin_daily_row_maps_expected_fields():
    client = _FakeGarminClient(
        stats={
            "totalSteps": 8342, "restingHeartRate": 52, "averageStressLevel": 28,
            "totalKilocalories": 2210.0, "minHeartRate": 48, "maxHeartRate": 142,
        },
        sleep={"dailySleepDTO": {"sleepTimeSeconds": 27000, "sleepScores": {"overall": {"value": 81}}}},
        stress={"avgStressLevel": 28},
    )
    repo = _repo_with_garmin(client)
    row = repo._garmin_daily_row(client, date(2026, 7, 8))
    assert row == {
        "date": "2026-07-08", "steps": 8342, "resting_hr": 52, "avg_stress": 28,
        "sleep_score": 81, "sleep_hours": 7.5, "calories_total": 2210.0,
        "min_hr": 48, "max_hr": 142,
    }


def test_garmin_daily_row_tolerates_missing_keys():
    client = _FakeGarminClient()  # everything empty
    repo = _repo_with_garmin(client)
    row = repo._garmin_daily_row(client, date(2026, 7, 8))
    assert row["date"] == "2026-07-08"
    assert row["steps"] is None
    assert row["sleep_hours"] is None


# ─── _garmin_activity_row ────────────────────────────────────────────────────

def test_garmin_activity_row_maps_expected_fields():
    repo = _repo_with_garmin(_FakeGarminClient())
    act = {
        "activityId": 123456, "activityName": "Morning Run",
        "activityType": {"typeKey": "running"},
        "startTimeLocal": "2026-07-08 07:15:00",
        "duration": 1800.0, "distance": 5000.0,
        "averageHR": 148, "maxHR": 172, "calories": 410,
    }
    row = repo._garmin_activity_row(act)
    assert row == {
        "activity_id": "123456", "date": "2026-07-08", "name": "Morning Run",
        "type": "running", "start_time_local": "2026-07-08 07:15:00",
        "duration_minutes": 30.0, "distance_km": 5.0,
        "avg_hr": 148, "max_hr": 172, "calories": 410,
    }


# ─── get_recent_garmin_activity_minutes ─────────────────────────────────────

def test_recent_activity_minutes_sums_only_activities_within_window():
    activities = [
        {"activityId": 1, "startTimeLocal": "2026-07-08 09:50:00", "duration": 1800.0},  # 10 min ago
        {"activityId": 2, "startTimeLocal": "2026-07-08 07:00:00", "duration": 3600.0},  # 3h ago - outside window
    ]
    client = _FakeGarminClient(activities=activities)
    repo = _repo_with_garmin(client)
    minutes, matched = repo.get_recent_garmin_activity_minutes(
        window_minutes=60, now=datetime(2026, 7, 8, 10, 0, 0),
    )
    assert minutes == 30.0
    assert len(matched) == 1
    assert matched[0]["activityId"] == 1


def test_recent_activity_minutes_returns_zero_when_not_configured():
    repo = Repository(_config())
    minutes, matched = repo.get_recent_garmin_activity_minutes(60)
    assert (minutes, matched) == (0.0, [])


def test_recent_activity_minutes_ignores_unparseable_timestamps():
    activities = [{"activityId": 1, "startTimeLocal": "", "duration": 600.0}]
    client = _FakeGarminClient(activities=activities)
    repo = _repo_with_garmin(client)
    minutes, matched = repo.get_recent_garmin_activity_minutes(60, now=datetime(2026, 7, 8, 10, 0, 0))
    assert (minutes, matched) == (0.0, [])


# ─── sync_garmin_daily_if_due ────────────────────────────────────────────────
# get_config_value/set_config are monkeypatched with a plain in-memory dict
# here rather than a full fake Notion client — this is testing the due-check
# orchestration, not Notion's config read/write mechanics (already covered
# by tests/test_repository.py's phases-related tests).

def _repo_with_due_check(client, config_values: dict, sync_calls: list) -> Repository:
    repo = _repo_with_garmin(client)
    repo.get_config_value = lambda key: config_values.get(key)
    repo.set_config = lambda key, value, today=None: config_values.__setitem__(key, value)
    repo.sync_garmin_daily = lambda days=7, today=None: sync_calls.append((days, today)) or days
    return repo


def test_sync_if_due_skips_entirely_when_not_configured():
    repo = Repository(_config())
    calls = []
    repo.sync_garmin_daily = lambda **kw: calls.append(kw) or 7
    ok, err = repo.sync_garmin_daily_if_due(today=date(2026, 7, 13))
    assert (ok, err) == (True, None)
    assert calls == []


def test_sync_if_due_runs_first_time_this_week():
    calls, config = [], {}
    repo = _repo_with_due_check(_FakeGarminClient(), config, calls)
    ok, err = repo.sync_garmin_daily_if_due(today=date(2026, 7, 13))  # a Monday
    assert (ok, err) == (True, None)
    assert calls == [(7, date(2026, 7, 13))]
    assert config["garmin_daily_last_synced_week"] == "2026-07-13"


def test_sync_if_due_skips_when_already_synced_this_week():
    calls = []
    config = {"garmin_daily_last_synced_week": "2026-07-13"}
    repo = _repo_with_due_check(_FakeGarminClient(), config, calls)
    ok, err = repo.sync_garmin_daily_if_due(today=date(2026, 7, 15))  # same week, Wed
    assert (ok, err) == (True, None)
    assert calls == []


def test_sync_if_due_runs_again_in_a_new_week():
    calls = []
    config = {"garmin_daily_last_synced_week": "2026-07-06"}  # last week's Monday
    repo = _repo_with_due_check(_FakeGarminClient(), config, calls)
    ok, err = repo.sync_garmin_daily_if_due(today=date(2026, 7, 13))  # new week's Monday
    assert (ok, err) == (True, None)
    assert calls == [(7, date(2026, 7, 13))]
    assert config["garmin_daily_last_synced_week"] == "2026-07-13"


def test_sync_if_due_returns_error_on_sync_failure():
    repo = _repo_with_garmin(_FakeGarminClient())
    repo.get_config_value = lambda key: None
    repo.set_config = lambda key, value, today=None: None

    def _boom(**kw):
        raise RuntimeError("garmin down")

    repo.sync_garmin_daily = _boom
    ok, err = repo.sync_garmin_daily_if_due(today=date(2026, 7, 13))
    assert ok is False
    assert "garmin down" in err
