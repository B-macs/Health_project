"""
Home — Daily dashboard. Readiness · Strain · Sleep.
Entry point: streamlit run app.py

Mobile-first, Oura visual language. Full-bleed photographic cards, semi-circular
arc gauges, sticky header + bottom nav, FAB to Morning Check-In.

Deterministic background mapping (same image always for same card type):
  Readiness  → background_templates/mountain.jpg
  Strain     → background_templates/wp13002291.jpg
  Sleep      → background_templates/Calm-iphone-11.jpg
"""

from __future__ import annotations

import base64
import math
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

import db
import engine
import nav
import readiness as readiness_model
import styles
import sync_sheets

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Home",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject sidebar-suppression CSS IMMEDIATELY — before any data fetching —
# so the sidebar never becomes visible during load.
st.markdown(nav.CHROME_CSS, unsafe_allow_html=True)

# ─── SPA Router ───────────────────────────────────────────────────────────────
# Navigation uses st.session_state (set by nav.inject's on_click buttons) so
# the WebSocket stays alive across transitions — no reconnect, no flash.
# URL query params ("?page=X") are honoured as a fallback for direct links.
_page = st.session_state.get("_nav_page",
         st.query_params.get("page", "home"))

if _page == "training":
    from views import training as _v
    styles.inject_css(); nav.inject("training"); _v.render(); st.stop()
elif _page == "insights":
    from views import insights as _v
    styles.inject_css(); nav.inject("insights"); _v.render(); st.stop()
elif _page == "sync":
    from views import sync as _v
    styles.inject_css(); nav.inject("sync"); _v.render(); st.stop()
elif _page == "checkin":
    from views import checkin as _v
    styles.inject_css(); nav.inject(""); _v.render(); st.stop()

# ─── Constants ────────────────────────────────────────────────────────────────

_BG_DIR = Path(__file__).parent / "background_templates"

# Deterministic card → background image (fixed mapping, never changes between sessions)
_CARD_BG: dict[str, Path] = {
    "readiness": _BG_DIR / "mountain.jpg",
    "strain":    _BG_DIR / "wp13002291.jpg",
    "sleep":     _BG_DIR / "Calm-iphone-11.jpg",
}

_SLEEP_NEED_HOURS = 8.0
_NOT_COMPUTED     = readiness_model.NOT_COMPUTED

# ─── URL state ───────────────────────────────────────────────────────────────

_today = date.today()
_params = st.query_params

try:
    selected_date = date.fromisoformat(_params.get("d", str(_today)))
except ValueError:
    selected_date = _today

view        = _params.get("view", "home")
is_today    = (selected_date == _today)
date_label  = "TODAY" if is_today else selected_date.isoformat()
prev_date   = selected_date - timedelta(days=1)
next_date   = selected_date + timedelta(days=1)
can_go_next = next_date <= _today

# ─── Data fetching ────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _bio_rolling(sheet_id: str, days: int = 32) -> list[dict]:
    return sync_sheets.get_biometric_rolling(sheet_id, days=days)


@st.cache_data(ttl=1800, show_spinner=False)
def _au_history(days: int = 28) -> list[dict]:
    return db.get_daily_session_au(days)


try:
    _sheet_id = st.secrets["GOOGLE_SHEETS_ID"]
    _bio_rows = _bio_rolling(_sheet_id, days=60)   # 60d to support 56d sleep baseline
except Exception:
    _bio_rows = []

_au_rows = []
try:
    _au_rows = _au_history()
except Exception:
    pass

try:
    _current_stage = db.get_current_stage()
except Exception:
    _current_stage = 1

_bio_day = next((r for r in _bio_rows if r.get("date") == selected_date.isoformat()), None)
_au_day  = next((r for r in _au_rows  if r.get("date") == selected_date.isoformat()), None)

_window_start = (selected_date - timedelta(days=6)).isoformat()
_window_end   = selected_date.isoformat()
_bio_7d = sorted(
    [r for r in _bio_rows if r.get("date") and _window_start <= r["date"] <= _window_end],
    key=lambda r: r["date"],
)

# ─── Domain helpers ───────────────────────────────────────────────────────────

def _au_to_strain(au: float | None) -> float | None:
    if au is None or au <= 0:
        return None
    return engine.au_to_strain(au, _current_stage)


