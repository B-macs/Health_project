"""Which page the app opens (move INS-8, 2026-10-19): the page the nav set,
else the address bar's, else Home; an unknown page is Home."""

from __future__ import annotations

from services import navigation as nav


def test_the_nav_wins_over_the_address_bar():
    assert nav.resolve_page("training", "insights") == "training"
    assert nav.resolve_page(None, "insights") == "insights"
    assert nav.resolve_page("", "checkin") == "checkin"


def test_no_page_or_an_unknown_page_is_home():
    assert nav.resolve_page(None, None) == nav.HOME
    assert nav.resolve_page(None, "sync") == nav.HOME, "an old voice-app bookmark"
    assert nav.resolve_page("strength", None) == nav.HOME
