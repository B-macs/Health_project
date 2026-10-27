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
import today
import styles
import training_constants as _tc
from services import background_writer
from services import dashboard as dash
from services import engine
from services import home
from services import navigation
from services import plan as plan_svc
from services import readiness as readiness_model
from services import sleep_score as sleep_score_model
from services import sleep_screen
from services import strain_screen
from services import sync_policy
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
#
# This is also the first touch of the Repository in any script run, which is
# where the local copy is rebuilt from Supabase at the process's first start.
_repository = repo.get_repository()
# An open pulls the local copy again when it is older than the freshness limit
# (the engine writes to Supabase too). Never waits, and only under a
# Streamlit server: no test may run the app's device-facing work.
if st.runtime.exists():
    repo.refresh_copy_if_stale()

# THE RETIRED APP (rebuild Phase 9, switch step 8): once the engine is the background
# writer, every page says so, and every write is refused with the same words
# (Repository._refuse_if_retired). Read live, at most once a minute, and only under a
# Streamlit server.
@st.cache_data(ttl=60, show_spinner=False)
def _app_retired() -> bool:
    return background_writer.current(repo.get_repository()) == background_writer.ENGINE


if st.runtime.exists() and _app_retired():
    st.error(background_writer.RETIRED_TEXT, icon="🔒")

if _repository.offline:
    _built = _repository.datastore_built_at() or "unknown"
    st.warning(
        f"**Offline** — reading a local snapshot, not the live store. "
        f"Snapshot built {_built}. Writes are disabled and today's data may "
        f"be missing. Unset `HEALTH_DATASTORE_PATH` to go live.",
        icon="🗄️",
    )

# ─── SPA Router ───────────────────────────────────────────────────────────────
# Primary: session_state["_nav_page"] set by nav trigger buttons (WebSocket rerun,
#          no page reload, same connection).
# Fallback: st.query_params["page"] for direct URL access and first load.
# An unknown page is Home (services/navigation.py).
_page = navigation.resolve_page(st.session_state.get("_nav_page"), st.query_params.get("page"))

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
# The day arrows, drill-down cards and FAB are BUTTONS now, and views/ is fully
# converted (CLAUDE.md Key Rule 17). Three in-chart anchors remain and are page
# RELOADS: styles.py's hit bands and the two controls in _point_detail_block.
# All three are anchors inside an HTML string another element renders, so there
# is nowhere to put a widget; tests/test_spa_navigation.py's _KNOWN map lists
# them, and carries the warning about the JS bridge that was tried for them and
# does not work.
if st.query_params.get("page") != _page:
    st.query_params["page"] = _page

# Clear the nav's once-per-run guard before anything can draw it — this is the
# top of every script run, and the flag lives in session_state so it survives
# the run that set it. See nav._RUN_FLAG.
nav.start_run()

# ⚠ nav.inject RUNS IN A `finally`, AND THAT IS THE WHOLE POINT. The bottom bar
# is the only way off a page, so a view that fails must not take the navigation
# down with it. Before this, any exception inside render() left the screen
# showing an error box and NO nav buttons at all — the athlete
# was stranded on the broken page with hand-editing the URL as the only escape.
# Reported 2026-08-18 against insights' UnserializableReturnValueError, which is
# a separate bug; this is the reason that bug was unrecoverable rather than
# merely annoying.
#
# It covers st.stop() too. StopException and RerunException derive from
# BaseException, not Exception, so they skipped the old inline `nav.inject(...)`
# exactly as an error did. views/training.py already works around that with ten
# explicit nav.inject calls of its own — and the one before its plan-start
# st.stop() (after seeding phase 1) was missing, so that screen has been
# rendering with no nav at all. nav.inject is idempotent within a run, so those
# ten still win and keep their own active-tab argument.
#
# ⚠ STILL UNCOVERED: the HOME page. Its own nav.inject sits at the very bottom
# of this module's top-level code, so an exception in the home body skips it the
# same way. Wrapping ~2000 lines of module-level statements is not a change to
# make in the same pass as a bug fix; the escape from a broken Home is still
# ?page=insights in the URL.
_view = None
if _page == "training":
    from views import training as _view
elif _page == "insights":
    from views import insights as _view
elif _page == "checkin":
    from views import checkin as _view

if _view is not None:
    styles.inject_css()
    try:
        _view.render()
    finally:
        try:
            nav.inject("" if _page == "checkin" else _page)
        except Exception:
            # Never let a failure in the escape hatch replace the error it
            # exists to escape from — that would swap a diagnosable traceback
            # for a misleading one pointing at the nav bar.
            pass
    st.stop()

# ─── Constants ────────────────────────────────────────────────────────────────

_BG_DIR = Path(__file__).parent / "background_templates"

# Deterministic card → background image (fixed mapping, never changes between sessions)
_CARD_BG: dict[str, Path] = {
    "readiness": _BG_DIR / "mountain.jpg",
    "strain":    _BG_DIR / "wp13002291.jpg",
    "sleep":     _BG_DIR / "Calm-iphone-11.jpg",
}

_NOT_COMPUTED     = readiness_model.NOT_COMPUTED

# ─── URL state ───────────────────────────────────────────────────────────────

_today = date.today()
_params = st.query_params

if "_home_date_opened" not in st.session_state:
    # The first run of a browser session: a past day survives only when it was
    # picked today, i.e. this is a reconnect (dash.home_date_on_open). Anything
    # else — the Home Screen app reopening an address from 17 September — opens
    # on today, and the stale keys leave the address.
    st.session_state["_home_date_opened"] = True
    selected_date = dash.home_date_on_open(
        _params.get("d"), _params.get(dash.HOME_DATE_SET_ON_PARAM), _today)
    if selected_date == _today:
        for _stale in ("d", dash.HOME_DATE_SET_ON_PARAM):
            if _stale in st.query_params:
                del st.query_params[_stale]
else:
    try:
        selected_date = min(date.fromisoformat(_params.get("d", str(_today))), _today)
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

# Strain drill-down, rest days only: show the PRIOR WEEK's regional shape
# instead of a blank panel. In the URL for the same reason as `pt` above, and
# off by default — a 7-day mean is a different measurement from a session, so
# it is something the athlete opens rather than something the screen asserts.
_strain_window_week = _params.get("rw") == "1"


def _go(**params) -> None:
    """Navigate the Home screen by URL state, WITHOUT reloading the page.

    Use as an st.button on_click. A key set to None is removed.

    This is what replaced the <a href="?d=..."> links — see CLAUDE.md Key
    Rule 17. The state still lives in the URL, deliberately, for the reconnect
    reason the router note above gives; what changed is HOW it gets there.
    Assigning to st.query_params enqueues a page_info_changed ForwardMsg and
    the frontend rewrites the address bar through the history API, so the
    rerun runs over the existing websocket — no reload, no reconnect, no cold
    caches (streamlit/runtime/state/query_params.py::_send_query_param_msg).
    An anchor with the identical href tears the whole page down instead.

    Callbacks run BEFORE the script reruns, so the values written here are
    what the `_params` reads at the top of this file see on the next pass.

    A day passes through dash.home_date_params: today writes no ?d= at all,
    and a past day writes the day it was picked on beside it, which is what
    lets the next session tell a reconnect from a reopened old address.
    """
    if "d" in params:
        chosen = params.pop("d")
        params.update(dash.home_date_params(chosen, date.today()))
    for key, value in params.items():
        if value is None:
            if key in st.query_params:
                del st.query_params[key]
        else:
            st.query_params[key] = str(value)


