"""
Training Plan — Interactive 14-Day Rehab Session Guide.
Session state persists across navigation — return exactly where you left off.
Timers resume via localStorage. Only completing all exercises or an explicit
Exit (with confirmation) ends the session.
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import date
import db
import engine
import sync_sheets
import training_plan as tp
import styles

st.set_page_config(page_title="Training Plan", layout="wide")
styles.inject_css()


# ─────────────────────────────────────────────────────────────────────────────
#  JavaScript Timer Components — all use localStorage to persist across navigation
# ─────────────────────────────────────────────────────────────────────────────

def _hold_timer(seconds: int, label: str = "HOLD", timer_key: str = "tp_h") -> None:
    """Isometric hold countdown. Saves state to localStorage; auto-resumes on return."""
    components.html(f"""
<div style="text-align:center;padding:12px 0;font-family:monospace;">
  <div style="font-size:13px;color:#00D4AA;letter-spacing:3px;margin-bottom:6px;">{label}</div>
  <div id="hold-num" style="font-size:72px;font-weight:700;color:#00D4AA;
       line-height:1;margin-bottom:12px;transition:color 0.3s;">{seconds}</div>
  <div style="display:flex;gap:10px;justify-content:center;">
    <button id="btn-start" onclick="startHold()" style="
        background:#00D4AA;color:#0E1117;border:none;border-radius:6px;
        padding:10px 24px;font-size:14px;font-weight:700;cursor:pointer;">▶ Start</button>
    <button onclick="resetHold()" style="
        background:#1A1F2E;color:#E8EAF0;border:1px solid #444;
        border-radius:6px;padding:10px 20px;font-size:14px;cursor:pointer;">↺ Reset</button>
  </div>
</div>
<script>
var _total = {seconds};
var _remaining = {seconds};
var _iv;
var _TKEY = "{timer_key}";

function _save(running) {{
  try {{ localStorage.setItem(_TKEY, JSON.stringify({{total:_total,remaining:_remaining,savedAt:Date.now(),running:running}})); }} catch(e) {{}}
}}
function _clear() {{ try {{ localStorage.removeItem(_TKEY); }} catch(e) {{}} }}

// Auto-restore on load
(function() {{
  try {{
    var s = JSON.parse(localStorage.getItem(_TKEY)||'null');
    if (!s || s.total !== _total) return;
    var el = document.getElementById('hold-num');
    if (s.running) {{
      _remaining = Math.max(0, s.remaining - (Date.now()-s.savedAt)/1000);
      if (_remaining <= 0) {{ el.textContent='✓'; el.style.color='#00D4AA'; _clear(); return; }}
      el.textContent = Math.ceil(_remaining);
      startHold();
    }} else {{
      _remaining = s.remaining;
      el.textContent = Math.ceil(_remaining);
    }}
  }} catch(e) {{}}
}})();

function startHold() {{
  clearInterval(_iv); _save(true);
  document.getElementById('btn-start').textContent = '⏸ Pause';
  document.getElementById('btn-start').onclick = pauseHold;
  _iv = setInterval(function() {{
    _remaining = Math.max(0, _remaining - 1);
    var el = document.getElementById('hold-num');
    el.textContent = Math.ceil(_remaining);
    if (_remaining <= 5) {{ el.style.color='#FF4B4B'; el.style.transform='scale(1.1)';
      setTimeout(function(){{ el.style.transform='scale(1)'; }}, 200); }}
    if (_remaining <= 0) {{
      clearInterval(_iv); _clear();
      el.textContent='✓'; el.style.color='#00D4AA';
      document.getElementById('btn-start').textContent='▶ Start';
      document.getElementById('btn-start').onclick=startHold;
    }}
  }}, 1000);
}}
function pauseHold() {{
  clearInterval(_iv); _save(false);
  document.getElementById('btn-start').textContent='▶ Resume';
  document.getElementById('btn-start').onclick=startHold;
}}
function resetHold() {{
  clearInterval(_iv); _clear(); _remaining=_total;
  var el=document.getElementById('hold-num');
  el.textContent=_total; el.style.color='#00D4AA';
  document.getElementById('btn-start').textContent='▶ Start';
  document.getElementById('btn-start').onclick=startHold;
}}
</script>""", height=160)


def _rest_timer(seconds: int, timer_key: str = "tp_r") -> None:
    """Rest period countdown. Auto-starts on entry; saves state to localStorage for resume on return."""
    m, s = divmod(seconds, 60)
    label = f"{m:02d}:{s:02d}"
    components.html(f"""
