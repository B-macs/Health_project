"""
Insights view — BioAge + Engine Data + Processing Queue + Macro Trends
(Tightness Map + multi-week trend analysis) + Sync.

Usage:
    from views.insights import render
    render()

Caller is responsible for st.set_page_config(), styles.inject_css(), nav.inject().
"""

import base64
import calendar as cal_mod
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import streamlit as st
import pandas as pd

import cluster_a_battery as cba
import cluster_a_mechanics
import cluster_a_prescription
import flexibility_baselines
import patient_profile
import repo
import strength_baselines
import styles
import today as today_mod
from services import ai
from services import dashboard as dash
from services import decision
from services import engine
from services import battery as btry
from services import flexibility as fx
from services import flexibility_screen as fxs
from services import stats as stats_mod
from services import insights as insights_svc
from services import insights_screens
from services import metabolism_screen as ms
from services import processing_queue
from services import sleep_architecture
from services import sessions as sessions_svc
from services import strength_screen as ss
from services import tonnage as tonnage_svc
from services import volume as volume_svc


# ─────────────────────────────────────────────────────────────────────────────
#  BioAge tab — 4 category cards (Strength/Flexibility/Metabolism/Cardio).
#  Card backgrounds are optional: filenames in _BIOAGE_BG below, in
#  background_templates/, appear automatically; if a file is ever missing,
#  cards fall back to a flat dark background (see _bioage_b64).
# ─────────────────────────────────────────────────────────────────────────────

_BIOAGE_BG_DIR = Path(__file__).resolve().parent.parent / "background_templates"

_BIOAGE_CATEGORIES: list[str] = ["strength", "flexibility", "metabolism", "cardio"]

_BIOAGE_LABELS: dict[str, str] = {
    "strength":    "Strength",
    "flexibility": "Flexibility",
    "metabolism":  "Metabolism",
    "cardio":      "Cardio",
}

_BIOAGE_COLORS: dict[str, str] = {
    "strength":    "#FF8C42",
    "flexibility": "#22C3E6",
    "metabolism":  "#9B6BFF",
    "cardio":      "#FF4368",
}

_BIOAGE_BG: dict[str, Path] = {
    "strength":    _BIOAGE_BG_DIR / "Strength_button.png",
    "flexibility": _BIOAGE_BG_DIR / "flexibility.png",
    "metabolism":  _BIOAGE_BG_DIR / "metabolism.png",
    "cardio":      _BIOAGE_BG_DIR / "cardio.png",
}


@st.cache_data(show_spinner=False)
def _bioage_b64(path_str: str) -> str:
    p = Path(path_str)
    if not p.exists():
        return ""
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


# ─────────────────────────────────────────────────────────────────────────────
#  BioAge category cards — a REAL st.button styled to look like the card.
#
#  These used to be an <a href="?page=insights&bioage=..."> wrapping a styled
#  div, which meant every tap was a full browser navigation: page reload,
#  websocket reconnect, session_state gone, every cache cold. On a phone that
#  reads as "it opened a new page". See CLAUDE.md Key Rule 17 — in-app
#  navigation never uses an anchor, and tests/test_spa_navigation.py fails if
#  one comes back.
#
#  Styled the way nav.py styles the bottom bar: one layer, no invisible
#  overlay, the button IS the card. st.button(key="bioage_card_strength")
#  puts a .st-key-bioage_card_strength class on the wrapper, which is the
#  documented hook (see streamlit's own theming reference). The overrides
#  below are the same set nav.py needed — Streamlit's button styles plus
#  styles.py's mobile defaults both have to be beaten, hence !important.
# ─────────────────────────────────────────────────────────────────────────────

#: Which BioAge detail is open. SESSION-STATE PRIMARY, URL as the fallback —
#: the same shape app.py's router uses for "page", and for the same reason:
#: session_state gives an instant websocket rerun, while the synced query
#: param is what survives a websocket reconnect (mobile screen lock, app
#: backgrounding, dropped signal), which clears session_state entirely.
#: Having both means navigation is instant AND a reconnect lands you back
#: where you were instead of on the card list.
_BIOAGE_STATE_KEY = "_bioage_detail"


def _bioage_selected() -> str | None:
    """The open category, or None for the card list."""
    sel = st.session_state.get(_BIOAGE_STATE_KEY)
    if sel is None:
        sel = st.query_params.get("bioage")
    return sel if sel in _BIOAGE_LABELS else None


def _open_bioage(key: str) -> None:
    st.session_state[_BIOAGE_STATE_KEY] = key


def _close_bioage() -> None:
    st.session_state[_BIOAGE_STATE_KEY] = None


def _sync_bioage_url(selected: str | None) -> None:
    """Keep ?bioage= in step with the real selection.

    Writing st.query_params updates the address bar via the history API — it
    does NOT reload the page, which is exactly why the anchor had to go and
    this does not. Without the sync the URL goes stale the moment you navigate
    by button, and the stale value would then win on the next reconnect.
    """
    if selected is None:
        if "bioage" in st.query_params:
            del st.query_params["bioage"]
    elif st.query_params.get("bioage") != selected:
        st.query_params["bioage"] = selected


def _bioage_card_key(key: str) -> str:
    return f"bioage_card_{key}"


def _bioage_card_css(key: str) -> str:
    """Scoped CSS turning this category's button into its 150px image card.

    Kept visually identical to the anchor version it replaced: same height,
    radius, gradient scrim, background image, neon label and right chevron.
    The chevron is a ::after rather than a second element because a button's
    label is markdown text, not markup.
    """
    color = _BIOAGE_COLORS[key]
    bg    = _bioage_b64(str(_BIOAGE_BG[key]))
    sel   = f".st-key-{_bioage_card_key(key)}"
    bg_css = (
        f"background-image:linear-gradient(90deg,#0B0F1A 0%,rgba(11,15,26,0.75) 45%,"
        f"rgba(11,15,26,0.15) 80%),url('{bg}') !important;"
        f"background-size:cover !important;background-position:center right !important;"
    ) if bg else "background:#0B0F1A !important;"
    return f"""<style>
{sel} button {{
    width:100% !important; height:150px !important; min-height:0 !important;
    border-radius:14px !important; overflow:hidden !important;
    border:1px solid rgba(255,255,255,0.08) !important;
    padding:0 22px !important; margin-bottom:14px !important;
    box-shadow:none !important;
    display:flex !important; align-items:center !important;
    justify-content:space-between !important;
    {bg_css}
}}
{sel} button:hover {{ border:1px solid {color}66 !important; {bg_css} }}
{sel} button:focus, {sel} button:focus-visible {{
    outline:none !important; box-shadow:none !important;
}}
{sel} button p, {sel} button span {{
    font-size:34px !important; font-weight:800 !important; color:{color} !important;
    text-shadow:0 0 18px {color}99, 0 0 4px {color} !important;
    letter-spacing:-0.5px !important; margin:0 !important; padding:0 !important;
    line-height:1 !important; pointer-events:none !important;
}}
{sel} button::after {{
    content:"\\203A"; font-size:26px; color:{color}; font-weight:300;
    line-height:1; pointer-events:none;
}}
{sel} [data-testid="stBaseButton-secondary"],
{sel} [data-testid="baseButton-secondary"] {{
    {bg_css} border:1px solid rgba(255,255,255,0.08) !important;
}}
</style>"""


# ─────────────────────────────────────────────────────────────────────────────
#  Strength BioAge detail screen (tab_bioage → ?bioage=strength).
#
#  Two metrics, kept conceptually apart and sharing no term:
#
#    Overall Strength Score  — the lifts as a % of the 2025 peak, measured:
#      the middle of the last 3 lifting weeks (services/strength.py, the
#      owner's choice of 2026-10-20). A heavier training week cannot raise it
#      on its own; a stronger estimated 1RM does.
#    Weekly tonnage          — the WORK COMPLETED in one week, in kilograms,
#      overall and per body sector. services/tonnage.py. No decay, no
#      carry-over; a week with no eligible loaded sets is zero.
#
#  One dropdown selects which of the five series the progress display shows,
#  and the axis, unit, readout and tooltips follow it.
#
#  Replaces the Stage-Adjusted Recovery Score, which was
#  min(100, current_28d / (best_ever_28d * cap) * 100) with the current window
#  inside the set its own denominator maximised over — so it returned a flat
#  100 for the whole first 28 days of any block and had produced exactly one
#  distinct value across every day it existed. Those scoring functions have
#  been deleted; services/bioage.py is now just the muscle-imbalance count,
#  which this screen still renders.
# ─────────────────────────────────────────────────────────────────────────────

# Shared box dimensions for the illustrated cards (hero, muscle balance) so
# they render at the same on-screen size, growing proportionally on a wide
# desktop card rather than staying a fixed height; min/max-height clamp the two
# ends. The derived illustrations keep their own native aspect ratio and render
# via background-size:contain, so the full image is always visible.
#
# ⚠ THE WIDTH COMES FIRST, and it is what keeps these cards on a phone screen
# (athlete, 2026-10: "Strength page is not aligned to the page it goes off the
# page to the right"). With no width of its own, a box with an aspect ratio and
# a minimum height is widened to keep the ratio: 220 px tall at 1194/356 is
# 738 px wide, so on a 390 px phone the hero and the muscle-balance card ran
# 740 px and the page scrolled sideways to 756. Width 100% makes the width
# fixed and the min-height wins on the height instead — 358 x 220 measured,
# page 390. The Metabolism hero shares this string and had the same fault.
_CARD_DIMENSIONS_CSS = ("width:100%;box-sizing:border-box;"
                        "aspect-ratio:1194/356;min-height:220px;max-height:420px;")

_STRENGTH_FACEPLATE_DIR = _BIOAGE_BG_DIR / "body_faceplates_v2"

# The three faceplates stack into one continuous figure, so they must render
# at the SAME displayed width with each image's own aspect ratio preserved —
# resizing their heights independently would break the join. Native sizes.
_STRENGTH_REGIONS: tuple[dict, ...] = (
    {"id": "upper_body", "name": "Upper body", "colour": "#FF8C42", "ratio": "893/640"},
    {"id": "core",       "name": "Core",       "colour": "#E8B04B", "ratio": "893/428"},
    {"id": "lower_body", "name": "Lower body", "colour": "#D9663A", "ratio": "893/534"},
)

#: Each progress series' colour. The series themselves, their units and the
#: window are services/strength_screen.METRICS and WEEKS.
_STRENGTH_COLOURS: dict[str, str] = {
    "Overall Strength Score": "#FF8C42", "Overall Strength Tonnage": "#FF8C42",
    "Upper Body Tonnage": "#FF8C42", "Core Tonnage": "#E8B04B", "Lower Body Tonnage": "#D9663A",
}

_INK, _INK2, _INK3 = "#F4F6FB", "#9AA3B2", "#5A6377"
_PANEL, _HAIR = "#0E1018", "rgba(255,255,255,0.06)"
_GOOD, _WARN, _BAD = "#6BAF8B", "#BFA06A", "#C47878"

_STRENGTH_CSS = f"""
<style>
[data-testid="stMainBlockContainer"][data-testid="stMainBlockContainer"]
  {{max-width:1600px !important;margin-left:auto !important;margin-right:auto !important;}}

/* the metric picker, restyled onto the screen's dark palette */
.st-key-strength_metric label {{ display:none !important; }}
.st-key-strength_metric div[data-baseweb="select"] > div {{
  background:rgba(255,255,255,.06) !important; border:1px solid {_HAIR} !important;
  border-radius:9px !important; color:{_INK} !important; font-weight:600 !important; }}
.st-key-strength_metric div[data-baseweb="select"] svg {{ fill:{_INK2} !important; }}
.st-key-strength_metric div[data-baseweb="select"] div {{ font-size:12.5px !important; }}
.st-key-strength_metric {{ max-width:250px; margin-left:auto; }}

.sb-readout {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px;
  background:{_PANEL}; border:1px solid {_HAIR}; border-radius:14px;
  padding:14px 18px; margin-top:10px; }}
.sb-readout .k {{ font:600 9px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:.13em; text-transform:uppercase; color:{_INK3}; }}
.sb-readout .v {{ font-size:22px; font-weight:600; color:{_INK}; margin-top:8px;
  line-height:1.1; font-variant-numeric:tabular-nums; }}
.sb-readout .v u {{ text-decoration:none; font-size:12px; font-weight:400;
  color:{_INK2}; margin-left:5px; }}
.sb-readout .p {{ font-size:11.5px; margin-top:5px; font-variant-numeric:tabular-nums; }}
@media (max-width:520px) {{ .sb-readout {{ grid-template-columns:1fr 1fr; }} }}

.sb-chartbox {{ background:{_PANEL}; border:1px solid {_HAIR}; border-radius:16px;
  padding:12px 8px 4px; margin:10px 0 18px; }}

.sb-splitbar {{ display:flex; height:12px; border-radius:6px; overflow:hidden;
  background:rgba(255,255,255,.05); margin:6px 0 0; }}
.sb-splitbar i {{ display:block; height:100%; }}
.sb-splitkey {{ display:flex; flex-wrap:wrap; gap:16px; margin:9px 0 14px;
  font-size:11.5px; color:{_INK2}; }}
.sb-splitkey span {{ display:inline-flex; align-items:center; gap:7px; }}
.sb-splitkey b {{ width:9px; height:9px; border-radius:3px; display:inline-block; }}

/* Body parts: three plates stacked into one continuous figure. Same displayed
   width, each keeping its own aspect ratio. */
.sb-bp {{ --fig:330px; }}
.sb-region {{ display:grid; grid-template-columns:minmax(0,1fr) var(--fig);
  align-items:center; gap:18px; position:relative; }}
.sb-region .txt {{ padding:4px 0 4px 20px; border-bottom:1px solid {_HAIR};
  align-self:stretch; display:flex; flex-direction:column; justify-content:center; }}
.sb-region:last-child .txt {{ border-bottom:0; }}
.sb-region .nm {{ font-size:20px; font-weight:700; margin-bottom:4px; }}
.sb-region .sc {{ font-size:26px; font-weight:300; color:{_INK};
  font-variant-numeric:tabular-nums; }}
.sb-region .sc u {{ text-decoration:none; font-size:12px; color:{_INK2}; margin-left:6px; }}
.sb-region .sc s {{ text-decoration:none; font-size:20px; color:{_INK2}; margin-left:9px; }}
.sb-region .idx {{ font-size:12px; color:{_INK2}; margin-top:6px;
  font-variant-numeric:tabular-nums; }}
.sb-region .idx em {{ font-style:normal; font-weight:600; color:{_INK}; }}
.sb-cbar {{ height:3px; border-radius:2px; background:rgba(255,255,255,.08);
  margin-top:9px; max-width:190px; overflow:hidden; }}
.sb-cbar i {{ display:block; height:100%; border-radius:2px; }}
.sb-cnote {{ font:600 9px/1.8 ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:.1em; text-transform:uppercase; margin-top:5px; }}

.sb-plate {{ width:var(--fig); background-repeat:no-repeat; background-size:100% 100%;
  transition:opacity 160ms ease, filter 160ms ease; }}
.sb-plate.off {{ opacity:.22; filter:grayscale(1); }}
/* Hovering the strip dims every plate; hovering ONE region lights that plate.
   The .off plate (a region with no confidence yet) starts dimmed, and a rule
   that dims the rest will also catch its OWN hover at equal specificity — so
   the row-hover rules name .off explicitly and come last, or pointing at core
   makes it darker instead of lighting it up. */
.sb-bp:hover .sb-plate {{ opacity:.45; }}
.sb-bp:hover .sb-plate.off {{ opacity:.18; }}
.sb-bp .sb-region:hover .sb-plate,
.sb-bp .sb-region:hover .sb-plate.off {{ opacity:1; filter:none; }}
@media (max-width:900px) {{ .sb-bp {{ --fig:240px; }} .sb-region {{ gap:12px; }} }}
@media (max-width:640px) {{ .sb-bp {{ --fig:168px; }} .sb-region .txt {{ padding-left:16px; }} }}

.sb-imblist {{ background:{_PANEL}; border:1px solid {_HAIR}; border-radius:16px;
  padding:6px 18px 14px; }}
.sb-imblist .grp {{ font:600 9px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:2px; text-transform:uppercase; color:{_INK3}; margin:14px 0 8px; }}
.sb-imblist .i {{ display:flex; gap:10px; align-items:baseline; font-size:12.5px;
  color:#C8CDD8; padding:4px 0; }}
.sb-imblist .i b {{ width:6px; height:6px; border-radius:50%; flex:none;
  transform:translateY(-1px); }}
</style>
"""


def _kg(value: float) -> str:
    return f"{value:,.0f}"


def _signed(value: float, points: bool) -> str:
    sign = "" if abs(value) < 5e-2 else ("−" if value < 0 else "+")
    return f"{sign}{abs(value):.1f}" if points else f"{sign}{_kg(abs(value))}"


