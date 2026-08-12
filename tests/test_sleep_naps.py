"""
Tests for nap handling — services/biometrics.py's sleep-period split, the
repository readers built on it, and the drill-down panel that explains it.

Three properties are load-bearing and each one is pinned here:

  1. DUPLICATES MUST COLLAPSE BEFORE ANYTHING IS SUMMED. Oura re-analyses a
     night by emitting a SECOND row rather than updating the first, and eight
     nights in April 2024 carry exactly that. Picking one period hid it;
     summing does not. The regression this guards is silent and enormous —
     2024-04-19 reading 14.78 h of sleep instead of 7.42 h.
  2. DURATION AND ARCHITECTURE PART COMPANY. sleep_duration_hours counts the
     naps; oura_sleep_total_seconds does not, because services/sleep_score.py
     divides REM and deep seconds by it. A change that "helpfully" unifies
     the two would silently deflate every REM/deep share on a nap day.
  3. THE NAP FLOOR IS NOT DECORATION. Over half the non-main periods in this
     athlete's history run 1-13 minutes at 2-38% efficiency. Those are the
     ring registering stillness, and they must not reach the engine.
"""

from __future__ import annotations

from services import biometrics
from services import dashboard
from services import repository as repo_mod
from services.config import Config
from services.repository import Repository


# ─── fixtures ────────────────────────────────────────────────────────────────

def _config() -> Config:
    return Config(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )


class _FakeTab:
    def __init__(self, records=None):
        self.records = records or []
        self.numericise_ignore = None


def _repo_with_periods(monkeypatch, rows) -> Repository:
    tabs = {repo_mod.sheets.OURA_SLEEP_PERIODS_WORKSHEET: _FakeTab(records=rows)}
    monkeypatch.setattr(
        repo_mod.sheets, "get_or_create_worksheet",
        lambda client, sheet_id, title, header: tabs.setdefault(title, _FakeTab()),
    )

    def get_records(ws, numericise_ignore=None):
        ws.numericise_ignore = numericise_ignore
        return ws.records

    monkeypatch.setattr(repo_mod.sheets, "get_worksheet_records", get_records)
    monkeypatch.setattr(Repository, "_sc", property(lambda self: object()))
    return Repository(_config())


def _period(**kw) -> dict:
    base = {
        "day": "2026-07-19", "type": "long_sleep",
        "bedtime_start": "2026-07-18T23:00:00.000+02:00",
        "bedtime_end": "2026-07-19T07:00:00.000+02:00",
        "total_sleep_duration": 25200,
    }
    base.update(kw)
    return base


# ─── 1. duplicate collapse ───────────────────────────────────────────────────

def test_duplicate_periods_collapse_to_the_longest():
    """The April 2024 shape: same window, same time_in_bed, two sleep_ids,
    totals a couple of minutes apart. Both survive today's pick-one because
    only one is ever read; summing them would double the night."""
    a = _period(total_sleep_duration=26520)
    b = _period(total_sleep_duration=26700)
    unique = biometrics.dedupe_sleep_periods([a, b])
    assert len(unique) == 1
    assert unique[0]["total_sleep_duration"] == 26700


def test_a_duplicated_night_does_not_double_the_days_total():
    """The concrete 2024-04-19 regression, stated in hours."""
    a = _period(total_sleep_duration=26520)
    b = _period(total_sleep_duration=26700)
    main, naps = biometrics.split_sleep_periods([a, b])
    total_h = biometrics.day_total_sleep_seconds(main, naps) / 3600
    assert round(total_h, 2) == 7.42
    assert naps == []


def test_partially_overlapping_periods_still_collapse():
    """Oura's re-analysis can shift a boundary by a few minutes, so equality
    of timestamps is too strict a test for 'the same sleep'."""
    a = _period()
    b = _period(bedtime_start="2026-07-18T23:04:00.000+02:00",
                bedtime_end="2026-07-19T06:58:00.000+02:00",
                total_sleep_duration=25000)
    assert len(biometrics.dedupe_sleep_periods([a, b])) == 1