<div style="text-align:center;padding:10px 0;font-family:monospace;
            background:#1A1F2E;border-radius:10px;margin:4px 0;">
  <div style="font-size:11px;color:#6B7280;letter-spacing:3px;margin-bottom:4px;">REST</div>
  <div id="rest-num" style="font-size:52px;font-weight:700;color:#6B7280;
       line-height:1;margin-bottom:10px;">{label}</div>
  <div style="font-size:11px;color:#6B7280;margin-bottom:10px;">
    breathe — reset — prepare for next set</div>
  <div style="display:flex;gap:8px;justify-content:center;">
    <button id="rest-btn" onclick="startRest()" style="
        background:#6B7280;color:#FFF;border:none;border-radius:6px;
        padding:8px 20px;font-size:13px;cursor:pointer;">⏸ Pause</button>
  </div>
</div>
<script>
var _rtotal = {seconds};
var _rrem   = {seconds};
var _riv;
var _TKEY = "{timer_key}";

function _save(running) {{
  try {{ localStorage.setItem(_TKEY, JSON.stringify({{total:_rtotal,remaining:_rrem,savedAt:Date.now(),running:running}})); }} catch(e) {{}}
}}
function _clear() {{ try {{ localStorage.removeItem(_TKEY); }} catch(e) {{}} }}
function fmt(n) {{ var m=Math.floor(n/60),s=Math.round(n%60); return (m<10?'0':'')+m+':'+(s<10?'0':'')+s; }}

// On load: restore saved state OR auto-start fresh
(function() {{
  try {{
    var s = JSON.parse(localStorage.getItem(_TKEY)||'null');
    if (s && s.total === _rtotal) {{
      var el = document.getElementById('rest-num');
      if (s.running) {{
        _rrem = Math.max(0, s.remaining - (Date.now()-s.savedAt)/1000);
        if (_rrem <= 0) {{
          el.textContent='GO'; el.style.color='#00D4AA'; el.style.fontSize='42px'; _clear(); return;
        }}
        el.textContent=fmt(_rrem); startRest(); return;
      }} else {{
        _rrem = s.remaining; el.textContent=fmt(_rrem);
        document.getElementById('rest-btn').textContent='▶ Resume';
        document.getElementById('rest-btn').onclick=startRest; return;
      }}
    }}
  }} catch(e) {{}}
  // No saved state — auto-start immediately
  startRest();
}})();

function startRest() {{
  clearInterval(_riv); _save(true);
  document.getElementById('rest-btn').textContent='⏸ Pause';
  document.getElementById('rest-btn').onclick=pauseRest;
  _riv = setInterval(function() {{
    _rrem = Math.max(0, _rrem - 1);
    document.getElementById('rest-num').textContent=fmt(_rrem);
    if (_rrem <= 5) {{ document.getElementById('rest-num').style.color='#00D4AA'; }}
    if (_rrem <= 0) {{
      clearInterval(_riv); _clear();
      var el=document.getElementById('rest-num');
      el.textContent='GO'; el.style.color='#00D4AA'; el.style.fontSize='42px';
      document.getElementById('rest-btn').textContent='▶ Restart';
      document.getElementById('rest-btn').onclick=startRest;
    }}
  }}, 1000);
}}
function pauseRest() {{
  clearInterval(_riv); _save(false);
  document.getElementById('rest-btn').textContent='▶ Resume';
  document.getElementById('rest-btn').onclick=startRest;
}}
</script>""", height=145)


def _duration_timer(minutes: int, timer_key: str = "tp_d") -> None:
    """Continuous activity timer. Saves state to localStorage; auto-resumes on return."""
    total = minutes * 60
    label = f"{minutes:02d}:00"
    components.html(f"""
