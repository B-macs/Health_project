"""End-to-end render of the Strength BioAge screen through Streamlit's own
test harness, with the repository stubbed.

The pure logic is covered by test_strength.py and test_tonnage.py. What this
adds is the wiring: that the page actually runs, that the dropdown offers the
five metrics, and that selecting each one redraws the display without an
exception. A render crash is not something a unit test on services/ can catch —
it lives in the view, in st.cache_data's ability to round-trip the frozen
dataclasses the services return, and in the HTML builders.
"""

from __future__ import annotations

import json

import pytest

from streamlit.testing.v1 import AppTest


# Two loaded weeks and one unloaded week, which is the shape the real log has:
# enough for a contribution split, a week-over-week change, and a zero week.
FIXTURE_ROWS = [
    # week of 2026-07-20
    {"movement_name": "Lat Pulldown", "session_date": "2026-07-21",
     "sets": [{"reps": 10, "weight": 40}] * 3, "exercise_rpe": 5, "session_rpe": 5},
    {"movement_name": "Hip Thrust (Loaded)", "session_date": "2026-07-22",
     "sets": [{"reps": 10, "weight": 30}] * 3, "exercise_rpe": 5, "session_rpe": 5},
    {"movement_name": "Pallof Press (Cable)", "session_date": "2026-07-22",
     "sets": [{"reps": 10, "weight": 7.5}] * 3, "exercise_rpe": 5, "session_rpe": 5},
    {"movement_name": "Incline DB Press", "session_date": "2026-07-21",
     "sets": [{"reps": 10, "weight": 14}] * 3, "exercise_rpe": 5, "session_rpe": 5},
    # week of 2026-07-27 — heavier
    {"movement_name": "Lat Pulldown", "session_date": "2026-07-28",
     "sets": [{"reps": 10, "weight": 45}] * 3, "exercise_rpe": 6, "session_rpe": 6},
    {"movement_name": "Incline DB Press", "session_date": "2026-07-28",
     "sets": [{"reps": 10, "weight": 16}] * 3, "exercise_rpe": 6, "session_rpe": 6},
    {"movement_name": "Romanian Deadlift (DB)", "session_date": "2026-07-29",
     "sets": [{"reps": 10, "weight": 40}] * 3, "exercise_rpe": 6, "session_rpe": 6},
    # week of 2026-08-03 — a real session, none of it loaded
    {"movement_name": "Dead Bug", "session_date": "2026-08-03",
     "sets": [{"reps": 12, "weight": None}] * 3, "exercise_rpe": 3, "session_rpe": 3},
]

_SCRIPT = """
import json
import repo

_rows = json.loads(r'''__ROWS__''')


class _Stub:
    def get_all_training_exercises_raw(self):
        return _rows


repo.get_repository = lambda: _Stub()
from views import insights as V
V._strength_screen_data.clear()
V._render_strength_detail()
"""

_OPTIONS = [
    "Overall Strength Score",
    "Overall Strength Tonnage",
    "Upper Body Tonnage",
    "Core Tonnage",
    "Lower Body Tonnage",
]


def _app():
    script = _SCRIPT.replace("__ROWS__", json.dumps(FIXTURE_ROWS))
    return AppTest.from_string(script, default_timeout=120).run()


def _html(app) -> str:
    return "".join(block.value for block in app.markdown)


@pytest.fixture(scope="module")
def app():
    rendered = _app()
    assert not rendered.exception, rendered.exception[0].message
    return rendered


def test_the_screen_renders_without_an_exception(app):
    assert not app.exception


def test_the_dropdown_offers_the_five_metrics_in_order(app):
    assert app.selectbox[0].options == _OPTIONS


def test_the_score_is_the_default_metric(app):
    """Strength capacity is the headline; tonnage is the supporting view."""
    assert app.selectbox[0].value == "Overall Strength Score"


