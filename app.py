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
from services import hr_load as _hr_load
from services import readiness as readiness_model
from services import sleep_score as sleep_score_model

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

# Keep the URL in sync with whichever page _nav_page resolved to. Nav
# buttons (nav.py's bottom nav, training.py's two internal "back to home"
# spots) only ever set session_state, never st.query_params — so without
# this, the address bar goes stale the moment you navigate anywhere via a
# button instead of a link. That's normally invisible, EXCEPT that
# st.query_params is the fallback used whenever session_state resets (any
# WebSocket reconnect: mobile screen lock, app backgrounding, a dropped
# connection — none of which are rare on a phone). When that happens, the
# user lands wherever the URL last pointed — which in practice is almost
# always ?page=checkin, since the Check-in FAB (app.py's own '+' button) is
# the only real <a href> link in the app, everything else being session-
# state-only nav buttons. Diagnosed by reproducing it directly: Check-in ->
# Training (works fine in-session, URL still said ?page=checkin) -> reload
# -> silently back on Check-in. Syncing here, once, centrally, fixes every
# nav path at once rather than patching each button's on_click individually.
if st.query_params.get("page") != _page:
    st.query_params["page"] = _page

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
    return repo.get_repository().get_daily_session_au_weighted(days)


@st.cache_data(ttl=1800, show_spinner=False)
def _metrics_history_rolling(days: int = 60) -> list[dict]:
    """Persisted Readiness/Sleep%/Strain history (Repository.
    get_metrics_history) for the Readiness/Sleep/Strain card drill-downs'
    trend sparklines — a fixed record, unlike the live recompute this page
    otherwise always does for `selected_date` itself."""
    start = (date.today() - timedelta(days=days)).isoformat()
    return repo.get_repository().get_metrics_history(start=start)


@st.cache_data(ttl=1800, show_spinner=False)
def _wake_time_adjustments_rolling(days: int = 60) -> dict[str, float]:
    """Per-night wake-time corrections for the same window as the Metrics
    History trend — threaded into dash.compute_daily_metrics_snapshot below
    so Sleep Score reflects any correction, and read again by the Sleep card
    drill-down for its "adjusted" badge/control. Cleared (like every other
    cached read here) by the blanket st.cache_data.clear() the drill-down's
    +/- control calls after writing a new adjustment.

    Resolves the manual correction (CLAUDE.md rule 4's narrow manual-entry
    exception) against the Oura+Garmin fusion's own phantom-wake figure —
    both subtract the same minutes, so exactly one wins per night. See
    services/sleep_fusion.py::effective_wake_adjustments."""
    start = (date.today() - timedelta(days=days)).isoformat()
    adjustments, _sources = repo.get_repository().get_effective_wake_adjustments(start=start)
    return adjustments


@st.cache_data(ttl=1800, show_spinner=False)
def _sleep_night_details(start: str, end: str) -> dict[str, dict]:
    """Per-night sleep detail for the drill-down. Deliberately NOT part of
    _bio_rolling: these fields (hypnogram, breathing rate, bedtime end) are
    display-only, and threading them through the engine's biometric rows
    would carry a 1,800-character string per row through readiness, traffic
    light and the metrics-history backfill for no engine benefit.

    Only called when the Sleep drill-down is actually open — see the
    `view == "sleep"` guard at the fetch site — so the ordinary three-card
    Home stream pays nothing for it."""
    return repo.get_repository().get_sleep_night_details(start, end)