def _fill_7day(rows: list[dict], key: str) -> list:
    by_date = {r["date"]: r.get(key) for r in rows}
    return [by_date.get((selected_date - timedelta(days=6 - i)).isoformat()) for i in range(7)]


# ─── Computed values ──────────────────────────────────────────────────────────

_readiness_score = readiness_model.compute_readiness(selected_date, _bio_rows)
_strain_score    = _au_to_strain(_au_day["total_au"] if _au_day else None)
_sleep_hours     = _bio_day.get("sleep_duration_hours") if _bio_day else None

# Progressive sleep baseline (7→14→28→56 nights, outliers <4h/>11h removed)
_sleep_base_hours, _sleep_base_window = readiness_model.sleep_baseline(_bio_rows)
_sleep_need = _sleep_base_hours if _sleep_base_hours else _SLEEP_NEED_HOURS
_sleep_pct  = round(_sleep_hours / _sleep_need * 100) if _sleep_hours else None

_hrv_7d = _fill_7day(_bio_7d, "hrv_ms")
_rhr_7d = _fill_7day(_bio_7d, "resting_heart_rate")

# ─── Image loading ────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _b64(path_str: str) -> str:
    p = Path(path_str)
    if not p.exists():
        return ""
    mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


_bg = {k: _b64(str(v)) for k, v in _CARD_BG.items()}

# ─── SVG: arc gauge ──────────────────────────────────────────────────────────

def _arc_svg(score, max_score: float, fill_color: str, size: int = 220) -> str:
    """
    270° arc gauge — gap at bottom (7:30 → 4:30 o'clock via top).
    score = None or NOT_COMPUTED → grey empty arc (exception state).
    """
    cx = cy = size // 2
    r  = size // 2 - 22
    sw = 11
    C  = 2 * math.pi * r
    arc_len = 0.75 * C
    arc_gap = C - arc_len

    empty    = score is None or score == _NOT_COMPUTED
    fill_len = 0.0 if empty else 0.75 * C * min(1.0, max(0.0, float(score) / max_score))
    fill_gap = C - fill_len
    t_col    = "rgba(255,255,255,0.12)"
    f_col    = "rgba(255,255,255,0.15)" if empty else fill_color

    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t_col}" stroke-width="{sw}"'
        f' stroke-dasharray="{arc_len:.1f} {arc_gap:.1f}" stroke-linecap="round"'
        f' transform="rotate(135 {cx} {cy})"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{f_col}" stroke-width="{sw}"'
        f' stroke-dasharray="{fill_len:.1f} {fill_gap:.1f}" stroke-linecap="round"'
        f' transform="rotate(135 {cx} {cy})"/>'
        f'</svg>'
    )


# ─── SVG: sparkline ──────────────────────────────────────────────────────────

def _sparkline(values: list, width: int = 290, height: int = 68,
               color: str = "#6BAF8B") -> str:
    clean = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(clean) < 2:
        return (
            f'<div style="height:{height}px;display:flex;align-items:center;'
            f'justify-content:center;">'
            f'<span style="color:#444;font-size:12px;font-style:italic;">'
            f'No historical readings available for this period.</span>'
            f'</div>'
        )
    n  = len(values)
    mn = min(v for _, v in clean)
    mx = max(v for _, v in clean)
    if mx == mn: mx = mn + 1
    pad, iw, ih = 10, width - 20, height - 20

    def _pt(i, v):
        return pad + i * iw / (n - 1), pad + (1 - (v - mn) / (mx - mn)) * ih

    pts  = [_pt(i, v) for i, v in clean]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>' for x, y in pts)
    lx, ly = pts[-1]
    return (
        f'<svg width="{width}" height="{height}" overflow="visible">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.5"'
        f' stroke-linejoin="round" stroke-linecap="round" opacity="0.9"/>'
        f'{dots}'
        f'<text x="{lx + 5:.1f}" y="{ly + 4:.1f}" fill="{color}" font-size="10"'
        f' font-family="system-ui">{clean[-1][1]:.0f}</text>'
        f'</svg>'
    )


# ─── Status classifiers ───────────────────────────────────────────────────────

