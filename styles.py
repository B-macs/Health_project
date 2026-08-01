"""
styles.py — Responsive dual-theme.
Oura aesthetic (mobile ≤768px) · Whoop aesthetic (desktop ≥769px).
"""

import math
import streamlit as st

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
</style>"""


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


def hypnogram_svg(codes: str, height: int = 52) -> str:
    """One night's stage sequence as a stacked band chart.

    `codes` is the digit-per-interval string Oura and services/sleep_fusion.py
    both use (1=deep 2=light 3=REM 4=awake). Consecutive identical intervals
    are merged into one rect, so a 500-minute night renders as a few dozen
    elements rather than 500."""
    if not codes:
        return ""
    n = len(codes)
    row_h = height / 4
    parts, i = [], 0
    while i < n:
        j = i
        while j < n and codes[j] == codes[i]:
            j += 1
        colour, _ = STAGE_BAND.get(codes[i], STAGE_BAND["0"])
        row = STAGE_ROW.get(codes[i])
        if row is not None:
            parts.append(
                f'<rect x="{i / n * 100:.3f}%" y="{row * row_h:.1f}" '
                f'width="{(j - i) / n * 100:.3f}%" height="{row_h:.1f}" fill="{colour}" />'
            )
        i = j
    return (f'<svg viewBox="0 0 100 {height}" preserveAspectRatio="none" role="img" '
            f'aria-label="Sleep stage timeline" '
            f'style="width:100%;height:{height}px;display:block;border-radius:4px;'
            f'background:#0E1220;">{"".join(parts)}</svg>')


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


def movement_svg(codes: str, height: int = 26) -> str:
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
    parts, i = [], 0
    while i < n:
        j = i
        while j < n and codes[j] == codes[i]:
            j += 1
        opacity = MOVEMENT_OPACITY.get(codes[i])
        if opacity is not None:
            tick_h = height * (0.25 + 0.75 * (int(codes[i]) - 1) / 3)
            parts.append(
                f'<rect x="{i / n * 100:.3f}%" y="{height - tick_h:.1f}" '
                f'width="{(j - i) / n * 100:.3f}%" height="{tick_h:.1f}" '
                f'fill="{MOVEMENT_HUE}" fill-opacity="{opacity}" />'
            )
        i = j
    return (f'<svg viewBox="0 0 100 {height}" preserveAspectRatio="none" role="img" '
            f'aria-label="Movement timeline" '
            f'style="width:100%;height:{height}px;display:block;border-radius:4px;'
            f'background:#0E1220;">{"".join(parts)}</svg>')


def overnight_chart_svg(values: list, height: int = 60, colour: str = "#8FCDF0",
                        baseline: float | None = None) -> str:
    """An overnight HR or HRV series as a filled line chart.

    `values` is one number per sample with None for gaps — Oura pads the
    start of the night with nulls, so gaps are normal and must break the line
    rather than being drawn through as if measured. The path is emitted as
    separate segments per contiguous run for exactly that reason.

    Scaled to the night's own min/max rather than an absolute axis: the point
    of these charts is the SHAPE of the night (the descent into deep sleep,
    the REM excursions), and a fixed axis would flatten a calm night into a
    straight line. The absolute numbers are stated beside the chart, so
    nothing is lost by relativising the plot.
    """
    nums = [v for v in values if isinstance(v, (int, float))]
    if len(nums) < 2:
        return ""
    lo, hi = min(nums), max(nums)
    span = (hi - lo) or 1.0
    n = len(values)
    pad = 4

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
                        f'stroke="#3A4356" stroke-width="1" stroke-dasharray="3 3" />')

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
