"""services/home.py: Home's three cards for one day.

Moved out of app.py on 2026-10-19 so the phone's API returns the same numbers
for the phone's date. What it pins:

  * every read ends on the day shown (inventory fault F8), and a failed
    biometric read says so while the other reads still happen;
  * an unreadable stage scores no strain and says why, never stage 1 (F7);
  * a past day's rest-day load counts back from that day, as its stored
    trend point does (F8);
  * the daily readiness and its breakdown come from one set of rows, and on
    today those are the engine's (F6);
  * the day rules: no day after the caller's today, the verdict on today
    only, the 30-day trend ending on the day shown.
"""

from __future__ import annotations

from datetime import date, timedelta

from services import dashboard as dash
from services import decision, home, readiness
from services.models import BiometricRecord

TODAY = date(2026, 10, 19)
PAST = date(2026, 10, 10)


class FakeRepo:
    """The reads home.read_home makes; each records what it was asked."""

    def __init__(self, fail=()):
        self.asked: dict[str, tuple] = {}
        self.fail = set(fail)

    def _maybe_fail(self, name):
        if name in self.fail:
            raise RuntimeError(f"{name} failed")

    def get_biometric_rolling(self, days=28, today=None):
        self.asked["bio"] = (days, today)
        self._maybe_fail("bio")
        return [BiometricRecord(date=today.isoformat(), hrv_ms=44.0)]

    def get_daily_session_au_weighted(self, days=28, today=None):
        self.asked["au"] = (days, today)
        return []

    def get_metrics_history(self, start=None, end=None):
        self.asked["history"] = (start, end)
        return []

    def get_effective_wake_adjustments(self, start=None, end=None):
        self.asked["wake"] = (start, end)
        return {}, {}

    def get_session_hr_history(self, start=None):
        self.asked["hr"] = (start,)
        return [{"date": "2026-10-09", "hr_strain": 9.0}, {"date": "2026-10-12", "hr_strain": 11.0}]

    def get_current_stage(self):
        self._maybe_fail("stage")
        return 2


def test_every_window_ends_on_the_day_shown():
    repo = FakeRepo()
    reads = home.read_home(repo, PAST)
    start = (PAST - timedelta(days=home.HISTORY_DAYS)).isoformat()
    assert repo.asked == {
        "bio": (home.BIO_DAYS, PAST), "au": (home.AU_DAYS, PAST),
        "history": (start, PAST.isoformat()), "wake": (start, PAST.isoformat()),
        "hr": (start,)}
    assert [r["date"] for r in reads.hr_rows] == ["2026-10-09"]     # nothing after the day
    assert reads.bio_rows[0]["date"] == PAST.isoformat() and reads.stage == 2


def test_a_failed_biometric_read_is_flagged_and_the_rest_still_read():
    repo = FakeRepo(fail={"bio"})
    reads = home.read_home(repo, PAST)
    assert reads.bio_failed and reads.bio_rows == []
    assert {"au", "history", "wake", "hr"} <= set(repo.asked)


def _au(day: date, au: float) -> dict:
    return {"date": day.isoformat(), "total_au": au}


def test_an_unreadable_stage_scores_no_strain_and_says_why():
    """F7. Read as stage 1, the same session would have scored another
    number, because the strain scales with the stage."""
    session = [_au(PAST, 420.0)]
    assert home.read_home(FakeRepo(fail={"stage"}), PAST).stage is None
    unknown = home.snapshot(home.HomeReads(day=PAST, au_rows=session, stage=None))
    assert unknown["strain"] is None and unknown["strain_unscored_reason"] == home.STAGE_UNREAD
    known = home.snapshot(home.HomeReads(day=PAST, au_rows=session, stage=2))
    assert known["strain"] is not None and known["strain_unscored_reason"] == ""
    guessed = home.snapshot(home.HomeReads(day=PAST, au_rows=session, stage=1))
    assert guessed["strain"] != known["strain"]


def test_a_past_days_rest_day_load_counts_back_from_that_day():
    """F8. No session on PAST, so its card shows the load of the 7 days before
    it — as its stored trend point does (Repository.sync_metrics_history
    counts back from each day) — not the 7 days before the server's today."""
    before_past = [_au(PAST - timedelta(days=n), 500.0) for n in range(1, 8)]
    before_today = [_au(TODAY - timedelta(days=n), 100.0) for n in range(1, 8)]
    reads = home.HomeReads(day=PAST, au_rows=before_past, stage=2)
    card = home.snapshot(reads)
    assert card["strain_is_rolling"]
    stored = dash.compute_daily_metrics_snapshot(PAST, [], before_past, 2)
    assert card["strain"] == stored["strain"]
    old = dash.compute_daily_metrics_snapshot(PAST, [], before_past + before_today, 2,
                                              rolling_reference_date=TODAY)
    assert old["strain"] != card["strain"]


_OURA_KEYS = ("oura_hrv_balance", "oura_recovery_index", "oura_previous_night",
              "oura_resting_heart_rate_score", "oura_body_temperature",
              "oura_previous_day_activity", "oura_sleep_regularity",
              "oura_activity_balance")