def _readiness_meta(score) -> tuple:
    if score is None or score == _NOT_COMPUTED:
        return "#555555", "--", "No Readings", "Awaiting Data", \
               "The readiness model hasn't computed a score yet.", ""
    s = float(score)
    if s >= 85:   c, lbl, hdr = "#6BAF8B", "Optimal",       "Bring it on"
    elif s >= 70: c, lbl, hdr = "#BFA06A", "Good",           "Ready to train"
    elif s >= 50: c, lbl, hdr = "#BFA06A", "Pay Attention",  "Take it measured"
    else:         c, lbl, hdr = "#C47878", "Rest",           "Recover today"
    descs = {
        "Optimal":      "Your recovery metrics indicate full training capacity today.",
        "Good":         "Your body is recovered. A solid session is on the cards.",
        "Pay Attention":"Some recovery markers are below baseline. Train within yourself.",
        "Rest":         "Significant fatigue signals present. Prioritise rest and mobility.",
    }
    return c, str(int(s)), lbl, hdr, descs[lbl], ""


def _strain_meta(score) -> tuple:
    if score is None:
        return "#555555", "--", "No Readings", "No workload logged", \
               "No training data recorded for this day."
    s = float(score)
    if s < 6:    c, lbl = "#6BAF8B", "Light"
    elif s < 10: c, lbl = "#BFA06A", "Moderate"
    elif s < 14: c, lbl = "#C47878", "Hard"
    else:        c, lbl = "#C47878", "Strenuous"
    heads = {"Light": "Light day", "Moderate": "Building momentum",
             "Hard": "High output", "Strenuous": "Peak effort"}
    descs = {
        "Light":       "Minimal cardiovascular stress. Ideal for active recovery.",
        "Moderate":    "Solid aerobic work accumulating. Body is adapting.",
        "Hard":        "Significant load logged. Adequate recovery needed before next session.",
        "Strenuous":   "Max exertion. Full recovery required before your next training block.",
    }
    return c, f"{s:.1f}", lbl, heads[lbl], descs[lbl]


def _sleep_meta(pct) -> tuple:
    if pct is None:
        return "#555555", "--%", "No Readings", "Sleep data missing", \
               "No sleep data available for this day."
    p = float(pct)
    if p >= 85:   c, lbl = "#6BAF8B", "Optimal"
    elif p >= 70: c, lbl = "#BFA06A", "Good"
    elif p >= 50: c, lbl = "#BFA06A", "Pay Attention"
    else:         c, lbl = "#C47878", "Insufficient"
    heads = {"Optimal": "Well rested", "Good": "Adequate rest",
             "Pay Attention": "Sleep deficit", "Insufficient": "Significant deficit"}
    _base_label = (
        f"{_sleep_base_window}d avg ({_sleep_need:.1f} h)"
        if _sleep_base_hours else f"target ({_sleep_need:.0f} h)"
    )
    descs = {
        "Optimal":      f"Sleep met or exceeded your personal baseline — {_base_label}.",
        "Good":         f"You reached {p:.0f}% of your baseline {_base_label}. Recovery is solid.",
        "Pay Attention":f"Only {p:.0f}% of baseline {_base_label} met. Fatigue may accumulate.",
        "Insufficient": f"Sleep critically short ({p:.0f}% of baseline {_base_label}). Recovery impaired.",
    }
    return c, f"{p:.0f}%", lbl, heads[lbl], descs[lbl]


# ─── Card builder ────────────────────────────────────────────────────────────

