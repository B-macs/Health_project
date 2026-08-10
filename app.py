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
import training_constants as _tc
from services import dashboard as dash
from services import engine
from services import hr_load as _hr_load
from services import plan as plan_svc
from services import readiness as readiness_model
from services import sleep_score as sleep_score_model
from services import strain_regions as _sr

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Home",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject sidebar-suppression CSS IMMEDIATELY — before any data fetching —
# so the sidebar never becomes visible during load.
st.markdown(nav.CHROME_CSS, unsafe_allow_html=True)

# ─── Offline-datastore banner ─────────────────────────────────────────────────
# HEALTH_DATASTORE_PATH makes every Sheets read come from a local snapshot
# (services/clients/datastore_reader.py) — for iterating without spending the
# 60-per-minute Sheets quota. It is deliberately unmissable and rendered
# BEFORE the router, so it appears at the top of every page: an app that
# looks live while serving a snapshot of last night's sleep is the one
# failure this mode must never produce silently. Costs nothing when unset.
if repo.get_repository().offline:
    _built = repo.get_repository().datastore_built_at() or "unknown"
    st.warning(
        f"**Offline** — reading the local datastore, not Google Sheets. "
        f"Snapshot built {_built}. Writes are disabled and today's data may "
        f"be missing. Unset `HEALTH_DATASTORE_PATH` to go live.",
        icon="🗄️",
    )

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
# the last remaining page-CHANGING <a href> link in the app, everything else
# being session-state-only nav buttons. Diagnosed by reproducing it directly:
# Check-in -> Training (works fine in-session, URL still said ?page=checkin)
# -> reload -> silently back on Check-in. Syncing here, once, centrally, fixes
# every nav path at once rather than patching each button's on_click
# individually.
#
# NOTE the anchors that remain below (this file's day arrows, drill-down
# cards and FAB, plus styles.py's chart hit bands) are page RELOADS, which is
# the lag CLAUDE.md Key Rule 17 exists to remove — see
# tests/test_spa_navigation.py's _KNOWN map for which are structural and
# which are merely not converted yet. views/ is already fully converted.
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

# Which point of which chart is open, as "<chart id>:<index>" — see
# services.dashboard.parse_point_selection. Carried in the URL rather than in
# session_state for the same reason `view` and `d` are: every link on this
# page is a plain <a href> (the drill-downs have no Streamlit widgets except
# the wake-time stepper), so the URL is already the page's state, and a
# selection kept anywhere else would be lost on the reconnects the router's
# note above describes. Malformed values resolve to (None, None) and simply
# select nothing.
_point_chart, _point_index = dash.parse_point_selection(_params.get("pt"))

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
def _region_au_history(days: int = 31) -> dict:
    """Per-region AU for the strain drill-down — upper/core/lower plus an
    `unattributed` bucket, summing exactly to each day's own weighted AU.

    Deliberately its OWN fetch rather than widening _au_history: this is
    called only from the strain drill-down, so the three-card Home stream
    never pays for it. Opening a drill-down is a deliberate click that can
    afford a read, which is the same trade services/home_snapshot.py makes
    when it declines to cache hr_detail.

    31 days so the 30-day trend window is fully covered.
    """
    return repo.get_repository().get_daily_region_au(days)


@st.cache_data(ttl=1800, show_spinner=False)
def _stage_start_cached():
    """Start date of the active phase — scopes the per-region ACWR's chronic
    baseline to the current stage, exactly as views/insights.py does for the
    overall one. None during a reassessment gap, where engine.acwr falls back
    to the flat 28-day calendar window."""
    return plan_svc.current_stage_start(repo.get_repository().get_phases(), date.today())


@st.cache_data(ttl=1800, show_spinner=False)
def _session_hr_rolling(days: int = 60) -> list[dict]:
    """Persisted per-session heart-rate load (Repository.
    get_session_hr_history) — Edwards'-TRIMP-derived strain for any day whose
    logged session matched a Garmin activity. Days with no row simply aren't
    in this list, and the strain for those falls back to RPE."""
    start = (date.today() - timedelta(days=days)).isoformat()
    return repo.get_repository().get_session_hr_history(start=start)


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

# _bio_rows_failed distinguishes "the read failed" from "there is no data",
# which the bare `except: _bio_rows = []` here could not. Every screen
# downstream renders an empty _bio_rows as absence — the Sleep drill-down
# said "Oura recorded no sleep period for this night", which is a statement
# of fact about the ring, and it was false whenever the real cause was a
# failed Sheets read. That is not hypothetical: a transient read failure
# produced exactly that screen on a night whose data was complete (all seven
# contributors present, score 76.8), and the same read-failure-looks-like-
# missing-data confusion had already caused one wrong conclusion about
# Metrics History. _sleep_night_blocks() has always drawn this distinction;
# the biometric rows now do too.
_bio_rows_failed = False
try:
    _bio_rows = _bio_rolling(days=60)   # 60d to support 56d sleep baseline
except Exception:
    _bio_rows = []
    _bio_rows_failed = True

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

# Readiness drill-down data — same guard-and-only-when-open pattern as the
# sleep block above. Only _sleep_details is needed: the Readiness screen's
# respiratory-rate tile and its two overnight charts all come from the night's
# sleep detail, and everything else it shows is already in _bio_rows.
if view == "readiness":
    _r_window_start = (selected_date - timedelta(days=7)).isoformat()
    _r_window_end = selected_date.isoformat()
    try:
        _sleep_details = _sleep_night_details(_r_window_start, _r_window_end)
        _sleep_details_loaded = True
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

# Is TODAY's dashboard settled — readiness and sleep both already persisted?
# Decides whether _run_startup_sync at the bottom of this file waits for the
# device sync or hands it to a worker thread. Always keyed on the real today,
# never selected_date: browsing back to a past day must not change what the
# CURRENT day still needs. A failed read leaves this False, which errs
# towards syncing in the foreground — the safe direction, since the cards are
# blank in that case anyway.
_today_metrics_row = next(
    (r for r in _metrics_hist if r.get("date") == _today.isoformat()), None,
)
_day_settled = dash.snapshot_is_complete(_today_metrics_row)

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


# ─── Charts: axes, tappable bands, point detail ───────────────────────────────
#  Everything here composes services.dashboard's pure axis maths with styles.py's
#  renderers. The old `_sparkline` this replaces drew a bare line with the last
#  value floating beside it and no scale of either kind — see the note at the
#  head of services/dashboard.py's axis section for why that had to change.
#
#  Clicking is an ordinary <a href> that adds `?pt=<chart>:<index>`, which is
#  the same mechanism the three Home cards already use to open these
#  drill-downs. No JS, no iframe, and no Streamlit widget — a widget here would
#  put a native button in the middle of an HTML panel and force the whole block
#  to be split across several st.markdown calls.