# CSS restyling the buttons that replaced those links so they look exactly
# like the markup they came from. Same approach as nav.py's bottom bar and
# views/insights.py's BioAge cards: st.button(key="x") emits a .st-key-x
# class on its wrapper, which is the documented styling hook.
#
# The three metric cards are the one place a button cannot BE the visual: a
# 460px card containing an SVG arc gauge cannot live inside a button's label,
# which is markdown text. There the card HTML renders as before and an
# invisible button is pulled over it. If that CSS ever fails to apply, the
# button simply appears below its card as an ordinary labelled button — still
# working, merely ugly — rather than the card becoming unclickable.
_NAV_BUTTON_CSS = """<style>
/* ── Metric cards: invisible full-card hit target ───────────────────────── */
.st-key-card_readiness, .st-key-card_strain, .st-key-card_sleep {
    margin-top: -464px !important;   /* card is 460px tall + 4px margin */
    margin-bottom: 0 !important;
    position: relative !important;
    z-index: 5 !important;
}
.st-key-card_readiness button, .st-key-card_strain button, .st-key-card_sleep button {
    width: 100% !important; height: 464px !important; min-height: 0 !important;
    background: transparent !important; border: none !important;
    box-shadow: none !important; padding: 0 !important;
    color: transparent !important;
}
.st-key-card_readiness button p, .st-key-card_strain button p,
.st-key-card_sleep button p {
    opacity: 0 !important;           /* kept in the DOM for screen readers */
    margin: 0 !important;
}
.st-key-card_readiness button:hover, .st-key-card_strain button:hover,
.st-key-card_sleep button:hover { background: rgba(255,255,255,0.03) !important; }
.st-key-card_readiness button:focus, .st-key-card_strain button:focus,
.st-key-card_sleep button:focus { outline: none !important; box-shadow: none !important; }

/* ── Fixed date-header arrows ───────────────────────────────────────────── */
.st-key-hdr_prev, .st-key-hdr_next, .st-key-hdr_back {
    position: fixed !important; top: 0 !important; z-index: 901 !important;
    width: 44px !important; margin: 0 !important;
}
.st-key-hdr_prev, .st-key-hdr_back { left: max(14px, calc((100vw - 480px)/2 + 14px)) !important; }
.st-key-hdr_next { right: max(14px, calc((100vw - 480px)/2 + 14px)) !important; }
/* Drill-down day arrows: BOTH on the right, because the back button owns the
   left. Same 44px cells, so dnext sits at the edge and dprev one cell in. */
.st-key-hdr_dprev, .st-key-hdr_dnext {
    position: fixed !important; top: 0 !important; z-index: 901 !important;
    width: 44px !important; margin: 0 !important;
}
.st-key-hdr_dnext { right: max(14px, calc((100vw - 480px)/2 + 14px)) !important; }
.st-key-hdr_dprev { right: max(58px, calc((100vw - 480px)/2 + 58px)) !important; }
.st-key-hdr_dprev button, .st-key-hdr_dnext button {
    width: 44px !important; height: 56px !important; min-height: 0 !important;
    background: transparent !important; border: none !important;
    box-shadow: none !important; padding: 0 !important;
}
.st-key-hdr_dprev button p, .st-key-hdr_dnext button p {
    font-size: 26px !important; color: #D4DCEE !important; line-height: 1 !important;
    margin: 0 !important;
}
.st-key-hdr_dnext button:disabled p { color: #2A2A3A !important; }
.st-key-hdr_dprev button:focus, .st-key-hdr_dnext button:focus {
    outline: none !important; box-shadow: none !important;
}
.st-key-hdr_prev button, .st-key-hdr_next button, .st-key-hdr_back button {
    width: 44px !important; height: 56px !important; min-height: 0 !important;
    background: transparent !important; border: none !important;
    box-shadow: none !important; padding: 0 !important;
}
.st-key-hdr_prev button p, .st-key-hdr_next button p, .st-key-hdr_back button p {
    font-size: 26px !important; color: #D4DCEE !important; line-height: 1 !important;
    margin: 0 !important;
}
.st-key-hdr_back button p { font-size: 22px !important; color: #6B7A9B !important; }
.st-key-hdr_next button:disabled p { color: #2A2A3A !important; }
.st-key-hdr_prev button:focus, .st-key-hdr_next button:focus,
.st-key-hdr_back button:focus { outline: none !important; box-shadow: none !important; }

/* ── Check-in FAB ───────────────────────────────────────────────────────── */
.st-key-fab_checkin {
    position: fixed !important; top: 69px !important;
    right: max(20px, calc((100vw - 480px)/2 + 16px)) !important;
    z-index: 900 !important; width: 52px !important; margin: 0 !important;
}
.st-key-fab_checkin button {
    width: 52px !important; height: 52px !important; min-height: 0 !important;
    border-radius: 50% !important; background: #FFFFFF !important;
    border: none !important; padding: 0 !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.45) !important;
}
.st-key-fab_checkin button p {
    font-size: 28px !important; color: #0B0F1E !important;
    font-weight: 300 !important; line-height: 1 !important; margin: 0 !important;
}
.st-key-fab_checkin button:hover { background: #EDEFF5 !important; }
.st-key-fab_checkin button:focus { outline: none !important; box-shadow: 0 4px 20px rgba(0,0,0,0.45) !important; }

/* ── Back to today (only while a past day shows) ────────────────────────── */
.st-key-go_today { display: flex !important; justify-content: center !important;
    margin: 0 0 8px 0 !important; }
.st-key-go_today button {
    min-height: 0 !important; padding: 5px 14px !important; border-radius: 14px !important;
    background: transparent !important; border: 1px solid #1E2840 !important;
}
.st-key-go_today button p { font-size: 12px !important; color: #8FCDF0 !important;
    margin: 0 !important; letter-spacing: 0.3px !important; }
.st-key-go_today button:focus { outline: none !important; box-shadow: none !important; }

/* No .st-key-detail_back rules: the in-panel back control was REMOVED rather
   than converted (see _detail_header), because the fixed header carries a real
   back button for those three views and is on screen whatever the scroll. */
</style>"""

# Never a day after today; the arrows step one day (home.day_bounds).
selected_date, prev_date, _after = home.day_bounds(selected_date, _today)
is_today    = (selected_date == _today)
date_label  = home.date_label(selected_date, _today)
next_date   = selected_date + timedelta(days=1)
can_go_next = _after is not None

# ─── Data fetching ────────────────────────────────────────────────────────────

# EVERY WINDOW BELOW ENDS ON THE DAY SHOWN, and each cache is keyed by that day
# (services/home.py's windows; inventory faults F8 and F9). They counted back
# from the server's today, so a day more than 60 days back read "not scored"
# and blamed the ring, and for half an hour after midnight the windows still
# ended yesterday.

@st.cache_data(ttl=1800, show_spinner=False)
def _bio_rolling(end_iso: str, days: int = home.BIO_DAYS) -> list[dict]:
    # engine.py/readiness.py still work on plain dicts -- asdict() converts
    # the typed BiometricRecord back to the exact shape they expect.
    return [asdict(r) for r in repo.get_repository().get_biometric_rolling(
        days=days, today=date.fromisoformat(end_iso))]


@st.cache_data(ttl=1800, show_spinner=False)
def _au_history(end_iso: str, days: int = home.AU_DAYS) -> list[dict]:
    return repo.get_repository().get_daily_session_au_weighted(
        days, today=date.fromisoformat(end_iso))


@st.cache_data(ttl=1800, show_spinner=False)
def _metrics_history_rolling(end_iso: str, days: int = home.HISTORY_DAYS) -> list[dict]:
    """Persisted Readiness/Sleep%/Strain history (Repository.
    get_metrics_history) for the Readiness/Sleep/Strain card drill-downs'
    trend sparklines — a fixed record, unlike the live recompute this page
    otherwise always does for `selected_date` itself."""
    return repo.get_repository().get_metrics_history(
        start=home.window_start(date.fromisoformat(end_iso), days), end=end_iso)


@st.cache_data(ttl=1800, show_spinner=False)
def _wake_time_adjustments_rolling(end_iso: str, days: int = home.HISTORY_DAYS
                                   ) -> tuple[dict[str, float], dict[str, str]]:
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
    start = home.window_start(date.fromisoformat(end_iso), days)
    # The SOURCE comes too: on a fused night the fusion figure wins, which the
    # wake-time stepper must know (sleep_screen.wake_control, fault F5).
    return repo.get_repository().get_effective_wake_adjustments(start=start, end=end_iso)


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
def _current_stage_cached() -> int:
    return repo.get_repository().get_current_stage()


@st.cache_data(ttl=1800, show_spinner=False)
def _region_au_history(end_iso: str, days: int = strain_screen.REGION_DAYS) -> dict:
    """Per-region AU for the strain drill-down — upper/core/lower plus an
    `unattributed` bucket, summing exactly to each day's own weighted AU.

    Deliberately its OWN fetch rather than widening _au_history: this is
    called only from the strain drill-down, so the three-card Home stream
    never pays for it. Opening a drill-down is a deliberate click that can
    afford a read, which is the same trade the dropped Home snapshot made
    when it declines to cache hr_detail.

    31 days so the 30-day trend window is fully covered, ending on the day
    shown, like Home's other reads (services/home.py).
    """
    return repo.get_repository().get_daily_region_au(days, today=date.fromisoformat(end_iso))


@st.cache_data(ttl=1800, show_spinner=False)
def _stage_start_cached(end_iso: str):
    """Start date of the phase active ON THE DAY SHOWN — scopes the per-region
    ACWR's chronic baseline to that stage, exactly as views/insights.py does
    for the overall one. None during a reassessment gap, where engine.acwr
    falls back to the flat 28-day calendar window. As of the day shown, like
    every other Home read (fault F27, 2026-10-19: it was the phase active on
    the server's today, so a past day in an earlier block got a stage start
    after itself)."""
    return plan_svc.current_stage_start(repo.get_repository().get_phases(),
                                        date.fromisoformat(end_iso))


@st.cache_data(ttl=1800, show_spinner=False)
def _session_hr_rolling(end_iso: str, days: int = home.HISTORY_DAYS) -> list[dict]:
    """Persisted per-session heart-rate load (Repository.
    get_session_hr_history) — Edwards'-TRIMP-derived strain for any day whose
    logged session matched a Garmin activity. Days with no row simply aren't
    in this list, and the strain for those falls back to RPE."""
    start = home.window_start(date.fromisoformat(end_iso), days)
    return repo.get_repository().get_session_hr_history(start=start)


@st.cache_data(ttl=1800, show_spinner=False)
def _watch_cardio_rolling(end_iso: str, days: int = home.HISTORY_DAYS) -> dict:
    """The watch's walks and runs no session holds (Repository.get_watch_cardio):
    they count on the day walked (2026-10-20), as on the phone."""
    start = home.window_start(date.fromisoformat(end_iso), days)
    return repo.get_repository().get_watch_cardio(start=start, end=end_iso)


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
    _bio_rows = _bio_rolling(selected_date.isoformat())   # 60d: the 56-night sleep baseline
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

