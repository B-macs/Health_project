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
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

import nav
import repo
import styles
from services import dashboard as dash
from services import engine
from services import readiness as readiness_model

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
# Primary: session_state["_nav_page"] set by nav trigger buttons (WebSocket rerun,
#          no page reload, same connection).
# Fallback: st.query_params["page"] for direct URL access and first load.
_page = st.session_state.get("_nav_page") or st.query_params.get("page", "home")

if _page == "training":
    from views import training as _v
    styles.inject_css(); _v.render(); nav.inject("training"); st.stop()
elif _page == "insights":
    from views import insights as _v
    styles.inject_css(); _v.render(); nav.inject("insights"); st.stop()
elif _page == "sync":
    from views import sync as _v
    styles.inject_css(); _v.render(); nav.inject("sync"); st.stop()
elif _page == "checkin":
    from views import checkin as _v
    styles.inject_css(); _v.render(); nav.inject(""); st.stop()

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
def _bio_rolling(days: int = 32) -> list[dict]:
    # engine.py/readiness.py still work on plain dicts -- asdict() converts
    # the typed BiometricRecord back to the exact shape they expect.
    return [asdict(r) for r in repo.get_repository().get_biometric_rolling(days=days)]


@st.cache_data(ttl=1800, show_spinner=False)
def _au_history(days: int = 28) -> list[dict]:
    return repo.get_repository().get_daily_session_au(days)


@st.cache_data(ttl=7200, show_spinner=False)  # 2 hours — runs on Home page open, idle in between
def _sync_oura_cached() -> tuple[bool, str | None]:
    """Oura sync (its own Sheet tabs — see Repository.sync_oura_all), feeding
    the engine's biometric blend (services/biometrics.py) as well as
    archiving. Throttled purely by this cache's TTL rather than a persisted
    Config-DB marker like Garmin's daily sync below: Oura's official API has
    generous rate limits (unlike Garmin's unofficial one), so an extra sync
    after a Streamlit restart is harmless — no need for that extra durability."""
    r = repo.get_repository()
    if not r.oura_configured():
        return True, None
    try:
        r.sync_oura_all(days=2)
        return True, None
    except Exception as exc:
        return False, str(exc)


@st.cache_data(ttl=7200, show_spinner=False)  # throttled for real by the Config-DB once/day marker below
def _sync_garmin_cached() -> tuple[bool, str | None]:
    """Garmin sync (Garmin Daily sheet tab), feeding the engine's biometric
    blend (30% weight for HRV/RHR/sleep, 80% for steps) as well as archiving.
    Was weekly-only and Training-page-only when Garmin was archival-only;
    now also runs on Home open like Oura, but still gated to once/day (not
    this cache's TTL) via sync_garmin_daily_if_due's Config-DB marker —
    Garmin's API is unofficial and rate-limit-sensitive, unlike Oura's."""
    r = repo.get_repository()
    if not r.garmin_configured():
        return True, None
    try:
        return r.sync_garmin_daily_if_due(days=2)
    except Exception as exc:
        return False, str(exc)


@st.cache_data(ttl=1800, show_spinner=False)
def _sync_biometric_blend_cached() -> tuple[bool, str | None]:
    """Persists the last few days of the Oura+Garmin blend to the Biometric
    Blend sheet tab (Repository.sync_biometric_blend) so past days become a
    fixed historical record instead of only being re-derivable live from
    Oura/Garmin's own tabs. Small rolling window (not full history) — the
    on-demand "Backfill full history" button in Insights → Sync covers the
    rest, once."""
    try:
        repo.get_repository().sync_biometric_blend(days=7)
        return True, None
    except Exception as exc:
        return False, str(exc)


# Oura/Garmin sync must run before _bio_rolling() below — get_biometric_rolling()
# now reads their Sheet tabs directly, so a stale-cache page load would
# otherwise blend yesterday's data even though the sync ran moments later.
_oura_sync_ok, _oura_sync_err = _sync_oura_cached()
_garmin_sync_ok, _garmin_sync_err = _sync_garmin_cached()
_blend_sync_ok, _blend_sync_err = _sync_biometric_blend_cached()

try:
    _bio_rows = _bio_rolling(days=60)   # 60d to support 56d sleep baseline
except Exception:
    _bio_rows = []

_au_rows = []
try:
    _au_rows = _au_history()
except Exception:
    pass

try:
    _current_stage = repo.get_repository().get_current_stage()
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

# ─── Computed values ──────────────────────────────────────────────────────────

_readiness_score = readiness_model.compute_readiness(selected_date, _bio_rows)
_strain_score    = dash.au_to_strain_or_none(_au_day["total_au"] if _au_day else None, _current_stage)
_sleep_hours     = _bio_day.get("sleep_duration_hours") if _bio_day else None