_EMPTY_CHART_HEIGHT = 92


def _chart_href(chart: str, index: int) -> str:
    return f"?d={selected_date}&view={view}&pt={dash.point_selection_key(chart, index)}"


def _clear_point_href() -> str:
    return f"?d={selected_date}&view={view}"


def _is_selected(chart: str, index: int) -> bool:
    return _point_chart == chart and _point_index == index


def _chart_empty(message: str, height: int = _EMPTY_CHART_HEIGHT) -> str:
    return (f'<div style="height:{height}px;display:flex;align-items:center;'
            f'justify-content:center;"><span style="color:#444;font-size:12px;'
            f'font-style:italic;">{message}</span></div>')


def _point_detail_block(detail: dict | None, extra_rows=(), open_view: str = "") -> str:
    """The panel a selected point opens, rendered INSIDE the chart's own block
    directly under it.

    Deliberately not a separate card at the top of the screen: the whole value
    of the thing is that it explains the point being looked at, and putting it
    anywhere else makes the reader hold a position on one chart in their head
    while reading numbers somewhere else.
    """
    if not detail:
        return ""
    rows = _kv_rows(list(detail["rows"]) + list(extra_rows))
    link = ""
    if detail.get("open_date") and open_view:
        link = (f'<a class="hp-link" href="?d={detail["open_date"]}&view={open_view}" '
                f'style="display:inline-block;margin-top:9px;font-size:11px;'
                f'color:#8FCDF0;text-decoration:none;">'
                f'Open {detail["open_date"]} &rarr;</a>')
    return (
        f'<div style="background:#0E1424;border:1px solid #1E2840;border-radius:10px;'
        f'padding:11px 13px;margin-top:13px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
        f'gap:10px;margin-bottom:5px;">'
        f'<span style="font-size:11px;font-weight:700;color:#D4DCEE;'
        f'letter-spacing:0.05em;text-transform:uppercase;">{detail["title"]}</span>'
        f'<a class="hp-link" href="{_clear_point_href()}" style="font-size:15px;'
        f'color:#6B7A9B;text-decoration:none;line-height:1;">&#10005;</a></div>'
        f'{rows}{link}</div>'
    )