# ⚠ THE NIGHT DETAIL AND THE BIOMETRIC ROWS READ THE SAME OURA SLEEP-PERIODS
# TAB, AND ARE CACHED SEPARATELY. _bio_rolling runs on every Home render, so
# it is usually taken BEFORE the day's device sync lands last night;
# _sleep_night_details runs only when a drill-down is opened, which is usually
# AFTER. The first morning open therefore rendered a complete night — total
# sleep, time in bed, efficiency, the whole architecture — underneath a header
# reading "No Readings" and a Contributors panel asserting "Oura recorded no
# sleep period for this night". Both statements were false, and the panel
# immediately below them was drawing the night that disproved them.
#
# When the detail read holds a night the biometric rows do not, the biometric
# rows are provably the older of the two, so re-read them. This is NOT the
# blanket st.cache_data.clear() Key Rule 14 forbids: ONE cached function,
# cleared only on positive evidence that it is stale, at most once per date
# per session, and only on a screen the user deliberately opened. A failed
# re-read keeps the rows we already have rather than emptying the screen.
_bio_rows_stale = dash.has_night_without_biometric_row(
    _bio_rows, _sleep_details, selected_date)
if _bio_rows_stale and not _bio_rows_failed:
    _refresh_key = f"_bio_refreshed_{selected_date.isoformat()}"
    if not st.session_state.get(_refresh_key):
        st.session_state[_refresh_key] = True
        try:
            _bio_rolling.clear()
            _bio_rows = _bio_rolling(selected_date.isoformat())
        except Exception:
            pass
    # Re-checked, not assumed: if the row is still absent after the re-read,
    # the contributors panel must still not blame the ring for a night it can
    # see on screen.
    _bio_rows_stale = dash.has_night_without_biometric_row(
        _bio_rows, _sleep_details, selected_date)

_au_rows = []
try:
    _au_rows = _au_history(selected_date.isoformat())
except Exception:
    pass

_metrics_hist = []
try:
    _metrics_hist = _metrics_history_rolling(selected_date.isoformat())
except Exception:
    pass

# Is TODAY's dashboard settled — readiness and sleep both already persisted?
# Decides whether _run_startup_sync at the bottom of this file waits for the
# device sync or hands it to a worker thread. Always keyed on the real today,
# never selected_date: browsing back to a past day must not change what the
# CURRENT day still needs. A failed read leaves this False, which errs
# towards syncing in the foreground — the safe direction, since the cards are
# blank in that case anyway.
try:
    _today_hist = _metrics_hist if is_today else _metrics_history_rolling(_today.isoformat())
except Exception:
    _today_hist = []
_today_metrics_row = next(
    (r for r in _today_hist if r.get("date") == _today.isoformat()), None,
)
_day_settled = dash.snapshot_is_complete(_today_metrics_row)

_wake_adjustments: dict[str, float] = {}
_wake_sources: dict[str, str] = {}
try:
    _wake_adjustments, _wake_sources = _wake_time_adjustments_rolling(selected_date.isoformat())
except Exception:
    pass

_hr_rows: list[dict] = []
try:
    _hr_rows = _session_hr_rolling(selected_date.isoformat())
except Exception:
    pass

_walks: dict = {}
try:
    _walks = _watch_cardio_rolling(selected_date.isoformat())
except Exception:
    pass

# An unreadable stage is None, never stage 1: strain is then not scored and
# says why (inventory fault F7; it moved the number through the stage's
# scaling and could print a Stage 1 ceiling).
try:
    _current_stage = _current_stage_cached()
except Exception:
    _current_stage = None


# ─── Computed values ──────────────────────────────────────────────────────────

# The three numbers, from services/home.py (the phone's API computes the same
# ones): compute_daily_metrics_snapshot, shared with
# Repository.sync_metrics_history, with the progressive sleep baseline
# (7→14→28→56 nights) computed once. The rest-day load is counted back from
# the DAY SHOWN, as each stored trend point is, so a past day's card agrees
# with its own point (inventory fault F8; it counted back from the server's
# today, i.e. described the load heading into today under a past day's card).
_snapshot = home.snapshot(home.HomeReads(
    day=selected_date, bio_rows=_bio_rows, bio_failed=_bio_rows_failed,
    au_rows=_au_rows, metrics_history=_metrics_hist,
    wake_adjustments=_wake_adjustments, hr_rows=_hr_rows, stage=_current_stage,
    walks=_walks))
_sleep_need         = _snapshot["sleep_need_hours"]
_sleep_base_window  = _snapshot["sleep_base_window"]
_readiness_score    = _snapshot["readiness_score"]
_sleep_score        = _snapshot["sleep_score"]
_display_strain     = _snapshot["strain"]
_strain_is_rolling  = _snapshot["strain_is_rolling"]

# The 7 days ending on the day shown (dash.fill_7day picks them from the rows).
_hrv_7d = dash.fill_7day(_bio_rows, "hrv_ms", selected_date)
_rhr_7d = dash.fill_7day(_bio_rows, "resting_heart_rate", selected_date)

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


# These are full navigations (see styles.enable_chart_links' docstring for why
# the JS bridge that would have avoided that does not work), so whatever they
# omit is DISCARDED. Every piece of drill-down URL state has to be listed here
# or a chart-point tap silently resets it — `rw` was, and tapping a point on
# the strain drill-down closed the rest-day week panel underneath the athlete.
def _url_state(**overrides) -> str:
    state = {"d": selected_date, "view": view}
    if _strain_window_week:
        state["rw"] = 1
    state.update(overrides)
    # The day goes through the same rule as _go: a full navigation starts a
    # new session, which keeps a past day only if the address says it was
    # picked today (dash.home_date_on_open).
    state.update(dash.home_date_params(state.pop("d", None), _today))
    return "?" + "&".join(f"{k}={v}" for k, v in state.items() if v is not None)


def _chart_href(chart: str, index: int) -> str:
    return _url_state(pt=dash.point_selection_key(chart, index))


