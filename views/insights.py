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
from dataclasses import asdict
from datetime import date
from pathlib import Path

import altair as alt
import streamlit as st
import pandas as pd

import repo
from services import ai
from services import engine
from services import stats as stats_mod
from services import insights as insights_svc


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
#  Premium dark-mode hero/progress/body-regions/muscle-balance/assessment
#  layout. Copy, illustrations and layout are the real UI; every *computed*
#  value (scores, dates, counts, chart history) is a placeholder (None) in
#  _STRENGTH_SCREEN below until the BioAge engine exists to fill it in.
# ─────────────────────────────────────────────────────────────────────────────

_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_STRENGTH_SCREEN: dict = {
    "hero": {
        "title":          "Strength BioAge",
        "value":          None,   # primary metric — blank until engine computes it
        "unit":           "years",
        "description":    "",
        "illustration":   _BIOAGE_BG_DIR / "derived" / "strength_hero.png",
        "accent_color":   _BIOAGE_COLORS["strength"],
        "cta_label":      "Assistance",
        "cta_icon":       "🎙️",
    },
    "progress": {
        "title":            "Progress",
        "subtitle":         "",
        "updated_label":    "Updated on",
        "updated_value":    None,   # blank
        "real_age_label":   "Real age",
        "real_age_value":   None,   # blank
        "chart_points":     [],     # list[(month_index 0-11, value)] — blank
        "y_min":            None,
        "y_max":            None,
        "button_label":     "Show All Progress",
    },
    "body_regions": [
        {
            "id": "upper_body", "name": "Upper body", "score": None, "unit": "years",
            "illustration": _BIOAGE_BG_DIR / "derived" / "upper_body.png",
            "accent_color": _BIOAGE_COLORS["strength"],
        },
        {
            "id": "core", "name": "Core", "score": None, "unit": "years",
            "illustration": _BIOAGE_BG_DIR / "derived" / "core.png",
            "accent_color": _BIOAGE_COLORS["strength"],
        },
        {
            "id": "lower_body", "name": "Lower body", "score": None, "unit": "years",
            "illustration": _BIOAGE_BG_DIR / "derived" / "lower_body.png",
            "accent_color": _BIOAGE_COLORS["strength"],
        },
    ],
    "muscle_balance": {
        "title":            "Muscle balance analysis",
        "summary":          "",
        "imbalance_count":  None,   # blank
        "illustration":     _BIOAGE_BG_DIR / "derived" / "muscle_balance.png",
        "cta_label":        "View All",
    },
    "assessment": {
        "title":        "Test your strength",
        "description":  (
            "Perform a strength test to get your muscle balance analysis "
            "and update your Strength BioAge."
        ),
        "primary_cta":          "Start Assessment",
        "completion_progress":  None,   # blank
    },
}


def _progress_chart_svg(
    points: list[tuple[int, float]],
    y_min: float | None,
    y_max: float | None,
    accent: str,
    width: int = 640,
    height: int = 220,
) -> str:
    """Minimal medical-style line chart: dashed gridlines, Jan-Dec x-axis,
    optional y-range, single highlighted (latest) point. Renders an empty
    grid with no plotted point when `points` is empty."""
    pad_l, pad_r, pad_t, pad_b = 34, 14, 14, 24
    iw, ih = width - pad_l - pad_r, height - pad_t - pad_b
    has_range = y_min is not None and y_max is not None and y_max > y_min
    lo, hi = (y_min, y_max) if has_range else (0.0, 1.0)

    def x_for(m: float) -> float:
        return pad_l + (m / 11) * iw

    def y_for(v: float) -> float:
        return pad_t + (1 - (v - lo) / (hi - lo)) * ih

    n_rows = 4
    grid, y_ticks = [], []
    for i in range(n_rows + 1):
        frac = i / n_rows
        gy = pad_t + frac * ih
        grid.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width - pad_r}" y2="{gy:.1f}" '
            f'stroke="rgba(255,255,255,0.08)" stroke-width="1" stroke-dasharray="2,4"/>'
        )
        label = f"{hi - frac * (hi - lo):.0f}" if has_range else "—"
        y_ticks.append(
            f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" font-size="10" '
            f'fill="#5A6377" font-family="system-ui">{label}</text>'
        )

    x_labels = []
    for i, m in enumerate(_MONTH_LABELS):
        gx = x_for(i)
        x_labels.append(
            f'<line x1="{gx:.1f}" y1="{pad_t}" x2="{gx:.1f}" y2="{height - pad_b}" '
            f'stroke="rgba(255,255,255,0.04)" stroke-width="1"/>'
            f'<text x="{gx:.1f}" y="{height - 6}" text-anchor="middle" font-size="9" '
            f'fill="#5A6377" font-family="system-ui">{m}</text>'
        )

    line_html = point_html = empty_html = ""
    if points:
        pts = sorted(points, key=lambda p: p[0])
        coords = [(x_for(m), y_for(v)) for m, v in pts]
        if len(coords) > 1:
            poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
            line_html = (
                f'<polyline points="{poly}" fill="none" stroke="{accent}" '
                f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        for i, (x, y) in enumerate(coords):
            is_last = i == len(coords) - 1
            r, fill = (6, accent) if is_last else (4, "rgba(255,255,255,0.25)")
            halo = (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 6}" fill="{accent}" opacity="0.18"/>'
                if is_last else ""
            )
            point_html += (
                f'{halo}<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" '
                f'stroke="#07080D" stroke-width="2"/>'
            )
    else:
        empty_html = (
            f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" font-size="12" '
            f'fill="#5A6377" font-style="italic" font-family="system-ui">'
            f'No progress recorded yet</text>'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'preserveAspectRatio="xMidYMid meet">'
        + "".join(grid) + "".join(y_ticks) + "".join(x_labels)
        + line_html + point_html + empty_html +
        '</svg>'
    )


