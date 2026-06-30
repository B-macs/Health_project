"""
nav.py — Shared bottom navigation bar.

Navigation uses st.session_state + on_click callbacks so the WebSocket
stays alive across transitions (no reconnect = no flash, no new page load).

How it works:
  1. Hidden Streamlit buttons (labelled ◉nav◉<page>◉) handle actual navigation.
     Their on_click sets st.session_state["_nav_page"] and triggers a rerun.
  2. A same-origin component iframe injects stNav() into the parent window and
     uses a MutationObserver to keep the trigger buttons invisible.
  3. The visual HTML nav bar calls stNav('<page>') on click — which finds
     and programmatically clicks the matching hidden button.

Call nav.inject(active) once per page, after styles.inject_css().
active keys: "home" | "training" | "insights" | "sync" | ""
"""

import streamlit as st
import streamlit.components.v1 as components

# ─── Chrome-suppression CSS ───────────────────────────────────────────────────

CHROME_CSS: str = """<style>
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarNav"],
#MainMenu,
[data-testid="stHeader"],
[data-testid="stToolbar"],
.stDeployButton,
footer { display:none !important; }

.main .block-container { padding-bottom:80px !important; }
</style>"""

# ─── Nav items ────────────────────────────────────────────────────────────────

_ITEMS = [
    ("⌂",  "Home",     "home"),
    ("📋", "Training", "training"),
    ("🧠", "Insights", "insights"),
    ("↻",  "Sync",     "sync"),
]

# Checkin has a trigger button (for the FAB) but no visible nav item
_ALL_PAGES = _ITEMS + [("", "Check-In", "checkin")]


def _set_page(page: str) -> None:
    st.session_state["_nav_page"] = page


# ─── JS bridge template ───────────────────────────────────────────────────────
# Runs inside a 1px same-origin iframe → can access window.parent.document.
# 1. Exposes stNav() in the parent window for onclick handlers.
# 2. Hides the ◉nav◉ trigger buttons by targeting their unique marker text.

_JS_BRIDGE_TMPL = """
<script>
(function() {{
  // Hide all ◉nav◉ trigger buttons — target only these, leave other buttons alone
  function hideNavTriggers() {{
    var btns = window.parent.document.querySelectorAll(
      'button[data-testid="baseButton-secondary"]'
    );
    for (var i = 0; i < btns.length; i++) {{
      var p = btns[i].querySelector('p');
      if (p && p.textContent.indexOf('◉nav◉') !== -1) {{
        var col = btns[i].closest('[data-testid="stColumn"]');
        if (col) col.style.cssText = 'position:absolute;left:-9999px;overflow:hidden;width:1px;height:1px;';
      }}
    }}
  }}

  // Expose stNav in parent window so onclick="stNav(...)" works in st.markdown content
  window.parent.stNav = function(page) {{
    var marker = '◉nav◉' + page + '◉';
    var btns = window.parent.document.querySelectorAll(
      'button[data-testid="baseButton-secondary"]'
    );
    for (var i = 0; i < btns.length; i++) {{
      var p = btns[i].querySelector('p');
      if (p && p.textContent.indexOf(marker) !== -1) {{
        btns[i].click();
        return;
      }}
    }}
  }};

  // Hide immediately and re-hide after any Streamlit re-render
  hideNavTriggers();
  setTimeout(hideNavTriggers, 150);
  var obs = new MutationObserver(hideNavTriggers);
  obs.observe(window.parent.document.body, {{childList: true, subtree: true}});
}})();
</script>
"""


def _item_html(icon: str, label: str, page: str, active: bool) -> str:
    col = "#D4DCEE" if active else "#6B7A9B"
    dot = (
        '<div style="width:4px;height:4px;border-radius:50%;background:#6BAF8B;'
        'margin:2px auto 0;"></div>'
    ) if active else '<div style="height:6px;"></div>'
    return (
        f'<div onclick="stNav(\'{page}\')" style="display:flex;flex-direction:column;'
        f'align-items:center;justify-content:center;flex:1;padding:8px 4px;cursor:pointer;">'
        f'<span style="font-size:20px;line-height:1;">{icon}</span>'
        f'<span style="font-size:10px;color:{col};margin-top:3px;letter-spacing:0.2px;">'
        f'{label}</span>'
        f'{dot}'
        f'</div>'
    )


def bottom_nav_html(active: str = "", max_width: int = 0) -> str:
    inner_style = (
        f"max-width:{max_width}px;margin:0 auto;height:68px;display:flex;align-items:stretch;"
        if max_width else
        "height:68px;display:flex;align-items:stretch;"
    )
    items = "".join(
        _item_html(icon, label, page, page == active)
        for icon, label, page in _ITEMS
    )
    return (
        '<div style="position:fixed;bottom:0;left:0;right:0;z-index:900;'
        'background:#0B0F1E;border-top:1px solid #1E2840;">'
        f'<div style="{inner_style}">'
        + items +
        '</div></div>'
    )


def inject(active: str = "", max_width: int = 0) -> None:
    """
    Inject sidebar-suppression CSS, JS navigation bridge, hidden trigger
    buttons, and the visual bottom nav bar.

    Must be called after st.set_page_config().
    """
    # 1. Hide sidebar / chrome immediately
    st.markdown(CHROME_CSS, unsafe_allow_html=True)

    # 2. JS bridge — 1px same-origin iframe; exposes stNav() in parent window
    #    and hides the ◉nav◉ trigger buttons
    components.html(_JS_BRIDGE_TMPL, height=1, scrolling=False)

    # 3. Hidden trigger buttons for all pages (including checkin for the FAB)
    _cols = st.columns(len(_ALL_PAGES))
    for col, (_, _, page) in zip(_cols, _ALL_PAGES):
        with col:
            st.button(
                f"◉nav◉{page}◉",  # ◉nav◉page◉ — unique marker for JS to find
                key=f"_nb_{page}",
                on_click=_set_page,
                args=(page,),
            )

    # 4. Visual nav bar (pure HTML, no <a href> — uses stNav() onclick)
    st.markdown(bottom_nav_html(active, max_width=max_width), unsafe_allow_html=True)
