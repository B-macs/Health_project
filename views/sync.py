"""
views/sync.py — Biometric Data sync view.
Call render() from the SPA router in app.py.
"""

import streamlit as st
import pandas as pd
from dataclasses import asdict
import repo


@st.cache_data(ttl=1800, show_spinner=False)
def _load_raw(sheet_id: str) -> list[dict]:
    return repo.get_repository().get_raw_sheet_rows()


@st.cache_data(ttl=1800, show_spinner=False)
def _load_engine_view(sheet_id: str) -> list[dict]:
    records = repo.get_repository().get_biometric_rolling(days=28)
    return [asdict(r) for r in records]


def render() -> None:
    st.title("Biometric Data")
    st.caption("Live from Google Sheets · Sheet1 · Auto-read by the engine every 30 min.")

    try:
        sheet_id = st.secrets["GOOGLE_SHEETS_ID"]
    except Exception:
        st.error("GOOGLE_SHEETS_ID missing from .streamlit/secrets.toml")
        return

    if st.button("Refresh", use_container_width=False, key="sync_refresh"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("Reading Sheet1 from Google Sheets…"):
        try:
            rows = _load_raw(sheet_id)
        except Exception as exc:
            st.error(f"Could not read Sheet1: {exc}")
            return

    if not rows:
        st.info("Sheet1 is empty — no data yet.")
        return

    df = pd.DataFrame(rows)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total rows", len(df))
    col2.metric("Earliest",   str(df["Date/Time"].iloc[0])[:10])
    col3.metric("Latest",     str(df["Date/Time"].iloc[-1])[:10])

    st.divider()

    st.subheader("Raw Sheet Data")
    st.dataframe(df, use_container_width=True, height=400)

    st.divider()
    st.subheader("Engine View — Last 28 Days")
    st.caption("After column mapping and kJ → kcal conversion, as passed to the traffic-light engine.")

    engine_rows = _load_engine_view(sheet_id)
    if engine_rows:
        st.dataframe(pd.DataFrame(engine_rows), use_container_width=True)
    else:
        st.info("No rows within the last 28 days.")

    st.divider()
    st.caption(
        "Weekly Rollup and Garmin Daily Metrics both sync automatically once a "
        "week (checked whenever the Training page loads — no button needed)."
    )

    st.divider()
    st.subheader("Garmin")
    r = repo.get_repository()
    if not r.garmin_configured():
        st.info(
            "Add GARMIN_EMAIL and GARMIN_PASSWORD to .streamlit/secrets.toml to enable "
            "Garmin sync. Archival only — does not feed the readiness/ACWR engine, "
            "which keeps reading Sheet1 exactly as it does today."
        )
    else:
        st.caption(
            "Daily wellness metrics and activities are archived to their own Sheet tabs "
            "(Garmin Daily, Garmin Activities) — not read by the readiness/ACWR engine. "
            "Daily Metrics also syncs automatically once a week; use the button below "
            "to run it on demand."
        )

        col_daily, col_activities = st.columns(2, gap="small")
        with col_daily:
            if st.button("Sync Garmin Daily Metrics", use_container_width=True, key="sync_garmin_daily"):
                with st.spinner("Pulling daily metrics from Garmin…"):
                    try:
                        n = r.sync_garmin_daily(days=7)
                        st.success(f"Synced {n} days to the Garmin Daily tab.")
                    except Exception as exc:
                        st.warning(f"Garmin daily sync failed: {exc}")
        with col_activities:
            if st.button("Sync Garmin Activities", use_container_width=True, key="sync_garmin_activities"):
                with st.spinner("Pulling activities from Garmin…"):
                    try:
                        n = r.sync_garmin_activities(limit=20)
                        st.success(f"Synced {n} activities to the Garmin Activities tab.")
                    except Exception as exc:
                        st.warning(f"Garmin activity sync failed: {exc}")

    st.divider()
    st.subheader("Oura")
    if not r.oura_configured():
        st.info(
            "Add OURA_TOKEN to .streamlit/secrets.toml to enable Oura sync. "
            "Archival only — does not feed the readiness/ACWR engine, which "
            "keeps reading Sheet1 exactly as it does today."
        )
    else:
        st.caption(
            "Daily summary scores (sleep, readiness, activity, stress, resilience, "
            "SpO2, cardiovascular age) archive to the Oura Daily tab; workouts, sleep "
            "periods, sessions, and rest-mode periods each get their own tab — not read "
            "by the readiness/ACWR engine. Also syncs automatically 2 hours after the "
            "Home page is opened; use the button below to pull a full week on demand."
        )
        if st.button("Sync Weekly Oura Details", use_container_width=False, key="sync_oura_weekly"):
            with st.spinner("Pulling the last 7 days from Oura…"):
                try:
                    counts = r.sync_oura_all(days=7)
                    st.success(
                        f"Synced {counts['daily']} days, {counts['workouts']} workouts, "
                        f"{counts['sleep_periods']} sleep periods, {counts['sessions']} sessions, "
                        f"{counts['rest_mode_periods']} rest-mode periods."
                    )
                except Exception as exc:
                    st.warning(f"Oura sync failed: {exc}")