def _clear_point_href() -> str:
    return _url_state(pt=None)


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
        link = (f'<a class="hp-link" '
                f'href="{_url_state(d=detail["open_date"], view=open_view, pt=None)}" '
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

def _verdict_line(v) -> str:
    """WHAT TRAINING IS ABOUT TO SAY, said here first.

    ⚠ 2026-08-23, the athlete: "I saw 66 but then saw reduce load in training
    ... I dont want to be suprised when I see the deload statement in
    training." Home showed the smoothed trend and Training decided on the raw
    score, and Training displays no readiness figure at all — so the two
    screens shared no number to disagree about. This is that fix: the SAME
    string services/sessions.py hands the training banner, printed here.

    The HRV note sits on its own line in neutral ink, never a warning tone, so
    a run cannot be mistaken for the load decision it did not cause.
    """
    if not v.has_something_to_say:
        return ""
    rows = ""
    # The reading the engine named (2026-10-13): Training prints it as the
    # headline, and a baseline-drift day — every tile green, load reduced — had
    # no reason on Home at all.
    if v.cause:
        rows += (f'<div style="font-size:13px;color:#D4DCEE;line-height:1.55;'
                 f'margin-bottom:5px;">{v.cause}</div>')
    if v.banner_text:
        rows += (f'<div style="font-size:13px;color:#B9C2D6;line-height:1.55;">'
                 f'{v.banner_text}</div>')
    if v.hrv_note:
        rows += (f'<div style="font-size:12.5px;color:#8A99A3;line-height:1.5;'
                 f'margin-top:{"7px" if v.banner_text else "0"};">{v.hrv_note}</div>')
    return (
        f'<div style="background:#131929;border-left:3px solid {v.tone};'
        f'border-radius:6px;padding:12px 14px;margin:-2px 0 14px;">{rows}</div>'
    )


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
    gauge_size: int = 220,
    badge: str = "",
    badge_tone: str = "",
    score_pair: tuple | None = None,
) -> str:
    scrim  = "linear-gradient(180deg,rgba(0,0,0,0.18) 0%,rgba(0,0,0,0.60) 50%,rgba(0,0,0,0.80) 100%)"
    bg_css = (
        f'background-image:url(\'{bg_data_url}\');background-size:cover;background-position:center;'
        if bg_data_url else "background:#1A2238;"
    )
    # TWO NUMBERS SIDE BY SIDE, EACH WITH ITS OWN TITLE, when score_pair is
    # given — the athlete's ask on 2026-08-23 ("show them both ... with daily
    # and trend as the titles of each"). Absent, this renders the single 58px
    # figure exactly as before, so the strain and sleep cards are unchanged.
    #
    # Readiness now passes a pair on EVERY day, blanks included (2026-08-25),
    # so `score_display` is unused there. It is still what strain and sleep
    # render, and still what readiness would fall back to if the pair were ever
    # dropped — so it stays a required argument rather than becoming dead.
    if score_pair:
        (_lab_a, _val_a), (_lab_b, _val_b) = score_pair
        _col = ("font-size:9px;letter-spacing:.16em;font-family:ui-monospace,monospace;"
                "color:rgba(255,255,255,0.58);margin-bottom:1px;")
        number_block = (
            f'<div style="display:flex;gap:22px;align-items:flex-start;justify-content:center;">'
            f'<div><div style="{_col}">{_lab_a}</div>'
            f'<div style="font-size:42px;font-weight:800;color:#fff;line-height:1;'
            f'letter-spacing:-1.5px;">{_val_a}</div></div>'
            f'<div><div style="{_col}">{_lab_b}</div>'
            f'<div style="font-size:42px;font-weight:800;color:rgba(255,255,255,0.72);'
            f'line-height:1;letter-spacing:-1.5px;">{_val_b}</div></div>'
            f'</div>'
        )
    else:
        number_block = (
            f'<div style="font-size:58px;font-weight:800;color:#fff;line-height:1;'
            f'letter-spacing:-2px;">{score_display}</div>'
        )
    badge_block = (
        f'<div><span style="display:inline-block;font:600 9.5px/1.7 ui-monospace,monospace;'
        f'letter-spacing:.12em;text-transform:uppercase;padding:2px 9px;border-radius:20px;'
        f'margin-top:9px;background:{badge_tone}2E;color:{badge_tone};">{badge}</span></div>'
    ) if badge and badge_tone else ""
    gauge_block = (
        f'<div style="position:relative;width:{gauge_size}px;height:{gauge_size}px;margin:0 auto;">'
        f'{gauge_svg}'
        f'<div style="position:absolute;top:42%;left:50%;transform:translate(-50%,-50%);'
        f'text-align:center;pointer-events:none;">'
        f'{number_block}'
        f'<div style="font-size:13px;font-weight:500;color:{status_color};margin-top:6px;">'
        f'{status_label}</div>'
        f'{badge_block}'
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
    # No click wrapper: the card is made clickable by an invisible button laid
    # over it at the render site (see _NAV_BUTTON_CSS and CLAUDE.md Key Rule
    # 17). It used to return an <a href> here, which reloaded the whole app on
    # every tap.
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


def _sleep_breakdown() -> dict:
    """The night's Sleep Score breakdown, computed once per render.

    Computed inline rather than cached: it is pure math over _bio_rows, which
    is already loaded and cached. Hashing 60 rows to memoise a microsecond of
    arithmetic would cost more than it saves. Held in a module global because
    TWO things now read it — the contributors panel, and the gate that decides
    whether any of the night panels render at all — and re-deriving it in the
    second would let the two disagree about whether the night was scored."""
    global _sleep_breakdown_cache
    if _sleep_breakdown_cache is None:
        _sleep_breakdown_cache = sleep_score_model.sleep_score_breakdown(
            selected_date, _bio_rows, wake_time_adjustments=_wake_adjustments,
        )
    return _sleep_breakdown_cache


_sleep_breakdown_cache: dict | None = None


def _sleep_is_scored() -> bool:
    """Whether this night has a Sleep Score at all — the ONE gate every night
    panel on this screen answers to. See _sleep_night_blocks."""
    return _sleep_breakdown()["score"] != _NOT_COMPUTED


def _sleep_contributors_block() -> str:
    """The seven contributors behind the Sleep Score.

    dashboard.sleep_meta's copy has told users to "check the breakdown for
    what's holding it back" since it was written, while no breakdown existed
    anywhere in the app. This is it."""
    breakdown = _sleep_breakdown()
    if breakdown["score"] == _NOT_COMPUTED:
        # A plain line, NOT a panel with a CONTRIBUTORS heading over it: there
        # are no contributors to head. Everything else on the screen is gone
        # too (see _sleep_night_blocks), so this line and the day arrows in the
        # header are the whole screen.
        return (
            '<div style="font-size:12px;color:#8A99A3;line-height:1.6;'
            'padding:2px 2px 8px;">'
            f'{dash.sleep_unscored_reason(_bio_rows_failed, _bio_rows_stale)}'
            '<br><span style="color:#6B7A9B;">Tap ‹ at the top to see an '
            'earlier night.</span></div>'
        )
    rows = "".join(_contributor_row(r) for r in dash.sleep_breakdown_rows(breakdown))
    # Total sleep and Efficiency here include the wake-time correction the
    # score used (Sleep Score MODEL_VERSION 4), and the figures below are the
    # same corrected ones; the caption names it (sleep_screen.contributors_caption).
    caption = sleep_screen.contributors_caption(
        dash.sleep_coverage_caption(breakdown), breakdown.get("wake_adjustment_minutes") or 0.0)
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
    # The breakdown of the SAME score the card shows (home.readiness_daily):
    # on today the engine's own rows, so the card and these rows cannot
    # disagree (inventory fault F6: they were computed from 60 rows while the
    # card showed the 14-row score).
    breakdown = _readiness_breakdown or readiness_model.readiness_breakdown(
        selected_date, _bio_rows)
    if breakdown["score"] == _NOT_COMPUTED:
        return _panel(
            "Contributors",
            '<div style="font-size:12px;color:#8A99A3;line-height:1.5;">'
            f'{dash.readiness_unscored_reason(_bio_rows_failed, _bio_rows_stale)}</div>',
        )
    rows = "".join(_contributor_row(r) for r in dash.readiness_breakdown_rows(breakdown))
    # ⚠ THE MASTHEAD ABOVE AND THESE ROWS GRADE DIFFERENT NUMBERS, and until
    # 2026-08-23 nothing on screen said so. The card shows
    # compute_readiness_trend (an EMA over ~14 days); these contributors
    # decompose the RAW compute_readiness for the night. On 2026-08-23 that was
    # 66 against 56.2 — the gap that produced "I saw 66 but then saw reduce load
    # in training". _sleep_contributors_block already solved this exact shape
    # with a one-line caption; this is its readiness twin.
    caption = home.readiness_contributors_caption(_readiness_score, breakdown)
    return _panel("Contributors", rows, caption)


def _readiness_key_metrics_block() -> str:
    """The 2x2 Oura puts on its own Readiness screen: RHR, HRV, body
    temperature deviation, respiratory rate. All four are already stored —
    the first two from the blend, the last two Oura-only."""
    detail = _sleep_details.get(selected_date.isoformat()) or {}
    row = next((r for r in _bio_rows if r.get("date") == selected_date.isoformat()), {})
    return _key_metric_grid(home.readiness_key_metrics(row, detail))


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
    # The fused master when there is one, else Oura's own sequence, and a
    # failed fusion read named as such (sleep_screen.strip_source).
    _src = sleep_screen.strip_source(fused, detail, _sleep_fusion_loaded)
    codes, title, phantom = _src["codes"], _src["title"], _src["phantom"]
    if not codes:
        return ('<div style="color:#444;font-size:12px;font-style:italic;padding:14px 0;'
                'text-align:center;">No stage timeline recorded for this night.</div>')

    if _src["note"] == "phantom":
        # ⚠ This used to end "Display only; the score above uses Oura." That
        # was false and had been for as long as fusion fed
        # get_effective_wake_adjustments: phantom_wake_minutes reaches
        # services/sleep_score.py as a wake-time adjustment, so the score above
        # is computed on exactly these minutes. As of 2026-08-25 every figure
        # on the screen is, which is what makes one sentence enough.
        note = (f'<div style="font-size:10px;color:#6B7A9B;margin-top:8px;line-height:1.5;">'
                f'<b style="color:#8FCDF0;">{title}</b> · {phantom} min of Oura wake '
                f'counted as sleep — Garmin saw no movement. Everything on this '
                f'screen, the score included, is this fused night.</div>')
    elif _src["note"] == "watch":
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
    # A watch-only night has no Oura sleep period, so the fusion row's own
    # window is the only description of the night (sleep_screen.strip_window).
    start_iso, total_minutes = sleep_screen.strip_window(detail, fused, dash.minutes_between)
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
    caption = sleep_screen.movement_caption(fused)
    if caption is None:
        return None, ""
    codes, title = caption["codes"], caption["title"]
    suffix = f" · {' · '.join(caption['details'])}" if caption["details"] else ""

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
    rows = []
    for stage in sleep_screen.watch_only_stages(fused):
        code, mins = stage["code"], stage["minutes"]
        pct = f"{stage['pct']:.0f} %" if stage["pct"] is not None else "—"
        rows.append(
            f'<div style="display:flex;align-items:center;gap:9px;padding:5px 0;font-size:12px;">'
            f'<span style="width:26px;height:6px;border-radius:3px;flex:none;'
            f'background:{styles.STAGE_BAND[code][0]};"></span>'
            f'<span style="color:#B9C2D6;width:52px;">{styles.STAGE_BAND[code][1]}</span>'
            f'<span style="color:#D4DCEE;">{dash.format_duration(mins * 60)}</span>'
            f'<span style="color:#6B7A9B;margin-left:auto;">{pct}</span></div>')
    return "".join(rows)


def _sleep_night_blocks() -> str:
    """Key metrics, sleep debt, architecture and vitals for the selected
    night. Everything here reads the Oura values the score itself used, so
    the numbers under the score always explain that score.

    ⚠ ALL OR NOTHING, and the gate is the SCORE — athlete, 2026-08-25:
    "I want the sleep to be fully blank until the data is there, I should be
    able to review yesterdays sleep by toggling to yesterday if I want that."

    A night detail can exist while the score does not (the two are separate
    reads of the same tab, taken at different moments), and this screen used
    the detail alone: it drew a full night — total sleep, time in bed,
    efficiency, the whole architecture — underneath a header reading "No
    Readings". Half a screen is worse than none of it, because the reader has
    no way to tell which half to believe. So the score decides for everything:
    no score, no night panels, and the day arrows in the header are how you go
    and look at a night that has one."""
    detail = _sleep_details.get(selected_date.isoformat())
    context = _sleep_context.get(selected_date.isoformat(), {})
    fused = _sleep_fusion_rows.get(selected_date.isoformat()) or {}
    mode = sleep_screen.screen_mode(_sleep_is_scored(), fused, detail, _sleep_details_loaded)
    if mode != sleep_screen.SCORED:
        if mode == sleep_screen.WATCH_ONLY:
            fused_only = fused
            # The ONE exception, and it earns it by saying so in its own text:
            # the ring was not worn, the watch has the night, and the panel
            # states in terms that there is no Sleep Score and that only the
            # timeline below it is real. Nothing here is presented as scoring.
            return _panel(
                "Time asleep",
                '<div style="font-size:11px;color:#6B7A9B;line-height:1.5;">'
                'No Oura ring reading for this night, so there is no Sleep Score — '
                'every contributor it is built from is an Oura measurement. '
                'Garmin recorded the night, so the stage timeline below is real.</div>'
                + _hypnogram_strip(None)
                + f'<div style="margin-top:12px;">{_garmin_only_stage_rows(fused_only)}</div>')
        if mode == sleep_screen.DETAIL_FAILED:
            # The read failed. Silently rendering nothing here would be
            # indistinguishable from "this night has no sleep data", which is
            # a different and much more alarming statement.
            return _panel(
                "Night detail",
                '<div style="font-size:12px;color:#8A99A3;line-height:1.5;">'
                'Could not load this night&rsquo;s detail — try again shortly.</div>')
        # BLANK, or a scored night without a detail row: nothing below the score.
        return ""

    # EVERY FIGURE ON THIS SCREEN IS THE CORRECTED NIGHT — athlete, 2026-08-25
    # (the fused night) — and the score above used the same correction (Sleep
    # Score MODEL_VERSION 4). The stepper's manual correction lands here too. Time in bed, heart rate, HRV, breathing and temperature
    # pass through. See dashboard.sleep_night_figures.
    _key = selected_date.isoformat()
    manual = (float(_wake_adjustments.get(_key) or 0.0)
              if _wake_sources.get(_key) == sleep_screen.MANUAL else 0.0)
    figures = dash.sleep_night_figures(detail, fused, manual)
    out = _key_metric_grid(dash.sleep_key_metrics(detail, fused, manual))
    fusion_caption = dash.sleep_fusion_caption(figures)
    if fusion_caption:
        out += (f'<div style="font-size:10px;color:#6B7A9B;line-height:1.5;'
                f'margin:-4px 2px 12px;">{fusion_caption}</div>')

    debt = dash.sleep_debt_display(
        readiness_model.sleep_debt_hours(_bio_rows, selected_date))
    out += _sleep_debt_block(debt)

    # stage_minutes off the fusion row, so these durations describe the SAME
    # sequence the strip above them draws. Without it a fused night showed a
    # fused strip over Oura's numbers.
    legend = dash.sleep_stage_legend(detail, dash.sleep_stage_minutes(detail, fused))
    stage_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:9px;padding:5px 0;font-size:12px;">'
        f'<span style="width:26px;height:6px;border-radius:3px;flex:none;'
        f'background:{styles.STAGE_BAND[k][0]};"></span>'
        f'<span style="color:#B9C2D6;width:52px;">{r["label"]}</span>'
        f'<span style="color:#D4DCEE;">{r["duration"]}</span>'
        f'<span style="color:#6B7A9B;margin-left:auto;">{r["pct"]}</span></div>'
        for r, k in zip(legend, ("4", "3", "2", "1"))
    )
    asleep = dash.format_duration(figures.get("total_seconds")) or "—"
    in_bed = dash.format_duration(figures.get("time_in_bed_seconds")) or "—"
    out += _panel(
        "Time asleep",
        f'<div style="font-size:28px;font-weight:700;color:#D4DCEE;">{asleep}</div>'
        f'<div style="font-size:11px;color:#6B7A9B;margin-top:2px;">Total duration {in_bed}</div>'
        + _hypnogram_strip(detail)
        + f'<div style="margin-top:12px;">{stage_rows}</div>',
    )

    out += _naps_block(dash.sleep_naps_display(detail))

    out += _overnight_panels(detail)

    vitals = dash.sleep_vitals_rows(detail, context)
    if vitals:
        out += _panel("Vitals while asleep", _kv_rows(vitals))
    return out