@pytest.mark.parametrize("option", _OPTIONS)
def test_every_metric_redraws_the_display(option):
    app = _app().selectbox[0].select(option).run()
    assert not app.exception, app.exception[0].message
    html = _html(app)
    unit = "points" if option.endswith("Score") else "kg"
    assert f"{option} · {unit}" in html
    assert 'class="sb-readout"' in html
    assert 'class="sb-chartbox"' in html
    assert "<svg" in html


def test_the_three_regions_always_render(app):
    assert _html(app).count('class="sb-region"') == 3


def test_the_hero_shows_the_anchor_and_the_calibrating_badge(app):
    html = _html(app)
    assert ">Overall Strength<" in html
    assert ">50.0<" in html
    assert "Calibrating" in html


def test_the_hero_carries_no_unit_suffix_or_sub_line(app):
    html = _html(app)
    assert "of your 2025 peak" not in html
    assert "Real age" not in html


def test_the_retired_screens_dead_affordances_are_gone(app):
    html = _html(app)
    for gone in ("Show All Progress", "Assistance", "Test your strength",
                 "Start Assessment"):
        assert gone not in html


def test_no_placeholder_leaks_into_the_markup(app):
    """A None or a NaN reaching the page means a value was formatted before it
    was checked. The image payloads and the CSS keyword `none` are excluded."""
    import re
    html = _html(app)
    scan = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    scan = re.sub(r"data:image/[a-z]+;base64,[A-Za-z0-9+/=]+", "IMG", scan)
    assert "None" not in scan
    assert "NaN" not in scan


def test_the_muscle_imbalance_findings_render(app):
    """They read the clinical profile rather than the network, so they must be
    present even though this run has a stubbed repository."""
    html = _html(app)
    assert "Muscle imbalances" in html
    assert html.count('class="i"') == 8


def test_each_plate_keeps_its_own_aspect_ratio(app):
    """The three faceplates stack into one continuous figure, so they render at
    the same width with their own native ratios. Resizing a height
    independently would break the join."""
    html = _html(app)
    for ratio in ("893/640", "893/428", "893/534"):
        assert f"aspect-ratio:{ratio}" in html


def test_only_a_zero_confidence_region_is_marked_off(app):
    """The dimmed plate is chosen by CONFIDENCE, never hardcoded. In this
    fixture — as in the real log — core is the only region with no comparable
    2025 baseline, because Pallof Press's 2025 peak was a band and a band is
    not a kilogram. Upper and lower each have two comparable lifts and so can
    corroborate themselves."""
    html = _html(app)
    assert "sb-plate core off" in html
    assert "sb-plate upper_body off" not in html
    assert "sb-plate lower_body off" not in html


def test_hovering_a_region_lights_its_own_plate_even_when_dimmed():
    """The bug this pins: the rule that dims the other plates also matched the
    dimmed plate's OWN hover at equal specificity, so pointing at core made it
    darker (.22 -> .18) instead of lighting it up. The row-hover rules must name
    .off explicitly AND come last, or the tie goes the wrong way."""
    from views import insights as V

    css = V._STRENGTH_CSS
    strip_dim = css.index(".sb-bp:hover .sb-plate.off")
    row_lights = css.index(".sb-bp .sb-region:hover .sb-plate.off")
    assert row_lights > strip_dim, "row-hover must come after strip-hover to win the tie"
    rule = css[row_lights:css.index("}", row_lights)]
    assert "opacity:1" in rule
    assert "filter:none" in rule, "the greyscale has to lift too, not just the opacity"


def test_the_screen_survives_a_repository_failure():
    """The imbalance findings still render; everything training-derived falls
    back to an empty log rather than crashing the page."""
    script = _SCRIPT.replace("__ROWS__", "[]").replace(
        "return _rows", "raise RuntimeError('notion is down')",
    )
    app = AppTest.from_string(script, default_timeout=120).run()
    assert not app.exception
    html = _html(app)
    assert "Muscle imbalances" in html
    assert html.count('class="sb-region"') == 3
