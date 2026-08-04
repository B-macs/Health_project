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

import patient_profile
import repo
import strength_baselines
import styles
import training_constants
from services import ai
from services import bioage
from services import dashboard as dash
from services import engine
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


def _bioage_card_html(key: str, href: str) -> str:
    color = _BIOAGE_COLORS[key]
    label = _BIOAGE_LABELS[key]
    bg    = _bioage_b64(str(_BIOAGE_BG[key]))
    bg_css = (
        f"background-image:linear-gradient(90deg,#0B0F1A 0%,rgba(11,15,26,0.75) 45%,"
        f"rgba(11,15,26,0.15) 80%),url('{bg}');background-size:cover;"
        f"background-position:center right;"
    ) if bg else "background:#0B0F1A;"
    return (
        f'<a href="{href}" style="text-decoration:none;">'
        f'<div style="position:relative;height:150px;border-radius:14px;overflow:hidden;'
        f'margin-bottom:14px;border:1px solid rgba(255,255,255,0.08);{bg_css}">'
        f'<div style="position:relative;z-index:1;height:100%;display:flex;'
        f'align-items:center;justify-content:space-between;padding:0 22px;">'
        f'<span style="font-size:34px;font-weight:800;color:{color};'
        f'text-shadow:0 0 18px {color}99,0 0 4px {color};letter-spacing:-0.5px;">{label}</span>'
        f'<span style="font-size:26px;color:{color};font-weight:300;">&rsaquo;</span>'
        f'</div>'
        f'</div>'
        f'</a>'
    )


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
#  distinct value across every day it existed. services/bioage.py's scoring
#  functions are left in place and tested but are no longer wired to this
#  screen; muscle_imbalance_count still is.
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
        selected = st.query_params.get("bioage")

        if selected in _BIOAGE_LABELS:
            color = _BIOAGE_COLORS[selected]
            label = _BIOAGE_LABELS[selected]
            st.markdown(
                '<a href="?page=insights" style="text-decoration:none;color:#9AA3B2;'
                'font-size:14px;">&larr; Back</a>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<h2 style='color:{color};margin-top:8px;'>{label}</h2>",
                unsafe_allow_html=True,
            )
            if selected == "strength":
                _render_strength_detail()
            else:
                st.info(f"{label} biological age breakdown — coming soon.")
        else:
            st.caption("Select a category to see its biological age breakdown.")
            for key in _BIOAGE_CATEGORIES:
                st.markdown(
                    _bioage_card_html(key, f"?page=insights&bioage={key}"),
                    unsafe_allow_html=True,
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
