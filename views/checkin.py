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
# (range_label, tier_title, description) and renders as one line in the
# reference guide.
TIGHTNESS_SCALE_TITLE = "Muscle Tightness Scale"
TIGHTNESS_SCALE_SUBTITLE = "Rate the level of restriction, stiffness, or resistance in your muscles."
TIGHTNESS_SCALE_GUIDE = [
    ("0",    "No Tightness",                  "Full, unrestricted range of motion."),
    ("1–2",  "Minimal / Normal",               "Barely noticeable. Muscles feel supple, warm, and ready to move."),
    ("3–4",  "Mild Tension",                   "Slight stiffness or light DOMS (Delayed Onset Muscle Soreness). "
                                                "You feel it, but it easily \"unlocks\" with a light warm-up or stretch."),
    ("5–6",  "Moderate Stiffness / Deep DOMS", "Pronounced tightness and heavy muscle soreness. Movement is "
                                                "restricted, and stretching feels highly intense but manageable."),
    ("7–8",  "Severe Tightness",               "Muscles feel highly contracted and guarded. Movement is "
                                                "uncomfortable, and attempting to stretch feels like hitting a "
                                                "hard, painful wall."),
    ("9–10", "Extreme Restriction",            "Muscle feels completely locked up or \"seized.\" Movement is "
                                                "severely restricted; trying to stretch feels like you might "
                                                "strain or tear the muscle."),
]

PAIN_SCALE_TITLE = "Pain Scale"
PAIN_SCALE_SUBTITLE = "Rate actual discomfort or pain (which is different from typical muscular fatigue or soreness)."
PAIN_SCALE_GUIDE = [
    ("0",    "Pain-Free",     "No discomfort at all."),
    ("1–2",  "Faint",         "A mild, passing ache or twinge. Only noticeable when you actively "
                               "think about it or press on the area."),
    ("3–4",  "Mild / Distracting", "A constant dull ache or sharp pinch during certain movements, but "
                                    "it doesn't stop you from completing daily tasks."),
    ("5–6",  "Moderate / Limiting", "Clear pain that causes you to alter your movement, compromise your "
                                     "form, or compensate to avoid discomfort."),
    ("7–8",  "Severe",         "Intense, sharp, or throbbing pain. Strongly interferes with normal "
                                "movement and requires you to stop or significantly modify training."),
    ("9–10", "Debilitating",   "Excruciating pain that makes any movement impossible. Requires "
                                "immediate rest or medical attention."),
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
                help=(
                    "Combined scale — emotional load and mental clarity together, "
                    "deliberately one metric rather than two overlapping ones.\n\n"
                    "**1 — Calm & Clear**: Relaxed, minimal stress, sharp focus, "
                    "thinking feels easy.\n\n"
                    "**2 — Mostly Calm**: Slight background stress or occasional "
                    "distraction, still generally clear-headed.\n\n"
                    "**3 — Moderate**: Noticeable stress or mental fog, focus takes "
                    "more effort than usual.\n\n"
                    "**4 — High**: Elevated stress, clarity noticeably reduced, "
                    "harder to concentrate, on edge.\n\n"
                    "**5 — Very High**: Significant stress or emotional load, "
                    "foggy/scattered thinking, hard to focus on simple tasks."
                ),
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
        col_joint_gut, col_body_hydration, col_meditation = st.columns(3, gap="large")

        with col_joint_gut:
            st.subheader("Joint / Gut")
            instability_events = st.number_input(
                "Instability Events", min_value=0, max_value=20, value=0, step=1,
                help="Count of joint subluxation/instability events since yesterday (HSD).",
                key="checkin_instability",
            )
            bristol_type = st.select_slider(
                "Bristol Stool Type", options=[1, 2, 3, 4, 5, 6, 7], value=4,
                help="1 = severe constipation, 7 = watery/diarrhea. 3–4 = normal.",
                key="checkin_bristol",
            )
            unusual_stool_colour = st.toggle(
                "Unusual Colour?", key="checkin_stool_colour",
            )

        with col_body_hydration:
            st.subheader("Body / Hydration")
            hunger_deviation = st.select_slider(
                "Hunger vs Baseline", options=[-2, -1, 0, 1, 2], value=0,
                help="−2 = far below normal appetite, +2 = far above normal appetite.",
                key="checkin_hunger",
            )
            thirst_intensity = st.select_slider(
                "Morning Thirst Intensity", options=[1, 2, 3, 4, 5], value=1,
                key="checkin_thirst",
            )
            electrolytes_taken = st.toggle(
                "Salt/Electrolytes Taken", key="checkin_electrolytes",
            )

        with col_meditation:
            st.subheader("Meditation")
            meditation_minutes = st.number_input(
                "Meditation Minutes", min_value=0.0, max_value=120.0,
                value=0.0, step=5.0,
                help="Practice Done is inferred automatically — any minutes logged counts as done.",
                key="checkin_meditation_minutes",
            )
            relaxation_depth = st.select_slider(
                "Relaxation Depth", options=[1, 2, 3, 4, 5], value=1,
                help="1 = restless/distracted, 5 = deeply relaxed. Only meaningful if practice was done.",
                key="checkin_relaxation",
            )

        st.divider()
        submitted = st.form_submit_button(
            "Save Morning Check-In", use_container_width=True, type="primary"
        )

    if submitted:
        # No explicit "Practice Done" toggle — inferred from minutes logged.
        meditation_done = meditation_minutes > 0
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
            instability_events=instability_events,
            bristol_type=bristol_type,
            unusual_stool_colour=unusual_stool_colour,
            hunger_deviation=hunger_deviation,
            thirst_intensity=thirst_intensity,
            electrolytes_taken=electrolytes_taken,
            meditation_done=meditation_done,
            meditation_minutes=meditation_minutes,
            relaxation_depth=relaxation_depth,
        ))
        # Readiness (Home page) reads today's alcohol units via cached
        # get_biometric_rolling() — clear so it recomputes with this
        # check-in's value instead of serving a stale pre-checkin score.
        st.cache_data.clear()
        st.success(
            f"Check-in saved — Tightness {tightness_score}/10, Pain {pain_score}/10. "
            "Head to Training Plan when ready to start your session."
        )

    st.divider()
    with st.expander("Scale Reference — Tightness & Pain", expanded=False):
        col_t, col_p = st.columns(2, gap="large")
        with col_t:
            st.markdown(f"**{TIGHTNESS_SCALE_TITLE}**")
            st.caption(TIGHTNESS_SCALE_SUBTITLE)
            for rng, title, desc in TIGHTNESS_SCALE_GUIDE:
                st.markdown(f"`{rng}` **{title}** — {desc}")
        with col_p:
            st.markdown(f"**{PAIN_SCALE_TITLE}**")
            st.caption(PAIN_SCALE_SUBTITLE)
            for rng, title, desc in PAIN_SCALE_GUIDE:
                st.markdown(f"`{rng}` **{title}** — {desc}")
