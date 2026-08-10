"""
styles.py — Responsive dual-theme.
Oura aesthetic (mobile ≤768px) · Whoop aesthetic (desktop ≥769px).
"""

import math
import streamlit as st

from services import dashboard as _dash

# ─── Colour palettes ───────────────────────────────────────────────────────────

OURA: dict[str, str] = {
    "bg":         "#0B0F1E",
    "surface":    "#131929",
    "surface_hi": "#1A2238",
    "text":       "#D4DCEE",
    "subtext":    "#6B7A9B",
    "border":     "#1E2840",
    "green":      "#6BAF8B",
    "amber":      "#BFA06A",
    "coral":      "#C47878",
    "radius":     "18px",
}

WHOOP: dict[str, str] = {
    "bg":         "#07080D",
    "surface":    "#0E1018",
    "surface_hi": "#13161F",
    "text":       "#FFFFFF",
    "subtext":    "#5A6377",
    "border":     "#1C1F2C",
    "green":      "#00E874",
    "yellow":     "#F5C700",
    "red":        "#FF2D44",
    "radius":     "4px",
}

_OURA_SIG: dict[str, str]  = {
    "green": OURA["green"], "yellow": OURA["amber"],
    "red": OURA["coral"],   "orange": OURA["amber"], "grey": OURA["subtext"],
}
_WHOOP_SIG: dict[str, str] = {
    "green": WHOOP["green"], "yellow": WHOOP["yellow"],
    "red": WHOOP["red"],     "orange": WHOOP["yellow"], "grey": WHOOP["subtext"],
}


def oura_signal(sig: str) -> str:
    return _OURA_SIG.get(sig, OURA["subtext"])


def whoop_signal(sig: str) -> str:
    return _WHOOP_SIG.get(sig, WHOOP["subtext"])


# ─── Layout switch ─────────────────────────────────────────────────────────────

def dual_layout(desktop_html: str, mobile_html: str) -> str:
    """Wrap content for CSS-based responsive switching."""
    return (
        f'<div class="whoop-only">{desktop_html}</div>'
        f'<div class="oura-only">{mobile_html}</div>'
    )


# ─── Component: Oura circular ring ────────────────────────────────────────────

