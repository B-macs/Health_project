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
import json
import math
import os
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import streamlit as st
import pandas as pd

import body_composition_baselines as bcb
import cluster_a_battery as cba
import cluster_a_mechanics
import cluster_a_prescription
import flexibility_baselines
import patient_profile
import repo
import strength_baselines
import styles
import training_constants
from services import ai
from services import bioage
from services import body_composition as bc
from services import dashboard as dash
from services import engine
from services import battery as btry
from services import flexibility as fx
from services import stats as stats_mod
from services import insights as insights_svc
from services import plan as plan_svc
from services import strength as strength_svc
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
#    Overall Strength Score  — estimated strength CAPACITY, in points, where
#      100 is the 2025 peak. services/strength.py. Moves on repeatable
#      performance and estimated-1RM trend; a heavier training week cannot
#      raise it on its own.
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
_CARD_DIMENSIONS_CSS = "aspect-ratio:1194/356;min-height:220px;max-height:420px;"

_STRENGTH_FACEPLATE_DIR = _BIOAGE_BG_DIR / "body_faceplates_v2"

# The three faceplates stack into one continuous figure, so they must render
# at the SAME displayed width with each image's own aspect ratio preserved —
# resizing their heights independently would break the join. Native sizes.
_STRENGTH_REGIONS: tuple[dict, ...] = (
    {"id": "upper_body", "name": "Upper body", "colour": "#FF8C42", "ratio": "893/640"},
    {"id": "core",       "name": "Core",       "colour": "#E8B04B", "ratio": "893/428"},
    {"id": "lower_body", "name": "Lower body", "colour": "#D9663A", "ratio": "893/534"},
)

# label → (series key, unit, short unit, accent). "score" is the strength
# metric; the other four are tonnage. Order is the dropdown's order.
_STRENGTH_METRICS: dict[str, dict] = {
    "Overall Strength Score":   {"key": "score",      "unit": "points", "short": "pts", "colour": "#FF8C42"},
    "Overall Strength Tonnage": {"key": "overall",    "unit": "kg",     "short": "kg",  "colour": "#FF8C42"},
    "Upper Body Tonnage":       {"key": "upper_body", "unit": "kg",     "short": "kg",  "colour": "#FF8C42"},
    "Core Tonnage":             {"key": "core",       "unit": "kg",     "short": "kg",  "colour": "#E8B04B"},
    "Lower Body Tonnage":       {"key": "lower_body", "unit": "kg",     "short": "kg",  "colour": "#D9663A"},
}

# Weeks of history in the progress display. Six bars is what the 640-unit
# chart can label without crowding, and it is a rolling window — a week with
# no eligible work is drawn as an explicit zero rather than dropped, so the
# series is always exactly this long.
_STRENGTH_WEEKS: int = 6

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


def _tone(value: float) -> str:
    if abs(value) < 5e-2:
        return _INK2
    return _GOOD if value > 0 else _BAD


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
    values = [wk.value(key).kg for wk in series]
    top = tonnage_svc.nice_axis_max(max(values) if values else 0.0)
    y_labels = [_kg(top * i / 4) for i in range(4, -1, -1)]
    x_labels = [wk.week_start.strftime("%-d %b") if os.name != "nt"
                else wk.week_start.strftime("%d %b").lstrip("0") for wk in series]
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
            # would hide exactly the work these counters exist to show.
            + (f" · {_kg(cell.unloaded_reps)} unloaded reps" if cell.unloaded_reps else "")
            + (f" · {_kg(cell.unloaded_seconds)}s held" if cell.unloaded_seconds else "")
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


