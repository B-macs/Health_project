"""
views/checkin.py — Morning Check-In view.
Call render() from the SPA router in app.py.
"""

from datetime import date
import streamlit as st
import repo
from services.models import CheckInRecord
from training_constants import ANATOMICAL_LOCATIONS, SENSATION_TAGS


CONDITION_OPTIONS = ["Excellent", "Good", "Average", "Below Average", "Poor"]

# Illustrative reference bands for the 0–10 sliders below — wording/ranges are
# a starting point, not a clinical standard. Tweak freely; each tuple is
# (range_label, description) and renders as one line in the reference guide.
TIGHTNESS_SCALE_GUIDE = [
    ("0",    "No tightness — full, unrestricted range of motion."),
    ("1–2",  "Loose, barely noticeable, no effect on movement."),
    ("3–4",  "Slight tightness, mild stiffness, doesn't restrict range."),
    ("5–6",  "Mild DOMS, noticeable stiffness, slight restriction in range of motion."),
    ("7–8",  "Moderate–severe DOMS, muscle feels stiff/knotted, restricted range, discomfort on stretch."),
    ("9–10", "Severe tightness, can't move the muscle through full range without pulling/resistance, feels locked up."),
]

PAIN_SCALE_GUIDE = [
    ("0",    "No pain — pain-free."),
    ("1–3",  "Mild, noticeable but doesn't affect training."),
    ("4–5",  "Moderate, distracting, would consider modifying training."),
    ("6–7",  "Significant pain, limits range/effort, should ease off that movement."),
    ("8–10", "Severe/sharp pain, stop the movement entirely."),
]


def render() -> None:
    st.title("Morning Check-In")
    st.caption(f"{date.today().strftime('%A, %d %B %Y')} — Stage 1: Rehab")
    st.divider()

    with st.form("morning_checkin", clear_on_submit=True):
        col_tissue, col_location, col_lifestyle = st.columns([1, 2, 1], gap="large")

        with col_tissue:
            st.subheader("Tissue State")
            tightness_score = st.slider(
                "Tightness Score", min_value=0, max_value=10, value=0, step=1,
                help="Clinical scale. 0 = no restriction, 10 = severe. "
                     "Primary metric for Stage 1 → 2 progression.",
            )
            pain_score = st.slider(
                "Pain Score", min_value=0, max_value=10, value=0, step=1,
                help="0 = pain-free, 10 = worst imaginable.",
            )
            current_condition = st.selectbox(
                "General Readiness", CONDITION_OPTIONS, key="checkin_condition"
            )

        with col_location:
            st.subheader("Location & Sensation")
            anatomical_locations = st.multiselect(
                "Affected Areas", ANATOMICAL_LOCATIONS,
                placeholder="Select one or more regions…",
                key="checkin_locations",
            )
            sensation_tags = st.multiselect(
                "Sensation Tags", SENSATION_TAGS,
                placeholder="Pick all that apply…",
                key="checkin_tags",
            )
            subjective_note = st.text_input(
                "Sensation Note",
                placeholder="e.g. Lower right back stiff when standing from chair, eases after 10 minutes",
                help="One sentence. Stored raw for AI parsing.",
                key="checkin_note",
            )

        with col_lifestyle:
            st.subheader("Lifestyle Factors")
            psych_stress = st.select_slider(
                "Psychological Stress", options=[1, 2, 3, 4, 5], value=1,
                help="1 = calm / no stress, 5 = high cognitive/emotional load.",
                key="checkin_stress",
            )
            alcohol_units = st.number_input(
                "Alcohol Units (last 24 h)", min_value=0.0, max_value=20.0,
                value=0.0, step=0.5,
                help="Standard drink = 1 unit. 0 = none consumed.",
                key="checkin_alcohol",
            )
            travel_flag = st.toggle(
                "Travel / Location Change",
                help="Hotel beds, flights, altitude changes — flags HRV/stiffness context for AI.",
                key="checkin_travel",
            )

        st.divider()
        submitted = st.form_submit_button(
            "Save Morning Check-In", use_container_width=True, type="primary"
        )

    if submitted:
        repo.get_repository().save_check_in(CheckInRecord(
            date=str(date.today()),
            current_condition=current_condition,
            tightness_score=tightness_score,
            pain_score=pain_score,
            anatomical_locations=anatomical_locations,
            sensation_tags=sensation_tags,
            subjective_tightness=subjective_note,
            alcohol_units=alcohol_units,
            travel_flag=travel_flag,
            psych_stress_score=psych_stress,
        ))
        st.success(
            f"Check-in saved — Tightness {tightness_score}/10, Pain {pain_score}/10. "
            "Head to Training Plan when ready to start your session."
        )

    st.divider()
    with st.expander("Scale Reference — Tightness & Pain", expanded=False):
        col_t, col_p = st.columns(2, gap="large")
        with col_t:
            st.markdown("**Tightness Score (0–10)**")
            for rng, desc in TIGHTNESS_SCALE_GUIDE:
                st.markdown(f"`{rng}` — {desc}")
        with col_p:
            st.markdown("**Pain Score (0–10)**")
            for rng, desc in PAIN_SCALE_GUIDE:
                st.markdown(f"`{rng}` — {desc}")
