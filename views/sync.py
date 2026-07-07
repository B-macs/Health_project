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
