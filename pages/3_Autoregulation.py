"""
Autoregulation Engine — Daily training directive.
Traffic Light × ACWR × Stage → single output: what to do today and why.
"""

import streamlit as st
import pandas as pd
from datetime import date
import db
import engine
import rules

st.set_page_config(page_title="Autoregulation", layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers — rendering only; all colour constants imported from engine.py
# ─────────────────────────────────────────────────────────────────────────────

def _badge(text: str, color: str, size: str = "14px") -> str:
    bg = engine.SIGNAL_COLORS.get(color, engine.SIGNAL_COLORS["grey"])
    fg = "#0E1117" if color in ("green", "yellow") else "#FFFFFF"
    return (
        f'<span style="background:{bg}; color:{fg}; padding:4px 12px; '
        f'border-radius:6px; font-family:monospace; font-weight:700; '
        f'font-size:{size};">{text}</span>'
    )


def _rec_banner(rec: dict) -> None:
    color = rec["signal_color"]
    bg    = engine.SIGNAL_COLORS.get(color, engine.SIGNAL_COLORS["grey"])
    fg    = "#0E1117" if color in ("green", "yellow") else "#FFFFFF"
    mult  = rec["multiplier"]
    mult_str = f"{int(mult * 100)}% volume" if mult > 0 else "NO loaded training"
    st.markdown(
        f"""
        <div style="background:{bg}; color:{fg}; border-radius:12px;
                    padding:20px 28px; margin-bottom:16px;">
            <div style="font-size:22px; font-weight:700; font-family:monospace;
                        letter-spacing:1px; margin-bottom:6px;">
                {rec['label']}
            </div>
            <div style="font-size:13px; opacity:0.9; line-height:1.5;">
                {rec['action']}
            </div>
            <div style="font-size:12px; margin-top:10px; opacity:0.75;">
                Volume multiplier: <strong>{mult_str}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(label, value, unit, baseline, delta_pct, signal) -> None:
    icon  = engine.SIGNAL_ICONS.get(signal, "⚫")
    color = engine.SIGNAL_COLORS.get(signal, engine.SIGNAL_COLORS["grey"])
    val_str = f"{value} {unit}" if value is not None else "—"
    base_str = f"28d avg: {baseline} {unit}" if baseline else "No baseline"
    delta_str = (
        f"{'▲' if delta_pct > 0 else '▼'} {abs(delta_pct):.1f}%"
        if delta_pct is not None else ""
    )
    st.markdown(
        f"""
        <div style="background:#1A1F2E; border-left:4px solid {color};
                    border-radius:8px; padding:14px 16px;">
            <div style="font-size:11px; color:#888; font-family:monospace;
                        text-transform:uppercase; letter-spacing:1px;">
                {label} {icon}
            </div>
            <div style="font-size:28px; font-weight:700; font-family:monospace;
                        color:#E8EAF0; margin:4px 0;">
                {val_str}
            </div>
            <div style="font-size:11px; color:#888;">{base_str}</div>
            <div style="font-size:12px; color:{color}; font-weight:600;">
                {delta_str}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Sidebar — Manual Biometric Entry
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Biometric Entry")
    st.caption("Enter this morning's metrics from Apple Health or your watch.")

    with st.form("biometrics_entry", clear_on_submit=True):
        entry_date = st.date_input("Date", value=date.today())
        hrv    = st.number_input("HRV (ms)",          min_value=0.0,  max_value=300.0, value=0.0,  step=0.1)
        rhr    = st.number_input("RHR (bpm)",          min_value=0,    max_value=220,   value=0,    step=1)
        sleep  = st.number_input("Sleep (hours)",      min_value=0.0,  max_value=16.0,  value=0.0,  step=0.25)
        deep   = st.number_input("Deep Sleep (hours)", min_value=0.0,  max_value=6.0,   value=0.0,  step=0.25)
        kcal   = st.number_input("Active Energy (kcal)", min_value=0, max_value=6000,   value=0,    step=10)
        weight = st.number_input("Weight (kg)",        min_value=0.0,  max_value=250.0, value=0.0,  step=0.1)
        steps  = st.number_input("Steps",              min_value=0,    max_value=100000,value=0,    step=100)

        save_bio = st.form_submit_button("Save Biometrics", use_container_width=True, type="primary")

    if save_bio:
        db.save_biometrics_today(
            date_str    = str(entry_date),
            rhr         = rhr   or None,
            hrv         = hrv   or None,
            sleep_hours = sleep or None,
            sleep_deep  = deep  or None,
            active_kcal = kcal  or None,
            weight_kg   = weight or None,
            steps       = steps or None,
        )
        st.success("Saved.")
        st.rerun()

    st.divider()
    st.subheader("Stage Override")
    current_stage_db = db.get_current_stage()
    new_stage = st.selectbox(
        "Current Stage",
        [1, 2, 3],
        index=current_stage_db - 1,
        format_func=lambda s: {1: "1 — Rehab", 2: "2 — Transition", 3: "3 — Performance"}[s],
    )
    if new_stage != current_stage_db:
        if st.button("Confirm Stage Change", type="primary"):
            db.set_config("current_stage", str(new_stage))
            st.success(f"Stage updated to {new_stage}.")
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  Fetch data & run engine
# ─────────────────────────────────────────────────────────────────────────────

current_stage    = db.get_current_stage()
biometric_rows   = db.get_biometric_rolling(28)
au_rows          = db.get_daily_session_au(28)
pain_streak      = db.get_pain_free_streak()
avg_tight        = db.get_avg_tightness(14)
diagnostic       = db.get_diagnostic_profile()
# Lambda sourced from DB diagnostic profile, not hardcoded
lambda_val       = float(diagnostic.get("injury_weight_decay_lambda") or 0.05)

tl          = engine.traffic_light(biometric_rows)
acwr_result = engine.acwr(au_rows, current_stage)
inj_weight  = engine.injury_weight(lambda_val, pain_streak)
stage_info  = engine.stage_status(current_stage, pain_streak, avg_tight)

# Observation mode uses engine constant — not a magic number in the page
obs_days_remaining = engine.observation_days_remaining(tl["data_days"])

# injury_weight_val now feeds into the recommendation — not just displayed
rec = engine.volume_recommendation(
    tl, acwr_result, current_stage, obs_days_remaining,
    injury_weight_val=inj_weight,
)

# Automatic stage advance check (deterministic — does NOT write to DB itself)
stage_advance = engine.check_auto_stage_advance(current_stage, pain_streak, avg_tight)


# ─────────────────────────────────────────────────────────────────────────────
#  Header bar
# ─────────────────────────────────────────────────────────────────────────────

st.title("Autoregulation Engine")
st.caption(f"{date.today().strftime('%A, %d %B %Y')}")

# ── Auto stage-advance notification (deterministic criteria met) ──────────────
if stage_advance["should_advance"]:
    st.warning(
        f"**Stage {stage_advance['current_stage']} criteria met** — "
        f"ready to advance to Stage {stage_advance['next_stage']}. "
        f"{stage_advance['criteria_summary']}. "
        f"Confirm with your physiotherapist, then click below."
    )
    if st.button(
        f"Advance to Stage {stage_advance['next_stage']}",
        type="primary",
        key="stage_advance_btn",
    ):
        db.set_config("current_stage", str(stage_advance["next_stage"]))
        st.success(f"Stage updated to {stage_advance['next_stage']}. Page will refresh.")
        st.rerun()

col_stage, col_streak, col_weight, col_acwr = st.columns(4)
col_stage.metric("Current Stage",    stage_info["stage_label"].split(" — ")[0].strip())
col_streak.metric("Pain-Free Streak", f"{pain_streak} days")
col_weight.metric("Injury Weight",    f"{int(inj_weight * 100)}%",
                  help="e^(-lambda*t): decays toward 0% as pain-free days accumulate.")
acwr_val = acwr_result.get("acwr")
col_acwr.metric(
    "ACWR",
    f"{acwr_val:.2f}" if acwr_val else "—",
    delta=f"Ceiling: {acwr_result['ceiling']}",
    delta_color="off",
)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  Today's Recommendation — the primary output
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Today's Directive")
_rec_banner(rec)

# ── Specific target calculator ────────────────────────────────────────────────
# Lets the user enter their planned movement and get exact adjusted targets.
with st.expander("Calculate specific targets for a movement", expanded=False):
    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
    t_sets   = col_t1.number_input("Planned sets",    min_value=1, max_value=20,  value=3,    key="t_sets")
    t_reps   = col_t2.number_input("Planned reps",    min_value=1, max_value=100, value=10,   key="t_reps")
    t_weight = col_t3.number_input("Planned weight (kg)", min_value=0.0, max_value=500.0, value=0.0, step=0.5, key="t_weight")

    targets = engine.apply_volume_recommendation(
        planned_sets=int(t_sets),
        planned_reps=int(t_reps),
        planned_weight_kg=float(t_weight),
        rec=rec,
        stage=current_stage,
    )

    col_r1, col_r2, col_r3 = st.columns(3)
    col_r1.metric("Adjusted Sets",   targets["sets"])
    col_r2.metric("Adjusted Reps",   targets["reps"])
    col_r3.metric("Adjusted Weight", f"{targets['weight_kg']} kg")
    st.caption(targets["note"])

# ─────────────────────────────────────────────────────────────────────────────
#  Biometric Traffic Light
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Biometric Traffic Light")

if tl["status"] == "insufficient_data":
    st.info(tl["message"])
else:
    overall_icon  = engine.SIGNAL_ICONS.get(tl["overall"], "⚫")
    overall_color = engine.SIGNAL_COLORS.get(tl["overall"], engine.SIGNAL_COLORS["grey"])
    st.markdown(
        f"Overall signal: {overall_icon} "
        + f'<span style="color:{overall_color}; font-weight:700;">'
        + tl["overall"].upper() + "</span> — " + tl["message"],
        unsafe_allow_html=True,
    )
    st.write("")

    c_hrv, c_rhr, c_sleep = st.columns(3)
    metrics = tl.get("metrics", {})

    with c_hrv:
        m = metrics.get("hrv_ms", {})
        _metric_card("HRV", m.get("value"), "ms", m.get("baseline_28d"), m.get("delta_pct"), m.get("signal", "grey"))

    with c_rhr:
        m = metrics.get("resting_heart_rate", {})
        _metric_card("RHR", m.get("value"), "bpm", m.get("baseline_28d"), m.get("delta_pct"), m.get("signal", "grey"))

    with c_sleep:
        m = metrics.get("sleep_duration_hours", {})
        _metric_card("Sleep", m.get("value"), "h", m.get("baseline_28d"), m.get("delta_pct"), m.get("signal", "grey"))

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  ACWR Panel
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Workload Ratio (ACWR)")

col_acwr_vals, col_acwr_chart = st.columns([1, 2], gap="large")

with col_acwr_vals:
    status_color = engine.ACWR_STATUS_COLORS.get(acwr_result["status"], "grey")

    st.markdown(
        _badge(acwr_result["status"].replace("_", " ").upper(), status_color, "13px"),
        unsafe_allow_html=True,
    )
    st.write("")
    st.metric("ACWR",          f"{acwr_val:.3f}" if acwr_val else "—")
    st.metric("Acute (7d avg AU)",   f"{acwr_result['acute_avg']}")
    st.metric("Chronic (28d avg AU)", f"{acwr_result['chronic_avg']}")
    st.metric("Stage ceiling",  acwr_result["ceiling"])

    if acwr_result["hard_locked"]:
        st.error("Hard lock active — do not increase volume this week.")

with col_acwr_chart:
    daily_au = acwr_result.get("daily_au_28", [0.0] * 28)
    today_dt = date.today()
    chart_dates = [
        (today_dt - __import__("datetime").timedelta(days=27 - i)).strftime("%b %d")
        for i in range(28)
    ]
    df_au = pd.DataFrame({
        "Date":  chart_dates,
        "AU":    daily_au,
        "Window": ["Chronic (28d)"] * 21 + ["Acute (7d)"] * 7,
    })
    # Colour the acute window differently using two separate series
    df_chronic = df_au[df_au["Window"] == "Chronic (28d)"].set_index("Date")["AU"]
    df_acute   = df_au[df_au["Window"] == "Acute (7d)"].set_index("Date")["AU"]
    df_chart   = pd.concat([df_chronic.rename("Chronic 28d"), df_acute.rename("Acute 7d")], axis=1)
    st.caption("Daily session AU — last 28 days (acute window highlighted)")
    st.bar_chart(df_chart, color=["#3D4F6B", "#00D4AA"])

    if acwr_val:
        ceiling_line = acwr_result["ceiling"] * acwr_result["chronic_avg"]
        st.caption(
            f"ACWR ceiling threshold at current chronic load = "
            f"**{ceiling_line:.0f} AU/day** acute average. "
            f"7-day acute average is currently **{acwr_result['acute_avg']} AU/day**."
        )

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
#  Stage Progression
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("Stage Progression")

col_s1, col_s2 = st.columns([2, 1], gap="large")

with col_s1:
    st.markdown(f"**{stage_info['stage_label']}**")
    st.caption(stage_info["message"])

    if stage_info.get("progress_days") and stage_info["progress_days"] != "—":
        st.markdown(f"Pain-free days: `{stage_info['progress_days']}`")
        st.progress(stage_info["days_progress_pct"])

    if stage_info.get("progress_tightness") and stage_info["progress_tightness"] != "—":
        st.markdown(f"Tightness target: `{stage_info['progress_tightness']}`")
        st.progress(stage_info["tight_progress_pct"])

    if stage_info["advance_ready"]:
        st.success(
            f"Criteria met for Stage {stage_info['next_stage']}. "
            "Confirm with physiotherapist, then update stage in the sidebar."
        )

with col_s2:
    st.markdown("**Injury Baseline Weight**")
    inj_signal = engine.injury_weight_signal(inj_weight)
    st.markdown(
        f"<div style='font-size:42px; font-weight:700; font-family:monospace; "
        f"color:{engine.SIGNAL_COLORS[inj_signal]};'>"
        f"{int(inj_weight * 100)}%</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"λ = {lambda_val} | {pain_streak} pain-free days  \n"
        "Decays toward 0% as pain-free training accumulates. "
        "At <5% the injury data becomes a silent background watcher only."
    )
    st.progress(inj_weight)
