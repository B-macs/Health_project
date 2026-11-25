"""A run of poor nights ends in rest (engine.poor_sleep_run, 2026-11-25).

The athlete, of 22 Nov: "Poor run of nights should also contribute, for me 5
nights of reduced sleep and then HRV drop and sleep drop two days in a row at
the end of a 5 night sleep drop. that should be rest." His two answers: our
Sleep Score is the measure of a reduced night ("Yes, build it"), and one good
night ends the run ("A").

The nights below are made up in the SHAPE of 18-22 Nov (the five Sleep Scores
falling, HRV and sleep time down on the last two), over a flat history; the
rule's replay on his own stored nights (rest on 22 Nov and on no other day
from 2026-07-01) is recorded in CLAUDE.md, not pinned here.
"""

from datetime import date, timedelta

import pytest

from services import decision, engine

DAY = date(2026, 11, 22)

#: The five nights of the run, oldest first: (Sleep Score, HRV ms, sleep h).
RUN = [(72.3, 18.0, 7.2), (72.0, 21.0, 6.87), (63.8, 22.0, 7.07),
       (61.4, 17.0, 6.08), (60.6, 16.0, 6.08)]
BASE = (74.0, 20.0, 7.0)


def _nights(run=RUN, history=40, last_day=DAY):
    """`history` flat nights, then the run ending on `last_day`: (rows, scores)."""
    nights = [BASE] * history + list(run)
    first = last_day - timedelta(days=len(nights) - 1)
    rows, scores = [], {}
    for i, (score, hrv, sleep) in enumerate(nights):
        d = (first + timedelta(days=i)).isoformat()
        rows.append({"date": d, "hrv_ms": hrv, "resting_heart_rate": 55.0,
                     "sleep_duration_hours": sleep, "oura_temperature_deviation": 0.0})
        if score is not None:
            scores[d] = score
    return rows, scores


def _light(rows, scores, for_date=DAY):
    return engine.traffic_light(rows[-28:], drift_rows=rows, for_date=for_date,
                                sleep_scores=scores)


def _recommendation(tl):
    return engine.volume_recommendation(tl, engine.acwr([], stage=2), stage=2,
                                        observation_days_remaining=0, injury_weight_val=0.0)


# ─── His example ────────────────────────────────────────────────────────────

def test_his_five_poor_nights_end_in_rest():
    rows, scores = _nights()
    tl = _light(rows, scores)
    assert tl["poor_sleep_run"]["fires"]
    assert tl["poor_sleep_run"]["nights"] == [(DAY - timedelta(days=4 - i)).isoformat()
                                              for i in range(5)]
    assert tl["overall"] == "red" and tl["poor_sleep_run_applied"]
    assert tl["drivers"][0] == engine.POOR_SLEEP_RUN
    assert tl["driver_summary"].startswith(engine.POOR_RUN_REASON)
    rec = _recommendation(tl)
    assert rec["label"] == "REST / DELOAD" and rec["multiplier"] == 0.0
    assert engine.POOR_RUN_REASON in rec["action"] and "Rest" in rec["action"]


def test_without_the_scores_the_same_morning_is_the_reduced_load_it_was():
    """The run is left out when no Sleep Scores are passed: the light every
    caller saw before 2026-11-25 (here HRV and sleep down: reduced load)."""
    rows, _ = _nights()
    tl = _light(rows, None)
    assert tl["overall"] == "yellow"
    assert not tl["poor_sleep_run"]["fires"]
    assert engine.POOR_SLEEP_RUN not in tl["drivers"]


def test_the_reason_says_the_rule_in_words():
    assert (engine.POOR_RUN_NIGHTS, engine.POOR_RUN_LAST_DOWN, engine.YELLOW_THRESHOLD) == (5, 2, 0.10)
    assert "five nights in a row" in engine.POOR_RUN_REASON
    assert "more than 10% under" in engine.POOR_RUN_REASON
    assert "the last two nights" in engine.POOR_RUN_REASON


# ─── His answer A: one good night ends the run ──────────────────────────────

def test_one_good_night_ends_the_run():
    rows, scores = _nights(run=RUN + [(79.0, 24.0, 7.9)], last_day=DAY + timedelta(days=1))
    tl = _light(rows, scores, for_date=DAY + timedelta(days=1))
    assert not tl["poor_sleep_run"]["fires"]
    assert tl["overall"] == "green"


# ─── What does not make the run ─────────────────────────────────────────────

def test_four_poor_nights_are_not_a_run():
    rows, scores = _nights(run=[(75.0, 20.0, 7.0)] + RUN[1:])
    assert not _light(rows, scores)["poor_sleep_run"]["fires"]


def test_a_night_with_no_sleep_score_breaks_the_run():
    rows, scores = _nights(run=[RUN[0], (None, 21.0, 6.87)] + RUN[2:])
    tl = _light(rows, scores)
    assert not tl["poor_sleep_run"]["fires"]
    assert tl["overall"] == "yellow"


def test_a_missing_day_breaks_the_run():
    rows, scores = _nights()
    gap = rows[-3]["date"]
    rows = [r for r in rows if r["date"] != gap]
    scores.pop(gap)
    assert not _light(rows, scores)["poor_sleep_run"]["fires"]