def test_the_same_instant_in_two_offsets_is_one_period():
    """2024-04-20 carries a period as both +01:00 and +02:00 — the same
    absolute instant written two ways. Comparing wall-clock strings would
    read them as two separate naps an hour apart."""
    a = _period(type="sleep", bedtime_start="2024-04-19T20:34:31.000+01:00",
                bedtime_end="2024-04-19T21:23:01.000+01:00",
                total_sleep_duration=690)
    b = _period(type="sleep", bedtime_start="2024-04-19T21:34:31.000+02:00",
                bedtime_end="2024-04-19T22:23:01.000+02:00",
                total_sleep_duration=600)
    assert len(biometrics.dedupe_sleep_periods([a, b])) == 1


def test_non_overlapping_periods_are_never_merged():
    night = _period()
    nap = _period(type="sleep", bedtime_start="2026-07-19T09:24:30.000+02:00",
                  bedtime_end="2026-07-19T12:30:30.000+02:00",
                  total_sleep_duration=8220)
    assert len(biometrics.dedupe_sleep_periods([night, nap])) == 2


def test_periods_without_usable_timestamps_are_kept_distinct():
    """A missing or malformed bound means the period cannot be placed on a
    timeline. Merging on a guess would delete real sleep; keeping it costs
    at most a duplicate, which the nap floor already tolerates."""
    a = _period(bedtime_end="")
    b = _period(bedtime_end="", total_sleep_duration=1)
    assert len(biometrics.dedupe_sleep_periods([a, b])) == 2


def test_dedupe_is_idempotent():
    rows = [_period(total_sleep_duration=26520), _period(total_sleep_duration=26700)]
    once = biometrics.dedupe_sleep_periods(rows)
    assert biometrics.dedupe_sleep_periods(once) == once


# ─── 2. the main/nap split ───────────────────────────────────────────────────

def test_naps_reaching_the_floor_are_counted():
    """2026-07-19, the case that motivated all of this: a 3.70 h night plus a
    137-minute morning sleep that the engine scored as 3.70 h."""
    night = _period(total_sleep_duration=13320)
    nap = _period(type="sleep", bedtime_start="2026-07-19T09:24:30.000+02:00",
                  bedtime_end="2026-07-19T12:30:30.000+02:00",
                  total_sleep_duration=8220)
    main, naps = biometrics.split_sleep_periods([night, nap])
    assert main["total_sleep_duration"] == 13320
    assert len(naps) == 1
    assert round(biometrics.day_total_sleep_seconds(main, naps) / 3600, 2) == 5.98


def test_periods_under_the_floor_are_discarded():
    """A 3-minute period at 15% efficiency is the ring noticing stillness."""
    night = _period()
    noise = _period(type="sleep", bedtime_start="2026-07-19T17:23:58.000+02:00",
                    bedtime_end="2026-07-19T17:40:29.000+02:00",
                    total_sleep_duration=180, efficiency=15)
    main, naps = biometrics.split_sleep_periods([night, noise])
    assert naps == []
    assert biometrics.day_total_sleep_seconds(main, naps) == 25200


def test_the_floor_is_inclusive_at_exactly_the_threshold():
    night = _period()
    nap = _period(type="sleep", bedtime_start="2026-07-19T14:00:00.000+02:00",
                  bedtime_end="2026-07-19T14:30:00.000+02:00",
                  total_sleep_duration=biometrics.NAP_MIN_SECONDS)
    _main, naps = biometrics.split_sleep_periods([night, nap])
    assert len(naps) == 1


def test_the_floor_is_overridable_without_touching_the_default():
    night = _period()
    nap = _period(type="sleep", bedtime_start="2026-07-19T14:00:00.000+02:00",
                  bedtime_end="2026-07-19T14:30:00.000+02:00",
                  total_sleep_duration=600)
    assert biometrics.split_sleep_periods([night, nap])[1] == []
    assert len(biometrics.split_sleep_periods([night, nap], nap_min_seconds=300)[1]) == 1


def test_a_late_nap_counts_like_any_other():
    """Oura attributes an evening nap to the FOLLOWING day, so its
    bedtime_start sits on the previous calendar date. That is Oura's own
    day-assignment and is honoured rather than re-derived."""
    night = _period()
    late = _period(type="late_nap", bedtime_start="2026-07-18T18:08:58.000+02:00",
                   bedtime_end="2026-07-18T19:15:00.000+02:00",
                   total_sleep_duration=2760)
    main, naps = biometrics.split_sleep_periods([night, late])
    assert main["type"] == "long_sleep"
    assert [n["type"] for n in naps] == ["late_nap"]