def _rows(end: date, n: int = 20) -> list[dict]:
    """Ascending rows ending on `end`, every readiness component scorable."""
    return [{"date": (end - timedelta(days=i)).isoformat(), "hrv_ms": 40.0 + i % 5,
             "resting_heart_rate": 54.0 + i % 3, "sleep_duration_hours": 7.0 + (i % 4) / 4,
             **{k: 70.0 + (i + j) % 20 for j, k in enumerate(_OURA_KEYS)}}
            for i in range(n)][::-1]


def test_the_daily_and_its_breakdown_come_from_one_set_of_rows():
    """F6. The card's daily IS the breakdown's score, and on today it is the
    number the engine bucketed (decision.readiness_raw over the same rows)."""
    rows = _rows(TODAY)
    daily, breakdown = home.readiness_daily(TODAY, rows)
    assert daily == breakdown["score"]
    assert daily == decision.readiness_raw(rows, TODAY)
    assert daily == readiness.compute_readiness(for_date=TODAY, bio_rows=rows)
    assert home.readiness_daily(TODAY, [])[0] is None


def test_today_reads_the_engines_rows_and_a_past_day_its_own():
    engine_rows, home_rows = _rows(TODAY, 14), _rows(TODAY, 60)
    assert home.readiness_rows_for(TODAY, TODAY, engine_rows, home_rows) is engine_rows
    assert home.readiness_rows_for(PAST, TODAY, None, home_rows) is home_rows
    assert home.readiness_rows_for(TODAY, TODAY, None, home_rows) is home_rows


def test_the_card_shows_the_daily_and_falls_back_to_the_trend():
    assert home.readiness_card(58.0, 66.0) == 58.0
    assert home.readiness_card(None, 66.0) == 66.0
    assert home.readiness_card(None, None) is None


def test_the_verdict_shows_on_the_callers_today_only():
    assert home.verdict_is_due(TODAY, TODAY)
    assert not home.verdict_is_due(PAST, TODAY)


def test_no_day_after_the_callers_today():
    assert home.day_bounds(TODAY + timedelta(days=3), TODAY) == (
        TODAY, TODAY - timedelta(days=1), None)
    assert home.day_bounds(PAST, TODAY) == (
        PAST, PAST - timedelta(days=1), PAST + timedelta(days=1))
    assert home.day_bounds(None, TODAY)[0] == TODAY


def test_sleep_need_is_the_baseline_else_the_default():
    assert home.sleep_need([])[0] == dash.SLEEP_NEED_HOURS_DEFAULT
    need, base, window = home.sleep_need(_rows(TODAY, 30))
    assert need == base and window


def test_the_trend_window_is_thirty_days_ending_on_the_day():
    window = home.trend_window(PAST)
    assert len(window) == home.TREND_DAYS == 30
    assert window[-1] == PAST and window[0] == PAST - timedelta(days=29)


def test_the_scales_are_the_cards_tops():
    assert home.SCALES == {"readiness": 100.0, "sleep": 100.0, "strain": 21.0}


def test_the_trend_series_reads_the_stored_record_for_thirty_days():
    history = [{"date": "2026-10-01", "readiness_score": 61.0},
               {"date": "2026-10-09", "readiness_score": 64.0},
               {"date": "2026-10-12", "readiness_score": 70.0}]       # after PAST
    dates, values, latest = home.trend_series(history, PAST, "readiness_score")
    assert dates == home.trend_window(PAST)
    assert values[-2] == 64.0 and values[-1] is None
    assert values.count(None) == 28
    assert latest == 64.0
    assert home.trend_series([], PAST, "strain")[2] is None


def test_home_reads_are_keyed_by_the_day_shown():
    """F9. A cached read keyed only by a window size kept ending yesterday for
    up to half an hour after midnight; each of Home's reads now takes the day
    its window ends on as its first argument, so the cache is keyed by it."""
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).resolve().parent.parent / "app.py").read_text(
        encoding="utf-8"))
    readers = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("_bio_rolling", "_au_history", "_metrics_history_rolling",
                 "_wake_time_adjustments_rolling", "_session_hr_rolling",
                 "_stage_start_cached"):    # F27: the stage start as of the day shown
        assert readers[name].args.args[0].arg == "end_iso", name


def test_the_date_bar_says_today_or_the_date():
    assert home.date_label(TODAY, TODAY) == "TODAY"
    assert home.date_label(PAST, TODAY) == PAST.isoformat()


def test_the_readiness_pair_is_always_both_figures_titled():
    # Athlete, 2026-08-25: "Rather always see both labeled even when blank."
    assert home.score_pair(56.7, 61.2) == (("DAILY", "57"), ("TREND", "61"))
    assert home.score_pair(None, 61.2) == (("DAILY", "--"), ("TREND", "61"))
    assert home.score_pair(None, None) == (("DAILY", "--"), ("TREND", "--"))
