"""
Insights view — Engine Data + Processing Queue +
Tightness Map - Macro Trends.

Usage:
    from views.insights import render
    render()

Caller is responsible for st.set_page_config(), styles.inject_css(), nav.inject().
"""

import calendar as cal_mod
import json
from dataclasses import asdict
from datetime import date

import streamlit as st
import pandas as pd

import repo
from services import ai
from services import engine
from services import stats as stats_mod
from services import insights as insights_svc


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level cached data fetchers  (must live outside render() so that
#  Streamlit recognises them as stable across reruns)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _bio():
    # engine.py/readiness.py still work on plain dicts -- asdict() converts
    # the typed BiometricRecord back to the exact shape they expect.
    return [asdict(r) for r in repo.get_repository().get_biometric_rolling(days=28)]

@st.cache_data(ttl=1800, show_spinner=False)
def _au():          return repo.get_repository().get_daily_session_au(28)

@st.cache_data(ttl=1800, show_spinner=False)
def _streak():      return repo.get_repository().get_pain_free_streak()

@st.cache_data(ttl=1800, show_spinner=False)
def _tight():       return repo.get_repository().get_avg_tightness(14)

@st.cache_data(ttl=1800, show_spinner=False)
def _diag():        return repo.get_repository().get_diagnostic_profile()

@st.cache_data(ttl=1800, show_spinner=False)
def _stage():       return repo.get_repository().get_current_stage()

@st.cache_data(ttl=1800, show_spinner=False)
def _sync_raw(sheet_id: str) -> list[dict]:
    return repo.get_repository().get_raw_sheet_rows()

@st.cache_data(ttl=1800, show_spinner=False)
def _sync_engine_view(sheet_id: str) -> list[dict]:
    records = repo.get_repository().get_biometric_rolling(days=28)
    return [asdict(r) for r in records]

@st.cache_data(ttl=1800, show_spinner=False)
def _blend_history() -> list[dict]:
    return [asdict(r) for r in repo.get_repository().get_biometric_blend_history()]


# ─────────────────────────────────────────────────────────────────────────────
#  render()
# ─────────────────────────────────────────────────────────────────────────────

def render() -> None:
    st.title("Insights")
    st.caption("Engine metrics, biometric trends, session pattern analysis.")

    injury_profile = repo.get_repository().get_diagnostic_profile()

    (
        tab_engine, tab_queue,
        tab_tightness, tab_sync,
    ) = st.tabs([
        "Engine Data",
        "Processing Queue",
        "Tightness Map - Macro Trends",
        "Sync",
    ])

    # =========================================================================
    #  Tab 0 — Engine Data
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
            avg_tight     = _tight()
            diagnostic    = _diag()
            current_stage = _stage()
            lambda_val    = float(diagnostic.get("injury_weight_decay_lambda") or 0.05)

            tl          = engine.traffic_light(bio_rows)
            acwr_result = engine.acwr(au_rows, current_stage)
            inj_weight  = engine.injury_weight(lambda_val, pain_streak)
            obs_rem     = engine.observation_days_remaining(tl["data_days"])
            rec         = engine.volume_recommendation(tl, acwr_result, current_stage, obs_rem, inj_weight)
            inj_signal  = engine.injury_weight_signal(inj_weight)
            stage_info  = engine.stage_status(current_stage, pain_streak, avg_tight)

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

        # ── Stage progression ─────────────────────────────────────────────────
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

            # Which source (if any) was missing for today's blended reading —
            # populated by services/biometrics.py's blend_biometric_day().
            _today_bio = next((r for r in bio_rows if r.get("date") == date.today().isoformat()), None)
            _sources_missing = set((_today_bio or {}).get("sources_missing") or ())

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
                delta_str = insights_svc.metric_delta_str(delta)
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
                missing_source = next(
                    (s.split(":")[1] for s in _sources_missing if s.startswith(f"{key}:")), None,
                )
                if missing_source:
                    col.caption(f"⚠ {missing_source.title()} pending — using the other source only.")

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
            daily_au = acwr_result.get("daily_au_28", [0.0] * 28)
            chart    = insights_svc.acwr_chart_data(daily_au, today=date.today())
            df_au = pd.DataFrame({
                "Date":   chart["dates"],
                "AU":     chart["au"],
                "Window": chart["windows"],
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
    #  Tab 1 — Processing Queue
    # =========================================================================

    with tab_queue:
        unparsed_notes     = repo.get_repository().get_unparsed_session_notes()
        unparsed_readiness = repo.get_repository().get_unparsed_readiness()

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
                        repo.get_repository().update_session_note_ai(
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
                        repo.get_repository().update_readiness_ai(
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

        # ── Warnings calendar ────────────────────────────────────────────────
        flagged = repo.get_repository().get_flagged_entries()
        if flagged:
            st.divider()
            st.subheader("Active Warnings")

            def _entry_date_str(entry: dict) -> str:
                d = entry.get("session_date") or entry.get("timestamp") or ""
                return str(d)[:10]

            by_date: dict[str, list[dict]] = {}
            for entry in flagged:
                by_date.setdefault(_entry_date_str(entry), []).append(entry)

            if "queue_cal_year" not in st.session_state:
                anchor = date.fromisoformat(max(by_date)) if by_date else date.today()
                st.session_state["queue_cal_year"]  = anchor.year
                st.session_state["queue_cal_month"] = anchor.month

            cal_year  = st.session_state["queue_cal_year"]
            cal_month = st.session_state["queue_cal_month"]

            nav_prev, nav_label, nav_next = st.columns([1, 3, 1])
            if nav_prev.button("◀", key="queue_cal_prev"):
                cal_month -= 1
                if cal_month < 1:
                    cal_month, cal_year = 12, cal_year - 1
                st.session_state["queue_cal_year"]  = cal_year
                st.session_state["queue_cal_month"] = cal_month
                st.rerun()
            nav_label.markdown(
                f"<div style='text-align:center;font-weight:700;'>"
                f"{cal_mod.month_name[cal_month]} {cal_year}</div>",
                unsafe_allow_html=True,
            )
            if nav_next.button("▶", key="queue_cal_next"):
                cal_month += 1
                if cal_month > 12:
                    cal_month, cal_year = 1, cal_year + 1
                st.session_state["queue_cal_year"]  = cal_year
                st.session_state["queue_cal_month"] = cal_month
                st.rerun()

            dow_cols = st.columns(7)
            for col, dow in zip(dow_cols, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
                col.markdown(
                    f"<div style='text-align:center;color:#888;font-size:11px;'>{dow}</div>",
                    unsafe_allow_html=True,
                )

            selected_date = st.session_state.get("queue_selected_date")
            weeks = cal_mod.Calendar(firstweekday=0).monthdatescalendar(cal_year, cal_month)

            for week in weeks:
                week_cols = st.columns(7)
                for col, day in zip(week_cols, week):
                    day_str     = day.isoformat()
                    day_entries = by_date.get(day_str, [])
                    if day_entries:
                        levels = {e.get("warning_level") for e in day_entries}
                        ball   = "🔴" if "flag" in levels else "🟡"
                        is_selected = selected_date == day_str
                        if col.button(
                            f"{day.day} {ball}",
                            key=f"queue_cal_{day_str}",
                            use_container_width=True,
                            type="primary" if is_selected else "secondary",
                        ):
                            st.session_state["queue_selected_date"] = day_str
                            st.rerun()
                    else:
                        dim = "#5A6172" if day.month == cal_month else "#2A2E38"
                        col.markdown(
                            f"<div style='text-align:center;color:{dim};padding:8px 0;'>{day.day}</div>",
                            unsafe_allow_html=True,
                        )

            if selected_date and selected_date in by_date:
                st.divider()
                st.markdown(f"**{date.fromisoformat(selected_date).strftime('%A, %d %B %Y')}**")
                for entry in by_date[selected_date]:
                    level    = entry.get("warning_level", "monitor")
                    color    = engine.WARNING_LEVEL_ICONS.get(level, "⚫")
                    source   = entry.get("source", "?")
                    parts    = entry.get("body_parts", "")
                    if isinstance(parts, str) and parts.startswith("["):
                        parts = ", ".join(json.loads(parts))
                    summary  = entry.get("summary", "")
                    movement = entry.get("movement_name", "")
                    st.markdown(
                        f"{color} **{level.upper()}** &nbsp;·&nbsp; {source}"
                        + (f" &nbsp;·&nbsp; _{movement}_" if movement else ""),
                        unsafe_allow_html=True,
                    )
                    if summary:
                        st.caption(str(summary)[:200])
                    if parts:
                        st.caption(f"Body areas: {parts}")
                    st.markdown("---")

    # =========================================================================
    #  Tab 2 — Tightness Map - Macro Trends
    # =========================================================================

    with tab_tightness:
        parsed_rows = repo.get_repository().get_parsed_readiness(limit=90)

        if not parsed_rows:
            st.info("No parsed readiness entries yet. Run the Processing Queue first.")
        else:
            body_freq = insights_svc.body_region_frequency(parsed_rows)

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

        # ── Macro Trends ────────────────────────────────────────────────────
        st.divider()
        st.subheader("Multi-Week Trend Analysis")

        trend_data = repo.get_repository().get_macro_trend_data(90)
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
                slope_rows = insights_svc.slope_direction_rows(slopes)
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
    #  Tab 3 — Sync
    # =========================================================================

    with tab_sync:
        st.caption(
            "Legacy Apple Health export (Sheet1) — no longer read by the engine. "
            "Kept for historical reference and the one-time Garmin backfill "
            "(scripts/backfill_garmin_from_sheet1.py) only."
        )

        try:
            sheet_id = st.secrets["GOOGLE_SHEETS_ID"]
        except Exception:
            sheet_id = None
            st.error("GOOGLE_SHEETS_ID missing from .streamlit/secrets.toml")

        if sheet_id:
            if st.button("Refresh", use_container_width=False, key="sync_refresh"):
                st.cache_data.clear()
                st.rerun()

            with st.spinner("Reading Sheet1 from Google Sheets…"):
                try:
                    sync_rows = _sync_raw(sheet_id)
                except Exception as exc:
                    sync_rows = None
                    st.error(f"Could not read Sheet1: {exc}")

            if sync_rows is not None:
                if not sync_rows:
                    st.info("Sheet1 is empty — no data yet.")
                else:
                    df_sync = pd.DataFrame(sync_rows)

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total rows", len(df_sync))
                    col2.metric("Earliest",   str(df_sync["Date/Time"].iloc[0])[:10])
                    col3.metric("Latest",     str(df_sync["Date/Time"].iloc[-1])[:10])

                    st.divider()

                    st.subheader("Raw Sheet Data")
                    st.dataframe(df_sync, use_container_width=True, height=400)

                    st.divider()
                    st.subheader("Engine View — Last 28 Days (live)")
                    st.caption(
                        "Oura (70%) + Garmin (30%) blend for HRV/RHR/sleep, Garmin (80%) + "
                        "Oura (20%) for steps — services/biometrics.py — as passed to the "
                        "traffic-light engine right now. Recomputed on every load; not "
                        "persisted. No longer sourced from Sheet1 above."
                    )

                    engine_rows = _sync_engine_view(sheet_id)
                    if engine_rows:
                        st.dataframe(pd.DataFrame(engine_rows), use_container_width=True)
                    else:
                        st.info("No rows within the last 28 days.")

                    st.divider()
                    st.subheader("Biometric Blend History (persisted)")
                    st.caption(
                        "A fixed daily record of the blend above, written once a day "
                        "(Repository.sync_biometric_blend) to its own sheet tab. Unlike the "
                        "live view above, a past day here doesn't change even if Oura/Garmin "
                        "later revise that day's raw reading — this is what you actually saw "
                        "at the time."
                    )
                    if st.button(
                        "Backfill full history now",
                        use_container_width=False,
                        key="backfill_biometric_blend",
                    ):
                        with st.spinner("Computing and persisting the full blend history…"):
                            try:
                                n = repo.get_repository().sync_biometric_blend(days=400)
                                st.success(f"Persisted {n} day(s) to the Biometric Blend tab.")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as exc:
                                st.warning(f"Backfill failed: {exc}")

                    try:
                        blend_history = _blend_history()
                    except Exception as exc:
                        blend_history = None
                        st.warning(f"Could not load blend history: {exc}")

                    if blend_history:
                        earliest = date.fromisoformat(blend_history[0]["date"])
                        latest = date.fromisoformat(blend_history[-1]["date"])
                        col_from, col_to = st.columns(2)
                        start_pick = col_from.date_input("From", value=earliest, key="blend_hist_from")
                        end_pick = col_to.date_input("To", value=latest, key="blend_hist_to")
                        filtered = [
                            r for r in blend_history
                            if str(start_pick) <= r["date"] <= str(end_pick)
                        ]
                        st.dataframe(pd.DataFrame(filtered), use_container_width=True, height=400)
                    elif blend_history is not None:
                        st.info(
                            "No persisted history yet — click \"Backfill full history now\" "
                            "above, or wait for the automatic once-a-day sync."
                        )

                    st.divider()
                    st.caption(
                        "Weekly Rollup syncs automatically once a week; Garmin Daily Metrics "
                        "syncs automatically once a day (both checked whenever the Home or "
                        "Training page loads — no button needed)."
                    )

                    st.divider()
                    st.subheader("Garmin")
                    sync_repo = repo.get_repository()
                    if not sync_repo.garmin_configured():
                        st.info(
                            "Add GARMIN_EMAIL and GARMIN_PASSWORD to .streamlit/secrets.toml to "
                            "enable Garmin sync. Feeds the readiness/ACWR engine (30% weight for "
                            "HRV/RHR/sleep, 80% for steps, blended with Oura) once configured."
                        )
                    else:
                        st.caption(
                            "Daily wellness metrics feed the readiness/ACWR engine (blended with "
                            "Oura) and archive to their own Sheet tabs (Garmin Daily, Garmin "
                            "Activities). Daily Metrics also syncs automatically once a day on "
                            "Home/Training page open; use the button below to run it on demand."
                        )

                        col_daily, col_activities = st.columns(2, gap="small")
                        with col_daily:
                            if st.button(
                                "Sync Garmin Daily Metrics",
                                use_container_width=True,
                                key="sync_garmin_daily",
                            ):
                                with st.spinner("Pulling daily metrics from Garmin…"):
                                    try:
                                        n = sync_repo.sync_garmin_daily(days=7)
                                        st.success(f"Synced {n} days to the Garmin Daily tab.")
                                    except Exception as exc:
                                        st.warning(f"Garmin daily sync failed: {exc}")
                        with col_activities:
                            if st.button(
                                "Sync Garmin Activities",
                                use_container_width=True,
                                key="sync_garmin_activities",
                            ):
                                with st.spinner("Pulling activities from Garmin…"):
                                    try:
                                        n = sync_repo.sync_garmin_activities(limit=20)
                                        st.success(
                                            f"Synced {n} activities to the Garmin Activities tab."
                                        )
                                    except Exception as exc:
                                        st.warning(f"Garmin activity sync failed: {exc}")

                    st.divider()
                    st.subheader("Oura")
                    if not sync_repo.oura_configured():
                        st.info(
                            "Add OURA_TOKEN to .streamlit/secrets.toml to enable Oura sync. "
                            "Feeds the readiness/ACWR engine (70% weight for HRV/RHR/sleep, 20% "
                            "for steps, blended with Garmin) once configured."
                        )
                    else:
                        st.caption(
                            "Daily steps and sleep-period HRV/RHR/sleep-duration feed the "
                            "readiness/ACWR engine (blended with Garmin). Daily summary scores "
                            "(sleep, readiness, activity, stress, resilience, SpO2, "
                            "cardiovascular age) archive to the Oura Daily tab; workouts, "
                            "sessions, and rest-mode periods each get their own archival tab. "
                            "Also syncs automatically 2 hours after the Home page is opened; use "
                            "the button below to pull a full week on demand."
                        )
                        if st.button(
                            "Sync Weekly Oura Details",
                            use_container_width=False,
                            key="sync_oura_weekly",
                        ):
                            with st.spinner("Pulling the last 7 days from Oura…"):
                                try:
                                    counts = sync_repo.sync_oura_all(days=7)
                                    st.success(
                                        f"Synced {counts['daily']} days, "
                                        f"{counts['workouts']} workouts, "
                                        f"{counts['sleep_periods']} sleep periods, "
                                        f"{counts['sessions']} sessions, "
                                        f"{counts['rest_mode_periods']} rest-mode periods."
                                    )
                                except Exception as exc:
                                    st.warning(f"Oura sync failed: {exc}")
