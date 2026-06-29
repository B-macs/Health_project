"""
Sync — Biometric data status.
Shows what Google Sheets is currently feeding into the Autoregulation engine.
No manual sync needed — the engine reads directly from Sheet1.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sync_sheets
import styles

st.set_page_config(page_title="Biometric Data", layout="wide")
styles.inject_css()

st.title("Biometric Data")
st.caption("Live from Google Sheets · Sheet1 · Auto-read by the Autoregulation engine every 30 min.")

try:
    sheet_id = st.secrets["GOOGLE_SHEETS_ID"]
except Exception:
    st.error("GOOGLE_SHEETS_ID missing from .streamlit/secrets.toml")
    st.stop()

# ── Single cached fetch — both views derive from this ─────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _load(sid: str) -> list[dict]:
    return sync_sheets.fetch_all_rows(sid)

if st.button("Refresh", use_container_width=False):
    st.cache_data.clear()
    st.rerun()

with st.spinner("Reading Sheet1 from Google Sheets…"):
    try:
        rows = _load(sheet_id)
    except Exception as exc:
        st.error(f"Could not read Sheet1: {exc}")
        st.stop()

if not rows:
    st.info("Sheet1 is empty — no data yet.")
    st.stop()

df = pd.DataFrame(rows)

# ── Summary strip ──────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
col1.metric("Total rows", len(df))
col2.metric("Earliest",   str(df["Date/Time"].iloc[0])[:10])
col3.metric("Latest",     str(df["Date/Time"].iloc[-1])[:10])

st.divider()

# ── Raw sheet ─────────────────────────────────────────────────────────────────
st.subheader("Raw Sheet Data")
st.dataframe(df, use_container_width=True, height=400)

# ── Engine view — derive from the already-fetched rows, no second API call ────
st.divider()
st.subheader("Engine View — Last 28 Days")
st.caption("After column mapping and kJ → kcal conversion, as passed to the traffic-light engine.")

cutoff = (date.today() - timedelta(days=28)).isoformat()
today_str = str(date.today())

engine_rows = []
for row in rows:
    d = str(row.get("Date/Time", "")).split(" ")[0].strip()
    if d and cutoff <= d <= today_str:
        try:
            kj = float(row.get("Active Energy (kJ)") or 0)
            engine_rows.append({
                "date":                 d,
                "hrv_ms":               float(row["Heart Rate Variability (ms)"]) if row.get("Heart Rate Variability (ms)") else None,
                "resting_heart_rate":   int(float(row["Resting Heart Rate (count/min)"])) if row.get("Resting Heart Rate (count/min)") else None,
                "sleep_hours":          float(row["Sleep Analysis [Total] (hr)"]) if row.get("Sleep Analysis [Total] (hr)") else None,
                "sleep_deep_hours":     float(row["Sleep Analysis [Deep] (hr)"]) if row.get("Sleep Analysis [Deep] (hr)") else None,
                "active_kcal":          round(kj / 4.184) if kj else None,
                "weight_kg":            float(row["Weight (kg)"]) if row.get("Weight (kg)") else None,
                "steps":                int(float(row["Step Count (count)"])) if row.get("Step Count (count)") else None,
            })
        except Exception:
            pass

if engine_rows:
    st.dataframe(pd.DataFrame(engine_rows), use_container_width=True)
else:
    st.info("No rows within the last 28 days.")
