"""
Tests for services/metrics.py — Weekly Rollup sync orchestration. Uses a
minimal fake Repository (duck-typed, not the real Notion/Sheets-backed one)
since this module only calls a handful of Repository methods.
"""

import ast
from datetime import date

from services import metrics
from services.models import Phase


class _FakeRepository:
    def __init__(self, phases=None, logged_dates=None, upsert_error=None):
        self._phases = phases or []
        self._logged_dates = logged_dates or set()
        self._upsert_error = upsert_error
        self.upserted = None

    def get_phases(self):
        return self._phases

    def get_logged_session_dates(self, start, end):
        return {d for d in self._logged_dates if start.isoformat() <= d <= end.isoformat()}

    def upsert_weekly_rollup(self, scores):
        if self._upsert_error:
            raise self._upsert_error
        self.upserted = scores
        return [s.week_start for s in scores]


_PHASE = Phase(phase_number=1, name="Stage 1 Rehab", start_date="2026-06-29", length_days=14, status="active")


def test_no_phases_is_a_clean_noop():
    repo = _FakeRepository(phases=[])
    result = metrics.sync_weekly_rollup(repo, today=date(2026, 7, 20))
    assert result.ok is True
    assert result.synced_week_starts == []


def test_never_writes_the_in_progress_week():
    # today falls inside the phase's 2nd week (2026-07-06..07-12) -> that
    # week must never appear in what gets upserted.
    repo = _FakeRepository(phases=[_PHASE], logged_dates={"2026-06-29", "2026-06-30"})
    result = metrics.sync_weekly_rollup(repo, today=date(2026, 7, 8))
    assert result.ok is True
    assert "2026-07-06" not in result.synced_week_starts
    assert all(s.status != "in_progress" for s in repo.upserted)


def test_writes_ended_weeks_stamped_with_computed_at():
    # today == the Monday right after the phase's last day (2026-07-12), so
    # the phase's own 2 weeks are both "ended" with no extra no_plan gap
    # week sneaking in before the new (2026-07-13) current week.
    repo = _FakeRepository(phases=[_PHASE], logged_dates=set())
    result = metrics.sync_weekly_rollup(repo, today=date(2026, 7, 13))
    assert result.ok is True
    assert result.synced_week_starts == ["2026-06-29", "2026-07-06"]
    assert all(s.computed_at is not None for s in repo.upserted)


def test_only_weeks_whose_verdict_changed_are_written():
    """Every ended week used to be re-stamped and rewritten on each refresh; in
    record mode each row is a waited Supabase write inside the Training page's
    render. A stored row that says the same thing is left alone — only the
    computed time would have differed."""
    from services.models import WeekScore

    class _Stored(_FakeRepository):
        def get_weekly_rollup_history(self):
            return [WeekScore(week_start="2026-06-29", week_end="2026-07-05", phase_number=1,
                              scheduled=self._first.scheduled, completed=self._first.completed,
                              status=self._first.status, computed_at="2026-07-06T08:00:00")]

    plain = _FakeRepository(phases=[_PHASE], logged_dates=set())
    metrics.sync_weekly_rollup(plain, today=date(2026, 7, 13))
    repo = _Stored(phases=[_PHASE], logged_dates=set())
    repo._first = plain.upserted[0]
    result = metrics.sync_weekly_rollup(repo, today=date(2026, 7, 13))
    assert result.ok is True
    assert result.synced_week_starts == ["2026-07-06"], "the unchanged week is not rewritten"


def test_an_unreadable_table_writes_every_ended_week():
    class _Unreadable(_FakeRepository):
        def get_weekly_rollup_history(self):
            raise RuntimeError("store unreachable")

    repo = _Unreadable(phases=[_PHASE], logged_dates=set())
    result = metrics.sync_weekly_rollup(repo, today=date(2026, 7, 13))
    assert result.synced_week_starts == ["2026-06-29", "2026-07-06"]


def test_upsert_failure_returns_failed_sync_result_not_raise():
    repo = _FakeRepository(phases=[_PHASE], upsert_error=RuntimeError("Sheets is down"))
    result = metrics.sync_weekly_rollup(repo, today=date(2026, 7, 20))
    assert result.ok is False
    assert result.synced_week_starts == []
    assert "Sheets is down" in result.error


def test_get_phases_failure_also_degrades_gracefully():
    class _BrokenRepository:
        def get_phases(self):
            raise ConnectionError("no network")

    result = metrics.sync_weekly_rollup(_BrokenRepository(), today=date(2026, 7, 20))
    assert result.ok is False
    assert "no network" in result.error


def test_no_streamlit_import():
    tree = ast.parse(open(metrics.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