def _score_chart_svg(points: list[dict], colour: str) -> str:
    """The modelled level, with the measured weeks beneath it. Measured is
    drawn in a muted grey precisely because it is NOT the score — it is the
    evidence the score is allowed to respond to."""
    w, h, pl, pr, pt, pb = 640, 220, 44, 14, 14, 24
    iw, ih = w - pl - pr, h - pt - pb
    seen = [v for p in points for v in (p["measured"], p["level"]) if v is not None]
    if seen:
        lo = max(0.0, (min(seen) // 10) * 10 - 10)
        hi = ((max(seen) // 10) + 2) * 10
        # The span has to divide into 4 gridlines cleanly, or the labels are
        # rounded to whole points while the lines sit on halves — 90/77.5/65/
        # 52.5/40 printing as 90/78/65/52/40, which misreads the chart.
        hi = lo + math.ceil((hi - lo) / 20.0) * 20.0
    else:
        lo, hi = 0.0, 100.0
    y_labels = [f"{hi - (hi - lo) * i / 4:.0f}" for i in range(0, 5)]
    x_labels = [p["week"].strftime("%-d %b") if os.name != "nt"
                else p["week"].strftime("%d %b").lstrip("0") for p in points]
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


def _strength_readout_html(current: float | None, previous: float | None,
                           labels: tuple[str, str], unit: str, points: bool,
                           year: int) -> str:
    def cell(k: str, v: str, sub: str, colour: str = _INK3) -> str:
        return (f'<div><div class="k">{k}</div><div class="v">{v}</div>'
                f'<div class="p" style="color:{colour}">{sub}</div></div>')

    def show(v: float | None) -> str:
        if v is None:
            return "—"
        return f'{v:.1f}<u>{unit}</u>' if points else f'{_kg(v)}<u>{unit}</u>'

    if current is None or previous is None:
        delta_html, delta_sub, delta_col = "—", "no comparable previous week", _INK3
    else:
        delta, pct = tonnage_svc.change(current, previous)
        delta_col = _tone(delta)
        delta_html = (f'<span style="color:{delta_col}">{_signed(delta, points)}'
                      f"<u>{unit}</u></span>")
        if pct is None:
            delta_sub = "no percentage — the previous week was zero"
        else:
            sign = "" if abs(pct) < 5e-2 else ("−" if pct < 0 else "+")
            delta_sub = f"{sign}{abs(pct):.1f}% week over week"
    return (
        '<div class="sb-readout">'
        + cell(f"This week · {labels[0]}", show(current), f"week of {labels[0]} {year}")
        + cell(f"Last week · {labels[1]}", show(previous), f"week of {labels[1]} {year}")
        + cell("Change", delta_html, delta_sub, delta_col)
        + "</div>"
    )


def _strength_region_strip_html(regions: list) -> str:
    by_id = {r.region: r for r in regions}
    rows = ""
    for meta in _STRENGTH_REGIONS:
        state = by_id.get(meta["id"])
        if state is None:
            continue
        plate = _bioage_b64(str(_STRENGTH_FACEPLATE_DIR / f"{meta['id']}.png"))
        conf = state.confidence
        conf_col = _GOOD if conf >= strength_svc.CALIBRATION_EXIT else (_WARN if conf > 0 else _BAD)
        band = "established" if conf >= strength_svc.CALIBRATION_EXIT else "provisional"
        off = " off" if conf <= 0 else ""
        aria = (f'{meta["name"]}, {state.contribution_points:.1f} points, '
                f'{state.contribution_pct:.1f} percent of overall, '
                f'index {state.displayed_index:.1f}, confidence {conf:.2f}')
        rows += (
            f'<div class="sb-region" role="group" aria-label="{aria}">'
            f'<div class="txt">'
            f'<div class="nm" style="color:{meta["colour"]}">{meta["name"]}</div>'
            f'<div class="sc">{state.contribution_points:.1f}'
            f'<u>pts&thinsp;<s>{state.contribution_pct:.1f}%</s></u></div>'
            f'<div class="idx">Index <em>{state.displayed_index:.1f}</em></div>'
            f'<div class="sb-cbar"><i style="width:{max(round(conf * 100), 2)}%;'
            f'background:{conf_col}"></i></div>'
            f'<div class="sb-cnote" style="color:{conf_col}">{band} · confidence {conf:.2f}</div>'
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
    by_id = {r.region: r for r in regions}
    ordered = [(m, by_id[m["id"]]) for m in _STRENGTH_REGIONS if m["id"] in by_id]
    bar = "".join(
        f'<i style="width:{r.contribution_pct:.1f}%;background:{m["colour"]}"></i>'
        for m, r in ordered
    )
    key = "".join(
        f'<span><b style="background:{m["colour"]}"></b>{m["name"]} '
        f'{r.contribution_points:.1f} pts · {r.contribution_pct:.1f}%</span>'
        for m, r in ordered
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
    out = '<div class="sb-imblist">'
    if over:
        out += '<div class="grp">Overactive · release first</div>'
        out += "".join(f'<div class="i"><b style="background:{_BAD}"></b>'
                       f"<span>{name}</span></div>" for name in over)
    if under:
        out += '<div class="grp">Underactive · activate second</div>'
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
            "Progress metric", list(_STRENGTH_METRICS), key="strength_metric",
            label_visibility="collapsed",
        )
    metric = _STRENGTH_METRICS[chosen]
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

    if is_score:
        points = data["score_series"]
        current = points[-1]["level"] if points else None
        previous = points[-2]["level"] if len(points) > 1 else None
        labels = (data["week_labels"][-1], data["week_labels"][-2])
        chart = _score_chart_svg(points, accent)
    else:
        series = data["tonnage"]
        current = series[-1].value(metric["key"]).kg if series else None
        previous = series[-2].value(metric["key"]).kg if len(series) > 1 else None
        labels = (data["week_labels"][-1], data["week_labels"][-2])
        chart = _tonnage_chart_svg(series, metric["key"], metric["colour"], chosen)

    st.markdown(
        _strength_readout_html(current, previous, labels, metric["unit"], is_score,
                               data["today"].year),
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="sb-chartbox">{chart}</div>', unsafe_allow_html=True)

    # ── Body parts ────────────────────────────────────────────────────────
    st.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;'>Body parts</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_strength_split_html(data["regions"]), unsafe_allow_html=True)
    st.markdown(_strength_region_strip_html(data["regions"]), unsafe_allow_html=True)

    # ── Muscle balance ────────────────────────────────────────────────────
    bal_l, bal_r = st.columns([2, 1])
    bal_l.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;margin:18px 0 12px;'>"
        f"Muscle balance analysis</div>",
        unsafe_allow_html=True,
    )
    bal_r.markdown(
        f"<div style='text-align:right;font-size:13px;color:{accent};margin-top:22px;'>"
        f"View All &rsaquo;</div>",
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

#: label → (series key, unit, decimals, minimum axis span, colour, source)
_METAB_METRICS: dict[str, dict] = {
    "Weight":            {"key": "weight",  "unit": "kg", "dp": 1, "span": 2.0,
                          "colour": _METAB_LEAN, "src": "scale"},
    "Fat mass":          {"key": "fat",     "unit": "kg", "dp": 1, "span": 1.5,
                          "colour": _METAB_FAT,  "src": "scale"},
    "Fat-free mass":     {"key": "ffm",     "unit": "kg", "dp": 1, "span": 1.5,
                          "colour": _METAB_LEAN, "src": "scale"},
    "Body fat percent":  {"key": "bf",      "unit": "%",  "dp": 1, "span": 1.5,
                          "colour": _METAB_FAT,  "src": "scale"},
    "Phase angle":       {"key": "phase",   "unit": "°",  "dp": 1, "span": 0.5,
                          "colour": _METAB_DEV,  "src": "inbody"},
    "ECW / TBW ratio":   {"key": "ecw",     "unit": "",   "dp": 3, "span": 0.008,
                          "colour": _METAB_DEV,  "src": "inbody"},
}

_METAB_RANGES: tuple[tuple[str, str], ...] = (
    ("Week", "week"), ("Month", "month"), ("Year", "year"), ("All", "all"),
)

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


def _metab_split_html(fat: float | None, lean: float | None) -> str:
    """Fat against fat-free, which must total the weight. It does so by
    construction — `fat = weight * pct` and `lean = weight - fat` — so this bar
    is a restatement of one number, never corroboration of it."""
    if fat is None or lean is None or (fat + lean) <= 0:
        return ""
    total = fat + lean
    pct = fat / total * 100
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


def _metab_readout_html(first: tuple | None, last: tuple | None,
                        unit: str, dp: int) -> str:
    """Latest, and the change across what the chart is showing.

    The change is first-to-last of the VISIBLE points, not of the whole series
    — a number that disagrees with the picture beside it teaches the reader to
    trust neither."""
    def cell(key: str, value: str) -> str:
        return f'<div><div class="k">{key}</div><div class="v">{value}</div></div>'

    if last is None:
        return (f'<div class="mb-readout">{cell("Latest", "—")}'
                f'{cell("Change", "—")}</div>')
    last_day, last_val = last
    latest = cell(f"Latest · {last_day.strftime('%d %b %Y').lstrip('0')}",
                  f"{last_val:.{dp}f}<u>{unit}</u>" if unit else f"{last_val:.{dp}f}")
    if first is None or first[0] == last_day and first[1] == last_val:
        return f'<div class="mb-readout">{latest}{cell("Change · one reading only", "—")}</div>'
    delta = last_val - first[1]
    colour = _INK3 if abs(delta) < 10 ** -dp / 2 else (_WARN if delta > 0 else _GOOD)
    sign = "" if abs(delta) < 10 ** -dp / 2 else ("−" if delta < 0 else "+")
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

    values = [v for _, v in points]
    mid = (min(values) + max(values)) / 2
    span_v = max(max(values) - min(values), min_span) * 1.25
    y_lo, y_hi = mid - span_v / 2, mid + span_v / 2

    def y_at(value: float) -> float:
        return pt + (1 - (value - y_lo) / (y_hi - y_lo)) * ih

    y_labels = [f"{y_hi - i / 4 * (y_hi - y_lo):.{dp}f}" for i in range(5)]
    x_labels = []
    for i in range(5):
        day = date.fromordinal(lo_d + round(i / 4 * span_d))
        x_labels.append(day.strftime("%d %b" if span_d <= 60 else "%b %y").lstrip("0"))
    out = _svg_frame(y_labels, x_labels, w, h, pl, pr, pt, pb)

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


def _metab_analysis_html(reading, accent: str) -> str:
    """Every remaining figure, each labelled with what it really is.

    `services.body_composition.DERIVED_COLUMNS` is the source of truth for which
    of these are arithmetic; nothing here is stored, it is all recomputed from
    the weight so that the screen cannot drift from the docstring."""
    if reading is None:
        return ""
    when = reading.day.strftime("%d %b %Y").lstrip("0")
    weight, pct = reading.weight_kg, reading.body_fat_pct
    fat, lean = reading.fat_mass_kg, reading.fat_free_mass_kg
    height = bc.TRUE_HEIGHT_M
    rows: list[tuple] = [
        ("MASS", "what the body is made of, in kilograms", [
            ("Weight", f"{weight:.1f}", "kg", "measured", ("ok", "Normal")),
            ("Body mass index", f"{weight / height ** 2:.1f}", "kg/m²", "derived", None),
        ]),
    ]
    if pct is not None and fat is not None and lean is not None:
        rows[0][2].extend([
            ("Body fat", f"{fat:.1f}", "kg", "derived", ("ok", "Normal")),
            ("Body fat", f"{pct:.1f}", "%", "derived", ("ok", "Normal")),
            ("Fat-free mass", f"{lean:.1f}", "kg", "derived", None),
            ("Bone mass", f"{lean * 0.04994:.1f}", "kg", "derived", None),
        ])
        rows.append(("ENERGY", "what it costs to run", [
            ("Basal metabolic rate", f"{370 + 21.6 * lean:.0f}", "kcal", "derived", None),
        ]))
        rows.append(("WATER", "how that mass is hydrated", [
            ("Body water", f"{0.72201 * (100 - pct):.1f}", "%", "derived", None),
            ("Protein", f"{0.22797 * (100 - pct):.1f}", "%", "derived", None),
        ]))
        rows.append(("RISK", "what it implies", [
            ("Visceral fat level", f"{-2.8932 + 0.5927 * pct:.1f}", "", "derived",
             ("ok", "Normal")),
            ("Subcutaneous fat", f"{pct - 2.25:.1f}", "%", "derived", None),
            ("Waist circumference", "—", "cm", "absent", None),
            ("Hip circumference", "—", "cm", "absent", None),
        ]))
    out = ""
    for group, blurb, cards in rows:
        out += f'<div class="mb-grp">{group}<span>{blurb}</span></div><div class="mb-cards">'
        out += "".join(
            _metab_card_html(n, v, u, when if v != "—" else "no reading", s, p, accent)
            for n, v, u, s, p in cards
        )
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
            "The scale export could not be read, so the figures below are "
            f"showing their no-data state — {data['load_error']}",
            icon="⚠️",
        )
    if latest:
        st.markdown(
            _metab_split_html(latest.fat_mass_kg, latest.fat_free_mass_kg),
            unsafe_allow_html=True,
        )

    # ── Progress ──────────────────────────────────────────────────────────
    head_l, head_r = st.columns([2, 1])
    head_l.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;margin-top:6px;'>"
        f"Progress</div>",
        unsafe_allow_html=True,
    )
    with head_r:
        chosen = st.selectbox("Progress metric", list(_METAB_METRICS),
                              key="metab_metric", label_visibility="collapsed")
    metric = _METAB_METRICS[chosen]

    kind = st.session_state.get("metab_range", "all")
    offset = st.session_state.get("metab_offset", 0)

    cols = st.columns([1, 1, 1, 1, 1, 3, 1])
    for i, (label, key) in enumerate(_METAB_RANGES):
        if cols[i].button(label, key=f"metab_r_{key}", use_container_width=True,
                          type="primary" if key == kind else "secondary"):
            # A new granularity always opens on the period containing today —
            # carrying an offset across a switch lands you somewhere arbitrary.
            st.session_state["metab_range"] = key
            st.session_state["metab_offset"] = 0
            st.rerun()

    earliest = readings[0].day if readings else None
    if cols[4].button("‹", key="metab_p_prev", use_container_width=True,
                      disabled=not bc.can_step(kind, offset, -1, today, earliest)):
        st.session_state["metab_offset"] = offset - 1
        st.rerun()
    window = bc.period_window(kind, offset, today, earliest)
    cols[5].markdown(
        f'<div class="mb-plabel"><b>{window.label}</b><i>{window.sub}</i></div>',
        unsafe_allow_html=True,
    )
    if cols[6].button("›", key="metab_p_next", use_container_width=True,
                      disabled=not bc.can_step(kind, offset, 1, today, earliest)):
        st.session_state["metab_offset"] = offset + 1
        st.rerun()

    source = scans if metric["src"] == "inbody" else readings
    gap = (bc.INBODY_GAP_BREAK_DAYS if metric["src"] == "inbody"
           else bc.SCALE_GAP_BREAK_DAYS)
    visible = bc.readings_in(source, window)
    points = [(r.day, v) for r in visible
              if (v := _metab_value(r, metric["key"])) is not None]
    runs = [[(r.day, v) for r in run if (v := _metab_value(r, metric["key"])) is not None]
            for run in bc.split_runs(visible, gap)]

    st.markdown(
        _metab_readout_html(points[0] if points else None,
                            points[-1] if points else None,
                            metric["unit"], metric["dp"]),
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="mb-chartbox">'
        f'{_metab_chart_svg(points, metric["colour"], metric["dp"], metric["span"], window, runs, chosen)}'
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Cellular health ───────────────────────────────────────────────────
    if scans:
        clean = scans[-1]
        st.markdown(
            f"<div style='color:{_INK};font-size:18px;font-weight:600;margin:6px 0 2px;'>"
            f"Cellular health</div>"
            f"<div style='font-size:11px;color:{_INK3};margin-bottom:9px;'>"
            f"{bcb.DEVICE} · nothing else measures these</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            _metab_cellular_html(clean, (today - clean.day).days, accent),
            unsafe_allow_html=True,
        )

    # ── Body analysis ─────────────────────────────────────────────────────
    st.markdown(
        f"<div style='color:{_INK};font-size:18px;font-weight:600;margin:22px 0 2px;'>"
        f"Body analysis</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_metab_analysis_html(latest, accent), unsafe_allow_html=True)

    # ── Add measurement ───────────────────────────────────────────────────
    st.markdown('<div class="mb-grp">Add measurement</div>', unsafe_allow_html=True)
    add_l, add_r = st.columns(2)
    add_l.button("＋  Foryond weigh-in", key="metab_add_weight",
                 use_container_width=True, disabled=True,
                 help="Weight entry — not wired up yet")
    add_r.button("＋  Tape baseline", key="metab_add_tape",
                 use_container_width=True, disabled=True,
                 help="Waist and hip — not wired up yet")


def _metab_value(record, key: str) -> float | None:
    """One accessor for both record types, so the chart does not need to know
    which device a series came from."""
    if key == "weight":
        return getattr(record, "weight_kg", None)
    if key == "fat":
        return record.fat_mass_kg
    if key == "ffm":
        return record.fat_free_mass_kg
    if key == "bf":
        return record.body_fat_pct
    if key == "phase":
        return getattr(record, "phase_angle_deg", None)
    if key == "ecw":
        return getattr(record, "ecw_tbw", None)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level cached data fetchers  (must live outside render() so that
#  Streamlit recognises them as stable across reruns)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _bio():
    # engine.py/readiness.py still work on plain dicts -- asdict() converts
    # the typed BiometricRecord back to the exact shape they expect.
    return [asdict(r) for r in repo.get_repository().get_biometric_rolling(days=28)]

@st.cache_data(ttl=1800, show_spinner=False)
def _bio_drift():
    """Wide history feeding ONLY engine.traffic_light's baseline-drift guard.
    Kept separate from _bio() because the same list is handed to
    readiness.compute_readiness elsewhere on this page, whose sleep_baseline
    silently widens from a 28- to a 56-night window on a longer list — see
    engine.traffic_light's drift_rows docstring."""
    records = repo.get_repository().get_biometric_rolling(
        days=engine.DRIFT_RECOMMENDED_FETCH_DAYS)
    return [asdict(r) for r in records]

@st.cache_data(ttl=1800, show_spinner=False)
def _au():          return repo.get_repository().get_daily_session_au_weighted(28)

@st.cache_data(ttl=1800, show_spinner=False)
def _streak():      return repo.get_repository().get_pain_free_streak()

@st.cache_data(ttl=1800, show_spinner=False)
def _tight():       return repo.get_repository().get_avg_tightness(14)

@st.cache_data(ttl=1800, show_spinner=False)
def _diag():        return repo.get_repository().get_diagnostic_profile()

@st.cache_data(ttl=1800, show_spinner=False)
def _stage():       return repo.get_repository().get_current_stage()

@st.cache_data(ttl=1800, show_spinner=False)
def _stage_start():
    """Start date of the active phase — scopes ACWR's chronic baseline to the
    current stage. None during a reassessment gap; acwr() then falls back to
    the flat 28-day calendar window."""
    return plan_svc.current_stage_start(repo.get_repository().get_phases(), date.today())

@st.cache_data(ttl=1800, show_spinner=False)
def _sync_raw(sheet_id: str) -> list[dict]:
    return repo.get_repository().get_raw_sheet_rows()

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
        f'Every four weeks. It usually stops early &mdash; the first failing slot is '
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

    with st.expander("The four slots, and why they run in order"):
        for slot in (btry.SLOT_STRUCTURE, btry.SLOT_REGRESSED,
                     btry.SLOT_PREREQUISITE, btry.SLOT_SPECTRUM):
            st.markdown(f"**{slot}. {btry.SLOT_LABELS[slot]}** — "
                        f"{btry.SLOT_QUESTIONS[slot]}")
            st.caption(f"Decides: {btry.SLOT_DECIDES[slot]}")
        st.caption("Stop at the first failure. There is no value in measuring a spectrum "
                   "profile for a skill that a bony block had already made unavailable.")

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
    done = {r.test_key for r in draft.readings if r.usable} if draft else set()
    ticks = []
    for i, key in enumerate(order):
        cls = "now" if i == step else ("done" if key in done else "")
        ticks.append(f'<i class="{cls}"></i>')
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
        try:
            yesterday = date.today() - timedelta(days=1)
            if yesterday in fx.leg_loading_days(repo_.get_recent_sessions(days=3)):
                st.warning("Yesterday's session loaded your legs. A cold reading this "
                           "morning will read tighter than your real baseline in "
                           "exactly the areas being tested — measure after a legs-free "
                           "day, or record today knowing it is not comparable with a "
                           "clean morning.", icon="⚠️")
        except Exception:                                      # noqa: BLE001
            pass

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
            repo_.save_flexibility_draft(btry.Assessment(
                cluster=spec["key"], taken_on=date.today(), readings=(),
                cold=cold.startswith("Cold"),
            ))
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
    live = btry.run(spec["key"], battery_mod.SLOT_EVALUATORS, draft)
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
            repo_.save_flexibility_assessment(draft)
            repo_.clear_flexibility_draft()
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
    order = list(getattr(battery_mod, "applicable_tests", lambda _d: battery_mod.AVAILABLE_TESTS)(draft))

    step = int(st.session_state.get("fx_step", 0))
    step = max(0, min(step, len(order) - 1))
    key = order[step]
    test = battery_mod.TESTS[key]

    st.markdown(_fx_steps_html(order, step, draft), unsafe_allow_html=True)
    for skipped_key in battery_mod.AVAILABLE_TESTS:
        if skipped_key not in order:
            note = getattr(battery_mod, "SKIP_NOTES", {}).get(skipped_key)
            if note:
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
            prior_setup = next((r.setup_value for r in draft.readings
                                if r.test_key == key and r.setup_value is not None), None)
            if prior_setup is None:
                try:
                    for past in reversed(repo_.get_flexibility_assessments()):
                        prior_setup = next((r.setup_value for r in past.readings
                                            if r.test_key == key
                                            and r.setup_value is not None), None)
                        if prior_setup is not None:
                            st.caption(f"Last time you used **{prior_setup:g}**. Use the "
                                       f"same number unless something real changed — a "
                                       f"new setup number starts a new comparison, and "
                                       f"every reading against the old one stops being "
                                       f"comparable.")
                            break
                except Exception:                              # noqa: BLE001
                    prior_setup = None
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
        updated = draft
        for side, value in entered.items():
            if value is None:
                continue
            updated = fx.merge_reading(updated, btry.Reading(
                test_key=key, value=float(value), unit=test.unit, side=side,
                load_kg=load, setup_value=setup_value, voided=bool(void),
            ))
        repo_.save_flexibility_draft(updated)
        if last:
            repo_.save_flexibility_assessment(updated)
            repo_.clear_flexibility_draft()
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
        f'<span><b>{len(result.slots)}</b> of 4 slots run</span></div></div>',
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
        skipped = 4 - len(result.slots)
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
    today = date.today()
    stored = repo.get_repository().get_flexibility_assessments()
    latest = stored[-1] if stored else None
    return {
        "report": fx.assess(latest, today, baseline_sessions=len(stored)),
        "count": len(stored),
    }


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




#: Where the Foryond export lands. Gitignored with the rest of `Input_files/`,
#: so a deployment without it renders the empty state rather than crashing —
#: which is also what a first-time user sees, and is the correct thing to show.
_FITDAYS_EXPORT = Path(__file__).resolve().parent.parent / "Input_files" / "Fitdays.csv"


@st.cache_data(ttl=1800, show_spinner=False)
def _metabolism_screen_data() -> dict:
    """Everything the Metabolism screen renders.

    The file read lives here rather than in `services/body_composition.py` —
    that module is pure by contract, so it takes CSV *text* and this layer owns
    the I/O, the same split every other service in this app uses.

    A read failure must not render as "you have never weighed yourself". The
    two are indistinguishable once the list is empty, and only one of them is a
    real reading — so the error is carried through and surfaced."""
    load_error: str | None = None
    readings: list = []
    try:
        if _FITDAYS_EXPORT.exists():
            readings = bc.parse_fitdays_csv(
                _FITDAYS_EXPORT.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        readings, load_error = [], f"{type(exc).__name__}: {exc}"

    # Every gym scan corrected to the true height before it is shown. Four of
    # the five were run against a height 3-7 cm out, and height is squared
    # inside InBody's first step — see body_composition_baselines.py.
    scans = [s.at_height() for s in bcb.SCANS]

    return {
        "readings": readings,
        "scans": scans,
        "today": date.today(),
        "load_error": load_error,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _strength_screen_data() -> dict:
    """Everything the Strength screen renders, from one unwindowed read.

    `get_all_training_exercises_raw()` is the only source with per-set reps and
    weight — `get_recent_sessions()` parses the Sets JSON and then keeps only
    `actual_sets` and `total_volume_kg`, so an estimated 1RM cannot be built
    from it, and neither can the loaded/unloaded split tonnage eligibility
    needs.

    Falls back to an empty log on a repository error rather than crashing the
    page — the muscle-imbalance findings still render, since they read the
    clinical profile rather than the network. Same spirit as
    Repository.run_home_syncs' per-step (ok, error) contract."""
    # A failure must not render as "you have never trained". The two are
    # indistinguishable once the log is empty — overall 50.0, three regions at
    # 50.0, every tonnage week zero — and only one of them is a real reading.
    load_error: str | None = None
    try:
        rows = repo.get_repository().get_all_training_exercises_raw()
    except Exception as exc:
        rows, load_error = [], f"{type(exc).__name__}: {exc}"

    today = date.today()
    movement_weights = {
        name: weight
        for name, (_category, weight) in training_constants.EXERCISE_MOVEMENT_WEIGHT.items()
    }

    snapshot = strength_svc.snapshot(
        rows,
        strength_baselines.PEAKS_2025,
        training_constants.EXERCISE_BODY_REGION,
        movement_weights,
        strength_baselines.REGION_PRIOR,
        strength_baselines.PR_RIR,
        strength_baselines.ANCHOR_VALUE,
        today=today,
        calibrating=True,
    )
    series, unmapped = tonnage_svc.weekly_tonnage(
        rows, training_constants.EXERCISE_BODY_REGION, today=today, weeks=_STRENGTH_WEEKS,
    )
    score_points = strength_svc.score_series(
        rows,
        strength_baselines.PEAKS_2025,
        movement_weights,
        strength_baselines.PR_RIR,
        strength_baselines.ANCHOR_DATE,
        strength_baselines.ANCHOR_VALUE,
        today=today,
        weeks=_STRENGTH_WEEKS,
        calibrating=True,
    )
    labels = [
        w.week_start.strftime("%-d %b") if os.name != "nt"
        else w.week_start.strftime("%d %b").lstrip("0")
        for w in series
    ]
    imbalances = patient_profile.PROFILE.get("imbalances", {})
    return {
        "today":           today,
        "load_error":      load_error,
        "overall":         snapshot["overall"],
        "calibrating":     snapshot["calibrating"],
        "regions":         snapshot["regions"],
        "exercises":       snapshot["exercises"],
        "tonnage":         series,
        "unmapped":        sorted(unmapped),
        "score_series":    score_points,
        "week_labels":     labels,
        "imbalances":      imbalances,
        "imbalance_count": bioage.muscle_imbalance_count(imbalances),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  render()
# ─────────────────────────────────────────────────────────────────────────────

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
        st.caption(f"Data as of {date.today().strftime('%A %d %B')} · refreshes every 30 min")

        if st.button("Refresh engine data", use_container_width=False, key="engine_refresh_btn"):
            st.cache_data.clear()
            st.rerun()

        with st.spinner("Loading…"):
            bio_rows      = _bio()
            au_rows       = _au()
            pain_streak   = _streak()
            avg_tight     = _tight()
            diagnostic    = _diag()
            current_stage = _stage()
            lambda_val    = float(diagnostic.get("injury_weight_decay_lambda") or 0.05)

            tl          = engine.traffic_light(bio_rows, drift_rows=_bio_drift())
            acwr_result = engine.acwr(au_rows, current_stage,
                                      stage_start=_stage_start())
            inj_weight  = engine.injury_weight(lambda_val, pain_streak)
            obs_rem     = engine.observation_days_remaining(tl["data_days"])
            rec         = engine.volume_recommendation(tl, acwr_result, current_stage, obs_rem, inj_weight)
            stage_info  = engine.stage_status(current_stage, pain_streak, avg_tight)

        # ── Directive banner ──────────────────────────────────────────────────
        sig = rec["signal_color"]
        sig_color = engine.SIGNAL_COLORS.get(sig, engine.SIGNAL_COLORS["grey"])
        st.markdown(
            f"<div style='background:{sig_color}20;border-left:4px solid {sig_color};"
            f"border-radius:6px;padding:12px 16px;margin-bottom:16px;'>"
            f"<div style='font-size:10px;color:{sig_color};font-family:monospace;"
            f"letter-spacing:2px;margin-bottom:2px;'>DIRECTIVE</div>"
            f"<div style='font-size:17px;font-weight:700;color:#E8EAF0;'>{rec['label']}</div>"
            f"<div style='font-size:12px;color:#9AA3B2;margin-top:4px;'>{rec['action']}</div>"
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
        if tl["status"] == "insufficient_data":
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
                m         = metrics.get(key, {})
                val       = m.get("value")
                unit      = m.get("unit", "")
                baseline  = m.get("baseline_28d")
                delta     = m.get("delta_pct")
                sig_k     = m.get("signal", "grey")
                color     = engine.SIGNAL_COLORS.get(sig_k, engine.SIGNAL_COLORS["grey"])
                val_str   = f"{val} {unit}" if val is not None else "—"
                base_str  = f"28d avg: {baseline} {unit}" if baseline else "No baseline"
                delta_str = insights_svc.metric_delta_str(delta)
                # Temperature deviation is scored against fixed cut points, not
                # a rolling baseline — "No baseline" would read as missing data
                # when it actually means "this metric doesn't use one".
                thresholds = m.get("absolute_thresholds")
                if thresholds:
                    val_str  = f"{val:+.2f} {unit}" if val is not None else "—"
                    base_str = f"vs personal norm · red ≥ +{thresholds['red']:.2f}"
                    delta_str = {
                        "red":    "Possible illness onset",
                        "yellow": "Elevated — re-check tomorrow",
                        "green":  "Normal range",
                    }.get(sig_k, "No reading")
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
                missing_source = next(
                    (s.split(":")[1] for s in _sources_missing if s.startswith(f"{key}:")), None,
                )
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
                    for _k, _v in _drift.get("metrics", {}).items():
                        _lbl = metrics.get(_k, {}).get("label", _k)
                        st.caption(
                            f"**{_lbl}** — last {engine.DRIFT_RECENT_DAYS} readings "
                            f"{_v['recent']} vs prior {_drift['prior_days']} "
                            f"{_v['prior']} ({_v['delta_pct']:+.1f}%)"
                            + ("  ⚠ adverse" if _v["adverse"] else "")
                        )

        st.divider()

        # ── ACWR workload chart ───────────────────────────────────────────────
        st.subheader("Workload Trend — 28 Days")
        col_vals, col_chart = st.columns([1, 3], gap="large")

        with col_vals:
            st.metric("ACWR",            f"{acwr_val:.3f}" if acwr_val else "—")
            st.metric("Acute 7d avg AU", str(acwr_result["acute_avg"]))
            _basis = acwr_result.get("chronic_basis", "calendar")
            st.metric(
                "Chronic avg" if _basis == "stage" else "Chronic 28d avg",
                str(acwr_result["chronic_avg"]),
                help=(f"Averaged over the {acwr_result.get('in_stage_days', 28)} days "
                      f"of the current stage only — a window spanning a stage "
                      f"transition divides training load by rehab load."
                      if _basis == "stage" else
                      "Flat 28-day calendar window."),
            )
            st.metric("Stage ceiling",   str(acwr_result["ceiling"]))
            if acwr_result["hard_locked"]:
                st.error("Hard lock — do not increase volume.")
            elif not acwr_result.get("baseline_established", True):
                st.info(f"Baseline establishing — {acwr_result.get('in_stage_days', 0)}"
                        f"/{engine.ACWR_MIN_IN_STAGE_DAYS} days into this stage. "
                        f"Ratio is not diagnostic yet.")
            elif acwr_result.get("exceeds_ceiling"):
                st.warning("Above ceiling — advisory only, volume is not capped.")

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
        recent_sessions = _recent_sessions()
        # Monday-anchored week starts, oldest to newest, last ~8 weeks —
        # same "Monday minus weekday()" formula as services.plan._monday.
        today = date.today()
        current_week_start = today - timedelta(days=today.weekday())
        week_starts = [current_week_start - timedelta(weeks=n) for n in range(7, -1, -1)]
        volume_by_week = [
            volume_svc.weekly_volume_load(recent_sessions, ws) for ws in week_starts
        ]
        if any(v > 0 for v in volume_by_week):
            df_vol = pd.DataFrame(
                {"Volume (kg)": volume_by_week},
                index=[ws.isoformat() for ws in week_starts],
            )
            st.bar_chart(df_vol, color=["#00E874"])
        else:
            st.info("No logged volume yet for loaded, countable-reps exercises in the last 8 weeks.")

    # =========================================================================
    #  Tab 2 — Processing Queue
    # =========================================================================

    with tab_queue:
        unparsed_notes     = repo.get_repository().get_unparsed_session_notes()
        unparsed_readiness = repo.get_repository().get_unparsed_readiness()

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
                total    = total_pending
                done     = 0
                errors   = []

                for note in unparsed_notes:
                    try:
                        result = ai.parse_session_note(note["raw_text"], injury_profile)
                        repo.get_repository().update_session_note_ai(
                            note_id=note["id"],
                            summary=result["summary"],
                            sentiment_score=result["sentiment_score"],
                            flagged_body_parts=result["flagged_body_parts"],
                            warning_level=result["warning_level"],
                        )
                    except Exception as exc:
                        errors.append(f"Note {note['id']}: {exc}")
                    done += 1
                    progress.progress(done / total, text=f"Parsed {done}/{total}...")

                for entry in unparsed_readiness:
                    try:
                        result = ai.parse_tightness(entry["subjective_tightness"], injury_profile)
                        repo.get_repository().update_readiness_ai(
                            row_id=entry["id"],
                            severity=result["severity"],
                            body_parts=result["body_parts"],
                            sensation_type=result["sensation_type"],
                            warning_level=result["warning_level"],
                            # readiness_checkins is keyed by DATE, not by
                            # page id, so the Supabase mirror cannot name the
                            # row without this. `timestamp` is the Date
                            # property, read by the same call that populates
                            # the `date` column.
                            entry_date=entry.get("timestamp"),
                        )
                    except Exception as exc:
                        errors.append(f"Readiness {entry['id']}: {exc}")
                    done += 1
                    progress.progress(done / total, text=f"Parsed {done}/{total}...")

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

            def _entry_date_str(entry: dict) -> str:
                d = entry.get("session_date") or entry.get("timestamp") or ""
                return str(d)[:10]

            by_date: dict[str, list[dict]] = {}
            for entry in flagged:
                by_date.setdefault(_entry_date_str(entry), []).append(entry)

            if "queue_cal_year" not in st.session_state:
                anchor = date.fromisoformat(max(by_date)) if by_date else date.today()
                st.session_state["queue_cal_year"]  = anchor.year
                st.session_state["queue_cal_month"] = anchor.month

            cal_year  = st.session_state["queue_cal_year"]
            cal_month = st.session_state["queue_cal_month"]

            nav_prev, nav_label, nav_next = st.columns([1, 3, 1])
            if nav_prev.button("◀", key="queue_cal_prev"):
                cal_month -= 1
                if cal_month < 1:
                    cal_month, cal_year = 12, cal_year - 1
                st.session_state["queue_cal_year"]  = cal_year
                st.session_state["queue_cal_month"] = cal_month
                st.rerun()
            nav_label.markdown(
                f"<div style='text-align:center;font-weight:700;'>"
                f"{cal_mod.month_name[cal_month]} {cal_year}</div>",
                unsafe_allow_html=True,
            )
            if nav_next.button("▶", key="queue_cal_next"):
                cal_month += 1
                if cal_month > 12:
                    cal_month, cal_year = 1, cal_year + 1
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
            weeks = cal_mod.Calendar(firstweekday=0).monthdatescalendar(cal_year, cal_month)

            today = date.today()

            for week in weeks:
                week_cols = st.columns(7)
                for col, day in zip(week_cols, week):
                    day_str     = day.isoformat()
                    day_entries = by_date.get(day_str, [])
                    is_today    = day == today
                    cell        = col.container(border=True) if is_today else col
                    if day_entries:
                        levels = {e.get("warning_level") for e in day_entries}
                        ball   = "🔴" if "flag" in levels else "🟡"
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
                    level    = entry.get("warning_level", "monitor")
                    color    = engine.WARNING_LEVEL_ICONS.get(level, "⚫")
                    source   = entry.get("source", "?")
                    parts    = entry.get("body_parts", "")
                    if isinstance(parts, str) and parts.startswith("["):
                        parts = ", ".join(json.loads(parts))
                    summary  = entry.get("summary", "")
                    movement = entry.get("movement_name", "")
                    st.markdown(
                        f"{color} **{level.upper()}** &nbsp;·&nbsp; {source}"
                        + (f" &nbsp;·&nbsp; _{movement}_" if movement else ""),
                        unsafe_allow_html=True,
                    )
                    if summary:
                        st.caption(str(summary)[:200])
                    if parts:
                        st.caption(f"Body areas: {parts}")
                    st.markdown("---")

    # =========================================================================
    #  Tab 3 — Macro Trends
    # =========================================================================

    with tab_tightness:
        parsed_rows = repo.get_repository().get_parsed_readiness(limit=90)

        if not parsed_rows:
            st.info("No parsed readiness entries yet. Run the Processing Queue first.")
        else:
            body_freq = insights_svc.body_region_frequency(parsed_rows)

            if body_freq:
                st.subheader("Most Flagged Body Regions")
                df_freq = (
                    pd.DataFrame(list(body_freq.items()), columns=["Region", "Mentions"])
                    .sort_values("Mentions", ascending=False)
                    .reset_index(drop=True)
                )
                freq_chart = (
                    alt.Chart(df_freq)
                    .mark_bar(color="#00E874")
                    .encode(
                        x=alt.X(
                            "Region:N", title=None, sort="-y",
                            axis=alt.Axis(
                                labelAngle=0, labelLimit=1000, labelPadding=10,
                                labelExpr="split(datum.label, ' — ')",
                            ),
                        ),
                        y=alt.Y("Mentions:Q"),
                    )
                    .properties(height=340)
                )
                st.altair_chart(freq_chart, use_container_width=True)
                st.caption(
                    "Frequency of each region appearing in parsed tightness entries "
                    "(keyword matching)."
                )

            st.divider()
            st.subheader("Tightness Severity Timeline")
            df_time = pd.DataFrame(parsed_rows)[
                ["date", "tightness_score", "ai_tightness_severity", "pain_score"]
            ]
            df_time = df_time.rename(columns={
                "tightness_score":       "Self-reported",
                "ai_tightness_severity": "Keyword-parsed severity",
                "pain_score":            "Pain score",
            }).set_index("date")
            st.line_chart(df_time.dropna(how="all"))
            st.caption("Self-reported vs keyword-parsed tightness severity over time.")

            st.divider()
            st.subheader("Warning Level History")

            rows_by_level: dict[str, list[dict]] = {"none": [], "monitor": [], "flag": []}
            for row in parsed_rows:
                rows_by_level.setdefault(row.get("ai_warning_level") or "none", []).append(row)

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
                    parts = row.get("ai_body_parts") or ""
                    if isinstance(parts, str) and parts.startswith("["):
                        try:
                            parts = ", ".join(json.loads(parts))
                        except Exception:
                            pass
                    sensation = row.get("ai_sensation_type") or ""
                    if isinstance(sensation, str) and sensation.startswith("["):
                        try:
                            sensation = ", ".join(json.loads(sensation))
                        except Exception:
                            pass
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
        n_bio      = len(trend_data["biometrics"])
        n_sessions = len(trend_data["sessions"])

        col_d, col_s = st.columns(2)
        col_d.metric("Biometric days available",    n_bio)
        col_s.metric("Training sessions available", n_sessions)

        if n_bio < engine.MIN_OBSERVATION_DAYS:
            st.warning(
                f"Need at least {engine.MIN_OBSERVATION_DAYS} days of biometric data for trend "
                f"analysis. Currently have {n_bio}. Keep logging daily."
            )
        else:
            computed     = stats_mod.compute_all_correlations(trend_data)
            notable      = computed.get("notable_correlations", [])
            slopes       = computed.get("slopes", {})
            recovery_dir = computed["recovery_direction"]

            st.markdown(
                f"**Recovery direction (deterministic):** "
                f"**{recovery_dir.replace('_', ' ').title()}**"
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

            recovery     = r.get("recovery_direction", "insufficient_data")
            recovery_map = {
                "improving":        "Improving",
                "stable":           "Stable",
                "degrading":        "Degrading",
                "insufficient_data": "Insufficient data",
            }
            st.markdown(
                f"**Recovery trajectory:** "
                f"{recovery_map.get(recovery, recovery.replace('_', ' ').title())}"
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
        fused_only = [r for r in fusion_rows if r.get("source") == "fused"]

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
            oura_only_n = len(fusion_rows) - len(fused_only)
            c1, c2, c3 = st.columns(3, gap="small")
            c1.metric("Nights fused", len(fused_only))
            c2.metric("Oura only", oura_only_n)
            if fused_only:
                phantom = [float(r.get("phantom_wake_minutes") or 0) for r in fused_only]
                c3.metric("Median phantom wake removed", f"{sorted(phantom)[len(phantom) // 2]:.0f} min")
            st.caption(
                f"{oura_only_n} night(s) have no matching Garmin stage data and pass "
                "Oura through unchanged — Garmin only began returning stage segments "
                "in May 2026."
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
            fused_hours = {
                r["date"]: float(r["master_sleep_hours"])
                for r in fused_only if str(r.get("master_sleep_hours") or "").strip() != ""
            }
            shadow = dash.sleep_fusion_shadow_report(_bio(), fused_hours)
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
        # The Supabase mirror's health. It runs behind every sync and nothing
        # reads from Postgres yet, so a mirror that stopped working is
        # INVISIBLE by construction — it looks exactly like one that is up to
        # date. This is the only place that difference is shown.
        _mirror_repo = repo.get_repository()
        if _mirror_repo.supabase_configured():
            _mirror_err = _mirror_repo.mirror_last_error
            if _mirror_err:
                st.warning(
                    f"**Supabase mirror failing on `{_mirror_err[0]}`** — "
                    f"Notion and Sheets are unaffected and still hold "
                    f"everything; the Postgres copy is behind. Repair with "
                    f"`python scripts/push_datastore_to_supabase.py`.\n\n"
                    f"```\n{_mirror_err[1]}\n```"
                )
            else:
                st.caption("Supabase mirror: no errors recorded this session.")

        st.caption(
            "Legacy Apple Health export (Sheet1) — no longer read by the engine. "
            "Kept for historical reference and the one-time Garmin backfill "
            "(scripts/backfill_garmin_from_sheet1.py) only."
        )

        try:
            sheet_id = st.secrets["GOOGLE_SHEETS_ID"]
        except Exception:
            sheet_id = None
            st.error("GOOGLE_SHEETS_ID missing from .streamlit/secrets.toml")

        if sheet_id:
            if st.button("Refresh", use_container_width=False, key="sync_refresh"):
                st.cache_data.clear()
                st.rerun()

            with st.spinner("Reading Sheet1 from Google Sheets…"):
                try:
                    sync_rows = _sync_raw(sheet_id)
                except Exception as exc:
                    sync_rows = None
                    st.error(f"Could not read Sheet1: {exc}")

            if sync_rows is not None:
                if not sync_rows:
                    st.info("Sheet1 is empty — no data yet.")
                else:
                    df_sync = pd.DataFrame(sync_rows)

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total rows", len(df_sync))
                    col2.metric("Earliest",   str(df_sync["Date/Time"].iloc[0])[:10])
                    col3.metric("Latest",     str(df_sync["Date/Time"].iloc[-1])[:10])

                    st.divider()

                    st.subheader("Raw Sheet Data")
                    st.dataframe(df_sync, use_container_width=True, height=400)

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
                        "A fixed daily record of the blend above, written once a day "
                        "(Repository.sync_biometric_blend) to its own sheet tab. Unlike the "
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
                        earliest = date.fromisoformat(blend_history[0]["date"])
                        latest = date.fromisoformat(blend_history[-1]["date"])
                        col_from, col_to = st.columns(2)
                        start_pick = col_from.date_input("From", value=earliest, key="blend_hist_from")
                        end_pick = col_to.date_input("To", value=latest, key="blend_hist_to")
                        filtered = [
                            r for r in blend_history
                            if str(start_pick) <= r["date"] <= str(end_pick)
                        ]
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
                        "once a day (Repository.sync_metrics_history) to its own sheet tab, "
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
                        earliest = date.fromisoformat(metrics_history[0]["date"])
                        latest = date.fromisoformat(metrics_history[-1]["date"])
                        col_from, col_to = st.columns(2)
                        start_pick = col_from.date_input("From", value=earliest, key="metrics_hist_from")
                        end_pick = col_to.date_input("To", value=latest, key="metrics_hist_to")
                        filtered = [
                            r for r in metrics_history
                            if str(start_pick) <= r["date"] <= str(end_pick)
                        ]
                        st.dataframe(pd.DataFrame(filtered), use_container_width=True, height=400)
                    elif metrics_history is not None:
                        st.info("No persisted history yet — wait for the automatic once-a-day sync.")

                    st.divider()
                    st.caption(
                        "Weekly Rollup syncs automatically once a week; Garmin Daily Metrics "
                        "syncs automatically once a day (both checked whenever the Home or "
                        "Training page loads — no button needed)."
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
                            "Oura) and archive to their own Sheet tabs (Garmin Daily, Garmin "
                            "Activities). Daily Metrics also syncs automatically once a day on "
                            "Home/Training page open; use the button below to run it on demand."
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
                        "Sheet tabs, so it never calls a device API and is safe to "
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
                            "Add OURA_TOKEN to .streamlit/secrets.toml to enable Oura sync. "
                            "Feeds the readiness/ACWR engine (70% weight for HRV/RHR/sleep, 20% "
                            "for steps, blended with Garmin) once configured."
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