<div style="text-align:center;padding:10px 0;font-family:monospace;">
  <div style="font-size:11px;color:#FFD700;letter-spacing:3px;margin-bottom:4px;">ACTIVITY TIMER</div>
  <div id="dur-num" style="font-size:56px;font-weight:700;color:#FFD700;
       line-height:1;margin-bottom:10px;">{label}</div>
  <button id="dur-btn" onclick="startDur()" style="
      background:#FFD700;color:#0E1117;border:none;border-radius:6px;
      padding:10px 24px;font-size:14px;font-weight:700;cursor:pointer;">
    ▶ Start {minutes}min Timer</button>
</div>
<script>
var _dtotal = {total};
var _drem   = {total};
var _div;
var _TKEY = "{timer_key}";

function _save(running) {{
  try {{ localStorage.setItem(_TKEY, JSON.stringify({{total:_dtotal,remaining:_drem,savedAt:Date.now(),running:running}})); }} catch(e) {{}}
}}
function _clear() {{ try {{ localStorage.removeItem(_TKEY); }} catch(e) {{}} }}
function fmt(n) {{ var m=Math.floor(n/60),s=Math.round(n%60); return (m<10?'0':'')+m+':'+(s<10?'0':'')+s; }}

// Auto-restore on load
(function() {{
  try {{
    var s = JSON.parse(localStorage.getItem(_TKEY)||'null');
    if (!s || s.total !== _dtotal) return;
    var el = document.getElementById('dur-num');
    if (s.running) {{
      _drem = Math.max(0, s.remaining - (Date.now()-s.savedAt)/1000);
      if (_drem <= 0) {{ el.textContent='DONE ✓'; el.style.color='#00D4AA'; _clear(); return; }}
      el.textContent=fmt(_drem); startDur();
    }} else {{
      _drem = s.remaining; el.textContent=fmt(_drem);
    }}
  }} catch(e) {{}}
}})();

