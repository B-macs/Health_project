"""
THE RULE: in-app navigation never uses an HTML anchor.

app.py is a single-page app. Every navigation should set state (session_state
for the page, st.query_params for the Home screen's date/view/point) and let
Streamlit rerun over the EXISTING websocket. That is a few milliseconds and
the screen keeps its place.

A real <a href="?..."> does something completely different: a full browser
navigation. The page reloads, the websocket reconnects, session_state is wiped
and every st.cache_data is cold. On a phone it reads as "it opened a new page",
which is exactly how the athlete reported it, and it is why tapping a BioAge
card used to be so much slower than using the bottom nav.

Assigning to st.query_params does NOT reload — it sends a page_info_changed
ForwardMsg and the frontend rewrites the URL via the history API (see
streamlit/runtime/state/query_params.py::_send_query_param_msg). So the Home
screen can keep carrying d/view/pt in the URL — which app.py:122-129 wants
deliberately, because URL state is what survives a mobile reconnect — while
still navigating by button rather than by anchor. The two are not in tension.

WHAT THIS TEST ENFORCES
  * views/ must contain ZERO page-navigating anchors. Fully clean today.
  * app.py and styles.py may only contain the anchors named in _KNOWN below.
    Anything new fails. The list is allowed to SHRINK without touching this
    test; it may only grow by a deliberate edit here, with a reason.

Not flagged, because they navigate away from the app rather than within it:
external http(s):// links, mailto:, and in-page "#" fragments.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "views"

#: An anchor whose href is relative — starts with "?" or "/" — navigates this
#: app and therefore reloads it. Anything absolute leaves the app and is fine.
_ANCHOR = re.compile(r"""<a\s[^>]*href\s*=\s*["'](?P<href>[?/][^"']*|\{[^"']*\})""", re.I)

#: Every in-app anchor that still exists, with why it has not been converted.
#: STRUCTURAL means there is no Streamlit widget that can do the job; those
#: need a different mechanism, not a find-and-replace. PENDING means it is
#: ordinary work that simply has not been done yet.
_KNOWN: dict[str, str] = {
    "styles.py:chart-hit-bands": (
        "STRUCTURAL. The chart hit bands are up to 180 absolutely-positioned "
        "click targets overlaid on a generated SVG, one per data point. A "
        "Streamlit button cannot be positioned inside an SVG, and 180 of them "
        "per chart is not a design. Fixing this means changing how charts "
        "render (e.g. a real chart component with selection events), not "
        "swapping the tag."
    ),
    "app.py:point-detail-open": (
        "STRUCTURAL. Inside _point_detail_block, which returns an HTML STRING "
        "composed into the chart's own markdown block. A Streamlit button "
        "cannot be placed inside a string another element renders."
    ),
    "app.py:point-detail-clear": "STRUCTURAL. Same block as point-detail-open.",
    "app.py:card-click-wrapper": (
        "PENDING. _card_html's click wrapper — the Readiness / Strain / Sleep "
        "drill-downs. Convertible: the card HTML stays and a keyed button is "
        "positioned over it, the same shape as views/insights.py's BioAge "
        "cards but with an overlay, since a 460px card containing an SVG "
        "gauge cannot be a button LABEL."
    ),
    "app.py:detail-back-arrow": "PENDING. The '←' out of a detail view. Convertible.",
    "app.py:header-back-arrow": "PENDING. The '←' in the fixed detail header. Convertible.",
    "app.py:header-prev-day": "PENDING. The '‹' previous-day arrow. Convertible.",
    "app.py:header-next-day": "PENDING. The '›' next-day arrow. Convertible.",
    "app.py:checkin-fab": (
        "PENDING. The Morning Check-In FAB. Convertible, and the one app.py's "
        "own router note calls out as the reason a reconnect used to land the "
        "athlete on Check-in."
    ),
}


def _anchor_lines(path: Path) -> list[tuple[int, str]]:
    """(line number, source line) for every relative-href anchor in a file.

    Reads the file as text rather than walking the AST because these anchors
    live inside f-strings assembled across several source lines, where the AST
    gives one JoinedStr node and loses the line the tag actually sits on.
    Comments are excluded so this module's own prose does not match.
    """
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if _ANCHOR.search(line):
            out.append((i, line.strip()))
    return out


def test_views_contain_no_in_app_anchors():
    """views/ is fully converted — keep it that way.

    If this fails you have added an <a href="?..."> to a screen. Use an
    st.button with on_click instead; views/insights.py's BioAge cards are the
    worked example of one styled to look like anything you like.
    """
    offenders = {
        f"{p.relative_to(ROOT)}:{n}": src
        for p in sorted(VIEWS.glob("*.py"))
        for n, src in _anchor_lines(p)
    }
    assert not offenders, (
        "in-app <a href> found in views/ — every one is a full page reload:\n"
        + "\n".join(f"  {k}\n    {v}" for k, v in offenders.items())
    )


def test_no_new_in_app_anchors_in_app_or_styles():
    """The count may fall freely; it may only rise by editing _KNOWN.

    Deliberately asserts on the COUNT rather than on exact line numbers, so
    unrelated edits that shift lines do not fail the gate, while a genuinely
    new anchor does.
    """
    found = _anchor_lines(ROOT / "app.py") + _anchor_lines(ROOT / "styles.py")
    assert len(found) <= len(_KNOWN), (
        f"{len(found)} in-app anchors across app.py + styles.py, but only "
        f"{len(_KNOWN)} are documented in _KNOWN. A new one navigates by page "
        f"reload — convert it to an st.button with on_click, or add it to "
        f"_KNOWN with a reason if it is genuinely structural.\n"
        + "\n".join(f"  line {n}: {src}" for n, src in found)
    )


def test_every_known_exception_carries_a_reason():
    """A bare entry in _KNOWN would let anything through unexplained."""
    for name, reason in _KNOWN.items():
        assert len(reason) > 40, f"{name} needs a real reason, got {reason!r}"
        assert reason.startswith(("STRUCTURAL", "PENDING")), (
            f"{name} must classify itself as STRUCTURAL (needs a different "
            f"mechanism) or PENDING (ordinary unconverted work); got {reason[:40]!r}"
        )


def test_the_bioage_cards_navigate_by_callback_not_by_url():
    """The athlete's actual complaint, pinned: tapping a BioAge card must set
    session_state through an on_click callback rather than navigate."""
    src = (VIEWS / "insights.py").read_text(encoding="utf-8")
    assert "on_click=_open_bioage" in src
    assert "on_click=_close_bioage" in src
    # Comment lines are skipped — the module documents the anchor it replaced,
    # and the historical note is not a live link.
    assert _anchor_lines(VIEWS / "insights.py") == []


def test_bioage_selection_prefers_session_state_with_a_url_fallback():
    """session_state gives the instant rerun; the synced query param is what
    survives a websocket reconnect, which clears session_state entirely."""
    src = (VIEWS / "insights.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_bioage_selected"
    )
    body = ast.unparse(fn)
    assert "session_state" in body and "query_params" in body
    assert body.index("session_state") < body.index("query_params"), (
        "session_state must be consulted before the URL fallback"
    )