# Rolling 7-day prior strain — body load already accumulated before today's session.
# Excludes today so it always reflects pre-session state.
_rolling_strain = dash.rolling_prior_strain(_au_rows, _current_stage, today=date.today())
# When no session today: show rolling body load. After training: show today's strain.
_display_strain, _strain_is_rolling = dash.display_strain(_strain_score, _rolling_strain)

# Step count modifier: shift displayed strain by yesterday's non-training load.
_display_strain = dash.apply_step_modifier(_display_strain, _bio_rows, today=date.today())

# Progressive sleep baseline (7→14→28→56 nights, outliers <4h/>11h removed)
_sleep_base_hours, _sleep_base_window = readiness_model.sleep_baseline(_bio_rows)
_sleep_need = _sleep_base_hours if _sleep_base_hours else _SLEEP_NEED_HOURS
_sleep_pct  = dash.sleep_percent(_sleep_hours, _sleep_need)

_hrv_7d = dash.fill_7day(_bio_7d, "hrv_ms", selected_date)
_rhr_7d = dash.fill_7day(_bio_7d, "resting_heart_rate", selected_date)

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


# Status classifiers (readiness_meta/strain_meta/sleep_meta) now live in
# services/dashboard.py — see the "Build cards" section below for call sites.


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

    s_col, s_disp, s_lbl, _, _ = dash.strain_meta(_display_strain, is_rolling=_strain_is_rolling)
    _detail_label = "STRAIN · 7D AVG" if _strain_is_rolling else f"STRAIN · {date_label}"
    return (
        f'<div style="padding:16px;">'
        f'<div style="display:flex;align-items:center;margin-bottom:20px;">'
        f'<a href="?d={selected_date}" style="color:#6B7A9B;font-size:22px;'
        f'text-decoration:none;margin-right:14px;line-height:1;">←</a>'
        f'<div>'
        f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;'
        f'text-transform:uppercase;margin-bottom:2px;">{_detail_label}</div>'
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

# FAB — Morning Check-In (?page=checkin → SPA router dispatches views/checkin.py)
# Anchored just below the fixed date header (57px tall) so it clears the
# header's right-aligned "›" next-day arrow instead of overlapping it.
_fab_html = (
    '<a href="?page=checkin" style="text-decoration:none;">'
    '<div style="position:fixed;top:69px;'
    'right:max(20px,calc((100vw - 480px)/2 + 16px));'
    'z-index:900;width:52px;height:52px;border-radius:50%;background:#FFFFFF;'
    'display:flex;align-items:center;justify-content:center;'
    'box-shadow:0 4px 20px rgba(0,0,0,0.45);cursor:pointer;">'
    '<span style="font-size:28px;color:#0B0F1E;line-height:1;font-weight:300;">+</span>'
    '</div>'
    '</a>'
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

r_col, r_disp, r_lbl, r_hdr, r_desc, r_tert = dash.readiness_meta(_readiness_score)
_card_readiness = _card_html(
    "READINESS", _bg["readiness"],
    _arc_svg(_readiness_score, 100, r_col),
    r_disp, r_lbl, r_col, r_hdr, r_desc, r_tert,
)

s_col, s_disp, s_lbl, s_hdr, s_desc = dash.strain_meta(_display_strain, is_rolling=_strain_is_rolling)
_strain_card_label = "STRAIN  ·  7D AVG" if _strain_is_rolling else "STRAIN"
_card_strain = _card_html(
    _strain_card_label, _bg["strain"],
    _arc_svg(_display_strain, 21, s_col),
    s_disp, s_lbl, s_col, s_hdr, s_desc,
    click_href=f"?d={selected_date}&view=strain",
)

sl_col, sl_disp, sl_lbl, sl_hdr, sl_desc = dash.sleep_meta(_sleep_pct, _sleep_need, _sleep_base_window)
_card_sleep = _card_html(
    "SLEEP", _bg["sleep"],
    _arc_svg(_sleep_pct, 100, sl_col),
    sl_disp, sl_lbl, sl_col, sl_hdr, sl_desc,
)

# ─── Render ───────────────────────────────────────────────────────────────────

# CHROME_CSS already injected at top of script (before data fetching)
styles.inject_css()                                # base styles (same as other pages)
st.markdown(_home_css,    unsafe_allow_html=True)  # home-specific overrides (480px max-width etc.)
st.markdown(_header_html, unsafe_allow_html=True)  # fixed date header
st.markdown(_fab_html,    unsafe_allow_html=True)  # FAB → Check-In

if view == "strain":
    st.markdown(_strain_detail(), unsafe_allow_html=True)
else:
    st.markdown(_card_readiness + _card_strain + _card_sleep, unsafe_allow_html=True)
if not _oura_sync_ok and _oura_sync_err:
    st.caption("Oura sync unavailable — will retry next visit.")
if not _garmin_sync_ok and _garmin_sync_err:
    st.caption("Garmin sync unavailable — will retry next visit.")
nav.inject("home")
