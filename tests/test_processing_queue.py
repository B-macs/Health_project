"""Insights › Processing Queue and Macro Trends, moved to services on
2026-10-19 (move INS-5): the keyword parse as one job, the warnings
calendar's grouping, the warning-level groups, the trend data gate and the
recovery labels. A fake repository; no network.
"""

from __future__ import annotations

from datetime import date

from services import engine
from services import insights as insights_svc
from services import processing_queue as pq


class _Repo:
    def __init__(self, fail_note: str | None = None):
        self.notes = [{"id": "n1", "raw_text": "hip felt tight on the left"},
                      {"id": "n2", "raw_text": "all good"}]
        self.readiness = [{"id": "r1", "subjective_tightness": "lower back stiff",
                           "timestamp": "2026-10-18"}]
        self.fail_note = fail_note
        self.written: list[tuple] = []

    def get_unparsed_session_notes(self):
        return self.notes

    def get_unparsed_readiness(self):
        return self.readiness

    def update_session_note_ai(self, note_id, **fields):
        if note_id == self.fail_note:
            raise RuntimeError("store unreachable")
        self.written.append(("note", note_id, sorted(fields)))

    def update_readiness_ai(self, row_id, **fields):
        self.written.append(("readiness", row_id, fields.get("entry_date")))


def test_the_job_parses_everything_and_names_each_failure():
    repo = _Repo(fail_note="n1")
    seen: list[tuple[int, int]] = []
    out = pq.process_all(repo, {}, on_progress=lambda done, total: seen.append((done, total)))
    assert out["total"] == 3
    assert out["errors"] == ["Note n1: store unreachable"], "one failure never stops the rest"
    assert [w[:2] for w in repo.written] == [("note", "n2"), ("readiness", "r1")]
    assert ("readiness", "r1", "2026-10-18") in repo.written, "the check-in is written by date"
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_the_calendar_groups_by_day_and_opens_on_the_latest_warning():
    flagged = [{"session_date": "2026-10-03", "warning_level": "monitor"},
               {"timestamp": "2026-10-03T08:00", "warning_level": "flag"},
               {"timestamp": "2026-09-20", "warning_level": "monitor"}]
    by_date = pq.warnings_by_date(flagged)
    assert sorted(by_date) == ["2026-09-20", "2026-10-03"]
    assert pq.day_level(by_date["2026-10-03"]) == "flag"
    assert pq.day_level(by_date["2026-09-20"]) == "monitor"
    assert pq.calendar_anchor(by_date, date(2026, 10, 19)) == (2026, 10)
    assert pq.calendar_anchor({}, date(2026, 10, 19)) == (2026, 10)
    assert pq.step_month(2026, 1, -1) == (2025, 12)
    assert pq.step_month(2026, 12, 1) == (2027, 1)
    weeks = pq.month_weeks(2026, 10)
    assert weeks[0][0] == date(2026, 9, 28) and weeks[0][0].weekday() == 0


def test_an_entry_reads_its_areas_from_a_stored_list():
    shown = pq.entry_view({"body_parts": '["Left hip", "Lower back"]', "summary": "x" * 300,
                           "source": "check-in"})
    assert shown["parts"] == "Left hip, Lower back"
    assert shown["level"] == "monitor" and len(shown["summary"]) == 200
    assert pq.names("[not json") == "[not json"
    assert pq.names(["a", "b"]) == "a, b" and pq.names(None) == ""


def test_parsed_check_ins_group_by_warning_level():
    groups = pq.rows_by_warning_level([{"ai_warning_level": "flag"}, {"ai_warning_level": None},
                                       {"ai_warning_level": "monitor"}, {}])
    assert {level: len(rows) for level, rows in groups.items()} == {
        "none": 2, "monitor": 1, "flag": 1}


def test_the_trend_gate_and_the_recovery_label():
    short = insights_svc.trend_gate({"biometrics": [{}] * 3, "sessions": [{}]})
    assert short == {"bio_days": 3, "sessions": 1, "needed": engine.MIN_OBSERVATION_DAYS,
                     "enough": False}
    assert insights_svc.trend_gate(
        {"biometrics": [{}] * engine.MIN_OBSERVATION_DAYS, "sessions": []})["enough"]
    assert insights_svc.recovery_label("insufficient_data") == "Insufficient data"
    assert insights_svc.recovery_label("improving") == "Improving"
    assert insights_svc.recovery_label("holding_steady") == "Holding Steady"
