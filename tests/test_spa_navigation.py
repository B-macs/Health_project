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
  * views/, app.py and styles.py must contain ZERO in-app anchors. _KNOWN is
    empty — every one has been converted — so any anchor at all now fails.
    It may only grow by a deliberate edit here, carrying a reason.

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

#: An opening anchor tag carrying an href. Deliberately NOT trying to parse the
#: href value: these are built inside f-strings where the value is itself an
#: expression containing quotes (styles.py's hit bands are
#: `href="{it["href"]}"`), and a value-matching regex silently fails to match
#: exactly the most dynamic — i.e. most likely to be navigation — cases. The
#: repo has no external <a> links at all, so "any anchor with an href" is the
#: honest rule; if a genuine external link is ever added, allowlist it in
#: _KNOWN with an EXTERNAL reason.
_ANCHOR = re.compile(r"<a\b[^>]*href\s*=", re.I)

#: Every in-app anchor that still exists, with why it has not been converted.
#: STRUCTURAL means there is no Streamlit widget that can do the job; those
#: need a different mechanism, not a find-and-replace. PENDING means it is
#: ordinary work that simply has not been done yet.
#: EMPTY, and that is the point: there is no in-app anchor left anywhere in
#: app.py, styles.py or views/. The three that survived the first two passes
#: were the chart hit bands and the two controls inside _point_detail_block —
#: all of them anchors inside an HTML STRING another element renders, with no
#: place in the element tree to put a button. They are now `data-nav` spans
#: that styles._CHART_LINK_JS intercepts: it rewrites the query string via the
#: History API and clicks a hidden trigger button, whose rerun request carries
#: the browser's live location.search (app_session.py:454). Same page, no
#: reload. Verified in a real browser, not reasoned about — see
#: tests/test_chart_nav_bridge.py.
#:
#: Anything added here needs a reason starting STRUCTURAL or PENDING. An
#: EXTERNAL entry would be the place for a genuine outbound https:// link,
#: of which the app currently has none.
_KNOWN: dict[str, str] = {}


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """id() of every Constant that is a module/class/function docstring.

    Excluded because several of these modules EXPLAIN the anchors they
    replaced, and prose describing the rule must not trip the rule.
    """
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def _anchor_lines(path: Path) -> list[tuple[int, str]]:
    """(line number, snippet) for every anchor tag in real string literals.

    AST-based rather than a line scan: comments and docstrings are skipped
    automatically, and an f-string spanning several source lines is attributed
    to the line its own fragment sits on rather than to the start of the
    expression.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_nodes(tree)
    out: list[tuple[int, str]] = []
    seen_inner: set[int] = set()

    # f-strings FIRST, reconstructed whole. An f-string splits into alternating
    # literal and expression nodes, so `<a class="{cls}" href="{h}"` contains
    # the tag in one Constant and href= in another and NEITHER matches on its
    # own. That is not hypothetical: it is exactly how styles.py builds the
    # chart hit bands, i.e. the single most important thing for this test to
    # see. Each expression collapses to "{}" so the tag reads as markup again.
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        text = ""
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                text += part.value
                seen_inner.add(id(part))
            else:
                text += "{}"
                for sub in ast.walk(part):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        seen_inner.add(id(sub))
        if _ANCHOR.search(text):
            out.append((node.lineno, text.strip()[:100]))

    # ...then plain literals not already accounted for inside an f-string.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in skip or id(node) in seen_inner:
            continue
        if _ANCHOR.search(node.value):
            out.append((node.lineno, node.value.strip()[:100]))
    return sorted(set(out))


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
