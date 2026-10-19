"""GET /api/today: Home's three cards (rebuild Phase 2, milestone 5).

What it pins:
- the answer is services/home.py:cards for the caller's day, through the
  contract's model, so the phone and the Streamlit Home page show the same
  numbers, bands and words;
- the day is the caller's (X-Local-Date), never the server's: a request at
  00:30 in Berlin is 22:30 UTC the day before, and must read the Berlin day;
- no day after the caller's day; the verdict under the caller's day only;
- a failed biometric read and an unreadable stage each say so (H20, F7);
- the router's own refusals and a bad parameter answer the one error shape.

A fake Repository with synthetic readings; no network.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from healthapi.deps import get_repository  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from healthapi.schemas import TodayOut  # noqa: E402
from services import home  # noqa: E402
from services.models import BiometricRecord  # noqa: E402

KEY = "test-engine-key"
TODAY = date(2026, 10, 19)


def _row(d: date) -> BiometricRecord:
    i = d.toordinal()          # a date's reading never depends on the window
    return BiometricRecord(
        date=d.isoformat(), hrv_ms=40.0 + i % 5, resting_heart_rate=55.0 + i % 3,
        sleep_duration_hours=7.0 + (i % 3) * 0.25,
        oura_hrv_balance=70.0 + i % 7, oura_recovery_index=80.0,
        oura_previous_night=75.0, oura_resting_heart_rate_score=85.0,
        oura_body_temperature=90.0, oura_previous_day_activity=65.0,
        oura_sleep_regularity=70.0, oura_activity_balance=72.0)


class FakeRepository:
    """Every read GET /api/today makes, over readings up to `last`."""

    def __init__(self, last: date = TODAY, stage_fails=False, bio_fails=False):
        self.last, self.stage_fails, self.bio_fails = last, stage_fails, bio_fails
        self.days_asked: list[date] = []

    def _ask(self, today):
        self.days_asked.append(today)

    def get_biometric_rolling(self, days=28, today=None):
        self._ask(today)
        if self.bio_fails:
            raise RuntimeError("the store did not answer")
        dates = [today - timedelta(days=days - 1 - k) for k in range(days)]
        return [_row(d) for d in dates if d <= self.last]

    def get_daily_session_au_weighted(self, days=28, today=None):
        self._ask(today)
        return [{"date": (today - timedelta(days=2)).isoformat(), "total_au": 320.0}]

    def get_metrics_history(self, start=None, end=None):
        return []

    def get_effective_wake_adjustments(self, start=None, end=None):
        return {}, {}

    def get_session_hr_history(self, start=None):
        return []

    def get_current_stage(self):
        if self.stage_fails:
            raise RuntimeError("the stored stage is missing")
        return 2

    def get_diagnostic_profile(self):
        return {}

    def get_pain_free_streak(self, today=None):
        self._ask(today)
        return 10

    def get_phases(self):
        return []

    def hrv_trend_series(self, days=120, today=None):
        self._ask(today)
        return {"oura": {}}


def _client(monkeypatch, repo):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.delenv("HEALTH_PROBES", raising=False)
    app = create_app(startup=False)
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app)


def _get(client, path, local=TODAY, method="get"):
    headers = {"X-Engine-Key": KEY}
    if local is not None:
        headers["X-Local-Date"] = local.isoformat()
    return getattr(client, method)(path, headers=headers)


def test_today_needs_the_callers_day(monkeypatch):
    with _client(monkeypatch, FakeRepository()) as c:
        r = _get(c, "/api/today", local=None)
    assert r.status_code == 400 and r.json() == {"error": "x_local_date_missing"}


def test_the_cards_are_the_home_service_for_the_callers_day(monkeypatch):
    with _client(monkeypatch, FakeRepository()) as c:
        body = _get(c, "/api/today").json()
    expected = TodayOut(**home.cards(FakeRepository(), None, TODAY)).model_dump(mode="json")
    assert body == expected
    assert body["date"] == TODAY.isoformat() and body["is_today"] and body["next"] is None
    assert body["date_label"] == "TODAY"
    assert [p["title"] for p in body["readiness"]["pair"]] == ["DAILY", "TREND"]
    assert body["readiness"]["headline"] is not None
    assert body["verdict"] is not None, "the decision shows under the caller's day"
    assert len(body["hrv_7d"]) == 7 and len(body["rhr_7d"]) == 7


def test_a_request_at_half_past_midnight_in_berlin_reads_the_berlin_day(monkeypatch):
    # 00:30 in Berlin is 22:30 UTC the day before: the server's clock says
    # yesterday, the phone says today. Every read must end on the phone's day.
    berlin_day = date.today() + timedelta(days=1)
    repo = FakeRepository(last=berlin_day)
    with _client(monkeypatch, repo) as c:
        body = _get(c, "/api/today", local=berlin_day).json()
    assert body["date"] == berlin_day.isoformat() and body["is_today"]
    assert repo.days_asked and set(repo.days_asked) == {berlin_day}


def test_a_past_day_has_no_verdict_and_steps_both_ways(monkeypatch):
    past = TODAY - timedelta(days=4)
    with _client(monkeypatch, FakeRepository()) as c:
        body = _get(c, f"/api/today?date={past}").json()
    assert body["date"] == past.isoformat() and not body["is_today"]
    assert body["verdict"] is None
    assert body["previous"] == (past - timedelta(days=1)).isoformat()
    assert body["next"] == (past + timedelta(days=1)).isoformat()
    assert body["date_label"] == past.isoformat()


def test_no_day_after_the_callers_day(monkeypatch):
    with _client(monkeypatch, FakeRepository()) as c:
        body = _get(c, f"/api/today?date={TODAY + timedelta(days=3)}").json()
    assert body["date"] == TODAY.isoformat() and body["next"] is None


def test_an_unreadable_stage_scores_no_strain_and_says_why(monkeypatch):
    with _client(monkeypatch, FakeRepository(stage_fails=True)) as c:
        strain = _get(c, "/api/today").json()["strain"]
    assert strain["value"] is None
    assert strain["header"] == "Not scored" and strain["description"] == home.STAGE_UNREAD
    assert strain["unscored_reason"] == home.STAGE_UNREAD


def test_a_failed_biometric_read_says_so(monkeypatch):
    with _client(monkeypatch, FakeRepository(bio_fails=True)) as c:
        r = _get(c, "/api/today")
    assert r.status_code == 200
    body = r.json()
    assert body["bio_failed"] is True
    assert body["readiness"]["headline"] is None and body["sleep"]["score"] is None


# ── the one error shape (Phase 0's open item) ────────────────────────────────

def test_an_unknown_route_answers_the_error_shape(monkeypatch):
    with _client(monkeypatch, FakeRepository()) as c:
        r = _get(c, "/api/nothing-here")
    assert r.status_code == 404 and r.json() == {"error": "not_found"}
    assert r.headers["Cache-Control"] == "no-store"


def test_a_wrong_method_answers_the_error_shape(monkeypatch):
    with _client(monkeypatch, FakeRepository()) as c:
        r = _get(c, "/api/today", method="delete")
    assert r.status_code == 405 and r.json() == {"error": "method_not_allowed"}


def test_a_bad_parameter_answers_the_error_shape(monkeypatch):
    with _client(monkeypatch, FakeRepository()) as c:
        r = _get(c, "/api/today?date=yesterday")
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"error"} and body["error"].startswith("invalid_request: query.date")
