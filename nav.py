"""
nav.py — Bottom navigation bar.

Single-layer pattern: four st.button() widgets in st.columns(4), positioned
fixed at the bottom of the viewport via CSS. No separate visual HTML, no
invisible overlay — one layer, one source of truth.

Navigation: on_click sets st.session_state["_nav_page"], triggering a WebSocket
rerun without page reload or new connection.

Call nav.inject(active) once per page, AFTER all page content is rendered.
active keys: "home" | "training" | "insights" | "sync" | ""
"""

import streamlit as st

# ─── Nav items ────────────────────────────────────────────────────────────────

_ITEMS = [
    ("⌂",  "Home",     "home"),
    ("📋", "Training", "training"),
    ("🧠", "Insights", "insights"),
    ("↻",  "Voice Training", "sync"),
]

# ─── Chrome-suppression + nav CSS ─────────────────────────────────────────────

CHROME_CSS: str = """<style>
[data-testid="stSidebar"],
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavViewButton"],
[data-testid="stTopNavSection"],
[data-testid="stTopNavPopover"],
[data-testid="stNavSectionHeader"],
[data-testid="stMainMenu"],
#MainMenu,
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stAppDeployButton"],
.stDeployButton,
footer { display:none !important; }

.main .block-container { padding-bottom:80px !important; }

/* ── Nav marker: remove from layout, keep in DOM for :has() ──────────────── */
[data-testid="stElementContainer"]:has(.stNavRow) {
    display: none !important;
}

/* ── Nav container (stElementContainer wrapping stHorizontalBlock) ───────────
   Streamlit 1.58 wraps every rendered element in stElementContainer.
   The marker's container is :has(.stNavRow); the NEXT sibling is the buttons. */
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 68px !important;
    z-index: 9000 !important;
    margin: 0 !important;
    padding: 0 !important;
    background: #0B0F1E !important;
    border-top: 1px solid #1E2840 !important;
    overflow: hidden !important;
}

/* ── Flex row: prevent Streamlit's 640px column-stacking breakpoint ──────────
   Below 640px Streamlit sets min-width: calc(100% - 1.8rem) on each column,
   stacking them vertically. Override to force 4 equal columns. */
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stHorizontalBlock"] {
    height: 68px !important;
    gap: 0 !important;
    flex-wrap: nowrap !important;
    align-items: stretch !important;
}
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stColumn"] {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    height: 68px !important;
    padding: 0 !important;
}

/* ── Propagate height down through inner stElementContainer ──────────────── */
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stColumn"] > div {
    height: 68px !important;
}

/* ── Button: full-height transparent slab ───────────────────────────────── */
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] button {
    width: 100% !important;
    height: 68px !important;
    min-height: 0 !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 4px !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] button:hover {
    background: rgba(255,255,255,0.06) !important;
    border: none !important;
}
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] button:focus,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] button:focus-visible {
    outline: none !important;
    box-shadow: none !important;
}

/* ── Button text: icon on first line (larger), label on second (smaller) ─────
   Label string is "{icon}  \\n{label}" — two trailing spaces create a markdown
   hard line break (<br>), so ::first-line matches the icon. */
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] button p,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] button span {
    white-space: pre-line !important;
    text-align: center !important;
    line-height: 1.25 !important;
    font-size: 10px !important;
    margin: 0 !important;
    padding: 0 !important;
    pointer-events: none !important;
}
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"] button p::first-line {
    font-size: 20px !important;
}

/* ── Inactive colour (overrides styles.py mobile button defaults) ──────────── */
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-secondary"],
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="baseButton-secondary"] {
    background: transparent !important;
    border: none !important;
    padding: 0 4px !important;
}
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-secondary"] p,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-secondary"] span,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="baseButton-secondary"] p,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="baseButton-secondary"] span {
    color: #6B7A9B !important;
}

/* ── Active colour ─────────────────────────────────────────────────────────── */
/* [data-testid="..."] repeated on each selector below is a deliberate
   specificity boost (doubling an attribute selector is valid CSS and reliably
   outweighs simpler page-level button rules like the training page's white-pill
   CTA override) so the active nav tab never gets swallowed by another page's CSS. */
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-primary"][data-testid="stBaseButton-primary"],
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="baseButton-primary"][data-testid="baseButton-primary"] {
    background: transparent !important;
    border: none !important;
    padding: 0 4px !important;
}
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-primary"][data-testid="stBaseButton-primary"] p,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-primary"][data-testid="stBaseButton-primary"] span,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="baseButton-primary"][data-testid="baseButton-primary"] p,
[data-testid="stElementContainer"]:has(.stNavRow) + [data-testid="stElementContainer"]
    [data-testid="baseButton-primary"][data-testid="baseButton-primary"] span {
    color: #00E874 !important;
}
</style>"""


def _set_page(page: str) -> None:
    st.session_state["_nav_page"] = page


def inject(active: str = "", max_width: int = 0) -> None:
    """
    Render sidebar-suppression CSS and fixed bottom nav buttons.
    Must be called after all page content is rendered.
    max_width is accepted for API compatibility but ignored (buttons span full width).
    """
    st.markdown(CHROME_CSS, unsafe_allow_html=True)
    # Marker: :has(.stNavRow) in CHROME_CSS identifies the nav container that follows.
    st.markdown('<div class="stNavRow" style="display:none"></div>', unsafe_allow_html=True)
    cols = st.columns(len(_ITEMS))
    for col, (icon, label, page) in zip(cols, _ITEMS):
        with col:
            st.button(
                f"{icon}  \n{label}",
                key=f"_nav_{page}",
                on_click=_set_page,
                args=(page,),
                type="primary" if page == active else "secondary",
                use_container_width=True,
            )
