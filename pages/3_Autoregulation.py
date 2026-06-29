"""
Autoregulation Engine — Background config & status.
The directive surfaces automatically in the Training Plan.
Full metrics (ACWR, biometrics, injury weight) are in AI Insights → Engine Data.
"""

import streamlit as st
from datetime import date
import db
import engine
import sync_sheets
import styles

st.set_page_config(page_title="Autoregulation", layout="wide")
styles.inject_css()


# ─────────────────────────────────────────────────────────────────────────────
#  Cached data fetchers
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800)
def _get_biometrics():
    sheet_id = st.secrets.get("GOOGLE_SHEETS_ID", "")
    return sync_sheets.get_biometric_rolling(sheet_id, days=28) if sheet_id else []

@st.cache_data(ttl=1800)
def _get_au():          return db.get_daily_session_au(28)

@st.cache_data(ttl=1800)
def _get_pain_streak(): return db.get_pain_free_streak()

@st.cache_data(ttl=1800)
def _get_avg_tight():   return db.get_avg_tightness(14)

@st.cache_data(ttl=1800)
def _get_diagnostic():  return db.get_diagnostic_profile()

@st.cache_data(ttl=1800)
def _get_stage():       return db.get_current_stage()


# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar — stage configuration only
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.subheader("Stage")
    st.caption("Change only when physiotherapist confirms progression criteria met.")
    current_stage_db = _get_stage()
    new_stage = st.selectbox(
        "Stage",
        [1, 2, 3],
        index=current_stage_db - 1,
        format_func=lambda s: {1: "1 — Rehab", 2: "2 — Transition", 3: "3 — Performance"}[s],
        label_visibility="collapsed",
    )
    if new_stage != current_stage_db:
        if st.button("Confirm Stage Change", type="primary", use_container_width=True):
            db.set_config("current_stage", str(new_stage))
            st.cache_data.clear()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  Engine computation
# ─────────────────────────────────────────────────────────────────────────────

current_stage  = _get_stage()
biometric_rows = _get_biometrics()
au_rows        = _get_au()
pain_streak    = _get_pain_streak()
avg_tight      = _get_avg_tight()
diagnostic     = _get_diagnostic()
lambda_val     = float(diagnostic.get("injury_weight_decay_lambda") or 0.05)

tl          = engine.traffic_light(biometric_rows)
acwr_result = engine.acwr(au_rows, current_stage)
inj_weight  = engine.injury_weight(lambda_val, pain_streak)
stage_info  = engine.stage_status(current_stage, pain_streak, avg_tight)
obs_rem     = engine.observation_days_remaining(tl["data_days"])

rec = engine.volume_recommendation(
    tl, acwr_result, current_stage, obs_rem, injury_weight_val=inj_weight,
)
stage_advance = engine.check_auto_stage_advance(current_stage, pain_streak, avg_tight)


# ─────────────────────────────────────────────────────────────────────────────
#  Page
# ─────────────────────────────────────────────────────────────────────────────

st.title("Autoregulation")
st.caption(f"{date.today().strftime('%A, %d %B %Y')} · Stage {current_stage} · {pain_streak} pain-free days")

# Stage advance notification
if stage_advance["should_advance"]:
    st.warning(
        f"**Stage {stage_advance['current_stage']} criteria met** — "
        f"ready to advance to Stage {stage_advance['next_stage']}. "
        f"{stage_advance['criteria_summary']}. "
        "Confirm with your physiotherapist, then update the stage in the sidebar."
    )
    if st.button(f"Advance to Stage {stage_advance['next_stage']}", type="primary"):
        db.set_config("current_stage", str(stage_advance["next_stage"]))
        st.cache_data.clear()
        st.rerun()

st.divider()

# ── Today's directive — plain language, no raw data ───────────────────────────
sig = rec["signal_color"]

_LABELS = {
    "green":  "Train normally today.",
    "yellow": "Reduced load today — keep the session controlled, don't push to failure.",
    "orange": "Reduced load today — keep the session controlled, don't push to failure.",
    "red":    "Rest day — mobility and walking only. No loaded training.",
    "grey":   "Building baseline — train at comfortable effort.",
}
_DETAIL = {
    "green":  rec["action"],
    "yellow": "Biometrics are slightly below your rolling average. Scale back total volume by around 20–25%. Hold intensity — just do fewer sets.",
    "orange": "Biometrics are slightly below your rolling average. Scale back total volume by around 20–25%. Hold intensity — just do fewer sets.",
    "red":    "Biometrics show significant systemic fatigue. Rest is the training stimulus today.",
    "grey":   rec["action"],
}

label  = _LABELS.get(sig, rec["label"])
detail = _DETAIL.get(sig, rec["action"])

if sig == "red":
    st.error(f"**{label}**\n\n{detail}")
elif sig in ("yellow", "orange"):
    st.warning(f"**{label}**\n\n{detail}")
elif sig == "green":
    st.success(f"**{label}**\n\n{detail}")
else:
    st.info(f"**{label}**\n\n{detail}")

st.divider()

# Stage progression summary — no raw metrics, just plain status
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
st.caption(
    "Full engine metrics — ACWR chart, biometric traffic light, "
    "injury weight decay, workload trend — are in **AI Insights → Engine Data**."
)
