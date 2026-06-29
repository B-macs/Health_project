"""
Insights -- Rule-Based Text Parser dashboard.
Parses raw session notes and tightness descriptions into structured clinical data
using deterministic keyword matching. No external API or model required.
"""

import json
import streamlit as st
import pandas as pd
import db
import ai
import engine
import stats as stats_mod

st.set_page_config(page_title="Insights", layout="wide")
st.title("Insights -- Rule-Based Parser")
st.caption("Keyword matching converts raw text into structured clinical data. No external API required.")

# ── Shared data ───────────────────────────────────────────────────────────────
injury_profile = db.get_diagnostic_profile()

tab_queue, tab_tightness, tab_trends, tab_mri = st.tabs([
    "Processing Queue", "Tightness Map", "Macro Trends", "MRI Intelligence"
])


# ─────────────────────────────────────────────────────────────────────────────
#  Tab 1 — Processing Queue
# ─────────────────────────────────────────────────────────────────────────────

with tab_queue:
    unparsed_notes     = db.get_unparsed_session_notes()
    unparsed_readiness = db.get_unparsed_readiness()

    col_a, col_b = st.columns(2)
    col_a.metric("Session notes pending", len(unparsed_notes))
    col_b.metric("Readiness entries pending", len(unparsed_readiness))

    total_pending = len(unparsed_notes) + len(unparsed_readiness)

    if total_pending == 0:
        st.success("All entries are processed. Nothing in the queue.")
    else:
        st.info(
            f"{total_pending} item(s) ready for parsing. "
            "Processing uses local keyword matching — no external service required."
        )

        if st.button("Process All", type="primary", use_container_width=True):
            progress = st.progress(0, text="Starting...")
            total    = total_pending
            done     = 0
            errors   = []

            # Parse session notes
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

            # Parse readiness tightness
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


# ─────────────────────────────────────────────────────────────────────────────
#  Tab 2 — Tightness Map
# ─────────────────────────────────────────────────────────────────────────────

with tab_tightness:
    parsed_rows = db.get_parsed_readiness(limit=90)

    if not parsed_rows:
        st.info("No parsed readiness entries yet. Run the Processing Queue first.")
    else:
        # Build body part frequency table
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
            st.caption("Frequency of each region appearing in parsed tightness entries (keyword matching).")

        # Tightness severity timeline
        st.divider()
        st.subheader("Tightness Severity Timeline")
        df_time = pd.DataFrame(parsed_rows)[["date", "tightness_score", "ai_tightness_severity", "pain_score"]]
        df_time = df_time.rename(columns={
            "tightness_score":      "Self-reported",
            "ai_tightness_severity": "Keyword-parsed severity",
            "pain_score":           "Pain score",
        }).set_index("date")
        st.line_chart(df_time.dropna(how="all"))
        st.caption("Self-reported vs keyword-parsed tightness severity over time.")

        # Warning level breakdown
        st.divider()
        st.subheader("Warning Level History")
        df_warn = pd.DataFrame(parsed_rows)[["date", "ai_warning_level"]]
        warn_counts = df_warn["ai_warning_level"].value_counts().reset_index()
        warn_counts.columns = ["Level", "Count"]
        col1, col2, col3 = st.columns(3)
        for _, wrow in warn_counts.iterrows():
            lvl = wrow["Level"]
            cnt = wrow["Count"]
            icon = engine.WARNING_LEVEL_ICONS.get(lvl, "⚫")
            if lvl == "none":      col1.metric(f"{icon} Clear",   cnt)
            elif lvl == "monitor": col2.metric(f"{icon} Monitor", cnt)
            elif lvl == "flag":    col3.metric(f"{icon} Flag",    cnt)


# ─────────────────────────────────────────────────────────────────────────────
#  Tab 3 — Macro Trends
# ─────────────────────────────────────────────────────────────────────────────

