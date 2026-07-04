"""
Insights view — Training Directive + Engine Data + Processing Queue +
Tightness Map + Macro Trends + MRI Intelligence.

Usage:
    from views.insights import render
    render()

Caller is responsible for st.set_page_config(), styles.inject_css(), nav.inject().
"""

import json
import datetime as _dt
from datetime import date

import streamlit as st
import pandas as pd

import db
import ai
import engine
import sync_sheets
import stats as stats_mod


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level cached data fetchers  (must live outside render() so that
#  Streamlit recognises them as stable across reruns)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _bio():
    sheet_id = st.secrets.get("GOOGLE_SHEETS_ID", "")
    return sync_sheets.get_biometric_rolling(sheet_id, 28) if sheet_id else []

@st.cache_data(ttl=1800, show_spinner=False)
def _au():          return db.get_daily_session_au(28)

@st.cache_data(ttl=1800, show_spinner=False)
def _streak():      return db.get_pain_free_streak()

@st.cache_data(ttl=1800, show_spinner=False)
def _tight():       return db.get_avg_tightness(14)

@st.cache_data(ttl=1800, show_spinner=False)
def _diag():        return db.get_diagnostic_profile()

@st.cache_data(ttl=1800, show_spinner=False)
def _stage():       return db.get_current_stage()


# ─────────────────────────────────────────────────────────────────────────────
#  render()
# ─────────────────────────────────────────────────────────────────────────────

def render() -> None:
    st.title("Insights")
    st.caption("Engine metrics, biometric trends, session pattern analysis.")

    injury_profile = db.get_diagnostic_profile()

    (
        tab_directive, tab_engine, tab_queue,
        tab_tightness, tab_trends, tab_mri,
    ) = st.tabs([
        "Training Directive",
        "Engine Data",
        "Processing Queue",
        "Tightness Map",
        "Macro Trends",
        "MRI Intelligence",
    ])

    # =========================================================================
    #  Tab 0 — Training Directive
    # =========================================================================

    with tab_directive:
        st.caption(f"{date.today().strftime('%A, %d %B %Y')}")

        with st.spinner("Loading…"):
            bio_rows      = _bio()
            au_rows       = _au()
            pain_streak   = _streak()
            avg_tight     = _tight()
            diagnostic    = _diag()
            current_stage = _stage()
            lambda_val    = float(diagnostic.get("injury_weight_decay_lambda") or 0.05)

            tl            = engine.traffic_light(bio_rows)
            acwr_result   = engine.acwr(au_rows, current_stage)
            inj_weight    = engine.injury_weight(lambda_val, pain_streak)
            stage_info    = engine.stage_status(current_stage, pain_streak, avg_tight)
            obs_rem       = engine.observation_days_remaining(tl["data_days"])
            rec           = engine.volume_recommendation(
                tl, acwr_result, current_stage, obs_rem, inj_weight,
            )
            stage_advance = engine.check_auto_stage_advance(current_stage, pain_streak, avg_tight)

        # Stage advance notification
        if stage_advance["should_advance"]:
            st.warning(
                f"**Stage {stage_advance['current_stage']} criteria met** — "
                f"ready to advance to Stage {stage_advance['next_stage']}. "
                f"{stage_advance['criteria_summary']}. "
                "Confirm with your physiotherapist, then update the stage below."
            )
            if st.button(
                f"Advance to Stage {stage_advance['next_stage']}",
                type="primary",
                key="directive_advance_btn",
            ):
                db.set_config("current_stage", str(stage_advance["next_stage"]))
                st.cache_data.clear()
                st.rerun()

        st.divider()

        # ── Today's directive — plain language, no raw data ───────────────────
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
            "yellow": (
                "Biometrics are slightly below your rolling average. "
                "Scale back total volume by around 20–25%. "
                "Hold intensity — just do fewer sets."
            ),
            "orange": (
                "Biometrics are slightly below your rolling average. "
                "Scale back total volume by around 20–25%. "
                "Hold intensity — just do fewer sets."
            ),
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

        # ── Stage progression summary ─────────────────────────────────────────
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

        # ── Inline stage change control ───────────────────────────────────────
        st.subheader("Change Stage")
        st.caption("Change only when physiotherapist confirms progression criteria met.")

        new_stage = st.selectbox(
            "Stage",
            [1, 2, 3],
            index=current_stage - 1,
            format_func=lambda s: {
                1: "1 — Rehab",
                2: "2 — Transition",
                3: "3 — Performance",
            }[s],
            key="directive_stage_select",
        )
        if new_stage != current_stage:
            if st.button(
                "Confirm Stage Change",
                type="primary",
                key="directive_stage_confirm",
            ):
                db.set_config("current_stage", str(new_stage))
                st.cache_data.clear()
                st.rerun()

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
            diagnostic    = _diag()
            current_stage = _stage()
            lambda_val    = float(diagnostic.get("injury_weight_decay_lambda") or 0.05)

            tl          = engine.traffic_light(bio_rows)
            acwr_result = engine.acwr(au_rows, current_stage)
            inj_weight  = engine.injury_weight(lambda_val, pain_streak)
            obs_rem     = engine.observation_days_remaining(tl["data_days"])
            rec         = engine.volume_recommendation(tl, acwr_result, current_stage, obs_rem, inj_weight)
            inj_signal  = engine.injury_weight_signal(inj_weight)

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

        # ── Key metrics strip ─────────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Stage",         f"Stage {current_stage}")
        col2.metric("Pain-Free",     f"{pain_streak} days")
        col3.metric("Injury Weight", f"{int(inj_weight * 100)}%",
                    help="e^(-λt) — decays toward 0% as pain-free days accumulate")
        acwr_val = acwr_result.get("acwr")
        col4.metric("ACWR",          f"{acwr_val:.2f}" if acwr_val else "—",
                    delta=f"ceiling {acwr_result['ceiling']}",
                    delta_color="off")

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
                delta_str = (f"{'▲' if delta > 0 else '▼'} {abs(delta):.1f}%" if delta else "")
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
            daily_au   = acwr_result.get("daily_au_28", [0.0] * 28)
            today_dt   = date.today()
            chart_dates = [
                (today_dt - _dt.timedelta(days=27 - i)).strftime("%Y-%m-%d")
                for i in range(28)
            ]
            df_au = pd.DataFrame({
                "Date":   chart_dates,
                "AU":     daily_au,
                "Window": ["Chronic (28d)"] * 21 + ["Acute (7d)"] * 7,
            })
            df_c = df_au[df_au["Window"] == "Chronic (28d)"].set_index("Date")["AU"]
            df_a = df_au[df_au["Window"] == "Acute (7d)"].set_index("Date")["AU"]
            st.caption("Daily session AU — last 28 days")
            st.bar_chart(
                pd.concat([df_c.rename("Chronic 28d"), df_a.rename("Acute 7d")], axis=1),
                color=["#3D4F6B", "#00E874"],
            )

        st.divider()

        # ── Injury weight ─────────────────────────────────────────────────────
        st.subheader("Injury Baseline Weight")
        inj_color = engine.SIGNAL_COLORS[inj_signal]
        col_iw, col_iw_desc = st.columns([1, 3], gap="large")
        with col_iw:
            st.markdown(
                f"<div style='font-size:48px;font-weight:700;font-family:monospace;"
                f"color:{inj_color};'>{int(inj_weight * 100)}%</div>",
                unsafe_allow_html=True,
            )
            st.progress(inj_weight)
        with col_iw_desc:
            st.caption(
                f"λ = {lambda_val} · {pain_streak} pain-free days\n\n"
                "Exponential decay e^(−λt): starts at 100% on injury day, "
                "approaches 0% as pain-free training accumulates. "
                "Below 20% the injury data becomes a silent background watcher only."
            )

    # =========================================================================
    #  Tab 2 — Processing Queue
    # =========================================================================

    with tab_queue:
        unparsed_notes     = db.get_unparsed_session_notes()
        unparsed_readiness = db.get_unparsed_readiness()

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
                        db.update_session_note_ai(
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
                        db.update_readiness_ai(
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

        # Warnings panel
        flagged = db.get_flagged_entries()
        if flagged:
            st.divider()
            st.subheader("Active Warnings")
            for entry in flagged:
                level    = entry.get("warning_level", "monitor")
                color    = engine.WARNING_LEVEL_ICONS.get(level, "⚫")
                source   = entry.get("source", "?")
                date_str = entry.get("session_date") or str(entry.get("timestamp", ""))[:10]
                parts    = entry.get("body_parts", "")
                if isinstance(parts, str) and parts.startswith("["):
                    parts = ", ".join(json.loads(parts))
                summary  = entry.get("summary", "")
                movement = entry.get("movement_name", "")
                st.markdown(
                    f"{color} **{level.upper()}** &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; {source}"
                    + (f" &nbsp;·&nbsp; _{movement}_" if movement else ""),
                    unsafe_allow_html=True,
                )
                if summary:
                    st.caption(str(summary)[:200])
                if parts:
                    st.caption(f"Body areas: {parts}")
                st.markdown("---")

    # =========================================================================
    #  Tab 3 — Tightness Map
    # =========================================================================

    with tab_tightness:
        parsed_rows = db.get_parsed_readiness(limit=90)

        if not parsed_rows:
            st.info("No parsed readiness entries yet. Run the Processing Queue first.")
        else:
            body_freq: dict = {}
            for row in parsed_rows:
                parts_raw = row.get("ai_body_parts") or "[]"
                try:
                    parts = json.loads(parts_raw)
                except Exception:
                    parts = []
                for p in parts:
                    body_freq[p] = body_freq.get(p, 0) + 1

            if body_freq:
                st.subheader("Most Flagged Body Regions")
                df_freq = (
                    pd.DataFrame(list(body_freq.items()), columns=["Region", "Mentions"])
                    .sort_values("Mentions", ascending=False)
                    .reset_index(drop=True)
                )
                st.bar_chart(df_freq.set_index("Region")["Mentions"])
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
            df_warn     = pd.DataFrame(parsed_rows)[["date", "ai_warning_level"]]
            warn_counts = df_warn["ai_warning_level"].value_counts().reset_index()
            warn_counts.columns = ["Level", "Count"]
            col1, col2, col3 = st.columns(3)
            for _, wrow in warn_counts.iterrows():
                lvl  = wrow["Level"]
                cnt  = wrow["Count"]
                icon = engine.WARNING_LEVEL_ICONS.get(lvl, "⚫")
                if lvl == "none":      col1.metric(f"{icon} Clear",   cnt)
                elif lvl == "monitor": col2.metric(f"{icon} Monitor", cnt)
                elif lvl == "flag":    col3.metric(f"{icon} Flag",    cnt)

    # =========================================================================
    #  Tab 4 — Macro Trends
    # =========================================================================

    with tab_trends:
        st.subheader("Multi-Week Trend Analysis")

        trend_data = db.get_macro_trend_data(90)
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
                slope_rows = [
                    {
                        "Variable":    k.replace("_slope", "").replace("_", " ").title(),
                        "Slope / day": f"{v:+.5f}" if v is not None else "--",
                        "Direction":   (
                            ("improving" if v < 0 else "worsening")
                            if (v is not None and k in ("pain_slope", "tightness_slope"))
                            else ("improving" if (v is not None and v > 0) else "--")
                        ),
                    }
                    for k, v in slopes.items()
                ]
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
    #  Tab 5 — MRI Intelligence
    # =========================================================================

    with tab_mri:
        st.subheader("MRI x Session Data Cross-Reference")

        if not injury_profile:
            st.warning("No diagnostic profile found. Run init_db.py to seed the MRI data.")
        else:
            with st.expander("Stored MRI Context (raw)", expanded=False):
                st.caption(f"Injury focus: {injury_profile.get('injury_focus', '--')}")
                st.caption(f"Compensations: {injury_profile.get('historical_compensations', '--')}")
                st.text_area(
                    "MRI raw text",
                    value=injury_profile.get("mri_raw_text", ""),
                    height=120,
                    disabled=True,
                    label_visibility="collapsed",
                )

            recent_notes = db.get_recent_raw_notes(limit=20)

            if recent_notes:
                note_summary_lines = []
                for n in recent_notes:
                    date_str = n.get("session_date") or "?"
                    text     = n.get("ai_summary") or n.get("raw_text", "")[:120]
                    parts    = n.get("flagged_body_parts") or ""
                    if isinstance(parts, str) and parts.startswith("["):
                        try:
                            parts = ", ".join(json.loads(parts))
                        except Exception:
                            pass
                    note_summary_lines.append(
                        f"[{date_str}] {text}" + (f" | Areas: {parts}" if parts else "")
                    )
                notes_summary_str = "\n".join(note_summary_lines)
            else:
                notes_summary_str = "No session notes logged yet."

            latest_risk = db.get_latest_movement_risk()
            if latest_risk:
                ts = str(latest_risk.get("timestamp", ""))[:16]
                st.caption(f"Last assessment: {ts} (rules-based)")
                st.markdown(f"**Risk Summary**\n\n{latest_risk.get('risk_summary', '--')}")

                flagged_mv = latest_risk.get("flagged_movements", "[]")
                safe_mv    = latest_risk.get("safe_movements",    "[]")
                if isinstance(flagged_mv, str):
                    try:
                        flagged_mv = json.loads(flagged_mv)
                    except Exception:
                        flagged_mv = [flagged_mv]
                if isinstance(safe_mv, str):
                    try:
                        safe_mv = json.loads(safe_mv)
                    except Exception:
                        safe_mv = [safe_mv]

                col_flag, col_safe = st.columns(2)
                with col_flag:
                    st.markdown("**Movements to Avoid / Modify**")
                    for m in flagged_mv:
                        st.markdown(f"- {m}")
                with col_safe:
                    st.markdown("**Cleared Movements**")
                    for m in safe_mv:
                        st.markdown(f"- {m}")

                corr = latest_risk.get("correlation_notes", "")
                if corr:
                    st.info(f"**MRI x Session Pattern:** {corr}")

            current_stage = _stage()

            if st.button("Run Movement Risk Assessment", type="primary", key="mri_assess_btn"):
                with st.spinner("Applying MRI rules and keyword analysis of session notes..."):
                    try:
                        result = ai.assess_movement_risk(
                            injury_profile, notes_summary_str, stage=current_stage
                        )
                        db.save_movement_risk(
                            risk_summary      = result["risk_summary"],
                            flagged_movements = result["flagged_movements"],
                            safe_movements    = result["safe_movements"],
                            correlation_notes = result["correlation_notes"],
                            model_used        = ai.MODEL_SMART,
                        )
                        st.success("Assessment saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Assessment failed: {exc}")
