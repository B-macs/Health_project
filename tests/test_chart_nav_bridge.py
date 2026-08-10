"""
The chart-point click bridge — styles._CHART_LINK_JS + chart_hits().

WHY A BROWSER TEST. Chart points were the last thing in the app that still
navigated: each tappable band was an <a href="?d=...&pt=...">, so selecting a
point on a chart reloaded the whole app — websocket reconnect, session_state
gone, every cache cold — to move a marker inside one chart (CLAUDE.md Key Rule
17). They could not become st.buttons: chart_hits() returns an HTML string
composed into a chart's own markdown, and there are up to services.dashboard.
hit_bands' max_bands (48) of them laid over a generated SVG, so there is no
point in the Streamlit element tree at which a widget could sit.

The fix is a JS bridge, and a bridge is exactly the kind of thing that is
plausible on paper and broken in practice. It rests on one fact that is not
documented anywhere and lives in minified frontend code: that a rerun request
carries the browser's LIVE window.location.search rather than a copy Streamlit
took when it last wrote the URL itself. The Python end of that is visible
(streamlit/runtime/app_session.py feeds ClientState.query_string straight into
RerunData) but the browser end is not, so it is asserted here against a real
Chromium rather than reasoned about.

The no-reload half matters just as much as the param half: a bridge that
worked by reloading would pass a naive "did Python see it" check while doing
precisely the thing being removed. A marker planted on window before the click
is the witness — a navigation wipes it.

Skipped, never failed, when playwright or its browser binary is missing: this
is a real end-to-end test and the gate must stay runnable on a bare checkout.
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="playwright not installed"
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


APP = """
import streamlit as st
import sys
sys.path.insert(0, {root!r})
import styles
from services import dashboard as dash

# The real stylesheet, because .hp-hit is what gives the bands their size —
# without it they are zero-area inline spans and nothing can be clicked.
styles.inject_css()

st.write("PT_VALUE:", st.query_params.get("pt", "<none>"))

# One real chart_hits overlay, built exactly the way the app builds it.
hits = [
    {{"left": l, "width": w, "href": "?d=2026-08-10&view=sleep&pt=" + dash.point_selection_key("sleep", i),
      "title": "point %d" % i, "selected": False}}
    for l, w, i in dash.hit_bands(4)
]
st.markdown(
    '<div id="chartbox" style="position:relative;height:80px;background:#123;">'
    + styles.chart_hits(hits) + '</div>',
    unsafe_allow_html=True,
)
st.markdown(styles.CHART_NAV_TRIGGER_CSS, unsafe_allow_html=True)
st.button(styles.CHART_NAV_TRIGGER_LABEL, key=styles.CHART_NAV_TRIGGER_KEY)
styles.enable_chart_links()
"""


@pytest.fixture(scope="module")
def running_app(tmp_path_factory):
    d = tmp_path_factory.mktemp("chartnav")
    script = d / "chart_nav_app.py"
    script.write_text(APP.format(root=str(ROOT)), encoding="utf-8")
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(script),
         "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        yield f"http://localhost:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_clicking_a_chart_point_selects_it_without_reloading(running_app):
    """The whole contract in one test, because the two halves are only
    meaningful together: Python must see the new selection AND the page must
    have survived. Either alone is a bridge that does not do its job."""
    with playwright_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:            # browser binary not downloaded
            pytest.skip(f"no chromium available: {exc}")
        try:
            page = browser.new_page()
            page.goto(running_app, wait_until="load")
            page.wait_for_selector("text=PT_VALUE", timeout=60000)
            page.wait_for_selector(".hp-hit", timeout=60000)
            time.sleep(2)  # let the bridge iframe install its listeners

            assert "<none>" in page.inner_text("body")

            # Survives a rerun; wiped by a navigation.
            page.evaluate("window.__navProbe = 'alive'")

            page.locator(".hp-hit").nth(2).click()
            time.sleep(4)

            body = page.inner_text("body")
            shown = re.search(r"PT_VALUE:\s*(\S+)", body)
            assert shown, f"PT_VALUE missing from page: {body[:300]}"
            assert "sleep" in shown.group(1), (
                f"Python did not receive the clicked point: {shown.group(1)}"
            )
            assert "pt=" in page.url, f"URL not updated: {page.url}"
            assert page.evaluate("window.__navProbe || '<WIPED>'") == "alive", (
                "the page RELOADED — the bridge is navigating, which is the "
                "exact behaviour Key Rule 17 exists to remove"
            )
        finally:
            browser.close()


def test_chart_hits_emits_no_anchor():
    """Cheap structural guard, no browser needed — the bridge only helps if
    the markup stopped being a link in the first place."""
    sys.path.insert(0, str(ROOT))
    import styles

    html = styles.chart_hits(
        [{"left": 0.0, "width": 0.5, "href": "?d=2026-08-10&pt=sleep:1",
          "title": "t", "selected": False}]
    )
    assert "<a " not in html and "href=" not in html
    assert 'data-nav="?d=2026-08-10&pt=sleep:1"' in html
    assert 'role="button"' in html and 'tabindex="0"' in html


def test_the_bridge_and_its_trigger_agree_on_the_label():
    """The bridge finds the hidden button by its LABEL TEXT. If the constant
    and the JS ever drift apart the click silently goes nowhere: the URL
    changes, no rerun happens, and the screen sits there looking broken."""
    sys.path.insert(0, str(ROOT))
    import styles

    assert styles.CHART_NAV_TRIGGER_LABEL in styles._CHART_LINK_JS
    assert f"st-key-{styles.CHART_NAV_TRIGGER_KEY}" in styles.CHART_NAV_TRIGGER_CSS
