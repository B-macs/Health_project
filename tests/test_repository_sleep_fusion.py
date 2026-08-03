"""
Tests for services/repository.py's Garmin sleep-stage capture and Sleep
Fusion persistence.

Two properties matter most here and neither is visible in
services/sleep_fusion.py's own tests:

  1. Capturing sleep stages must cost ZERO extra Garmin API calls — the
     payload was already being fetched and discarded. The fake client counts
     calls so a regression that re-fetches shows up as a failing number, not
     as a slow sync nobody notices until the next 429.
  2. Fusion must never call a device API at all, so it stays runnable while
     Garmin is rate-limited and re-runnable after a RULES_VERSION bump.

Garmin/Sheets clients are faked directly, mirroring tests/
test_repository_garmin.py's _FakeGarminClient idiom.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from services import repository as repo_mod
from services import sleep_fusion as sf
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
        garmin_email="a@b.com",
        garmin_password="secret",
    )
    base.update(overrides)
    return Config(**base)


_SEGMENTS = [
    {"startGMT": "2026-07-27T19:38:00.0", "endGMT": "2026-07-27T20:08:00.0", "activityLevel": 1.0},
    {"startGMT": "2026-07-27T20:08:00.0", "endGMT": "2026-07-27T20:38:00.0", "activityLevel": 0.0},
    {"startGMT": "2026-07-27T20:38:00.0", "endGMT": "2026-07-27T20:48:00.0", "activityLevel": 2.0},
    {"startGMT": "2026-07-27T20:48:00.0", "endGMT": "2026-07-27T20:58:00.0", "activityLevel": 3.0},
]
_DTO = {
    "sleepTimeSeconds": 4200,
    "deepSleepSeconds": 1800, "lightSleepSeconds": 1800,
    "remSleepSeconds": 600, "awakeSleepSeconds": 600,
    "sleepStartTimestampGMT": 1785181140000,
    "sleepStartTimestampLocal": 1785188340000,
    "sleepEndTimestampGMT": 1785185340000,
}


class _CountingGarminClient:
    """Counts every endpoint call, so "no additional API calls" is asserted
    rather than assumed."""

    def __init__(self, sleep=None):
        self._sleep = sleep if sleep is not None else {"dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS}
        self.calls: dict[str, int] = {}

    def _bump(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1

    def get_stats(self, cdate):
        self._bump("stats")
        return {"totalSteps": 9000, "restingHeartRate": 52}

    def get_sleep_data(self, cdate):
        self._bump("sleep")
        return self._sleep

    def get_stress_data(self, cdate):
        self._bump("stress")
        return {"avgStressLevel": 30}

    def get_hrv_data(self, cdate):
        self._bump("hrv")
        return {"hrvSummary": {"lastNightAvg": 41}}


class _FakeTab:
    def __init__(self, records=None):
        self.records = records or []
        self.upserts: list[list] = []
        self.numericise_ignore = None


def _patch_sheets(monkeypatch, tabs: dict[str, _FakeTab]):
    monkeypatch.setattr(
        repo_mod.sheets, "get_or_create_worksheet",
        lambda client, sheet_id, title, header: tabs.setdefault(title, _FakeTab()),
    )

    def get_records(ws, numericise_ignore=None):
        ws.numericise_ignore = numericise_ignore
        return ws.records

    def upsert(ws, key_col, key_value, row_values):
        ws.upserts.append(row_values)

    def rewrite(ws, header, rows, chunk_size=500):
        ws.rewritten = (header, rows)
        return len(rows)

    monkeypatch.setattr(repo_mod.sheets, "get_worksheet_records", get_records)
    monkeypatch.setattr(repo_mod.sheets, "upsert_row_by_key", upsert)
    monkeypatch.setattr(repo_mod.sheets, "rewrite_worksheet", rewrite)
    monkeypatch.setattr(Repository, "_sc", property(lambda self: object()))


def _repo(client=None) -> Repository:
    repo = Repository(_config())
    repo._garmin_client_obj = client
    repo._garmin_login_attempted = True
    return repo


# ─── the refactor must not change existing behaviour ────────────────────────

def test_garmin_daily_row_returns_the_same_dict_after_the_raw_day_split():
    """_garmin_daily_row was split into a fetch (_garmin_raw_day) and an
    extraction (_garmin_daily_row_from_raw). Its own output must be
    unchanged — tests/test_repository_garmin.py depends on it."""
    client = _CountingGarminClient()
    repo = _repo(client)
    d = date(2026, 7, 28)
    direct = repo._garmin_daily_row(client, d)
    from_raw = repo._garmin_daily_row_from_raw(repo._garmin_raw_day(client, d), d)
    assert direct == from_raw
    assert direct["sleep_hours"] == 1.17
    assert direct["hrv_ms"] == 41
    assert direct["steps"] == 9000


def test_one_raw_day_costs_exactly_four_calls():
    client = _CountingGarminClient()
    _repo(client)._garmin_raw_day(client, date(2026, 7, 28))
    assert client.calls == {"stats": 1, "sleep": 1, "stress": 1, "hrv": 1}


def test_capturing_sleep_stages_makes_no_additional_api_calls():
    """The whole reason this was cheap to build: _garmin_daily_row already
    fetched the payload holding sleepLevels and threw it away."""
    client = _CountingGarminClient()
    repo = _repo(client)
    raw = repo._garmin_raw_day(client, date(2026, 7, 28))
    before = dict(client.calls)
    repo._garmin_daily_row_from_raw(raw, date(2026, 7, 28))
    repo._garmin_sleep_stages_row(raw, date(2026, 7, 28))
    assert client.calls == before


# ─── _garmin_sleep_stages_row ───────────────────────────────────────────────

def test_sleep_stages_row_derives_per_stage_seconds_from_the_segments():
    repo = _repo()
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS}},
                                        date(2026, 7, 28))
    assert row["segment_count"] == 4
    assert row["deep_seconds"] == 1800
    assert row["light_seconds"] == 1800
    assert row["rem_seconds"] == 600
    assert row["awake_seconds"] == 600


def test_totals_match_is_true_when_the_mapping_reproduces_garmins_own_totals():
    repo = _repo()
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS}},
                                        date(2026, 7, 28))
    assert row["totals_match"] is True


def test_totals_match_goes_false_when_garmins_own_totals_disagree():
    """The runtime guard on the activityLevel->stage mapping. It was verified
    on one night; this is what catches a future Garmin schema drift instead
    of silently producing a wrong hypnogram."""
    repo = _repo()
    bad_dto = {**_DTO, "deepSleepSeconds": 60}
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": bad_dto, "sleepLevels": _SEGMENTS}},
                                        date(2026, 7, 28))
    assert row["totals_match"] is False


def test_totals_match_tolerates_a_minute_of_rounding():
    """Segment bounds are minute-rounded; the real 2026-07-28 payload is 60s
    out on light sleep alone."""
    repo = _repo()
    dto = {**_DTO, "lightSleepSeconds": 1740}
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": dto, "sleepLevels": _SEGMENTS}},
                                        date(2026, 7, 28))
    assert row["totals_match"] is True


def test_a_night_with_no_segments_is_not_marked_as_matching():
    repo = _repo()
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": _DTO, "sleepLevels": []}},
                                        date(2026, 7, 28))
    assert row["totals_match"] is False
    assert row["segment_count"] == 0


def test_segments_are_stored_losslessly_as_json():
    """Not as a derived minute-string: baking the resampling choice into
    storage would mean a RULES_VERSION bump could never be recomputed without
    re-calling Garmin."""
    repo = _repo()
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS}},
                                        date(2026, 7, 28))
    assert json.loads(row["sleep_levels_json"]) == _SEGMENTS


def test_sleep_stages_row_records_the_nights_utc_offset():
    repo = _repo()
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS}},
                                        date(2026, 7, 28))
    assert row["utc_offset_minutes"] == 120


def test_an_empty_sleep_payload_yields_a_blank_row_rather_than_raising():
    repo = _repo()
    row = repo._garmin_sleep_stages_row({}, date(2026, 7, 28))
    assert row["date"] == "2026-07-28"
    assert row["segment_count"] == 0
    assert row["totals_match"] is False


def test_sleep_stages_row_keys_match_the_sheet_header():
    repo = _repo()
    row = repo._garmin_sleep_stages_row({"sleep": {"dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS}},
                                        date(2026, 7, 28))
    assert set(row) == set(repo_mod._GARMIN_SLEEP_STAGES_HEADER)


# ─── sync_garmin_daily — the 429 mitigation ─────────────────────────────────

def test_sync_skips_past_days_already_complete_in_both_tabs(monkeypatch):
    """A days=7 sync used to spend 28 API calls every 2 hours, almost all of
    it re-fetching immutable history — the likeliest cause of the 429s."""
    tabs = {
        repo_mod.sheets.GARMIN_DAILY_WORKSHEET: _FakeTab(records=[
            {"date": "2026-07-25", "sleep_hours": 7.5},
            {"date": "2026-07-24", "sleep_hours": 8.0},
        ]),
        repo_mod.sheets.GARMIN_SLEEP_STAGES_WORKSHEET: _FakeTab(records=[
            {"date": "2026-07-25"}, {"date": "2026-07-24"},
        ]),
    }
    _patch_sheets(monkeypatch, tabs)
    client = _CountingGarminClient()
    repo = _repo(client)

    fetched = repo.sync_garmin_daily(days=5, today=date(2026, 7, 28))

    # 07-28, 07-27, 07-26 fetched; 07-25 and 07-24 skipped.
    assert fetched == 3
    assert client.calls["sleep"] == 3


def test_today_and_yesterday_always_resync_because_garmin_backfills_them(monkeypatch):
    """Garmin fills in sleep and stress well after midnight, so a "complete"
    row for today is not actually final."""
    tabs = {
        repo_mod.sheets.GARMIN_DAILY_WORKSHEET: _FakeTab(records=[
            {"date": "2026-07-28", "sleep_hours": 7.5},
            {"date": "2026-07-27", "sleep_hours": 7.5},
        ]),
        repo_mod.sheets.GARMIN_SLEEP_STAGES_WORKSHEET: _FakeTab(records=[
            {"date": "2026-07-28"}, {"date": "2026-07-27"},
        ]),
    }
    _patch_sheets(monkeypatch, tabs)
    client = _CountingGarminClient()

    fetched = _repo(client).sync_garmin_daily(days=2, today=date(2026, 7, 28))
    assert fetched == 2


def test_force_refetches_everything(monkeypatch):
    tabs = {
        repo_mod.sheets.GARMIN_DAILY_WORKSHEET: _FakeTab(records=[
            {"date": f"2026-07-2{i}", "sleep_hours": 7.5} for i in range(4, 9)
        ]),
        repo_mod.sheets.GARMIN_SLEEP_STAGES_WORKSHEET: _FakeTab(records=[
            {"date": f"2026-07-2{i}"} for i in range(4, 9)
        ]),
    }
    _patch_sheets(monkeypatch, tabs)
    client = _CountingGarminClient()
    assert _repo(client).sync_garmin_daily(days=5, today=date(2026, 7, 28), force=True) == 5


def test_sync_writes_both_the_daily_row_and_the_sleep_stages_row(monkeypatch):
    tabs: dict[str, _FakeTab] = {}
    _patch_sheets(monkeypatch, tabs)
    _repo(_CountingGarminClient()).sync_garmin_daily(days=1, today=date(2026, 7, 28))
    assert len(tabs[repo_mod.sheets.GARMIN_DAILY_WORKSHEET].upserts) == 1
    assert len(tabs[repo_mod.sheets.GARMIN_SLEEP_STAGES_WORKSHEET].upserts) == 1


# ─── the 429 circuit breaker ────────────────────────────────────────────────

def test_the_breaker_reports_rate_limited_until_the_backoff_expires(monkeypatch):
    repo = _repo()
    stored: dict[str, str] = {}
    monkeypatch.setattr(Repository, "set_config",
                        lambda self, k, v, today=None: stored.__setitem__(k, v))
    monkeypatch.setattr(Repository, "get_config_value", lambda self, k: stored.get(k))

    now = datetime(2026, 7, 31, 9, 0, 0)
    repo.open_garmin_rate_limit_breaker(now=now)
    assert repo.garmin_rate_limited(now=now + timedelta(hours=1)) is True
    assert repo.garmin_rate_limited(now=now + timedelta(hours=7)) is False


def test_an_open_breaker_short_circuits_the_sync_without_calling_garmin(monkeypatch):
    """Retrying a throttled endpoint on every page load is how a transient
    429 becomes a persistent one."""
    client = _CountingGarminClient()
    repo = _repo(client)
    now = datetime(2026, 7, 31, 9, 0, 0)
    stored = {"garmin_rate_limited_until": (now + timedelta(hours=3)).isoformat()}
    monkeypatch.setattr(Repository, "get_config_value", lambda self, k: stored.get(k))
    monkeypatch.setattr(Repository, "has_checked_in", lambda self, d: False)

    ok, err = repo.sync_garmin_daily_if_due(today=date(2026, 7, 31), now=now)
    assert ok is True and err is None
    assert client.calls == {}


def test_a_rate_limited_sync_opens_the_breaker_and_is_not_reported_as_failure(monkeypatch):
    """(True, msg): "backing off", not "broken". A caller that treats it as an
    error would surface a scary banner for a self-healing condition."""
    repo = _repo(_CountingGarminClient())
    stored: dict[str, str] = {}
    monkeypatch.setattr(Repository, "set_config",
                        lambda self, k, v, today=None: stored.__setitem__(k, v))
    monkeypatch.setattr(Repository, "get_config_value", lambda self, k: stored.get(k))
    monkeypatch.setattr(Repository, "has_checked_in", lambda self, d: False)
    monkeypatch.setattr(Repository, "sync_garmin_daily",
                        lambda self, **kw: (_ for _ in ()).throw(repo_mod.garmin.RateLimited("429")))

    ok, msg = repo.sync_garmin_daily_if_due(today=date(2026, 7, 31),
                                            now=datetime(2026, 7, 31, 9, 0, 0))
    assert ok is True
    assert "rate-limited" in msg
    assert "garmin_rate_limited_until" in stored


# ─── fusion — reads Sheets only ─────────────────────────────────────────────

def _fusion_repo(monkeypatch, oura_rows, garmin_rows):
    tabs = {
        repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET: _FakeTab(records=oura_rows),
        repo_mod.sheets.GARMIN_SLEEP_STAGES_WORKSHEET: _FakeTab(records=garmin_rows),
    }
    _patch_sheets(monkeypatch, tabs)
    return _repo(), tabs


_OURA_ROW = {
    "sleep_id": "ac08e613", "day": "2026-07-28", "type": "long_sleep",
    "bedtime_start": "2026-07-27T21:38:00.000+02:00",
    "sleep_phase_30_sec": "22" * 30 + "44" * 5 + "22" * 25,   # 60 minutes
}
_GARMIN_ROW = {
    "date": "2026-07-28", "totals_match": True, "utc_offset_minutes": 120,
    "sleep_levels_json": json.dumps([
        {"startGMT": "2026-07-27T19:38:00.0", "endGMT": "2026-07-27T20:38:00.0",
         "activityLevel": 1.0},
    ]),
}


def test_fusion_makes_no_device_api_calls_at_all(monkeypatch):
    """So it stays runnable while Garmin is rate-limited, and re-runnable
    after a RULES_VERSION bump."""
    repo, _ = _fusion_repo(monkeypatch, [_OURA_ROW], [_GARMIN_ROW])

    def explode(*a, **k):
        raise AssertionError("fusion must not call a device API")

    for name in ("get_sleep_data", "get_daily_summary", "get_stress_data", "get_hrv_data"):
        monkeypatch.setattr(repo_mod.garmin, name, explode)
    monkeypatch.setattr(repo_mod.oura, "get_collection", explode)

    counts = repo.sync_sleep_fusion(days=3, today=date(2026, 7, 28))
    assert counts == {sf.SOURCE_FUSED: 1}


def test_a_fused_night_removes_ouras_phantom_wake(monkeypatch):
    repo, tabs = _fusion_repo(monkeypatch, [_OURA_ROW], [_GARMIN_ROW])
    summary = repo.compute_sleep_fusion_for_date(
        "2026-07-28", repo._oura_hypnograms_by_date("2026-07-01", "2026-07-31"),
        repo.get_garmin_sleep_stages())
    assert summary["source"] == sf.SOURCE_FUSED
    assert summary["phantom_wake_minutes"] == 5
    assert summary["master_sleep_hours"] >= summary["oura_sleep_hours"]


def test_a_night_with_no_garmin_row_is_written_as_oura_only(monkeypatch):
    repo, _ = _fusion_repo(monkeypatch, [_OURA_ROW], [])
    summary = repo.compute_sleep_fusion_for_date(
        "2026-07-28", repo._oura_hypnograms_by_date("2026-07-01", "2026-07-31"), {})
    assert summary["source"] == sf.SOURCE_OURA_ONLY
    assert summary["master_hypnogram"] == summary["oura_hypnogram"]
    assert summary["phantom_wake_minutes"] == 0


def test_a_night_whose_garmin_totals_did_not_match_is_refused(monkeypatch):
    """totals_match False means our activityLevel->stage mapping could not be
    verified for that night — fusing anyway would trust an unverified mapping."""
    repo, _ = _fusion_repo(monkeypatch, [_OURA_ROW], [{**_GARMIN_ROW, "totals_match": False}])
    summary = repo.compute_sleep_fusion_for_date(
        "2026-07-28", repo._oura_hypnograms_by_date("2026-07-01", "2026-07-31"),
        repo.get_garmin_sleep_stages())
    assert summary["source"] == sf.SOURCE_OURA_ONLY


def test_a_garmin_night_a_whole_day_out_is_refused_rather_than_fused(monkeypatch):
    """A silent one-day misalignment produces a plausible but completely wrong
    hypnogram and breaks nothing visibly — the worst failure mode here."""
    stale = {**_GARMIN_ROW, "date": "2026-07-27", "sleep_levels_json": json.dumps([
        {"startGMT": "2026-07-25T19:38:00.0", "endGMT": "2026-07-25T20:38:00.0",
         "activityLevel": 1.0},
    ])}
    repo, _ = _fusion_repo(monkeypatch, [_OURA_ROW], [stale])
    summary = repo.compute_sleep_fusion_for_date(
        "2026-07-28", repo._oura_hypnograms_by_date("2026-07-01", "2026-07-31"),
        repo.get_garmin_sleep_stages())
    assert summary["source"] == sf.SOURCE_OURA_ONLY
    assert summary["window_overlap_pct"] == 0.0


def test_a_night_without_a_hypnogram_is_skipped_entirely(monkeypatch):
    repo, _ = _fusion_repo(monkeypatch, [{**_OURA_ROW, "sleep_phase_30_sec": ""}], [])
    assert repo._oura_hypnograms_by_date("2026-07-01", "2026-07-31") == {}


def test_naps_do_not_displace_the_main_sleep_period(monkeypatch):
    """Uses the same biometrics.pick_main_sleep_period gate the engine already
    applies, so fusion describes the same night everything else does."""
    nap = {"sleep_id": "nap", "day": "2026-07-28", "type": "late_nap",
           "bedtime_start": "2026-07-28T14:00:00.000+02:00",
           "sleep_phase_30_sec": "22" * 10, "total_sleep_duration": 600}
    main = {**_OURA_ROW, "total_sleep_duration": 27300}
    repo, _ = _fusion_repo(monkeypatch, [nap, main], [])
    picked = repo._oura_hypnograms_by_date("2026-07-01", "2026-07-31")["2026-07-28"]
    assert picked["sleep_id"] == "ac08e613"
    assert picked["periods_on_day"] == 2


# ─── persistence — the digit-string hazard ──────────────────────────────────

def test_the_fusion_tab_exempts_its_hypnogram_columns_from_numericising(monkeypatch):
    """Same hazard as the Oura tab: gspread would read a 450-digit hypnogram
    back as an int and write it out as an unrepresentable JSON number."""
    repo, tabs = _fusion_repo(monkeypatch, [], [])
    tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET] = _FakeTab(records=[])
    repo.get_sleep_fusion_history()
    assert (tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET].numericise_ignore
            == repo_mod._SLEEP_FUSION_NUMERICISE_IGNORE)


def test_the_numericise_exemption_covers_exactly_the_digit_string_columns():
    header = repo_mod._SLEEP_FUSION_HEADER
    exempt = [header[i - 1] for i in repo_mod._SLEEP_FUSION_NUMERICISE_IGNORE]
    assert exempt == [
        "master_hypnogram", "oura_hypnogram", "garmin_hypnogram", "reason_codes",
        # The movement series are digit strings on the same terms as the
        # hypnograms; movement_cutpoints is comma-joined floats, where a
        # single value would read as a float and a full triple as text.
        "master_movement", "oura_movement", "garmin_movement", "movement_cutpoints",
    ]


def test_saving_a_night_writes_every_header_column_in_order(monkeypatch):
    repo, tabs = _fusion_repo(monkeypatch, [], [])
    tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET] = _FakeTab()
    summary = sf.night_summary("2026-07-28", None, [sf.LIGHT] * 5, None)
    repo.save_sleep_fusion(summary)
    written = tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET].upserts[0]
    assert len(written) == len(repo_mod._SLEEP_FUSION_HEADER)
    assert written[repo_mod._SLEEP_FUSION_HEADER.index("master_hypnogram")] == "22222"
    assert written[repo_mod._SLEEP_FUSION_HEADER.index("computed_at")] != ""


# ─── the wake-correction handoff ────────────────────────────────────────────

def test_a_full_rebuild_writes_one_batch_rather_than_a_call_per_night(monkeypatch):
    """~400 nights x 2 API calls per upsert would blow through Sheets'
    60-writes-per-minute quota, which is what makes a RULES_VERSION bump
    re-derivable in practice rather than only in principle."""
    repo, tabs = _fusion_repo(monkeypatch, [_OURA_ROW], [_GARMIN_ROW])
    tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET] = _FakeTab(records=[])
    repo.sync_sleep_fusion(days=1000, today=date(2026, 7, 28))
    ws = tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET]
    assert ws.upserts == []
    assert len(ws.rewritten[1]) == 1


def test_a_rebuild_keeps_nights_outside_the_window(monkeypatch):
    """The output is always a superset of what was stored."""
    repo, tabs = _fusion_repo(monkeypatch, [_OURA_ROW], [_GARMIN_ROW])
    tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET] = _FakeTab(records=[
        {"date": "2020-01-01", "source": sf.SOURCE_OURA_ONLY},
    ])
    repo.sync_sleep_fusion(days=3, today=date(2026, 7, 28))
    written = {r[0] for r in tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET].rewritten[1]}
    assert {"2020-01-01", "2026-07-28"} <= written


def test_only_genuinely_fused_nights_contribute_a_wake_correction(monkeypatch):
    """An oura_only night has nothing to say about phantom wake and must not
    override a manual correction the user entered."""
    repo, tabs = _fusion_repo(monkeypatch, [], [])
    tabs[repo_mod.sheets.SLEEP_FUSION_WORKSHEET] = _FakeTab(records=[
        {"date": "2026-07-28", "source": sf.SOURCE_FUSED, "phantom_wake_minutes": 88},
        {"date": "2026-07-27", "source": sf.SOURCE_OURA_ONLY, "phantom_wake_minutes": 0},
    ])
    assert repo.get_fused_wake_adjustments() == {"2026-07-28": 88.0}


# ─── get_sleep_night_details / get_oura_daily_sleep_context (2026-07-31) ────
#  Display-only reads for the Home page Sleep drill-down. Kept out of
#  BiometricRecord on purpose — see the method docstring.

_DETAIL_ROW = {
    "sleep_id": "ac08e613", "day": "2026-07-28", "type": "long_sleep", "period": 0,
    "bedtime_start": "2026-07-27T22:42:00.000+02:00",
    "bedtime_end": "2026-07-28T06:44:00.000+02:00",
    "total_sleep_duration": 21540, "time_in_bed": 28980, "awake_time": 7440,
    "deep_sleep_duration": 2940, "light_sleep_duration": 13620,
    "rem_sleep_duration": 5040, "efficiency": 74, "latency": 720,
    "average_heart_rate": 63.0, "lowest_heart_rate": 60.0, "average_hrv": 18,
    "average_breath": 14.2, "restless_periods": 18,
    "readiness_score": 71, "readiness_temperature_deviation": -0.07,
    "sleep_phase_30_sec": "2211",
}


def test_night_details_map_every_field_the_drilldown_shows(monkeypatch):
    """No Oura column name should ever reach app.py — the repository is the
    only place they live."""
    tabs = {repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET: _FakeTab(records=[_DETAIL_ROW])}
    _patch_sheets(monkeypatch, tabs)
    d = _repo().get_sleep_night_details("2026-07-01", "2026-07-31")["2026-07-28"]
    assert d["total_seconds"] == 21540
    assert d["time_in_bed_seconds"] == 28980
    assert d["light_seconds"] == 13620
    assert d["average_breath"] == 14.2
    assert d["lowest_heart_rate"] == 60.0
    assert d["temperature_deviation"] == -0.07
    assert d["bedtime_end"] == "2026-07-28T06:44:00.000+02:00"
    assert d["hypnogram_30sec"] == "2211"


def test_night_details_read_the_hypnogram_as_text_not_a_number(monkeypatch):
    """gspread would numericise a 1,800-digit hypnogram into an int that
    cannot survive a write-back — the same hazard the Oura tab already
    guards."""
    tabs = {repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET: _FakeTab(records=[_DETAIL_ROW])}
    _patch_sheets(monkeypatch, tabs)
    _repo().get_sleep_night_details("2026-07-01", "2026-07-31")
    assert (tabs[repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET].numericise_ignore
            == repo_mod._OURA_NUMERICISE_IGNORE["sleep_periods"])


def test_night_details_describe_the_main_period_not_a_nap(monkeypatch):
    """Same pick_main_sleep_period gate the engine uses, so the drill-down
    always explains the same night the score was computed from.

    The nap carries its own afternoon window rather than inheriting the
    night's: two periods sharing one set of timestamps are a re-analysis of
    the same sleep, not two sleeps, and biometrics.dedupe_sleep_periods
    would rightly collapse them (see tests/test_sleep_naps.py)."""
    nap = {**_DETAIL_ROW, "sleep_id": "nap", "type": "late_nap",
           "bedtime_start": "2026-07-27T16:10:00.000+02:00",
           "bedtime_end": "2026-07-27T16:40:00.000+02:00",
           "total_sleep_duration": 900, "average_breath": 99.0}
    tabs = {repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET: _FakeTab(records=[nap, _DETAIL_ROW])}
    _patch_sheets(monkeypatch, tabs)
    d = _repo().get_sleep_night_details("2026-07-01", "2026-07-31")["2026-07-28"]
    assert d["average_breath"] == 14.2
    assert d["periods_on_day"] == 2


def test_night_details_scope_to_the_requested_window(monkeypatch):
    tabs = {repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET: _FakeTab(
        records=[_DETAIL_ROW, {**_DETAIL_ROW, "day": "2025-01-01"}])}
    _patch_sheets(monkeypatch, tabs)
    out = _repo().get_sleep_night_details("2026-07-01", "2026-07-31")
    assert set(out) == {"2026-07-28"}


def test_a_blank_reading_becomes_none_rather_than_zero(monkeypatch):
    """Zero is a real value for several of these; blank means no reading."""
    tabs = {repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET: _FakeTab(
        records=[{**_DETAIL_ROW, "average_breath": "", "average_hrv": ""}])}
    _patch_sheets(monkeypatch, tabs)
    d = _repo().get_sleep_night_details("2026-07-01", "2026-07-31")["2026-07-28"]
    assert d["average_breath"] is None
    assert d["average_hrv"] is None


def test_daily_sleep_context_surfaces_the_breathing_columns_the_engine_ignores(monkeypatch):
    tabs = {repo_mod.sheets.OURA_DAILY_WORKSHEET: _FakeTab(records=[{
        "date": "2026-07-28", "spo2_average": 98.0,
        "spo2_breathing_disturbance_index": 2, "sleep_time_optimal_bedtime": "22:30",
    }])}
    _patch_sheets(monkeypatch, tabs)
    c = _repo().get_oura_daily_sleep_context("2026-07-01", "2026-07-31")["2026-07-28"]
    assert c["spo2_average"] == 98.0
    assert c["breathing_disturbance_index"] == 2


# ─── Worksheet read cache (2026-07-31) ──────────────────────────────────────
#  One Sleep drill-down render was opening Oura Daily 3x, Sleep Periods 2x and
#  Sleep Fusion 2x — 10 tab reads where 6 would do. Correctness rests on the
#  write-generation key, so these two properties are the whole contract.

class _CountingTab(_FakeTab):
    def __init__(self, records=None):
        super().__init__(records)
        self.title = "Counting Tab"
        self.reads = 0


def _patch_counting(monkeypatch, tab):
    def get_records(ws, numericise_ignore=None):
        ws.reads += 1
        return ws.records
    monkeypatch.setattr(repo_mod.sheets, "get_worksheet_records", get_records)
    monkeypatch.setattr(Repository, "_sc", property(lambda self: object()))


def test_the_same_tab_read_twice_in_one_render_hits_the_api_once():
    """The whole point: three independent code paths can each ask for Oura
    Daily without three round trips."""
    tab = _CountingTab(records=[{"date": "2026-07-28"}])
    repo = _repo()
    import pytest as _pytest
    mp = _pytest.MonkeyPatch()
    try:
        _patch_counting(mp, tab)
        repo._read_records(tab)
        repo._read_records(tab)
        repo._read_records(tab)
        assert tab.reads == 1
    finally:
        mp.undo()


def test_a_write_anywhere_invalidates_the_cached_read():
    """Keyed on sheets.write_generation(), so a sync that writes a tab can
    never be followed by a read that serves the pre-write rows — and no call
    site has to remember to invalidate."""
    tab = _CountingTab(records=[{"date": "2026-07-28"}])
    repo = _repo()
    import pytest as _pytest
    mp = _pytest.MonkeyPatch()
    try:
        _patch_counting(mp, tab)
        repo._read_records(tab)
        repo_mod.sheets._bump_write_generation()
        repo._read_records(tab)
        assert tab.reads == 2
    finally:
        mp.undo()


def test_the_cache_expires_so_an_external_write_cannot_go_unseen_forever():
    """write_generation only knows about writes from THIS process. The TTL
    bounds staleness from another device writing the sheet."""
    tab = _CountingTab(records=[{"date": "2026-07-28"}])
    repo = _repo()
    import pytest as _pytest
    mp = _pytest.MonkeyPatch()
    try:
        _patch_counting(mp, tab)
        repo._read_records(tab)
        # Capture the REAL clock before patching — a lambda that calls the
        # patched name recurses into itself.
        real_monotonic = repo_mod.time.monotonic
        mp.setattr(repo_mod.time, "monotonic",
                   lambda: real_monotonic() + Repository._READ_CACHE_TTL_SECONDS + 1)
        repo._read_records(tab)
        assert tab.reads == 2
    finally:
        mp.undo()


def test_different_numericise_settings_are_cached_separately():
    """A hypnogram-exempt read and a plain read of the same tab return
    genuinely different values; sharing one cache entry would hand one
    caller the other's coercion."""
    tab = _CountingTab(records=[{"date": "2026-07-28"}])
    repo = _repo()
    import pytest as _pytest
    mp = _pytest.MonkeyPatch()
    try:
        _patch_counting(mp, tab)
        repo._read_records(tab)
        repo._read_records(tab, numericise_ignore=[27, 28])
        assert tab.reads == 2
    finally:
        mp.undo()