def _trend_chart(chart: str, dates: list, values: list, *, colour: str,
                 unit: str = "", decimals: int = 0,
                 floor: float | None = None, cap: float | None = None,
                 date_fmt: str = "%d %b", max_x_ticks: int = 5,
                 height: int = _EMPTY_CHART_HEIGHT) -> str:
    """A dated trend with both axes and one tappable band per day.

    `floor`/`cap` are the scale's real limits, not the data's — a readiness
    axis that rounds up to 110 is claiming a score that cannot exist, and one
    that rounds a resting heart rate down past 0 is worse.
    """
    axis = dash.value_axis(values, ticks=4, floor=floor, cap=cap)
    y_labels = styles.axis_gutter_labels(axis, height)
    svg = styles.trend_chart_svg(
        values, height=height, colour=colour,
        lo=axis["lo"] if axis else None, hi=axis["hi"] if axis else None,
        gridlines=[f for f, _ in y_labels],
    )
    if not svg or not axis:
        return _chart_empty("No historical readings available for this period.", height)

    n = len(values)
    hits = []
    for left, width, i in dash.hit_bands(n, max_bands=n):
        v = values[i]
        reading = f"{v:.{decimals}f}{f' {unit}' if unit else ''}" if v is not None else "no reading"
        hits.append({
            "left": left, "width": width, "href": _chart_href(chart, i),
            "title": f"{dash.format_axis_date(dates[i])} · {reading}",
            "selected": _is_selected(chart, i),
        })
    points = [
        {"x": (i / (n - 1)) if n > 1 else 0.0,
         "y": styles.plot_y_fraction(v, axis["lo"], axis["hi"], height),
         "colour": colour, "selected": _is_selected(chart, i)}
        for i, v in enumerate(values) if v is not None
    ]
    x_labels = dash.x_axis_labels(
        [dash.format_axis_date(d, date_fmt) for d in dates], max_ticks=max_x_ticks)
    return styles.chart_frame(
        [{"svg": svg, "height": height, "y_labels": y_labels,
          "overlay": styles.chart_hits(hits) + styles.chart_points(points)}],
        x_labels=x_labels,
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

# The two skins these panels come in.
#
# _SKIN_HOME is what Readiness and Sleep have always looked like, and is the
# DEFAULT everywhere, so those two screens are bit-identical after this change.
# _SKIN_BOARD is views/insights.py's Strength-screen palette, adopted by the
# STRAIN drill-down only. The values are that screen's _PANEL/_INK/_INK2/_INK3
# and _HAIR — copied rather than imported because views/insights.py is a page
# module and app.py must not import one, and re-declared rather than shared
# because the two screens deliberately differ (see the note in
# views/insights.py: a screen that does not inject _STRENGTH_CSS must own its
# own classes).
# `border` is a whole declaration, not just a colour: "none" is the div default,
# so the home skin cannot shift an existing panel by the 2px a transparent 1px
# border would have added.
_SKIN_HOME: dict[str, str] = {
    "panel": "#131929", "ink": "#D4DCEE", "ink2": "#6B7A9B",
    # "#555" not "#555555" — the same colour, but the exact string
    # _chart_block's subtitle already emitted, so Readiness and Sleep keep
    # byte-identical markup rather than merely identical-looking markup.
    "ink3": "#555", "border": "none", "radius": "12px",
}
_SKIN_BOARD: dict[str, str] = {
    "panel": "#0E1018", "ink": "#F4F6FB", "ink2": "#9AA3B2",
    "ink3": "#5A6377", "border": "1px solid rgba(255,255,255,0.06)",
    "radius": "16px",
}


def _panel(overline: str, body: str, caption: str = "", skin: dict | None = None) -> str:
    """The detail-view panel every block on this screen sits in, factored out
    so a new section can't drift from them.

    `skin` defaults to _SKIN_HOME — the #131929 / 12px surface this screen has
    always used — so every existing call site renders exactly as before."""
    s = skin or _SKIN_HOME
    cap = (f'<div style="font-size:10px;color:{s["ink2"]};margin-top:10px;'
           f'line-height:1.5;">{caption}</div>' if caption else "")
    return (
        f'<div style="background:{s["panel"]};border:{s["border"]};'
        f'border-radius:{s["radius"]};padding:16px 18px;margin-bottom:10px;">'
        f'<div style="font-size:10px;color:{s["ink2"]};letter-spacing:2px;'
        f'text-transform:uppercase;font-weight:600;margin-bottom:10px;">{overline}</div>'
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
    # Optional weight, shown only where the rows carry one. Sleep's seven
    # weights are near-equal and disclosed in its caption; readiness' span
    # 4.5%-22.5%, where "this component is red" means very different things
    # at either end, so the weight belongs on the row itself.
    weight = row.get("weight_display")
    wt = (f'<span style="font-size:10px;color:#4A5568;margin-left:6px;">{weight}</span>'
          if weight else "")
    return (
        f'<div style="padding:9px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">'
        f'<span style="font-size:13px;color:{lbl_col};">{row["label"]}{wt}</span>'
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
            f'{dash.sleep_unscored_reason(_bio_rows_failed)}</div>',
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


# ─── Readiness drill-down blocks ─────────────────────────────────────────────
#  The Readiness card opened to a score arc and a sparkline and nothing else,
#  while compute_readiness is a seven-component weighted average with
#  renormalisation plus a post-hoc alcohol deduction — none of it visible.
#  Structured to match the Sleep drill-down block-for-block; every panel here
#  reuses _panel/_contributor_row/_key_metric_grid/_overnight_panel unchanged.

def _readiness_contributors_block() -> str:
    """The seven components behind our Readiness Score, with weights.

    Pure math over _bio_rows, which is already loaded and cached — computed
    inline for the same reason _sleep_contributors_block is."""
    breakdown = readiness_model.readiness_breakdown(selected_date, _bio_rows)
    if breakdown["score"] == _NOT_COMPUTED:
        return _panel(
            "Contributors",
            '<div style="font-size:12px;color:#8A99A3;line-height:1.5;">'
            f'{dash.readiness_unscored_reason(_bio_rows_failed)}</div>',
        )
    rows = "".join(_contributor_row(r) for r in dash.readiness_breakdown_rows(breakdown))
    caption = " ".join(c for c in (
        dash.readiness_coverage_caption(breakdown),
        dash.readiness_alcohol_caption(breakdown),
    ) if c)
    return _panel("Contributors", rows, caption)


def _readiness_key_metrics_block() -> str:
    """The 2x2 Oura puts on its own Readiness screen: RHR, HRV, body
    temperature deviation, respiratory rate. All four are already stored —
    the first two from the blend, the last two Oura-only."""
    detail = _sleep_details.get(selected_date.isoformat()) or {}
    row = next((r for r in _bio_rows if r.get("date") == selected_date.isoformat()), {})

    def num(v, fmt, suffix=""):
        return "—" if v is None else f"{fmt.format(v)}{suffix}"

    dev = row.get("oura_temperature_deviation")
    return _key_metric_grid([
        {"label": "Resting Heart Rate", "value": num(row.get("resting_heart_rate"), "{:.0f}", " bpm")},
        {"label": "Heart Rate Variability", "value": num(row.get("hrv_ms"), "{:.0f}", " ms")},
        # Signed deliberately: +0.4 and -0.4 are physiologically opposite and
        # an unsigned "0.4 °C" would read as the same reading.
        {"label": "Body Temperature", "value": "—" if dev is None else f"{dev:+.2f} °C"},
        {"label": "Respiratory Rate", "value": num(detail.get("average_breath"), "{:.1f}", " /min")},
    ])


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


def _naps_block(naps: dict | None) -> str:
    """Naps Oura recorded beside the main night, and the day total that
    includes them.

    Rendered only on days that actually have one. The day total is stated
    explicitly because it is the figure readiness and the Sleep Score were
    built from, while every other panel on this screen describes the night
    alone — see dashboard.sleep_naps_display."""
    if naps is None:
        return ""
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:9px;padding:5px 0;font-size:12px;">'
        f'<span style="color:#B9C2D6;">{r["label"]}</span>'
        f'<span style="color:#D4DCEE;margin-left:auto;">{r["duration"]}</span>'
        f'<span style="color:#6B7A9B;width:42px;text-align:right;">{r["efficiency"]}</span></div>'
        for r in naps["rows"]
    )
    noun = "nap" if naps["count"] == 1 else "naps"
    body = (
        f'<div style="font-size:28px;font-weight:700;color:#D4DCEE;">{naps["day_total"]}</div>'
        f'<div style="font-size:11px;color:#6B7A9B;margin-top:2px;">'
        f'{naps["night_total"]} at night plus {naps["nap_total"]} '
        f'across {naps["count"]} {noun}</div>'
        f'<div style="margin-top:12px;">{rows}</div>'
    )
    return _panel("Day total", body,
                  "Readiness and Sleep Score use this total. The stages, "
                  "vitals and efficiency above describe the night only.")


_SLEEP_SOURCE_TITLES = {
    "fused": "Fused (Oura + Garmin)",
    "oura_only": "Oura",
    "garmin_only": "Garmin",
}

# {code: name} — styles.STAGE_BAND stores (colour, name), and everything on the
# click path wants only the name. Derived once rather than unpacked at each of
# the three call sites, so the strip's tooltip, its detail panel and its Y-axis
# labels cannot end up naming the same stage differently.
_STAGE_LABELS = {code: label for code, (_c, label) in styles.STAGE_BAND.items()}


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

    # The window the strips are stretched across. Both are drawn full-width
    # over the SAME span regardless of their own grid (Oura's hypnogram is
    # 30-second, the fused master per-minute, movement 30-second), so one
    # start + one duration describes every tick on either of them — which is
    # what makes a single shared time axis honest rather than approximate.
    start_iso = detail.get("bedtime_start") or fused.get("window_start_utc")
    total_minutes = dash.minutes_between(detail.get("bedtime_start"),
                                         detail.get("bedtime_end"))
    if total_minutes is None and fused.get("minutes"):
        # garmin_only: no Oura sleep period, so the fusion row's own window is
        # the only description of the night that exists.
        try:
            total_minutes = float(fused["minutes"])
        except (TypeError, ValueError):
            total_minutes = None
    x_labels = dash.clock_axis_labels(start_iso, total_minutes, max_ticks=5)

    hyp_height = 56
    hyp_sel = (dash.run_at(codes, _point_index)
               if _point_chart == "hyp" and _point_index is not None else None)
    plots = [{
        "svg": styles.hypnogram_svg(codes, height=hyp_height, rows=True,
                                    highlight=(hyp_sel[0], hyp_sel[1]) if hyp_sel else None),
        "height": hyp_height,
        "y_labels": styles.hypnogram_row_labels(),
        "overlay": styles.chart_hits(
            _strip_hits("hyp", codes, start_iso, total_minutes, _STAGE_LABELS)),
    }]

    movement_plot, movement_note = _movement_strip(fused, start_iso, total_minutes)
    if movement_plot:
        plots.append(movement_plot)

    strip_detail = ""
    for chart_id, strip_codes, labels, kind in (
        ("hyp", codes, _STAGE_LABELS, "Stage"),
        ("mov", str(fused.get("master_movement") or ""), styles.MOVEMENT_LABELS, "Movement"),
    ):
        if _point_chart == chart_id and _point_index is not None and strip_codes:
            strip_detail += _point_detail_block(dash.segment_point_detail(
                strip_codes, _point_index, start_iso=start_iso,
                total_minutes=total_minutes, labels=labels, kind=kind))

    # Wider gutter than the value charts': these axes are labelled with stage
    # and movement NAMES, and the widest ("No motion") measures ~58px in this
    # theme's monospace face where "100" measures 18. Sized to that label
    # rather than left at the default, which pushed it out through the panel's
    # own padding.
    # strip_detail sits directly under the frame, ahead of the legends and
    # source notes — same placement the value charts give it, and the thing a
    # tap opens should be next to what was tapped.
    return (f'<div style="margin-top:14px;">'
            f'{styles.chart_frame(plots, x_labels=x_labels, gutter_px=58)}</div>'
            f'{strip_detail}{styles.stage_legend_html()}{note}{movement_note}')


def _strip_hits(chart: str, codes: str, start_iso, total_minutes,
                labels: dict) -> list[dict]:
    """Tappable bands over a digit-coded strip.

    Uniform bands rather than one per run: a hypnogram has runs as short as a
    single 30-second slot, which is ~0.1% of the night and cannot be tapped on
    a phone. The band resolves to the slot at its centre and the detail then
    reports the whole RUN that slot belongs to, so what opens is still a real
    segment with real start and end times.
    """
    n = len(codes)
    if not n:
        return []
    per_slot = (float(total_minutes) / n) if total_minutes else None
    active = _point_index if _point_chart == chart else None
    out = []
    for left, width, i in dash.hit_bands(n):
        run = dash.run_at(codes, i)
        name = labels.get(run[2], "")
        clock = (dash.format_clock_offset(start_iso, run[0] * per_slot)
                 if per_slot and start_iso else "")
        # Highlight every band the selected RUN covers, so the shaded bands
        # and the outline the SVG draws describe the same segment. The band's
        # own span is checked as well: a hand-edited ?pt= index need not be a
        # band centre, and without it such an index would shade nothing while
        # still opening a detail panel.
        selected = active is not None and (
            run[0] <= active < run[1]
            or int(left * n) <= active < max(int((left + width) * n), int(left * n) + 1)
        )
        out.append({
            "left": left, "width": width, "href": _chart_href(chart, i),
            "title": f"{name} · {clock}" if clock else str(name),
            "selected": selected,
        })
    return out


_MOVEMENT_STRIP_HEIGHT = 34


def _movement_strip(fused: dict, start_iso, total_minutes) -> tuple[dict | None, str]:
    """The fused movement tick strip as a chart_frame plot, or (None, "") when
    the night has none.

    Returns the plot and its caption separately because the caller stacks the
    strip under the hypnogram inside one frame while the captions collect
    below it — keeping both charts on one axis instead of giving each its own.
    """
    codes = str(fused.get("master_movement") or "")
    if not codes:
        return None, ""

    source = str(fused.get("movement_source") or "")
    title = _SLEEP_SOURCE_TITLES.get(source, "Movement")
    shifts = fused.get("movement_position_shifts")
    detail_bits = []
    if source == "fused":
        detail_bits.append("ring resolves small motion, watch confirms whole-body")
    if shifts not in (None, ""):
        detail_bits.append(f"{shifts} position shift{'s' if shifts != 1 else ''}")
    suffix = f" · {' · '.join(detail_bits)}" if detail_bits else ""

    sel = (dash.run_at(codes, _point_index)
           if _point_chart == "mov" and _point_index is not None else None)
    plot = {
        "svg": styles.movement_svg(codes, height=_MOVEMENT_STRIP_HEIGHT,
                                   highlight=(sel[0], sel[1]) if sel else None),
        "height": _MOVEMENT_STRIP_HEIGHT,
        "gap": 4,
        "y_labels": styles.movement_row_labels(),
        "overlay": styles.chart_hits(
            _strip_hits("mov", codes, start_iso, total_minutes, styles.MOVEMENT_LABELS)),
    }
    note = (f'<div style="font-size:10px;color:#6B7A9B;margin-top:6px;line-height:1.5;">'
            f'Movement — <b style="color:#8FCDF0;">{title}</b>{suffix}.</div>'
            f'{styles.movement_legend_html()}')
    return plot, note


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

    out += _naps_block(dash.sleep_naps_display(detail))

    out += _overnight_panel(
        "Lowest heart rate", detail.get("hr_series"), "bpm",
        headline="low", secondary="average", colour="#8FCDF0", detail=detail,
        chart="ohr")
    out += _overnight_panel(
        "Average HRV", detail.get("hrv_series"), "ms",
        headline="average", secondary="high", colour="#6BAF8B", detail=detail,
        chart="ohrv")

    vitals = dash.sleep_vitals_rows(detail, context)
    if vitals:
        out += _panel("Vitals while asleep", _kv_rows(vitals))
    return out


_OVERNIGHT_LABELS = {"low": "Lowest", "high": "Max", "average": "Average"}


_OVERNIGHT_CHART_HEIGHT = 78


def _overnight_panel(overline: str, payload, unit: str, headline: str,
                     secondary: str, colour: str, detail: dict,
                     chart: str = "") -> str:
    """One overnight series as a headline figure plus its shape over the night.

    Omitted entirely when the series is absent rather than drawn as an empty
    box: these columns were only added on 2026-07-31, so every night before
    the Oura tabs were rebuilt genuinely has nothing to plot, and an empty
    chart would imply a flat night rather than no measurement.

    `chart` is the id used for point selection; passing "" leaves the plot
    non-interactive, which is what a caller with no URL to link to needs.
    """
    series = dash.overnight_series(payload)
    if not series["count"]:
        return ""
    height = _OVERNIGHT_CHART_HEIGHT
    axis = dash.value_axis(series["values"], ticks=4, floor=0.0)
    y_labels = styles.axis_gutter_labels(axis, height)
    plot = styles.overnight_chart_svg(
        series["values"], height=height, colour=colour,
        baseline=series["average"],
        lo=axis["lo"] if axis else None, hi=axis["hi"] if axis else None,
        gridlines=[f for f, _ in y_labels],
    )
    if not plot or not axis:
        return ""

    values = series["values"]
    hits, points = [], []
    if chart:
        for left, width, i in dash.hit_bands(len(values)):
            v = values[i]
            hits.append({
                "left": left, "width": width, "href": _chart_href(chart, i),
                "title": f"{v:g} {unit}" if v is not None else "not measured",
                "selected": _is_selected(chart, i),
            })
        # Only the SELECTED sample gets a marker. A night is up to 180 points,
        # and dotting every one turns a line whose whole purpose is its shape
        # into a band of speckle.
        if _point_chart == chart and _point_index is not None:
            i = _point_index
            if 0 <= i < len(values) and values[i] is not None:
                points.append({
                    "x": (i / (len(values) - 1)) if len(values) > 1 else 0.0,
                    "y": styles.plot_y_fraction(values[i], axis["lo"], axis["hi"], height),
                    "colour": colour, "selected": True,
                })

    # Prefer the series' own timestamps; fall back to the night's bedtime
    # window, which is all an older night (stored before the interval and
    # timestamp fields were captured) has.
    x_labels = dash.overnight_axis_labels(series, max_ticks=4)
    if not x_labels:
        start = dash.format_clock(detail.get("bedtime_start"))
        end = dash.format_clock(detail.get("bedtime_end"))
        x_labels = [(0.0, start), (1.0, end)] if start and end else []

    body = styles.chart_frame(
        [{"svg": plot, "height": height, "y_labels": y_labels,
          "overlay": styles.chart_hits(hits) + styles.chart_points(points)}],
        x_labels=x_labels,
    )
    point_detail = (
        dash.overnight_point_detail(series, _point_index, unit=unit)
        if chart and _point_chart == chart and _point_index is not None else None
    )

    big = series[headline]
    small = series[secondary]
    return _panel(
        overline,
        f'<div style="display:flex;align-items:baseline;gap:10px;">'
        f'<span style="font-size:28px;font-weight:700;color:#D4DCEE;">{big:g}</span>'
        f'<span style="font-size:12px;color:#6B7A9B;">{unit}</span>'
        f'<span style="font-size:11px;color:#6B7A9B;margin-left:auto;">'
        f'{_OVERNIGHT_LABELS[secondary]} {small:g} {unit}</span></div>'
        f'<div style="margin-top:12px;">{body}</div>'
        + _point_detail_block(point_detail))


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


_FACEPLATE_DIR = Path(__file__).resolve().parent / "background_templates" / "body_faceplates_v2"


def _region_split_bar_html(data: dict) -> str:
    """The AU share. THE exactly-additive quantity on this screen, which is
    why it leads and why its label says so.

    The athlete's ask was that a hike "adds PROPORTIONALLY more to the
    lowerbody" — and share is the only figure here that carries a proportion
    intact. engine.load_to_strain is logarithmic, so an intended 16:1
    lower:upper localisation shows up as 2.34:1 once through the curve. The
    strain triple below is real, but it is not what answers his question."""
    s = _SKIN_BOARD
    segs, key = "", ""
    for region in data["regions"]:
        meta = _tc.REGION_DISPLAY[region["id"]]
        pct = region["au_pct"] or 0.0
        segs += f'<i style="width:{pct:.1f}%;background:{meta["colour"]};"></i>'
        key += (f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                f'<b style="width:8px;height:8px;border-radius:3px;display:inline-block;'
                f'background:{meta["colour"]};"></b>{meta["short"]} {pct:.0f}%</span>')
    un_pct = data.get("unattributed_pct") or 0.0
    if un_pct > 0:
        segs += f'<i style="width:{un_pct:.1f}%;background:{s["ink3"]};"></i>'
        key += (f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                f'<b style="width:8px;height:8px;border-radius:3px;display:inline-block;'
                f'background:{s["ink3"]};"></b>Unattributed {un_pct:.0f}%</span>')
    # The label changes when coverage is partial. That one word swap is what
    # keeps the additive claim true rather than silently renormalising.
    heading = ("Load share &middot; adds to 100%" if un_pct <= 0
               else "Load share &middot; adds to 100% of MAPPED load")
    return (
        f'<div style="font:600 8.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;'
        f'letter-spacing:.14em;text-transform:uppercase;color:{s["ink3"]};'
        f'margin-bottom:8px;">{heading}</div>'
        f'<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;'
        f'background:rgba(255,255,255,0.06);">{segs}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:9px;'
        f'font-size:11px;color:{s["ink2"]};font-variant-numeric:tabular-nums;">{key}</div>'
    )


def _region_rows_html(data: dict, overall: float | None) -> str:
    """One row per region: name, its own 0-21 reading, a track against 21 with
    the OVERALL drawn on it as a tick, its advisory ACWR, and the faceplate.

    The tick is what makes the non-additivity visible rather than merely
    stated: it lands at the same x on all three tracks, every bar stops short
    of it (regional AU <= total AU and the curve is monotonic, so a region can
    never read above the headline), and the three bars together obviously
    overrun the axis.

    The continuous-figure join views/insights.py:151-153 requires is
    deliberately abandoned here. At this column width the text block is taller
    than two of the three plates, so they would float apart with gaps that read
    as a broken join; each plate gets its own soft container instead."""
    s = _SKIN_BOARD
    tick = ""
    if overall is not None:
        pct = max(0.0, min(100.0, overall / 21.0 * 100.0))
        tick = (f'<u style="position:absolute;left:{pct:.1f}%;top:-4px;bottom:-4px;'
                f'width:1px;text-decoration:none;background:rgba(212,220,238,0.65);"></u>')

    rows = ""
    for region in data["regions"]:
        meta = _tc.REGION_DISPLAY[region["id"]]
        plate = _b64(str(_FACEPLATE_DIR / f'{region["id"]}.png'))
        strain = region["strain"]
        acwr = region["acwr"]
        if strain is None:
            value = f'<span style="color:{s["ink3"]};">&mdash;</span>'
            fill = ""
            dim = "opacity:.22;filter:grayscale(1);"
        else:
            value = (f'{strain:.1f}<u style="text-decoration:none;font-size:11px;'
                     f'color:{s["ink2"]};margin-left:4px;">/21</u>'
                     f'<s style="text-decoration:none;font-size:11px;color:{s["ink2"]};'
                     f'margin-left:9px;">{region["au"]:,.0f} AU &middot; '
                     f'{region["au_pct"]:.0f}%</s>')
            fill = (f'<i style="display:block;height:100%;border-radius:4px;'
                    f'width:{min(100.0, strain / 21.0 * 100.0):.1f}%;'
                    f'background:{meta["colour"]};"></i>')
            dim = ""
        plate_html = (
            f'<div style="width:100%;aspect-ratio:{meta["ratio"]};background-size:100% 100%;'
            f'background-repeat:no-repeat;border-radius:10px;{dim}'
            f'background-image:url(\'{plate}\');"></div>' if plate else
            f'<div style="width:100%;aspect-ratio:{meta["ratio"]};border-radius:10px;'
            f'background:rgba(255,255,255,0.02);"></div>'
        )
        rows += (
            f'<div style="display:grid;grid-template-columns:minmax(0,1fr) 34%;'
            f'gap:12px;align-items:center;padding:10px 0;'
            f'border-bottom:1px solid rgba(255,255,255,0.05);" role="group" '
            f'aria-label="{meta["name"]}, strain {strain if strain is not None else "not available"}">'
            f'<div>'
            f'<div style="font-size:13.5px;font-weight:700;color:{meta["colour"]};">'
            f'{meta["name"]}</div>'
            f'<div style="font-size:25px;font-weight:300;color:{s["ink"]};margin-top:3px;'
            f'line-height:1.05;font-variant-numeric:tabular-nums;">{value}</div>'
            f'<div style="position:relative;height:7px;border-radius:4px;margin:9px 0 8px;'
            f'background:rgba(255,255,255,0.07);">{fill}{tick}</div>'
            f'<div style="font:600 10px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;'
            f'letter-spacing:.05em;color:{acwr["colour"]};">{acwr["value"]}'
            f'<em style="display:block;font-style:normal;font-size:9px;letter-spacing:.04em;'
            f'text-transform:uppercase;opacity:.8;">{acwr["reason"]}</em></div>'
            f'</div>{plate_html}</div>'
        )
    return f'<div>{rows}</div>'


def _region_block(data: dict, overall: float | None, stage: int) -> str:
    """The whole "where it landed" section, or the honest empty state.

    A rest day, a yoga day and a day with no session each get a stated reason
    rather than three zeros — an unmapped region has no number, never a 0.0,
    the same rule the flexibility ladder applies to an unmeasured muscle."""
    s = _SKIN_BOARD
    if not data.get("has_split"):
        names = data.get("unmapped_names") or []
        listed = ("" if not names else
                  f'<div style="font-size:11px;color:{s["ink3"]};margin-top:8px;'
                  f'line-height:1.6;">Not in the region map: '
                  f'{" &middot; ".join(names[:8])}'
                  f'{f" +{len(names) - 8} more" if len(names) > 8 else ""}</div>')
        return _panel(
            "Where it landed",
            f'<div style="font-size:12.5px;color:{s["ink2"]};line-height:1.6;">'
            f'No regional split for this day. Either nothing was logged, the '
            f'number above is the 7-day stand-in, or none of what was logged '
            f'maps to a body region &mdash; so there is nothing to divide. '
            f'The strain figure above is unaffected.</div>{listed}',
            "An exercise with no region mapping is excluded from every sector "
            "total, here and on the Strength screen.",
            skin=s,
        )

    gap = data.get("additivity_gap")
    gap_txt = (f" They total {gap + (overall or 0):.1f} against {overall:.1f}."
               if gap is not None and overall is not None else "")
    caveat = ""
    frac = data.get("attributed_fraction")
    if data.get("attributed_is_low") and frac is not None:
        caveat = (f' Attributed from {frac * 100:.0f}% of logged session time, '
                  f'so the split rests on a thin sample of the session.')
    unmapped = data.get("unmapped_names") or []
    unmapped_txt = ("" if not unmapped else
                    f' {len(unmapped)} item(s) have no region mapping and sit '
                    f'in the unattributed share: {" &middot; ".join(unmapped[:5])}'
                    f'{f" +{len(unmapped) - 5} more" if len(unmapped) > 5 else ""}.')

    body = (
        _region_split_bar_html(data)
        + f'<div style="font:600 8.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;'
          f'letter-spacing:.14em;text-transform:uppercase;color:{s["ink3"]};'
          f'margin:16px 0 8px;">Strain &middot; same 0&ndash;21 curve</div>'
        + f'<div style="border-left:2px solid #BFA06A;padding:1px 0 1px 11px;'
          f'margin:0 0 6px;font-size:11.5px;line-height:1.55;color:#9AA6BE;">'
          f'{_sr.NON_ADDITIVE_NOTE}{gap_txt}</div>'
        + _region_rows_html(data, overall)
    )
    ceiling = _rules_ceiling(stage)
    return _panel(
        "Where it landed",
        body,
        (f'Reported, never enforced &mdash; a regional ACWR informs, it never '
         f'caps volume. Stage {stage} ceiling {ceiling:.2f}.{caveat}{unmapped_txt} '
         f'The region weights are <b>{data["shares_basis"]}</b> (v{data["shares_version"]}): '
         f'authored for this athlete, not measured.'),
        skin=s,
    )


def _rules_ceiling(stage: int) -> float:
    from services import rules as _rules
    return _rules.STAGE_CONSTRAINTS.get(stage, {}).get("acwr_ceiling", 1.3)


def _metric_detail(view: str) -> str:
    # The strain drill-down is the one screen in the Strength-board palette.
    # Readiness and Sleep keep _SKIN_HOME, so their markup is byte-identical.
    skin = _SKIN_BOARD if view == "strain" else _SKIN_HOME

    def _chart_block(title: str, headline: str, subtitle: str, chart_html: str,
                     detail_html: str = "") -> str:
        """The surface every chart on this screen sits in — the same panel as
        _panel, with room for a headline figure and a subtitle above the plot."""
        sub = (f'<div style="font-size:10px;color:{skin["ink3"]};margin-bottom:9px;">{subtitle}</div>'
               if subtitle else '<div style="height:6px;"></div>')
        return (
            f'<div style="background:{skin["panel"]};border:{skin["border"]};'
            f'border-radius:{skin["radius"]};padding:16px 18px;margin-bottom:10px;">'
            f'<div style="font-size:10px;color:{skin["ink2"]};letter-spacing:2px;text-transform:uppercase;'
            f'font-weight:600;margin-bottom:4px;">{title}</div>'
            f'<div style="font-size:28px;font-weight:700;color:{skin["ink"]};margin-bottom:4px;">{headline}</div>'
            f'{sub}{chart_html}{detail_html}</div>'
        )

    def _trend_block(chart: str, title: str, unit: str, values: list, color: str,
                     floor: float | None = None, cap: float | None = None) -> str:
        """7-day, day-of-week-labelled block — used for Strain's supplementary
        HRV/RHR context (the live 7-day biometric blend, not persisted
        history)."""
        dates = [selected_date - timedelta(days=6 - i) for i in range(7)]
        current = next((v for v in reversed(values) if v is not None), None)
        val_str = f"{current:.0f} {unit}" if current is not None else "—"
        detail = (dash.trend_point_detail(dates, values, _point_index,
                                          unit=unit, label=title)
                  if _point_chart == chart and _point_index is not None else None)
        return _chart_block(
            title, val_str, "",
            _trend_chart(chart, dates, values, colour=color, unit=unit,
                         floor=floor, cap=cap, date_fmt="%a", max_x_ticks=7),
            _point_detail_block(detail),
        )

    def _history_trend_block(chart: str, title: str, metric: str, unit: str,
                             dates: list, values: list, color: str, hist_key: str,
                             floor: float | None = None, cap: float | None = None,
                             decimals: int = 0) -> str:
        """30-day trend from the PERSISTED Metrics History tab (see
        Repository.get_metrics_history) — a fixed record, unlike the 7-day
        blocks above which recompute live from Oura/Garmin's raw tabs.

        A selected point also lists that day's OTHER persisted metrics, which
        is the question this chart provokes and could not previously answer:
        a readiness dip is only interpretable next to what sleep and strain
        did on the same day."""
        current = next((v for v in reversed(values) if v is not None), None)
        val_str = f"{current:.{decimals}f}{unit}" if current is not None else "—"
        range_label = (f"{dash.format_axis_date(dates[0])} – "
                       f"{dash.format_axis_date(dates[-1])}") if dates else ""
        detail = extra = None
        if _point_chart == chart and _point_index is not None:
            detail = dash.trend_point_detail(dates, values, _point_index,
                                             unit=unit, decimals=decimals,
                                             label=metric)
            if detail:
                row = next((r for r in _metrics_hist
                            if r.get("date") == detail["open_date"]), None)
                extra = dash.metrics_history_rows(row, exclude=hist_key)
        return _chart_block(
            title, val_str, range_label,
            _trend_chart(chart, dates, values, colour=color, unit=unit,
                         decimals=decimals, floor=floor, cap=cap),
            _point_detail_block(detail, extra or (), open_view=view),
        )

    # pre_blocks render BEFORE the 30-day trend, extra_blocks after. Sleep's
    # contributor breakdown has to lead — it explains the number in the
    # header — whereas strain's supplementary context reads as a footnote.
    pre_blocks = ""
    # hist_floor/hist_cap are the SCALE's limits, not the window's: readiness
    # and sleep are 0-100 by construction and strain is 0-21 (engine.au_to_strain
    # clamps to it), so the rounded axis must never claim a value outside them.
    hist_decimals = 0
    if view == "readiness":
        col, disp, lbl, _, _, _ = dash.readiness_meta(_readiness_score)
        detail_label = f"READINESS · {date_label}"
        hist_key, hist_unit, hist_title, hist_color = "readiness_score", "", "Readiness Trend", "#6BAF8B"
        hist_metric = "Readiness"
        hist_floor, hist_cap = 0.0, 100.0
        # Order mirrors Oura's own Readiness screen: contributors, then key
        # metrics, then the overnight autonomic series. The HR/HRV panels are
        # the same _overnight_panel the Sleep drill-down uses — Oura puts them
        # on Readiness, and they are autonomic-recovery signals, so they earn
        # a place on both rather than being moved off Sleep.
        _r_detail = _sleep_details.get(selected_date.isoformat()) or {}
        pre_blocks = (
            _readiness_contributors_block()
            + _readiness_key_metrics_block()
            + _overnight_panel("Lowest heart rate", _r_detail.get("hr_series"), "bpm",
                               headline="low", secondary="average",
                               colour="#8FCDF0", detail=_r_detail, chart="ohr")
            + _overnight_panel("Average HRV", _r_detail.get("hrv_series"), "ms",
                               headline="average", secondary="high",
                               colour="#6BAF8B", detail=_r_detail, chart="ohrv")
        )
        extra_blocks = ""
    elif view == "sleep":
        col, disp, lbl, _, _ = dash.sleep_meta(_sleep_score, _sleep_need, _sleep_base_window)
        _today_wake_adj = _wake_adjustments.get(selected_date.isoformat(), 0.0)
        detail_label = f"SLEEP · {date_label}" + (" · ADJUSTED" if _today_wake_adj else "")
        hist_key, hist_unit, hist_title, hist_color = "sleep_score", "", "Sleep Score Trend", "#4FC3F7"
        hist_metric = "Sleep Score"
        hist_floor, hist_cap = 0.0, 100.0
        pre_blocks = _sleep_contributors_block() + _sleep_night_blocks()
        extra_blocks = ""
    else:
        col, disp, lbl, _, _ = dash.strain_meta(_display_strain, is_rolling=_strain_is_rolling)
        detail_label = "STRAIN · 7D AVG" if _strain_is_rolling else f"STRAIN · {date_label}"
        hist_key, hist_unit, hist_title, hist_color = "strain", "", "Strain Trend", "#BFA06A"
        hist_metric = "Strain"
        # WHERE IT LANDED leads, above the 30-day trend: it explains the number
        # in the header, the way Sleep's contributor breakdown does. Every read
        # below happens only on this branch, so the three-card Home stream
        # never pays for it.
        _region_data: dict = {"has_split": False, "unmapped_names": []}
        try:
            _regions = _region_au_history()
            _acwr = _sr.region_acwr(
                _regions["rows"], _current_stage, today=date.today(),
                stage_start=_stage_start_cached(),
            )
            _region_data = dash.compute_region_strain_snapshot(
                selected_date, _regions["rows"], _current_stage,
                overall_snapshot=_snapshot, provenance=_regions,
                acwr_results=_acwr,
            )
        except Exception:
            # A failed read must not take the strain number down with it — the
            # panel states its own absence instead.
            pass
        pre_blocks = _region_block(_region_data, _display_strain, _current_stage)
        # 21.0 is the same ceiling the strain arc is drawn against above
        # (_arc_svg(_display_strain, 21, ...)) and the one engine.load_to_strain
        # saturates at.
        hist_floor, hist_cap = 0.0, 21.0
        # One decimal: strain spans 0-21, so a whole-number axis rounds a
        # 1.4-point difference between two sessions away to nothing.
        hist_decimals = 1
        extra_blocks = (
            _strain_source_block()
            + _trend_block("hrv7", "Heart Rate Variability", "ms", _hrv_7d,
                           "#6BAF8B", floor=0.0)
            + _trend_block("rhr7", "Resting Heart Rate", "bpm", _rhr_7d,
                           "#BFA06A", floor=0.0)
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
        + _history_trend_block("hist", hist_title, hist_metric, hist_unit,
                               hist_dates, hist_values, hist_color, hist_key,
                               floor=hist_floor, cap=hist_cap,
                               decimals=hist_decimals)
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

/* styles.enable_chart_links()'s zero-height iframe. Streamlit still gives its
   element container the standard vertical gap, which on a drill-down shows up
   as a stray band of empty page under the last chart. Home renders no other
   component, so collapsing them all here is exact rather than a broad guess. */
[data-testid="stElementContainer"]:has(> [data-testid="stIFrame"]),
[data-testid="stElementContainer"]:has(> iframe) {
    height:0 !important; min-height:0 !important; margin:0 !important;
    padding:0 !important; overflow:hidden !important;
}
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

# A failed biometric read blanks every card on this page — the arcs go grey
# and read "No Readings", which is indistinguishable from a night you simply
# did not wear the ring. Say which one it is, once, at the top. Most likely
# cause is Sheets' 60-operations-per-minute quota during the startup sync's
# write burst (see _run_startup_sync's note); reloading in a moment fixes it.
if _bio_rows_failed:
    st.warning(
        "**Could not load your biometric readings.** The scores below are "
        "blank because the read failed, not because the data is missing — "
        "reload in a moment.",
        icon="⚠️",
    )

if view in ("strain", "readiness", "sleep"):
    st.markdown(_metric_detail(view), unsafe_allow_html=True)
    # Only the drill-downs carry chart links, so the iframe this installs is
    # never paid for on the three-card Home stream.
    styles.enable_chart_links()
    if view == "sleep":
        _render_wake_time_control(selected_date)
else:
    st.markdown(_card_readiness + _card_strain + _card_sleep, unsafe_allow_html=True)
if not _oura_sync_ok and _oura_sync_err:
    st.caption("Oura sync unavailable — will retry next visit.")
if not _garmin_sync_ok and _garmin_sync_err:
    st.caption("Garmin sync unavailable — will retry next visit.")
# A per-step failure surfaces above. This is the case those two can't cover:
# the whole chain blew up before any step reported, so every status is still
# its (True, None) default and the page would claim everything is fine.
_sync_run_error = repo.get_sync_runner().last_error()
if _sync_run_error:
    st.caption("Device sync failed to run — will retry next visit.")
nav.inject("home")


def _run_startup_sync() -> None:
    """Refresh the device tabs. Deliberately the LAST thing in the script.

    Streamlit streams each widget as it executes, so everything above is
    already on screen by the time this runs — the user sees their night in
    ~5s rather than staring at "No Readings" for ~77s while it finishes.

    FOREGROUND or BACKGROUND depends on whether today's numbers are already
    on screen:

      not settled  run inline and wait. This is the first open of the day:
                   last night's Oura row is not in Sheets yet, so the cards
                   above are showing yesterday. Going to the background here
                   would mean today's numbers do not appear until the NEXT
                   time the app is opened, which is the one case where
                   waiting is clearly right.
      settled      hand it to a worker thread and return immediately. The
                   numbers are already up; the sync is topping up data that
                   may not even have changed. Inline, it kept the Streamlit
                   session busy for up to ~77s after the page looked
                   finished — every nav tap in that window did nothing.

    Either way the cadence is the same 2 hours per step, durably marked, and
    triggered by opening the app rather than by a timer.

    Ordering between the six lives in Repository.run_home_syncs so the two
    paths cannot drift apart.

    Deliberately NO cache-clear and NO st.rerun() afterwards. The first
    version did both, on the reasoning that the page above had rendered
    against pre-sync data. It made things strictly worse and the screenshots
    showed it: the page painted correctly, then the rerun replaced it with
    "No Readings" and "Could not load this night's detail". Clearing every
    cached read forces a re-read of six tabs at the exact moment the sync
    has just spent a burst of writes, which walks into Sheets'
    60-operations-per-minute quota — so the rerun reliably re-read into
    failure. Leaving it out is also what makes the day's numbers STABLE:
    once shown they stay put, and are replaced only when a later read
    genuinely returns something different.
    """
    runner = repo.get_sync_runner()

    if not _day_settled:
        # Inline: the numbers aren't up yet and the user is waiting for them.
        results = runner.run_now()
        st.session_state["_sync_status_oura"] = results.get("oura", (True, None))
        st.session_state["_sync_status_garmin"] = results.get("garmin", (True, None))
        return

    # Settled: fire and forget. start() returns False when a run is already
    # in flight, which is the normal case on a rerun and not an error.
    runner.start()
    results = runner.results()
    if results:
        st.session_state["_sync_status_oura"] = results.get("oura", (True, None))
        st.session_state["_sync_status_garmin"] = results.get("garmin", (True, None))

    # Deliberately NO cache-clear and NO st.rerun() here.
    #
    # The first version did both, on the reasoning that the page above had
    # rendered against pre-sync data and should be refreshed. It made things
    # strictly worse and the screenshots showed it: the page painted
    # correctly, then the rerun replaced it with "No Readings" and "Could not
    # load this night's detail". Clearing every cached read forces a full
    # re-read of six tabs at the exact moment the sync has just spent a burst
    # of writes, which walks into Sheets' 60-operations-per-minute quota — so
    # the rerun reliably re-read into failure.
    #
    # Nothing is lost by leaving it out. The syncs' purpose is to have the
    # data ready, and the caches expire on their own TTL, so the freshly
    # written night appears on the next visit rather than a few seconds later.
    # That is the same trade this whole function already makes: briefly stale
    # beats briefly absent.


_run_startup_sync()