def _card_html(
    label_text: str,
    bg_data_url: str,
    gauge_svg: str,
    score_display: str,
    status_label: str,
    status_color: str,
    header: str,
    description: str,
    tertiary: str = "",
    click_href: str = "",
    gauge_size: int = 220,
) -> str:
    scrim  = "linear-gradient(180deg,rgba(0,0,0,0.18) 0%,rgba(0,0,0,0.60) 50%,rgba(0,0,0,0.80) 100%)"
    bg_css = (
        f'background-image:url(\'{bg_data_url}\');background-size:cover;background-position:center;'
        if bg_data_url else "background:#1A2238;"
    )
    gauge_block = (
        f'<div style="position:relative;width:{gauge_size}px;height:{gauge_size}px;margin:0 auto;">'
        f'{gauge_svg}'
        f'<div style="position:absolute;top:42%;left:50%;transform:translate(-50%,-50%);'
        f'text-align:center;pointer-events:none;">'
        f'<div style="font-size:58px;font-weight:800;color:#fff;line-height:1;letter-spacing:-2px;">'
        f'{score_display}</div>'
        f'<div style="font-size:13px;font-weight:500;color:{status_color};margin-top:6px;">'
        f'{status_label}</div>'
        f'</div>'
        f'</div>'
    )
    tert = (
        f'<div style="font-size:12px;color:rgba(255,255,255,0.48);margin-top:5px;'
        f'letter-spacing:0.5px;font-family:monospace;">{tertiary}</div>'
    ) if tertiary else ""

    inner = (
        f'<div style="position:relative;width:100%;height:460px;overflow:hidden;margin-bottom:4px;">'
        f'<div style="position:absolute;inset:0;{bg_css}"></div>'
        f'<div style="position:absolute;inset:0;background:{scrim};"></div>'
        f'<div style="position:relative;z-index:1;height:100%;display:flex;'
        f'flex-direction:column;padding:20px 16px 22px;">'
        f'<div style="font-size:10px;color:rgba(255,255,255,0.48);letter-spacing:3px;'
        f'text-transform:uppercase;font-weight:600;">{label_text}</div>'
        f'<div style="flex:1;display:flex;align-items:center;justify-content:center;">'
        f'{gauge_block}'
        f'</div>'
        f'<div style="text-align:center;padding-bottom:4px;">'
        f'<div style="font-size:20px;font-weight:700;color:#fff;letter-spacing:-0.3px;">{header}</div>'
        f'<div style="font-size:13px;color:rgba(255,255,255,0.70);margin-top:6px;line-height:1.55;'
        f'max-width:300px;margin-left:auto;margin-right:auto;">{description}</div>'
        f'{tert}'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    if click_href:
        return f'<a href="{click_href}" style="display:block;text-decoration:none;">{inner}</a>'
    return inner


# ─── Strain drill-down ────────────────────────────────────────────────────────

def _strain_detail() -> str:
    def _trend_block(title: str, unit: str, values: list, color: str) -> str:
        has_data = any(v is not None for v in values)
        current  = next((v for v in reversed(values) if v is not None), None)
        val_str  = f"{current:.0f} {unit}" if current is not None else "—"

        day_labels = "".join(
            f'<span style="font-size:9px;color:#555;flex:1;text-align:center;">'
            f'{(selected_date - timedelta(days=6 - i)).strftime("%a")}</span>'
            for i in range(7)
        )
        chart_or_empty = (
            f'<div style="display:flex;justify-content:center;">'
            + (_sparkline(values, width=290, height=68, color=color) if has_data else
               f'<div style="width:290px;height:68px;display:flex;align-items:center;'
               f'justify-content:center;"><span style="color:#444;font-size:12px;'
               f'font-style:italic;">No historical readings available for this period.</span></div>')
            + f'</div>'
        )
        return (
            f'<div style="background:#131929;border-radius:12px;padding:16px 18px;margin-bottom:10px;">'
            f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;text-transform:uppercase;'
            f'font-weight:600;margin-bottom:4px;">{title}</div>'
            f'<div style="font-size:28px;font-weight:700;color:#D4DCEE;margin-bottom:12px;">{val_str}</div>'
            f'<div style="display:flex;width:290px;margin:0 auto 4px;">'
            f'{day_labels}</div>'
            f'{chart_or_empty}'
            f'</div>'
        )

    s_col, s_disp, s_lbl, _, _ = _strain_meta(_strain_score)
    return (
        f'<div style="padding:16px;">'
        f'<div style="display:flex;align-items:center;margin-bottom:20px;">'
        f'<a href="?d={selected_date}" style="color:#6B7A9B;font-size:22px;'
        f'text-decoration:none;margin-right:14px;line-height:1;">←</a>'
        f'<div>'
        f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;'
        f'text-transform:uppercase;margin-bottom:2px;">STRAIN · {date_label}</div>'
        f'<div style="font-size:30px;font-weight:800;color:{s_col};line-height:1;">{s_disp}</div>'
        f'<div style="font-size:12px;color:#6B7A9B;margin-top:2px;">{s_lbl}</div>'
        f'</div>'
        f'</div>'
        + _trend_block("Heart Rate Variability", "ms",  _hrv_7d, "#6BAF8B")
        + _trend_block("Resting Heart Rate",     "bpm", _rhr_7d, "#BFA06A")
        + f'</div>'
    )


# ─── Fixed UI elements ────────────────────────────────────────────────────────

_next_style = "color:#D4DCEE;" if can_go_next else "color:#2A2A3A;pointer-events:none;"
_next_href  = f"?d={next_date}" if can_go_next else "#"

if view == "strain":
    _header_inner = (
        f'<a href="?d={selected_date}" style="color:#6B7A9B;text-decoration:none;'
        f'font-size:22px;line-height:1;margin-right:14px;">←</a>'
        f'<span style="color:#D4DCEE;font-weight:600;font-size:15px;">Strain History</span>'
        f'<div style="width:36px;"></div>'
    )
    _header_justify = "flex-start"
else:
    _header_inner = (
        f'<a href="?d={prev_date}" style="color:#D4DCEE;text-decoration:none;'
        f'font-size:26px;line-height:1;padding:4px 6px;">‹</a>'
        f'<span style="color:#D4DCEE;font-weight:600;font-size:15px;letter-spacing:0.5px;">'
        f'{date_label}</span>'
        f'<a href="{_next_href}" style="{_next_style}text-decoration:none;'
        f'font-size:26px;line-height:1;padding:4px 6px;">›</a>'
    )
    _header_justify = "space-between"

_header_html = (
    '<div style="position:fixed;top:0;left:0;right:0;z-index:900;'
    'background:#0B0F1E;border-bottom:1px solid #1E2840;">'
    f'<div style="max-width:480px;margin:0 auto;height:56px;display:flex;'
    f'align-items:center;justify-content:{_header_justify};padding:0 20px;">'
    + _header_inner +
    '</div>'
    '</div>'
)

# FAB — Morning Check-In (stNav keeps WebSocket alive, no page reload)
_fab_html = (
    '<div onclick="stNav(\'checkin\')">'
    '<div style="position:fixed;bottom:80px;'
    'right:max(20px,calc((100vw - 480px)/2 + 16px));'
    'z-index:900;width:52px;height:52px;border-radius:50%;background:#FFFFFF;'
    'display:flex;align-items:center;justify-content:center;'
    'box-shadow:0 4px 20px rgba(0,0,0,0.45);cursor:pointer;">'
    '<span style="font-size:28px;color:#0B0F1E;line-height:1;font-weight:300;">+</span>'
    '</div>'
    '</div>'
)

# ─── Home-specific CSS (home-page-only overrides) ─────────────────────────────

_home_css = """<style>
/* Constrain card stream to mobile width, centred */
.main .block-container {
    padding: 60px 0 76px !important;
    max-width: 480px !important;
    margin: 0 auto !important;
}
.stApp, [data-testid="stAppViewContainer"] { background:#0B0F1E !important; }
</style>"""

# ─── Build cards ─────────────────────────────────────────────────────────────

r_col, r_disp, r_lbl, r_hdr, r_desc, r_tert = _readiness_meta(_readiness_score)
_card_readiness = _card_html(
    "READINESS", _bg["readiness"],
    _arc_svg(_readiness_score, 100, r_col),
    r_disp, r_lbl, r_col, r_hdr, r_desc, r_tert,
)

s_col, s_disp, s_lbl, s_hdr, s_desc = _strain_meta(_strain_score)
_card_strain = _card_html(
    "STRAIN", _bg["strain"],
    _arc_svg(_strain_score, 21, s_col),
    s_disp, s_lbl, s_col, s_hdr, s_desc,
    click_href=f"?d={selected_date}&view=strain",
)

sl_col, sl_disp, sl_lbl, sl_hdr, sl_desc = _sleep_meta(_sleep_pct)
_card_sleep = _card_html(
    "SLEEP", _bg["sleep"],
    _arc_svg(_sleep_pct, 100, sl_col),
    sl_disp, sl_lbl, sl_col, sl_hdr, sl_desc,
)

# ─── Render ───────────────────────────────────────────────────────────────────

# CHROME_CSS already injected at top of script (before data fetching)
st.markdown(_home_css,    unsafe_allow_html=True)  # home-specific layout
st.markdown(_header_html, unsafe_allow_html=True)  # fixed date header
st.markdown(_fab_html,    unsafe_allow_html=True)  # FAB → Check-In
nav.inject("home", max_width=480)  # bottom nav with JS bridge + session_state buttons

if view == "strain":
    st.markdown(_strain_detail(), unsafe_allow_html=True)
else:
    st.markdown(_card_readiness + _card_strain + _card_sleep, unsafe_allow_html=True)