def _strength_hero_html() -> str:
    hero = _STRENGTH_SCREEN["hero"]
    accent = hero["accent_color"]
    bg = _bioage_b64(str(hero["illustration"]))
    bg_css = (
        f"background-image:linear-gradient(100deg,rgba(11,15,26,0.92) 0%,"
        f"rgba(11,15,26,0.55) 32%,rgba(11,15,26,0.08) 62%),url('{bg}');"
        f"background-size:cover;background-position:center right;"
    ) if bg else "background:#0B0F1A;"
    value = hero["value"] if hero["value"] is not None else "—"
    desc_html = (
        f'<div style="font-size:13px;color:#9AA3B2;margin-top:10px;max-width:220px;">'
        f'{hero["description"]}</div>'
    ) if hero["description"] else ""
    return (
        # aspect-ratio matches the derived crop (see prepare_bioage_illustrations.py)
        # so the hero grows taller on a wide desktop card instead of forcing
        # background-size:cover to upscale/crop it into a thin strip; min/max-height
        # clamp the two ends (enough room for the text on mobile, not absurdly
        # tall on an ultrawide monitor).
        f'<div style="position:relative;aspect-ratio:1194/356;min-height:220px;'
        f'max-height:420px;border-radius:22px;overflow:hidden;'
        f'margin-bottom:18px;border:1px solid rgba(255,255,255,0.08);{bg_css}'
        f'box-shadow:0 8px 32px rgba(0,0,0,0.4);">'
        f'<div style="position:relative;z-index:1;height:100%;box-sizing:border-box;'
        f'padding:28px 24px;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div>'
        f'<div style="font-size:11px;color:{accent};letter-spacing:2px;text-transform:uppercase;'
        f'font-weight:600;margin-bottom:8px;">{hero["title"]}</div>'
        f'<div style="font-size:46px;font-weight:800;color:#F4F6FB;line-height:1;'
        f'text-shadow:0 0 24px {accent}40;">{value}'
        f'<span style="font-size:18px;font-weight:500;color:#9AA3B2;margin-left:8px;">'
        f'{hero["unit"]}</span></div>'
        f'{desc_html}'
        f'</div>'
        f'<div><span style="display:inline-flex;align-items:center;gap:6px;'
        f'background:rgba(255,255,255,0.08);color:#D4DCEE;font-size:13px;font-weight:500;'
        f'padding:10px 18px;border-radius:30px;">{hero["cta_icon"]} {hero["cta_label"]}</span>'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def _body_region_card_html(region: dict) -> str:
    accent = region["accent_color"]
    bg = _bioage_b64(str(region["illustration"]))
    bg_css = (
        f"background-image:linear-gradient(90deg,rgba(11,15,26,0.88) 0%,"
        f"rgba(11,15,26,0.4) 30%,rgba(11,15,26,0.04) 65%),url('{bg}');"
        f"background-size:cover;background-position:center right;"
    ) if bg else "background:#0B0F1A;"
    score = region["score"] if region["score"] is not None else "—"
    return (
        f'<div style="position:relative;min-height:132px;border-radius:16px;overflow:hidden;'
        f'margin-bottom:12px;border:1px solid rgba(255,255,255,0.06);{bg_css}">'
        f'<div style="position:relative;z-index:1;min-height:132px;display:flex;'
        f'flex-direction:column;justify-content:center;padding:18px 44px 18px 20px;">'
        f'<div style="font-size:20px;font-weight:700;color:{accent};margin-bottom:4px;">'
        f'{region["name"]}</div>'
        f'<div style="font-size:26px;font-weight:300;color:#F4F6FB;">{score}'
        f'<span style="font-size:12px;color:#9AA3B2;margin-left:6px;">{region["unit"]}</span>'
        f'</div></div>'
        f'<div style="position:absolute;top:50%;right:16px;transform:translateY(-50%);'
        f'font-size:22px;color:{accent};font-weight:300;">&rsaquo;</div>'
        f'</div>'
    )


def _muscle_balance_card_html() -> str:
    mb = _STRENGTH_SCREEN["muscle_balance"]
    bg = _bioage_b64(str(mb["illustration"]))
    bg_css = (
        f"background-image:linear-gradient(90deg,rgba(11,15,26,0.88) 0%,"
        f"rgba(11,15,26,0.55) 30%,rgba(11,15,26,0.1) 58%),url('{bg}');"
        f"background-size:cover;background-position:center right;"
    ) if bg else "background:#0B0F1A;"
    count = mb["imbalance_count"]
    count_display = str(count) if count is not None else "—"
    return (
        f'<div style="position:relative;min-height:150px;border-radius:16px;overflow:hidden;'
        f'margin-bottom:8px;border:1px solid rgba(255,255,255,0.06);{bg_css}">'
        f'<div style="position:relative;z-index:1;min-height:150px;display:flex;'
        f'flex-direction:column;justify-content:center;padding:20px 22px;">'
        f'<div style="font-size:16px;font-weight:600;color:#F4F6FB;margin-bottom:6px;">'
        f'Muscle imbalances</div>'
        f'<div style="font-size:30px;font-weight:300;color:#F4F6FB;">{count_display}'
        f'<span style="font-size:13px;color:#9AA3B2;margin-left:6px;">imbalances</span></div>'
        f'</div></div>'
    )


def _assessment_card_html() -> str:
    a = _STRENGTH_SCREEN["assessment"]
    return (
        f'<div style="border-radius:16px;overflow:hidden;margin-bottom:10px;'
        f'border:1px solid rgba(255,255,255,0.06);'
        f'background:linear-gradient(135deg,#12161F 0%,#0B0F1A 100%);padding:24px 22px;">'
        f'<div style="font-size:19px;font-weight:700;color:#F4F6FB;margin-bottom:8px;">'
        f'{a["title"]}</div>'
        f'<div style="font-size:13px;color:#9AA3B2;line-height:1.6;">{a["description"]}</div>'
        f'</div>'
    )


def _render_strength_detail() -> None:
    """Strength BioAge detail — hero, progress chart, body regions, muscle
    balance, assessment CTA. One continuous scroll, no sub-tabs/transitions."""
    s = _STRENGTH_SCREEN
    accent = s["hero"]["accent_color"]

    # Span the full desktop/Whoop breakpoint width, capped only at a generous
    # ceiling — real browser windows rarely exceed this, so in practice the
    # screen goes edge-to-edge; the cap just stops an ultrawide monitor from
    # stretching the illustrations past the point their (now widened, see
    # scripts/prepare_bioage_illustrations.py) native resolution supports.
    st.markdown(
        '<style>[data-testid="stMainBlockContainer"][data-testid="stMainBlockContainer"]'
        "{max-width:1600px !important;margin-left:auto !important;"
        "margin-right:auto !important;}</style>",
        unsafe_allow_html=True,
    )

    st.markdown(_strength_hero_html(), unsafe_allow_html=True)

    # ── Progress ──────────────────────────────────────────────────────────
    # Plain divs, not <h3>, below: styles.py's global h3 rule forces
    # font-size:10px + uppercase (!important) which would hijack these.
    p = s["progress"]
    updated  = p["updated_value"] or "—"
    real_age = p["real_age_value"] if p["real_age_value"] is not None else "—"

    head_l, head_r = st.columns([2, 1])
    head_l.markdown(
        f"<div style='color:#F4F6FB;font-size:18px;font-weight:600;'>{p['title']}</div>",
        unsafe_allow_html=True,
    )
    head_r.markdown(
        f"<div style='text-align:right;font-size:11px;color:#5A6377;margin-top:6px;'>"
        f"{p['updated_label']} {updated}</div>",
        unsafe_allow_html=True,
    )

    sub_l, sub_r = st.columns([2, 1])
    sub_l.markdown(
        f"<div style='font-size:13px;color:#6BAF8B;'>{p['real_age_label']}: {real_age}</div>",
        unsafe_allow_html=True,
    )
    sub_r.markdown(
        "<div style='text-align:right;font-size:11px;color:#5A6377;'>Age (yrs)</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="background:#0E1018;border:1px solid rgba(255,255,255,0.06);'
        f'border-radius:16px;padding:12px 8px 4px;margin:10px 0 16px;">'
        f'{_progress_chart_svg(p["chart_points"], p["y_min"], p["y_max"], accent)}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="text-align:center;padding:12px;border-radius:30px;'
        f'background:rgba(255,255,255,0.06);color:#D4DCEE;font-size:13px;'
        f'font-weight:500;margin-bottom:24px;">{p["button_label"]}</div>',
        unsafe_allow_html=True,
    )

    # ── Body performance ──────────────────────────────────────────────────
    st.markdown(
        "<div style='color:#F4F6FB;font-size:18px;font-weight:600;"
        "margin-bottom:12px;'>Body parts</div>",
        unsafe_allow_html=True,
    )
    for region in s["body_regions"]:
        st.markdown(_body_region_card_html(region), unsafe_allow_html=True)

    # ── Muscle balance ────────────────────────────────────────────────────
    mb = s["muscle_balance"]
    bal_l, bal_r = st.columns([2, 1])
    bal_l.markdown(
        f"<div style='color:#F4F6FB;font-size:18px;font-weight:600;"
        f"margin-bottom:12px;'>{mb['title']}</div>",
        unsafe_allow_html=True,
    )
    bal_r.markdown(
        f"<div style='text-align:right;font-size:13px;color:{accent};margin-top:6px;'>"
        f"{mb['cta_label']} &rsaquo;</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_muscle_balance_card_html(), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    # ── Assessment CTA ────────────────────────────────────────────────────
    st.markdown(_assessment_card_html(), unsafe_allow_html=True)


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
def _au():          return repo.get_repository().get_daily_session_au(28)

@st.cache_data(ttl=1800, show_spinner=False)
def _streak():      return repo.get_repository().get_pain_free_streak()

@st.cache_data(ttl=1800, show_spinner=False)
def _tight():       return repo.get_repository().get_avg_tightness(14)

@st.cache_data(ttl=1800, show_spinner=False)
def _diag():        return repo.get_repository().get_diagnostic_profile()

@st.cache_data(ttl=1800, show_spinner=False)
def _stage():       return repo.get_repository().get_current_stage()

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


# ─────────────────────────────────────────────────────────────────────────────
#  render()
# ─────────────────────────────────────────────────────────────────────────────

def render() -> None:
    st.title("Insights")
    st.caption("Engine metrics, biometric trends, session pattern analysis.")

    injury_profile = repo.get_repository().get_diagnostic_profile()

    (
        tab_bioage, tab_engine, tab_queue,
        tab_tightness, tab_sync,
    ) = st.tabs([
        "BioAge",
        "Engine Data",
        "Processing Queue",
        "Macro Trends",
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

            tl          = engine.traffic_light(bio_rows)
            acwr_result = engine.acwr(au_rows, current_stage)
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
            c_hrv, c_rhr, c_sleep = st.columns(3)

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

        st.divider()

        # ── ACWR workload chart ───────────────────────────────────────────────
        st.subheader("Workload Trend — 28 Days")
        col_vals, col_chart = st.columns([1, 3], gap="large")

        with col_vals:
            st.metric("ACWR",            f"{acwr_val:.3f}" if acwr_val else "—")
            st.metric("Acute 7d avg AU", str(acwr_result["acute_avg"]))
            st.metric("Chronic 28d avg", str(acwr_result["chronic_avg"]))
            st.metric("Stage ceiling",   str(acwr_result["ceiling"]))
            if acwr_result["hard_locked"]:
                st.error("Hard lock — do not increase volume.")

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
    #  Tab 4 — Sync
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
                        with st.spinner("Computing and persisting the full blend history…"):
                            try:
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
                                with st.spinner("Pulling daily metrics from Garmin…"):
                                    try:
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
                                with st.spinner("Pulling activities from Garmin…"):
                                    try:
                                        n = sync_repo.sync_garmin_activities(limit=20)
                                        st.success(
                                            f"Synced {n} activities to the Garmin Activities tab."
                                        )
                                    except Exception as exc:
                                        st.warning(f"Garmin activity sync failed: {exc}")

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
                            with st.spinner("Pulling the last 7 days from Oura…"):
                                try:
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
