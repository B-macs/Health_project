"""
Training Plan — Interactive 14-Day Rehab Session Guide.
Shows today's exercises with live hold timers and auto rest countdown between sets.
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import date, timedelta
import db
import training_plan as tp

st.set_page_config(page_title="Training Plan", layout="wide")

# ─────────────────────────────────────────────────────────────────────────────
#  JavaScript Timer Components
# ─────────────────────────────────────────────────────────────────────────────

def _hold_timer(seconds: int, label: str = "HOLD") -> None:
    """Countdown timer for isometric holds — teal, pulses in final 5s."""
    components.html(
        f"""
        <div style="text-align:center; padding:12px 0; font-family:monospace;">
            <div style="font-size:13px; color:#00D4AA; letter-spacing:3px; margin-bottom:6px;">
                {label}
            </div>
            <div id="hold-num" style="
                font-size:72px; font-weight:700; color:#00D4AA;
                line-height:1; margin-bottom:12px; transition:color 0.3s;">
                {seconds}
            </div>
            <div style="display:flex; gap:10px; justify-content:center;">
                <button id="btn-start" onclick="startHold()" style="
                    background:#00D4AA; color:#0E1117; border:none; border-radius:6px;
                    padding:10px 24px; font-size:14px; font-weight:700; cursor:pointer;">
                    ▶ Start
                </button>
                <button onclick="resetHold()" style="
                    background:#1A1F2E; color:#E8EAF0; border:1px solid #444;
                    border-radius:6px; padding:10px 20px; font-size:14px; cursor:pointer;">
                    ↺ Reset
                </button>
            </div>
        </div>
        <script>
        var _total = {seconds};
        var _remaining = {seconds};
        var _iv;
        function startHold() {{
            clearInterval(_iv);
            document.getElementById('btn-start').textContent = '⏸ Pause';
            document.getElementById('btn-start').onclick = pauseHold;
            _iv = setInterval(function() {{
                _remaining--;
                var el = document.getElementById('hold-num');
                el.textContent = _remaining;
                if (_remaining <= 5) {{
                    el.style.color = '#FF4B4B';
                    el.style.transform = 'scale(1.1)';
                    setTimeout(function(){{ el.style.transform = 'scale(1)'; }}, 200);
                }}
                if (_remaining <= 0) {{
                    clearInterval(_iv);
                    el.textContent = '✓';
                    el.style.color = '#00D4AA';
                    document.getElementById('btn-start').textContent = '▶ Start';
                    document.getElementById('btn-start').onclick = startHold;
                }}
            }}, 1000);
        }}
        function pauseHold() {{
            clearInterval(_iv);
            document.getElementById('btn-start').textContent = '▶ Resume';
            document.getElementById('btn-start').onclick = startHold;
        }}
        function resetHold() {{
            clearInterval(_iv);
            _remaining = _total;
            var el = document.getElementById('hold-num');
            el.textContent = _total;
            el.style.color = '#00D4AA';
            document.getElementById('btn-start').textContent = '▶ Start';
            document.getElementById('btn-start').onclick = startHold;
        }}
        </script>
        """,
        height=160,
    )


def _rest_timer(seconds: int) -> None:
    """Countdown timer for rest periods — blue-grey, calm styling."""
    m, s = divmod(seconds, 60)
    label = f"{m:02d}:{s:02d}"
    components.html(
        f"""
        <div style="text-align:center; padding:10px 0; font-family:monospace;
                    background:#1A1F2E; border-radius:10px; margin:4px 0;">
            <div style="font-size:11px; color:#6B7280; letter-spacing:3px; margin-bottom:4px;">
                REST
            </div>
            <div id="rest-num" style="font-size:52px; font-weight:700; color:#6B7280; line-height:1; margin-bottom:10px;">
                {label}
            </div>
            <div style="font-size:11px; color:#6B7280; margin-bottom:10px;">
                breathe — reset — prepare for next set
            </div>
            <div style="display:flex; gap:8px; justify-content:center;">
                <button id="rest-btn" onclick="startRest()" style="
                    background:#6B7280; color:#FFF; border:none; border-radius:6px;
                    padding:8px 20px; font-size:13px; cursor:pointer;">
                    ▶ Start Rest Timer
                </button>
                <button onclick="skipRest()" style="
                    background:#1A1F2E; color:#E8EAF0; border:1px solid #444;
                    border-radius:6px; padding:8px 16px; font-size:13px; cursor:pointer;">
                    Skip →
                </button>
            </div>
        </div>
        <script>
        var _rtotal = {seconds};
        var _rrem = {seconds};
        var _riv;
        function fmt(n) {{ var m=Math.floor(n/60), s=n%60; return (m<10?'0':'')+m+':'+(s<10?'0':'')+s; }}
        function startRest() {{
            clearInterval(_riv);
            document.getElementById('rest-btn').textContent = '⏸ Pause';
            document.getElementById('rest-btn').onclick = pauseRest;
            _riv = setInterval(function() {{
                _rrem--;
                document.getElementById('rest-num').textContent = fmt(_rrem);
                if (_rrem <= 5) {{
                    document.getElementById('rest-num').style.color = '#00D4AA';
                }}
                if (_rrem <= 0) {{
                    clearInterval(_riv);
                    document.getElementById('rest-num').textContent = 'GO';
                    document.getElementById('rest-num').style.color = '#00D4AA';
                    document.getElementById('rest-num').style.fontSize = '42px';
                    document.getElementById('rest-btn').textContent = '▶ Start';
                    document.getElementById('rest-btn').onclick = startRest;
                }}
            }}, 1000);
        }}
        function pauseRest() {{
            clearInterval(_riv);
            document.getElementById('rest-btn').textContent = '▶ Resume';
            document.getElementById('rest-btn').onclick = startRest;
        }}
        function skipRest() {{
            clearInterval(_riv);
            _rrem = _rtotal;
            document.getElementById('rest-num').textContent = fmt(_rrem);
            document.getElementById('rest-num').style.color = '#6B7280';
            document.getElementById('rest-num').style.fontSize = '52px';
        }}
        </script>
        """,
        height=155,
    )


def _duration_timer(minutes: int) -> None:
    """Countdown timer for continuous activities (walking, breathing)."""
    total = minutes * 60
    label = f"{minutes:02d}:00"
    components.html(
        f"""
        <div style="text-align:center; padding:10px 0; font-family:monospace;">
            <div style="font-size:11px; color:#FFD700; letter-spacing:3px; margin-bottom:4px;">ACTIVITY TIMER</div>
            <div id="dur-num" style="font-size:56px; font-weight:700; color:#FFD700; line-height:1; margin-bottom:10px;">
                {label}
            </div>
            <button id="dur-btn" onclick="startDur()" style="
                background:#FFD700; color:#0E1117; border:none; border-radius:6px;
                padding:10px 24px; font-size:14px; font-weight:700; cursor:pointer;">
                ▶ Start {minutes}min Timer
            </button>
        </div>
        <script>
        var _dtotal = {total};
        var _drem = {total};
        var _div;
        function fmt(n) {{ var m=Math.floor(n/60), s=n%60; return (m<10?'0':'')+m+':'+(s<10?'0':'')+s; }}
        function startDur() {{
            clearInterval(_div);
            document.getElementById('dur-btn').textContent = '⏸ Pause';
            document.getElementById('dur-btn').onclick = pauseDur;
            _div = setInterval(function() {{
                _drem--;
                document.getElementById('dur-num').textContent = fmt(_drem);
                if (_drem <= 30) document.getElementById('dur-num').style.color = '#00D4AA';
                if (_drem <= 0) {{
                    clearInterval(_div);
                    document.getElementById('dur-num').textContent = 'DONE ✓';
                    document.getElementById('dur-btn').textContent = '▶ Restart';
                    document.getElementById('dur-btn').onclick = function(){{_drem=_dtotal; startDur();}};
                }}
            }}, 1000);
        }}
        function pauseDur() {{
            clearInterval(_div);
            document.getElementById('dur-btn').textContent = '▶ Resume';
            document.getElementById('dur-btn').onclick = startDur;
        }}
        </script>
        """,
        height=140,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Session State
# ─────────────────────────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "tp_ex_idx":      0,       # which exercise in today's list (0-indexed)
        "tp_set":         1,       # current set number (1-indexed)
        "tp_rep_in_set":  1,       # current rep number within a hold_reps set
        "tp_phase":       "intro", # "intro" | "active" | "resting" | "done"
        "tp_done_today":  False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_session():
    for k in ["tp_ex_idx", "tp_set", "tp_rep_in_set", "tp_phase", "tp_done_today"]:
        if k in st.session_state:
            del st.session_state[k]
    _init_state()


_init_state()


# ─────────────────────────────────────────────────────────────────────────────
#  Plan Setup / Day Calculation
# ─────────────────────────────────────────────────────────────────────────────

def _get_plan_start() -> date | None:
    raw = db.get_config_value("plan_start_date")
    if raw:
        try:
            return date.fromisoformat(raw.strip())
        except ValueError:
            pass
    return None


def _get_day_number(plan_start: date) -> int:
    return (date.today() - plan_start).days + 1


# ─────────────────────────────────────────────────────────────────────────────
#  Exercise Display Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _prescription_label(ex: dict) -> str:
    t = ex["type"]
    if t == "hold":
        sides = " each side" if ex["laterality"] == "unilateral" else ""
        return f"{ex['sets']} sets × {ex['hold_seconds']}s hold{sides}  |  {ex['rest_seconds']}s rest"
    if t == "hold_reps":
        sides = " each side" if ex["laterality"] in ("unilateral", "alternating") else ""
        return f"{ex['sets']} sets × {ex['reps_in_set']} reps × {ex['hold_seconds']}s hold{sides}  |  {ex['rest_seconds']}s rest"
    if t == "reps":
        sides = " each side" if ex["laterality"] in ("unilateral", "alternating") else ""
        tempo = f"  Tempo {ex['tempo']}" if ex.get("tempo") else ""
        return f"{ex['sets']} sets × {ex['reps']} reps{sides}{tempo}  |  {ex['rest_seconds']}s rest"
    if t == "duration":
        return f"{ex['duration_minutes']} minutes continuous"
    return ""


def _type_icon(ex: dict) -> str:
    icons = {"hold": "⏱", "hold_reps": "⏱", "reps": "↕", "duration": "🚶"}
    return icons.get(ex["type"], "•")


# ─────────────────────────────────────────────────────────────────────────────
#  Main Page
# ─────────────────────────────────────────────────────────────────────────────

st.title("Training Plan")

plan_start = _get_plan_start()

# ── Plan not yet configured ───────────────────────────────────────────────────
if plan_start is None:
    st.subheader("Set Your Plan Start Date")
    st.info(
        "This 14-day progressive rehab plan is tailored to your MRI profile "
        "(L5/S1 disc pathology, Stage 1 Rehab). "
        "Bodyweight only — no equipment required. "
        "Set your start date and the app will show the correct day's exercises automatically."
    )
    start_input = st.date_input(
        "Plan start date",
        value=date.today(),
        help="You can backdate if you've already started.",
    )
    if st.button("Begin 14-Day Plan", type="primary", use_container_width=True):
        db.set_config("plan_start_date", str(start_input))
        st.success(f"Plan starts {start_input}. Come back each day for your session.")
        st.rerun()
    st.stop()

# ── Calculate current day ──────────────────────────────────────────────────────
day_num = _get_day_number(plan_start)

# Sidebar — plan overview and reset
with st.sidebar:
    st.header("Plan Status")
    st.metric("Plan Start", str(plan_start))
    st.metric("Today", str(date.today()))
    if 1 <= day_num <= 14:
        st.metric("Current Day", f"Day {day_num} of 14")
        st.progress(day_num / 14, text=f"{int(day_num/14*100)}% complete")
    st.divider()
    if st.button("Reset Plan (set new start date)", use_container_width=True):
        db.set_config("plan_start_date", "")
        _reset_session()
        st.rerun()

# ── Before plan start ──────────────────────────────────────────────────────────
if day_num < 1:
    days_until = (plan_start - date.today()).days
    st.info(f"Your plan starts in {days_until} day(s) on {plan_start}. Come back then.")
    st.stop()

# ── Plan complete ──────────────────────────────────────────────────────────────
if day_num > 14:
    st.balloons()
    st.success(
        "**14-Day Stage 1 Rehab Complete.**\n\n"
        "Your objectives: tissue tolerance established, neural desensitisation, "
        "gluteal activation, hip hinge pattern, and spinal stability foundation.\n\n"
        "Open the **Autoregulation** page to check Stage 1 → 2 progression criteria. "
        "If criteria are met, confirm with your physiotherapist before advancing."
    )
    st.stop()

# ── Active plan day ────────────────────────────────────────────────────────────
today_plan = tp.PLAN[day_num]
exercises  = today_plan["exercises"]
n_ex       = len(exercises)

# Header
st.markdown(
    f"<h2 style='margin-bottom:2px;'>Day {day_num} of 14</h2>"
    f"<p style='color:#00D4AA; font-family:monospace; font-size:15px; margin-top:0;'>"
    f"{today_plan['objective']}</p>"
    f"<p style='color:#888; font-size:13px;'>{today_plan['phase']} — RPE target: ≤{today_plan['session_rpe_target']}/10</p>",
    unsafe_allow_html=True,
)

# Overall day progress
ex_idx = st.session_state.tp_ex_idx
if st.session_state.tp_done_today:
    ex_idx = n_ex
st.progress(ex_idx / n_ex, text=f"{ex_idx}/{n_ex} exercises complete")
st.divider()

# ── Session done for today ─────────────────────────────────────────────────────
if st.session_state.tp_done_today:
    st.success(
        f"**Day {day_num} session complete!**\n\n"
        "Log your pain score and session notes in the **Morning Check-In** or **Training Entry** pages "
        "before you finish. See you tomorrow."
    )
    if day_num < 14:
        next_plan = tp.PLAN[day_num + 1]
        with st.expander(f"Preview: Day {day_num + 1} — {next_plan['objective']}", expanded=False):
            for nex in next_plan["exercises"]:
                st.markdown(f"- {_type_icon(nex)} **{nex['name']}** — {_prescription_label(nex)}")
    if st.button("Reset session (redo today)", use_container_width=True):
        _reset_session()
        st.rerun()
    st.stop()

# ── Exercise list sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Today's Exercises")
    for i, ex in enumerate(exercises):
        done   = i < st.session_state.tp_ex_idx
        active = i == st.session_state.tp_ex_idx
        icon   = "✅" if done else ("▶" if active else "○")
        color  = "#00D4AA" if active else ("#444" if not done else "#666")
        st.markdown(
            f"<div style='color:{color}; font-size:13px; padding:3px 0;'>"
            f"{icon} {ex['name']}</div>",
            unsafe_allow_html=True,
        )

# ── Active exercise ────────────────────────────────────────────────────────────
if st.session_state.tp_ex_idx >= n_ex:
    st.session_state.tp_done_today = True
    st.rerun()

ex   = exercises[st.session_state.tp_ex_idx]
ex_n = st.session_state.tp_ex_idx + 1   # 1-indexed for display

# Exercise header
st.markdown(
    f"<div style='background:#1A1F2E; border-left:4px solid #00D4AA; "
    f"border-radius:8px; padding:16px 20px; margin-bottom:12px;'>"
    f"<div style='font-size:11px; color:#00D4AA; font-family:monospace; "
    f"text-transform:uppercase; letter-spacing:2px;'>Exercise {ex_n} of {n_ex}</div>"
    f"<div style='font-size:24px; font-weight:700; color:#E8EAF0; margin:4px 0;'>"
    f"{_type_icon(ex)} {ex['name']}</div>"
    f"<div style='font-size:13px; color:#888; font-family:monospace;'>"
    f"{_prescription_label(ex)}</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# Mechanics cue (always visible — not collapsed — for gym use)
st.markdown(
    f"<div style='background:#0E1117; border:1px solid #333; border-radius:8px; "
    f"padding:14px 16px; margin-bottom:12px; font-size:14px; line-height:1.65; color:#C8CAD0;'>"
    f"<span style='color:#FFD700; font-weight:700; font-size:11px; "
    f"letter-spacing:2px; font-family:monospace;'>MECHANICS &nbsp;</span><br>"
    f"{ex['mechanics']}"
    f"</div>",
    unsafe_allow_html=True,
)

# Warning banner (for exercises like sciatic floss)
if ex.get("warning"):
    st.error(f"⚠️ {ex['warning']}")

# ── Set progress and timers ────────────────────────────────────────────────────
ex_type   = ex["type"]
cur_set   = st.session_state.tp_set
total_sets = ex.get("sets", 1)
cur_rep   = st.session_state.tp_rep_in_set

col_prog, col_timer = st.columns([1, 2], gap="large")

with col_prog:
    if ex_type == "duration":
        st.markdown(
            f"<div style='text-align:center; padding:12px;'>"
            f"<div style='font-size:11px; color:#888; font-family:monospace; letter-spacing:2px;'>DURATION</div>"
            f"<div style='font-size:48px; font-weight:700; color:#FFD700;'>{ex['duration_minutes']}</div>"
            f"<div style='font-size:13px; color:#888;'>minutes</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='text-align:center; padding:8px;'>"
            f"<div style='font-size:11px; color:#888; font-family:monospace; letter-spacing:2px;'>SET</div>"
            f"<div style='font-size:56px; font-weight:700; color:#E8EAF0; line-height:1;'>"
            f"{cur_set}<span style='font-size:28px; color:#555;'>/{total_sets}</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if ex_type == "hold_reps" and ex.get("reps_in_set"):
            st.markdown(
                f"<div style='text-align:center;'>"
                f"<div style='font-size:11px; color:#888; font-family:monospace; letter-spacing:2px;'>REP</div>"
                f"<div style='font-size:40px; font-weight:700; color:#00D4AA; line-height:1;'>"
                f"{cur_rep}<span style='font-size:22px; color:#555;'>/{ex['reps_in_set']}</span></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        if ex_type == "reps":
            st.markdown(
                f"<div style='text-align:center; margin-top:8px;'>"
                f"<div style='font-size:11px; color:#888; font-family:monospace; letter-spacing:2px;'>REPS</div>"
                f"<div style='font-size:48px; font-weight:700; color:#E8EAF0; line-height:1;'>{ex['reps']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if ex.get("tempo"):
                ec, p, cn = (ex["tempo"].split("-") + ["?","?","?"])[:3]
                st.markdown(
                    f"<div style='text-align:center; margin-top:6px;'>"
                    f"<span style='font-size:11px; color:#888; font-family:monospace;'>"
                    f"TEMPO: {ec}s lower · {p}s pause · {cn}s lift</span></div>",
                    unsafe_allow_html=True,
                )

with col_timer:
    phase = st.session_state.tp_phase

    # Duration exercise — just show activity timer
    if ex_type == "duration":
        _duration_timer(ex["duration_minutes"])
        if st.button("✓ Activity Complete", type="primary", use_container_width=True):
            st.session_state.tp_ex_idx += 1
            st.session_state.tp_set = 1
            st.session_state.tp_rep_in_set = 1
            st.session_state.tp_phase = "intro"
            st.rerun()

    # Reps exercise — rest timer after each set
    elif ex_type == "reps":
        if phase == "resting":
            _rest_timer(ex["rest_seconds"])
            if st.button("→ Next Set", type="primary", use_container_width=True):
                st.session_state.tp_phase = "intro"
                st.rerun()
        else:
            st.markdown(
                f"<div style='background:#1A1F2E; border-radius:8px; padding:20px; text-align:center;'>"
                f"<div style='color:#888; font-size:13px; margin-bottom:8px;'>Perform {ex['reps']} reps</div>"
                f"<div style='color:#E8EAF0; font-size:12px;'>"
                + (f"Tempo: {ex['tempo'].replace('-','s – ')}s" if ex.get("tempo") else "Control each rep") +
                f"</div></div>",
                unsafe_allow_html=True,
            )
            if st.button(f"✓ Set {cur_set} Complete", type="primary", use_container_width=True):
                if cur_set >= total_sets:
                    st.session_state.tp_ex_idx += 1
                    st.session_state.tp_set = 1
                    st.session_state.tp_phase = "intro"
                else:
                    st.session_state.tp_set += 1
                    st.session_state.tp_phase = "resting"
                st.rerun()

    # Single isometric hold
    elif ex_type == "hold":
        if phase == "resting":
            _rest_timer(ex["rest_seconds"])
            if st.button("→ Next Set", type="primary", use_container_width=True):
                st.session_state.tp_phase = "intro"
                st.rerun()
        else:
            sides_label = "HOLD — each side" if ex["laterality"] == "unilateral" else "HOLD"
            _hold_timer(ex["hold_seconds"], label=sides_label)
            if st.button(f"✓ Set {cur_set} Complete", type="primary", use_container_width=True):
                if cur_set >= total_sets:
                    st.session_state.tp_ex_idx += 1
                    st.session_state.tp_set = 1
                    st.session_state.tp_phase = "intro"
                else:
                    st.session_state.tp_set += 1
                    st.session_state.tp_phase = "resting"
                st.rerun()

    # Hold reps (X reps × Y-second hold per rep)
    elif ex_type == "hold_reps":
        reps_per_set = ex.get("reps_in_set", 5)
        if phase == "resting":
            _rest_timer(ex["rest_seconds"])
            if st.button("→ Next Set", type="primary", use_container_width=True):
                st.session_state.tp_rep_in_set = 1
                st.session_state.tp_phase = "intro"
                st.rerun()
        else:
            _hold_timer(ex["hold_seconds"], label=f"REP {cur_rep} of {reps_per_set}")
            if st.button(f"✓ Rep {cur_rep} Done", type="primary", use_container_width=True):
                if cur_rep >= reps_per_set:
                    # Completed all reps in this set
                    if cur_set >= total_sets:
                        st.session_state.tp_ex_idx += 1
                        st.session_state.tp_set = 1
                        st.session_state.tp_rep_in_set = 1
                        st.session_state.tp_phase = "intro"
                    else:
                        st.session_state.tp_set += 1
                        st.session_state.tp_rep_in_set = 1
                        st.session_state.tp_phase = "resting"
                else:
                    st.session_state.tp_rep_in_set += 1
                st.rerun()

# ── Clinical guidance section ──────────────────────────────────────────────────
st.divider()
col_bio, col_prog_reg = st.columns(2, gap="large")

with col_bio:
    st.markdown(
        f"<div style='background:#0E1117; border:1px solid #222; border-radius:8px; padding:14px;'>"
        f"<div style='font-size:10px; color:#00D4AA; font-family:monospace; "
        f"letter-spacing:2px; margin-bottom:6px;'>BIOMECHANICAL FOCUS</div>"
        f"<div style='font-size:13px; color:#C8CAD0; line-height:1.55;'>{ex['biomechanical_focus']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

with col_prog_reg:
    st.markdown(
        f"<div style='background:#0E1117; border:1px solid #222; border-radius:8px; padding:14px;'>"
        f"<div style='font-size:10px; color:#00D4AA; font-family:monospace; "
        f"letter-spacing:2px; margin-bottom:6px;'>PROGRESSION / REGRESSION</div>"
        f"<div style='font-size:12px; color:#C8CAD0; line-height:1.5;'>"
        f"<span style='color:#00D4AA;'>▲ Progress if:</span> {ex['progression']}<br><br>"
        f"<span style='color:#FF4B4B;'>▼ Regress if:</span> {ex['regression']}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

# ── Skip exercise option ───────────────────────────────────────────────────────
with st.expander("Skip this exercise", expanded=False):
    st.caption("Only skip if pain prevents performance. Log the reason in session notes.")
    if st.button("Skip — move to next exercise", use_container_width=True):
        st.session_state.tp_ex_idx += 1
        st.session_state.tp_set = 1
        st.session_state.tp_rep_in_set = 1
        st.session_state.tp_phase = "intro"
        st.rerun()
