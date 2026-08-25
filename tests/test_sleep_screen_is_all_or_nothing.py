"""The Sleep screen is all of a night or none of it.

2026-08-25, 08:03. The athlete opened Sleep and got "No Readings" over "Oura
recorded no sleep period for this night" -- with 7h 06m asleep, 8h 56m in bed,
80 % efficiency and 56 bpm drawn immediately underneath it.

The night was real: Oura had 2026-08-25 at 25,590 s asleep in 32,168 s in bed,
efficiency 80, lowest HR 56, from a period that ended 07:56:35 -- seven minutes
before the screenshot. What was stale was the OTHER read. The score and the
night detail come off the same Oura sleep-periods tab through the same
main-period gate, but they are cached separately and taken at different
moments, so the top of the screen was working off a read taken before the
morning sync and the panels below it off one taken after.

His instruction: "I want the sleep to be fully blank until the data is there,
I should be able to review yesterdays sleep by toggling to yesterday if I want
that."

So two things hold this shut. The score decides for the WHOLE screen -- no
score, no night panels, no wake-time stepper -- and the drill-down carries its
own day arrows, because it used to replace them with the back button and the
only way to reach another night was to go back to Home and re-open the card.
"""

import ast
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The actual night behind the screenshot, as Oura stored it.
NIGHT = {
    "total_seconds": 25590.0, "time_in_bed_seconds": 32168.0,
    "efficiency": 80.0, "lowest_heart_rate": 56.0,
    "deep_seconds": 3600.0, "light_seconds": 15000.0, "rem_seconds": 6990.0,
    "awake_seconds": 6578.0, "naps": [], "hypnogram_30sec": "",
    "hr_series": {}, "hrv_series": {}, "movement_30sec": "",
    "bedtime_start": "2026-08-24T23:00:27.000+01:00",
    "bedtime_end": "2026-08-25T07:56:35.000+01:00",
}
NIGHT_DATE = date(2026, 8, 25)

LEFT_ARROW = "‹"


def _sleep_screen(monkeypatch, *, score, details=None, fusion=None,
                  read_failed=False, stale=False):
    """The sleep drill-down's two blocks, rendered against one night."""
    import app as home
    monkeypatch.setattr(home, "selected_date", NIGHT_DATE)
    monkeypatch.setattr(home, "_sleep_details",
                        {NIGHT_DATE.isoformat(): NIGHT} if details is None else details)
    monkeypatch.setattr(home, "_sleep_details_loaded", True)
    monkeypatch.setattr(home, "_sleep_context", {})
    monkeypatch.setattr(home, "_sleep_fusion_rows", fusion or {})
    monkeypatch.setattr(home, "_bio_rows", [])
    monkeypatch.setattr(home, "_wake_adjustments", {})
    monkeypatch.setattr(home, "_bio_rows_failed", read_failed)
    monkeypatch.setattr(home, "_bio_rows_stale", stale)
    monkeypatch.setattr(home, "_sleep_breakdown_cache", {"score": score})
    return home, home._sleep_contributors_block(), home._sleep_night_blocks()


def test_a_full_night_is_not_drawn_under_a_header_saying_there_is_none(monkeypatch):
    """THE REPORTED SCREEN. The detail read has the whole night; the score
    does not. Nothing about the night may render."""
    import app as home
    _h, _contrib, night = _sleep_screen(monkeypatch, score=home._NOT_COMPUTED)
    assert night == ""
    for figure in ("7h 06m", "8h 56m", "80 %", "56 bpm",
                   "Total sleep", "Time in bed", "Sleep debt", "Time asleep"):
        assert figure not in night


def test_the_same_night_renders_in_full_once_it_is_scored(monkeypatch):
    """The gate must not blank a good night -- which is the whole reason the
    stale biometric rows are re-read rather than simply believed."""
    _h, _contrib, night = _sleep_screen(monkeypatch, score=84.8)
    for figure in ("Total sleep", "7h 06m", "Time in bed", "8h 56m",
                   "80 %", "56 bpm"):
        assert figure in night


def test_an_unscored_night_says_why_without_a_contributors_heading(monkeypatch):
    """There are no contributors to head. One plain line, and it points at the
    arrow that reaches a night which does have data."""
    import app as home
    _h, contrib, _night = _sleep_screen(monkeypatch, score=home._NOT_COMPUTED)
    assert "Oura recorded no sleep period for this night." in contrib
    assert ">Contributors<" not in contrib
    assert LEFT_ARROW in contrib, "the way out has to be on the screen"


def test_a_failed_read_still_says_so_rather_than_blaming_the_ring(monkeypatch):
    """Blanking the screen must not swallow the one message the reader can
    act on."""
    import app as home
    _h, contrib, night = _sleep_screen(
        monkeypatch, score=home._NOT_COMPUTED, read_failed=True)
    assert "loading problem" in contrib
    assert "no sleep period" not in contrib
    assert night == ""


def test_the_watch_only_night_is_the_one_thing_that_still_draws(monkeypatch):
    """It earns the exception by saying in its own text that there is no Sleep
    Score and that only the timeline is real -- nothing there is presented as
    having been scored."""
    import app as home
    fusion = {NIGHT_DATE.isoformat(): {
        "source": "garmin_only", "master_hypnogram": "2223",
        "master_deep_minutes": 60, "master_light_minutes": 240,
        "master_rem_minutes": 90, "master_awake_minutes": 20,
    }}
    _h, _contrib, night = _sleep_screen(
        monkeypatch, score=home._NOT_COMPUTED, details={}, fusion=fusion)
    assert "there is no Sleep Score" in night
    assert "the stage timeline below is real" in night


def test_a_night_with_nothing_at_all_draws_nothing_at_all(monkeypatch):
    import app as home
    _h, _contrib, night = _sleep_screen(
        monkeypatch, score=home._NOT_COMPUTED, details={}, fusion={})
    assert night == ""


# --- The way out: day arrows on the drill-down -------------------------------

def test_the_drill_down_carries_its_own_day_arrows():
    """It used to render ONLY the back button, so reaching another night meant
    going back to Home, stepping the day there and re-opening the card."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'key="hdr_dprev"' in src and 'key="hdr_dnext"' in src
    assert ".st-key-hdr_dprev" in src and ".st-key-hdr_dnext" in src, \
        "unpositioned, they land in the page body instead of the header"


def test_stepping_the_day_drops_the_selected_chart_point():
    """A selected point is an index into THIS night's series. Carried across,
    it silently selects an unrelated sample of another night."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_render_header_buttons")
    day_buttons = [
        c for c in ast.walk(fn)
        if isinstance(c, ast.Call)
        and any(k.arg == "key" and getattr(k.value, "value", None) in
                ("hdr_dprev", "hdr_dnext") for k in c.keywords)
    ]
    assert len(day_buttons) == 2
    for call in day_buttons:
        kwargs = next(k.value for k in call.keywords if k.arg == "kwargs")
        keys = {getattr(k, "value", None) for k in kwargs.keys}
        assert "d" in keys and "pt" in keys


def test_the_wake_time_stepper_is_gated_on_the_same_score():
    """Offering a wake-time correction for a night with no reading is the same
    half-a-screen the night panels were gated for."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'if view == "sleep" and _sleep_is_scored():' in src


def test_one_breakdown_serves_both_the_panel_and_the_gate():
    """Two derivations could disagree about whether the night was scored,
    which is exactly the split this whole file exists to close."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert src.count("sleep_score_model.sleep_score_breakdown(") == 1
