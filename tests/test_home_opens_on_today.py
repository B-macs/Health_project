"""Home opens on today; a past day lasts only for the visit it was picked in.

Athlete, 2026-10: "When opening readiness - 17th Sept was opened it should be
today's date." Home keeps its day in the address (?d=) so a reconnect mid-visit
lands where it was, and the Home Screen app reopens the last address — so a day
picked on 17 September came back weeks later, and a card tapped on any day
pinned the address to a date that was yesterday by the next morning (the tap
wrote today's date as a fixed value). Now today writes no ?d= at all, a past
day carries the day it was picked on (?ds=), and a new session keeps the past
day only when it was picked today — which is what a reconnect is.
"""
from __future__ import annotations

import pathlib
from datetime import date

from services import dashboard as dash

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = date(2026, 10, 13)


def test_a_new_session_opens_on_today_unless_the_day_was_picked_today():
    on_open = dash.home_date_on_open
    assert on_open(None, None, TODAY) == TODAY
    assert on_open("2026-09-17", None, TODAY) == TODAY, "the address from 17 September"
    assert on_open("2026-09-17", "2026-09-17", TODAY) == TODAY, "picked on an earlier day"
    assert on_open("2026-10-10", "2026-10-13", TODAY) == date(2026, 10, 10), "a reconnect"
    assert on_open("2026-10-13", "2026-10-13", TODAY) == TODAY
    assert on_open("2026-10-20", "2026-10-13", TODAY) == TODAY, "never a future day"
    assert on_open("not-a-date", "2026-10-13", TODAY) == TODAY


def test_today_writes_nothing_and_a_past_day_says_when_it_was_picked():
    params = dash.home_date_params
    assert params(TODAY, TODAY) == {"d": None, dash.HOME_DATE_SET_ON_PARAM: None}
    assert params(None, TODAY) == {"d": None, dash.HOME_DATE_SET_ON_PARAM: None}
    assert params(date(2026, 10, 12), TODAY) == {
        "d": "2026-10-12", dash.HOME_DATE_SET_ON_PARAM: "2026-10-13"}
    assert params("2026-10-12", TODAY)["d"] == "2026-10-12"


def test_what_is_written_reads_back_as_the_same_day_in_a_reconnect():
    """The two halves agree: a day written by home_date_params is the day a
    same-day new session opens on, and tomorrow it is today again."""
    for picked in (date(2026, 10, 1), date(2026, 10, 12), TODAY):
        written = dash.home_date_params(picked, TODAY)
        assert dash.home_date_on_open(written["d"], written[dash.HOME_DATE_SET_ON_PARAM],
                                      TODAY) == picked
        tomorrow = date(2026, 10, 14)
        assert dash.home_date_on_open(written["d"], written[dash.HOME_DATE_SET_ON_PARAM],
                                      tomorrow) == tomorrow


def test_every_writer_of_the_day_goes_through_the_rule():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "dash.home_date_on_open(" in src, "the session-start read"
    assert "params.update(dash.home_date_params(chosen, date.today()))" in src, "_go"
    assert 'state.update(dash.home_date_params(state.pop("d", None), _today))' in src, (
        "_url_state, for the chart links that reload the page")


def test_there_is_one_button_back_to_today_and_it_is_a_button():
    """Key Rule 17: in-app navigation is a button, never an anchor
    (tests/test_spa_navigation.py counts the anchors)."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert src.count('key="go_today"') == 1
    assert 'st.button("Back to today", key="go_today", on_click=_go,' in src
