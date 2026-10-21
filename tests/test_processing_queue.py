"""Insights › Processing Queue and Macro Trends, moved to services on
2026-10-19 (move INS-5): the keyword parse as one job, the warnings
calendar's grouping, the warning-level groups, the trend data gate and the
recovery labels. A fake repository; no network.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

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


def test_the_calendar_groups_by_day_and_opens_on_today():
    flagged = [{"session_date": "2026-10-03", "warning_level": "monitor"},
               {"timestamp": "2026-10-03T08:00", "warning_level": "flag"},
               {"timestamp": "2026-09-20", "warning_level": "monitor"}]
    by_date = pq.warnings_by_date(flagged)
    assert sorted(by_date) == ["2026-09-20", "2026-10-03"]
    assert pq.day_level(by_date["2026-10-03"]) == "flag"
    assert pq.day_level(by_date["2026-09-20"]) == "monitor"
    assert pq.calendar_anchor(date(2026, 10, 19)) == (2026, 10)
    # The owner, 2026-10-21: "When I go to warnings it should open on the current day". It
    # opened on the latest warning's month, which read as a calendar stuck in August.
    assert pq.calendar_anchor(date(2026, 12, 2)) == (2026, 12), "today's month, not the latest warning's"

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


# ── every save that stores a note reads it for warnings (I63) ──────────────────

#: The calls that store a note (a check-in's sensation note, a session's notes, a yoga
#: flow's note), by file: the name each is called by there.
_NOTE_SAVES = {
    "services/checkin_form.py": {"save"},
    "services/training_session.py": {"save_session", "save_yoga"},
    "views/checkin.py": {"save"},
    "views/training.py": {"save_session", "save_yoga"},
}


def _called(fn: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    return names


def test_every_save_that_stores_a_note_reads_it_for_warnings():
    """The old app's check-in and session saves did not run the keyword parse, so every
    note they stored after the Processing Queue's button was last pressed (early August)
    waited unread, and the warnings calendar showed nothing after 6 August until the first
    check-in saved from the phone (2026-10-21, 07:18) read the backlog. Every function that
    stores a note now runs the parse after it, in the engine and in the old app."""
    repo_root = Path(__file__).resolve().parents[1]
    checked = 0
    for rel, saves in _NOTE_SAVES.items():
        tree = ast.parse((repo_root / rel).read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                called = _called(fn)
                if called & saves and fn.name not in saves:
                    checked += 1
                    assert "parse_after_save" in called, f"{rel}::{fn.name} stores a note and never reads it"
    assert checked >= 6, f"only {checked} saving functions found: the scan has lost its targets"