#: How a week-over-week change is coloured (services/strength_screen.readout).
_TONE: dict[str | None, str] = {"up": _GOOD, "down": _BAD, "flat": _INK2, None: _INK3}


def _svg_frame(y_labels: list[str], x_labels: list[str], w: int, h: int,
               pl: int, pr: int, pt: int, pb: int) -> str:
    """Dashed gridlines + axis labels, the geometry the whole screen uses."""
    iw, ih = w - pl - pr, h - pt - pb
    out, n = "", len(y_labels) - 1
    for i, label in enumerate(y_labels):
        gy = pt + (i / n) * ih
        out += (
            f'<line x1="{pl}" y1="{gy:.1f}" x2="{w - pr}" y2="{gy:.1f}" '
            f'stroke="rgba(255,255,255,0.08)" stroke-width="1" stroke-dasharray="2,4"/>'
            f'<text x="{pl - 8}" y="{gy + 4:.1f}" text-anchor="end" font-size="10" '
            f'fill="{_INK3}" font-family="system-ui">{label}</text>'
        )
    for i, label in enumerate(x_labels):
        gx = pl + (i / max(1, len(x_labels) - 1)) * iw
        out += (
            f'<line x1="{gx:.1f}" y1="{pt}" x2="{gx:.1f}" y2="{h - pb}" '
            f'stroke="rgba(255,255,255,0.04)" stroke-width="1"/>'
            f'<text x="{gx:.1f}" y="{h - 6}" text-anchor="middle" font-size="9" '
            f'fill="{_INK3}" font-family="system-ui">{label}</text>'
        )
    return out


def _tonnage_chart_svg(series: list, key: str, colour: str, label: str) -> str:
    """Weekly tonnage bars. A zero week draws a baseline stub and a "0" rather
    than nothing — absent from the chart and zero in the chart are different
    claims, and tonnage is a statement about the week."""
    w, h, pl, pr, pt, pb = 640, 220, 44, 14, 14, 24
    iw, ih = w - pl - pr, h - pt - pb
    _values, top = ss.tonnage_axis(series, key)
    y_labels = [_kg(top * i / 4) for i in range(4, -1, -1)]
    x_labels = [ss.week_label(wk.week_start) for wk in series]
    out = _svg_frame(y_labels, x_labels, w, h, pl, pr, pt, pb)
    bw = iw / max(1, len(series)) * 0.52
    for i, wk in enumerate(series):
        cx = pl + (i / max(1, len(series) - 1)) * iw
        cell = wk.value(key)
        tip = (
            f"Week of {x_labels[i]}\n{_kg(cell.kg)} kg\n"
            f"{cell.sets} loaded set{'' if cell.sets == 1 else 's'} · "
            f"{wk.training_days} training day{'' if wk.training_days == 1 else 's'}"
            # Reps and seconds are reported separately and never summed — a
            # hold is logged as 1 rep with the work in `tut`, so adding them
            # would hide exactly the work these counters exist to show. Same
            # words as the line under the chart, which a phone can see.
            + (f" · without load: {tonnage_svc.unloaded_text(cell)}"
               if tonnage_svc.unloaded_text(cell) else "")
        )
        if cell.kg <= 0:
            out += (
                f'<g><title>{tip}</title>'
                f'<line x1="{cx - bw / 2:.1f}" y1="{pt + ih}" x2="{cx + bw / 2:.1f}" '
                f'y2="{pt + ih}" stroke="{_INK3}" stroke-width="2.5" stroke-linecap="round"/>'
                f'<text x="{cx:.1f}" y="{pt + ih - 7}" text-anchor="middle" font-size="9" '
                f'fill="{_INK3}" font-family="ui-monospace,monospace">0</text>'
                f'<rect x="{cx - bw / 2:.1f}" y="{pt}" width="{bw:.1f}" height="{ih}" '
                f'fill="transparent"/></g>'
            )
            continue
        bh = (cell.kg / top) * ih
        out += (
            f'<g><title>{tip}</title>'
            f'<rect x="{cx - bw / 2:.1f}" y="{pt + ih - bh:.1f}" width="{bw:.1f}" '
            f'height="{bh:.1f}" rx="3" fill="{colour}" fill-opacity="0.9"/>'
            f'<text x="{cx:.1f}" y="{pt + ih - bh - 7:.1f}" text-anchor="middle" '
            f'font-size="10" fill="{_INK}" font-family="ui-monospace,monospace">'
            f'{_kg(cell.kg)}</text></g>'
        )
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="{label}, kilograms per week">{out}</svg>'
    )


def _unloaded_note_html(series: list, key: str) -> str:
    """This week's and last week's work without load, under a tonnage chart.

    The chart counts kilograms only, so a week of planks and bodyweight reps
    draws a zero bar. The tooltip said what was done, and a tooltip never
    shows on a touch screen (WP-15, 2026-10-13). Empty when neither week did
    any, so a loaded-only sector carries no extra line."""
    lines = [f'<div style="font-size:13px;color:{_INK2};">{label}: {text}</div>'
             for label, text in ss.unloaded_lines(series, key)]
    if not lines:
        return ""
    return (f'<div class="sb-unloaded" style="margin:-4px 0 16px;">'
            f'<div style="font-size:12px;color:{_INK3};letter-spacing:.04em;'
            f'margin-bottom:2px;">Work not counted in kg</div>{"".join(lines)}</div>')


def _score_chart_svg(points: list[dict], colour: str) -> str:
    """The headline's line (the middle of the last 3 lifting weeks), with each
    week's measured index beneath it in a muted grey (2026-10-20)."""
    w, h, pl, pr, pt, pb = 640, 220, 44, 14, 14, 24
    iw, ih = w - pl - pr, h - pt - pb
    # The span divides into 4 gridlines cleanly (services/strength_screen).
    lo, hi = ss.score_axis(points)
    y_labels = [f"{hi - (hi - lo) * i / 4:.0f}" for i in range(0, 5)]
    x_labels = [ss.week_label(p["week"]) for p in points]
    out = _svg_frame(y_labels, x_labels, w, h, pl, pr, pt, pb)

    def x_at(i: int) -> float:
        return pl + (i / max(1, len(points) - 1)) * iw

    def y_at(v: float) -> float:
        return pt + (1 - (v - lo) / (hi - lo)) * ih

    measured = [(i, p["measured"]) for i, p in enumerate(points) if p["measured"] is not None]
    if len(measured) > 1:
        poly = " ".join(f"{x_at(i):.1f},{y_at(v):.1f}" for i, v in measured)
        out += (f'<polyline points="{poly}" fill="none" stroke="#6B7A9B" '
                f'stroke-width="1.5" stroke-dasharray="3,3"/>')
    for n, (i, v) in enumerate(measured):
        out += (f'<g><title>Week of {x_labels[i]}\n{v:.1f} points measured</title>'
                f'<circle cx="{x_at(i):.1f}" cy="{y_at(v):.1f}" r="3.5" fill="#6B7A9B"/></g>')
        if n == 0:
            # The grey series has to be named ON the chart. An SVG <title>
            # never fires on touch and this app is mobile-first, so without
            # this the second line is permanently unexplained on a phone —
            # while running ABOVE the headline number, which invites reading
            # it as a truer score being suppressed.
            out += (f'<text x="{x_at(i) + 7:.1f}" y="{y_at(v) + 14:.1f}" font-size="9" '
                    f'fill="#6B7A9B" font-family="ui-monospace,monospace">'
                    f'{v:.1f} measured</text>')

    levels = [(i, p["level"]) for i, p in enumerate(points) if p["level"] is not None]
    if len(levels) > 1:
        poly = " ".join(f"{x_at(i):.1f},{y_at(v):.1f}" for i, v in levels)
        out += (f'<polyline points="{poly}" fill="none" stroke="{colour}" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    for n, (i, v) in enumerate(levels):
        last = n == len(levels) - 1
        halo = (f'<circle cx="{x_at(i):.1f}" cy="{y_at(v):.1f}" r="12" fill="{colour}" '
                f'opacity="0.18"/>') if last else ""
        out += (
            f'<g><title>Week of {x_labels[i]}\n{v:.1f} points\n{points[i]["why"]}</title>'
            f'{halo}<circle cx="{x_at(i):.1f}" cy="{y_at(v):.1f}" r="{6 if last else 3.5}" '
            f'fill="{colour}" stroke="#07080D" stroke-width="2"/></g>'
        )
        if last:
            # The newest week sits ON the right edge of the plot, so a
            # left-anchored label runs past the viewBox and is clipped. Anchor
            # it to the end and it grows inward instead.
            at_edge = i == len(points) - 1
            out += (
                f'<text x="{x_at(i) + (4 if not at_edge else -4):.1f}" '
                f'y="{y_at(v) - 13:.1f}" text-anchor="{"end" if at_edge else "start"}" '
                f'font-size="11" fill="{colour}" '
                f'font-family="ui-monospace,monospace">{v:.1f}</text>'
            )
    if not measured and not levels:
        out += (f'<text x="{w / 2}" y="{h / 2}" text-anchor="middle" font-size="12" '
                f'fill="{_INK3}" font-style="italic" font-family="system-ui">'
                f'No progress recorded yet</text>')
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'aria-label="Overall Strength Score, points per week">{out}</svg>'
    )


def _strength_hero_html(value: float | None, calibrating: bool) -> str:
    accent = _BIOAGE_COLORS["strength"]
    bg = _bioage_b64(str(_BIOAGE_BG_DIR / "derived" / "strength_hero.png"))
    bg_css = (
        f"background-image:linear-gradient(100deg,rgba(11,15,26,0.94) 0%,"
        f"rgba(11,15,26,0.58) 34%,rgba(11,15,26,0.08) 64%),url('{bg}');"
        f"background-size:contain;background-repeat:no-repeat;background-position:center right;"
    ) if bg else "background:#0B0F1A;"
    shown = f"{value:.1f}" if value is not None else "—"
    badge = (
        f'<div><span style="display:inline-block;font:600 9.5px/1.7 ui-monospace,monospace;'
        f'letter-spacing:.12em;text-transform:uppercase;padding:2px 9px;border-radius:20px;'
        f'margin-top:12px;background:rgba(191,160,106,.18);color:{_WARN};">Calibrating</span></div>'
    ) if calibrating else ""
    return (
        f'<div style="position:relative;{_CARD_DIMENSIONS_CSS}border-radius:22px;overflow:hidden;'
        f'margin-bottom:18px;border:1px solid rgba(255,255,255,0.08);{bg_css}'
        f'box-shadow:0 8px 32px rgba(0,0,0,0.4);">'
        f'<div style="position:relative;z-index:1;height:100%;box-sizing:border-box;'
        f'padding:28px 24px;display:flex;flex-direction:column;justify-content:center;">'
        f'<div>'
        f'<div style="font-size:11px;color:{accent};letter-spacing:2px;text-transform:uppercase;'
        f'font-weight:600;margin-bottom:8px;">Overall Strength</div>'
        f'<div style="font-size:46px;font-weight:800;color:{_INK};line-height:1;'
        f'font-variant-numeric:tabular-nums;text-shadow:0 0 24px rgba(255,140,66,.25);">{shown}</div>'
        f'{badge}'
        f'</div></div></div>'
    )


def _strength_readout_html(r: dict, year: int) -> str:
    """This week, last week and the change (services/strength_screen.readout)."""
    unit, points = r["unit"], r["points"]

    def cell(k: str, v: str, sub: str, colour: str = _INK3) -> str:
        return (f'<div><div class="k">{k}</div><div class="v">{v}</div>'
                f'<div class="p" style="color:{colour}">{sub}</div></div>')

    def show(v: float | None) -> str:
        if v is None:
            return "—"
        return f'{v:.1f}<u>{unit}</u>' if points else f'{_kg(v)}<u>{unit}</u>'

    labels = r["labels"]
    if r["delta"] is None:
        delta_html, delta_sub, delta_col = "—", "no comparable previous week", _INK3
    else:
        delta_col = _TONE[r["tone"]]
        delta_html = (f'<span style="color:{delta_col}">{_signed(r["delta"], points)}'
                      f"<u>{unit}</u></span>")
        pct = r["pct"]
        if pct is None:
            delta_sub = "no percentage — the previous week was zero"
        else:
            sign = "" if abs(pct) < 5e-2 else ("−" if pct < 0 else "+")
            delta_sub = f"{sign}{abs(pct):.1f}% week over week"
    return (
        '<div class="sb-readout">'
        + cell(f"This week · {labels[0]}", show(r["current"]), f"week of {labels[0]} {year}")
        + cell(f"Last week · {labels[1]}", show(r["previous"]), f"week of {labels[1]} {year}")
        + cell("Change", delta_html, delta_sub, delta_col)
        + "</div>"
    )


def _strength_region_strip_html(regions: list, core_hold: dict | None = None) -> str:
    """The three body-part cards. Core has no kilogram scale; from the first
    timed plank test its card shows its hold-time index instead, marked
    provisional (services/strength.core_hold_index, decided 2026-10-13) — it
    is never part of the headline."""
    # Each card's numbers, index ("—", never 0, with nothing measured) and
    # band come from services/strength_screen.region_cards.
    meta_by_id = {m["id"]: m for m in _STRENGTH_REGIONS}
    tone_colour = {"good": _GOOD, "warn": _WARN, "bad": _BAD}
    rows = ""
    for card in ss.region_cards(regions, core_hold):
        meta = meta_by_id[card["region"]]
        plate = _bioage_b64(str(_STRENGTH_FACEPLATE_DIR / f"{meta['id']}.png"))
        conf = card["confidence"]
        conf_col = tone_colour[card["tone"]]
        band, off = card["band"], " off" if card["off"] else ""
        index_label, index_text = card["index_label"], card["index_text"]
        aria = (f'{meta["name"]}, {card["points"]:.1f} points, '
                f'{card["pct"]:.1f} percent of overall, '
                f'{index_label.lower()} {"not measured" if index_text == "—" else index_text}, '
                f'confidence {conf:.2f}')
        rows += (
            f'<div class="sb-region" role="group" aria-label="{aria}">'
            f'<div class="txt">'
            f'<div class="nm" style="color:{meta["colour"]}">{meta["name"]}</div>'
            f'<div class="sc">{card["points"]:.1f}'
            f'<u>pts&thinsp;<s>{card["pct"]:.1f}%</s></u></div>'
            f'<div class="idx">{index_label} <em>{index_text}</em></div>'
            f'<div class="sb-cbar"><i style="width:{max(round(conf * 100), 2)}%;'
            f'background:{conf_col}"></i></div>'
            f'<div class="sb-cnote" style="color:{conf_col}">{band}'
            + ("" if index_label != "Index" else f" · confidence {conf:.2f}") + '</div>'
            f'</div>'
            # An absent faceplate keeps its slot at the right aspect ratio
            # rather than collapsing the grid column and shunting the numbers
            # sideways — background-image:url('') would also make the browser
            # re-request the page itself.
            + (f'<div class="sb-plate {meta["id"]}{off}" style="aspect-ratio:{meta["ratio"]};'
               f'background-image:url(\'{plate}\')"></div>'
               if plate else
               f'<div class="sb-plate {meta["id"]}{off}" style="aspect-ratio:{meta["ratio"]};'
               f'background:rgba(255,255,255,.02);border-radius:12px"></div>')
            + '</div>'
        )
    return f'<div class="sb-bp">{rows}</div>'


def _strength_split_html(regions: list) -> str:
    # Looked up by id, not zipped: zip() would pair by position and silently
    # recolour every segment if services.strength.REGIONS were ever reordered.
    meta_by_id = {m["id"]: m for m in _STRENGTH_REGIONS}
    ordered = [(meta_by_id[p["region"]], p) for p in ss.split(regions)]
    bar = "".join(
        f'<i style="width:{p["pct"]:.1f}%;background:{m["colour"]}"></i>'
        for m, p in ordered
    )
    key = "".join(
        f'<span><b style="background:{m["colour"]}"></b>{m["name"]} '
        f'{p["points"]:.1f} pts · {p["pct"]:.1f}%</span>'
        for m, p in ordered
    )
    return f'<div class="sb-splitbar">{bar}</div><div class="sb-splitkey">{key}</div>'