with tab_trends:
    st.subheader("Multi-Week Trend Analysis")

    trend_data = db.get_macro_trend_data(90)
    n_bio      = len(trend_data["biometrics"])
    n_sessions = len(trend_data["sessions"])

    col_d, col_s = st.columns(2)
    col_d.metric("Biometric days available", n_bio)
    col_s.metric("Training sessions available", n_sessions)

    if n_bio < engine.MIN_OBSERVATION_DAYS:
        st.warning(
            f"Need at least {engine.MIN_OBSERVATION_DAYS} days of biometric data for trend analysis. "
            f"Currently have {n_bio}. Keep logging daily."
        )
    else:
        # Step 1: deterministic stats (always shown, no button required)
        computed     = stats_mod.compute_all_correlations(trend_data)
        notable      = computed.get("notable_correlations", [])
        slopes       = computed.get("slopes", {})
        recovery_dir = computed["recovery_direction"]

        recovery_icons = {"improving": "up", "stable": "stable", "degrading": "down", "insufficient_data": "?"}
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
                    "Direction":   ("improving" if v < 0 else "worsening") if (v is not None and k in ("pain_slope", "tightness_slope"))
                                   else ("improving" if (v is not None and v > 0) else "--"),
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

        # Step 2: template-based interpretation (deterministic, no API call)
        if st.button("Generate Trend Interpretation", type="primary"):
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
        recovery_map = {"improving": "Improving", "stable": "Stable", "degrading": "Degrading", "insufficient_data": "Insufficient data"}
        st.markdown(f"**Recovery trajectory:** {recovery_map.get(recovery, recovery.replace('_', ' ').title())}")

        load_note = r.get("load_management_note", "")
        if load_note:
            st.info(load_note)

        correlations = r.get("correlation_interpretations", [])
        if correlations:
            st.subheader("Correlation Interpretations")
            for corr in correlations:
                st.markdown(f"**{corr.get('variable_pair', '--')}** (lag {corr.get('lag_days', '?')}d)")
                st.caption(corr.get("clinical_note", ""))

        recs = r.get("recommendations", [])
        if recs:
            st.subheader("Recommendations")
            for rec in recs:
                st.markdown(f"- {rec}")


# ─────────────────────────────────────────────────────────────────────────────
#  Tab 4 — MRI Intelligence
# ─────────────────────────────────────────────────────────────────────────────

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

        # Summarise recent session notes for keyword analysis
        recent_notes = db.get_recent_raw_notes(limit=20)

        if recent_notes:
            note_summary_lines = []
            for n in recent_notes:
                date_str = n.get("session_date") or "?"
                text     = n.get("ai_summary") or n.get("raw_text", "")[:120]
                parts    = n.get("flagged_body_parts") or ""
                if isinstance(parts, str) and parts.startswith("["):
                    try: parts = ", ".join(json.loads(parts))
                    except Exception: pass
                note_summary_lines.append(
                    f"[{date_str}] {text}" + (f" | Areas: {parts}" if parts else "")
                )
            notes_summary_str = "\n".join(note_summary_lines)
        else:
            notes_summary_str = "No session notes logged yet."

        # Show latest risk assessment if cached
        latest_risk = db.get_latest_movement_risk()
        if latest_risk:
            ts = str(latest_risk.get("timestamp", ""))[:16]
            st.caption(f"Last assessment: {ts} (rules-based)")

            st.markdown(f"**Risk Summary**\n\n{latest_risk.get('risk_summary', '--')}")

            flagged = latest_risk.get("flagged_movements", "[]")
            safe    = latest_risk.get("safe_movements", "[]")
            if isinstance(flagged, str):
                try: flagged = json.loads(flagged)
                except Exception: flagged = [flagged]
            if isinstance(safe, str):
                try: safe = json.loads(safe)
                except Exception: safe = [safe]

            col_flag, col_safe = st.columns(2)
            with col_flag:
                st.markdown("**Movements to Avoid / Modify**")
                for m in flagged:
                    st.markdown(f"- {m}")
            with col_safe:
                st.markdown("**Cleared Movements**")
                for m in safe:
                    st.markdown(f"- {m}")

            corr = latest_risk.get("correlation_notes", "")
            if corr:
                st.info(f"**MRI x Session Pattern:** {corr}")

        current_stage = db.get_current_stage()

        if st.button("Run Movement Risk Assessment", type="primary"):
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