_OVERNIGHT_CHART_HEIGHT = 78
#: Each overnight series' colour and chart id; which series and which figures
#: lead are sleep_screen.OVERNIGHT_PANELS.
_OVERNIGHT_DRAW = {"hr_series": ("#8FCDF0", "ohr"), "hrv_series": ("#6BAF8B", "ohrv")}


def _overnight_panels(detail: dict) -> str:
    """The two overnight series, as Oura shows them on both screens."""
    return "".join(
        _overnight_panel(heading, detail.get(key), unit, headline=big, secondary=small,
                         colour=_OVERNIGHT_DRAW[key][0], detail=detail,
                         chart=_OVERNIGHT_DRAW[key][1])
        for heading, key, unit, big, small in sleep_screen.OVERNIGHT_PANELS)


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
    x_labels = sleep_screen.overnight_axis(
        dash.overnight_axis_labels(series, max_ticks=4), detail, dash.format_clock)

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
        f'{sleep_screen.OVERNIGHT_LABELS[secondary]} {small:g} {unit}</span></div>'
        f'<div style="margin-top:12px;">{body}</div>'
        + _point_detail_block(point_detail))


def _strain_source_block() -> str:
    """Which method produced today's strain, and the HR detail behind it when
    there was one — so a fall back to RPE-only is visible rather than silent
    (the explicit ask in item 17)."""
    info = strain_screen.strain_source(_snapshot)
    if info is None:
        return ""
    label = info["label"]
    tint, icon = ("#8A99A3", "○") if info["kind"] == "rpe" else ("#6BAF8B", "●")
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:11px;color:#8A99A3;margin-top:4px;">'
        f'<span>{name}</span><span style="color:#C8CAD0;">{val}</span></div>'
        for name, val in info["hr_rows"])
    if info["blend"]:
        hr_strain, rpe_strain, hr_weight = info["blend"]
        rows += (
            f'<div style="font-size:10px;color:#6B7A9B;margin-top:8px;">'
            f'HR {hr_strain} · RPE {rpe_strain} → blended at {hr_weight}% HR</div>'
        )

    return (
        f'<div style="background:#1A2026;border-radius:12px;padding:12px 14px;margin:14px 0;">'
        f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;'
        f'text-transform:uppercase;margin-bottom:6px;">Strain source</div>'
        f'<div style="font-size:13px;color:{tint};font-weight:600;">{icon} {label}</div>'
        f'{rows}</div>'
    )


_FACEPLATE_DIR = Path(__file__).resolve().parent / "background_templates" / "body_faceplates_v2"


def _region_split_bar_html(panel: dict) -> str:
    """The AU share. THE exactly-additive quantity on this screen, which is
    why it leads and why its label says so.

    The athlete's ask was that a hike "adds PROPORTIONALLY more to the
    lowerbody" — and share is the only figure here that carries a proportion
    intact. engine.load_to_strain is logarithmic, so an intended 16:1
    lower:upper localisation shows up as 2.34:1 once through the curve. The
    strain triple below is real, but it is not what answers his question."""
    s = _SKIN_BOARD

    # SEGMENTS WITH GAPS AND NO TRACK BEHIND THEM, on purpose. This bar always
    # spans the full width — it is a PARTITION of the day, not a level — and it
    # sits directly above three region tracks that ARE partial fills of an
    # 0-21 scale. Drawn as one continuous fill inside a track it read as a
    # gauge pinned at maximum, which is the first thing a reader said about it.
    # The gaps and the absent track are what make it read as a divided whole.
    def _seg(pct: float, colour: str) -> str:
        return (f'<i style="flex:0 1 {pct:.1f}%;min-width:3px;height:100%;'
                f'border-radius:2px;background:{colour};"></i>')

    segs, key = "", ""
    for region in panel["regions"]:
        meta = _tc.REGION_DISPLAY[region["id"]]
        pct = region["au_pct"]
        segs += _seg(pct, meta["colour"])
        key += (f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                f'<b style="width:8px;height:8px;border-radius:3px;display:inline-block;'
                f'background:{meta["colour"]};"></b>{meta["short"]} {pct:.0f}%</span>')
    un_pct = panel["unattributed_pct"]
    if un_pct > 0:
        segs += _seg(un_pct, s["ink3"])
        key += (f'<span style="display:inline-flex;align-items:center;gap:6px;">'
                f'<b style="width:8px;height:8px;border-radius:3px;display:inline-block;'
                f'background:{s["ink3"]};"></b>Unattributed {un_pct:.0f}%</span>')
    # The label changes when coverage is partial. That one word swap is what
    # keeps the additive claim true rather than silently renormalising.
    heading = ("Load share &middot; adds to 100% of MAPPED load" if panel["mapped_only"]
               else "Load share &middot; adds to 100%")
    return (
        f'<div style="font:600 8.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;'
        f'letter-spacing:.14em;text-transform:uppercase;color:{s["ink3"]};'
        f'margin-bottom:8px;">{heading}</div>'
        f'<div style="display:flex;gap:3px;height:10px;">{segs}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:9px;'
        f'font-size:11px;color:{s["ink2"]};font-variant-numeric:tabular-nums;">{key}</div>'
    )


