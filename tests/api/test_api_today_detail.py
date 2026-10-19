"""Today's drill-downs and the wake-time correction (rebuild Phase 2,
milestone 5): GET /api/today/readiness, /api/today/sleep, /api/today/strain
and PUT /api/sleep/wake-adjustment over services/home_detail.py.

What it pins:
- each answer is the service's, through the contract's model;
- every window ends on the day asked for, never after the caller's day;
- the Sleep screen's all-or-nothing rule: no score, no night panels and no
  wake stepper; a watch-only night says there is no score (H35, H36);
- each chart carries its axes and one tap detail per point;
- the strain panel's stage start is the one active on the day shown (F27),
  and an unreadable stage leaves the panel out with its reason (F7);
- the wake correction: absolute values only, the stepper's values only, a
  scored night only, never a fused night (F5); a repeat stores one value.

A fake Repository with synthetic readings; no network.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from healthapi.deps import get_repository  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from healthapi.schemas import (ReadinessDetailOut, SleepDetailOut,  # noqa: E402
                               StrainDetailOut)
from services import dashboard as dash  # noqa: E402
from services import home, home_detail, plan, rules, sleep_screen, strain_screen  # noqa: E402
from services.models import BiometricRecord, Phase  # noqa: E402

KEY = "test-engine-key"
TODAY = date(2026, 10, 19)
OURA_KEYS = ("oura_hrv_balance", "oura_recovery_index", "oura_previous_night",
             "oura_resting_heart_rate_score", "oura_body_temperature",
             "oura_previous_day_activity", "oura_sleep_regularity", "oura_activity_balance")


def _bio(day: date) -> BiometricRecord:
    i = day.toordinal()        # a night's reading never depends on the window
    fields = {"date": day.isoformat(), "hrv_ms": 42.0 + i % 5,
              "resting_heart_rate": 54.0 + i % 3,
              "sleep_duration_hours": 7.0 + (i % 4) / 4,
              **{k: 70.0 + (i + j) % 20 for j, k in enumerate(OURA_KEYS)},
              "oura_sleep_total_seconds": 25590.0 - 60 * (i % 5),
              "oura_sleep_efficiency": 85.0, "oura_sleep_latency_seconds": 600.0,
              "oura_sleep_deep_seconds": 3600.0, "oura_sleep_rem_seconds": 6990.0,
              "oura_sleep_awake_seconds": 3500.0, "oura_sleep_restfulness": 70.0,
              "oura_sleep_restless_periods": 40.0,
              "oura_sleep_bedtime_start": f"{(day - timedelta(days=1)).isoformat()}T23:00:00+02:00"}
    known = BiometricRecord.__dataclass_fields__
    return BiometricRecord(**{k: v for k, v in fields.items() if k in known})


def _night(end: str) -> dict:
    night = date.fromisoformat(end)
    series = {"interval": 300, "timestamp": f"{(night - timedelta(days=1)).isoformat()}T23:05:00+01:00"}
    return {
        "total_seconds": 25590.0, "time_in_bed_seconds": 32168.0, "efficiency": 80.0,
        "lowest_heart_rate": 56.0, "deep_seconds": 3600.0, "light_seconds": 15000.0,
        "rem_seconds": 6990.0, "awake_seconds": 6578.0, "naps": [],
        "average_heart_rate": 61.0, "average_hrv": 44.0, "average_breath": 14.2,
        "temperature_deviation": -0.12,
        "hypnogram_30sec": "4422211223334422", "movement_30sec": "",
        "hr_series": {**series, "items": [60, 58, None, 57, 56, 59, 61]},
        "hrv_series": {**series, "items": [40, 44, 47, None, 45, 42]},
        "bedtime_start": f"{(night - timedelta(days=1)).isoformat()}T23:00:27.000+01:00",
        "bedtime_end": f"{end}T07:56:35.000+01:00"}


BLOCK_B = Phase(4, "Block B", "2026-09-21", 28, "complete")
GOAL_BLOCK = Phase(5, "12-week block", "2026-10-19", 84, "active")


class HomeFake:
    """Every read the three drill-downs make, and the wake-time writer.
    `ring_last` is the last night the ring recorded; `fusion` is a fusion row
    for the day asked for; `wake` is (minutes, source) for every night."""

    def __init__(self, ring_last: date = TODAY, fusion: dict | None = None,
                 wake: tuple[float, str] | None = None, stage_fails=False,
                 detail_last: date | None = None, night_fails=False, naps=(),
                 history=True, session_days=None):
        self.ring_last, self.fusion, self.wake = ring_last, fusion, wake
        self.stage_fails, self.night_fails, self.naps = stage_fails, night_fails, list(naps)
        self.detail_last = detail_last or ring_last
        self.history = history
        #: Days before the day asked for that logged a session (default every other day).
        self.session_days = session_days
        self.stored: dict[str, float] = {}

    def get_biometric_rolling(self, days=28, today=None):
        dates = [today - timedelta(days=days - 1 - k) for k in range(days)]
        return [_bio(d) for d in dates if d <= self.ring_last]

    def _session_offsets(self, days):
        return self.session_days if self.session_days is not None else range(0, days, 2)

    def get_daily_session_au_weighted(self, days=28, today=None):
        return [{"date": (today - timedelta(days=n)).isoformat(), "total_au": 300.0 + n}
                for n in self._session_offsets(days)]

    def get_metrics_history(self, start=None, end=None):
        if not self.history:
            return []
        end_d = date.fromisoformat(end)
        return [{"date": (end_d - timedelta(days=n)).isoformat(),
                 "readiness_score": 60.0 + n % 7, "sleep_score": 75.0 + n % 5,
                 "strain": 9.0 + n % 4} for n in range(0, 60)]

    def get_effective_wake_adjustments(self, start=None, end=None):
        if self.stored:
            return dict(self.stored), {k: "manual" for k in self.stored}
        if self.wake is None:
            return {}, {}
        minutes, source = self.wake
        nights = [date.fromisoformat(end) - timedelta(days=n) for n in range(60)]
        return ({d.isoformat(): minutes for d in nights},
                {d.isoformat(): source for d in nights})

    def set_wake_time_adjustment(self, d, minutes):
        self.stored[d.isoformat()] = minutes

    def get_session_hr_history(self, start=None):
        return []

    def get_current_stage(self):
        if self.stage_fails:
            raise RuntimeError("the stored stage is missing")
        return 2

    def get_phases(self):
        return [BLOCK_B, GOAL_BLOCK]

    def get_daily_region_au(self, days=28, today=None):
        return {"rows": [{"date": (today - timedelta(days=n)).isoformat(), "upper_body": 80.0,
                          "core": 70.0, "lower_body": 150.0 + n, "unattributed": 10.0,
                          "total_au": 310.0 + n, "regions_known": True}
                         for n in self._session_offsets(days)],
                "unmapped_names": ["Sun Salutation"]}

    def get_sleep_night_details(self, start, end):
        if self.night_fails:
            raise RuntimeError("the night detail did not load")
        if date.fromisoformat(end) > self.detail_last:
            return {}
        night = _night(end)
        if self.naps:
            nap_seconds = sum(n["total_seconds"] for n in self.naps)
            night.update(naps=self.naps, nap_seconds=nap_seconds,
                         day_total_seconds=night["total_seconds"] + nap_seconds)
        return {end: night}

    def get_sleep_fusion_history(self, start, end):
        return [{**self.fusion, "date": end}] if self.fusion else []

    def get_oura_daily_sleep_context(self, start, end):
        return {end: {"spo2_average": 97.0, "breathing_disturbance_index": 3.0}}

    def get_diagnostic_profile(self):
        return {}

    def get_pain_free_streak(self, today=None):
        return 4

    def hrv_trend_series(self, days=90, today=None):
        return {"oura": {}}


def _client(monkeypatch, repo):
    monkeypatch.setenv("HEALTH_ENGINE_KEY", KEY)
    monkeypatch.delenv("HEALTH_PROBES", raising=False)
    app = create_app(startup=False)
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app)


def _headers(local: date = TODAY) -> dict:
    return {"X-Engine-Key": KEY, "X-Local-Date": local.isoformat()}


def _get(monkeypatch, repo, path):
    with _client(monkeypatch, repo) as c:
        r = c.get(path, headers=_headers())
    assert r.status_code == 200, r.text
    return r.json()


def _put_wake(monkeypatch, repo, day: date, minutes):
    with _client(monkeypatch, repo) as c:
        return c.put("/api/sleep/wake-adjustment", headers=_headers(),
                     json={"date": day.isoformat(), "minutes": minutes})


# ── Readiness ────────────────────────────────────────────────────────────────

def test_readiness_detail_is_the_service_for_the_callers_day(monkeypatch):
    body = _get(monkeypatch, HomeFake(), "/api/today/readiness")
    assert body == ReadinessDetailOut(**home_detail.readiness_detail(
        HomeFake(), None, TODAY)).model_dump(mode="json")
    assert body["title"] == "READINESS · TODAY" and body["screen_title"] == "Readiness History"
    assert body["contributors"]["scored"] and body["contributors"]["rows"]
    assert [m["label"] for m in body["key_metrics"]] == [
        "Resting Heart Rate", "Heart Rate Variability", "Body Temperature", "Respiratory Rate"]
    assert [p["key"] for p in body["overnight"]] == ["hr_series", "hrv_series"]
    hr = body["overnight"][0]
    assert hr["headline"] == 56 and hr["secondary_label"] == "Average"
    assert len(hr["bands"]) == len(hr["values"]) and hr["bands"][0]["detail"]["rows"]


def test_the_30_day_trend_ends_on_the_day_and_details_every_point(monkeypatch):
    past = TODAY - timedelta(days=9)
    body = _get(monkeypatch, HomeFake(), f"/api/today/readiness?date={past}")
    assert body["previous"] == (past - timedelta(days=1)).isoformat()
    assert body["next"] == (past + timedelta(days=1)).isoformat() and not body["is_today"]
    trend = body["trend"]
    assert len(trend["dates"]) == home.TREND_DAYS and trend["dates"][-1] == past.isoformat()
    assert trend["axis"] and 0 <= trend["axis"]["lo"] and trend["axis"]["hi"] <= 100
    assert len(trend["points"]) == home.TREND_DAYS and not trend["empty"]
    last = trend["points"][-1]
    assert last["open_date"] == past.isoformat()
    # The day's OTHER stored metrics ride with each point, never itself.
    assert {r["label"] for r in last["extra"]} == {"Sleep Score", "Strain"}


def test_a_failed_biometric_read_says_so_in_the_contributors(monkeypatch):
    class Failing(HomeFake):
        def get_biometric_rolling(self, days=28, today=None):
            raise RuntimeError("the store did not answer")
    body = _get(monkeypatch, Failing(), "/api/today/readiness")
    assert body["bio_failed"] and not body["contributors"]["scored"]
    assert body["contributors"]["unscored_reason"] == dash.readiness_unscored_reason(True, False)


# ── Sleep ────────────────────────────────────────────────────────────────────

def test_a_scored_night_carries_every_panel_and_the_wake_stepper(monkeypatch):
    body = _get(monkeypatch, HomeFake(), "/api/today/sleep")
    assert body == SleepDetailOut(**home_detail.sleep_detail(
        HomeFake(), None, TODAY)).model_dump(mode="json")
    assert body["mode"] == sleep_screen.SCORED and body["contributors"]["scored"]
    night = body["night"]
    assert [s["code"] for s in night["stages"]] == list(home_detail.STAGE_ROW_CODES)
    hyp = night["hypnogram"]
    assert not hyp["empty"] and hyp["note"] == "plain"
    assert {run["name"] for run in hyp["stages"]["runs"]} <= set(sleep_screen.STAGE_NAMES.values())
    assert hyp["stages"]["bands"][0]["detail"]["rows"][0]["label"] == "Stage"
    assert night["vitals"] and night["debt"] is not None
    wake = body["wake"]
    assert wake["editable"] and wake["label"] == "No adjustment"
    assert (wake["decrease_to"], wake["increase_to"]) == (0.0, 5.0)


def test_no_score_means_no_night_panels_and_no_stepper(monkeypatch):
    # H35, the all-or-nothing rule: the ring recorded nothing last night.
    body = _get(monkeypatch, HomeFake(ring_last=TODAY - timedelta(days=1)), "/api/today/sleep")
    assert body["mode"] == sleep_screen.BLANK
    assert body["night"] is None and body["wake"] is None and body["watch_only"] is None
    assert not body["contributors"]["scored"] and body["contributors"]["unscored_reason"]
    assert body["masthead"]["label"] == dash.sleep_meta(None, 8.0, None)[2]


def test_a_watch_only_night_says_it_has_no_score_and_shows_the_watch(monkeypatch):
    fusion = {"source": "garmin_only", "master_hypnogram": "22233344221", "minutes": 420,
              "master_deep_minutes": 60, "master_light_minutes": 240,
              "master_rem_minutes": 100, "master_awake_minutes": 20,
              "window_start_utc": f"{(TODAY - timedelta(days=1)).isoformat()}T22:00:00+00:00"}
    body = _get(monkeypatch, HomeFake(ring_last=TODAY - timedelta(days=1), fusion=fusion),
                "/api/today/sleep")
    assert body["mode"] == sleep_screen.WATCH_ONLY and body["night"] is None
    stages = body["watch_only"]["stages"]
    assert [s["name"] for s in stages] == ["Awake", "REM", "Light", "Deep"]
    assert body["watch_only"]["hypnogram"]["note"] == "watch"


def test_a_fused_night_offers_no_stepper_and_says_why(monkeypatch):
    fusion = {"source": "fused", "master_hypnogram": "4422211223334422", "minutes": 476,
              "phantom_wake_minutes": 12, "master_movement": "1122334411112222",
              "movement_source": "fused", "movement_position_shifts": 3}
    body = _get(monkeypatch, HomeFake(fusion=fusion, wake=(12.0, "fusion")), "/api/today/sleep")
    movement = body["night"]["hypnogram"]["movement"]
    assert movement["title"] == sleep_screen.SOURCE_TITLES["fused"]
    assert "3 position shifts" in movement["details"]
    assert {run["name"] for run in movement["runs"]} <= set(sleep_screen.MOVEMENT_NAMES.values())
    assert movement["bands"][0]["detail"]["rows"][0]["label"] == "Movement"
    assert body["title"] == "SLEEP · TODAY · ADJUSTED" and body["adjusted"]
    assert body["night"]["hypnogram"]["note"] == "phantom"
    assert body["night"]["hypnogram"]["phantom_minutes"] == 12
    assert not body["wake"]["editable"] and "fused night" in body["wake"]["caption"]
    assert body["nights_adjusted"] == home.TREND_DAYS


# ── Strain ───────────────────────────────────────────────────────────────────

def test_strain_detail_names_the_regions_and_the_stage_ceiling(monkeypatch):
    body = _get(monkeypatch, HomeFake(), "/api/today/strain")
    assert body == StrainDetailOut(**home_detail.strain_detail(
        HomeFake(), None, TODAY)).model_dump(mode="json")
    region = body["region"]
    assert region["state"] == "split"
    assert [r["name"] for r in region["regions"]] == ["Upper body", "Core", "Lower body"]
    assert region["ceiling"] == rules.STAGE_CONSTRAINTS[2]["acwr_ceiling"]
    assert len(body["hrv_7d"]["dates"]) == 7 and body["hrv_7d"]["unit"] == "ms"
    assert body["hrv_7d"]["points"][-1]["rows"][0]["label"] == "Heart Rate Variability"
    assert body["source"]["kind"] == "rpe" and body["source"]["label"]
    assert body["trend"]["axis"]["hi"] <= home.SCALES["strain"]


def test_the_region_acwr_starts_at_the_stage_active_on_the_day_shown(monkeypatch):
    # F27: a day in Block B took the 12-week block's start (the phase active
    # on the server's today), a start AFTER the day itself.
    seen = []
    real = strain_screen.region_data

    def spy(region_au, stage, day, stage_start, snapshot, show_week):
        seen.append(stage_start)
        return real(region_au, stage, day, stage_start, snapshot, show_week)

    monkeypatch.setattr(strain_screen, "region_data", spy)
    past = date(2026, 10, 15)
    _get(monkeypatch, HomeFake(), f"/api/today/strain?date={past}")
    assert seen == [plan.current_stage_start([BLOCK_B, GOAL_BLOCK], past)]
    assert seen[0] == date(2026, 9, 21)


def test_an_unreadable_stage_leaves_the_region_panel_out_and_says_why(monkeypatch):
    body = _get(monkeypatch, HomeFake(stage_fails=True), "/api/today/strain")
    assert body["region"] is None and body["stage_unread"] == home.STAGE_UNREAD


# ── The wake-time correction ─────────────────────────────────────────────────

def test_a_correction_is_stored_once_and_returned(monkeypatch):
    repo = HomeFake()
    first = _put_wake(monkeypatch, repo, TODAY, 10)
    again = _put_wake(monkeypatch, repo, TODAY, 10)
    assert first.status_code == 200 and again.json() == first.json()
    assert repo.stored == {TODAY.isoformat(): 10.0}
    assert first.json()["label"] == "−10 min" and first.json()["decrease_to"] == 5.0


@pytest.mark.parametrize("minutes", [7, -5, 125, 2.5])
def test_only_the_steppers_values_are_taken(monkeypatch, minutes):
    r = _put_wake(monkeypatch, HomeFake(), TODAY, minutes)
    assert r.status_code == 422 and r.json() == {"error": "minutes_invalid"}


def test_no_correction_for_a_night_after_the_callers_day(monkeypatch):
    r = _put_wake(monkeypatch, HomeFake(), TODAY + timedelta(days=1), 10)
    assert r.status_code == 422 and r.json() == {"error": "future_day"}


def test_no_correction_for_a_night_with_no_score(monkeypatch):
    repo = HomeFake(ring_last=TODAY - timedelta(days=1))
    r = _put_wake(monkeypatch, repo, TODAY, 10)
    assert r.status_code == 409 and r.json() == {"error": "night_not_scored"}
    assert repo.stored == {}


def test_no_correction_where_the_fusion_figure_wins(monkeypatch):
    repo = HomeFake(fusion={"source": "fused", "master_hypnogram": "4422",
                            "phantom_wake_minutes": 12}, wake=(12.0, "fusion"))
    r = _put_wake(monkeypatch, repo, TODAY, 20)
    assert r.status_code == 409 and r.json() == {"error": "fusion_applies"}
    assert repo.stored == {}


def test_the_stepper_values_are_the_steppers_own():
    reached, value = {0.0}, 0.0
    for _ in range(40):
        value = dash.step_wake_time_adjustment(value, +1)
        reached.add(value)
    assert reached == home_detail.WAKE_VALUES


def test_a_failed_night_read_says_so_rather_than_showing_nothing(monkeypatch):
    # H37: a read that failed must not look like a night with no data.
    body = _get(monkeypatch, HomeFake(night_fails=True), "/api/today/sleep")
    assert body["mode"] == sleep_screen.DETAIL_FAILED and body["night"] is None
    assert body["contributors"]["scored"], "the score itself was read"


def test_a_night_the_detail_holds_but_the_rows_lack_is_not_blamed_on_the_ring(monkeypatch):
    # H58: the night detail holds last night, the biometric rows do not yet.
    repo = HomeFake(ring_last=TODAY - timedelta(days=1), detail_last=TODAY)
    body = _get(monkeypatch, repo, "/api/today/sleep")
    assert not body["contributors"]["scored"]
    assert body["contributors"]["unscored_reason"] == dash.sleep_unscored_reason(False, True)


def test_naps_carry_the_day_total(monkeypatch):
    nap = {"type": "sleep", "total_seconds": 1800.0, "efficiency": 90.0,
           "bedtime_start": f"{TODAY.isoformat()}T14:00:00+02:00"}
    naps = _get(monkeypatch, HomeFake(naps=[nap]), "/api/today/sleep")["night"]["naps"]
    assert naps["count"] == 1 and naps["rows"][0]["label"].startswith("Nap")
    assert naps["day_total"] != naps["night_total"]


def test_a_rest_day_offers_the_week_and_shows_it_when_asked(monkeypatch):
    # H50, H51: no session on the day; the 7 days before it carry load.
    repo = HomeFake(session_days=range(1, 31, 2))
    day = _get(monkeypatch, repo, "/api/today/strain")
    assert day["is_rolling"] and day["title"] == strain_screen.strain_labels(True, "TODAY")[1]
    assert day["region"]["state"] == "empty" and day["region"]["reason"] == "rolling"
    assert day["region"]["can_show_window"] and not day["region"]["showing_week"]
    week = _get(monkeypatch, repo, "/api/today/strain?week=true")["region"]
    assert week["state"] == "split" and week["week"] and week["showing_week"]


def test_a_chart_with_fewer_than_two_readings_is_empty(monkeypatch):
    # H56: the phone shows its empty message, never a flat line.
    trend = _get(monkeypatch, HomeFake(history=False), "/api/today/readiness")["trend"]
    assert trend["empty"] and trend["headline"] == "—" and trend["axis"] is None
