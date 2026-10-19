"""Fault F21 (rebuild Phase 2, fixed 2026-10-19): screen text that no longer
described the app. Supabase is the only store since 2026-10-09, Oura runs on
an OAuth login since 2026-08-17, the device sync runs every 2 hours, and the
plan is not 14 days. None of the old wording may come back.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENS = [ROOT / "app.py", *(ROOT / "views").glob("*.py")]

OUT_OF_DATE = (
    "not Google Sheets",
    "Add OURA_TOKEN",
    "14-Day Plan",
    "syncs automatically once a day",
    "Sheet tabs",
    "its own sheet tab",
)


def test_no_screen_prints_the_out_of_date_wording():
    for path in SCREENS:
        text = path.read_text(encoding="utf-8")
        for phrase in OUT_OF_DATE:
            assert phrase not in text, f"{path.name}: {phrase!r}"


def test_the_oura_setup_text_names_the_login():
    text = (ROOT / "views" / "insights.py").read_text(encoding="utf-8")
    assert "python scripts/authorize_oura.py" in text