def _region_rows_html(panel: dict) -> str:
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
    if panel["tick_pct"] is not None:
        tick = (f'<u style="position:absolute;left:{panel["tick_pct"]:.1f}%;top:-4px;bottom:-4px;'
                f'width:1px;text-decoration:none;background:rgba(212,220,238,0.65);"></u>')

    rows = ""
    for region in panel["regions"]:
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
                    f'width:{region["fill_pct"]:.1f}%;'
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


# The rest-day toggle is a real st.button, not an anchor — see
# tests/test_spa_navigation.py. An anchor pointing at the identical target
# tears the page down and reconnects the websocket; assigning to
# st.query_params through _go() reruns over the existing one. This CSS makes
# the button look like the control the panel wants, using the .st-key-<key>
# hook the same way _NAV_BUTTON_CSS already does for the metric cards.
_WEEK_TOGGLE_CSS = """<style>
.st-key-strain_week { margin-top:-6px; margin-bottom:14px; }
.st-key-strain_week button {
    background:transparent !important; border:1px solid #5A6377 !important;
    color:#9AA3B2 !important; border-radius:9px !important;
    font:600 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace !important;
    letter-spacing:.12em !important; text-transform:uppercase !important;
    padding:10px 14px !important; width:auto !important; min-height:0 !important;
}
.st-key-strain_week button:hover { color:#F4F6FB !important;
    border-color:#9AA3B2 !important; }
.st-key-strain_week button[kind="primary"] {
    background:rgba(217,102,58,.12) !important;
    border-color:rgba(217,102,58,.5) !important; color:#D9663A !important; }
</style>"""


def _render_week_toggle(data: dict, showing_week: bool) -> None:
    """Rest days only: open the prior week's regional shape, or close it again.

    Off by default and opened deliberately, because a 7-day mean is a
    different measurement from a session — the screen should not assert it as
    though it were today's split."""
    if not data.get("can_show_window"):
        return
    st.markdown(_WEEK_TOGGLE_CSS, unsafe_allow_html=True)
    st.button(
        "Hide the week" if showing_week else "Show the week's shape",
        key="strain_week",
        type="primary" if showing_week else "secondary",
        on_click=_go,
        kwargs={"rw": None if showing_week else 1},
        help=("Back to the day, which logged no session"
              if showing_week else
              "Split the last 7 days by region — the load already carried in"),
    )


def _region_block(data: dict, overall: float | None, stage: int) -> str:
    """The whole "where it landed" section, or the honest empty state.

    A rest day, a yoga day and a day with no session each get a stated reason
    rather than three zeros — an unmapped region has no number, never a 0.0,
    the same rule the flexibility ladder applies to an unmeasured muscle.

    A rest day is the one blank the athlete can open: the week behind it is
    real load, already carried, and _render_week_toggle offers it."""
    s = _SKIN_BOARD
    panel = strain_screen.region_panel(data, overall, stage)

    if panel["state"] == "empty":
        # No list of the exercises without a body area (the owner, 2026-10-20: it
        # "doesn't give me any details about strain").
        listed = ""
        reason = (
            "No session logged for this day, so there is no day to divide. "
            "The number above is this day's own: its watch walks, or 0."
            if panel["reason"] == "rest_day" else
            "No regional split for this day. Either nothing was logged, or "
            "none of what was logged maps to a body region &mdash; so there "
            "is nothing to divide. The strain figure above is unaffected."
        )
        return _panel(
            "Where it landed",
            f'<div style="font-size:12.5px;color:{s["ink2"]};line-height:1.6;">'
            f'{reason}</div>{listed}',
            "An exercise with no region mapping is excluded from every sector "
            "total, here and on the Strength screen.",
            skin=s,
        )

    week = panel["week"]
    gap_txt = (f" They total {panel['regions_total']:.1f} against {overall:.1f}."
               if panel["regions_total"] is not None else "")
    caveat = ""
    if panel["thin_sample_pct"] is not None:
        caveat = (f' Attributed from {panel["thin_sample_pct"]:.0f}% of logged session time, '
                  f'so the split rests on a thin sample of the session.')
    unmapped_txt = ""   # no list of exercises without a body area (the owner, 2026-10-20)

    # A 7-day mean and a single session look alike and are not the same
    # measurement, so the week says so in three places: the panel title, the
    # strain sub-heading, and a line of its own. The mean also sits far lower
    # on the log curve, where it is steepest, so the three values compress
    # toward each other — the share is what stays comparable.
    week_note = ("" if not week else
                 f'<div style="font-size:11.5px;line-height:1.55;color:{s["ink2"]};'
                 f'margin:0 0 12px;">These are the seven days before today, averaged '
                 f'&mdash; the load already carried in, before any training. '
                 f'{panel["window_days"]} of those 7 days had a session. '
                 f'A weekly mean sits low on the strain curve, where it is steepest, '
                 f'so the three readings crowd together; the share above does not.</div>')

    body = (
        week_note
        + _region_split_bar_html(panel)
        + f'<div style="font:600 8.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;'
          f'letter-spacing:.14em;text-transform:uppercase;color:{s["ink3"]};'
          f'margin:16px 0 8px;">'
          f'{"Weekly average" if week else "Strain"} &middot; same 0&ndash;21 curve</div>'
        + f'<div style="border-left:2px solid #BFA06A;padding:1px 0 1px 11px;'
          f'margin:0 0 6px;font-size:11.5px;line-height:1.55;color:#9AA6BE;">'
          f'{_sr.NON_ADDITIVE_NOTE}{gap_txt}</div>'
        + _region_rows_html(panel)
    )
    # The ceiling from rules.STAGE_CONSTRAINTS only (Key Rule 3): none named
    # for an unknown stage, where a copied 1.3 used to stand in.
    ceiling_txt = (f' Stage {stage} ceiling {panel["ceiling"]:.2f}.'
                   if panel["ceiling"] is not None else "")
    return _panel(
        "Where it landed &mdash; last 7 days" if week else "Where it landed",
        body,
        (f'Reported, never enforced &mdash; a regional ACWR informs, it never '
         f'caps volume.{ceiling_txt}{caveat}{unmapped_txt} '
         f'The region weights are <b>{panel["shares_basis"]}</b> (v{panel["shares_version"]}): '
         f'authored for this athlete, not measured.'),
        skin=s,
    )


def _detail_header(detail_label: str, colour: str, display: str, tier: str) -> str:
    """The drill-down's own masthead — overline, THE headline number, and the
    tier word under it.

    Extracted from _metric_detail rather than left inline because this is where
    the overall strain value lives: the region panel below states shares and
    three regional readings, and the number all of them are read against is
    here. Anything rendering this screen outside app.py — a design review, a
    walkthrough — needs the real markup rather than a copy that can drift.

    No back control: the fixed header carries a real back BUTTON for these
    three views, and being position:fixed it is on screen however far down the
    panel you have scrolled, so a second one here was redundant as well as slow
    (a page reload — CLAUDE.md Key Rule 17)."""
    return (
        f'<div style="display:flex;align-items:center;margin-bottom:20px;">'
        f'<div>'
        f'<div style="font-size:10px;color:#6B7A9B;letter-spacing:2px;'
        f'text-transform:uppercase;margin-bottom:2px;">{detail_label}</div>'
        f'<div style="font-size:30px;font-weight:800;color:{colour};'
        f'line-height:1;">{display}</div>'
        f'<div style="font-size:12px;color:#6B7A9B;margin-top:2px;">{tier}</div>'
        f'</div>'
        f'</div>'
    )


