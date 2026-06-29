"""
Training Entry — Gym session logging.
Per-set dial inputs, auto rest timer, session RPE, and AI session notes.
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import date
import db
import engine
import rules
from training_constants import ALL_EXERCISES, MOVEMENT_TYPES, VELOCITY_OPTIONS, EXERCISES

st.set_page_config(page_title="Training Entry", layout="wide")

REST_TIMER_HTML = """
<div style="text-align:center; padding: 8px 0;">
    <div id="timer" style="
        font-family: monospace;
        font-size: 52px;
        font-weight: 700;
        color: #00D4AA;
        letter-spacing: 4px;
        margin-bottom: 8px;
    ">00:00</div>
    <button onclick="startTimer()" style="
        background:#00D4AA; color:#0E1117; border:none; border-radius:6px;
        padding:8px 20px; font-size:14px; font-weight:600; cursor:pointer; margin:4px;
    ">▶ Start</button>
    <button onclick="resetTimer()" style="
        background:#1A1F2E; color:#E8EAF0; border:1px solid #444; border-radius:6px;
        padding:8px 20px; font-size:14px; cursor:pointer; margin:4px;
    ">↺ Reset</button>
</div>
<script>
let _interval;
let _secs = 0;
function startTimer() {
    clearInterval(_interval);
    _interval = setInterval(() => {
        _secs++;
        const m = String(Math.floor(_secs / 60)).padStart(2,'0');
        const s = String(_secs % 60).padStart(2,'0');
        document.getElementById('timer').textContent = m + ':' + s;
    }, 1000);
}
function resetTimer() {
    clearInterval(_interval);
    _secs = 0;
    document.getElementById('timer').textContent = '00:00';
}
</script>
"""

# ── Session state init ────────────────────────────────────────────────────────

if "exercises" not in st.session_state:
    st.session_state.exercises = []   # list of dicts: {name, type, planned_sets, planned_reps, rpe, sets[], note}
if "session_saved" not in st.session_state:
    st.session_state.session_saved = False

# ── Header ────────────────────────────────────────────────────────────────────

st.title("Training Entry")
st.caption(f"{date.today().strftime('%A, %d %B %Y')}")
st.divider()

# ── Phase 1: Add Exercises ────────────────────────────────────────────────────

st.subheader("Exercises")

# Show saved exercises
for i, ex in enumerate(st.session_state.exercises):
    sets_summary = ", ".join(
        f"Set {s['set_num']}: {s['reps']}r @ {s['weight']}kg"
        for s in ex["sets"]
    )
    with st.expander(f"✓  {ex['name']}  —  {ex['type']}  |  {len(ex['sets'])} sets logged", expanded=False):
        st.caption(sets_summary if sets_summary else "No sets logged yet.")
        if ex.get("note"):
            st.caption(f"Note: {ex['note']}")
        if st.button("Remove", key=f"remove_{i}"):
            st.session_state.exercises.pop(i)
            st.rerun()

st.divider()
st.markdown("**Add Exercise**")

with st.form("add_exercise_form", clear_on_submit=True):
    col_ex, col_type = st.columns([3, 1])
    with col_ex:
        exercise_input = st.selectbox(
            "Exercise",
            ["— Custom (type below) —"] + ALL_EXERCISES,
        )
        custom_name = st.text_input("Custom name", placeholder="Type if not in list above")
    with col_type:
        movement_type = st.selectbox("Type", MOVEMENT_TYPES)
        planned_sets = st.number_input("Planned Sets", 1, 20, 3)
        planned_reps = st.number_input("Planned Reps", 1, 100, 10)

    st.markdown("**Sets**")
    set_cols = st.columns(6)
    headers = ["Set #", "Reps", "Weight (kg)", "Rest (s)", "TUT (s)", "Velocity"]
    for col, h in zip(set_cols, headers):
        col.markdown(f"<small style='color:#888'>{h}</small>", unsafe_allow_html=True)

    sets_data = []
    for s in range(1, int(planned_sets) + 1):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1: st.markdown(f"<div style='padding-top:8px'>{s}</div>", unsafe_allow_html=True)
        with c2: reps = st.number_input("", min_value=0, max_value=200, value=int(planned_reps), key=f"reps_{s}", label_visibility="collapsed")
        with c3: weight = st.number_input("", min_value=0.0, max_value=500.0, value=0.0, step=0.5, key=f"weight_{s}", label_visibility="collapsed")
        with c4: rest = st.number_input("", min_value=0, max_value=600, value=90, key=f"rest_{s}", label_visibility="collapsed")
        with c5: tut = st.number_input("", min_value=0, max_value=300, value=0, key=f"tut_{s}", label_visibility="collapsed")
        with c6: vel = st.selectbox("", VELOCITY_OPTIONS, key=f"vel_{s}", label_visibility="collapsed")
        sets_data.append({"set_num": s, "reps": reps, "weight": weight, "rest": rest, "tut": tut, "velocity": vel})

    ex_rpe = st.slider("Exercise RPE", 1, 10, 6, help="How hard did this exercise feel?")
    ex_note = st.text_input("Quick note (optional)", placeholder="e.g. Felt some L5 tightness on last set")

    add_ex = st.form_submit_button("Add Exercise to Session", use_container_width=True)

if add_ex:
    name = custom_name.strip() if exercise_input.startswith("—") else exercise_input
    if name:
        # Deterministic safety check from rules.py before logging
        current_stage = db.get_current_stage()
        safety = rules.check_movement(name, current_stage)
        if safety["severity"] == "contraindicated":
            st.error(
                f"**{name}** is contraindicated at Stage {current_stage}. "
                f"Reason: {safety['reason']} "
                + (f"Available from Stage {safety['stage_available']}." if safety.get("stage_available") else "")
            )
        else:
            if safety["severity"] == "caution":
                st.warning(f"**Caution — {name}:** {safety['reason']}")
            st.session_state.exercises.append({
                "name": name,
                "type": movement_type,
                "planned_sets": int(planned_sets),
                "planned_reps": int(planned_reps),
                "rpe": ex_rpe,
                "sets": sets_data,
                "note": ex_note,
                "safety": safety["severity"],
            })
            st.rerun()

# ── Rest Timer ────────────────────────────────────────────────────────────────

st.divider()
st.subheader("Rest Timer")
components.html(REST_TIMER_HTML, height=120)

# ── Phase 2: Finalise Session ─────────────────────────────────────────────────

if st.session_state.exercises:
    st.divider()
    st.subheader("Finalise Session")

    with st.form("finalise_session", clear_on_submit=False):
        col_meta, col_notes = st.columns([1, 2], gap="large")

        with col_meta:
            session_date = st.date_input("Session Date", value=date.today())
            duration = st.number_input(
                "Session Duration (minutes)", min_value=1, max_value=300, value=45,
                help="Total time from first exercise to last. Used for AU = Session-RPE × Duration."
            )
            session_rpe = st.slider(
                "Session RPE (Overall)", 1, 10, 6,
                help="How hard did the entire session feel? This × duration = Arbitrary Units (AU) for ACWR."
            )
            au = engine.compute_session_au(session_rpe, int(duration))
            st.metric("Session AU", f"{int(au)}", help="Arbitrary Units = Session-RPE × Duration (min). Fed directly into ACWR engine.")

        with col_notes:
            st.markdown("**Session Notes**")
            st.caption("How did the session feel? Any sensations, hesitations, or wins. Stored raw -- keyword parsing runs from the Insights page.")
            session_notes = st.text_area(
                "Notes",
                height=180,
                placeholder=(
                    "e.g. Hip flexors felt noticeably looser than last week on the bird-dog. "
                    "Slight pull on the right L5 area during the last set of glute bridges — "
                    "not painful but I backed off. Overall session felt controlled. Sleep was good last night."
                ),
                label_visibility="collapsed",
            )

        save_btn = st.form_submit_button("Save Session", use_container_width=True, type="primary")

    if save_btn and not st.session_state.session_saved:
        # create_training_session now returns a dict with session metadata
        session_info = db.create_training_session(
            session_date=session_date,
            duration_minutes=int(duration),
            session_rpe=session_rpe,
        )
        last_log_id = None
        for ex in st.session_state.exercises:
            # Sets and per-exercise notes are passed directly — one Notion page per exercise
            log_id = db.save_training_exercise(
                session_id=session_info["session_id"],
                movement_name=ex["name"],
                movement_type=ex["type"],
                planned_sets=ex["planned_sets"],
                planned_reps=ex["planned_reps"],
                rpe=ex["rpe"],
                sets=ex.get("sets", []),
                note=ex.get("note", ""),
                session_date=session_info["session_date"],
                session_duration_minutes=session_info["duration_minutes"],
                session_rpe=session_info["session_rpe"],
                session_au=session_info["session_au"],
            )
            last_log_id = log_id

        # Overall session notes appended to the last exercise page
        if session_notes.strip() and last_log_id:
            db.save_session_notes(last_log_id, session_notes)

        st.session_state.exercises = []
        st.session_state.session_saved = True
        st.success(f"Session saved — AU = {au}. View it in the Data Grid.")

if st.session_state.session_saved:
    if st.button("Start New Session"):
        st.session_state.session_saved = False
        st.rerun()
