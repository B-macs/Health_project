"""
Morning Check-In — Daily readiness capture.
Runs as the Streamlit home page: streamlit run app.py
"""

import streamlit as st
from datetime import date
import db
import styles

st.set_page_config(
    page_title="Health Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)
styles.inject_css()

# ── Reference data ────────────────────────────────────────────────────────────

# Injury-specific anatomical map (L-spine → hip kinetic chain from MRI profile)
ANATOMICAL_LOCATIONS = [
    "Lumbar — L3/L4 (Left)",
    "Lumbar — L4/L5 (Left)",
    "Lumbar — L5/S1 (Right — Primary)",
    "Lumbar — L5/S1 (Left)",
    "Central Lower Back",
    "Sacroiliac Joint — Right",
    "Sacroiliac Joint — Left",
    "Hip Flexor / Psoas — Right",
    "Hip Flexor / Psoas — Left",
    "Glute — Right",
    "Glute — Left",
    "Glute Medius — Right",
    "Glute Medius — Left",
    "Piriformis — Right",
    "Piriformis — Left",
    "Hamstring — Right",
    "Hamstring — Left",
    "Calf — Right",
    "Calf — Left",
    "Thoracic / Mid Back",
    "Other",
]

SENSATION_TAGS = [
    "Normal",
    "Tight",
    "Stiff",
    "Dull Ache",
    "Sharp",
    "Neural",
    "Mild Tiredness",
    "Very Tight",
    "Slightly Tired",
]

CONDITION_OPTIONS = ["Excellent", "Good", "Average", "Below Average", "Poor"]

# ── Header ────────────────────────────────────────────────────────────────────

st.title("Morning Check-In")
st.caption(f"{date.today().strftime('%A, %d %B %Y')} — Stage 1: Rehab")
st.divider()

# ── Form ──────────────────────────────────────────────────────────────────────

with st.form("morning_checkin", clear_on_submit=True):

    col_tissue, col_location, col_lifestyle = st.columns([1, 2, 1], gap="large")

    # ── Column 1: Tissue State ────────────────────────────────────────────────
    with col_tissue:
        st.subheader("Tissue State")
        tightness_score = st.slider(
            "Tightness Score",
            min_value=0, max_value=10, value=0, step=1,
            help="Clinical scale. 0 = no restriction, 10 = severe. "
                 "Primary metric for Stage 1 → 2 progression.",
        )
        pain_score = st.slider(
            "Pain Score",
            min_value=0, max_value=10, value=0, step=1,
            help="0 = pain-free, 10 = worst imaginable.",
        )
        current_condition = st.selectbox("General Readiness", CONDITION_OPTIONS)

    # ── Column 2: Location & Sensation ───────────────────────────────────────
    with col_location:
        st.subheader("Location & Sensation")
        anatomical_locations = st.multiselect(
            "Affected Areas",
            ANATOMICAL_LOCATIONS,
            placeholder="Select one or more regions…",
        )
        sensation_tags = st.multiselect(
            "Sensation Tags",
            SENSATION_TAGS,
            placeholder="Pick all that apply…",
        )
        subjective_note = st.text_input(
            "Sensation Note",
            placeholder="e.g. Lower right back stiff when standing from chair, eases after 10 minutes",
            help="One sentence. Stored raw for AI parsing.",
        )

    # ── Column 3: Lifestyle Factors ───────────────────────────────────────────
    with col_lifestyle:
        st.subheader("Lifestyle Factors")
        psych_stress = st.select_slider(
            "Psychological Stress",
            options=[1, 2, 3, 4, 5],
            value=1,
            help="1 = calm / no stress, 5 = high cognitive/emotional load.",
        )
        alcohol_units = st.number_input(
            "Alcohol Units (last 24 h)",
            min_value=0.0, max_value=20.0, value=0.0, step=0.5,
            help="Standard drink = 1 unit. 0 = none consumed.",
        )
        travel_flag = st.toggle(
            "Travel / Location Change",
            help="Hotel beds, flights, altitude changes — flags HRV/stiffness context for AI.",
        )

    st.divider()
    submitted = st.form_submit_button(
        "Save Morning Check-In", use_container_width=True, type="primary"
    )

if submitted:
    db.save_daily_readiness(
        current_condition=current_condition,
        tightness_score=tightness_score,
        pain_score=pain_score,
        anatomical_locations=anatomical_locations,
        sensation_tags=sensation_tags,
        subjective_tightness=subjective_note,
        alcohol_units=alcohol_units,
        travel_flag=travel_flag,
        psych_stress_score=psych_stress,
    )
    st.success(
        f"Check-in saved — Tightness {tightness_score}/10, Pain {pain_score}/10. "
        "Head to Training Plan when ready to start your session."
    )