@st.cache_data(ttl=1800, show_spinner=False)
def _sleep_fusion_by_date(start: str, end: str) -> dict[str, dict]:
    """Fused hypnograms for the window, keyed by date. The strip prefers the
    fused master; nights without a row fall back to Oura's own sequence."""
    return {
        r["date"]: r
        for r in repo.get_repository().get_sleep_fusion_history(start, end)
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _sleep_daily_context(start: str, end: str) -> dict[str, dict]:
    """Blood oxygen and breathing from the Oura Daily tab — stored since the
    schema widened, surfaced nowhere until now."""
    return repo.get_repository().get_oura_daily_sleep_context(start, end)


@st.cache_data(ttl=1800, show_spinner=False)
def _wake_adjustment_sources(days: int = 60) -> dict[str, str]:
    """{date: "fusion"|"manual"} for the same window — lets the Sleep card
    say which correction it applied rather than showing an unexplained
    number."""
    start = (date.today() - timedelta(days=days)).isoformat()
    _adjustments, sources = repo.get_repository().get_effective_wake_adjustments(start=start)
    return sources


@st.cache_data(ttl=1800, show_spinner=False)
def _current_stage_cached() -> int:
    return repo.get_repository().get_current_stage()


@st.cache_data(ttl=1800, show_spinner=False)
def _session_hr_rolling(days: int = 60) -> list[dict]:
    """Persisted per-session heart-rate load (Repository.
    get_session_hr_history) — Edwards'-TRIMP-derived strain for any day whose
    logged session matched a Garmin activity. Days with no row simply aren't
    in this list, and the strain for those falls back to RPE."""
    start = (date.today() - timedelta(days=days)).isoformat()
    return repo.get_repository().get_session_hr_history(start=start)


@st.cache_data(ttl=7200, show_spinner=False)  # 2h — matches the Garmin sync cadence
def _sync_session_hr_cached() -> tuple[bool, str | None]:
    """Match the last couple of days' logged sessions to their Garmin
    activities and persist the HR load (services/hr_load.py).

    Runs after the Garmin sync above, since it needs that day's activities to
    already be available. Only the last 2 days: a session's Garmin activity
    doesn't change retroactively, and each date costs several calls to
    Garmin's unofficial API. A date that yields nothing (no session, no
    per-set timestamps, no matching activity) is a normal fall-back-to-RPE
    outcome, not an error."""
    r = repo.get_repository()
    if not r.garmin_configured():
        return True, None
    try:
        for offset in (0, 1):
            r.sync_session_hr_for_date(date.today() - timedelta(days=offset))
        return True, None
    except Exception as exc:
        return False, str(exc)


@st.cache_data(ttl=7200, show_spinner=False)  # 2 hours — runs on Home page open, idle in between
def _sync_oura_cached() -> tuple[bool, str | None]:
    """Oura sync (its own Sheet tabs — see Repository.sync_oura_all), feeding
    the engine's biometric blend (services/biometrics.py) as well as
    archiving.

    Throttled by Repository.oura_sync_due() (a local .sync_state.json file —
    see services/clients/local_cache.py), NOT just this cache's TTL: this
    st.cache_data layer alone doesn't reliably throttle anything, since
    st.cache_data is in-memory (reset by every process restart) and gets
    wiped by any unrelated st.cache_data.clear() call elsewhere in the app
    (views/checkin.py clears it on every check-in save) — without the local
    file, either of those forces a full Oura resync on the very next Home
    load. Was "purely this cache's TTL, no durability needed" (Oura's official
    API has generous rate limits) until the days=7 change below made each
    actual sync heavy enough that this stopped being harmless. See
    2026-07-14 fix.

    days=7 (not 2): a rolling 2-day window permanently skips any day that
    falls outside every window the app happened to run during — e.g. the
    app not being opened for a stretch silently drops those days from Oura
    Sleep Periods (the only HRV source now that this rig's Garmin device
    doesn't report HRV at all). A week-wide window self-heals gaps up to
    that size on the next open."""
    r = repo.get_repository()
    if not r.oura_configured():
        return True, None
    if not r.oura_sync_due(hours=2):
        return True, None
    try:
        r.sync_oura_all(days=7)
        r.mark_oura_synced()
        return True, None
    except Exception as exc:
        return False, str(exc)


@st.cache_data(ttl=7200, show_spinner=False)  # throttled for real by the Config-DB marker below, not this TTL
def _sync_garmin_cached() -> tuple[bool, str | None]:
    """Garmin sync (Garmin Daily sheet tab), feeding the engine's biometric
    blend (30% weight for HRV/RHR/sleep, 80% for steps) as well as archiving.
    Was weekly-only and Training-page-only when Garmin was archival-only;
    now also runs on Home open like Oura. Gated to at most every 2 hours
    (matching Oura's cadence), and stops entirely for the rest of the day
    once today's Morning Check-In is submitted — not by this cache's TTL,
    but by sync_garmin_daily_if_due's Config-DB marker + has_checked_in
    check. Garmin's API is unofficial and rate-limit-sensitive, unlike
    Oura's, so this stays throttled rather than syncing every page load."""
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


@st.cache_data(ttl=1800, show_spinner=False)
def _sync_metrics_history_cached() -> tuple[bool, str | None]:
    """Persists the last few days of Readiness/Sleep %/Strain to the
    Metrics History sheet tab (Repository.sync_metrics_history) — same
    "fixed daily snapshot" rationale as Biometric Blend above, and must run
    after it since sync_metrics_history reads the biometric rolling blend
    (and session AU) live. Small rolling window — the on-demand "Backfill
    full history" button in Insights → Sync covers the rest, once."""
    try:
        repo.get_repository().sync_metrics_history(days=7)
        return True, None
    except Exception as exc:
        return False, str(exc)


# ─── Device sync runs AFTER the page paints — see _run_startup_sync() at the
#     bottom of this file. It used to run here, before _bio_rolling(), so that
#     a page load could never blend data the sync was about to refresh.
#
#     That trade was backwards, and measurably so: sync_oura_all takes ~50s
#     and sync_garmin_daily_if_due ~27s, against 4.3s to read what is already
#     in Sheets. Every cold start therefore spent ~77 seconds rendering "No
#     Readings" — a blank screen — purely to avoid showing data up to a couple
#     of hours old. Freshness was being bought with total unavailability.
#
#     Now the page renders from stored data immediately and reruns once when
#     the sync finishes, so the worst case is briefly-stale rather than
#     briefly-absent. ─────────────────────────────────────────────────────────
_oura_sync_ok, _oura_sync_err = st.session_state.get("_sync_status_oura", (True, None))
_garmin_sync_ok, _garmin_sync_err = st.session_state.get("_sync_status_garmin", (True, None))

try:
    _bio_rows = _bio_rolling(days=60)   # 60d to support 56d sleep baseline
except Exception:
    _bio_rows = []

# Sleep drill-down data — fetched ONLY when that view is open. These are two
# extra Sheet reads; paying them on every Home render to populate a screen
# most visits never reach would be the wrong trade.
_sleep_details: dict[str, dict] = {}
_sleep_details_loaded = False
_sleep_context: dict[str, dict] = {}
_sleep_fusion_rows: dict[str, dict] = {}
_sleep_fusion_loaded = False
if view == "sleep":
    _sleep_window_start = (selected_date - timedelta(days=7)).isoformat()
    _sleep_window_end = selected_date.isoformat()
    try:
        _sleep_details = _sleep_night_details(_sleep_window_start, _sleep_window_end)
        _sleep_details_loaded = True
    except Exception:
        pass
    try:
        _sleep_context = _sleep_daily_context(_sleep_window_start, _sleep_window_end)
    except Exception:
        pass
    try:
        _sleep_fusion_rows = _sleep_fusion_by_date(_sleep_window_start, _sleep_window_end)
        _sleep_fusion_loaded = True
    except Exception:
        pass

_au_rows = []
try:
    _au_rows = _au_history()
except Exception:
    pass

_metrics_hist = []
try:
    _metrics_hist = _metrics_history_rolling(days=60)
except Exception:
    pass

_wake_adjustments: dict[str, float] = {}
try:
    _wake_adjustments = _wake_time_adjustments_rolling(days=60)
except Exception:
    pass

_hr_rows: list[dict] = []
try:
    _hr_rows = _session_hr_rolling(days=60)
except Exception:
    pass

try:
    _current_stage = _current_stage_cached()
except Exception:
    _current_stage = 1

_window_start = (selected_date - timedelta(days=6)).isoformat()
_window_end   = selected_date.isoformat()
_bio_7d = sorted(
    [r for r in _bio_rows if r.get("date") and _window_start <= r["date"] <= _window_end],
    key=lambda r: r["date"],
)

# ─── Computed values ──────────────────────────────────────────────────────────

# Progressive sleep baseline (7→14→28→56 nights, outliers <4h/>11h removed) —
# computed once here since sleep_meta()'s description text needs the window
# size too, not just the score; passed into the snapshot below so it isn't
# recomputed a second time there.
_sleep_base_hours, _sleep_base_window = readiness_model.sleep_baseline(_bio_rows)
_sleep_need = _sleep_base_hours if _sleep_base_hours else _SLEEP_NEED_HOURS

# Shared with Repository.sync_metrics_history so the persisted trend history
# can never drift from what's actually shown here. rolling_reference_date
# stays pinned to the real "today" (not selected_date) — the rolling-prior-
# strain fallback and step modifier represent body load accumulated heading
# into training right now, a concept anchored to the present even while
# browsing a past day's card for reference.
_snapshot = dash.compute_daily_metrics_snapshot(
    selected_date, _bio_rows, _au_rows, _current_stage,
    sleep_base_hours=_sleep_base_hours, rolling_reference_date=date.today(),
    wake_time_adjustments=_wake_adjustments,
    hr_rows=_hr_rows,
)
_readiness_score    = _snapshot["readiness_score"]
_sleep_score        = _snapshot["sleep_score"]
_display_strain     = _snapshot["strain"]
_strain_is_rolling  = _snapshot["strain_is_rolling"]

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


# ─── Metric drill-downs (Readiness / Sleep / Strain) ──────────────────────────

def _panel(overline: str, body: str, caption: str = "") -> str:
    """The detail-view panel every block on this screen sits in — same
    #131929 / 12px surface _trend_block and _history_trend_block already use,
    factored out so a new section can't drift from them."""
    cap = (f'<div style="font-size:10px;color:#6B7A9B;margin-top:10px;line-height:1.5;">{caption}</div>'
           if caption else "")
    return (
        f'<div style="background:#131929;border-radius:12px;padding:16px 18px;margin-bottom:10px;">'
        f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;text-transform:uppercase;'
        f'font-weight:600;margin-bottom:10px;">{overline}</div>'
        f'{body}{cap}</div>'
    )


def _contributor_row(row: dict) -> str:
    """Label left, RAW value right, a 4px bar underneath carrying the
    sub-score — Oura's own pattern. Showing sub-score AND raw AND weight on
    one row was tested in the mockup and read as noise at phone width.

    An unscored contributor keeps its row, dimmed with an empty track: on
    this panel the gap is the most informative thing on screen, so it must
    not be silently dropped."""
    scored = row["scored"]
    lbl_col = "#B9C2D6" if scored else "#4A5568"
    val_col = row["colour"] if scored else "#4A5568"
    fill = (f'<i style="display:block;height:100%;border-radius:2px;'
            f'width:{max(0.0, min(100.0, row["bar_pct"])):.1f}%;background:{row["colour"]};"></i>'
            if scored else "")
    return (
        f'<div style="padding:9px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">'
        f'<span style="font-size:13px;color:{lbl_col};">{row["label"]}</span>'
        f'<span style="font-size:13px;font-weight:600;color:{val_col};">{row["value_display"]}</span>'
        f'</div>'
        f'<div style="height:4px;border-radius:2px;background:rgba(255,255,255,0.08);'
        f'margin-top:7px;overflow:hidden;">{fill}</div>'
        f'</div>'
    )


def _sleep_contributors_block() -> str:
    """The seven contributors behind the Sleep Score.

    dashboard.sleep_meta's copy has told users to "check the breakdown for
    what's holding it back" since it was written, while no breakdown existed
    anywhere in the app. This is it."""
    # Computed inline rather than cached: it is pure math over _bio_rows,
    # which is already loaded and cached. Hashing 60 rows to memoise a
    # microsecond of arithmetic would cost more than it saves.
    breakdown = sleep_score_model.sleep_score_breakdown(
        selected_date, _bio_rows, wake_time_adjustments=_wake_adjustments,
    )
    if breakdown["score"] == _NOT_COMPUTED:
        return _panel(
            "Contributors",
            '<div style="font-size:12px;color:#8A99A3;line-height:1.5;">'
            'Oura recorded no sleep period for this night.</div>',
        )
    rows = "".join(_contributor_row(r) for r in dash.sleep_breakdown_rows(breakdown))
    caption = dash.sleep_coverage_caption(breakdown)

    # Total sleep and Efficiency here are the ADJUSTED figures the score was
    # computed from; Key metrics below shows Oura's raw readings. Without
    # this line the screen carries two different "total sleep" numbers a few
    # centimetres apart with nothing explaining the gap.
    adj = breakdown.get("wake_adjustment_minutes") or 0
    if adj:
        note = (f"Total sleep and Efficiency include a {adj:.0f} min wake-time "
                f"correction; Key metrics below shows Oura's raw readings.")
        caption = f"{caption} {note}".strip()
    return _panel("Contributors", rows, caption)


def _kv_rows(rows: list[dict], label_key: str = "label", value_key: str = "value") -> str:
    """The label/value row shape _strain_source_block established."""
    return "".join(
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:11px;color:#8A99A3;padding:4px 0;">'
        f'<span>{r[label_key]}</span><span style="color:#C8CAD0;">{r[value_key]}</span></div>'
        for r in rows
    )


def _key_metric_grid(cells: list[dict]) -> str:
    """The 2x2 of headline numbers. A fixed set, so a missing reading shows a
    dash instead of collapsing the grid and shifting everything under it."""
    def cell(c):
        return (
            f'<div style="background:#131929;border-radius:12px;padding:14px;">'
            f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;'
            f'text-transform:uppercase;font-weight:600;margin-bottom:6px;">{c["label"]}</div>'
            f'<div style="font-size:20px;font-weight:700;color:#D4DCEE;">{c["value"]}</div>'
            f'</div>'
        )
    return ('<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;'
            'margin-bottom:10px;">' + "".join(cell(c) for c in cells) + '</div>')


def _sleep_debt_block(debt: dict) -> str:
    """Debt against the 9.5 h threshold that actually reschedules training
    (scheduling.should_shift_session), so the gauge and the rule agree."""
    if debt["value_display"] is None:
        return ""
    segs = "".join(
        f'<span style="height:3px;border-radius:2px;background:'
        f'{debt["colour"] if i < debt["filled"] else "rgba(255,255,255,0.08)"};"></span>'
        for i in range(4)
    )
    body = (
        f'<div style="display:flex;align-items:baseline;gap:10px;">'
        f'<span style="font-size:28px;font-weight:700;color:#D4DCEE;">{debt["value_display"]}</span>'
        f'<span style="font-size:10px;font-weight:700;letter-spacing:0.08em;'
        f'color:{debt["colour"]};text-transform:uppercase;">{debt["band"]}</span></div>'
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:12px 0 5px;">'
        f'{segs}</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#6B7A9B;">'
        f'<span>None</span><span>High</span></div>'
    )
    return _panel("Sleep debt", body,
                  f'Rest is triggered at {debt["threshold"]:.1f} h.')


_SLEEP_SOURCE_TITLES = {
    "fused": "Fused (Oura + Garmin)",
    "oura_only": "Oura",
    "garmin_only": "Garmin",
}


def _hypnogram_strip(detail: dict | None) -> str:
    """One strip, named for whatever actually produced it.

    Prefers the fused master, falling back to Oura's own sequence. This is
    honest by construction: services/sleep_fusion.py::fuse guarantees a
    Garmin-less night returns Oura's sequence bit-identically, so an
    `oura_only` row really IS Oura's hypnogram — the label just stops
    implying a correction that never happened.

    `detail` may be None on a garmin_only night: the ring was not worn, so
    there is no Oura sleep period to describe, but the watch still has a
    timeline worth drawing."""
    detail = detail or {}
    fused = _sleep_fusion_rows.get(selected_date.isoformat()) or {}
    codes = str(fused.get("master_hypnogram") or "") or detail.get("hypnogram_30sec") or ""
    if not codes:
        return ('<div style="color:#444;font-size:12px;font-style:italic;padding:14px 0;'
                'text-align:center;">No stage timeline recorded for this night.</div>')

    if fused.get("master_hypnogram"):
        source = str(fused.get("source") or "oura_only")
        title = _SLEEP_SOURCE_TITLES.get(source, "Oura")
    else:
        # Fell back to Oura's own column. Distinguish "this night genuinely
        # has no fusion row" from "the fusion read failed" — labelling a
        # failed read as plain Oura would quietly misattribute the strip.
        source = "oura_only"
        title = "Oura" if _sleep_fusion_loaded else "Oura (fusion unavailable)"

    phantom = fused.get("phantom_wake_minutes")
    if source == "fused" and phantom:
        note = (f'<div style="font-size:10px;color:#6B7A9B;margin-top:8px;line-height:1.5;">'
                f'<b style="color:#8FCDF0;">{title}</b> · {phantom} min of Oura wake '
                f'reclassified as sleep — Garmin saw no movement. Display only; the score '
                f'above uses Oura.</div>')
    elif source == "garmin_only":
        # Say plainly that this is the weaker sensor. Garmin mislabels REM as
        # Light, so presenting its hypnogram as equivalent to a ring night
        # would overstate it — and the stage percentages below are the ones
        # most affected.
        note = (f'<div style="font-size:10px;color:#6B7A9B;margin-top:8px;line-height:1.5;">'
                f'Stage timeline from <b style="color:#8FCDF0;">{title}</b> — the ring '
                f'recorded nothing this night. Garmin under-reports REM, so treat the '
                f'stage split as approximate.</div>')
    else:
        note = (f'<div style="font-size:10px;color:#6B7A9B;margin-top:8px;">'
                f'Stage timeline from <b style="color:#8FCDF0;">{title}</b>.</div>')

    start = dash.format_clock(detail.get("bedtime_start")) or dash.format_clock(
        fused.get("window_start_utc"))
    end = dash.format_clock(detail.get("bedtime_end"))
    if not end and start and fused.get("minutes"):
        # garmin_only: no Oura bedtime_end, so derive the axis end from the
        # fusion row's own window rather than leaving the strip unlabelled.
        end = dash.format_clock_offset(fused.get("window_start_utc"), fused.get("minutes"))
    axis = (f'<div style="display:flex;justify-content:space-between;font-size:10px;'
            f'color:#6B7A9B;margin-top:6px;"><span>{start}</span><span>{end}</span></div>'
            if start and end else "")
    # The movement strip sits between the hypnogram and the single shared
    # axis, so "same time axis" is literally true on screen rather than a
    # claim two separately-labelled charts are asking to be believed.
    movement, movement_note = _movement_strip(fused)
    return (f'<div style="margin-top:14px;">{styles.hypnogram_svg(codes, height=56)}</div>'
            f'{movement}{axis}{styles.stage_legend_html()}{note}{movement_note}')


def _movement_strip(fused: dict) -> tuple[str, str]:
    """The fused movement tick strip, or ("", "") when the night has none.

    Returns the strip and its caption separately because the caller sandwiches
    the strip above the shared time axis while the captions collect below —
    keeping both charts on one axis instead of giving each its own.
    """
    codes = str(fused.get("master_movement") or "")
    if not codes:
        return "", ""

    source = str(fused.get("movement_source") or "")
    title = _SLEEP_SOURCE_TITLES.get(source, "Movement")
    shifts = fused.get("movement_position_shifts")
    detail_bits = []
    if source == "fused":
        detail_bits.append("ring resolves small motion, watch confirms whole-body")
    if shifts not in (None, ""):
        detail_bits.append(f"{shifts} position shift{'s' if shifts != 1 else ''}")
    suffix = f" · {' · '.join(detail_bits)}" if detail_bits else ""

    strip = (f'<div style="margin-top:4px;">{styles.movement_svg(codes, height=26)}</div>')
    note = (f'<div style="font-size:10px;color:#6B7A9B;margin-top:6px;line-height:1.5;">'
            f'Movement — <b style="color:#8FCDF0;">{title}</b>{suffix}.</div>'
            f'{styles.movement_legend_html()}')
    return strip, note


def _garmin_only_stage_rows(fused: dict) -> str:
    """Stage legend for a night with no Oura period, read straight off the
    fusion row's own master_* minute counts.

    dashboard.sleep_stage_legend can't serve here — it takes Oura's per-stage
    seconds, which is exactly what a garmin_only night does not have. Same
    visual shape so the two paths look identical on screen even though they
    are sourced differently."""
    total = sum(_float_or_zero(fused.get(f"master_{k}_minutes"))
                for k in ("deep", "light", "rem"))
    rows = []
    for key, code in (("awake", "4"), ("rem", "3"), ("light", "2"), ("deep", "1")):
        mins = _float_or_zero(fused.get(f"master_{key}_minutes"))
        pct = f"{mins / total * 100:.0f} %" if total and key != "awake" else "—"
        rows.append(
            f'<div style="display:flex;align-items:center;gap:9px;padding:5px 0;font-size:12px;">'
            f'<span style="width:26px;height:6px;border-radius:3px;flex:none;'
            f'background:{styles.STAGE_BAND[code][0]};"></span>'
            f'<span style="color:#B9C2D6;width:52px;">{styles.STAGE_BAND[code][1]}</span>'
            f'<span style="color:#D4DCEE;">{dash.format_duration(mins * 60)}</span>'
            f'<span style="color:#6B7A9B;margin-left:auto;">{pct}</span></div>')
    return "".join(rows)


def _float_or_zero(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _sleep_night_blocks() -> str:
    """Key metrics, sleep debt, architecture and vitals for the selected
    night. Everything here reads the Oura values the score itself used, so
    the numbers under the score always explain that score."""
    detail = _sleep_details.get(selected_date.isoformat())
    context = _sleep_context.get(selected_date.isoformat(), {})
    fused = _sleep_fusion_rows.get(selected_date.isoformat()) or {}
    if detail is None:
        if not _sleep_details_loaded:
            # The read failed. Silently rendering nothing here would be
            # indistinguishable from "this night has no sleep data", which is
            # a different and much more alarming statement.
            return _panel(
                "Night detail",
                '<div style="font-size:12px;color:#8A99A3;line-height:1.5;">'
                'Could not load this night&rsquo;s detail — try again shortly.</div>')
        if str(fused.get("source")) == "garmin_only" and fused.get("master_hypnogram"):
            # The ring was not worn but the watch has this night. Everything
            # below is built from Oura fields and genuinely does not exist, so
            # show the architecture the watch DOES have rather than nothing —
            # and say why the score above is blank, which is otherwise the
            # most confusing part of the screen.
            return _panel(
                "Time asleep",
                '<div style="font-size:11px;color:#6B7A9B;line-height:1.5;">'
                'No Oura ring reading for this night, so there is no Sleep Score — '
                'every contributor it is built from is an Oura measurement. '
                'Garmin recorded the night, so the stage timeline below is real.</div>'
                + _hypnogram_strip(None)
                + f'<div style="margin-top:12px;">{_garmin_only_stage_rows(fused)}</div>')
        return ""

    out = _key_metric_grid(dash.sleep_key_metrics(detail))

    debt = dash.sleep_debt_display(
        readiness_model.sleep_debt_hours(_bio_rows, selected_date))
    out += _sleep_debt_block(debt)

    legend = dash.sleep_stage_legend(detail)
    stage_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:9px;padding:5px 0;font-size:12px;">'
        f'<span style="width:26px;height:6px;border-radius:3px;flex:none;'
        f'background:{styles.STAGE_BAND[k][0]};"></span>'
        f'<span style="color:#B9C2D6;width:52px;">{r["label"]}</span>'
        f'<span style="color:#D4DCEE;">{r["duration"]}</span>'
        f'<span style="color:#6B7A9B;margin-left:auto;">{r["pct"]}</span></div>'
        for r, k in zip(legend, ("4", "3", "2", "1"))
    )
    asleep = dash.format_duration(detail.get("total_seconds")) or "—"
    in_bed = dash.format_duration(detail.get("time_in_bed_seconds")) or "—"
    out += _panel(
        "Time asleep",
        f'<div style="font-size:28px;font-weight:700;color:#D4DCEE;">{asleep}</div>'
        f'<div style="font-size:11px;color:#6B7A9B;margin-top:2px;">Total duration {in_bed}</div>'
        + _hypnogram_strip(detail)
        + f'<div style="margin-top:12px;">{stage_rows}</div>',
    )

    vitals = dash.sleep_vitals_rows(detail, context)
    if vitals:
        out += _panel("Vitals while asleep", _kv_rows(vitals))
    return out


def _strain_source_block() -> str:
    """Which method produced today's strain, and the HR detail behind it when
    there was one — so a fall back to RPE-only is visible rather than silent
    (the explicit ask in item 17)."""
    source = _snapshot.get("strain_source")
    label = _snapshot.get("strain_source_label") or ""
    if not source or source == _NOT_COMPUTED:
        return ""
    if source == "rpe":
        tint, icon = "#8A99A3", "○"
    elif source == "none":
        return ""
    else:
        tint, icon = "#6BAF8B", "●"

    rows = ""
    hr = _snapshot.get("hr_detail") or {}
    if hr:
        zones = hr.get("zone_minutes") or {}
        zone_txt = "  ".join(
            f"Z{z} {m:g}m" for z, m in sorted(zones.items(), key=lambda kv: str(kv[0]))
        )
        for name, val in (
            ("Edwards' load", f"{hr.get('edwards_load')} zone-weighted min"),
            ("Avg / max HR", f"{hr.get('avg_hr') or '—'} / {hr.get('max_hr') or '—'} bpm"),
            ("HRmax used", f"{hr.get('hr_max_used') or '—'} bpm (observed)"),
            ("Banister TRIMP", f"{hr.get('banister_trimp') or '—'}  (cross-check)"),
            ("Time in zones", zone_txt or "—"),
        ):
            rows += (
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:11px;color:#8A99A3;margin-top:4px;">'
                f'<span>{name}</span><span style="color:#C8CAD0;">{val}</span></div>'
            )
        both = (_snapshot.get("strain_hr_only"), _snapshot.get("strain_rpe_only"))
        if all(v is not None for v in both):
            rows += (
                f'<div style="font-size:10px;color:#6B7A9B;margin-top:8px;">'
                f'HR {both[0]} · RPE {both[1]} → blended at '
                f'{int(_hr_load.HR_BLEND_WEIGHT * 100)}% HR</div>'
            )

    return (
        f'<div style="background:#1A2026;border-radius:12px;padding:12px 14px;margin:14px 0;">'
        f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;'
        f'text-transform:uppercase;margin-bottom:6px;">Strain source</div>'
        f'<div style="font-size:13px;color:{tint};font-weight:600;">{icon} {label}</div>'
        f'{rows}</div>'
    )


def _metric_detail(view: str) -> str:
    def _trend_block(title: str, unit: str, values: list, color: str) -> str:
        """7-day, day-of-week-labeled block — used for Strain's supplementary
        HRV/RHR context (the live 7-day biometric blend, not persisted
        history)."""
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

    def _history_trend_block(title: str, unit: str, dates: list, values: list, color: str) -> str:
        """30-day trend from the PERSISTED Metrics History tab (see
        Repository.get_metrics_history) — a fixed record, unlike the 7-day
        blocks above which recompute live from Oura/Garmin's raw tabs."""
        has_data = any(v is not None for v in values)
        current  = next((v for v in reversed(values) if v is not None), None)
        val_str  = f"{current:.0f}{unit}" if current is not None else "—"
        range_label = f"{dates[0].strftime('%d %b')} – {dates[-1].strftime('%d %b')}" if dates else ""
        chart_or_empty = (
            f'<div style="display:flex;justify-content:center;">'
            + (_sparkline(values, width=290, height=68, color=color) if has_data else
               f'<div style="width:290px;height:68px;display:flex;align-items:center;'
               f'justify-content:center;"><span style="color:#444;font-size:12px;'
               f'font-style:italic;">No persisted history yet — check back after a few days.</span></div>')
            + f'</div>'
        )
        return (
            f'<div style="background:#131929;border-radius:12px;padding:16px 18px;margin-bottom:10px;">'
            f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;text-transform:uppercase;'
            f'font-weight:600;margin-bottom:4px;">{title}</div>'
            f'<div style="font-size:28px;font-weight:700;color:#D4DCEE;margin-bottom:4px;">{val_str}</div>'
            f'<div style="font-size:10px;color:#555;margin-bottom:8px;">{range_label}</div>'
            f'{chart_or_empty}'
            f'</div>'
        )

    # pre_blocks render BEFORE the 30-day trend, extra_blocks after. Sleep's
    # contributor breakdown has to lead — it explains the number in the
    # header — whereas strain's supplementary context reads as a footnote.
    pre_blocks = ""
    if view == "readiness":
        col, disp, lbl, _, _, _ = dash.readiness_meta(_readiness_score)
        detail_label = f"READINESS · {date_label}"
        hist_key, hist_unit, hist_title, hist_color = "readiness_score", "", "Readiness Trend", "#6BAF8B"
        extra_blocks = ""
    elif view == "sleep":
        col, disp, lbl, _, _ = dash.sleep_meta(_sleep_score, _sleep_need, _sleep_base_window)
        _today_wake_adj = _wake_adjustments.get(selected_date.isoformat(), 0.0)
        detail_label = f"SLEEP · {date_label}" + (" · ADJUSTED" if _today_wake_adj else "")
        hist_key, hist_unit, hist_title, hist_color = "sleep_score", "", "Sleep Score Trend", "#4FC3F7"
        pre_blocks = _sleep_contributors_block() + _sleep_night_blocks()
        extra_blocks = ""
    else:
        col, disp, lbl, _, _ = dash.strain_meta(_display_strain, is_rolling=_strain_is_rolling)
        detail_label = "STRAIN · 7D AVG" if _strain_is_rolling else f"STRAIN · {date_label}"
        hist_key, hist_unit, hist_title, hist_color = "strain", "", "Strain Trend", "#BFA06A"
        extra_blocks = (
            _strain_source_block()
            + _trend_block("Heart Rate Variability", "ms",  _hrv_7d, "#6BAF8B")
            + _trend_block("Resting Heart Rate",     "bpm", _rhr_7d, "#BFA06A")
        )

    hist_dates = [selected_date - timedelta(days=29 - i) for i in range(30)]
    hist_by_date = {r["date"]: r.get(hist_key) for r in _metrics_hist}
    hist_values = [hist_by_date.get(d.isoformat()) for d in hist_dates]

    # Sleep-only: a simple marker for how many nights in this 30-day window
    # carry a wake-time adjustment (CLAUDE.md rule 4's narrow manual-entry
    # exception) — deliberately just a count/caption, not a per-point
    # sparkline annotation.
    adjusted_marker = ""
    if view == "sleep":
        adjusted_nights = sum(1 for d in hist_dates if _wake_adjustments.get(d.isoformat()))
        if adjusted_nights:
            adjusted_marker = (
                f'<div style="font-size:10px;color:#4FC3F7;margin:-4px 0 10px;">'
                f'⚡ {adjusted_nights} night(s) wake-time adjusted in this window</div>'
            )

    return (
        f'<div style="padding:16px;">'
        f'<div style="display:flex;align-items:center;margin-bottom:20px;">'
        f'<a href="?d={selected_date}" style="color:#6B7A9B;font-size:22px;'
        f'text-decoration:none;margin-right:14px;line-height:1;">←</a>'
        f'<div>'
        f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;'
        f'text-transform:uppercase;margin-bottom:2px;">{detail_label}</div>'
        f'<div style="font-size:30px;font-weight:800;color:{col};line-height:1;">{disp}</div>'
        f'<div style="font-size:12px;color:#6B7A9B;margin-top:2px;">{lbl}</div>'
        f'</div>'
        f'</div>'
        + pre_blocks
        + _history_trend_block(hist_title, hist_unit, hist_dates, hist_values, hist_color)
        + adjusted_marker
        + extra_blocks
        + f'</div>'
    )


def _render_wake_time_control(d: date) -> None:
    """+/- stepper for the per-night wake-time adjustment (CLAUDE.md rule
    4's narrow manual-entry exception — corrects Oura's known wake-time-
    overestimation pattern, not general manual biometric entry). Mirrors
    views/training.py's reps/weight stepper pattern visually: a small
    uppercase monospace label, a [1,2,1] column row of −/value/+, real
    st.button widgets (this can't live inside _metric_detail's plain HTML
    string). Writes via Repository.set_wake_time_adjustment and reruns so
    the Sleep Score/trend immediately reflect the new value — the raw Oura
    reading itself is never touched."""
    current = _wake_adjustments.get(d.isoformat(), 0.0)
    st.markdown(
        "<div style='padding:0 16px;'><div style='font-size:10px;color:#6B7A9B;"
        "letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;'>"
        "Adjust Wake Time</div></div>",
        unsafe_allow_html=True,
    )
    wc1, wc2, wc3 = st.columns([1, 2, 1])
    with wc1:
        if st.button("−", key="wt_adj_dec", use_container_width=True):
            repo.get_repository().set_wake_time_adjustment(
                d, dash.step_wake_time_adjustment(current, -1),
            )
            st.cache_data.clear()
            st.rerun()
    with wc2:
        label = f"−{current:.0f} min" if current else "No adjustment"
        st.markdown(
            f"<div style='text-align:center;font-size:22px;font-weight:700;"
            f"color:#D4DCEE;'>{label}</div>",
            unsafe_allow_html=True,
        )
    with wc3:
        if st.button("+", key="wt_adj_inc", use_container_width=True):
            repo.get_repository().set_wake_time_adjustment(
                d, dash.step_wake_time_adjustment(current, +1),
            )
            st.cache_data.clear()
            st.rerun()
    if current:
        st.caption(
            f"Wake time corrected −{current:.0f} min for {d.isoformat()} "
            "(known Oura wake-time-overestimation pattern)."
        )


# ─── Fixed UI elements ────────────────────────────────────────────────────────

_next_style = "color:#D4DCEE;" if can_go_next else "color:#2A2A3A;pointer-events:none;"
_next_href  = f"?d={next_date}" if can_go_next else "#"

_DETAIL_VIEW_TITLES = {"strain": "Strain History", "readiness": "Readiness History", "sleep": "Sleep History"}
if view in _DETAIL_VIEW_TITLES:
    _header_inner = (
        f'<a href="?d={selected_date}" style="color:#6B7A9B;text-decoration:none;'
        f'font-size:22px;line-height:1;margin-right:14px;">←</a>'
        f'<span style="color:#D4DCEE;font-weight:600;font-size:15px;">{_DETAIL_VIEW_TITLES[view]}</span>'
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
    click_href=f"?d={selected_date}&view=readiness",
)

s_col, s_disp, s_lbl, s_hdr, s_desc = dash.strain_meta(_display_strain, is_rolling=_strain_is_rolling)
_strain_card_label = "STRAIN  ·  7D AVG" if _strain_is_rolling else "STRAIN"
_card_strain = _card_html(
    _strain_card_label, _bg["strain"],
    _arc_svg(_display_strain, 21, s_col),
    s_disp, s_lbl, s_col, s_hdr, s_desc,
    click_href=f"?d={selected_date}&view=strain",
)

sl_col, sl_disp, sl_lbl, sl_hdr, sl_desc = dash.sleep_meta(_sleep_score, _sleep_need, _sleep_base_window)
_card_sleep = _card_html(
    "SLEEP", _bg["sleep"],
    _arc_svg(_sleep_score, 100, sl_col),
    sl_disp, sl_lbl, sl_col, sl_hdr, sl_desc,
    click_href=f"?d={selected_date}&view=sleep",
)

# ─── Render ───────────────────────────────────────────────────────────────────

# CHROME_CSS already injected at top of script (before data fetching)
styles.inject_css()                                # base styles (same as other pages)
st.markdown(_home_css,    unsafe_allow_html=True)  # home-specific overrides (480px max-width etc.)
st.markdown(_header_html, unsafe_allow_html=True)  # fixed date header
st.markdown(_fab_html,    unsafe_allow_html=True)  # FAB → Check-In

if view in ("strain", "readiness", "sleep"):
    st.markdown(_metric_detail(view), unsafe_allow_html=True)
    if view == "sleep":
        _render_wake_time_control(selected_date)
else:
    st.markdown(_card_readiness + _card_strain + _card_sleep, unsafe_allow_html=True)
if not _oura_sync_ok and _oura_sync_err:
    st.caption("Oura sync unavailable — will retry next visit.")
if not _garmin_sync_ok and _garmin_sync_err:
    st.caption("Garmin sync unavailable — will retry next visit.")
nav.inject("home")


def _run_startup_sync() -> None:
    """Refresh the device tabs, then rerun once so the page picks it up.

    Deliberately the LAST thing in the script. Streamlit streams each widget
    as it executes, so everything above is already on screen by the time this
    runs — the user sees their night in ~5s and this tops it up behind them,
    instead of staring at "No Readings" for ~77s while it finishes.

    Ordering between the five is still load-bearing and unchanged: the blend
    derives from the Oura and Garmin tabs, session HR needs today's Garmin
    activities, and metrics history derives from all of the above.

    Runs at most once per session. Each call is individually throttled anyway
    (Repository.oura_sync_due's local marker, and Garmin's own 2-hour gate),
    so this guard is about not paying the rerun repeatedly, not about
    preventing duplicate API calls.
    """
    if st.session_state.get("_startup_sync_done"):
        return
    st.session_state["_startup_sync_done"] = True

    st.session_state["_sync_status_oura"] = _sync_oura_cached()
    st.session_state["_sync_status_garmin"] = _sync_garmin_cached()
    _sync_biometric_blend_cached()
    _sync_session_hr_cached()
    _sync_metrics_history_cached()

    # The reads above this point ran against pre-sync data. Drop their cached
    # results so the rerun genuinely re-reads, rather than repainting exactly
    # what was already on screen.
    for cached in (_bio_rolling, _sleep_night_details, _sleep_fusion_by_date,
                   _sleep_daily_context, _metrics_history_rolling):
        try:
            cached.clear()
        except Exception:
            pass
    st.rerun()


_run_startup_sync()