def _muscle_balance_card_html(count: int | None) -> str:
    bg = _bioage_b64(str(_BIOAGE_BG_DIR / "derived" / "muscle_balance.png"))
    bg_css = (
        f"background-image:linear-gradient(90deg,rgba(11,15,26,0.90) 0%,"
        f"rgba(11,15,26,0.58) 32%,rgba(11,15,26,0.10) 60%),url('{bg}');"
        f"background-size:contain;background-repeat:no-repeat;background-position:center right;"
    ) if bg else "background:#0B0F1A;"
    shown = str(count) if count is not None else "—"
    return (
        f'<div style="position:relative;{_CARD_DIMENSIONS_CSS}border-radius:16px;overflow:hidden;'
        f'margin-bottom:8px;border:1px solid {_HAIR};{bg_css}">'
        f'<div style="position:relative;z-index:1;height:100%;box-sizing:border-box;display:flex;'
        f'flex-direction:column;justify-content:center;padding:20px 22px;">'
        f'<div style="font-size:16px;font-weight:600;color:{_INK};margin-bottom:6px;">'
        f'Muscle imbalances</div>'
        f'<div style="font-size:30px;font-weight:300;color:{_INK};'
        f'font-variant-numeric:tabular-nums;">{shown}'
        f'<span style="font-size:13px;color:{_INK2};margin-left:6px;">imbalances</span></div>'
        f'</div></div>'
    )


def _imbalance_list_html(imbalances: dict) -> str:
    over = imbalances.get("overactive_tight", [])
    under = imbalances.get("underactive_weak", [])
    if not over and not under:
        return ""
    # The headings describe a STATE, not a programme step (2026-10-13): they said
    # "release first" / "activate second" while the programme had run without
    # release since 2026-09-22. The order of work lives in training_plan.py.
    out = '<div class="sb-imblist">'
    if over:
        out += '<div class="grp">Hold tension at rest</div>'
        out += "".join(f'<div class="i"><b style="background:{_BAD}"></b>'
                       f"<span>{name}</span></div>" for name in over)
    if under:
        out += '<div class="grp">Work too little</div>'
        out += "".join(f'<div class="i"><b style="background:{_GOOD}"></b>'
                       f"<span>{name}</span></div>" for name in under)
    return out + "</div>"


