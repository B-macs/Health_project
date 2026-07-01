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
