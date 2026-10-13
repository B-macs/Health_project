"""Strain's two inflating inputs: a session left open, and a repeat save.

The athlete asked where strain is weak (2026-10). The two weaknesses that move
the number most are both inputs, not maths: session minutes are clock time
from Start to Save (2026-09-16 was left open and logged 189 min — 378 AU
against a real ~90), and a repeat save adds the whole session again (2026-09-10
was saved three times — 1,306 AU, strain 17.1). The save now asks which length
to keep when the clock runs past 1.5 times the plan, and the Sync tab lists a
date with two plan sessions or a day far above the rest.
"""
from __future__ import annotations

import pathlib
from datetime import date

from services import sessions as sess
from services.config import Config
from services.repository import Repository

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ─── the length question ─────────────────────────────────────────────────────

def test_the_save_asks_only_when_the_clock_runs_well_past_the_plan():
    assert sess.duration_needs_a_check(189, 45), "2026-09-16"
    assert sess.duration_needs_a_check(91, 60)
    assert not sess.duration_needs_a_check(90, 60), "1.5 times is not past it"
    assert not sess.duration_needs_a_check(66, 67), "the usual session"
    assert not sess.duration_needs_a_check(30, 0), "no model, no question"


def test_the_training_screen_saves_the_chosen_length():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "sess.duration_needs_a_check(elapsed_minutes, _modelled_minutes)" in src
    assert "elapsed_minutes = _save_minutes" in src, "the save uses the chosen minutes"
    assert "options=[_modelled_minutes, elapsed_minutes], index=0" in src, (
        "the planned length is the default answer")


# ─── the log check ───────────────────────────────────────────────────────────

def _s(sid, d, au, plan=True):
    return {"session_id": sid, "date": d, "au": au, "duration_minutes": 60, "plan": plan}


def test_two_plan_sessions_on_one_date_are_flagged_and_a_yoga_beside_one_is_not():
    rows = [_s("a", "2026-09-10", 410), _s("b", "2026-09-10", 405),
            _s("c", "2026-10-05", 380), _s("d", "2026-10-05", 45, plan=False)]
    warnings = sess.session_log_warnings(rows)
    assert len(warnings) == 1
    assert "2026-09-10" in warnings[0] and "repeat save" in warnings[0]


def test_a_day_far_above_every_other_is_flagged():
    days = [_s(f"s{i}", f"2026-09-{i:02d}", 300) for i in range(1, 9)]
    days.append(_s("x", "2026-09-16", 900))
    warnings = sess.session_log_warnings(days)
    assert any("2026-09-16" in w and "left open" in w for w in warnings)


def test_a_clean_log_and_a_thin_one_say_nothing():
    clean = [_s(f"s{i}", f"2026-09-{i:02d}", 280 + i * 5) for i in range(1, 15)]
    assert sess.session_log_warnings(clean) == []
    thin = [_s("a", "2026-09-01", 100), _s("b", "2026-09-02", 900)]
    assert sess.session_log_warnings(thin) == [], "too few days to call one an outlier"


# ─── the reader: one row per SESSION, not per date ──────────────────────────

def _page(sid, d, au, kind="Strength"):
    return {"properties": {
        "Session ID": {"type": "rich_text", "rich_text": [{"plain_text": sid}]},
        "Session Date": {"type": "date", "date": {"start": d}},
        "Session AU": {"type": "number", "number": au},
        "Session Duration": {"type": "number", "number": 60},
        "Type": {"type": "select", "select": {"name": kind}},
    }}


def test_the_reader_keeps_two_sessions_on_one_date_apart(monkeypatch):
    repo = Repository(Config(
        notion_api_key="ntn_test", notion_db_readiness="db-readiness",
        notion_db_training="db-training", notion_db_config="db-config",
        google_sheets_id="sheet-id", google_service_account={"type": "service_account"}))
    pages = [_page("2026-09-10-a", "2026-09-10", 410), _page("2026-09-10-a", "2026-09-10", 410),
             _page("2026-09-10-b", "2026-09-10", 405),
             _page("2026-10-05-y", "2026-10-05", 45, kind="Yoga")]
    monkeypatch.setattr(repo, "_query", lambda db, filter_=None, sorts=None: pages)
    rows = repo.get_session_summaries(days=35, today=date(2026, 10, 13))
    assert [r["session_id"] for r in rows] == ["2026-09-10-a", "2026-09-10-b", "2026-10-05-y"]
    assert [r["plan"] for r in rows] == [True, True, False]
    assert any("2026-09-10" in w for w in sess.session_log_warnings(rows))


def test_the_sync_tab_shows_the_checks():
    src = (ROOT / "views" / "insights.py").read_text(encoding="utf-8")
    assert "sessions_svc.session_log_warnings(" in src
    assert "get_session_summaries(days=35)" in src