def test_a_day_with_no_long_sleep_still_reports_a_night():
    """11 days in this history have naps only — the whole night ran under 3 h
    so Oura never typed anything long_sleep. The longest period is the night;
    it must not be demoted to a nap and leave the day with no main period."""
    a = _period(type="sleep", total_sleep_duration=8520,
                bedtime_start="2023-07-16T05:40:32.000+02:00",
                bedtime_end="2023-07-16T08:55:02.000+02:00")
    b = _period(type="sleep", total_sleep_duration=1800,
                bedtime_start="2023-07-16T14:00:00.000+02:00",
                bedtime_end="2023-07-16T14:40:00.000+02:00")
    main, naps = biometrics.split_sleep_periods([a, b])
    assert main["total_sleep_duration"] == 8520
    assert len(naps) == 1


def test_a_second_long_sleep_counts_as_additional_sleep():
    """Two long_sleep periods on one day is rare but real. The shorter is
    still sleep that happened, so it is counted rather than dropped."""
    a = _period(total_sleep_duration=25200)
    b = _period(total_sleep_duration=14400,
                bedtime_start="2026-07-19T13:00:00.000+02:00",
                bedtime_end="2026-07-19T17:00:00.000+02:00")
    main, naps = biometrics.split_sleep_periods([a, b])
    assert main["total_sleep_duration"] == 25200
    assert len(naps) == 1


def test_the_main_pick_does_not_depend_on_row_order():
    rows = [
        _period(type="sleep", total_sleep_duration=3600,
                bedtime_start="2026-07-19T14:00:00.000+02:00",
                bedtime_end="2026-07-19T15:00:00.000+02:00"),
        _period(total_sleep_duration=25200),
    ]
    assert (biometrics.split_sleep_periods(rows)[0]
            == biometrics.split_sleep_periods(list(reversed(rows)))[0])


def test_naps_are_ordered_by_when_they_started():
    night = _period()
    late = _period(type="sleep", total_sleep_duration=1800,
                   bedtime_start="2026-07-19T16:00:00.000+02:00",
                   bedtime_end="2026-07-19T16:40:00.000+02:00")
    early = _period(type="sleep", total_sleep_duration=1800,
                    bedtime_start="2026-07-19T10:00:00.000+02:00",
                    bedtime_end="2026-07-19T10:40:00.000+02:00")
    _main, naps = biometrics.split_sleep_periods([night, late, early])
    assert [n["bedtime_start"] for n in naps] == [
        early["bedtime_start"], late["bedtime_start"]]


def test_no_periods_yields_no_main_and_no_naps():
    assert biometrics.split_sleep_periods([]) == (None, [])
    assert biometrics.day_total_sleep_seconds(None, []) == 0.0


# ─── 3. duration counts naps, architecture does not ──────────────────────────

def test_duration_includes_naps_but_the_architecture_denominator_does_not(monkeypatch):
    """The single most important invariant here. sleep_score divides REM and
    deep seconds by oura_sleep_total_seconds; if that ever picked up nap
    sleep whose REM is not in the numerator, every REM and deep share on a
    nap day would silently deflate."""
    repo = _repo_with_periods(monkeypatch, [
        _period(total_sleep_duration=13320, efficiency=74,
                rem_sleep_duration=3000, deep_sleep_duration=2400),
        _period(type="sleep", total_sleep_duration=8220,
                bedtime_start="2026-07-19T09:24:30.000+02:00",
                bedtime_end="2026-07-19T12:30:30.000+02:00"),
    ])
    day = repo._oura_sleep_metrics_by_date("2026-07-01", "2026-07-31")["2026-07-19"]
    assert day["sleep_duration_hours"] == 5.98        # night + nap
    assert day["oura_sleep_total_seconds"] == 13320   # night only
    assert day["oura_sleep_efficiency"] == 74         # night only