# ─── Garmin movement capture (sleepMovement) ────────────────────────────────
#  Shapes and figures below come from the real archived payloads in
#  Input_files/garmin_export/ (53 nights, verified 2026-07-31).

_MOVEMENT = [
    {"startGMT": "2026-07-27T19:38:00.0", "endGMT": "2026-07-27T19:39:00.0",
     "activityLevel": 5.67199759213915},
    {"startGMT": "2026-07-27T19:39:00.0", "endGMT": "2026-07-27T19:40:00.0",
     "activityLevel": 0.4171},
    {"startGMT": "2026-07-27T19:40:00.0", "endGMT": "2026-07-27T19:41:00.0",
     "activityLevel": 1.132},
]


def _stages_row(monkeypatch, sleep_payload):
    _patch_sheets(monkeypatch, {})
    repo = Repository(_config())
    return repo._garmin_sleep_stages_row({"sleep": sleep_payload}, date(2026, 7, 28))


def test_garmin_row_captures_movement_from_the_same_payload_as_stages(monkeypatch):
    """sleepMovement rides in the payload _garmin_sleep_stages_row already
    consumes, so movement capture must cost zero additional API calls."""
    row = _stages_row(monkeypatch, {
        "dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS, "sleepMovement": _MOVEMENT})
    assert row["movement_slot_count"] == 3
    assert row["movement_levels"] == "5.67,0.42,1.13"
    assert row["movement_contiguous"] is True
    assert row["movement_gap_slots"] == 0


def test_garmin_row_gap_fills_movement_so_later_values_keep_their_position(monkeypatch):
    """The real 2026-05-27 failure: a 4-minute hole in sleepMovement. Packing
    the survivors end-to-end would shift the rest of the night."""
    gapped = [_MOVEMENT[0], {
        "startGMT": "2026-07-27T19:42:00.0", "endGMT": "2026-07-27T19:43:00.0",
        "activityLevel": 9.0}]
    row = _stages_row(monkeypatch, {
        "dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS, "sleepMovement": gapped})
    # 19:38 then 19:42 — three uncovered minutes between them, so the second
    # value must land at index 4, not index 1.
    assert row["movement_levels"] == "5.67,,,,9.00"
    assert row["movement_contiguous"] is False
    assert row["movement_gap_slots"] == 3


def test_garmin_row_blanks_movement_when_the_payload_has_none(monkeypatch):
    """Nights before the watch reported movement must not fail the row."""
    row = _stages_row(monkeypatch, {"dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS})
    assert row["movement_levels"] == ""
    assert row["movement_slot_count"] == 0
    assert row["movement_start_gmt"] == ""


def test_garmin_row_stores_overnight_hr_and_stress_as_json(monkeypatch):
    row = _stages_row(monkeypatch, {
        "dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS,
        "sleepHeartRate": [{"value": 61, "startGMT": 1785181080000}],
        "sleepStress": [{"value": 21, "startGMT": 1785180960000}]})
    assert json.loads(row["sleep_hr_json"]) == [{"value": 61, "startGMT": 1785181080000}]
    assert json.loads(row["sleep_stress_json"]) == [{"value": 21, "startGMT": 1785180960000}]


def test_garmin_row_never_writes_a_cell_over_the_sheets_limit(monkeypatch):
    """Raw sleepMovement is ~84k chars a night against a 50,000-char cell
    limit — the whole reason it is stored reduced rather than losslessly."""
    long_night = [
        {"startGMT": f"2026-07-27T{18 + i // 60:02d}:{i % 60:02d}:00.0",
         "endGMT": f"2026-07-27T{18 + (i + 1) // 60:02d}:{(i + 1) % 60:02d}:00.0",
         "activityLevel": 4.123456789}
        for i in range(719)
    ]
    row = _stages_row(monkeypatch, {
        "dailySleepDTO": _DTO, "sleepLevels": _SEGMENTS, "sleepMovement": long_night})
    assert all(len(str(v)) < 50000 for v in row.values())


def test_get_garmin_sleep_stages_round_trips_movement_back_into_a_grid(monkeypatch):
    """Storage must be transparent: a caller cannot tell whether the night
    came from a live payload or from the Sheet."""
    tabs = {repo_mod.sheets.GARMIN_SLEEP_STAGES_WORKSHEET: _FakeTab(records=[{
        "date": "2026-07-28", "sleep_levels_json": "[]",
        "movement_start_gmt": "2026-07-27T19:38:00+00:00",
        "movement_interval_seconds": 60, "movement_levels": "5.67,,1.13",
        "movement_contiguous": "FALSE", "movement_gap_slots": 1,
    }])}
    _patch_sheets(monkeypatch, tabs)
    got = Repository(_config()).get_garmin_sleep_stages()["2026-07-28"]["movement"]
    assert got["levels"] == [5.67, None, 1.13]
    assert got["contiguous"] is False
    assert got["gap_slots"] == 1
    assert got["start_utc"] == datetime(2026, 7, 27, 19, 38, tzinfo=timezone.utc)


def test_get_garmin_sleep_stages_survives_a_row_with_no_movement(monkeypatch):
    """Every night captured before this schema change has these cells blank."""
    tabs = {repo_mod.sheets.GARMIN_SLEEP_STAGES_WORKSHEET: _FakeTab(records=[
        {"date": "2026-05-01", "sleep_levels_json": "[]"}])}
    _patch_sheets(monkeypatch, tabs)
    got = Repository(_config()).get_garmin_sleep_stages()["2026-05-01"]["movement"]
    assert got["levels"] == []
    assert got["start_utc"] is None


# ─── Tab re-heading (the silent column-drop bug) ────────────────────────────

def test_rebuild_tab_rewrites_the_header_so_a_new_column_becomes_readable(monkeypatch):
    """The bug this exists for: get_or_create_worksheet writes the header ONLY
    on creation, and upsert_row_by_key never touches row 1. Adding a column to
    a _HEADER constant therefore writes values into an unheadered column that
    gspread's get_all_records silently drops.

    Real instance: hrv_ms on the Garmin Daily tab.
    """
    tab = _FakeTab(records=[{"date": "2026-07-01", "steps": 9000}])
    _patch_sheets(monkeypatch, {})
    repo = Repository(_config())

    written = {}
    monkeypatch.setattr(
        repo_mod.sheets, "rewrite_worksheet",
        lambda ws, header, rows: written.update(header=header, rows=rows) or len(rows))

    repo.rebuild_tab(tab, ["date", "steps", "hrv_ms"],
                     {"2026-07-02": {"date": "2026-07-02", "steps": 100, "hrv_ms": 44}})

    assert written["header"] == ["date", "steps", "hrv_ms"]
    # The pre-existing row is carried through, blank in the new column.
    assert written["rows"][0] == ["2026-07-01", 9000, ""]
    assert written["rows"][1] == ["2026-07-02", 100, 44]


def test_rebuild_tab_never_drops_rows_outside_the_fresh_set(monkeypatch):
    """Output must always be a superset — a rewrite that lost history would be
    unrecoverable, and sync_sleep_fusion relies on this."""
    tab = _FakeTab(records=[{"date": d} for d in ("2026-06-01", "2026-06-02", "2026-06-03")])
    _patch_sheets(monkeypatch, {})
    repo = Repository(_config())
    written = {}
    monkeypatch.setattr(
        repo_mod.sheets, "rewrite_worksheet",
        lambda ws, header, rows: written.update(rows=rows) or len(rows))

    repo.rebuild_tab(tab, ["date"], {"2026-06-02": {"date": "2026-06-02"}})
    assert [r[0] for r in written["rows"]] == ["2026-06-01", "2026-06-02", "2026-06-03"]