def _metric_detail_parts(view: str) -> tuple[str, str]:
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
        col, disp, lbl, _, _, _ = dash.readiness_meta(
            _readiness_today if _readiness_today is not None else _readiness_score)
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
            + _overnight_panels(_r_detail)
        )
        extra_blocks = ""
    elif view == "sleep":
        col, disp, lbl, _, _ = dash.sleep_meta(_sleep_score, _sleep_need, _sleep_base_window)
        _wake_view = sleep_screen.wake_display(selected_date, _wake_adjustments,
                                               home.trend_window(selected_date))
        detail_label = f"SLEEP · {date_label}" + (" · ADJUSTED" if _wake_view["adjusted"] else "")
        hist_key, hist_unit, hist_title, hist_color = "sleep_score", "", "Sleep Score Trend", "#4FC3F7"
        hist_metric = "Sleep Score"
        hist_floor, hist_cap = 0.0, 100.0
        pre_blocks = _sleep_contributors_block() + _sleep_night_blocks()
        extra_blocks = ""
    else:
        col, disp, lbl, _, _ = dash.strain_meta(_display_strain, rest_day=bool(_snapshot.get("rest_day")))
        _card_label, detail_label = strain_screen.strain_labels(_strain_is_rolling, date_label)
        hist_key, hist_unit, hist_title, hist_color = "strain", "", "Strain Trend", "#BFA06A"
        hist_metric = "Strain"
        # WHERE IT LANDED leads, above the 30-day trend: it explains the number
        # in the header, the way Sleep's contributor breakdown does. Every read
        # below happens only on this branch, so the three-card Home stream
        # never pays for it.
        _region_data: dict = strain_screen.empty_region_data(_strain_is_rolling)
        try:
            if _current_stage is None:
                raise ValueError(home.STAGE_UNREAD)
            # As of the day shown, with the week's shape on a rest day when
            # asked for (strain_screen.region_data).
            _region_data = strain_screen.region_data(
                _region_au_history(selected_date.isoformat()), _current_stage,
                selected_date, _stage_start_cached(selected_date.isoformat()), _snapshot,
                _strain_window_week)
        except Exception:
            # A failed read must not take the strain number down with it — the
            # panel states its own absence instead.
            pass
        globals()["_STRAIN_REGION_DATA"] = _region_data
        pre_blocks = (_region_block(_region_data, _display_strain, _current_stage)
                      if _current_stage is not None else
                      _panel("Where it landed",
                             f'<div style="font-size:12px;color:{skin["ink2"]};line-height:1.5;">'
                             f'{home.STAGE_UNREAD}</div>', skin=skin))
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

    hist_dates, hist_values, _latest = home.trend_series(_metrics_hist, selected_date, hist_key)

    # Sleep-only: a simple marker for how many nights in this 30-day window
    # carry a wake-time adjustment (CLAUDE.md rule 4's narrow manual-entry
    # exception) — deliberately just a count/caption, not a per-point
    # sparkline annotation.
    adjusted_marker = ""
    if view == "sleep":
        adjusted_nights = sleep_screen.wake_display(
            selected_date, _wake_adjustments, hist_dates)["nights_adjusted"]
        if adjusted_nights:
            adjusted_marker = (
                f'<div style="font-size:10px;color:#4FC3F7;margin:-4px 0 10px;">'
                f'⚡ {adjusted_nights} night(s) wake-time adjusted in this window</div>'
            )

    # TWO parts, so a Streamlit control can be placed BETWEEN them.
    # _metric_detail() below joins them and is what readiness and sleep render,
    # unchanged. Strain renders them separately with the rest-day week toggle
    # in the seam — a button cannot live inside a markdown string, and putting
    # it after the whole block would strand it under two charts, a long way
    # from the panel it acts on.
    head = (
        f'<div style="padding:16px;">'
        + _detail_header(detail_label, col, disp, lbl)
        + pre_blocks
        + f'</div>'
    )
    tail = (
        f'<div style="padding:0 16px 16px;">'
        + _history_trend_block("hist", hist_title, hist_metric, hist_unit,
                               hist_dates, hist_values, hist_color, hist_key,
                               floor=hist_floor, cap=hist_cap,
                               decimals=hist_decimals)
        + adjusted_marker
        + extra_blocks
        + f'</div>'
    )
    return head, tail


def _metric_detail(view: str) -> str:
    """The whole drill-down as one string — what readiness and sleep render."""
    return "".join(_metric_detail_parts(view))


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
    control = sleep_screen.wake_control(d, _wake_adjustments, _wake_sources or {})
    current = control["minutes"]
    st.markdown(
        "<div style='padding:0 16px;'><div style='font-size:10px;color:#6B7A9B;"
        "letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;'>"
        "Adjust Wake Time</div></div>",
        unsafe_allow_html=True,
    )
    if not control["editable"]:
        # A fused night: the fusion figure wins, so a manual value would change
        # nothing (inventory fault F5). Say so instead of offering − and +.
        st.caption(control["caption"])
        return
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
    if control["caption"]:
        st.caption(control["caption"])


# ─── Fixed UI elements ────────────────────────────────────────────────────────

# The fixed header keeps its LABEL as markup; the two arrows (and the detail
# view's back arrow) are real buttons, positioned into the same bar by
# _NAV_BUTTON_CSS. They used to be <a href="?d=..."> links, i.e. a full page
# reload per day stepped — see CLAUDE.md Key Rule 17. Rendered by
# _render_header_buttons() below, after the header markup so they layer above it.
_DETAIL_VIEW_TITLES = {"strain": "Strain History", "readiness": "Readiness History", "sleep": "Sleep History"}
if view in _DETAIL_VIEW_TITLES:
    # The date rides in the fixed header, not only in the panel's own overline:
    # the arrows beside it are how the athlete moves between nights, and once
    # he has scrolled the overline is gone while this is not. margin-right
    # clears the two arrow buttons _NAV_BUTTON_CSS pins over this bar.
    _header_inner = (
        f'<span style="color:#D4DCEE;font-weight:600;font-size:15px;'
        f'margin-left:44px;">{_DETAIL_VIEW_TITLES[view]}</span>'
        f'<span style="color:#6B7A9B;font-size:12px;letter-spacing:1px;'
        f'margin-left:auto;margin-right:92px;">{date_label}</span>'
    )
    _header_justify = "flex-start"
else:
    _header_inner = (
        f'<span style="color:#D4DCEE;font-weight:600;font-size:15px;letter-spacing:0.5px;'
        f'margin:0 auto;">{date_label}</span>'
    )
    _header_justify = "center"


def _render_header_buttons() -> None:
    """The fixed header's navigation, as buttons rather than links."""
    if view in _DETAIL_VIEW_TITLES:
        # rw too: it is drill-down state. Left behind it means nothing on the
        # Home stream, and the next tap on the Strain card would silently
        # re-open the rest-day week panel the athlete had closed.
        st.button("←", key="hdr_back", on_click=_go,
                  kwargs={"view": None, "pt": None, "rw": None}, help="Back")
        # ⚠ THE DRILL-DOWN USED TO REPLACE THE DAY ARROWS WITH THE BACK BUTTON,
        # so the only way to reach another night was to go back to Home, step
        # the day there and re-open the card. That is why a morning with no
        # reading yet had nowhere to go — athlete, 2026-08-25: "I should be
        # able to review yesterdays sleep by toggling to yesterday if I want
        # that." Separate keys from the Home pair so each has its own position
        # in _NAV_BUTTON_CSS rather than one rule trying to serve both layouts.
        #
        # pt is dropped on a day change: a selected chart point is an index
        # into THIS night's series, and carrying it to another night would
        # silently select an unrelated sample.
        st.button("‹", key="hdr_dprev", on_click=_go,
                  kwargs={"d": prev_date, "pt": None}, help="Previous day")
        st.button("›", key="hdr_dnext", on_click=_go,
                  kwargs={"d": next_date, "pt": None},
                  disabled=not can_go_next, help="Next day")
        return
    st.button("‹", key="hdr_prev", on_click=_go, kwargs={"d": prev_date},
              help="Previous day")
    st.button("›", key="hdr_next", on_click=_go, kwargs={"d": next_date},
              disabled=not can_go_next, help="Next day")

_header_html = (
    '<div style="position:fixed;top:0;left:0;right:0;z-index:900;'
    'background:#0B0F1E;border-bottom:1px solid #1E2840;">'
    f'<div style="max-width:480px;margin:0 auto;height:56px;display:flex;'
    f'align-items:center;justify-content:{_header_justify};padding:0 20px;">'
    + _header_inner +
    '</div>'
    '</div>'
)

# FAB — Morning Check-In. Sets _nav_page, exactly like the bottom nav, so the
# SPA router dispatches views/checkin.py over the existing websocket. It used
# to be an <a href="?page=checkin">, which is the link the router note at the
# top of this file blames for a reconnect landing the athlete on Check-in:
# an anchor navigation left ?page=checkin in the address bar as the state the
# next reconnect would read back. Positioned by _NAV_BUTTON_CSS.


def _open_checkin() -> None:
    st.session_state["_nav_page"] = "checkin"

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

# TWO NUMBERS, BOTH SHOWN, AND THE ONE WITH CONSEQUENCES LEADS.
# Athlete, 2026-08-23: "I dont like the way I have two different numbers for
# readiness, I either want them put together or show them both."
#
# Averaging them was refused: it would manufacture a third figure that is
# neither today's score nor the fortnight's, break the r=0.992 agreement with
# Oura's own readiness that MODEL_VERSION 2 was validated against, and make
# every stored row incomparable with every new one.
#
# So both are on the card, and TODAY'S leads — because today's is the number
# with consequences. engine.readiness_training_modifier buckets the raw score;
# the trend drives nothing at all. Showing the trend large while the raw score
# decided the session is the lie of emphasis that produced the original report:
# 66 on screen, "reduce load" on the next one, and on that day the raw score
# was 56.7 -> "below" -> -10% volume, while the trend would have bucketed
# "normal" and contributed nothing.
#
# ⚠ _readiness_score (the TREND) stays exactly as it is everywhere else: it is
# what compute_daily_metrics_snapshot persists into Metrics History, and what
# the 30-day sparkline plots. Only the card's headline moves.
# ⚠ FOR selected_date, NOT date.today(). Home renders a past day whenever the
# `d` query param is set, and today.today_readiness_raw() always answers for
# TODAY — pairing it with a past day's trend would put two different dates
# side by side under one pair of titles.
# ⚠ ON TODAY, THE DISPLAYED DAILY MUST BE THE NUMBER THE ENGINE BUCKETED.
# compute_readiness reads a window, and the score moves with how wide that
# window is — measured on 2026-08-23: 56.7 over the engine's 14 days against
# 56.2 over the card's 60. Both round to "56" and both bucket "below", so it
# is invisible today; near a bucket edge the card would show one number while
# the session was decided on another. That is the mismatch this whole change
# exists to remove, so today's figure comes from the engine's own reader.
# A past date has no live decision to agree with, so it uses the rows Home
# already holds.
# The daily and its breakdown come from ONE set of rows (home.readiness_daily):
# today's are the engine's own 14 (today._bio_for_readiness, the rows
# today.today_readiness_raw scores), a past day's are Home's rows ending on it.
try:
    _readiness_today, _readiness_breakdown = home.readiness_daily(
        selected_date, home.readiness_rows_for(
            selected_date, _today,
            today._bio_for_readiness() if is_today else None, _bio_rows))