def test_hrv_and_resting_hr_stay_main_period_only(monkeypatch):
    """A nap's average_hrv is measured over minutes of a body that has been
    awake all day. Averaging it into an overnight figure would corrupt the
    baseline every readiness score is scaled against."""
    repo = _repo_with_periods(monkeypatch, [
        _period(total_sleep_duration=13320, average_hrv=42, lowest_heart_rate=51),
        _period(type="sleep", total_sleep_duration=8220, average_hrv=10,
                lowest_heart_rate=71,
                bedtime_start="2026-07-19T09:24:30.000+02:00",
                bedtime_end="2026-07-19T12:30:30.000+02:00"),
    ])
    day = repo._oura_sleep_metrics_by_date("2026-07-01", "2026-07-31")["2026-07-19"]
    assert day["hrv_ms"] == 42
    assert day["resting_heart_rate"] == 51


def test_a_duplicated_night_reaches_the_engine_once(monkeypatch):
    repo = _repo_with_periods(monkeypatch, [
        _period(total_sleep_duration=26520),
        _period(total_sleep_duration=26700),
    ])
    day = repo._oura_sleep_metrics_by_date("2026-07-01", "2026-07-31")["2026-07-19"]
    assert day["sleep_duration_hours"] == 7.42


def test_a_night_with_no_nap_is_unchanged(monkeypatch):
    """The overwhelming majority of days. Nap support must be invisible on
    them, or it has moved history it had no business moving."""
    repo = _repo_with_periods(monkeypatch, [_period(total_sleep_duration=25200)])
    day = repo._oura_sleep_metrics_by_date("2026-07-01", "2026-07-31")["2026-07-19"]
    assert day["sleep_duration_hours"] == 7.0
    assert day["oura_sleep_total_seconds"] == 25200


# ─── 4. the drill-down ───────────────────────────────────────────────────────

def test_the_drill_down_carries_naps_and_both_totals(monkeypatch):
    repo = _repo_with_periods(monkeypatch, [
        _period(total_sleep_duration=13320),
        _period(type="sleep", total_sleep_duration=8220, efficiency=74,
                bedtime_start="2026-07-19T09:24:30.000+02:00",
                bedtime_end="2026-07-19T12:30:30.000+02:00"),
    ])
    d = repo.get_sleep_night_details("2026-07-01", "2026-07-31")["2026-07-19"]
    assert d["total_seconds"] == 13320          # the night the stages describe
    assert d["day_total_seconds"] == 21540      # what the engine scored
    assert d["nap_seconds"] == 8220
    assert len(d["naps"]) == 1
    assert d["naps"][0]["efficiency"] == 74


def test_the_drill_down_counts_deduplicated_periods(monkeypatch):
    """periods_on_day is shown to a person; counting a re-analysis as a
    second period would claim a night that did not happen."""
    repo = _repo_with_periods(monkeypatch, [
        _period(total_sleep_duration=26520),
        _period(total_sleep_duration=26700),
    ])
    d = repo.get_sleep_night_details("2026-07-01", "2026-07-31")["2026-07-19"]
    assert d["periods_on_day"] == 1
    assert d["naps"] == []


def test_the_nap_panel_is_absent_on_a_night_without_naps():
    assert dashboard.sleep_naps_display({"naps": [], "total_seconds": 25200}) is None
    assert dashboard.sleep_naps_display(None) is None


def test_the_nap_panel_states_both_totals():
    panel = dashboard.sleep_naps_display({
        "total_seconds": 13320, "nap_seconds": 8220, "day_total_seconds": 21540,
        "naps": [{"type": "sleep", "total_seconds": 8220, "efficiency": 74,
                  "bedtime_start": "2026-07-19T09:24:30.000+02:00"}],
    })
    assert panel["night_total"] == "3h 42m"
    assert panel["day_total"] == "5h 59m"
    assert panel["nap_total"] == "2h 17m"
    assert panel["count"] == 1
    assert panel["rows"][0]["label"] == "Nap · 09:24"
    assert panel["rows"][0]["duration"] == "2h 17m"


def test_the_nap_panel_labels_a_late_nap_as_such():
    panel = dashboard.sleep_naps_display({
        "total_seconds": 25200, "nap_seconds": 2760, "day_total_seconds": 27960,
        "naps": [{"type": "late_nap", "total_seconds": 2760,
                  "bedtime_start": "2026-07-18T18:08:58.000+02:00"}],
    })
    assert panel["rows"][0]["label"] == "Late nap · 18:08"
    assert panel["rows"][0]["efficiency"] == ""
