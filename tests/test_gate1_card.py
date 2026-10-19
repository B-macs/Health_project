"""The gate-1 card read and answered through services/gate1.py (move
TRN-13, 2026-10-19), so the training page and the engine API show the same
count, the same waiting week and the same flare-up, and store answers the
same way. A fake repository; no network.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from services import gate1 as g
from services import sessions as sess

START = date(2026, 10, 19)
PHASE = sess.build_phase(5, START)


def _mon(week: int) -> date:
    return START + timedelta(days=7 * (week - 1))


def _days(week: int, offsets) -> set[str]:
    return {(_mon(week) + timedelta(days=i)).isoformat() for i in offsets}


class _Repo:
    def __init__(self, logged=(), raw=None, history=None):
        self.logged = set(logged)
        self.config = {g.CONFIG_KEY: raw}
        self.history = history or {}
        self.reads = []

    def get_config_value(self, key):
        self.reads.append("config")
        return self.config.get(key)

    def set_config(self, key, value):
        self.config[key] = value

    def get_logged_session_dates(self, start, today, include_supplementary=True):
        assert include_supplementary is False, "a yoga session is not a core session"
        self.reads.append("logged")
        return set(self.logged)

    def get_recent_session_sets(self, lift, limit=0):
        self.reads.append("lift")
        return self.history.get(lift, [])


def test_a_short_week_waits_for_its_reason_and_the_answer_moves_the_count():
    repo = _Repo(logged=_days(1, (0, 1, 3)) | _days(2, (0, 1)))
    today = _mon(3) + timedelta(days=2)
    card = g.read_card(repo, PHASE, today)
    assert card["count"]["run"] == 1
    assert card["waiting"] == {"monday": _mon(2), "core_done": 2}
    g.record_reason(repo, PHASE, today, _mon(2), g.REASON_PAUSE)
    card = g.read_card(repo, PHASE, today)
    assert card["waiting"] is None and card["count"]["run"] == 1, "travel or illness pauses"


def test_a_flare_up_this_week_is_recorded_and_shown():
    repo = _Repo(logged=_days(1, (0, 1, 3)))
    today = _mon(2) + timedelta(days=3)
    assert not g.read_card(repo, PHASE, today)["flare_this_week"]
    g.record_flare(repo, PHASE, today)
    card = g.read_card(repo, PHASE, today)
    assert card["flare_this_week"] and card["this_monday"] == _mon(2)


def test_an_answer_for_a_week_outside_the_block_or_not_yet_ended_is_refused():
    repo = _Repo()
    today = _mon(3) + timedelta(days=2)
    with pytest.raises(ValueError):
        g.record_reason(repo, PHASE, today, _mon(5), g.REASON_OTHER)        # in the future
    with pytest.raises(ValueError):
        g.record_reason(repo, PHASE, today, _mon(1) + timedelta(days=1), g.REASON_OTHER)
    with pytest.raises(ValueError):
        g.record_reason(repo, PHASE, today, _mon(1), "felt lazy")
    assert repo.config[g.CONFIG_KEY] is None, "nothing was stored"


def test_the_logged_days_are_read_only_once_a_week_has_ended():
    repo = _Repo()
    g.read_card(repo, PHASE, START + timedelta(days=3))
    assert repo.reads == ["config"] + ["lift"] * len(g.MAIN_LIFTS)
    repo = _Repo()
    g.read_card(repo, PHASE, _mon(2))
    assert repo.reads == ["config", "logged"] + ["lift"] * len(g.MAIN_LIFTS)


def test_cached_reads_are_used_when_the_caller_passes_them():
    repo = _Repo()
    weights = {lift: (40.0, 44.0) for lift in g.MAIN_LIFTS}
    card = g.read_card(repo, PHASE, _mon(2), weights=weights, logged_dates=set())
    assert repo.reads == ["config"]
    assert card["lifts_met"] == len(g.MAIN_LIFTS)
    assert not card["passed"], "the weeks are not met yet"


def test_the_lift_weights_are_read_inside_the_block():
    history = {"Hack Squat": [("2026-11-02", [{"reps": 10, "weight": 66.0}]),
                              ("2026-10-19", [{"reps": 10, "weight": 60.0}]),
                              ("2026-10-12", [{"reps": 10, "weight": 40.0}])]}
    weights = g.read_lift_weights(_Repo(history=history), START)
    assert weights["Hack Squat"] == (60.0, 66.0)
    assert weights["Machine Chest Press"] == (None, None)
