"""
Data Grid — Historical view across all three data streams.
High-density AG Grid tables for readiness, training sessions, and biometrics.
"""

import json
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import db

st.set_page_config(page_title="Data Grid", layout="wide")
st.title("Data Grid")

DAYS = st.sidebar.selectbox("History window", [14, 30, 60, 90, 180], index=1)
st.sidebar.caption(f"Showing last {DAYS} days of data.")

tab_readiness, tab_training, tab_biometrics = st.tabs([
    "Daily Readiness", "Training Sessions", "Biometrics"
])


def _aggrid(df, height=400):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        filter=True,
        sortable=True,
        resizable=True,
        wrapText=False,
    )
    gb.configure_grid_options(
        rowHeight=28,
        headerHeight=32,
        suppressMovableColumns=False,
    )
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=25)
    AgGrid(
        df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.NO_UPDATE,
        use_container_width=True,
        theme="alpine",
        height=height,
        allow_unsafe_jscode=False,
    )


# ── Daily Readiness ───────────────────────────────────────────────────────────

with tab_readiness:
    data = db.get_recent_readiness(DAYS)
    if not data:
        st.info("No readiness data yet. Complete your first Morning Check-In.")
    else:
        df = pd.DataFrame(data)
        # Decode JSON tag columns for display
        for col in ("anatomical_locations", "sensation_tags"):
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda v: ", ".join(json.loads(v)) if v else ""
                )
        df["travel"] = df["travel_flag"].map({0: "", 1: "Yes"})
        df = df.drop(columns=["travel_flag"], errors="ignore")
        df = df.rename(columns={
            "date": "Date",
            "current_condition": "Readiness",
            "tightness_score": "Tightness",
            "pain_score": "Pain",
            "anatomical_locations": "Locations",
            "sensation_tags": "Sensations",
            "subjective_tightness": "Note",
            "alcohol_units": "Alcohol",
            "travel": "Travel",
            "psych_stress_score": "Stress",
        })
        st.metric("Entries", len(df))
        _aggrid(df, height=500)


# ── Training Sessions ─────────────────────────────────────────────────────────

with tab_training:
    data = db.get_recent_sessions(DAYS)
    if not data:
        st.info("No training sessions logged yet. Head to Training Entry to log your first session.")
    else:
        df = pd.DataFrame(data)
        df = df.rename(columns={
            "session_date": "Date",
            "session_duration_minutes": "Duration (min)",
            "session_rpe": "Session RPE",
            "session_au": "AU",
            "movement_name": "Exercise",
            "movement_type": "Type",
            "planned_sets": "Planned Sets",
            "planned_reps": "Planned Reps",
            "exercise_rpe": "Ex RPE",
            "actual_sets": "Actual Sets",
            "total_volume_kg": "Volume (kg)",
        })

        col1, col2, col3 = st.columns(3)
        col1.metric("Sessions", df["Date"].nunique())
        col2.metric("Total AU", f"{df['AU'].sum():.0f}" if "AU" in df else "—")
        col3.metric("Exercises logged", len(df))

        _aggrid(df, height=500)


# ── Biometrics ────────────────────────────────────────────────────────────────

with tab_biometrics:
    data = db.get_biometrics(DAYS)
    if not data:
        st.info("No biometric data yet. Apple Health sync will be wired up in a future bucket.")
        st.caption(
            "Manual entry: you can insert rows directly into the `daily_biometrics` table "
            "using any SQLite browser (e.g. DB Browser for SQLite) until Apple Health import is built."
        )
    else:
        df = pd.DataFrame(data)
        df = df.rename(columns={
            "date": "Date",
            "resting_heart_rate": "RHR",
            "heart_rate_avg": "HR Avg",
            "hrv_ms": "HRV (ms)",
            "sleep_duration_hours": "Sleep (h)",
            "sleep_deep_hours": "Deep Sleep (h)",
            "active_energy_kcal": "Active kcal",
            "weight_kg": "Weight (kg)",
            "steps": "Steps",
        })
        _aggrid(df, height=500)
