"""The sleep-movement scale is fitted on one watch's nights only.

CLAUDE.md, written before the upgrade: "REFIT the movement calibration, and do
NOT pool 645 and 265 nights." The rule was in sleep_movement.py's comments and
nothing enforced it: the fit kept running over all paired history, pooling 26
Forerunner 645 nights with the 265's (found 2026-10-13 while answering whether
Garmin movement could feed Restfulness). The 265's first night on record is
the first night Garmin reported HRV, which the 645 never did: 2026-08-06.
"""
from __future__ import annotations

from services import sleep_movement
from services.config import Config
from services.repository import Repository


def _repo() -> Repository:
    return Repository(Config(
        notion_api_key="ntn_test", notion_db_readiness="db-readiness",
        notion_db_training="db-training", notion_db_config="db-config",
        google_sheets_id="sheet-id", google_service_account={"type": "service_account"}))


def _night(day: str) -> dict:
    return {"movement_30_sec": "1112211", "bedtime_start": f"{day}T23:00:00+02:00"}


def test_the_first_night_is_the_first_night_the_watch_reported_hrv():
    assert sleep_movement.CALIBRATION_WATCH_FIRST_NIGHT == "2026-08-06"


def test_only_the_current_watchs_nights_reach_the_fit(monkeypatch):
    repo = _repo()
    asked: list[str] = []

    def match(day, start, end, garmin_by_date):
        asked.append(day)
        return None, 0.0
    monkeypatch.setattr(repo, "_match_garmin_night", match)
    oura = {d: _night(d) for d in ("2026-07-20", "2026-08-03", "2026-08-05",
                                   "2026-08-06", "2026-09-01")}
    assert repo.sleep_movement_cutpoints(oura, {}) is None, "nothing paired, nothing fitted"
    assert sorted(asked) == ["2026-08-06", "2026-09-01"], (
        "a 645 night, or a night that may be one, must never be paired")