def _render_strength_detail() -> None:
    """Strength BioAge detail — hero, a five-series progress display, the
    regional split, and the muscle-balance findings. One continuous scroll."""
    accent = _BIOAGE_COLORS["strength"]
    data = _strength_screen_data()
    st.markdown(_STRENGTH_CSS, unsafe_allow_html=True)

    st.markdown(
        _strength_hero_html(data["overall"], data["calibrating"]),
        unsafe_allow_html=True,
    )
    if data.get("load_error"):
        st.warning(
            "Training history could not be read, so every figure below is "
            "showing its no-data state rather than your actual training — "
            f"{data['load_error']}",
            icon="⚠️",
        )

    # ── Progress ──────────────────────────────────────────────────────────
    # Plain divs, not <h3>: styles.py's global h3 rule forces font-size:10px +
    # uppercase (!important) and would hijack these.
    head_l, head_r = st.columns([2, 1])
    head_l.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;margin-top:6px;'>Progress</div>",
        unsafe_allow_html=True,
    )
    with head_r:
        chosen = st.selectbox(
            "Progress metric", list(ss.METRICS), key="strength_metric",
            label_visibility="collapsed",
        )
    metric = ss.METRICS[chosen]
    is_score = metric["key"] == "score"

    sub_l, sub_r = st.columns([2, 1])
    sub_l.markdown(
        f"<div style='font-size:13px;color:{_INK2};'>{chosen} · {metric['unit']}</div>",
        unsafe_allow_html=True,
    )
    sub_r.markdown(
        f"<div style='text-align:right;font-size:11px;color:{_INK3};'>"
        f"Updated on {data['today'].strftime('%d %b %Y').lstrip('0')}</div>",
        unsafe_allow_html=True,
    )

    chart = (_score_chart_svg(data["score_series"], accent) if is_score
             else _tonnage_chart_svg(data["tonnage"], metric["key"],
                                     _STRENGTH_COLOURS[chosen], chosen))
    st.markdown(
        _strength_readout_html(ss.readout(data, chosen), data["today"].year),
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="sb-chartbox">{chart}</div>', unsafe_allow_html=True)
    if not is_score:
        note = _unloaded_note_html(data["tonnage"], metric["key"])
        if note:
            st.markdown(note, unsafe_allow_html=True)

    # ── Body parts ────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;'>Body parts</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_strength_split_html(data["regions"]), unsafe_allow_html=True)
    st.markdown(_strength_region_strip_html(data["regions"], data.get("core_hold")),
                unsafe_allow_html=True)

    # ── Muscle balance ────────────────────────────────────────────────────
    st.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;margin:18px 0 12px;'>"
        f"Muscle balance analysis</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_muscle_balance_card_html(data["imbalance_count"]), unsafe_allow_html=True)
    st.markdown(_imbalance_list_html(data["imbalances"]), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Metabolism BioAge detail screen (tab_bioage → ?bioage=metabolism).
#
#  Two devices, kept in separate lanes on purpose:
#
#    Foryond foot-only scale — 142 readings, near-daily when the habit holds.
#      Contributes exactly ONE measurement, weight. Its body fat percent is
#      fitted from weight and age (R^2 0.9966) so the fat/lean split shown here
#      is a statement about weight wearing the vocabulary of composition. It is
#      still the best split available and it is labelled as derived everywhere.
#    InBody 770 at the gym — five scans, then nothing for over a year. The only
#      source of PHASE ANGLE and the ECW/TBW ratio, which are the two readings
#      on either device that no height typed at a console can move.
#
#  The screen never blends them. Weight is the only quantity they agree on
#  (mean gap +0.24 kg across five paired dates); everything else they estimate
#  separately, so a fused number would invent agreement that is not there.
#  See services/body_composition.py for the measured constants.
# ─────────────────────────────────────────────────────────────────────────────

_METAB_FAT, _METAB_LEAN, _METAB_DEV = "#B8822A", "#9B6BFF", "#3FA895"

#: Each measure's chart colour. The measures themselves, with their units,
#: spans and better directions, are services/metabolism_screen.METRICS.
_METAB_COLOURS: dict[str, str] = {
    "Weight": _METAB_LEAN, "Fat mass": _METAB_FAT, "Fat-free mass": _METAB_LEAN,
    "Body fat percent": _METAB_FAT, "Phase angle": _METAB_DEV, "ECW / TBW ratio": _METAB_DEV,
}

_METABOLISM_CSS = f"""
<style>
.st-key-metab_metric label {{ display:none !important; }}
.st-key-metab_metric div[data-baseweb="select"] > div {{
  background:rgba(255,255,255,.06) !important; border:1px solid {_HAIR} !important;
  border-radius:9px !important; color:{_INK} !important; font-weight:600 !important; }}
.st-key-metab_metric div[data-baseweb="select"] svg {{ fill:{_INK2} !important; }}
.st-key-metab_metric div[data-baseweb="select"] div {{ font-size:12.5px !important; }}
.st-key-metab_metric {{ max-width:250px; margin-left:auto; }}

/* Range + period stepper. Streamlit buttons, restyled onto the dark screen. */
div[class*="st-key-metab_r_"] button, div[class*="st-key-metab_p_"] button {{
  background:rgba(255,255,255,.05) !important; border:1px solid {_HAIR} !important;
  color:{_INK2} !important; border-radius:8px !important;
  font:600 11.5px/1 system-ui !important; padding:7px 4px !important; width:100%; }}
div[class*="st-key-metab_r_"] button:hover, div[class*="st-key-metab_p_"] button:hover {{
  color:{_INK} !important; background:rgba(255,255,255,.10) !important; }}
div[class*="st-key-metab_r_"] button[kind="primary"] {{
  background:rgba(155,107,255,.22) !important; color:{_INK} !important;
  border-color:rgba(155,107,255,.45) !important; }}
div[class*="st-key-metab_p_"] button:disabled {{ opacity:.3 !important; }}

.mb-plabel {{ text-align:center; line-height:1.25; padding-top:5px; }}
.mb-plabel b {{ display:block; font-size:13px; font-weight:600; color:{_INK};
  font-variant-numeric:tabular-nums; }}
.mb-plabel i {{ display:block; font:400 10px/1.4 ui-monospace,monospace;
  font-style:normal; letter-spacing:.06em; text-transform:uppercase; color:{_INK3}; }}

/* The split bar and chart panel. Named mb-* rather than reusing the sb-*
   classes: _STRENGTH_CSS is only injected by the Strength screen, so borrowing
   its class names here renders them unstyled. */
.mb-splitbar {{ display:flex; gap:2px; height:13px; border-radius:7px; overflow:hidden;
  background:rgba(255,255,255,.05); margin:6px 0 0; }}
.mb-splitbar i {{ display:block; height:100%; }}
.mb-splitkey {{ display:flex; flex-wrap:wrap; gap:18px; margin:10px 0 14px;
  font-size:11.5px; color:{_INK2}; }}
.mb-splitkey span {{ display:inline-flex; align-items:center; gap:7px; }}
.mb-splitkey b {{ width:9px; height:9px; border-radius:3px; display:inline-block; }}
.mb-chartbox {{ background:{_PANEL}; border:1px solid {_HAIR}; border-radius:16px;
  padding:12px 8px 4px; margin:10px 0 18px; }}

.mb-readout {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px;
  background:{_PANEL}; border:1px solid {_HAIR}; border-radius:14px;
  padding:14px 18px; margin-top:10px; }}
.mb-readout .k {{ font:600 9px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
  letter-spacing:.13em; text-transform:uppercase; color:{_INK3}; }}
.mb-readout .v {{ font-size:22px; font-weight:600; color:{_INK}; margin-top:8px;
  line-height:1.1; font-variant-numeric:tabular-nums; }}
.mb-readout .v u {{ text-decoration:none; font-size:12px; font-weight:400;
  color:{_INK2}; margin-left:5px; }}
@media (max-width:520px) {{ .mb-readout {{ grid-template-columns:1fr; }} }}

.mb-cards {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
@media (max-width:640px) {{ .mb-cards {{ grid-template-columns:1fr; }} }}
.mb-card {{ background:{_PANEL}; border:1px solid {_HAIR}; border-radius:14px;
  padding:13px 15px 12px; }}
.mb-card .top {{ display:flex; justify-content:space-between; align-items:baseline;
  gap:10px; }}
.mb-card .nm {{ font-size:13.5px; font-weight:600; line-height:1.3; }}
.mb-card .dt {{ font:11px ui-monospace,monospace; color:{_INK3}; white-space:nowrap;
  font-variant-numeric:tabular-nums; }}
.mb-card .val {{ font-size:25px; font-weight:300; color:{_INK}; margin-top:5px;
  font-variant-numeric:tabular-nums; line-height:1.15; }}
.mb-card .val u {{ text-decoration:none; font-size:12px; color:{_INK2}; margin-left:5px; }}
.mb-card.empty .val {{ color:{_INK3}; }}
.mb-card .foot {{ display:flex; justify-content:space-between; align-items:center;
  gap:8px; margin-top:9px; }}
.mb-src {{ font:600 8.5px/1.7 ui-monospace,monospace; letter-spacing:.1em;
  text-transform:uppercase; padding:1px 7px; border-radius:5px; white-space:nowrap; }}
.mb-src.measured {{ background:rgba(155,107,255,.16); color:#C6A9FF; }}
.mb-src.derived {{ background:rgba(255,255,255,.06); color:{_INK3}; }}
.mb-src.absent {{ background:rgba(196,120,120,.14); color:{_BAD}; }}
.mb-pill {{ font:600 9px/1.7 ui-monospace,monospace; letter-spacing:.1em;
  text-transform:uppercase; padding:1px 8px; border-radius:20px; white-space:nowrap; }}
.mb-pill.ok {{ background:rgba(107,175,139,.18); color:{_GOOD}; }}
.mb-pill.bad {{ background:rgba(196,120,120,.18); color:{_BAD}; }}
.mb-grp {{ font:600 9px/1 ui-monospace,monospace; letter-spacing:2px;
  text-transform:uppercase; color:{_INK3}; margin:20px 0 9px; }}
.mb-grp span {{ color:{_INK2}; text-transform:none; letter-spacing:0;
  font-family:system-ui,sans-serif; font-weight:400; font-size:11px; margin-left:9px; }}

div[class*="st-key-metab_add_"] button {{
  background:{_PANEL} !important; border:1px solid rgba(155,107,255,.28) !important;
  color:{_INK} !important; border-radius:14px !important; width:100%;
  padding:16px 14px !important; font:600 14px/1.3 system-ui !important; }}
div[class*="st-key-metab_add_"] button:hover {{
  border-color:rgba(155,107,255,.55) !important;
  background:rgba(155,107,255,.07) !important; }}
</style>
"""


def _metab_hero_html(fat: float | None, lean: float | None,
                     taken: date | None, accent: str) -> str:
    """Fat and fat-free in kilograms, which is the most the data supports.

    Not an age in years: the scale already ships one and it is
    `-20.73 + 1.226*body_fat_pct + 0.900*chronological age`, i.e. age predicting
    age. A composition hero also degrades honestly — it can say how old the
    reading is, where a number in years just keeps printing."""
    bg = _bioage_b64(str(_BIOAGE_BG_DIR / "derived" / "metabolism_hero.png"))
    layer = (
        f"background-image:linear-gradient(100deg,rgba(11,15,26,0.95) 0%,"
        f"rgba(11,15,26,0.62) 36%,rgba(11,15,26,0.10) 66%),url('{bg}');"
        f"background-size:contain;background-repeat:no-repeat;"
        f"background-position:center right;"
    ) if bg else "background:#0B0F1A;"
    if fat is None or lean is None:
        body = (
            f"<div style='font-size:30px;font-weight:800;color:#555;line-height:1;"
            f"margin-top:6px;'>—</div>"
            f"<div style='font-size:12.5px;color:{_INK3};margin-top:8px;'>"
            f"No weigh-in on record yet.</div>"
        )
    else:
        body = (
            f"<div style='font-size:44px;font-weight:800;color:{_INK};line-height:1;"
            f"font-variant-numeric:tabular-nums;'>{fat:.1f}"
            f"<u style='text-decoration:none;font-size:17px;font-weight:500;"
            f"color:{_INK2};margin-left:8px;'>kg fat</u>"
            f"<span style='margin:0 14px;color:{_INK3};'>·</span>{lean:.1f}"
            f"<u style='text-decoration:none;font-size:17px;font-weight:500;"
            f"color:{_INK2};margin-left:8px;'>kg fat-free</u></div>"
            f"<div style='display:inline-block;font:600 9.5px/1.7 ui-monospace,monospace;"
            f"letter-spacing:.12em;text-transform:uppercase;padding:2px 9px;"
            f"border-radius:20px;margin-top:12px;background:rgba(107,175,139,.18);"
            f"color:{_GOOD};'>Measured · "
            f"{taken.strftime('%d %b %Y').lstrip('0')}</div>"
        )
    # Double quotes on the outer style attribute: `layer` contains
    # url('data:...'), and single-quoting the attribute would close it at the
    # first quote of the URL and drop the background entirely.
    return (
        f'<div style="position:relative;{_CARD_DIMENSIONS_CSS}overflow:hidden;'
        f'border-radius:22px;margin-bottom:14px;border:1px solid rgba(255,255,255,0.08);'
        f'box-shadow:0 8px 32px rgba(0,0,0,0.4);{layer}">'
        f'<div style="position:relative;z-index:1;height:100%;box-sizing:border-box;'
        f'padding:26px 24px;display:flex;flex-direction:column;justify-content:center;"><div>'
        f'<div style="font-size:11px;color:{accent};letter-spacing:2px;'
        f'text-transform:uppercase;font-weight:600;margin-bottom:8px;">Composition</div>'
        f"{body}</div></div></div>"
    )


def _metab_split_html(split: dict | None) -> str:
    """Fat against fat-free (services/metabolism_screen.split), which total the
    weight by construction — a restatement of one number, never corroboration
    of it."""
    if split is None:
        return ""
    fat, lean, total, pct = split["fat"], split["lean"], split["total"], split["fat_pct"]
    return (
        f'<div class="mb-splitbar">'
        f'<i style="width:{pct:.1f}%;background:{_METAB_FAT}"></i>'
        f'<i style="width:{100 - pct:.1f}%;background:{_METAB_LEAN}"></i></div>'
        f'<div class="mb-splitkey">'
        f'<span><b style="background:{_METAB_FAT}"></b>Fat {fat:.1f} kg · {pct:.1f}%</span>'
        f'<span><b style="background:{_METAB_LEAN}"></b>Fat-free {lean:.1f} kg · '
        f'{100 - pct:.1f}%</span>'
        f'<span style="color:{_INK3}">total {total:.1f} kg</span></div>'
    )


#: How a change is coloured, by services/metabolism_screen.change_tone.
_METAB_TONE: dict[str, str] = {"flat": _INK3, "neutral": _INK2, "good": _GOOD, "bad": _WARN}


def _metab_readout_html(s: dict) -> str:
    """Latest, and the change across what the chart is showing
    (services/metabolism_screen.series).

    The change is first-to-last of the VISIBLE points, not of the whole series
    — a number that disagrees with the picture beside it teaches the reader to
    trust neither — and it is coloured by what is better for this measure
    (fault F11: every rise used to be amber and every fall green)."""
    unit, dp = s["metric"]["unit"], s["metric"]["dp"]

    def cell(key: str, value: str) -> str:
        return f'<div><div class="k">{key}</div><div class="v">{value}</div></div>'

    first, last = s["first"], s["last"]
    if last is None:
        return (f'<div class="mb-readout">{cell("Latest", "—")}'
                f'{cell("Change", "—")}</div>')
    last_day, last_val = last
    latest = cell(f"Latest · {last_day.strftime('%d %b %Y').lstrip('0')}",
                  f"{last_val:.{dp}f}<u>{unit}</u>" if unit else f"{last_val:.{dp}f}")
    if s["change"] is None:
        return f'<div class="mb-readout">{latest}{cell("Change · one reading only", "—")}</div>'
    delta = s["change"]
    colour = _METAB_TONE[s["tone"]]
    sign = "" if s["tone"] == "flat" else ("−" if delta < 0 else "+")
    span = (f"Change · {first[0].strftime('%d %b %Y').lstrip('0')} → "
            f"{last_day.strftime('%d %b %Y').lstrip('0')}")
    body = (f'<span style="color:{colour}">{sign}{abs(delta):.{dp}f}'
            f'{f"<u>{unit}</u>" if unit else ""}</span>')
    return f'<div class="mb-readout">{latest}{cell(span, body)}</div>'


def _metab_chart_svg(points: list[tuple], colour: str, dp: int, min_span: float,
                     window, runs: list[list], label: str) -> str:
    """One series across a calendar window, auto-scaled to what is visible.

    `min_span` stops a zoomed-in week of near-identical readings being magnified
    into drama, and `runs` carries the gap breaks so the 97-day injury hole is
    never drawn as a line."""
    w, h, pl, pr, pt, pb = 640, 236, 46, 16, 16, 30
    iw, ih = w - pl - pr, h - pt - pb
    lo_d, hi_d = window.start.toordinal(), window.end.toordinal()
    span_d = max(1, hi_d - lo_d)

    def x_at(day: date) -> float:
        return pl + (day.toordinal() - lo_d) / span_d * iw

    if not points:
        return (
            f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" '
            f'aria-label="{label}, no reading in {window.label}">'
            f'<text x="{w / 2}" y="{pt + ih / 2 - 6}" text-anchor="middle" '
            f'font-size="13" fill="{_INK2}" font-family="system-ui">'
            f'No reading in {window.label}</text></svg>'
        )

    # The scale is the engine's (metabolism_screen.chart_axis), so the phone draws the same.
    axis = ms.chart_axis(points, min_span, dp, window)
    y_lo, y_hi = axis["lo"], axis["hi"]

    def y_at(value: float) -> float:
        return pt + (1 - (value - y_lo) / (y_hi - y_lo)) * ih

    out = _svg_frame(axis["y_labels"], axis["x_labels"], w, h, pl, pr, pt, pb)

    for run in runs:
        if len(run) < 2:
            continue
        pts = " ".join(f"{x_at(d):.1f},{y_at(v):.1f}" for d, v in run)
        out += (f'<polyline points="{pts}" fill="none" stroke="{colour}" '
                f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round" '
                f'opacity="0.85"/>')
    radius = 1.9 if len(points) > 40 else 3.2
    for day, value in points:
        out += (f'<circle cx="{x_at(day):.1f}" cy="{y_at(value):.1f}" r="{radius}" '
                f'fill="{colour}" opacity="0.8"/>')
    last_day, last_val = points[-1]
    out += (
        f'<circle cx="{x_at(last_day):.1f}" cy="{y_at(last_val):.1f}" r="11" '
        f'fill="{colour}" opacity="0.18"/>'
        f'<circle cx="{x_at(last_day):.1f}" cy="{y_at(last_val):.1f}" r="5" '
        f'fill="{colour}" stroke="#0B0F1A" stroke-width="2"/>'
        f'<text x="{x_at(last_day) - 15:.1f}" y="{y_at(last_val) - 13:.1f}" '
        f'text-anchor="end" font-size="11" fill="{colour}" '
        f'font-family="ui-monospace, monospace">{last_val:.{dp}f}</text>'
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" aria-label="{label}, '
        f'{len(points)} readings in {window.label}">{out}</svg>'
    )


def _metab_card_html(name: str, value: str, unit: str, when: str, source: str,
                     pill: tuple[str, str] | None, colour: str) -> str:
    empty = value == "—"
    pill_html = (f'<span class="mb-pill {pill[0]}">{pill[1]}</span>') if pill else ""
    return (
        f'<div class="mb-card{" empty" if empty else ""}">'
        f'<div class="top"><span class="nm" style="color:{colour}">{name}</span>'
        f'<span class="dt">{when} &rsaquo;</span></div>'
        f'<div class="val">{value}{f"<u>{unit}</u>" if unit else ""}</div>'
        f'<div class="foot"><span class="mb-src {source}">{source}</span>'
        f'{pill_html}</div></div>'
    )


def _metab_cellular_html(scan, days_old: int, accent: str) -> str:
    """Phase angle and ECW/TBW — the two readings the entered height cannot
    reach, given their own block above the derived cards because they are the
    only measurements on this screen that are not restatements of weight."""
    if scan is None:
        return ""
    cards = [
        _metab_card_html("Phase angle",
                         f"{scan.phase_angle_deg:.1f}" if scan.phase_angle_deg else "—",
                         "°", scan.day.strftime("%d %b %Y").lstrip("0"),
                         "measured" if scan.phase_angle_deg else "absent",
                         ("bad", f"{days_old} days old"), _METAB_DEV),
        _metab_card_html("ECW / TBW ratio", f"{scan.ecw_tbw:.3f}", "",
                         scan.day.strftime("%d %b %Y").lstrip("0"), "measured",
                         ("bad", f"{days_old} days old"), _METAB_DEV),
    ]
    return f'<div class="mb-cards">{"".join(cards)}</div>'


def _metab_analysis_html(groups: list[dict], when: str, accent: str) -> str:
    """Every remaining figure, each labelled with what it really is
    (services/metabolism_screen.analysis). No card carries a status pill: the
    "Normal" each derived card printed was no check (fault F11)."""
    out = ""
    for group in groups:
        out += (f'<div class="mb-grp">{group["group"]}<span>{group["blurb"]}</span></div>'
                f'<div class="mb-cards">')
        for card in group["cards"]:
            value = "—" if card["value"] is None else f'{card["value"]:.{card["dp"]}f}'
            out += _metab_card_html(card["name"], value, card["unit"],
                                    when if value != "—" else "no reading",
                                    card["source"], None, accent)
        out += "</div>"
    return out


def _render_metabolism_detail() -> None:
    """Metabolism BioAge detail — composition hero, a steppable progress
    display, the two height-immune readings, and the derived cards."""
    accent = _BIOAGE_COLORS["metabolism"]
    data = _metabolism_screen_data()
    st.markdown(_METABOLISM_CSS, unsafe_allow_html=True)

    readings, scans, today = data["readings"], data["scans"], data["today"]
    latest = readings[-1] if readings else None

    st.markdown(
        _metab_hero_html(latest.fat_mass_kg if latest else None,
                         latest.fat_free_mass_kg if latest else None,
                         latest.day if latest else None, accent),
        unsafe_allow_html=True,
    )
    if data.get("load_error"):
        st.warning(
            "The readings could not be read, so the figures below are "
            f"showing their no-data state — {data['load_error']}",
            icon="⚠️",
        )
    if latest:
        st.markdown(_metab_split_html(ms.split(latest)), unsafe_allow_html=True)

    # ── Progress ──────────────────────────────────────────────────────────
    head_l, head_r = st.columns([2, 1])
    head_l.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;margin-top:6px;'>"
        f"Progress</div>",
        unsafe_allow_html=True,
    )
    with head_r:
        chosen = st.selectbox("Progress metric", list(ms.METRICS),
                              key="metab_metric", label_visibility="collapsed")

    kind = st.session_state.get("metab_range", "all")
    offset = st.session_state.get("metab_offset", 0)
    shown = ms.series(data, chosen, kind, offset)
    metric, window = shown["metric"], shown["window"]

    cols = st.columns([1, 1, 1, 1, 1, 3, 1])
    for i, (label, key) in enumerate(ms.RANGES):
        if cols[i].button(label, key=f"metab_r_{key}", use_container_width=True,
                          type="primary" if key == kind else "secondary"):
            # A new granularity always opens on the period containing today —
            # carrying an offset across a switch lands you somewhere arbitrary.
            st.session_state["metab_range"] = key
            st.session_state["metab_offset"] = 0
            st.rerun()

    if cols[4].button("‹", key="metab_p_prev", use_container_width=True,
                      disabled=not shown["can_back"]):
        st.session_state["metab_offset"] = offset - 1
        st.rerun()
    cols[5].markdown(
        f'<div class="mb-plabel"><b>{window.label}</b><i>{window.sub}</i></div>',
        unsafe_allow_html=True,
    )
    if cols[6].button("›", key="metab_p_next", use_container_width=True,
                      disabled=not shown["can_forward"]):
        st.session_state["metab_offset"] = offset + 1
        st.rerun()

    st.markdown(_metab_readout_html(shown), unsafe_allow_html=True)
    st.markdown(
        f'<div class="mb-chartbox">'
        f'{_metab_chart_svg(shown["points"], _METAB_COLOURS[chosen], metric["dp"], metric["span"], window, shown["runs"], chosen)}'
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Cellular health ───────────────────────────────────────────────────
    cell = ms.cellular(scans, today)
    if cell:
        st.markdown(
            f"<div style='color:{_INK};font-size:18px;font-weight:600;margin:6px 0 2px;'>"
            f"Cellular health</div>"
            f"<div style='font-size:11px;color:{_INK3};margin-bottom:9px;'>"
            f"{cell['device']} · nothing else measures these</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            _metab_cellular_html(cell["scan"], cell["days_old"], accent),
            unsafe_allow_html=True,
        )

    # ── Body analysis ─────────────────────────────────────────────────────
    st.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;margin:22px 0 2px;'>"
        f"Body analysis</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        _metab_analysis_html(ms.analysis(latest),
                             latest.day.strftime("%d %b %Y").lstrip("0") if latest else "",
                             accent),
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level cached data fetchers  (must live outside render() so that
#  Streamlit recognises them as stable across reruns)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _bio():
    # engine.py/readiness.py still work on plain dicts -- asdict() converts
    # the typed BiometricRecord back to the exact shape they expect.
    return [asdict(r) for r in repo.get_repository().get_biometric_rolling(days=28)]

# The Engine Data tab's own readers (_bio_drift, _au, _streak, _tight, _diag,
# _stage, _stage_start) were removed on 2026-10-19: the tab reads
# decision.engine_state through _engine_state below, the same reads and
# arithmetic as the directive Home and Training show.

@st.cache_data(ttl=1800, show_spinner=False)
def _sync_engine_view(sheet_id: str) -> list[dict]:
    records = repo.get_repository().get_biometric_rolling(days=28)
    return [asdict(r) for r in records]

@st.cache_data(ttl=1800, show_spinner=False)
def _blend_history() -> list[dict]:
    return [asdict(r) for r in repo.get_repository().get_biometric_blend_history()]


@st.cache_data(ttl=1800, show_spinner=False)
def _metrics_history() -> list[dict]:
    return repo.get_repository().get_metrics_history()


@st.cache_data(ttl=1800, show_spinner=False)
def _sleep_fusion_history() -> list[dict]:
    return repo.get_repository().get_sleep_fusion_history()


@contextmanager
def _manual_sync(spinner_message: str):
    """Wraps a manual sync button: spinner, plus the background runner's
    one-at-a-time lock so the button cannot collide with the automatic chain.

    These buttons call Repository.sync_* directly instead of going through
    run_home_syncs, so the runner's lock is the only thing that can serialise
    them — see BackgroundSyncRunner.exclusive() for why racing corrupts rows
    (upsert_row_by_key is find-then-write, so two chains appending the same
    missing date give it two rows) rather than merely wasting calls.

    The button queues rather than forcing through. That costs nothing,
    because every one of these buttons runs the same work as the automatic
    step over a window at least as wide.
    """
    with st.spinner(spinner_message):
        with repo.get_sync_runner().exclusive():
            yield


# Sleep-stage rendering moved to styles.py (shared with app.py's Sleep
# drill-down) — see styles.STAGE_BAND / hypnogram_svg / stage_legend_html.

@st.cache_data(ttl=1800, show_spinner=False)
def _engine_state() -> dict:
    """Everything Engine Data shows below its banner, read once for today
    (decision.engine_state: the same reads and arithmetic as the directive)."""
    return decision.engine_state(repo.get_repository(), date.today(), with_stage_status=True)


@st.cache_data(ttl=1800, show_spinner=False)
def _recent_sessions():
    return repo.get_repository().get_recent_sessions(days=60)


# ─────────────────────────────────────────────────────────────────────────────
#  Flexibility detail screen (tab_bioage → ?bioage=flexibility). v3 — clusters.
#
#  THREE STATES, DESIGNED SEPARATELY. Empty is not a degraded version of
#  populated — it is where this athlete actually is, and it is the only state
#  with an obvious single action. It gets its own screen with one button on it.
#
#  CAPTURE STOPS AT THE FIRST FAILING SLOT, and that is not a shortcut — it is
#  the method. Slots below a failure are meaningless rather than lower priority,
#  so continuing would collect numbers that cannot be read. The screen runs the
#  real battery against the draft after every step rather than duplicating the
#  rule, so the flow and the engine cannot disagree about when to stop.
#
#  Populated leads with the PATTERN and the one thing to train. The model this
#  replaced led with the worst rung across every ladder, which is how
#  "chest/pecs is limiting you" got shown against a goal chest has nothing to
#  do with.
# ─────────────────────────────────────────────────────────────────────────────

_ACCENT_FLEX = _BIOAGE_COLORS["flexibility"]

_FLEXIBILITY_CSS = f"""
<style>
.fx-card {{ background:{_PANEL}; border:1px solid {_HAIR}; border-radius:14px;
           padding:16px 18px; margin-bottom:10px; }}
.fx-card.hi {{ border-color:rgba(196,120,120,.45); background:rgba(196,120,120,.07); }}
.fx-cap {{ font-size:9px; letter-spacing:.13em; text-transform:uppercase;
          color:{_INK3}; font-weight:700; }}
.fx-huge {{ font-size:38px; font-weight:800; line-height:1.08; margin-top:8px; }}
.fx-big {{ font-size:28px; font-weight:800; line-height:1.12; margin-top:6px; }}
.fx-sm {{ font-size:12px; color:{_INK2}; margin-top:8px; line-height:1.65; }}
.fx-read {{ font-size:12.5px; color:{_INK2}; line-height:1.65; margin:8px 0 4px; }}
.fx-row {{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; }}
.fx-nm {{ font-size:15px; font-weight:650; color:{_INK}; }}
.fx-kv {{ display:flex; gap:16px; flex-wrap:wrap; margin-top:9px; font-size:11.5px;
         color:{_INK3}; }}
.fx-kv b {{ color:{_INK2}; font-weight:650; }}
.fx-lock {{ background:rgba(191,160,106,.11); border:1px solid rgba(191,160,106,.32);
           color:#E2CB9B; border-radius:10px; padding:11px 13px; font-size:11.5px;
           line-height:1.65; margin:12px 0; }}
.fx-steps {{ display:flex; gap:3px; margin-bottom:14px; }}
.fx-steps i {{ height:3px; flex:1; border-radius:2px; background:rgba(255,255,255,.10); }}
.fx-steps i.done {{ background:{_GOOD}; }}
.fx-steps i.now {{ background:{_ACCENT_FLEX}; }}
.fx-steps i.skip {{ background:{_INK3}; }}
.fx-pill {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:9.5px;
           font-weight:700; }}
.fx-rung {{ border:1px solid {_HAIR}; border-radius:10px; padding:9px 12px 10px;
           margin-bottom:6px; }}
.fx-rung.limit {{ border-color:{_ACCENT_FLEX}; background:rgba(34,195,230,.06); }}
.fx-rung .top {{ display:flex; justify-content:space-between; align-items:baseline;
           gap:10px; font-size:12px; color:{_INK}; }}
.fx-rung .top b {{ font-weight:650; }}
.fx-rung .mus {{ font-size:10.5px; color:{_INK2}; }}
.fx-rung .val {{ font-size:11.5px; color:{_INK2}; white-space:nowrap;
           font-variant-numeric:tabular-nums; }}
.fx-rung .bar {{ height:5px; border-radius:3px; background:rgba(255,255,255,.08);
           margin-top:7px; overflow:hidden; }}
.fx-rung .bar i {{ display:block; height:5px; border-radius:3px; }}
.fx-rung .det {{ font-size:10.5px; color:{_INK2}; margin-top:6px; line-height:1.5; }}
.fx-rung .tag {{ font-size:9px; letter-spacing:.11em; text-transform:uppercase;
           font-weight:700; }}
/* The page-wide caption style is 10px dim grey, which is fine for metadata but
   unreadable for protocol text — and on this screen the athlete READS captions
   mid-test. Injected after styles.py's sheet, so it wins at equal specificity. */
[data-testid="stCaptionContainer"] p {{ color:{_INK2} !important;
    font-size:12px !important; line-height:1.6 !important; }}
</style>
"""


def _fx_bold(text: str) -> str:
    """`**x**` -> `<b>x</b>`, for the fields rendered as raw HTML.

    The protocol text is authored in markdown so it reads correctly in the
    source documents and in st.caption. Three fields go out through
    st.markdown(unsafe_allow_html=True) instead, where markdown is NOT applied
    and the asterisks would show literally — and the emphasis is load-bearing,
    because it marks the tell that says a trial is void.
    """
    parts = text.split("**")
    return "".join(p if i % 2 == 0 else f"<b>{p}</b>" for i, p in enumerate(parts))


# ── state 1: empty ───────────────────────────────────────────────────────────

def _fx_render_empty(accent: str) -> None:
    spec = fx.CLUSTERS[fx.DEFAULT_CLUSTER]
    n = len(spec["battery"].AVAILABLE_TESTS)
    st.markdown(
        f'<div class="fx-card"><div class="fx-cap">Standing goal &middot; no deadline</div>'
        f'<div class="fx-huge" style="color:{accent};">Not measured</div>'
        f'<div class="fx-sm">{spec["label"]} &middot; up to {n} tests &middot; measured '
        f'<b style="color:{_INK2};">cold</b>, no warm-up.<br>'
        f'Every twelve weeks. It usually stops early &mdash; the first failing slot is '
        f'your answer, and nothing below it is worth measuring.</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Start assessment", key="fx_start", use_container_width=True,
                 type="primary"):
        st.session_state["fx_mode"] = "capture"
        st.session_state["fx_step"] = 0
        st.rerun()

    st.markdown(
        f'<div class="fx-card" style="margin-top:12px;">'
        f'<div class="fx-cap">What this produces</div>'
        f'<div class="fx-sm">One <b style="color:{_INK2};">pattern label</b>, and nothing '
        f'else. Not a score. The label is what the training stack is looked up by &mdash; '
        f'and a stack without a label is a guess, so the app refuses to produce one.'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # THREE slots, not four: gate 0 was removed on the athlete's instruction,
    # 2026-08-12 — see cluster_a_battery.REMOVED_GATE_0. The slot vocabulary in
    # services/battery.py still carries SLOT_STRUCTURE because it is the general
    # layer and another cluster may use it; this screen shows the slots THIS
    # cluster actually runs, which is what the evaluator list decides.
    with st.expander("The slots, and why they run in order"):
        for slot in (btry.SLOT_REGRESSED,
                     btry.SLOT_PREREQUISITE, btry.SLOT_SPECTRUM):
            st.markdown(f"**{slot}. {btry.SLOT_LABELS[slot]}** — "
                        f"{btry.SLOT_QUESTIONS[slot]}")
            st.caption(f"Decides: {btry.SLOT_DECIDES[slot]}")
        st.caption("Stop at the first failure. There is no value in measuring a spectrum "
                   "profile for a skill an earlier slot has already made unavailable.")

    # The expected-outcome expander was REMOVED from this screen on the
    # athlete's request (2026-08-07). The prediction itself stays in
    # cluster_a_battery.EXPECTED_PATTERN — its job is to be written down BEFORE
    # measuring, which the code does; the screen does not need to advertise it.
    held = list(cba.DEFERRED_TESTS)
    if held:
        with st.expander(f"Held back for now · {len(held)}"):
            st.caption("Held on a CONDITION rather than a date — a date passes whether or "
                       "not the thing it was waiting for has happened, which is how a hold "
                       "becomes permanent by nobody looking at it.")
            for key in held:
                test = cba.TESTS[key]
                st.markdown(f"**{test.label}** — until {test.deferred_until}")
                if test.safety:
                    st.caption(_fx_bold(test.safety))


# ── state 2: capture ─────────────────────────────────────────────────────────

def _fx_steps_html(order: list, step: int, draft) -> str:
    ticks = [f'<i class="{state}"></i>' for state in fxs.step_ticks(order, step, draft)]
    return f'<div class="fx-steps">{"".join(ticks)}</div>'


def _fx_render_capture(accent: str) -> None:
    repo_ = repo.get_repository()
    spec = fx.CLUSTERS[fx.DEFAULT_CLUSTER]
    battery_mod = spec["battery"]

    draft = repo_.get_flexibility_draft()

    # ── the cold gate ───────────────────────────────────────────────────────
    if draft is None:
        st.markdown(
            f'<div class="fx-card"><div class="fx-cap">Before you start</div>'
            f'<div class="fx-big" style="color:{accent};">Measure cold</div>'
            f'<div class="fx-sm">No warm-up, no session beforehand, first thing. A warm '
            f'reading measures a viscoelastic effect that is gone within hours &mdash; a '
            f'cold one isolates the durable change. A warm session is still worth '
            f'recording, but it is labelled and never compared with a cold one.'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        cold = st.radio("Is this a cold measurement?",
                        ["Cold — no warm-up", "Warm — I have trained today"],
                        key="fx_cold", label_visibility="collapsed")

        # The other half of "measure cold": yesterday. A leg day the day before
        # reads as extra tightness in exactly the areas being tested, so even a
        # genuinely cold reading this morning measures the leg day, not the
        # baseline. Warn, never block — but say what the reading would mean.
        if fxs.legs_loaded_yesterday(repo_, date.today()):
            st.warning("Yesterday's session loaded your legs. A cold reading this "
                       "morning will read tighter than your real baseline in "
                       "exactly the areas being tested — measure after a legs-free "
                       "day, or record today knowing it is not comparable with a "
                       "clean morning.", icon="⚠️")

        with st.expander("How to understand the three numbers", expanded=True):
            for measure, short, long in flexibility_baselines.MEASURES_EXPLAINED:
                st.markdown(f"**{measure.title()} — {short}**")
                st.caption(long)
            st.markdown(flexibility_baselines.GAP_EXPLAINED)
            st.caption("Assisted work always comes after unassisted: the spectrum runs "
                       "**active → isometric → passive**, and the tilt runs own power "
                       "before helped. Help and passive work leave everything looser, so "
                       "taking either first would flatter what follows it.")

        with st.expander("What a LOCK is, and what to do if you lose it"):
            st.markdown(flexibility_baselines.LOCK_EXPLAINED)

        with st.expander("Measure these once, then re-use them forever"):
            st.caption("Setup numbers, not scores. Get one wrong and two sessions are not "
                       "comparable however carefully each was measured.")
            for name, why in flexibility_baselines.FROZEN_CONSTANTS:
                st.markdown(f"**{name.replace('_', ' ')}** — {why}")
            moving_name, moving_why = flexibility_baselines.PROGRESSION_VARIABLE
            st.markdown(f"**{moving_name.replace('_', ' ')}** — *this one is meant to "
                        f"move.* {moving_why}")

        with st.expander("Two things to record but never chase"):
            st.markdown("**The nerve check**")
            st.markdown(_fx_bold(cba.NERVE_CHECK))
            st.markdown("**Medial knee discomfort**")
            st.markdown(_fx_bold(cba.MEDIAL_KNEE_NOTE))

        c1, c2 = st.columns([2, 1])
        if c1.button("Begin", key="fx_begin", use_container_width=True, type="primary"):
            repo_.save_flexibility_draft(fxs.begin(date.today(), cold.startswith("Cold"),
                                                   spec["key"]))
            st.rerun()
        if c2.button("Cancel", key="fx_cancel0", use_container_width=True):
            st.session_state["fx_mode"] = None
            st.rerun()
        return

    # ── has the battery already reached an answer? ──────────────────────────
    #
    # Asked of the REAL engine rather than re-implemented here, so the flow and
    # the battery cannot disagree about when to stop. This is the early exit,
    # and it is the method rather than a convenience: once a slot has failed,
    # everything below it is unreadable and collecting it wastes 30 minutes.
    live = fxs.live_result(draft)
    if live.pattern:
        st.markdown(
            f'<div class="fx-card hi"><div class="fx-cap" style="color:{_GOOD};">'
            f'That is your answer &mdash; stop here</div>'
            f'<div class="fx-big" style="color:{accent};">Pattern {live.pattern} '
            f'&middot; {cba.PATTERNS[live.pattern]}</div>'
            f'<div class="fx-sm">{live.slots[-1].reason}</div>'
            f'<div class="fx-sm">The remaining tests measure things below the slot that '
            f'stopped you, and a reading taken below a failure cannot be interpreted. '
            f'There is nothing more to collect today.</div></div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([2, 1])
        if c1.button("Save assessment", key="fx_finish_early", use_container_width=True,
                     type="primary"):
            fxs.finish(repo_, draft)
            _flexibility_screen_data.clear()
            st.session_state["fx_mode"] = None
            st.rerun()
        if c2.button("Keep going anyway", key="fx_continue", use_container_width=True):
            st.session_state["fx_force_continue"] = True
            st.rerun()
        if not st.session_state.get("fx_force_continue"):
            return

    # The LIVE order, asked of the battery module rather than computed here —
    # a neutral reading well off the floor puts the turned-out comparison out
    # of scope, and the module owns that rule so the screen cannot disagree
    # with the evaluator about when it matters.
    order = fxs.capture_order(draft)
    step = fxs.clamp_step(st.session_state.get("fx_step", 0), order)
    key = order[step]
    test = battery_mod.TESTS[key]

    st.markdown(_fx_steps_html(order, step, draft), unsafe_allow_html=True)
    for note in fxs.skip_notes(draft):
        st.caption(note)
    st.markdown(
        f'<div class="fx-row"><span class="fx-nm">{test.label}</span>'
        f'<span class="fx-cap">{step + 1} of {len(order)} &middot; slot {test.slot} '
        f'{btry.SLOT_LABELS[test.slot]}</span></div>',
        unsafe_allow_html=True,
    )

    # The lock is the loudest thing on the screen, above the setup and above the
    # fields — a lost lock makes the reading BETTER, not worse, so nothing warns
    # you and the tell has to be impossible to miss.
    st.markdown(f'<div class="fx-lock"><b>LOCK</b> &mdash; {_fx_bold(test.lock)}</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="fx-card"><div class="fx-sm" style="color:{_INK2};">'
                f'{_fx_bold(test.setup)}</div></div>', unsafe_allow_html=True)

    with st.expander("How to read it"):
        st.caption(_fx_bold(test.measurement))
        st.markdown("**What you're testing**")
        st.caption(test.what_youre_testing)
        if test.adapted_from:
            st.caption(f"*Adapted for you — {test.adapted_from}.*")
        if test.safety:
            st.warning(test.safety, icon="⚠️")

    sides = ["left", "right"] if test.bilateral else [""]
    last = step == len(order) - 1
    existing = {(r.test_key, r.side): r for r in draft.readings}

    # A FORM, not loose inputs. st.number_input does not commit until the field
    # loses focus — type a value, press Save immediately, and Streamlit still
    # holds the old one, silently dropping a reading the athlete physically
    # took. A form commits every field atomically on submit.
    with st.form(key=f"fx_form_{key}", border=False):
        # WHERE the number comes from, at the field itself — the athlete should
        # not have to open an expander to know what to type.
        if test.input_hint:
            st.markdown(f'<div class="fx-read"><b>What to type:</b> '
                        f'{_fx_bold(test.input_hint)}</div>', unsafe_allow_html=True)
        cols = st.columns(len(sides))
        entered: dict[str, float | None] = {}
        for col, side in zip(cols, sides):
            with col:
                if side:
                    st.markdown(f'<div class="fx-cap">{side}</div>', unsafe_allow_html=True)
                prior = existing.get((key, side))
                entered[side] = st.number_input(
                    f"{test.label} {side} ({test.unit})".strip(),
                    value=float(prior.value) if prior else None,
                    step=0.5, format="%.1f",
                    key=f"fx_{key}_{side}", label_visibility="collapsed",
                )

        load = None
        if test.slot == btry.SLOT_SPECTRUM and "isometric" in key:
            load = st.number_input(
                "Added load (kg), if any — logged beside the reading, they are one datum",
                value=None, step=0.5, format="%.1f", key=f"fx_load_{key}",
            )

        # The setup number this trial was taken at. Same principle as the load,
        # and on the bent-knee leverage it is the number that decides which
        # PATTERN comes out — heels closer than the reference drop the knees
        # further, so the test passes too easily and a whole-group restriction
        # reads as a gracilis one.
        setup_value = None
        if test.setup_input:
            # The setup number is the SAME number every session by design, so
            # the last recorded one is offered back: re-measuring it fresh by
            # eye is exactly what makes two sessions incomparable.
            try:
                earlier = repo_.get_flexibility_assessments()
            except Exception:                                  # noqa: BLE001
                earlier = ()
            prior_setup, from_earlier = fxs.prior_setup(draft, earlier, key)
            if from_earlier:
                st.caption(f"Last time you used **{prior_setup:g}**. Use the "
                           f"same number unless something real changed — a "
                           f"new setup number starts a new comparison, and "
                           f"every reading against the old one stops being "
                           f"comparable.")
            setup_value = st.number_input(
                f"{test.setup_input} — recorded beside the reading, they are one datum",
                value=float(prior_setup) if prior_setup is not None else None,
                step=0.5, format="%.1f", key=f"fx_setup_{key}",
            )

        void = st.checkbox("The lock was lost — void this trial",
                           key=f"fx_void_{key}")
        submitted = st.form_submit_button(
            "Save & finish" if last else "Save & next",
            use_container_width=True, type="primary")

    if submitted:
        updated = fxs.apply_entries(draft, key, entered, load=load,
                                    setup_value=setup_value, void=bool(void))
        repo_.save_flexibility_draft(updated)
        if last:
            fxs.finish(repo_, updated)
            _flexibility_screen_data.clear()
            st.session_state["fx_mode"] = None
        else:
            st.session_state["fx_step"] = step + 1
        st.rerun()

    c1, c2, c3 = st.columns(3)
    if c1.button("Skip", key=f"fx_skip_{key}", use_container_width=True):
        st.session_state["fx_step"] = min(step + 1, len(order) - 1)
        st.rerun()
    if c2.button("Back", key=f"fx_back_{key}", use_container_width=True, disabled=step == 0):
        st.session_state["fx_step"] = max(0, step - 1)
        st.rerun()
    if c3.button("Pause", key=f"fx_pause_{key}", use_container_width=True):
        st.session_state["fx_mode"] = None
        st.rerun()


# ── state 3: populated ───────────────────────────────────────────────────────

def _fx_render_ladder(report) -> None:
    """The battery's decision path made visual (athlete's ask, 2026-08-07):
    tightest at the bottom, the working rung highlighted. NOT the v2 rung model
    returning — nothing is aggregated, an unmeasured muscle has no number, and
    the working rung IS the pattern the battery already chose. Rendered in the
    no-pattern state too: seeing what was measured is most useful exactly when
    the battery stopped without an answer."""
    if not report.ladder:
        return
    st.markdown('<div class="fx-cap" style="margin:18px 0 8px;">The ladder &mdash; '
                'tightest at the bottom, work the marked rung first</div>',
                unsafe_allow_html=True)
    rows = []
    for rung in reversed(report.ladder):          # top rung renders first
        cls, tag_color, tag = "", _INK3, ""
        fill, fill_color = 0.0, _GOOD
        if rung.state == btry.RUNG_LIMITING:
            cls, tag_color = " limit", _ACCENT_FLEX
            tag = f"▶ work this first · §{rung.pattern}" if rung.pattern else \
                  "▶ work this first"
            fill, fill_color = rung.fraction or 0.0, _ACCENT_FLEX
        elif rung.state == btry.RUNG_PASSED:
            tag, tag_color = "✓ climbed", _GOOD
            fill = rung.fraction if rung.fraction is not None else 1.0
        elif rung.state == btry.RUNG_CONTEXT:
            tag, tag_color = "context, not diagnosis", _WARN
            fill, fill_color = rung.fraction or 0.0, _WARN
        elif rung.state == btry.RUNG_UNREADABLE:
            tag, tag_color = "botched — repeat", _BAD
        else:
            tag = "not measured"

        if rung.fraction is not None:
            value = (f"{rung.measured:g}{rung.unit} of {rung.target:g}{rung.unit}"
                     f" · {rung.fraction * 100:.0f}%")
        elif rung.measured is not None:
            value = f"{rung.measured:g}{rung.unit}"
        else:
            value = "—"
        prov = (' <span class="tag" style="color:{c};">provisional target</span>'
                .format(c=_INK3) if rung.provisional and rung.fraction is not None
                else "")
        bar = (f'<div class="bar"><i style="width:{fill * 100:.0f}%;'
               f'background:{fill_color};"></i></div>'
               if rung.state not in (btry.RUNG_UNMEASURED, btry.RUNG_UNREADABLE)
               else '<div class="bar"></div>')
        detail = f'<div class="det">{rung.detail}</div>' if rung.detail else ""
        rows.append(
            f'<div class="fx-rung{cls}">'
            f'<div class="top"><span><b>{rung.label}</b> '
            f'<span class="mus">· {rung.muscle}</span></span>'
            f'<span class="val">{value}{prov}</span></div>'
            f'{bar}'
            f'<div class="tag" style="color:{tag_color};margin-top:6px;">{tag}</div>'
            f'{detail}</div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)
    st.caption("A grey rung is unknown, not zero — the battery stops at the first "
               "failure, so rungs above it are unmeasured until you choose to keep "
               "going. No rung is ever averaged with another.")


def _fx_fill_missing(report) -> None:
    """Take the one or two readings the battery is waiting on, right here.

    THE ALTERNATIVE WAS "go back and do the slot again", which is what the
    screen used to say, and it is a bad trade: the athlete has already done the
    work, is already cold, and a slot he mostly completed does not need
    repeating — one number does. The battery decides WHICH number
    (cluster_a_battery.missing_inputs); this only renders it.

    Nothing here judges anything. The values are merged into the stored
    assessment and the battery is re-run over the result, so a filled-in
    reading reaches a pattern by exactly the path a live one does.
    """
    repo_ = repo.get_repository()
    spec = fx.CLUSTERS[fx.DEFAULT_CLUSTER]
    battery_mod = spec["battery"]

    try:
        stored = repo_.get_flexibility_assessments()
    except Exception:                                          # noqa: BLE001
        return
    if not stored:
        return
    assessment = stored[-1]
    missing = fxs.missing_inputs(assessment, report)
    if not missing:
        return

    st.markdown(
        f'<div class="fx-cap" style="margin-top:14px;">Fill in what is missing</div>'
        f'<div class="fx-sm">The slot stopped because {"this reading was" if len(missing) == 1 else "these readings were"} '
        f'never recorded, not because anything was wrong. Add '
        f'{"it" if len(missing) == 1 else "them"} and the battery runs again from '
        f'here &mdash; there is no need to repeat the rest of the slot.</div>',
        unsafe_allow_html=True,
    )

    with st.form(key="fx_fill_missing", border=False):
        entered: dict = {}
        for item in missing:
            st.markdown(f'<div class="fx-read"><b>{item.label}</b> &mdash; {item.hint}</div>',
                        unsafe_allow_html=True)
            entered[item] = st.number_input(
                item.label, value=None, step=0.5, format="%.1f",
                key=f"fx_fill_{item.test_key}_{item.side}_{int(item.setup)}",
                label_visibility="collapsed",
            )
        if not st.form_submit_button("Add and re-run", use_container_width=True):
            return

    updated = fxs.fill_missing(assessment, entered)

    if updated is assessment:
        st.warning("Nothing was entered, so nothing changed.", icon="⚠️")
        return
    repo_.save_flexibility_assessment(updated)
    _flexibility_screen_data.clear()
    st.rerun()


def _fx_render_populated(report, accent: str) -> None:
    result = report.result

    if not report.pattern:
        st.markdown(
            f'<div class="fx-card"><div class="fx-cap">Assessed '
            f'{report.assessed_on:%d %b %Y}</div>'
            f'<div class="fx-big" style="color:{_INK3};">No pattern reached</div>'
            f'<div class="fx-sm">{result.slots[-1].reason if result and result.slots else ""}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        st.info("A missing measurement is not a pass. Re-run the slot that stopped, rather "
                "than reading this as nothing being wrong.", icon="ℹ️")
        _fx_fill_missing(report)
        _fx_render_ladder(report)
        return

    warm = "" if result.cold else (
        f'<span style="color:{_WARN};"> &middot; <b>WARM — not comparable with a cold '
        f'reading</b></span>')
    st.markdown(
        f'<div class="fx-card hi"><div class="fx-cap">{report.cluster_label} &middot; '
        f'assessed {report.assessed_on:%d %b %Y}{warm}</div>'
        f'<div class="fx-cap" style="color:{_BAD};margin-top:8px;">What is stopping you</div>'
        f'<div class="fx-big" style="color:{_BAD};">{report.pattern_label}</div>'
        f'<div class="fx-kv"><span>pattern <b>{report.pattern}</b></span>'
        f'<span>stopped at <b>{report.stopped_at_label}</b></span>'
        f'<span><b>{len(result.slots)}</b> of {fxs.slots_total(report)} slots run</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    st.caption(result.slots[-1].reason)

    # The invented-cut-point FACEPLATE was removed on the athlete's request
    # (2026-08-07) — understood, and it does not need a banner. The distinction
    # itself survives where it belongs: per rung in the ladder ("provisional
    # target") and per slot in the trail expander.
    if not report.trusted:
        st.warning(
            f"This is a **hypothesis, not a verdict**. A pattern is trusted after "
            f"{btry.BASELINE_SESSIONS_REQUIRED} baseline mornings; there "
            f"{'is' if result.baseline_sessions == 1 else 'are'} "
            f"{result.baseline_sessions}. Until then every threshold above is provisional "
            f"and no single reading is a reason to change anything.",
            icon="⚠️")

    _fx_render_ladder(report)

    # ── the stack ───────────────────────────────────────────────────────────
    #
    # 2026-08-07, on the athlete's review: the pre-session release block is the
    # TRAINING PLAN's business and no longer renders here (the prescription
    # layer keeps release_block() for the block build), and stack intros are
    # why-material — the ladder and the slot reason already say what is
    # stopping him, so the stack opens directly on the work.
    try:
        stack = fx.prescribe(report)
    except cluster_a_prescription.NoPatternError as exc:
        st.error(str(exc), icon="🚫")
        return

    st.markdown(f'<div class="fx-cap" style="margin:18px 0 8px;">Your stack &mdash; '
                f'&sect;{stack.pattern}, {stack.limiter}</div>', unsafe_allow_html=True)

    for i, item in enumerate(stack.live_items, 1):
        ex = cluster_a_mechanics.exercise(item.exercise)
        tint = _GOOD if ex and ex.spectrum == flexibility_baselines.RESISTED else _INK3
        with st.expander(f"{i}. {item.exercise}  ·  {item.dose}"):
            if ex:
                st.markdown(f'<span class="fx-cap" style="color:{tint};">{ex.spectrum}'
                            f'</span>', unsafe_allow_html=True)
                # HOW before WHY — the athlete's direction (2026-08-07). The
                # why is assumed correct in the background; understanding how
                # is the part the user needs mid-session.
                if ex.position:
                    st.markdown(f"**Position** — {ex.position}")
                    st.markdown(f"**The movement** — {ex.movement}")
                    st.markdown(f"**You should feel** — {ex.feel}")
                    st.markdown(f"**Stop rule** — {ex.stop}")
                    st.markdown(f"**Progress is** — {ex.progress}")
                # Readable ink by construction (fx-read), not by hoping the
                # page-wide caption override wins — the dim grey these used to
                # inherit is banned for anything the athlete actually reads.
                if ex.note:
                    st.markdown(f'<div class="fx-read">Why — {_fx_bold(ex.note)}</div>',
                                unsafe_allow_html=True)
                if ex.adapted_from:
                    st.markdown(f'<div class="fx-read"><i>Adapted for you — replaces '
                                f'{ex.adapted_from}. Reverts when {ex.reverts_when}.</i>'
                                f'</div>', unsafe_allow_html=True)
            if item.note:
                st.markdown(_fx_bold(item.note))

    deferred = [i for i in stack.items if i.deferred]
    if deferred:
        with st.expander(f"Held back for now · {len(deferred)}"):
            for item in deferred:
                ex = cluster_a_mechanics.exercise(item.exercise)
                st.markdown(f"**{item.exercise}**")
                if ex and ex.deferred_until:
                    st.caption(f"Until {ex.deferred_until}. {ex.reverts_when}")

    if stack.outro:
        st.markdown(stack.outro)

    # ── the trail ───────────────────────────────────────────────────────────
    with st.expander(f"How that was reached · {len(result.slots)} slot(s) run"):
        for slot in result.slots:
            mark = "✓" if slot.passed else ("—" if slot.indeterminate else "✗")
            basis = ("compares your own readings"
                     if slot.basis == btry.BASIS_RELATIVE
                     else "rests on a cut point we invented")
            st.markdown(f"**{mark} Slot {slot.slot} · {btry.SLOT_LABELS[slot.slot]}** — "
                        f"{btry.SLOT_QUESTIONS[slot.slot]}  ·  *{basis}*")
            st.caption(slot.reason)
        skipped = fxs.slots_not_run(report)
        if skipped:
            st.caption(f"{skipped} slot(s) below the failure were NOT measured. That is the "
                       f"method, not an omission — a reading taken below a failing slot "
                       f"cannot be interpreted.")

    with st.expander("Every reading"):
        for r in result.slots[-1].readings or ():
            side = f" *{r.side}*" if r.side else ""
            load = f" @ {r.load_kg:g} kg" if r.load_kg else ""
            setup = f" · setup {r.setup_value:g}" if r.setup_value is not None else ""
            st.markdown(f"**{r.test_key}**{side} — {r.value:g}{r.unit}{load}{setup}")

    # When the retest falls, and whether the morning it falls on is clean —
    # the same status the training screen banners a day in advance.
    if report.assessed_on:
        try:
            status, reason = fx.retest_readiness(
                report.assessed_on, date.today(),
                fx.leg_loading_days(_recent_sessions()))
            if status == fx.RETEST_NOT_DUE:
                st.caption(f"{reason[0].upper()}{reason[1:]}.")
            elif status == fx.RETEST_BLOCKED:
                st.warning(f"Retest due, but {reason}", icon="⚠️")
            else:
                st.info(f"Retest — {reason}", icon="🧘")
        except Exception:                                      # noqa: BLE001
            pass

    c1, c2 = st.columns(2)
    if c1.button("Re-assess", key="fx_reassess", use_container_width=True):
        st.session_state["fx_mode"] = "capture"
        st.session_state["fx_step"] = 0
        st.session_state.pop("fx_force_continue", None)
        st.rerun()
    c2.caption(cluster_a_prescription.RETEST)


# ── entry point ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _flexibility_screen_data() -> dict:
    return fxs.read_data(repo.get_repository(), date.today())


def _render_flexibility_detail() -> None:
    accent = _ACCENT_FLEX
    st.markdown(_FLEXIBILITY_CSS, unsafe_allow_html=True)

    if st.session_state.get("fx_mode") == "capture":
        _fx_render_capture(accent)
        return

    try:
        data = _flexibility_screen_data()
    except Exception as exc:                                  # noqa: BLE001
        st.error(f"Could not read the flexibility record: {exc}", icon="🚫")
        return

    draft = None
    try:
        draft = repo.get_repository().get_flexibility_draft()
    except Exception:                                          # noqa: BLE001
        pass

    if draft is not None:
        done, total = fx.capture_progress(draft)
        st.info(f"Assessment in progress — {done} of {total} tests, started "
                f"{draft.taken_on:%d %b}. It picks up where you left off.", icon="⏸️")
        if st.button("Resume assessment", key="fx_resume", use_container_width=True,
                     type="primary"):
            st.session_state["fx_mode"] = "capture"
            st.rerun()

    report = data["report"]
    if not report.measured:
        _fx_render_empty(accent)
        return
    _fx_render_populated(report, accent)




@st.cache_data(ttl=1800, show_spinner=False)
def _metabolism_screen_data() -> dict:
    """Everything the Metabolism screen renders: the readings from the store
    (services/metabolism_screen.read_data; fault F15 — they came from a local,
    git-ignored CSV, so a server showed none). A read failure is carried
    through as load_error, never shown as "you have never weighed yourself"."""
    return ms.read_data(repo.get_repository(), date.today())


@st.cache_data(ttl=1800, show_spinner=False)
def _strength_screen_data() -> dict:
    """Everything the Strength screen renders (services/strength_screen.read_data:
    one unwindowed read of the training log). A failed read is carried as
    load_error, never shown as "you have never trained"."""
    return ss.read_data(repo.get_repository(), date.today(), {
        "peaks": strength_baselines.PEAKS_2025,
        "region_prior": strength_baselines.REGION_PRIOR,
        "pr_rir": strength_baselines.PR_RIR,
        "anchor_date": strength_baselines.ANCHOR_DATE,
        "anchor_value": strength_baselines.ANCHOR_VALUE,
        "hold_baselines": strength_baselines.HOLD_BASELINES_2025,
        "imbalances": patient_profile.PROFILE.get("imbalances", {}),
    })


# ─────────────────────────────────────────────────────────────────────────────
#  render()
# ─────────────────────────────────────────────────────────────────────────────

def _render_engine_data() -> None:
    """Insights › Engine Data. Its own function since 2026-10-19 so it can be
    rendered alone in a test (tests/test_engine_data_panel.py)."""
    st.caption(f"Data as of {date.today().strftime('%A %d %B')} · refreshes every 30 min")

    if st.button("Refresh engine data", use_container_width=False, key="engine_refresh_btn"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("Loading…"):
        try:
            _state = _engine_state()
        except Exception as exc:
            # A failed read, including an unreadable stage (fault F23), is
            # said here instead of taking the whole Insights page down.
            st.warning(f"The engine's readings could not be read: {exc}", icon="⚠️")
            return
        bio_rows    = _state["bio_rows"]
        tl          = _state["traffic_light"]
        acwr_result = _state["acwr"]
        stage_info  = _state["stage_status"]

    # ── Directive banner ──────────────────────────────────────────────────
    # THE VERDICT HOME SHOWS, the same cached object (today.py), in Home's
    # words and tone. Until 2026-10-19 this panel built its own load policy
    # from the directive alone, without the readiness signal Home passes, so
    # on a day only readiness asked for less, Home said REDUCED LOAD and this
    # panel said NO CHANGE TO LOAD (inventory fault F4). The raw engine
    # label stays, as a caption.
    _verdict = today_mod.today_verdict()
    rec = today_mod.today_directive()
    sig_color = _verdict.tone
    _words = insights_svc.directive_words(_verdict)
    st.markdown(
        f"<div style='background:{sig_color}20;border-left:4px solid {sig_color};"
        f"border-radius:6px;padding:12px 16px;margin-bottom:16px;'>"
        f"<div style='font-size:10px;color:{sig_color};font-family:monospace;"
        f"letter-spacing:2px;margin-bottom:2px;'>DIRECTIVE</div>"
        f"<div style='font-size:17px;font-weight:700;color:#E8EAF0;'>{_words}</div>"
        f"<div style='font-size:12px;color:#9AA3B2;margin-top:4px;'>{rec['action']}</div>"
        f"<div style='font-size:10px;color:#6B7A9B;margin-top:6px;font-family:monospace;'>"
        f"engine label: {rec['label']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    # ACWR rides alongside the directive rather than driving it while the
    # engine is in advisory mode — see engine.ACWR_ADVISORY_MODE.
    if rec.get("acwr_advisory"):
        st.caption(rec["acwr_advisory"])

    acwr_val = acwr_result.get("acwr")

    st.divider()

    # ── Stage progression ─────────────────────────────────────────────────
    st.subheader("Stage Progression")
    st.markdown(f"**{stage_info['stage_label']}**")
    st.caption(stage_info["message"])

    if stage_info.get("progress_days") and stage_info["progress_days"] != "—":
        st.markdown(f"Pain-free days: `{stage_info['progress_days']}`")
        st.progress(stage_info["days_progress_pct"])

    if stage_info.get("progress_tightness") and stage_info["progress_tightness"] != "—":
        st.markdown(f"Tightness target: `{stage_info['progress_tightness']}`")
        st.progress(stage_info["tight_progress_pct"])

    st.divider()

    # ── Biometric traffic light ───────────────────────────────────────────
    st.subheader("Biometric Traffic Light")
    if tl["status"] in engine.NO_READING_STATUSES:
        st.info(tl["message"])
    else:
        overall_color = engine.SIGNAL_COLORS.get(tl["overall"], engine.SIGNAL_COLORS["grey"])
        st.markdown(
            f"Overall: <span style='color:{overall_color};font-weight:700;'>"
            f"{tl['overall'].upper()}</span> — {tl['message']}",
            unsafe_allow_html=True,
        )
        st.write("")
        metrics = tl.get("metrics", {})
        c_hrv, c_rhr, c_sleep, c_temp = st.columns(4)

        # Which source (if any) was missing for today's blended reading —
        # populated by services/biometrics.py's blend_biometric_day().
        _today_bio = next((r for r in bio_rows if r.get("date") == date.today().isoformat()), None)
        _sources_missing = set((_today_bio or {}).get("sources_missing") or ())

        def _metric_card(col, key, label):
            card      = insights_svc.metric_card(metrics.get(key, {}))
            color     = engine.SIGNAL_COLORS.get(card["signal"], engine.SIGNAL_COLORS["grey"])
            val_str, base_str, delta_str = card["value"], card["comparison"], card["change"]
            col.markdown(
                f"<div style='background:#1A1F2E;border-left:4px solid {color};"
                f"border-radius:6px;padding:12px 14px;'>"
                f"<div style='font-size:10px;color:#888;font-family:monospace;"
                f"letter-spacing:1px;'>{label}</div>"
                f"<div style='font-size:26px;font-weight:700;color:#E8EAF0;"
                f"font-family:monospace;'>{val_str}</div>"
                f"<div style='font-size:11px;color:#888;'>{base_str}</div>"
                f"<div style='font-size:11px;color:{color};'>{delta_str}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            missing_source = insights_svc.missing_source(_sources_missing, key)
            if missing_source:
                col.caption(f"⚠ {missing_source.title()} pending — using the other source only.")

        _metric_card(c_hrv,   "hrv_ms",              "HRV")
        _metric_card(c_rhr,   "resting_heart_rate",   "RHR")
        _metric_card(c_sleep, "sleep_duration_hours", "SLEEP")
        _metric_card(c_temp,  "oura_temperature_deviation", "BODY TEMP")

        # ── Baseline-drift guard ──────────────────────────────────────
        # Shown whenever drift is detected, not only when it changed the
        # light: "your baseline is sliding" is worth reading on a day the
        # light was already yellow for other reasons.
        _drift = tl.get("drift", {})
        if _drift.get("drifted"):
            _dc = engine.SIGNAL_COLORS["yellow"]
            _applied_line = (
                "<div style='font-size:11px;color:#9AA3B2;margin-top:4px;'>"
                "Light downgraded green → yellow.</div>"
                if tl.get("drift_applied") else ""
            )
            st.write("")
            st.markdown(
                f"<div style='background:{_dc}18;border-left:4px solid {_dc};"
                f"border-radius:6px;padding:10px 14px;'>"
                f"<div style='font-size:10px;color:{_dc};font-family:monospace;"
                f"letter-spacing:2px;'>BASELINE DRIFT — "
                f"{_drift.get('severity','').upper()}</div>"
                f"<div style='font-size:12px;color:#C8CEDA;margin-top:4px;'>"
                f"{_drift.get('message','')}</div>"
                f"{_applied_line}"
                f"</div>",
                unsafe_allow_html=True,
            )
            with st.expander("Drift detail", expanded=False):
                for _line in insights_svc.drift_lines(_drift, metrics):
                    st.caption(_line)

    st.divider()

    # ── ACWR workload chart ───────────────────────────────────────────────
    st.subheader("Workload Trend — 28 Days")
    col_vals, col_chart = st.columns([1, 3], gap="large")

    with col_vals:
        st.metric("ACWR",            f"{acwr_val:.3f}" if acwr_val else "—")
        st.metric("Acute 7d avg AU", str(acwr_result["acute_avg"]))
        _chronic_label, _chronic_help = insights_svc.acwr_chronic_label(acwr_result)
        st.metric(_chronic_label, str(acwr_result["chronic_avg"]), help=_chronic_help)
        st.metric("Stage ceiling",   str(acwr_result["ceiling"]))
        _acwr_status = insights_svc.acwr_status(acwr_result)
        if _acwr_status:
            {"error": st.error, "info": st.info, "warning": st.warning}[_acwr_status[0]](
                _acwr_status[1])

    with col_chart:
        daily_au = acwr_result.get("daily_au_28", [0.0] * 28)
        chart    = insights_svc.acwr_chart_data(daily_au, today=date.today())
        df_au = pd.DataFrame({
            "Date":   chart["dates"],
            "AU":     chart["au"],
            "Window": chart["windows"],
        })
        df_c = df_au[df_au["Window"] == "Chronic (28d)"].set_index("Date")["AU"]
        df_a = df_au[df_au["Window"] == "Acute (7d)"].set_index("Date")["AU"]
        st.caption("Daily session AU — last 28 days")
        st.bar_chart(
            pd.concat([df_c.rename("Chronic 28d"), df_a.rename("Acute 7d")], axis=1),
            color=["#3D4F6B", "#00E874"],
        )

    st.divider()

    # ── Weekly Volume Load (tonnage) chart ──────────────────────────────
    st.subheader("Weekly Volume Load")
    st.caption(
        "Total kg moved (Σ reps × weight) per Monday-anchored week — only "
        "meaningful once loaded double-progression exercises are logged "
        "(Stage 2A+). Complements ACWR (session RPE × duration) with actual "
        "tonnage lifted."
    )
    _volume = volume_svc.weekly_volume_series(_recent_sessions(), date.today())
    if any(kg > 0 for _week, kg in _volume):
        df_vol = pd.DataFrame(
            {"Volume (kg)": [kg for _week, kg in _volume]},
            index=[week.isoformat() for week, _kg in _volume],
        )
        st.bar_chart(df_vol, color=["#00E874"])
    else:
        st.info("No logged volume yet for loaded, countable-reps exercises in the last 8 weeks.")


def render() -> None:
    st.title("Insights")
    st.caption("Engine metrics, biometric trends, session pattern analysis.")

    injury_profile = repo.get_repository().get_diagnostic_profile()

    (
        tab_bioage, tab_engine, tab_queue,
        tab_tightness, tab_sleep, tab_sync,
    ) = st.tabs([
        "BioAge",
        "Engine Data",
        "Processing Queue",
        "Macro Trends",
        "Sleep Architecture",
        "Sync",
    ])

    # =========================================================================
    #  Tab 0 — BioAge
    # =========================================================================

    with tab_bioage:
        selected = _bioage_selected()
        _sync_bioage_url(selected)

        if selected is not None:
            color = _BIOAGE_COLORS[selected]
            label = _BIOAGE_LABELS[selected]
            st.button("← Back", key="bioage_back", on_click=_close_bioage,
                      type="tertiary")
            st.markdown(
                f"<h2 style='color:{color};margin-top:8px;'>{label}</h2>",
                unsafe_allow_html=True,
            )
            if selected == "strength":
                _render_strength_detail()
            elif selected == "metabolism":
                _render_metabolism_detail()
            elif selected == "flexibility":
                _render_flexibility_detail()
            else:
                st.info(f"{label} biological age breakdown — coming soon.")
        else:
            st.caption("Select a category to see its biological age breakdown.")
            for key in _BIOAGE_CATEGORIES:
                # CSS first, then the button it styles — one <style> per card
                # because each carries its own base64 background and colour.
                st.markdown(_bioage_card_css(key), unsafe_allow_html=True)
                st.button(
                    _BIOAGE_LABELS[key],
                    key=_bioage_card_key(key),
                    on_click=_open_bioage,
                    args=(key,),
                    use_container_width=True,
                )

    # =========================================================================
    #  Tab 1 — Engine Data
    # =========================================================================

    with tab_engine:
        _render_engine_data()

    # =========================================================================
    #  Tab 2 — Processing Queue
    # =========================================================================

    with tab_queue:
        queue = processing_queue.pending(repo.get_repository())
        unparsed_notes, unparsed_readiness = queue["notes"], queue["readiness"]

        col_a, col_b = st.columns(2)
        col_a.metric("Session notes pending",    len(unparsed_notes))
        col_b.metric("Readiness entries pending", len(unparsed_readiness))

        total_pending = len(unparsed_notes) + len(unparsed_readiness)

        if total_pending == 0:
            st.success("All entries are processed. Nothing in the queue.")
        else:
            st.info(
                f"{total_pending} item(s) ready for parsing. "
                "Processing uses local keyword matching — no external service required."
            )

            if st.button("Process All", type="primary", use_container_width=True, key="queue_process_btn"):
                progress = st.progress(0, text="Starting...")
                # services/processing_queue.process_all: one failure never
                # stops the rest, and each error names its item.
                errors = processing_queue.process_all(
                    repo.get_repository(), injury_profile, queue,
                    on_progress=lambda done, total: progress.progress(
                        done / total, text=f"Parsed {done}/{total}..."),
                )["errors"]
                progress.progress(1.0, text="Complete.")
                if errors:
                    st.warning(f"Completed with {len(errors)} error(s):")
                    for e in errors:
                        st.caption(e)
                else:
                    st.success("All items processed successfully.")
                    st.rerun()

        # ── Warnings calendar ────────────────────────────────────────────────
        flagged = repo.get_repository().get_flagged_entries()
        if flagged:
            st.divider()
            st.subheader("Active Warnings")

            by_date = processing_queue.warnings_by_date(flagged)

            if "queue_cal_year" not in st.session_state:
                (st.session_state["queue_cal_year"],
                 st.session_state["queue_cal_month"]) = processing_queue.calendar_anchor(
                    by_date, date.today())

            cal_year  = st.session_state["queue_cal_year"]
            cal_month = st.session_state["queue_cal_month"]

            nav_prev, nav_label, nav_next = st.columns([1, 3, 1])
            if nav_prev.button("◀", key="queue_cal_prev"):
                cal_year, cal_month = processing_queue.step_month(cal_year, cal_month, -1)
                st.session_state["queue_cal_year"]  = cal_year
                st.session_state["queue_cal_month"] = cal_month
                st.rerun()
            nav_label.markdown(
                f"<div style='text-align:center;font-weight:700;'>"
                f"{cal_mod.month_name[cal_month]} {cal_year}</div>",
                unsafe_allow_html=True,
            )
            if nav_next.button("▶", key="queue_cal_next"):
                cal_year, cal_month = processing_queue.step_month(cal_year, cal_month, 1)
                st.session_state["queue_cal_year"]  = cal_year
                st.session_state["queue_cal_month"] = cal_month
                st.rerun()

            dow_cols = st.columns(7)
            for col, dow in zip(dow_cols, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
                col.markdown(
                    f"<div style='text-align:center;color:#888;font-size:11px;'>{dow}</div>",
                    unsafe_allow_html=True,
                )

            selected_date = st.session_state.get("queue_selected_date")
            weeks = processing_queue.month_weeks(cal_year, cal_month)

            today = date.today()

            for week in weeks:
                week_cols = st.columns(7)
                for col, day in zip(week_cols, week):
                    day_str     = day.isoformat()
                    day_entries = by_date.get(day_str, [])
                    is_today    = day == today
                    cell        = col.container(border=True) if is_today else col
                    if day_entries:
                        ball = ("🔴" if processing_queue.day_level(day_entries) == "flag"
                                else "🟡")
                        is_selected = selected_date == day_str
                        if cell.button(
                            f"{day.day} {ball}",
                            key=f"queue_cal_{day_str}",
                            use_container_width=True,
                            type="primary" if is_selected else "secondary",
                        ):
                            st.session_state["queue_selected_date"] = day_str
                            st.rerun()
                    else:
                        if is_today:
                            dim, weight = "#00E874", "700"
                        else:
                            dim    = "#5A6172" if day.month == cal_month else "#2A2E38"
                            weight = "400"
                        cell.markdown(
                            f"<div style='text-align:center;color:{dim};padding:8px 0;"
                            f"font-weight:{weight};'>{day.day}</div>",
                            unsafe_allow_html=True,
                        )

            if selected_date and selected_date in by_date:
                st.divider()
                st.markdown(f"**{date.fromisoformat(selected_date).strftime('%A, %d %B %Y')}**")
                for entry in by_date[selected_date]:
                    shown    = processing_queue.entry_view(entry)
                    level    = shown["level"]
                    color    = engine.WARNING_LEVEL_ICONS.get(level, "⚫")
                    source   = shown["source"]
                    parts    = shown["parts"]
                    summary  = shown["summary"]
                    movement = shown["movement"]
                    st.markdown(
                        f"{color} **{level.upper()}** &nbsp;·&nbsp; {source}"
                        + (f" &nbsp;·&nbsp; _{movement}_" if movement else ""),
                        unsafe_allow_html=True,
                    )
                    if summary:
                        st.caption(summary)
                    if parts:
                        st.caption(f"Body areas: {parts}")
                    st.markdown("---")

    # =========================================================================
    #  Tab 3 — Macro Trends
    # =========================================================================

    with tab_tightness:
        parsed_rows = repo.get_repository().get_parsed_readiness(limit=90)
        # The body areas he SELECTED and the tightness of every check-in (2026-10-20), from
        # the service the phone reads, so the two apps show one answer.
        checkin_trend = insights_screens.checkin_trend(repo.get_repository(), date.today())
        if checkin_trend["regions"]:
            st.subheader("Body Areas You Selected Most")
            df_freq = pd.DataFrame([(r["region"], r["mentions"]) for r in checkin_trend["regions"]],
                                   columns=["Region", "Mentions"])
            st.altair_chart(
                alt.Chart(df_freq).mark_bar(color="#00E874").encode(
                    x=alt.X("Region:N", title=None, sort="-y",
                            axis=alt.Axis(labelAngle=0, labelLimit=1000, labelPadding=10,
                                          labelExpr="split(datum.label, ' — ')")),
                    y=alt.Y("Mentions:Q"),
                ).properties(height=340),
                use_container_width=True,
            )
            st.caption("How often you selected each area in your check-ins over the last 90 days.")
            st.divider()

        if checkin_trend["timeline"]:
            st.subheader("Tightness Severity Timeline")
            df_time = pd.DataFrame(checkin_trend["timeline"]).rename(columns={
                "self_reported":   "Self-reported",
                "parsed_severity": "Keyword-parsed severity",
                "pain":            "Pain score",
            }).set_index("date").apply(pd.to_numeric, errors="coerce")
            st.line_chart(df_time.dropna(how="all"))
            st.caption("Your tightness and pain at each check-in over the last 90 days, on 0 to "
                       "10. Keyword-parsed is the tightness read from your note, where the note "
                       "was read.")
            st.divider()

        if not parsed_rows:
            st.info("No parsed readiness entries yet. Run the Processing Queue first.")
        else:
            st.subheader("Warning Level History")

            rows_by_level = processing_queue.rows_by_warning_level(parsed_rows)

            selected_level = st.session_state.get("tight_warn_level")

            col1, col2, col3 = st.columns(3)
            for col, lvl, label in [
                (col1, "none",    "Clear"),
                (col2, "monitor", "Monitor"),
                (col3, "flag",    "Flag"),
            ]:
                icon = engine.WARNING_LEVEL_ICONS.get(lvl, "⚫")
                cnt  = len(rows_by_level.get(lvl, []))
                if col.button(
                    f"{icon} {label} ({cnt})",
                    key=f"tight_warn_btn_{lvl}",
                    use_container_width=True,
                    type="primary" if selected_level == lvl else "secondary",
                    disabled=cnt == 0,
                ):
                    st.session_state["tight_warn_level"] = lvl
                    st.rerun()

            if selected_level and rows_by_level.get(selected_level):
                icon = engine.WARNING_LEVEL_ICONS.get(selected_level, "⚫")
                st.markdown(f"**{icon} {selected_level.upper()} entries**")
                for row in rows_by_level[selected_level]:
                    parts = processing_queue.names(row.get("ai_body_parts") or "")
                    sensation = processing_queue.names(row.get("ai_sensation_type") or "")
                    severity = row.get("ai_tightness_severity")
                    st.markdown(
                        f"**{row.get('date', '?')}** &nbsp;·&nbsp; "
                        f"Tightness {row.get('tightness_score', '—')} &nbsp;·&nbsp; "
                        f"Pain {row.get('pain_score', '—')}"
                        + (f" &nbsp;·&nbsp; Severity {severity}" if severity is not None else "")
                    )
                    if parts:
                        st.caption(f"Body areas: {parts}")
                    if sensation:
                        st.caption(f"Sensation: {sensation}")
                    st.markdown("---")

        # ── Macro Trends ────────────────────────────────────────────────────
        st.divider()
        st.subheader("Multi-Week Trend Analysis")

        trend_data = repo.get_repository().get_macro_trend_data(90)
        gate = insights_svc.trend_gate(trend_data)

        col_d, col_s = st.columns(2)
        col_d.metric("Biometric days available",    gate["bio_days"])
        col_s.metric("Training sessions available", gate["sessions"])

        if not gate["enough"]:
            st.warning(
                f"Need at least {gate['needed']} days of biometric data for trend "
                f"analysis. Currently have {gate['bio_days']}. Keep logging daily."
            )
        else:
            computed     = stats_mod.compute_all_correlations(trend_data)
            notable      = computed.get("notable_correlations", [])
            slopes       = computed.get("slopes", {})
            recovery_dir = computed["recovery_direction"]

            st.markdown(
                f"**Recovery direction (deterministic):** "
                f"**{insights_svc.recovery_label(recovery_dir)}**"
                f" -- computed from pain/tightness trend slopes"
            )

            if slopes:
                slope_rows = insights_svc.slope_direction_rows(slopes)
                st.dataframe(pd.DataFrame(slope_rows), use_container_width=True, hide_index=True)

            if notable:
                st.subheader("Statistically Notable Correlations (|r| >= 0.3 -- computed)")
                for c in notable:
                    icon = engine.CORRELATION_STRENGTH_ICONS.get(c["strength"], "o")
                    st.markdown(
                        f"{icon} **{c['pair']}** | lag {c['lag_days']}d | "
                        f"r = {c['r']} ({c['strength']}, {c['direction']})"
                    )
            else:
                st.info("No statistically notable correlations (|r| >= 0.3) yet. Keep logging.")

            st.divider()

            if st.button("Generate Trend Interpretation", type="primary", key="trends_interp_btn"):
                with st.spinner("Applying interpretation templates to computed statistics..."):
                    try:
                        result = ai.analyze_macro_trends(trend_data, injury_profile)
                        st.session_state["trend_result"] = result
                    except Exception as exc:
                        st.error(f"Interpretation failed: {exc}")

        if "trend_result" in st.session_state:
            r = st.session_state["trend_result"]

            st.divider()
            st.markdown(f"### {r.get('headline', '--')}")

            st.markdown(
                f"**Recovery trajectory:** "
                f"{insights_svc.recovery_label(r.get('recovery_direction', 'insufficient_data'))}"
            )

            load_note = r.get("load_management_note", "")
            if load_note:
                st.info(load_note)

            correlations = r.get("correlation_interpretations", [])
            if correlations:
                st.subheader("Correlation Interpretations")
                for corr in correlations:
                    st.markdown(
                        f"**{corr.get('variable_pair', '--')}** (lag {corr.get('lag_days', '?')}d)"
                    )
                    st.caption(corr.get("clinical_note", ""))

            recs = r.get("recommendations", [])
            if recs:
                st.subheader("Recommendations")
                for rec_item in recs:
                    st.markdown(f"- {rec_item}")

    # =========================================================================
    #  Tab 4 — Sleep Architecture
    # =========================================================================

    with tab_sleep:
        st.caption(
            "Oura reads sleep stage well but over-reports Awake — a ring registers "
            "micro-movement and autonomic spikes as waking. Garmin's wrist sensor "
            "needs real rotational motion, so its Awake is a strict filter, but it "
            "mislabels REM as Light. Fusion takes stage from Oura and "
            "permission-to-call-Awake from Garmin."
        )

        # get_sleep_fusion_history RAISES on a read failure by design, so that
        # a broken read cannot masquerade as "no fused nights" (and, wrapped in
        # @st.cache_data, stay wrong for 30 minutes). Catching it here is what
        # turns that distinction into two different messages on screen.
        try:
            fusion_rows = _sleep_fusion_history()
            fusion_loaded = True
        except Exception:
            fusion_rows, fusion_loaded = [], False
        # The counts per source (services/sleep_architecture.py). "Oura only"
        # counted the watch-only nights too until 2026-10-19 (fault F12).
        arch = sleep_architecture.summary(fusion_rows)
        fused_only = arch["fused_rows"]

        if not fusion_loaded:
            st.warning(
                "Could not read the Sleep Fusion tab — this is a read failure, "
                "not an absence of fused nights. Try again shortly."
            )
        elif not fusion_rows:
            st.info(
                "No fused nights yet. Run **Rebuild Sleep Fusion** on the Sync tab. "
                "Fusion needs both an Oura hypnogram and a matching Garmin night."
            )
        else:
            c1, c2, c3, c4 = st.columns(4, gap="small")
            c1.metric("Nights fused", arch["fused"])
            c2.metric("Oura only", arch["oura_only"])
            c3.metric("Watch only", arch["watch_only"])
            if arch["median_phantom_wake"] is not None:
                c4.metric("Median phantom wake removed", f"{arch['median_phantom_wake']:.0f} min")
            st.caption(
                f"{arch['oura_only']} night(s) have no matching Garmin stage data and pass "
                "Oura through unchanged — Garmin only began returning stage segments "
                f"in May 2026. {arch['watch_only']} night(s) the ring did not record "
                "use the watch's stages alone."
            )

            if fused_only:
                st.divider()
                st.subheader("Nightly hypnograms")
                options = [r["date"] for r in reversed(fused_only)]
                chosen = st.selectbox("Night", options, key="fusion_night")
                row = next(r for r in fused_only if r["date"] == chosen)

                st.markdown(styles.stage_legend_html(), unsafe_allow_html=True)
                for label, key in (
                    ("Oura (as recorded)", "oura_hypnogram"),
                    ("Master (fused)", "master_hypnogram"),
                    ("Garmin (as recorded)", "garmin_hypnogram"),
                ):
                    st.markdown(
                        f'<div style="color:#9AA3B2;font-size:12px;margin:8px 0 3px;">{label}</div>'
                        + styles.hypnogram_svg(str(row.get(key) or "")),
                        unsafe_allow_html=True,
                    )

                m1, m2, m3, m4 = st.columns(4, gap="small")
                m1.metric("Oura sleep", f"{row.get('oura_sleep_hours')} h")
                m2.metric("Fused sleep", f"{row.get('master_sleep_hours')} h")
                m3.metric("Phantom wake removed", f"{row.get('phantom_wake_minutes')} min")
                m4.metric("Window overlap", f"{row.get('window_overlap_pct')}%")

                st.caption(
                    f"Device agreement {row.get('agreement_pct')}% "
                    f"(Cohen's κ {row.get('cohen_kappa')}). κ corrects for the agreement "
                    "two devices reach by chance — both spend most of the night in "
                    "Light, which flatters raw percent agreement. Garmin covered "
                    f"{row.get('garmin_covered_minutes')} of {row.get('minutes')} minutes."
                )

            st.divider()
            st.subheader("Shadow report — what wiring this into the engine would change")
            st.caption(
                "Fusion is display-only by design. Per night, fused sleep is always "
                "≥ Oura's — but that does **not** simply loosen every constraint. "
                "The traffic light and sleep debt both score a day against a rolling "
                "baseline built from the same rows, so raising the nights that have "
                "Garmin data also raises the bar the rest are judged against. With "
                "partial coverage the window mixes two different measurements and the "
                "effect is not directional — the same argument that keeps ACWR off "
                "heart-rate-derived strain."
            )
            shadow = dash.sleep_fusion_shadow_report(
                _bio(), sleep_architecture.fused_hours(fusion_rows))
            if not shadow["nights_compared"]:
                st.info("No fused night overlaps the current biometric window yet.")
            else:
                s1, s2, s3 = st.columns(3, gap="small")
                s1.metric("Traffic light now", str(shadow["traffic_light_now"]).title())
                s2.metric("If fused", str(shadow["traffic_light_fused"]).title(),
                          delta="would flip" if shadow["traffic_light_would_flip"] else "no change",
                          delta_color="inverse" if shadow["traffic_light_would_flip"] else "off")
                if shadow["readiness_median_delta"] is not None:
                    s3.metric("Readiness delta (median)",
                              f"{shadow['readiness_median_delta']:+.1f}")
                st.caption(
                    f"Compared over {shadow['nights_compared']} fused night(s). "
                    f"7-day sleep debt {shadow['sleep_debt_now']} h → "
                    f"{shadow['sleep_debt_fused']} h; rest trigger "
                    f"{'ON' if shadow['rest_trigger_now'] else 'off'} → "
                    f"{'ON' if shadow['rest_trigger_fused'] else 'off'}."
                )

    # =========================================================================
    #  Tab 5 — Sync
    # =========================================================================

    with tab_sync:
        # Supabase is the only store (2026-10-09): a save is written there and
        # waited for before the screen confirms it, so there is no queued copy
        # that can fall behind. The legacy mirror warning and the Sheet1 table
        # were dropped 2026-10-19 (inventory I80, I81).
        if repo.get_repository().supabase_record:
            st.caption(
                "Supabase holds all data. Each save is written there before "
                "the screen confirms it. Notion and Google Sheets are no longer used."
            )
        sheet_id = ""

        st.divider()
        st.subheader("Engine View — Last 28 Days (live)")
        st.caption(
            "Oura (70%) + Garmin (30%) blend for HRV/RHR/sleep, Garmin (80%) + "
            "Oura (20%) for steps — services/biometrics.py — as passed to the "
            "traffic-light engine right now. Recomputed on every load; not "
            "persisted. No longer sourced from Sheet1 above."
        )

        engine_rows = _sync_engine_view(sheet_id)
        if engine_rows:
            st.dataframe(pd.DataFrame(engine_rows), use_container_width=True)
        else:
            st.info("No rows within the last 28 days.")

        st.divider()
        st.subheader("Biometric Blend History (persisted)")
        st.caption(
            "A fixed daily record of the blend above, written by the device sync "
            "(Repository.sync_biometric_blend) to its own table. Unlike the "
            "live view above, a past day here doesn't change even if Oura/Garmin "
            "later revise that day's raw reading — this is what you actually saw "
            "at the time."
        )
        if st.button(
            "Backfill full history now",
            use_container_width=False,
            key="backfill_biometric_blend",
        ):
            try:
                with _manual_sync("Computing and persisting the full blend history…"):
                    n = repo.get_repository().sync_biometric_blend(days=400)
                st.success(f"Persisted {n} day(s) to the Biometric Blend tab.")
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                st.warning(f"Backfill failed: {exc}")

        try:
            blend_history = _blend_history()
        except Exception as exc:
            blend_history = None
            st.warning(f"Could not load blend history: {exc}")

        if blend_history:
            earliest, latest = insights_svc.date_span(blend_history)
            col_from, col_to = st.columns(2)
            start_pick = col_from.date_input("From", value=earliest, key="blend_hist_from")
            end_pick = col_to.date_input("To", value=latest, key="blend_hist_to")
            filtered = insights_svc.rows_between(blend_history, start_pick, end_pick)
            st.dataframe(pd.DataFrame(filtered), use_container_width=True, height=400)
        elif blend_history is not None:
            st.info(
                "No persisted history yet — click \"Backfill full history now\" "
                "above, or wait for the automatic once-a-day sync."
            )

        st.divider()
        st.subheader("Metrics History (persisted)")
        st.caption(
            "A fixed daily record of Readiness, Sleep Score, and Strain — written "
            "by the device sync (Repository.sync_metrics_history) to its own table, "
            "same rationale as Biometric Blend above. This is also what feeds the "
            "trend sparklines behind the Readiness/Sleep/Strain cards on Home "
            "(tap a card to see it)."
        )

        try:
            metrics_history = _metrics_history()
        except Exception as exc:
            metrics_history = None
            st.warning(f"Could not load metrics history: {exc}")

        if metrics_history:
            earliest, latest = insights_svc.date_span(metrics_history)
            col_from, col_to = st.columns(2)
            start_pick = col_from.date_input("From", value=earliest, key="metrics_hist_from")
            end_pick = col_to.date_input("To", value=latest, key="metrics_hist_to")
            filtered = insights_svc.rows_between(metrics_history, start_pick, end_pick)
            st.dataframe(pd.DataFrame(filtered), use_container_width=True, height=400)
        elif metrics_history is not None:
            st.info("No persisted history yet — wait for the automatic once-a-day sync.")

        # ── Session checks (2026-10-13): the two inputs that have inflated
        #    strain before — a repeat save and a session left open.
        st.divider()
        st.subheader("Session checks")
        try:
            _log_warnings = sessions_svc.session_log_warnings(
                repo.get_repository().get_session_summaries(days=35))
        except Exception as exc:
            _log_warnings = None
            st.warning(f"Could not check the session log: {exc}")
        if _log_warnings:
            for _w in _log_warnings:
                st.warning(_w)
        elif _log_warnings is not None:
            st.caption("The last 35 days of the session log look clean: no repeat saves, "
                       "and no day far above the rest.")

        st.divider()
        st.caption(
            "Garmin daily metrics and activities sync by themselves every 2 hours "
            "while the app is open (daily metrics stop once the day's check-in is "
            "saved); the weekly rollup is written when the Training page opens. "
            "No button is needed."
        )

        st.divider()
        st.subheader("Garmin")
        sync_repo = repo.get_repository()
        if not sync_repo.garmin_configured():
            st.info(
                "Add GARMIN_EMAIL and GARMIN_PASSWORD to .streamlit/secrets.toml to "
                "enable Garmin sync. Feeds the readiness/ACWR engine (30% weight for "
                "HRV/RHR/sleep, 80% for steps, blended with Oura) once configured."
            )
        else:
            st.caption(
                "Daily wellness metrics feed the readiness/ACWR engine (blended with "
                "Oura) and are stored in their own tables (Garmin Daily, Garmin "
                "Activities). Both sync by themselves every 2 hours while the app is "
                "open; the buttons below run them now."
            )

            col_daily, col_activities = st.columns(2, gap="small")
            with col_daily:
                if st.button(
                    "Sync Garmin Daily Metrics",
                    use_container_width=True,
                    key="sync_garmin_daily",
                ):
                    try:
                        with _manual_sync("Pulling daily metrics from Garmin…"):
                            n = sync_repo.sync_garmin_daily(days=7)
                        st.success(f"Synced {n} days to the Garmin Daily tab.")
                    except Exception as exc:
                        st.warning(f"Garmin daily sync failed: {exc}")
            with col_activities:
                if st.button(
                    "Sync Garmin Activities",
                    use_container_width=True,
                    key="sync_garmin_activities",
                ):
                    try:
                        with _manual_sync("Pulling activities from Garmin…"):
                            n = sync_repo.sync_garmin_activities(limit=20)
                        st.success(
                            f"Synced {n} activities to the Garmin Activities tab."
                        )
                    except Exception as exc:
                        st.warning(f"Garmin activity sync failed: {exc}")

        st.divider()
        st.subheader("Sleep Fusion")
        st.caption(
            "Merges Oura's stage sequence with Garmin's into one master "
            "hypnogram — Oura reads stage well but over-reports Awake; "
            "Garmin's wrist sensor needs real rotational movement, so its "
            "Awake acts as a strict filter. Reads only the already-synced "
            "tables, so it never calls a device API and is safe to "
            "re-run while Garmin is rate-limited. Display-only: the engine "
            "still reads the Oura/Garmin biometric blend."
        )
        if st.button(
            "Rebuild Sleep Fusion (full history)",
            use_container_width=True,
            key="sync_sleep_fusion",
        ):
            try:
                with _manual_sync("Recomputing fused hypnograms…"):
                    counts = sync_repo.sync_sleep_fusion(days=1200)
                st.cache_data.clear()
                st.success(
                    f"Fused {counts.get('fused', 0)} night(s); "
                    f"{counts.get('oura_only', 0)} had no Garmin match "
                    "and pass Oura through unchanged."
                )
            except Exception as exc:
                st.warning(f"Sleep fusion rebuild failed: {exc}")

        st.divider()
        st.subheader("Oura")
        if not sync_repo.oura_configured():
            st.info(
                "Oura is not connected. Authorise it once with "
                "`python scripts/authorize_oura.py`. It feeds the readiness/ACWR "
                "engine (70% weight for HRV/RHR/sleep, 20% for steps, blended with "
                "Garmin) once connected."
            )
        else:
            st.caption(
                "Daily steps and sleep-period HRV/RHR/sleep-duration feed the "
                "readiness/ACWR engine (blended with Garmin). Daily summary scores "
                "(sleep, readiness, activity, stress, resilience, SpO2, "
                "cardiovascular age) archive to the Oura Daily tab; workouts, "
                "sessions, and rest-mode periods each get their own archival tab. "
                "Also syncs automatically 2 hours after the Home page is opened; use "
                "the button below to pull a full week on demand."
            )
            if st.button(
                "Sync Weekly Oura Details",
                use_container_width=False,
                key="sync_oura_weekly",
            ):
                try:
                    with _manual_sync("Pulling the last 7 days from Oura…"):
                        counts = sync_repo.sync_oura_all(days=7)
                    st.success(
                        f"Synced {counts['daily']} days, "
                        f"{counts['workouts']} workouts, "
                        f"{counts['sleep_periods']} sleep periods, "
                        f"{counts['sessions']} sessions, "
                        f"{counts['rest_mode_periods']} rest-mode periods."
                    )
                except Exception as exc:
                    st.warning(f"Oura sync failed: {exc}")
