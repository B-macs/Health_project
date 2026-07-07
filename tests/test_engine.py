"""
Tests for services/engine.py's today-parameterization fix — the one required
logic change in this refactor (both functions previously called date.today()
directly instead of accepting it as a parameter). Full engine.py coverage
already exists in the ported tests.py suite; this file targets specifically
what changed.
"""

import ast
from datetime import date

from services import engine


def test_readiness_training_modifier_is_deterministic_given_explicit_today():
    bio_rows = [{"date": "2026-07-05", "hrv_ms": 45, "resting_heart_rate": 55,
                 "sleep_duration_hours": 7.5}]
    fixed_today = date(2026, 7, 7)
    r1 = engine.readiness_training_modifier(bio_rows, today=fixed_today)
    r2 = engine.readiness_training_modifier(bio_rows, today=fixed_today)
    assert r1 == r2


def test_readiness_training_modifier_defaults_to_real_today_when_omitted():
    # Doesn't raise, still returns a well-formed directive with no rows
    result = engine.readiness_training_modifier([])
    assert "volume_factor" in result


def test_acwr_is_deterministic_given_explicit_today():
    rows = [{"date": "2026-07-01", "total_au": 100.0}, {"date": "2026-07-05", "total_au": 150.0}]
    fixed_today = date(2026, 7, 7)
    r1 = engine.acwr(rows, stage=1, today=fixed_today)
    r2 = engine.acwr(rows, stage=1, today=fixed_today)
    assert r1 == r2
    assert len(r1["daily_au_28"]) == 28


def test_acwr_different_today_changes_the_calendar_window():
    rows = [{"date": "2026-07-01", "total_au": 100.0}]
    r1 = engine.acwr(rows, today=date(2026, 7, 7))
    r2 = engine.acwr(rows, today=date(2026, 8, 7))
    # A month later, that same logged day has fallen out of the 28-day window
    assert r1["daily_au_28"] != r2["daily_au_28"]


def test_acwr_defaults_to_real_today_when_omitted():
    result = engine.acwr([], stage=1)
    assert result["status"] == "insufficient_data"


def test_no_streamlit_import():
    tree = ast.parse(open(engine.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