def test_hrv_down_without_sleep_down_is_not_the_end_of_a_run():
    rows, scores = _nights(run=RUN[:4] + [(60.6, 16.0, 7.0)])
    assert not _light(rows, scores)["poor_sleep_run"]["fires"]


def test_only_the_last_night_down_is_not_the_end_of_a_run():
    rows, scores = _nights(run=RUN[:3] + [(61.4, 20.0, 7.0), RUN[4]])
    tl = _light(rows, scores)
    assert not tl["poor_sleep_run"]["fires"]
    assert tl["overall"] == "yellow"


def test_too_little_history_is_not_judged():
    rows, scores = _nights(history=engine.POOR_RUN_MIN_BASELINE_ROWS - 6)
    assert not engine.poor_sleep_run(rows, scores, DAY)["fires"]


# ─── How each night is judged ───────────────────────────────────────────────

def test_each_night_is_judged_against_its_own_average():
    """The first night (73.0) is under its own 28-day average (about 74) and
    over the judged day's, which already holds four very poor nights: it is a
    reduced night, as 18 Nov was."""
    run = [(73.0, 20.0, 7.0), (50.0, 20.0, 7.0), (50.0, 20.0, 7.0),
           (50.0, 16.0, 6.0), (50.0, 16.0, 6.0)]
    rows, scores = _nights(run=run)
    judged_day_average = sum(scores[r["date"]] for r in rows[-28:]) / 28
    assert 73.0 > judged_day_average
    assert _light(rows, scores)["poor_sleep_run"]["fires"]


def test_the_run_never_makes_a_day_clearer():
    """A day already red stays red, and the run is still named first."""
    rows, scores = _nights(run=RUN[:4] + [(60.6, 12.0, 6.08)])
    tl = _light(rows, scores)
    assert tl["overall"] == "red" and tl["poor_sleep_run"]["fires"]
    assert not tl["poor_sleep_run_applied"]
    assert tl["drivers"][:2] == [engine.POOR_SLEEP_RUN, "hrv_ms"]


def test_a_morning_with_no_reading_stays_waiting():
    rows, scores = _nights()
    for k in ("hrv_ms", "resting_heart_rate", "sleep_duration_hours"):
        rows[-1][k] = None
    tl = _light(rows, scores)
    assert tl["status"] == engine.STATUS_AWAITING_DATA


# ─── The decision feeds it ──────────────────────────────────────────────────

class _Repo:
    def __init__(self, fail_wake=False):
        self.asked = []
        self.fail_wake = fail_wake

    def get_effective_wake_adjustments(self, start=None, end=None):
        self.asked.append((start, end))
        if self.fail_wake:
            raise RuntimeError("wake failed")
        return {end: 30.0}, {end: "fusion"}


def test_the_decision_scores_each_night_with_its_wake_correction(monkeypatch):
    rows, _ = _nights()
    seen = []

    def score(d, bio_rows, wake_time_adjustments=None):
        seen.append(wake_time_adjustments)
        return 70.0

    monkeypatch.setattr(decision.sleep_score, "compute_sleep_score", score)
    repo = _Repo()
    scores = decision.run_sleep_scores(repo, rows, DAY)
    need = engine.POOR_RUN_NIGHTS + engine.POOR_RUN_BASELINE_ROWS
    assert len(scores) == need and max(scores) == DAY.isoformat()
    assert repo.asked == [(rows[-need]["date"], DAY.isoformat())]
    assert all(a == {DAY.isoformat(): 30.0} for a in seen)


def test_a_failed_wake_read_scores_ouras_own_nights(monkeypatch):
    rows, _ = _nights()
    seen = []
    monkeypatch.setattr(decision.sleep_score, "compute_sleep_score",
                        lambda d, r, wake_time_adjustments=None: seen.append(wake_time_adjustments) or 70.0)
    assert decision.run_sleep_scores(_Repo(fail_wake=True), rows, DAY)
    assert set(map(repr, seen)) == {"None"}


def test_a_failed_score_leaves_the_run_out_and_never_the_light(monkeypatch):
    rows, _ = _nights()

    def boom(*a, **k):
        raise RuntimeError("score failed")

    monkeypatch.setattr(decision.sleep_score, "compute_sleep_score", boom)
    assert decision.run_sleep_scores(_Repo(), rows, DAY) is None


def test_engine_state_passes_the_scores_to_the_light(monkeypatch):
    captured = {}
    real = engine.traffic_light

    def spy(*a, **k):
        captured.update(k)
        return real(*a, **k)

    monkeypatch.setattr(decision.engine, "traffic_light", spy)
    monkeypatch.setattr(decision, "run_sleep_scores", lambda repo, rows, day: {"x": 1.0})
    from tests.test_decision import FakeRepo
    decision.engine_state(FakeRepo(), DAY)
    assert captured["sleep_scores"] == {"x": 1.0}
    assert captured["for_date"] == DAY


def test_the_hrv_note_stays_quiet_when_the_run_decided_the_day():
    reads = []
    note = decision.hrv_note({"_traffic_drivers": (engine.POOR_SLEEP_RUN,)}, DAY,
                             lambda: reads.append(1) or {})
    assert note == "" and reads == []