except Exception:
    _readiness_today, _readiness_breakdown = None, None
# A day with no reading of its own still shows the trend rather than nothing,
# which is the pre-existing behaviour of this card.
_r_card = home.readiness_card(_readiness_today, _readiness_score)
r_col, r_disp, r_lbl, r_hdr, r_desc, r_tert = dash.readiness_meta(_r_card)
# BOTH FIGURES, EACH TITLED, ALWAYS — including when one or both are blank.
# Athlete, 2026-08-25: "Rather always see both labeled even when blank."
#
# This used to pair them only when both existed AND rounded differently, on the
# reasoning that two identical figures side by side invent a distinction. What
# that actually bought was a card that changed SHAPE from day to day: one big
# untitled number when they agreed, two small titled ones when they did not,
# and a bare "--" on a morning before the ring uploaded. Three renders of one
# card — and on the days it showed a single figure, nothing on screen said
# which of the two you were looking at.
#
# A "--" under TREND is information, not an empty slot: it says that number
# does not exist yet, which is precisely what a morning with no reading needs
# to say. Both go blank together by construction — compute_readiness_trend
# returns NOT_COMPUTED whenever the date carries no score of its own — so this
# never shows one figure beside a hole.
_r_pair = home.score_pair(_readiness_today, _readiness_score)
# The SAME verdict object views/training.py renders from — one load_policy call
# per process, so the two screens cannot describe different days.
# ⚠ ONLY ON TODAY. The verdict describes today's session; rendering it under
# a card the athlete has navigated back to would attach a live training
# decision to a day that is already over.
_verdict = None
if is_today:
    try:
        _verdict = today.today_verdict(readiness_display=_readiness_score,
                                       readiness_band=r_lbl)
    except Exception:
        _verdict = None
_verdict_html = _verdict_line(_verdict) if _verdict else ""
_card_readiness = _card_html(
    "READINESS", _bg["readiness"],
    _arc_svg(_r_card, home.SCALES["readiness"], r_col),
    r_disp, r_lbl, r_col, r_hdr, r_desc, r_tert,
    badge=(_verdict.badge if _verdict else ""),
    badge_tone=(_verdict.tone if _verdict else ""),
    score_pair=_r_pair,
)

s_col, s_disp, s_lbl, s_hdr, s_desc = dash.strain_meta(_display_strain, rest_day=bool(_snapshot.get("rest_day")))
if _snapshot.get("rest_day") and _snapshot.get("strain_7d") is not None:
    # The 7-day average on its own line on a rest day, as on the phone (2026-10-20).
    s_desc = f"{s_desc} 7-day average {_snapshot['strain_7d']:.1f}."
if _snapshot.get("strain_unscored_reason"):
    # Not "no workload logged": the load may well be there, the stage is not.
    s_hdr, s_desc = "Not scored", _snapshot["strain_unscored_reason"]
_strain_card_label, _strain_detail_label = strain_screen.strain_labels(_strain_is_rolling, date_label)
_card_strain = _card_html(
    _strain_card_label, _bg["strain"],
    _arc_svg(_display_strain, strain_screen.STRAIN_TOP, s_col),
    s_disp, s_lbl, s_col, s_hdr, s_desc,
)

sl_col, sl_disp, sl_lbl, sl_hdr, sl_desc = dash.sleep_meta(_sleep_score, _sleep_need, _sleep_base_window)
_card_sleep = _card_html(
    "SLEEP", _bg["sleep"],
    _arc_svg(_sleep_score, home.SCALES["sleep"], sl_col),
    sl_disp, sl_lbl, sl_col, sl_hdr, sl_desc,
)

# ─── Render ───────────────────────────────────────────────────────────────────

# CHROME_CSS already injected at top of script (before data fetching)
styles.inject_css()                                # base styles (same as other pages)
st.markdown(_home_css,    unsafe_allow_html=True)  # home-specific overrides (480px max-width etc.)
st.markdown(_header_html, unsafe_allow_html=True)  # fixed date header (label only)
st.markdown(_NAV_BUTTON_CSS, unsafe_allow_html=True)  # positions the buttons below
_render_header_buttons()                           # ‹ / › / ← , into the header bar
st.button("+", key="fab_checkin", on_click=_open_checkin,
          help="Morning check-in")                 # FAB → Check-In
if not is_today:
    # One tap back to today (2026-10-13). The arrows step a day at a time, and
    # a past day is something picked during this visit, never where Home opens.
    st.button("Back to today", key="go_today", on_click=_go,
              kwargs={"d": None, "pt": None}, help="Show today")

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
    if view == "strain":
        # Split render: the week toggle belongs beside the panel it acts on,
        # and a Streamlit button cannot live inside a markdown string.
        _head, _tail = _metric_detail_parts(view)
        st.markdown(_head, unsafe_allow_html=True)
        _render_week_toggle(globals().get("_STRAIN_REGION_DATA") or {},
                            _strain_window_week)
        st.markdown(_tail, unsafe_allow_html=True)
    else:
        st.markdown(_metric_detail(view), unsafe_allow_html=True)
    # Only the drill-downs carry chart links, so the iframe this installs is
    # never paid for on the three-card Home stream.
    styles.enable_chart_links()
    if view == "sleep" and _sleep_is_scored():
        # Nothing to correct on a night with no reading — and offering a
        # wake-time stepper under "No Readings" is the same half-a-screen the
        # night panels were just gated for.
        _render_wake_time_control(selected_date)
else:
    # Rendered card-by-card rather than as one concatenated blob: each needs
    # its own invisible hit-target button pulled over it by _NAV_BUTTON_CSS,
    # which replaced the <a href="?d=...&view=..."> wrapper the card markup
    # used to carry (CLAUDE.md Key Rule 17). A 460px card containing an SVG
    # arc gauge cannot be a button LABEL, so here — and only here — the button
    # sits over the visual instead of being it.
    for _ckey, _chtml, _cview in (
        ("card_readiness", _card_readiness, "readiness"),
        ("card_strain",    _card_strain,    "strain"),
        ("card_sleep",     _card_sleep,     "sleep"),
    ):
        st.markdown(_chtml, unsafe_allow_html=True)
        st.button(f"Open {_cview} detail", key=_ckey, on_click=_go,
                  kwargs={"d": selected_date, "view": _cview},
                  use_container_width=True)
        # ⚠ AFTER the button, never between it and the card. _NAV_BUTTON_CSS
        # pulls the invisible hit target up 464px over the IMMEDIATELY
        # PRECEDING element; anything inserted between them drags the button
        # onto the wrong element and the card silently stops being tappable.
        # The button is 464px tall and pulled up 464px, so emitting here costs
        # zero net flow offset and lands directly under the card.
        if _cview == "readiness" and _verdict_html:
            st.markdown(_verdict_html, unsafe_allow_html=True)
# A DEAD CREDENTIAL AND A FLAKY NETWORK ARE NOT THE SAME NOTICE, and
# collapsing them into one grey caption is what let the Oura token die on
# 2026-08-12 and go unnoticed for five days. "will retry next visit" was
# actively wrong: no number of retries fixes a revoked token, and the gap did
# not read as a gap — readiness renormalised onto its one surviving component
# (services/readiness.py:309-317) and went UP, so the screen looked healthier
# than the week it was hiding.
#
# Checked INDEPENDENTLY of this run's sync result, not nested inside it. The
# sync is throttled to 2 hours and backs off after a failure, so most opens
# during an outage carry a (True, None) status — nesting the check would
# restore the silence by the other door.
try:
    _oura_auth = repo.get_repository().oura_auth_status()
except Exception:
    _oura_auth = {"needs_authorisation": False}
# Which notices show, in order, is sync_policy.sync_notices: a dead
# credential is an error, a failed step a caption, and a chain that blew up
# before any step reported says so too.
_SYNC_NOTICE_TEXT = {
    sync_policy.OURA_UNAUTHORISED: (
        "**Oura is not authorised — your sleep is not being recorded.** Readiness "
        "and HRV are running without it, so today's numbers are not comparable "
        "with last week's. Re-authorise with `python scripts/authorize_oura.py`, "
        "then backfill the missed nights."),
    sync_policy.OURA_UNAVAILABLE: "Oura sync unavailable — will retry next visit.",
    sync_policy.GARMIN_UNAVAILABLE: "Garmin sync unavailable — will retry next visit.",
    sync_policy.SYNC_FAILED_TO_RUN: "Device sync failed to run — will retry next visit.",
}
for _level, _code in sync_policy.sync_notices(
        _oura_auth, (_oura_sync_ok, _oura_sync_err), (_garmin_sync_ok, _garmin_sync_err),
        repo.get_sync_runner().last_error()):
    if _level == "error":
        st.error(_SYNC_NOTICE_TEXT[_code], icon="🔴")
    else:
        st.caption(_SYNC_NOTICE_TEXT[_code])
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


# Only under a Streamlit server. Imported any other way — a test did, until
# 2026-10-09 — this file runs the Home page with the checkout's real secrets,
# and this line then synced Oura and Garmin from that machine.
if st.runtime.exists():
    _run_startup_sync()