def oura_ring(value: float | int | None, label: str, color: str,
              fill: float = -1.0, size: int = 100) -> str:
    """SVG arc ring — Oura style.  fill ∈ [0,1]; -1 = auto from value/100."""
    if fill < 0:
        fill = max(0.0, min(1.0, float(value) / 100.0)) if value is not None else 0.0
    r = (size - 18) // 2
    circ = round(2 * math.pi * r, 2)
    offset = round(circ * (1 - fill), 2)
    if value is None:
        display = "—"
    elif isinstance(value, float) and not value.is_integer():
        display = f"{value:.1f}"
    else:
        display = str(int(value))
    hw = size // 2
    fsize  = max(14, size // 6)
    lfsize = max(9,  size // 12)
    return (
        f'<div style="position:relative;width:{size}px;height:{size}px;margin:0 auto 6px;">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{hw}" cy="{hw}" r="{r}" fill="none"'
        f' stroke="{OURA["surface_hi"]}" stroke-width="9"/>'
        f'<circle cx="{hw}" cy="{hw}" r="{r}" fill="none"'
        f' stroke="{color}" stroke-width="9"'
        f' stroke-dasharray="{circ}" stroke-dashoffset="{offset}"'
        f' stroke-linecap="round" transform="rotate(-90 {hw} {hw})"/>'
        f'</svg>'
        f'<div style="position:absolute;top:50%;left:50%;'
        f'transform:translate(-50%,-50%);text-align:center;line-height:1.2;">'
        f'<div style="font-size:{fsize}px;font-weight:500;color:{OURA["text"]};'
        f'font-family:system-ui;">{display}</div>'
        f'<div style="font-size:{lfsize}px;color:{OURA["subtext"]};'
        f'letter-spacing:0.3px;white-space:nowrap;">{label}</div>'
        f'</div></div>'
    )


# ─── Component: Oura soft card ─────────────────────────────────────────────────

def oura_card(title: str, body: str, accent: str | None = None,
              subtitle: str = "") -> str:
    border = f"border-top:3px solid {accent};" if accent else ""
    sub = (
        f'<div style="font-size:12px;color:{OURA["subtext"]};margin-bottom:8px;">'
        f'{subtitle}</div>'
    ) if subtitle else ""
    return (
        f'<div style="background:{OURA["surface"]};border-radius:{OURA["radius"]};'
        f'padding:18px 20px;margin-bottom:12px;{border}'
        f'box-shadow:0 2px 14px rgba(0,0,0,0.28);">'
        f'<div style="font-size:15px;font-weight:600;color:{OURA["text"]};'
        f'margin-bottom:3px;">{title}</div>'
        f'{sub}'
        f'<div style="font-size:13px;color:{OURA["subtext"]};line-height:1.6;">{body}</div>'
        f'</div>'
    )


# ─── Component: Whoop stat block ───────────────────────────────────────────────

def whoop_stat(label: str, value: str, delta: str = "",
               signal: str = "grey", unit: str = "") -> str:
    """Dense left-bordered stat — Whoop style."""
    color = whoop_signal(signal)
    delta_html = (
        f'<div style="font-size:9px;color:{color};margin-top:1px;font-family:monospace;">'
        f'{delta}</div>'
    ) if delta else ""
    return (
        f'<div style="border-left:2px solid {color};padding:8px 10px;'
        f'background:{WHOOP["surface"]};'
        f'border-radius:0 {WHOOP["radius"]} {WHOOP["radius"]} 0;margin-bottom:4px;">'
        f'<div style="font-size:8px;color:{WHOOP["subtext"]};letter-spacing:1.5px;'
        f'text-transform:uppercase;font-family:monospace;">{label}</div>'
        f'<div style="font-size:20px;font-weight:700;color:{WHOOP["text"]};'
        f'font-family:monospace;line-height:1.1;margin-top:1px;">'
        f'{value}'
        f'<span style="font-size:9px;color:{WHOOP["subtext"]};margin-left:2px;">{unit}</span>'
        f'</div>'
        f'{delta_html}'
        f'</div>'
    )


# ─── Component: Whoop bordered panel ──────────────────────────────────────────

def whoop_panel(title: str, body: str, signal: str = "grey") -> str:
    color = whoop_signal(signal)
    return (
        f'<div style="background:{WHOOP["surface"]};border:1px solid {WHOOP["border"]};'
        f'border-top:2px solid {color};border-radius:{WHOOP["radius"]};'
        f'padding:12px 14px;">'
        f'<div style="font-size:8px;color:{WHOOP["subtext"]};letter-spacing:2px;'
        f'text-transform:uppercase;font-family:monospace;margin-bottom:8px;">{title}</div>'
        f'{body}'
        f'</div>'
    )


# ─── Global CSS injection ─────────────────────────────────────────────────────

def inject_css() -> None:
    """Call once at the top of every page (after set_page_config)."""
    st.markdown(_build_css(), unsafe_allow_html=True)


def _build_css() -> str:
    W = WHOOP
    O = OURA
    return f"""<style>
/* ── layout-switch helpers ─────────────────────────────────────────────────── */
.whoop-only {{ display:block; }}
.oura-only  {{ display:none;  }}

/* ══ WHOOP  /  DESKTOP ════════════════════════════════════════════════════════ */

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"]  {{ background:{W['bg']} !important; }}
[data-testid="stSidebar"] {{ background:{W['surface']} !important;
                             border-right:1px solid {W['border']} !important; }}
.main .block-container    {{ padding:1.1rem 1.4rem 2rem !important; max-width:none !important; }}

h1 {{ color:{W['text']} !important; font-size:20px !important; font-weight:700 !important;
      letter-spacing:-0.01em !important; }}
h2 {{ color:{W['text']} !important; font-size:11px !important; font-weight:700 !important;
      text-transform:uppercase !important; letter-spacing:2px !important; }}
h3 {{ color:{W['subtext']} !important; font-size:10px !important;
      text-transform:uppercase !important; letter-spacing:1.5px !important; }}

p, .stMarkdown p, li   {{ color:{W['text']} !important; font-size:13px !important; }}
.stCaption,
[data-testid="stCaptionContainer"] p {{ color:{W['subtext']} !important; font-size:10px !important; }}
hr {{ border-color:{W['border']} !important; margin:10px 0 !important; }}

/* Native metrics — covers stMetric (1.36+) and metric-container (legacy) */
[data-testid="stMetric"],
[data-testid="metric-container"] {{ background:{W['surface']} !important;
    border:1px solid {W['border']} !important; border-radius:{W['radius']} !important;
    padding:10px 14px !important; }}
[data-testid="stMetricValue"]    {{ color:{W['text']} !important; font-size:22px !important;
    font-weight:700 !important; font-family:monospace !important; }}
[data-testid="stMetricLabel"]    {{ color:{W['subtext']} !important; font-size:9px !important;
    text-transform:uppercase !important; letter-spacing:1.5px !important; }}
[data-testid="stMetricDelta"]    {{ font-size:10px !important; }}

/* Buttons — covers Streamlit ≤1.35 (baseButton-*) and 1.36+ (stBaseButton-*) */
[data-testid="stBaseButton-secondary"],
[data-testid="baseButton-secondary"] {{ background:{W['surface_hi']} !important;
    color:{W['text']} !important; border:1px solid {W['border']} !important;
    border-radius:{W['radius']} !important; font-size:12px !important; }}
[data-testid="stBaseButton-primary"],
[data-testid="baseButton-primary"]   {{ background:{W['green']} !important;
    color:{W['bg']} !important; border:none !important;
    border-radius:{W['radius']} !important; font-size:12px !important; font-weight:700 !important; }}

/* Expander / Form */
[data-testid="stExpander"] {{ background:{W['surface']} !important;
    border:1px solid {W['border']} !important; border-radius:{W['radius']} !important; }}
[data-testid="stForm"]     {{ background:{W['surface']} !important;
    border:1px solid {W['border']} !important; border-radius:{W['radius']} !important; }}

/* Inputs */
.stTextInput input, .stNumberInput input, .stTextArea textarea {{
    background:{W['surface_hi']} !important; border:1px solid {W['border']} !important;
    color:{W['text']} !important; border-radius:{W['radius']} !important; font-size:13px !important; }}

/* Progress bars */
[data-testid="stProgress"] > div        {{ background:{W['surface_hi']} !important;
    height:3px !important; border-radius:1px !important; }}
[data-testid="stProgress"] > div > div,
[role="progressbar"] > div              {{ background:{W['green']} !important; }}

/* Alerts */
[role="alert"] {{ border-radius:{W['radius']} !important; font-size:12px !important; }}

/* Tabs */
[data-testid="stTabs"] [role="tab"] {{ color:{W['subtext']} !important; font-size:12px !important; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{ color:{W['text']} !important; }}

/* ══ OURA  /  MOBILE  (≤ 768 px) ═════════════════════════════════════════════ */

@media (max-width: 768px) {{
    .whoop-only {{ display:none;  }}
    .oura-only  {{ display:block; }}

    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"]  {{ background:{O['bg']} !important; }}
    [data-testid="stSidebar"] {{ background:{O['surface']} !important;
                                 border-right:none !important; }}
    .main .block-container    {{ padding:0.875rem 0.875rem 4rem !important; }}

    h1 {{ color:{O['text']} !important; font-size:26px !important;
          font-weight:300 !important; letter-spacing:-0.02em !important; }}
    h2 {{ color:{O['text']} !important; font-size:18px !important;
          font-weight:400 !important; text-transform:none !important; letter-spacing:0 !important; }}
    h3 {{ color:{O['subtext']} !important; font-size:14px !important;
          font-weight:500 !important; text-transform:none !important; letter-spacing:0 !important; }}

    p, .stMarkdown p, li {{ color:{O['text']} !important;
        font-size:15px !important; line-height:1.65 !important; }}
    .stCaption,
    [data-testid="stCaptionContainer"] p {{ color:{O['subtext']} !important; font-size:12px !important; }}
    hr {{ border-color:{O['border']} !important; margin:18px 0 !important; }}

    /* Metrics — larger, rounded; covers stMetric (1.36+) and metric-container (legacy) */
    [data-testid="stMetric"],
    [data-testid="metric-container"] {{ background:{O['surface']} !important;
        border:none !important; border-radius:{O['radius']} !important;
        padding:20px !important; box-shadow:0 2px 14px rgba(0,0,0,0.3) !important; }}
    [data-testid="stMetricValue"]    {{ color:{O['text']} !important;
        font-size:30px !important; font-weight:300 !important; font-family:system-ui !important; }}
    [data-testid="stMetricLabel"]    {{ color:{O['subtext']} !important;
        font-size:12px !important; text-transform:none !important; letter-spacing:0 !important; }}

    /* Buttons — large touch targets; covers both old and new testid names */
    [data-testid="stBaseButton-secondary"],
    [data-testid="baseButton-secondary"] {{ background:{O['surface_hi']} !important;
        color:{O['text']} !important; border:none !important; border-radius:14px !important;
        font-size:15px !important; padding:14px !important; }}
    [data-testid="stBaseButton-primary"],
    [data-testid="baseButton-primary"]   {{ background:{O['green']} !important;
        color:{O['bg']} !important; border:none !important; border-radius:14px !important;
        font-size:15px !important; font-weight:600 !important; padding:14px !important; }}

    /* Expander / Form */
    [data-testid="stExpander"] {{ background:{O['surface']} !important;
        border:none !important; border-radius:{O['radius']} !important;
        box-shadow:0 2px 12px rgba(0,0,0,0.25) !important; margin-bottom:10px !important; }}
    [data-testid="stForm"]     {{ background:{O['surface']} !important;
        border:none !important; border-radius:{O['radius']} !important;
        box-shadow:0 2px 12px rgba(0,0,0,0.25) !important; padding:16px !important; }}

    /* Inputs */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {{
        background:{O['surface_hi']} !important; border:none !important;
        color:{O['text']} !important; border-radius:12px !important;
        font-size:15px !important; padding:12px !important; }}

    /* Progress bars — thicker, rounded */
    [data-testid="stProgress"] > div        {{ background:{O['surface_hi']} !important;
        height:7px !important; border-radius:4px !important; }}
    [data-testid="stProgress"] > div > div,
    [role="progressbar"] > div              {{ background:{O['green']} !important;
        border-radius:4px !important; }}

    [role="alert"] {{ border-radius:{O['radius']} !important; font-size:14px !important; }}

    [data-testid="stTabs"] [role="tab"] {{ font-size:14px !important; padding:10px !important; }}
}}

/* ══ CHART AXES + CLICKABLE POINTS ═══════════════════════════════════════════
   Used by the Home drill-down charts (chart_frame / chart_hits / chart_points).
   Classes rather than inline styles because :hover cannot be expressed inline,
   and hover is what makes a tappable band discoverable on desktop — on a phone
   the band is found by tapping it, which is why the hit target is a full-height
   column and not just the dot. Outside any media query on purpose: the Home
   screen renders in the Oura mobile language at every width. */
.hp-hit {{ position:absolute; top:0; bottom:0; display:block;
           text-decoration:none; border-radius:3px;
           -webkit-tap-highlight-color:transparent; }}
.hp-hit:hover {{ background:rgba(255,255,255,0.07); }}
.hp-hit.hp-on {{ background:rgba(255,255,255,0.10);
                 box-shadow:inset 0 0 0 1px rgba(255,255,255,0.22); }}
.hp-dot {{ position:absolute; width:6px; height:6px; border-radius:50%;
           transform:translate(-50%,-50%); pointer-events:none; }}
.hp-dot.hp-on {{ width:11px; height:11px;
                 box-shadow:0 0 0 2px rgba(11,15,30,0.95); }}
</style>"""


# ─── Chart axes and clickable points (2026-08-03) ───────────────────────────
#  The rendering half of services/dashboard.py's axis section — see the long
#  note there for why the Home drill-down charts needed axes at all.
#
#  Every plot here is drawn into a viewBox of `0 0 100 height` with
#  preserveAspectRatio="none", i.e. horizontally stretched to whatever width
#  the panel happens to be. That is deliberate (it is what lets the hypnogram
#  and the movement strip share one time axis without either knowing the
#  other's length) and it has one consequence that shapes this whole section:
#  ANY text or circle inside such an SVG is stretched with it. So no label and
#  no point marker is ever drawn in the SVG. Axis text lives in positioned HTML
#  gutters, and point markers in an HTML overlay — which is also what makes
#  them clickable, since a plain <a> is already proven to work inside
#  st.markdown on this page while SVG-namespaced links are not.

AXIS_RULE = "#23304D"
AXIS_TEXT = "#5A6785"
GRID_LINE = "rgba(255,255,255,0.055)"

#  Vertical breathing room inside a value plot, in the same units as `height`.
#  Shared by the plot builders and by axis_gutter_labels so a gridline, its
#  label and the point it explains all land on the same pixel — a Y axis whose
#  labels are a few pixels off its own gridlines is worse than none.
PLOT_PAD = 5


def axis_gutter_labels(axis: dict | None, height: int,
                       pad: int = PLOT_PAD) -> list[tuple[float, str]]:
    """dashboard.value_axis_labels' VALUE-space fractions → CONTAINER-space
    fractions of `height`, i.e. where the tick actually sits on screen once
    the plot's padding is accounted for."""
    if not axis or height <= 0:
        return []
    inner = (height - 2 * pad) / height
    return [(pad / height + frac * inner, text)
            for frac, text in _dash.value_axis_labels(axis)]


def _y_gutter(labels, height: int, width: int) -> str:
    if not labels:
        return f'<div style="width:{width}px;height:{height}px;flex:none;"></div>'
    spans = "".join(
        f'<span style="position:absolute;right:6px;top:{frac * 100:.3f}%;'
        f'transform:translateY(-50%);font-size:9px;line-height:1;'
        f'color:{AXIS_TEXT};white-space:nowrap;">{text}</span>'
        for frac, text in labels
    )
    return (f'<div style="position:relative;width:{width}px;height:{height}px;'
            f'flex:none;">{spans}</div>')


def _x_axis_row(labels, height: int = 13) -> str:
    """The tick row under the plot. First and last labels are anchored to the
    edges instead of centred on their tick, because a centred label at
    fraction 0 hangs half its width off the left of the chart and gets clipped
    at phone width — the one place an axis label is guaranteed to be read."""
    if not labels:
        return ""
    parts = []
    for frac, text in labels:
        if frac <= 0.001:
            pos = "left:0;"
        elif frac >= 0.999:
            pos = "right:0;"
        else:
            pos = f"left:{frac * 100:.3f}%;transform:translateX(-50%);"
        parts.append(
            f'<span style="position:absolute;top:0;{pos}font-size:9px;'
            f'line-height:1.2;color:{AXIS_TEXT};white-space:nowrap;">{text}</span>'
        )
    return (f'<div style="position:relative;height:{height}px;margin-top:5px;">'
            f'{"".join(parts)}</div>')


_RULE_LEFT = (f'<i style="position:absolute;left:0;top:0;bottom:0;width:1px;'
              f'background:{AXIS_RULE};pointer-events:none;"></i>')
_RULE_BOTTOM = (f'<i style="position:absolute;left:0;right:0;bottom:0;height:1px;'
                f'background:{AXIS_RULE};pointer-events:none;"></i>')


def chart_frame(plots: list[dict], *, x_labels=(), gutter_px: int = 40) -> str:
    """One or more stacked plots wrapped in a shared Y gutter and X axis.

    `plots` is a list of {"svg", "height", "y_labels", "overlay", "gap"}. It
    is a LIST rather than a single plot because the Sleep screen stacks the
    hypnogram over the movement strip on one time axis, and giving each its
    own axis row would state twice, at slightly different pixel positions,
    that they cover the same night. The gutter column mirrors the plot
    column's spacers exactly, which is what keeps a Y label beside the plot
    it belongs to.

    The axis rules are absolutely-positioned 1px children, not CSS borders:
    a border participates in layout, and under `box-sizing:border-box` it
    would silently eat a pixel of the plot it is meant to be framing —
    enough to walk the gridlines off their labels.
    """
    gutter, column = [], []
    for i, plot in enumerate(plots):
        height, gap = int(plot["height"]), int(plot.get("gap") or 0)
        if gap:
            spacer = f'<div style="height:{gap}px;"></div>'
            gutter.append(spacer)
            column.append(spacer)
        gutter.append(_y_gutter(plot.get("y_labels") or (), height, gutter_px))
        rules = _RULE_LEFT + (_RULE_BOTTOM if i == len(plots) - 1 else "")
        column.append(
            f'<div style="position:relative;height:{height}px;">'
            f'{plot["svg"]}{rules}{plot.get("overlay") or ""}</div>'
        )
    return (f'<div style="display:flex;align-items:flex-start;">'
            f'<div style="flex:none;">{"".join(gutter)}</div>'
            f'<div style="flex:1;min-width:0;">{"".join(column)}'
            f'{_x_axis_row(x_labels)}</div></div>')


def chart_hits(items: list[dict]) -> str:
    """The clickable band overlay: one <a> per tappable slice of a chart.

    Each item is {"left", "width"} as fractions, plus "href", "title" and
    "selected". `title` becomes the native browser tooltip, so a desktop
    hover reads the point without a round trip while a tap still opens the
    full detail — the app is mobile-first and hover does not exist there.
    """
    parts = []
    for it in items:
        cls = "hp-hit hp-on" if it.get("selected") else "hp-hit"
        title = str(it.get("title") or "")
        parts.append(
            f'<a class="{cls}" href="{it["href"]}" title="{title}" '
            f'style="left:{max(0.0, float(it["left"])) * 100:.3f}%;'
            f'width:{max(0.0, float(it["width"])) * 100:.3f}%;"></a>'
        )
    return "".join(parts)


def chart_points(points: list[dict]) -> str:
    """The point markers, in their own pointer-events:none layer above the
    hit bands.

    Separate from chart_hits because a marker sits at its value's exact x
    while a hit band is a uniform slice — putting the dot inside the <a>
    would peg it to the band centre and walk every point a few pixels off
    the line it belongs to.
    """
    if not points:
        return ""
    dots = "".join(
        f'<i class="hp-dot{" hp-on" if p.get("selected") else ""}" '
        f'style="left:{float(p["x"]) * 100:.3f}%;top:{float(p["y"]) * 100:.3f}%;'
        f'background:{p.get("colour", OURA["green"])};"></i>'
        for p in points
    )
    return (f'<div style="position:absolute;inset:0;pointer-events:none;">'
            f'{dots}</div>')


# ─── Same-tab navigation for chart links ────────────────────────────────────
#  Streamlit's markdown renderer rewrites EVERY <a> it emits to
#  target="_blank" rel="noopener noreferrer" — verified in the running app, not
#  assumed. For the three Home cards that is merely untidy (one extra tab, once
#  per session). For a chart with 48 tappable bands it makes the feature
#  unusable: inspecting five points would leave five orphaned tabs, each having
#  paid a full cold app start.
#
#  There is no Streamlit-level opt-out, and st.markdown strips <script>, so the
#  only route is a components iframe — which is same-origin and can therefore
#  reach window.parent.
#
#  It removes the injected target attribute rather than intercepting the click
#  and assigning parent.location. That was the first attempt and it does not
#  work: Streamlit's component iframe is sandboxed WITHOUT allow-top-navigation,
#  so a top-level navigation initiated by script inside it is silently dropped —
#  the click was swallowed and nothing happened, which is worse than the extra
#  tab. Stripping the attribute leaves the navigation to the parent document's
#  own default click handling, which is not sandboxed and simply works.
#
#  The MutationObserver is required, not defensive: Streamlit re-renders the
#  markdown block on every rerun and re-adds target each time. Patching is
#  self-terminating — the selector matches only anchors that still HAVE a
#  target, so the observer's own edits cannot retrigger it into a loop. Matches
#  ONLY this feature's two classes; every other link in the app keeps whatever
#  behaviour it already had.
_CHART_LINK_JS = """
<script>
(function () {
  try {
    var p = window.parent;
    if (!p || !p.document || p.__healthChartNav) { return; }
    p.__healthChartNav = true;
    var patch = function () {
      var links = p.document.querySelectorAll(
        'a.hp-hit[target], a.hp-link[target]');
      for (var i = 0; i < links.length; i++) {
        links[i].removeAttribute('target');
      }
    };
    patch();
    new p.MutationObserver(patch).observe(p.document.body, {
      childList: true, subtree: true,
      attributes: true, attributeFilter: ['target']
    });
  } catch (err) { /* cross-origin or no parent: links keep opening a tab */ }
})();
</script>
"""


def enable_chart_links() -> None:
    """Make chart point links navigate in place. Call once per page that
    renders chart_hits() output or an hp-link anchor.

    These stay real anchors, so a chart-point tap RELOADS the page — the one
    place in the app that still does (CLAUDE.md Key Rule 17,
    tests/test_spa_navigation.py's _KNOWN). That is not for want of trying.

    ⚠ DO NOT RE-ATTEMPT THE JS BRIDGE. Shipped 2026-08-10 as 77c6984 and
    reverted the same day. The shape was: emit data-nav spans instead of
    anchors, intercept the click, rewrite the query string with
    history.replaceState, then click a hidden button to force a rerun. The
    Python side genuinely supports it — app_session.py feeds
    ClientState.query_string straight into RerunData — but the BROWSER decides
    what goes into that field, and the shipped frontend's getQueryString is

        state.queryParams || document.location.search

    i.e. the live URL is read ONLY when Streamlit's own cached copy is empty,
    and that cache is written solely by PYTHON assigning st.query_params.
    app.py's router assigns `page` on every single run, so in the real app the
    cache is never empty and replaceState is ignored outright.

    The failure is silent and looks like success from every angle that is
    cheap to check: the URL updates, the page does not reload, no error
    appears — and Python keeps reading the OLD selection, so the marker never
    moves. It was verified "working" in a probe whose app never assigned
    st.query_params, which is exactly the condition that cannot hold here.
    Measure any replacement against a page that ALREADY has a query param.

    Also tried and rejected: dispatching popstate after replaceState (the
    frontend's only history listener is popstate -> onHistoryChange, which
    does not refresh state.queryParams), pushState + popstate, and driving a
    hidden text_input through React's native value setter. None reached Python.

    A real fix means changing how these charts render — a chart component with
    genuine selection events — not intercepting clicks on hand-built SVG.
    """
    import streamlit.components.v1 as _components
    _components.html(_CHART_LINK_JS, height=0)


def _grid_svg(gridlines, height: int) -> str:
    """Horizontal gridlines at container-space fractions of `height`."""
    return "".join(
        f'<line x1="0" y1="{frac * height:.2f}" x2="100" y2="{frac * height:.2f}" '
        f'stroke="{GRID_LINE}" stroke-width="1" vector-effect="non-scaling-stroke" />'
        for frac in gridlines
    )


def trend_chart_svg(values: list, *, height: int = 92, colour: str = "#6BAF8B",
                    lo: float | None = None, hi: float | None = None,
                    gridlines=()) -> str:
    """A dated trend as a filled line, drawn against an EXPLICIT [lo, hi].

    Replaces app.py's fixed-width `_sparkline`. Two differences beyond the
    axis: it is full-width (the old 290px was ~2/3 of the panel it sat in,
    which cramped 30 points into a smear), and it takes its bounds from the
    caller instead of the data's own min/max — the bounds have to be the
    ROUNDED ones the axis is labelled with, or every gridline lands somewhere
    other than the value printed beside it.

    Gaps are drawn THROUGH rather than broken, unlike overnight_chart_svg. A
    missing day in a 30-day score history is a day the ring was not worn, and
    the trend either side of it is genuinely continuous; a missing sample
    mid-night is not.
    """
    clean = [(i, float(v)) for i, v in enumerate(values)
             if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if len(clean) < 2:
        return ""
    n = len(values)
    if lo is None or hi is None or hi <= lo:
        lo = min(v for _, v in clean)
        hi = max(v for _, v in clean)
        if hi == lo:
            hi = lo + 1
    span = float(hi) - float(lo)

    def xy(i, v):
        x = i / (n - 1) * 100 if n > 1 else 0.0
        y = PLOT_PAD + (1 - (v - lo) / span) * (height - 2 * PLOT_PAD)
        return x, y

    pts = [xy(i, v) for i, v in clean]
    d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    area = d + f" L{pts[-1][0]:.2f},{height} L{pts[0][0]:.2f},{height} Z"
    return (
        f'<svg viewBox="0 0 100 {height}" preserveAspectRatio="none" role="img" '
        f'aria-label="Trend" style="width:100%;height:{height}px;display:block;">'
        f'{_grid_svg(gridlines, height)}'
        f'<path d="{area}" fill="{colour}" fill-opacity="0.12" />'
        f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.6" '
        f'stroke-linejoin="round" stroke-linecap="round" '
        f'vector-effect="non-scaling-stroke" />'
        f'</svg>'
    )


def plot_y_fraction(value, lo, hi, height: int = 0, pad: int = PLOT_PAD) -> float:
    """Where a value sits vertically inside a padded plot, as a fraction of
    the container. The inverse of axis_gutter_labels, and the reason a point
    marker lands on its own gridline."""
    span = (float(hi) - float(lo)) or 1.0
    if height <= 0:
        return max(0.0, min(1.0, 1 - (float(value) - float(lo)) / span))
    inner = (height - 2 * pad) / height
    return pad / height + (1 - (float(value) - float(lo)) / span) * inner


# ─── Sleep-stage rendering (2026-07-31) ─────────────────────────────────────
#  Moved here from views/insights.py now that app.py's Sleep drill-down needs
#  it too. This file is already the home for HTML string builders
#  (oura_ring/oura_card/whoop_stat) and already owns the palettes.
#
#  Colours: blues for the three sleep stages, cream for awake. The earlier
#  palette used coral for awake, which made ordinary wakefulness rhyme with
#  the coral this app spends on "pay attention" and a HIGH sleep-debt band —
#  reading a normal part of every night as a fault. Cream separates "awake"
#  from "problem".

STAGE_BAND: dict[str, tuple[str, str]] = {
    "1": ("#1E4D7B", "Deep"),
    "2": ("#3C8FD4", "Light"),
    "3": ("#8FCDF0", "REM"),
    "4": ("#EFE9DD", "Awake"),
    "0": ("#2A2E37", "No data"),
}
# Awake on top descending to deep — the vertical order a clinical hypnogram
# uses, so the shape reads the way a sleep chart is expected to.
STAGE_ROW: dict[str, int] = {"4": 0, "3": 1, "2": 2, "1": 3}


def hypnogram_svg(codes: str, height: int = 52, *, rows: bool = False,
                  highlight: tuple[int, int] | None = None) -> str:
    """One night's stage sequence as a stacked band chart.

    `codes` is the digit-per-interval string Oura and services/sleep_fusion.py
    both use (1=deep 2=light 3=REM 4=awake). Consecutive identical intervals
    are merged into one rect, so a 500-minute night renders as a few dozen
    elements rather than 500.

    `rows` draws the three row separators, turning the four implicit stage
    lanes into a labelled categorical Y axis (see hypnogram_row_labels).
    `highlight` outlines one (start, end-exclusive) run — the segment a click
    selected. Both default off so views/insights.py's call is unchanged.
    """
    if not codes:
        return ""
    n = len(codes)
    row_h = height / 4
    parts = []
    for i, j, code in _dash.merge_runs(codes):
        colour, _ = STAGE_BAND.get(code, STAGE_BAND["0"])
        row = STAGE_ROW.get(code)
        if row is not None:
            parts.append(
                f'<rect x="{i / n * 100:.3f}%" y="{row * row_h:.1f}" '
                f'width="{(j - i) / n * 100:.3f}%" height="{row_h:.1f}" fill="{colour}" />'
            )
    if rows:
        parts.append(_grid_svg([0.25, 0.5, 0.75], height))
    if highlight:
        s, e = highlight
        # A 30-second run is a hair over 0.1% of the night, far too narrow to
        # read as an outline alone, so the selection is also washed lighter.
        parts.append(
            f'<rect x="{s / n * 100:.3f}%" y="0" width="{(e - s) / n * 100:.3f}%" '
            f'height="{height}" fill="#FFFFFF" fill-opacity="0.16" />'
            f'<rect x="{s / n * 100:.3f}%" y="0.75" width="{(e - s) / n * 100:.3f}%" '
            f'height="{height - 1.5}" fill="none" stroke="#FFFFFF" stroke-opacity="0.8" '
            f'stroke-width="1.5" vector-effect="non-scaling-stroke" />'
        )
    return (f'<svg viewBox="0 0 100 {height}" preserveAspectRatio="none" role="img" '
            f'aria-label="Sleep stage timeline" '
            f'style="width:100%;height:{height}px;display:block;border-radius:4px;'
            f'background:#0E1220;">{"".join(parts)}</svg>')


def hypnogram_row_labels() -> list[tuple[float, str]]:
    """(fraction from top, stage name) centred in each of the four lanes —
    the hypnogram's Y axis. Derived from STAGE_ROW rather than hard-coded so
    the labels cannot end up describing a different vertical order than the
    one hypnogram_svg draws."""
    return [((row + 0.5) / 4, STAGE_BAND[code][1])
            for code, row in sorted(STAGE_ROW.items(), key=lambda kv: kv[1])]


def stage_legend_html() -> str:
    items = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;">'
        f'<span style="width:10px;height:10px;border-radius:2px;background:{c};'
        f'display:inline-block;"></span>'
        f'<span style="color:#9AA3B2;font-size:11px;">{label}</span></span>'
        for c, label in (STAGE_BAND[k] for k in ("1", "2", "3", "4"))
    )
    return f'<div style="margin:6px 0 10px 0;">{items}</div>'


# ─── Movement rendering ─────────────────────────────────────────────────────
#  Deliberately ONE hue at four opacities, not four colours. The hypnogram
#  above already spends the page's colour budget, and the two strips sit on a
#  shared time axis directly beneath one another — a second multi-colour band
#  would read as a competing categorical scale rather than as the intensity
#  scale movement actually is. Opacity encodes magnitude, which is what an
#  ordinal 1-4 class means.
MOVEMENT_HUE = "#8FCDF0"
MOVEMENT_LABELS: dict[str, str] = {
    "1": "No motion", "2": "Restless", "3": "Tossing", "4": "Active",
}
MOVEMENT_OPACITY: dict[str, float] = {"1": 0.16, "2": 0.42, "3": 0.72, "4": 1.0}


def movement_row_labels() -> list[tuple[float, str]]:
    """(fraction from top, class name) for the movement strip's Y axis.

    Only the two ENDS are labelled. The tick heights are 25/50/75/100% of a
    strip that is a couple of dozen pixels tall, so four 9px labels would
    overlap into an unreadable stack; the middle two classes are already
    named in movement_legend_html directly beneath. The end labels are what
    the strip actually lacked — without them an upward tick has no stated
    direction.

    Inset from the exact ends rather than pinned to 0 and 1: a label is
    centred on its position, so one at 0.0 hangs half its height above the
    strip and collides with the bottom row label of the hypnogram stacked
    directly over it."""
    return [(0.12, MOVEMENT_LABELS["4"]), (0.88, MOVEMENT_LABELS["1"])]


def movement_svg(codes: str, height: int = 26, *,
                 highlight: tuple[int, int] | None = None) -> str:
    """One night's fused movement as a tick strip, drawn to share the
    hypnogram's time axis exactly.

    `codes` is the digit-per-slot string from services/sleep_movement.py
    (1=still 2=restless 3=tossing 4=active), on the 30-SECOND grid — twice the
    hypnogram's resolution but anchored at the same window_start, so equal
    x-fractions are the same instant in both. Both are drawn full-width with
    the same percentage arithmetic, which is what keeps them aligned without
    either needing to know the other's length.

    Ticks grow upward from the baseline so the strip reads as intensity over
    time; uncovered slots render as nothing at all rather than as a zero-height
    tick, because "not measured" and "did not move" are different claims.
    """
    if not codes:
        return ""
    n = len(codes)
    parts = []
    for i, j, code in _dash.merge_runs(codes):
        opacity = MOVEMENT_OPACITY.get(code)
        if opacity is not None:
            tick_h = height * (0.25 + 0.75 * (int(code) - 1) / 3)
            parts.append(
                f'<rect x="{i / n * 100:.3f}%" y="{height - tick_h:.1f}" '
                f'width="{(j - i) / n * 100:.3f}%" height="{tick_h:.1f}" '
                f'fill="{MOVEMENT_HUE}" fill-opacity="{opacity}" />'
            )
    if highlight:
        s, e = highlight
        parts.append(
            f'<rect x="{s / n * 100:.3f}%" y="0.75" width="{(e - s) / n * 100:.3f}%" '
            f'height="{height - 1.5}" fill="#FFFFFF" fill-opacity="0.14" '
            f'stroke="#FFFFFF" stroke-opacity="0.8" stroke-width="1.5" '
            f'vector-effect="non-scaling-stroke" />'
        )
    return (f'<svg viewBox="0 0 100 {height}" preserveAspectRatio="none" role="img" '
            f'aria-label="Movement timeline" '
            f'style="width:100%;height:{height}px;display:block;border-radius:4px;'
            f'background:#0E1220;">{"".join(parts)}</svg>')


def overnight_chart_svg(values: list, height: int = 60, colour: str = "#8FCDF0",
                        baseline: float | None = None, *,
                        lo: float | None = None, hi: float | None = None,
                        gridlines=()) -> str:
    """An overnight HR or HRV series as a filled line chart.

    `values` is one number per sample with None for gaps — Oura pads the
    start of the night with nulls, so gaps are normal and must break the line
    rather than being drawn through as if measured. The path is emitted as
    separate segments per contiguous run for exactly that reason.

    Scaled to the night rather than to an absolute axis: the point of these
    charts is the SHAPE of the night (the descent into deep sleep, the REM
    excursions), and a fixed 0-based axis would flatten a calm night into a
    straight line. That was always the right call, but until this chart
    carried a labelled Y axis it also meant the vertical scale was unstated —
    a 4 ms HRV wobble and a 40 ms collapse drew identically. `lo`/`hi` now
    take the ROUNDED bounds the axis is labelled with (dashboard.value_axis),
    falling back to the data's own min/max when omitted so an unlabelled call
    still renders exactly as before.
    """
    nums = [v for v in values if isinstance(v, (int, float))]
    if len(nums) < 2:
        return ""
    if lo is None or hi is None or hi <= lo:
        lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1.0
    n = len(values)
    pad = PLOT_PAD

    def xy(i, v):
        x = i / (n - 1) * 100 if n > 1 else 0
        y = pad + (1 - (v - lo) / span) * (height - 2 * pad)
        return x, y

    segments, run = [], []
    for i, v in enumerate(values):
        if isinstance(v, (int, float)):
            run.append(xy(i, v))
        elif run:
            segments.append(run); run = []
    if run:
        segments.append(run)

    parts = []
    for seg in segments:
        if len(seg) < 2:
            continue
        d = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in seg)
        area = (d + f" L{seg[-1][0]:.2f},{height} L{seg[0][0]:.2f},{height} Z")
        parts.append(f'<path d="{area}" fill="{colour}" fill-opacity="0.13" />')
        parts.append(f'<path d="{d}" fill="none" stroke="{colour}" '
                     f'stroke-width="1.6" stroke-linejoin="round" '
                     f'stroke-linecap="round" vector-effect="non-scaling-stroke" />')

    if baseline is not None and lo <= baseline <= hi:
        # Drawn FIRST so the series sits on top of it, and dashed so it reads
        # as a reference rather than a second measured series.
        _, by = xy(0, baseline)
        parts.insert(0, f'<line x1="0" y1="{by:.2f}" x2="100" y2="{by:.2f}" '
                        f'stroke="#3A4356" stroke-width="1" stroke-dasharray="3 3" '
                        f'vector-effect="non-scaling-stroke" />')
    # Gridlines go under everything, including the baseline: the baseline is a
    # measured figure and must stay the most legible horizontal on the chart.
    if gridlines:
        parts.insert(0, _grid_svg(gridlines, height))

    return (f'<svg viewBox="0 0 100 {height}" preserveAspectRatio="none" role="img" '
            f'aria-label="Overnight trend" '
            f'style="width:100%;height:{height}px;display:block;">{"".join(parts)}</svg>')


def movement_legend_html() -> str:
    items = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;">'
        f'<span style="width:10px;height:10px;border-radius:2px;background:{MOVEMENT_HUE};'
        f'opacity:{MOVEMENT_OPACITY[k]};display:inline-block;"></span>'
        f'<span style="color:#9AA3B2;font-size:11px;">{MOVEMENT_LABELS[k]}</span></span>'
        for k in ("1", "2", "3", "4")
    )
    return f'<div style="margin:6px 0 10px 0;">{items}</div>'