function startDur() {{
  clearInterval(_div); _save(true);
  document.getElementById('dur-btn').textContent='⏸ Pause';
  document.getElementById('dur-btn').onclick=pauseDur;
  _div = setInterval(function() {{
    _drem = Math.max(0, _drem - 1);
    document.getElementById('dur-num').textContent=fmt(_drem);
    if (_drem <= 30) {{ document.getElementById('dur-num').style.color='#00D4AA'; }}
    if (_drem <= 0) {{
      clearInterval(_div); _clear();
      document.getElementById('dur-num').textContent='DONE ✓';
      document.getElementById('dur-btn').textContent='▶ Restart';
      document.getElementById('dur-btn').onclick=function(){{_drem=_dtotal;startDur();}};
    }}
  }}, 1000);
}}
function pauseDur() {{
  clearInterval(_div); _save(false);
  document.getElementById('dur-btn').textContent='▶ Resume';
  document.getElementById('dur-btn').onclick=startDur;
}}
</script>""", height=140)


# ─────────────────────────────────────────────────────────────────────────────
#  Session State
# ─────────────────────────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "tp_ex_idx":         0,
        "tp_set":            1,
        "tp_rep_in_set":     1,
        "tp_phase":          "intro",
        "tp_done_today":     False,
        "tp_session_logged": False,
        "tp_exit_confirm":   False,   # True → show exit confirmation screen
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_session():
    for k in list(st.session_state.keys()):
        if k.startswith("tp_"):
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
    return {"hold": "⏱", "hold_reps": "⏱", "reps": "↕", "duration": "🚶"}.get(ex["type"], "•")


# ─────────────────────────────────────────────────────────────────────────────
#  Auto-logging Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _movement_category(ex: dict) -> str:
    name = ex["name"].lower()
    if any(k in name for k in ("walk", "breath", "diaphragm")):
        return "Conditioning"
    if any(k in name for k in ("glute bridge", "rdl", "hinge", "deadlift")):
        return "Hip Hinge"
    if any(k in name for k in ("bird", "plank", "curl-up", "curl up", "side lying",
                                "dead bug", "pallof")):
        return "Core Stability"
    if any(k in name for k in ("squat", "lunge", "step")):
        return "Squat Pattern"
    return "Mobility"


def _planned_reps(ex: dict) -> int:
    t = ex["type"]
    if t == "reps":       return ex.get("reps") or 1
    if t == "hold_reps":  return ex.get("reps_in_set") or 1
    return 1


def _make_sets_data(ex: dict) -> list[dict]:
    t, sets, rest = ex["type"], ex.get("sets", 1), ex.get("rest_seconds", 60)
    out = []
    if t == "duration":
        out.append({"set_num": 1, "reps": 1, "weight": 0.0, "rest": 0,
                    "tut": (ex.get("duration_minutes") or 0) * 60, "velocity": "continuous"})
    elif t == "reps":
        for i in range(1, sets + 1):
            out.append({"set_num": i, "reps": ex.get("reps") or 1, "weight": 0.0,
                        "rest": rest, "tut": 0, "velocity": "controlled"})
    elif t == "hold":
        for i in range(1, sets + 1):
            out.append({"set_num": i, "reps": 1, "weight": 0.0,
                        "rest": rest, "tut": ex.get("hold_seconds") or 0, "velocity": "isometric"})
    elif t == "hold_reps":
        for i in range(1, sets + 1):
            out.append({"set_num": i, "reps": ex.get("reps_in_set") or 1, "weight": 0.0,
                        "rest": rest, "tut": ex.get("hold_seconds") or 0, "velocity": "isometric"})
    return out


def _estimate_duration(exercises: list) -> int:
    total = 120
    for ex in exercises:
        t, sets, rest = ex["type"], ex.get("sets", 1), ex.get("rest_seconds", 60)
        if t == "duration":       total += (ex.get("duration_minutes") or 0) * 60 + 30
        elif t == "hold":         total += sets * (ex.get("hold_seconds") or 0) + (sets - 1) * rest + 30
        elif t == "hold_reps":    total += sets * (ex.get("hold_seconds") or 0) * (ex.get("reps_in_set") or 1) + (sets - 1) * rest + 30
        elif t == "reps":         total += sets * 20 + (sets - 1) * rest + 30
    return max(10, round(total / 60))


def _auto_log_session(day_num: int, exercises: list, session_rpe: int,
                      duration_minutes: int, notes: str) -> None:
    session_info = db.create_training_session(
        session_date=date.today(),
        duration_minutes=duration_minutes,
        session_rpe=session_rpe,
    )
    last_id = None
    for ex in exercises:
        last_id = db.save_training_exercise(
            session_id=session_info["session_id"],
            movement_name=ex["name"],
            movement_type=_movement_category(ex),
            planned_sets=ex.get("sets", 1),
            planned_reps=_planned_reps(ex),
            rpe=session_rpe,
            sets=_make_sets_data(ex),
            note="",
            session_date=session_info["session_date"],
            session_duration_minutes=session_info["duration_minutes"],
            session_rpe=session_info["session_rpe"],
            session_au=session_info["session_au"],
        )
    if notes.strip() and last_id:
        db.save_session_notes(last_id, notes)


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
    start_input = st.date_input("Plan start date", value=date.today(),
                                help="You can backdate if you've already started.")
    if st.button("Begin 14-Day Plan", type="primary", use_container_width=True):
        db.set_config("plan_start_date", str(start_input))
        st.success(f"Plan starts {start_input}. Come back each day for your session.")
        st.rerun()
    st.stop()

# ── Calculate current day ──────────────────────────────────────────────────────
day_num = _get_day_number(plan_start)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Plan Status")
    st.metric("Plan Start", str(plan_start))
    st.metric("Today", str(date.today()))
    if 1 <= day_num <= 14:
        st.metric("Current Day", f"Day {day_num} of 14")
        st.progress(day_num / 14, text=f"{int(day_num/14*100)}% complete")
    st.divider()

    # ── Exit Training button — only shown during an active in-progress session ──
    session_active = (
        1 <= day_num <= 14
        and not st.session_state.tp_done_today
        and st.session_state.tp_ex_idx > 0  # at least one exercise started
    )
    if session_active:
        st.markdown(
            "<div style='background:#150808;border:1px solid #FF2D44;border-radius:8px;"
            "padding:10px 12px;margin-bottom:10px;'>"
            "<div style='font-size:10px;color:#FF2D44;letter-spacing:1px;margin-bottom:4px;'>"
            "SESSION IN PROGRESS</div>"
            "<div style='font-size:11px;color:#888;'>Navigate freely — your place is saved.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Exit Training", use_container_width=True):
            st.session_state.tp_exit_confirm = True
            st.rerun()
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
        "Open **Autoregulation** to check Stage 1 → 2 progression criteria. "
        "If criteria are met, confirm with your physiotherapist before advancing."
    )
    st.stop()

# ── Engine directive banner ────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def _engine_directive() -> dict:
    try:
        sheet_id = st.secrets.get("GOOGLE_SHEETS_ID", "")
        bio      = sync_sheets.get_biometric_rolling(sheet_id, 28) if sheet_id else []
        au       = db.get_daily_session_au(28)
        diag     = db.get_diagnostic_profile()
        stage    = db.get_current_stage()
        streak   = db.get_pain_free_streak()
        tight    = db.get_avg_tightness(14)
        lam      = float(diag.get("injury_weight_decay_lambda") or 0.05)
        tl       = engine.traffic_light(bio)
        acwr_r   = engine.acwr(au, stage)
        inj_w    = engine.injury_weight(lam, streak)
        obs_rem  = engine.observation_days_remaining(tl["data_days"])
        return engine.volume_recommendation(tl, acwr_r, stage, obs_rem, inj_w)
    except Exception:
        return {"signal_color": "grey", "label": "", "action": "", "multiplier": 1.0}

_directive = _engine_directive()
_sig = _directive["signal_color"]
if _sig == "red":
    st.error("Rest day recommended today — mobility and walking only. No loaded exercises.")
elif _sig in ("yellow", "orange"):
    st.warning("Reduced load today — keep this session controlled. Don't push to failure.")
# green / grey: no banner — train normally, nothing to flag

# ── Active plan day ────────────────────────────────────────────────────────────
today_plan = tp.PLAN[day_num]
exercises  = today_plan["exercises"]
n_ex       = len(exercises)

# ── EXIT CONFIRMATION SCREEN ──────────────────────────────────────────────────
if st.session_state.tp_exit_confirm:
    ex_done = st.session_state.tp_ex_idx
    st.markdown(
        f"<div style='background:#0E0A0A;border:2px solid #FF2D44;border-radius:12px;"
        f"padding:28px 32px;margin:24px 0;text-align:center;'>"
        f"<div style='font-size:13px;color:#FF2D44;letter-spacing:2px;font-family:monospace;"
        f"margin-bottom:10px;'>EXIT TRAINING</div>"
        f"<div style='font-size:22px;font-weight:700;color:#FFFFFF;margin-bottom:8px;'>"
        f"Are you sure you want to leave?</div>"
        f"<div style='font-size:14px;color:#888;line-height:1.6;'>"
        f"You've completed <strong style='color:#FFFFFF;'>{ex_done} of {n_ex}</strong> exercises today.<br>"
        f"Your progress is saved — you can <strong>return and continue at any time</strong>.<br>"
        f"To fully exit and discard today's progress, click below."
        f"</div></div>",
        unsafe_allow_html=True,
    )
    col_back, col_exit = st.columns(2, gap="large")
    with col_back:
        if st.button("↩  Continue Training", type="primary", use_container_width=True):
            st.session_state.tp_exit_confirm = False
            st.rerun()
    with col_exit:
        if st.button("Exit & Discard Progress", use_container_width=True):
            _reset_session()
            st.rerun()
    st.stop()

# Header
st.markdown(
    f"<h2 style='margin-bottom:2px;'>Day {day_num} of 14</h2>"
    f"<p style='color:#00D4AA;font-family:monospace;font-size:15px;margin-top:0;'>"
    f"{today_plan['objective']}</p>"
    f"<p style='color:#888;font-size:13px;'>{today_plan['phase']} — RPE target: ≤{today_plan['session_rpe_target']}/10</p>",
    unsafe_allow_html=True,
)

# Overall day progress bar
ex_idx = n_ex if st.session_state.tp_done_today else st.session_state.tp_ex_idx
st.progress(ex_idx / n_ex, text=f"{ex_idx}/{n_ex} exercises complete")
st.divider()

# ── Session done for today ─────────────────────────────────────────────────────
if st.session_state.tp_done_today:

    if not st.session_state.tp_session_logged:
        st.markdown(
            f"<div style='background:#071410;border-left:4px solid #00E874;"
            f"border-radius:8px;padding:16px 20px;margin-bottom:16px;'>"
            f"<div style='font-size:11px;color:#00E874;font-family:monospace;"
            f"letter-spacing:2px;margin-bottom:4px;'>DAY {day_num} COMPLETE</div>"
            f"<div style='font-size:20px;font-weight:700;color:#FFFFFF;'>"
            f"All {n_ex} exercises done — save your session.</div></div>",
            unsafe_allow_html=True,
        )
        est = _estimate_duration(exercises)
        with st.form("log_session_form"):
            col_rpe, col_dur = st.columns(2, gap="large")
            with col_rpe:
                session_rpe = st.slider("Session RPE — how hard did it feel?",
                                        min_value=1, max_value=10, value=5,
                                        help="1 = very easy  ·  10 = maximal effort")
                st.caption(f"Estimated AU: **{session_rpe * est}** (RPE × {est} min)")
            with col_dur:
                duration = st.number_input("Session Duration (minutes)",
                                           min_value=5, max_value=120, value=est,
                                           help="Adjust if actual time differed from estimate.")
            session_notes = st.text_area(
                "Session Notes (optional)",
                placeholder="e.g. Hip flexors felt looser. Slight tightness on last bird-dog set.",
                height=80,
            )
            save_btn = st.form_submit_button("Save Session to Log",
                                             type="primary", use_container_width=True)
        if save_btn:
            with st.spinner("Saving session to Notion…"):
                _auto_log_session(day_num, exercises, session_rpe, int(duration), session_notes)
            st.session_state.tp_session_logged = True
            st.rerun()

    else:
        st.success(
            f"**Day {day_num} session logged.**  "
            "Open Morning Check-In to record your pain score. See you tomorrow."
        )
        if day_num < 14:
            next_plan = tp.PLAN[day_num + 1]
            with st.expander(f"Preview: Day {day_num + 1} — {next_plan['objective']}", expanded=False):
                for nex in next_plan["exercises"]:
                    st.markdown(f"- {_type_icon(nex)} **{nex['name']}** — {_prescription_label(nex)}")
        if st.button("Redo today's session", use_container_width=True):
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
        color  = "#00D4AA" if active else ("#666" if done else "#444")
        st.markdown(
            f"<div style='color:{color};font-size:13px;padding:3px 0;'>"
            f"{icon} {ex['name']}</div>",
            unsafe_allow_html=True,
        )

# ── Active exercise ────────────────────────────────────────────────────────────
if st.session_state.tp_ex_idx >= n_ex:
    st.session_state.tp_done_today = True
    st.rerun()

ex   = exercises[st.session_state.tp_ex_idx]
ex_n = st.session_state.tp_ex_idx + 1

# Unique timer keys scoped to this exercise / set / rep
_eidx = st.session_state.tp_ex_idx
_eset = st.session_state.tp_set
_erep = st.session_state.tp_rep_in_set
_hold_key     = f"tp_h_{_eidx}_{_eset}_{_erep}"
_rest_key     = f"tp_r_{_eidx}_{_eset}"
_dur_key      = f"tp_d_{_eidx}"

# Exercise header
st.markdown(
    f"<div style='background:#1A1F2E;border-left:4px solid #00D4AA;"
    f"border-radius:8px;padding:16px 20px;margin-bottom:12px;'>"
    f"<div style='font-size:11px;color:#00D4AA;font-family:monospace;"
    f"text-transform:uppercase;letter-spacing:2px;'>Exercise {ex_n} of {n_ex}</div>"
    f"<div style='font-size:24px;font-weight:700;color:#E8EAF0;margin:4px 0;'>"
    f"{_type_icon(ex)} {ex['name']}</div>"
    f"<div style='font-size:13px;color:#888;font-family:monospace;'>"
    f"{_prescription_label(ex)}</div></div>",
    unsafe_allow_html=True,
)

# Mechanics cue
st.markdown(
    f"<div style='background:#0E1117;border:1px solid #333;border-radius:8px;"
    f"padding:14px 16px;margin-bottom:12px;font-size:14px;line-height:1.65;color:#C8CAD0;'>"
    f"<span style='color:#FFD700;font-weight:700;font-size:11px;"
    f"letter-spacing:2px;font-family:monospace;'>MECHANICS &nbsp;</span><br>"
    f"{ex['mechanics']}</div>",
    unsafe_allow_html=True,
)

if ex.get("warning"):
    st.error(f"⚠️ {ex['warning']}")

# ── Set progress and timers ────────────────────────────────────────────────────
ex_type    = ex["type"]
cur_set    = st.session_state.tp_set
total_sets = ex.get("sets", 1)
cur_rep    = st.session_state.tp_rep_in_set

col_prog, col_timer = st.columns([1, 2], gap="large")

with col_prog:
    if ex_type == "duration":
        st.markdown(
            f"<div style='text-align:center;padding:12px;'>"
            f"<div style='font-size:11px;color:#888;font-family:monospace;letter-spacing:2px;'>DURATION</div>"
            f"<div style='font-size:48px;font-weight:700;color:#FFD700;'>{ex['duration_minutes']}</div>"
            f"<div style='font-size:13px;color:#888;'>minutes</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='text-align:center;padding:8px;'>"
            f"<div style='font-size:11px;color:#888;font-family:monospace;letter-spacing:2px;'>SET</div>"
            f"<div style='font-size:56px;font-weight:700;color:#E8EAF0;line-height:1;'>"
            f"{cur_set}<span style='font-size:28px;color:#555;'>/{total_sets}</span></div></div>",
            unsafe_allow_html=True,
        )
        if ex_type == "hold_reps" and ex.get("reps_in_set"):
            st.markdown(
                f"<div style='text-align:center;'>"
                f"<div style='font-size:11px;color:#888;font-family:monospace;letter-spacing:2px;'>REP</div>"
                f"<div style='font-size:40px;font-weight:700;color:#00D4AA;line-height:1;'>"
                f"{cur_rep}<span style='font-size:22px;color:#555;'>/{ex['reps_in_set']}</span></div></div>",
                unsafe_allow_html=True,
            )
        if ex_type == "reps":
            st.markdown(
                f"<div style='text-align:center;margin-top:8px;'>"
                f"<div style='font-size:11px;color:#888;font-family:monospace;letter-spacing:2px;'>REPS</div>"
                f"<div style='font-size:48px;font-weight:700;color:#E8EAF0;line-height:1;'>{ex['reps']}</div></div>",
                unsafe_allow_html=True,
            )
            if ex.get("tempo"):
                ec, p, cn = (ex["tempo"].split("-") + ["?", "?", "?"])[:3]
                st.markdown(
                    f"<div style='text-align:center;margin-top:6px;'>"
                    f"<span style='font-size:11px;color:#888;font-family:monospace;'>"
                    f"TEMPO: {ec}s lower · {p}s pause · {cn}s lift</span></div>",
                    unsafe_allow_html=True,
                )

with col_timer:
    phase = st.session_state.tp_phase

    if ex_type == "duration":
        _duration_timer(ex["duration_minutes"], timer_key=_dur_key)
        if st.button("✓ Activity Complete", type="primary", use_container_width=True):
            st.session_state.tp_ex_idx += 1
            st.session_state.tp_set = 1
            st.session_state.tp_rep_in_set = 1
            st.session_state.tp_phase = "intro"
            st.rerun()

    elif ex_type == "reps":
        if phase == "resting":
            _rest_timer(ex["rest_seconds"], timer_key=_rest_key)
            if st.button("→ Next Set", type="primary", use_container_width=True):
                st.session_state.tp_phase = "intro"
                st.rerun()
        else:
            st.markdown(
                f"<div style='background:#1A1F2E;border-radius:8px;padding:20px;text-align:center;'>"
                f"<div style='color:#888;font-size:13px;margin-bottom:8px;'>Perform {ex['reps']} reps</div>"
                f"<div style='color:#E8EAF0;font-size:12px;'>"
                + (f"Tempo: {ex['tempo'].replace('-','s – ')}s" if ex.get("tempo") else "Control each rep")
                + "</div></div>",
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

    elif ex_type == "hold":
        if phase == "resting":
            _rest_timer(ex["rest_seconds"], timer_key=_rest_key)
            if st.button("→ Next Set", type="primary", use_container_width=True):
                st.session_state.tp_phase = "intro"
                st.rerun()
        else:
            sides_label = "HOLD — each side" if ex["laterality"] == "unilateral" else "HOLD"
            _hold_timer(ex["hold_seconds"], label=sides_label, timer_key=_hold_key)
            if st.button(f"✓ Set {cur_set} Complete", type="primary", use_container_width=True):
                if cur_set >= total_sets:
                    st.session_state.tp_ex_idx += 1
                    st.session_state.tp_set = 1
                    st.session_state.tp_phase = "intro"
                else:
                    st.session_state.tp_set += 1
                    st.session_state.tp_phase = "resting"
                st.rerun()

    elif ex_type == "hold_reps":
        reps_per_set = ex.get("reps_in_set", 5)
        if phase == "resting":
            _rest_timer(ex["rest_seconds"], timer_key=_rest_key)
            if st.button("→ Next Set", type="primary", use_container_width=True):
                st.session_state.tp_rep_in_set = 1
                st.session_state.tp_phase = "intro"
                st.rerun()
        else:
            _hold_timer(ex["hold_seconds"], label=f"REP {cur_rep} of {reps_per_set}",
                        timer_key=_hold_key)
            if st.button(f"✓ Rep {cur_rep} Done", type="primary", use_container_width=True):
                if cur_rep >= reps_per_set:
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
        f"<div style='background:#0E1117;border:1px solid #222;border-radius:8px;padding:14px;'>"
        f"<div style='font-size:10px;color:#00D4AA;font-family:monospace;"
        f"letter-spacing:2px;margin-bottom:6px;'>BIOMECHANICAL FOCUS</div>"
        f"<div style='font-size:13px;color:#C8CAD0;line-height:1.55;'>{ex['biomechanical_focus']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

with col_prog_reg:
    st.markdown(
        f"<div style='background:#0E1117;border:1px solid #222;border-radius:8px;padding:14px;'>"
        f"<div style='font-size:10px;color:#00D4AA;font-family:monospace;"
        f"letter-spacing:2px;margin-bottom:6px;'>PROGRESSION / REGRESSION</div>"
        f"<div style='font-size:12px;color:#C8CAD0;line-height:1.5;'>"
        f"<span style='color:#00D4AA;'>▲ Progress if:</span> {ex['progression']}<br><br>"
        f"<span style='color:#FF4B4B;'>▼ Regress if:</span> {ex['regression']}"
        f"</div></div>",
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
