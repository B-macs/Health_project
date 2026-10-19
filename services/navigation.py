"""Which page the app opens (move INS-8, rebuild Phase 2, 2026-10-19).

The Streamlit app routes on the page set by its nav buttons, with the
address bar's ?page= as the fallback after a reconnect. An unknown page is
Home: an old ?page=sync bookmark from before the voice app moved out (rebuild
Phase 1) must not keep the address bar on a page that no longer exists.
"""

from __future__ import annotations

HOME = "home"
#: Every page the app routes to.
PAGES: tuple[str, ...] = (HOME, "training", "insights", "checkin")


def resolve_page(nav_page: str | None, url_page: str | None) -> str:
    """The page to draw: the one the nav set, else the address bar's, else
    Home; an unknown page is Home."""
    page = nav_page or url_page or HOME
    return page if page in PAGES else HOME
