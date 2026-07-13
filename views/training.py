"""
Training Plan — Interactive 14-Day Rehab Session Guide.
Progress persists across navigation and across dropped sessions — return exactly
where you left off. In-session state lives in st.session_state for the active
browser connection, and is checkpointed to Notion (Config DB, key
"training_progress") on every set/rep/exercise transition, so a lost websocket
connection (e.g. phone backgrounded for several minutes) can be restored on
reconnect. Timers resume via localStorage. Only completing all exercises or an
explicit Exit (with confirmation) ends the session.
"""

import streamlit as st
import streamlit.components.v1 as components
from dataclasses import asdict
from datetime import date, timedelta
import json
import time
import nav
import repo
import training_plan as tp
from services import engine
from services import metrics
from services import metrics_logic as ml
from services import plan as ph  # aliased: render()'s guided flow has a local var named `phase`
from services import sessions as sess
from services import yoga as yg


# ─────────────────────────────────────────────────────────────────────────────
#  JavaScript Timer Components — all use localStorage to persist across navigation
# ─────────────────────────────────────────────────────────────────────────────

def _hold_timer(seconds: int, label: str = "HOLD", timer_key: str = "tp_h",
                set_auto_start: bool = False) -> None:
    """Isometric hold countdown. Auto-completes at 0 (clicks the ✓ button in parent).
    set_auto_start=True writes tp_auto_start to localStorage so the NEXT hold timer
    (same exercise, next rep/side) auto-starts without a button press.
    Reads tp_auto_start on load to auto-start when flagged by rest timer or previous hold."""
    _flag_js = "try { localStorage.setItem('tp_auto_start', '1'); } catch(e) {}" if set_auto_start else ""
    components.html(f"""
<div style="text-align:center;padding:12px 0;font-family:monospace;">
  <div style="font-size:13px;color:#E8ECEF;letter-spacing:3px;margin-bottom:6px;">{label}</div>
  <div id="hold-num" style="font-size:72px;font-weight:700;color:#E8ECEF;
       line-height:1;margin-bottom:12px;transition:color 0.3s;">{seconds}</div>
  <div style="display:flex;gap:10px;justify-content:center;">
    <button id="btn-start" onclick="startHold()" style="
        background:#E8ECEF;color:#0E1117;border:none;border-radius:6px;
        padding:10px 24px;font-size:14px;font-weight:700;cursor:pointer;">▶ Start</button>
    <button onclick="resetHold()" style="
        background:#1A2026;color:#E8ECEF;border:1px solid #444;
        border-radius:6px;padding:10px 20px;font-size:14px;cursor:pointer;">↺ Reset</button>
  </div>
</div>
<script>
var _total = {seconds};
var _remaining = {seconds};
var _iv;
var _beeped = {{}};
var _TKEY = "{timer_key}";

function _beep(freq, dur, vol) {{
  try {{
    var ctx = window._audioCtx || (window._audioCtx = new (window.AudioContext || window.webkitAudioContext)());
    if (ctx.state === 'suspended') ctx.resume();
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.type = 'sine'; o.frequency.value = freq;
    g.gain.setValueAtTime(vol || 0.35, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
    o.start(ctx.currentTime); o.stop(ctx.currentTime + dur);
  }} catch(e) {{}}
}}
function _tickBeep() {{ _beep(880, 0.12, 0.35); }}
function _doneBeep() {{
  _beep(660, 0.18, 0.5);
  setTimeout(function() {{ _beep(880, 0.28, 0.65); }}, 220);
}}

function _save(running) {{
  try {{ localStorage.setItem(_TKEY, JSON.stringify({{total:_total,remaining:_remaining,savedAt:Date.now(),running:running}})); }} catch(e) {{}}
}}
function _clear() {{ try {{ localStorage.removeItem(_TKEY); }} catch(e) {{}} }}

function _autoComplete() {{
  try {{
    var btns = window.parent.document.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {{
      // Match the guided-flow's own completion buttons ("✓ Set 2 Complete",
      // "✓ Right Side Done", "✓ Rep 3 Done", "✓ Activity Complete") — not just
      // any "✓"-leading button. The week day-strip's completed-day buttons
      // (e.g. "✓ Mon") also start with "✓" and render earlier in the page,
      // so a bare "starts with ✓" match was clicking those instead and
      // navigating away to that day.
      var t = btns[i].textContent.trim();
      if (t.charAt(0) === '✓' && (t.includes('Complete') || t.includes('Done'))) {{
        btns[i].click(); return;
      }}
    }}
  }} catch(e) {{}}
}}

// Auto-restore on load; auto-start if flagged by rest timer or previous hold/rep
(function() {{
  try {{
    if (localStorage.getItem('tp_auto_start')) {{
      localStorage.removeItem('tp_auto_start');
      startHold(); return;
    }}
  }} catch(e) {{}}
  try {{
    var s = JSON.parse(localStorage.getItem(_TKEY)||'null');
    if (!s || s.total !== _total) return;
    var el = document.getElementById('hold-num');
    if (s.running) {{
      _remaining = Math.max(0, s.remaining - (Date.now()-s.savedAt)/1000);
      if (_remaining <= 0) {{ el.textContent='✓'; el.style.color='#E8ECEF'; _clear(); return; }}
      el.textContent = Math.ceil(_remaining);
      startHold();
    }} else {{
      _remaining = s.remaining;
      el.textContent = Math.ceil(_remaining);
    }}
  }} catch(e) {{}}
}})();

function startHold() {{
  clearInterval(_iv); _beeped={{}}; _save(true);
  document.getElementById('btn-start').textContent = '⏸ Pause';
  document.getElementById('btn-start').onclick = pauseHold;
  _iv = setInterval(function() {{
    _remaining = Math.max(0, _remaining - 1);
    var r = Math.round(_remaining);
    var el = document.getElementById('hold-num');
    el.textContent = Math.ceil(_remaining);
    if (_remaining <= 3) {{ el.style.color='#FF4B4B'; el.style.transform='scale(1.1)';
      setTimeout(function(){{ el.style.transform='scale(1)'; }}, 200); }}
    if (r >= 1 && r <= 3 && !_beeped[r]) {{ _beeped[r]=true; _tickBeep(); }}
    if (_remaining <= 0) {{
      clearInterval(_iv); _clear();
      el.textContent='✓'; el.style.color='#E8ECEF';
      document.getElementById('btn-start').textContent='▶ Start';
      document.getElementById('btn-start').onclick=startHold;
      _doneBeep();
      {_flag_js}
      setTimeout(_autoComplete, 700);
    }}
  }}, 1000);
}}
function pauseHold() {{
  clearInterval(_iv); _save(false);
  document.getElementById('btn-start').textContent='▶ Resume';
  document.getElementById('btn-start').onclick=startHold;
}}
function resetHold() {{
  clearInterval(_iv); _clear(); _remaining=_total; _beeped={{}};
  var el=document.getElementById('hold-num');
  el.textContent=_total; el.style.color='#E8ECEF';
  document.getElementById('btn-start').textContent='▶ Start';
  document.getElementById('btn-start').onclick=startHold;
}}
</script>""", height=160)


def _rest_timer(seconds: int, timer_key: str = "tp_r") -> None:
    """Rest countdown. Auto-starts; beeps 3-2-1 then double-ring at 0; auto-advances to next set."""
    m, s = divmod(seconds, 60)
    label = f"{m:02d}:{s:02d}"
    components.html(f"""
<div style="text-align:center;padding:10px 0;font-family:monospace;
            background:#1A2026;border-radius:10px;margin:4px 0;">
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
var _TKEY   = "{timer_key}";
var _beeped = {{}};

function _beep(freq, dur, vol) {{
  try {{
    var ctx = window._audioCtx || (window._audioCtx = new (window.AudioContext || window.webkitAudioContext)());
    if (ctx.state === 'suspended') ctx.resume();
    var o = ctx.createOscillator(), g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.type = 'sine'; o.frequency.value = freq;
    g.gain.setValueAtTime(vol || 0.35, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
    o.start(ctx.currentTime); o.stop(ctx.currentTime + dur);
  }} catch(e) {{}}
}}
function _tickBeep() {{ _beep(880, 0.12, 0.35); }}
function _goBeep()  {{
  _beep(660, 0.18, 0.5);
  setTimeout(function() {{ _beep(880, 0.28, 0.65); }}, 220);
}}

function _autoAdvance() {{
  try {{ localStorage.setItem('tp_auto_start', '1'); }} catch(e) {{}}
  try {{
    var btns = window.parent.document.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {{
      if (btns[i].textContent.trim().includes('Next Set')) {{ btns[i].click(); return; }}
    }}
  }} catch(e) {{}}
}}

function _save(running) {{
  try {{ localStorage.setItem(_TKEY, JSON.stringify({{total:_rtotal,remaining:_rrem,savedAt:Date.now(),running:running}})); }} catch(e) {{}}
}}
function _clear() {{ try {{ localStorage.removeItem(_TKEY); }} catch(e) {{}} }}
function fmt(n) {{ var m=Math.floor(n/60),s=Math.round(n%60); return (m<10?'0':'')+m+':'+(s<10?'0':'')+s; }}

(function() {{
  try {{
    var s = JSON.parse(localStorage.getItem(_TKEY)||'null');
    if (s && s.total === _rtotal) {{
      var el = document.getElementById('rest-num');
      if (s.running) {{
        _rrem = Math.max(0, s.remaining - (Date.now()-s.savedAt)/1000);
        if (_rrem <= 0) {{ el.textContent='GO'; el.style.color='#E8ECEF'; el.style.fontSize='42px'; _clear(); return; }}
        el.textContent=fmt(_rrem); startRest(); return;
      }} else {{
        _rrem = s.remaining; el.textContent=fmt(_rrem);
        document.getElementById('rest-btn').textContent='▶ Resume';
        document.getElementById('rest-btn').onclick=startRest; return;
      }}
    }}
  }} catch(e) {{}}
  startRest();
}})();

function startRest() {{
  clearInterval(_riv); _beeped={{}}; _save(true);
  document.getElementById('rest-btn').textContent='⏸ Pause';
  document.getElementById('rest-btn').onclick=pauseRest;
  _riv = setInterval(function() {{
    _rrem = Math.max(0, _rrem - 1);
    var r = Math.round(_rrem);
    document.getElementById('rest-num').textContent = fmt(_rrem);
    if (_rrem <= 5) {{ document.getElementById('rest-num').style.color='#E8ECEF'; }}
    if (r >= 1 && r <= 3 && !_beeped[r]) {{ _beeped[r]=true; _tickBeep(); }}
    if (_rrem <= 0) {{
      clearInterval(_riv); _clear();
      var el = document.getElementById('rest-num');
      el.textContent='GO'; el.style.color='#E8ECEF'; el.style.fontSize='42px';
      document.getElementById('rest-btn').textContent='▶ Restart';
      document.getElementById('rest-btn').onclick=function(){{ _beeped={{}}; _rrem=_rtotal; startRest(); }};
      _goBeep();
      setTimeout(_autoAdvance, 900);
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
      if (_drem <= 0) {{ el.textContent='DONE ✓'; el.style.color='#E8ECEF'; _clear(); return; }}
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
    if (_drem <= 30) {{ document.getElementById('dur-num').style.color='#E8ECEF'; }}
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

def _save_checkpoint(day_num: int) -> None:
    """Persist in-progress training state to Notion so it survives a dropped
    Streamlit session (e.g. phone backgrounded for several minutes) — session_state
    alone only lives as long as the browser's websocket connection stays open."""
    try:
        state = {k: st.session_state[k] for k in sess.CHECKPOINT_FIELDS}
        payload = sess.checkpoint_payload(day_num, state)
        repo.get_repository().set_config("training_progress", json.dumps(payload))
    except Exception:
        pass  # never block the training flow on a persistence failure


def _load_checkpoint(day_num: int) -> dict | None:
    raw = repo.get_repository().get_config_value("training_progress")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return sess.restore_from_checkpoint(data, day_num)


def _init_state(day_num: int | None = None):
    defaults = {
        "tp_ex_idx":           0,
        "tp_set":              1,
        "tp_rep_in_set":       1,
        "tp_phase":            "intro",
        "tp_done_today":       False,
        "tp_session_logged":   False,
        "tp_exit_confirm":     False,
        "tp_started":          False,    # False = show the day-overview screen; True = guided flow
        "tp_side":             "right",  # 'right' → 'left' for unilateral exercises
        "tp_session_start_ts": 0,        # Unix timestamp, set on first set completion
        "tp_fab_open":         False,    # "Add Training" + menu expanded/collapsed
        "tp_yoga_select":      False,    # showing the yoga-picker sub-screen
        "tp_yoga_detail":      None,     # slug of the yoga being viewed (video + Complete), if any
        "tp_garmin_minutes":   {},       # {exercise_idx: actual_minutes} pulled from Garmin on Complete
        "tp_garmin_activity_detail": {}, # {exercise_idx: {avg_hr, max_hr, distance_km, calories}}
    }
    is_fresh_session = "tp_ex_idx" not in st.session_state
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if is_fresh_session and day_num is not None:
        checkpoint = _load_checkpoint(day_num)
        if checkpoint:
            for k in sess.CHECKPOINT_FIELDS:
                if k in checkpoint:
                    st.session_state[k] = checkpoint[k]
        # Authoritative check, independent of the checkpoint above: if a session is
        # already logged in Notion for today, never allow re-entering the exercise
        # flow — a missing/stale/lost checkpoint must not let a second session start.
        try:
            if repo.get_repository().has_logged_session(date.today()):
                st.session_state.tp_done_today = True
                st.session_state.tp_session_logged = True
        except Exception:
            pass


def _reset_session(day_num: int | None = None):
    for k in list(st.session_state.keys()):
        if k.startswith("tp_"):
            del st.session_state[k]
    _init_state()
    if day_num is not None:
        _save_checkpoint(day_num)  # overwrite any saved checkpoint with the cleared state


# ─────────────────────────────────────────────────────────────────────────────
#  Plan Setup / Day Calculation
# ─────────────────────────────────────────────────────────────────────────────

def _get_plan_start() -> date | None:
    raw = repo.get_repository().get_config_value("plan_start_date")
    if raw:
        try:
            return date.fromisoformat(raw.strip())
        except ValueError:
            pass
    return None


def _get_day_number(plan_start: date) -> int:
    return (date.today() - plan_start).days + 1


# ─────────────────────────────────────────────────────────────────────────────
#  Exercise display / auto-logging helpers now live in services/sessions.py —
#  _prescription_label/_type_icon/_movement_category/_planned_reps/
#  _make_sets_data/_estimate_duration all became sess.* below. Only the I/O
#  orchestration (writing the session to Notion) stays here.
# ─────────────────────────────────────────────────────────────────────────────

def _auto_log_session(day_num: int, exercises: list, session_rpe: int,
                      duration_minutes: int, notes: str) -> None:
    r = repo.get_repository()
    garmin_minutes = st.session_state.get("tp_garmin_minutes", {})
    garmin_detail = st.session_state.get("tp_garmin_activity_detail", {})
    session_info = r.create_training_session(
        session_date=date.today(),
        duration_minutes=duration_minutes,
        session_rpe=session_rpe,
    )
    last_id = None
    for idx, ex in enumerate(exercises):
        actual_min = garmin_minutes.get(idx)
        # Garmin-verified duration overrides the planned one for this
        # exercise's own logged tut — a shallow copy so the shared
        # training_plan.py PLAN dict is never mutated in place.
        log_ex = dict(ex, duration_minutes=actual_min) if actual_min else ex
        garmin_note = (
            f"Garmin-verified duration: {actual_min:.0f} min "
            f"(planned {ex.get('duration_minutes')} min)."
        ) if actual_min else ""
        user_note = (st.session_state.get(f"tp_note_{idx}") or "").strip()
        note = "\n".join(n for n in (garmin_note, user_note) if n)
        detail = garmin_detail.get(idx) or {}
        last_id = r.save_training_exercise(
            session_id=session_info["session_id"],
            movement_name=ex["name"],
            movement_type=sess.movement_category(ex),
            planned_sets=ex.get("sets", 1),
            planned_reps=sess.planned_reps(ex),
            rpe=session_rpe,
            sets=sess.make_sets_data(log_ex),
            note=note,
            session_date=session_info["session_date"],
            session_duration_minutes=session_info["duration_minutes"],
            session_rpe=session_info["session_rpe"],
            session_au=session_info["session_au"],
            garmin_avg_hr=detail.get("avg_hr"),
            garmin_max_hr=detail.get("max_hr"),
            garmin_distance_km=detail.get("distance_km"),
            garmin_calories=detail.get("calories"),
        )
    if notes.strip() and last_id:
        r.save_session_notes(last_id, notes)


# ─────────────────────────────────────────────────────────────────────────────
#  Engine Directive (cached at module level so it persists across reruns)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _engine_directive() -> dict:
    try:
        r        = repo.get_repository()
        bio      = [asdict(b) for b in r.get_biometric_rolling(days=28)]
        au       = r.get_daily_session_au(28)
        diag     = r.get_diagnostic_profile()
        stage    = r.get_current_stage()
        streak   = r.get_pain_free_streak()
        tight    = r.get_avg_tightness(14)
        lam      = float(diag.get("injury_weight_decay_lambda") or 0.05)
        tl       = engine.traffic_light(bio)
        acwr_r   = engine.acwr(au, stage)
        inj_w    = engine.injury_weight(lam, streak)
        obs_rem  = engine.observation_days_remaining(tl["data_days"])
        return engine.volume_recommendation(tl, acwr_r, stage, obs_rem, inj_w)
    except Exception:
        return {"signal_color": "grey", "label": "", "action": "", "multiplier": 1.0}


@st.cache_data(ttl=1800, show_spinner=False)
def _bio_for_readiness() -> list[dict]:
    return [asdict(b) for b in repo.get_repository().get_biometric_rolling(days=14)]


# ─────────────────────────────────────────────────────────────────────────────
#  Day-Overview Screen — shown before a session is started for the day.
#  Tapping "Start" hands off to the existing guided exercise-by-exercise flow
#  below, which is unchanged.
# ─────────────────────────────────────────────────────────────────────────────

_OV_BG_ELEV  = "#1A2026"
_OV_TEXT_PRI = "#E8ECEF"
_OV_TEXT_SEC = "#8A99A3"
_OV_ACCENT   = "#00E874"  # green — reserved for progress fills, active nav tab, today-indicator only
_OV_AMBER    = "#C9A227"  # missed-day indicator only
_OV_CTA_BG   = "#FFFFFF"
_OV_CTA_TEXT = "#12171A"

# Page-wide CSS: every primary-type button becomes a solid white pill (covers
# "Back to Home", session-log save, and every set/rep-completion button in the
# guided flow below — one rule, not special-cased per button), and content is
# constrained to a centered ~840px column. Applied once at the top of render().
_PAGE_CSS = f"""<style>
.main .block-container {{ max-width: 840px; margin-left: auto; margin-right: auto; }}
[data-testid="stBaseButton-primary"], [data-testid="baseButton-primary"] {{
    background: {_OV_CTA_BG} !important;
    color: {_OV_CTA_TEXT} !important;
    border: none !important;
    border-radius: 28px !important;
    font-weight: 700 !important;
}}
[data-testid="stBaseButton-primary"] p, [data-testid="baseButton-primary"] p {{
    color: {_OV_CTA_TEXT} !important;
}}
</style>"""


def _progress_bar(label: str, value_label: str, fraction: float) -> None:
    """Label row above (muted left, right-aligned value) + a thin rounded green
    fill — replaces st.progress(..., text=...), which clips its label on mobile."""
    pct = max(0.0, min(1.0, fraction))
    st.markdown(
        f"""
<div style='display:flex;justify-content:space-between;margin-bottom:5px;'>
  <span style='color:{_OV_TEXT_SEC};font-size:11px;letter-spacing:0.5px;'>{label}</span>
  <span style='color:{_OV_TEXT_PRI};font-size:11px;font-weight:600;'>{value_label}</span>
</div>
<div style='width:100%;height:7px;background:rgba(255,255,255,0.10);border-radius:4px;overflow:hidden;'>
  <div style='width:{pct * 100:.0f}%;height:100%;background:{_OV_ACCENT};border-radius:4px;'></div>
</div>
""",
        unsafe_allow_html=True,
    )

# The pre-session release protocol's exercise-name set now lives in
# services.sessions.RELEASE_EXERCISE_NAMES (used below via sess.*).


@st.cache_data(ttl=300, show_spinner=False)
def _week_logged_dates(week_start_iso: str) -> set[str]:
    week_start = date.fromisoformat(week_start_iso)
    return repo.get_repository().get_logged_session_dates(week_start, week_start + timedelta(days=6))


@st.cache_data(ttl=300, show_spinner=False)
def _all_logged_dates(start_iso: str, today_iso: str) -> set[str]:
    """Every logged session date across the full plan history, for the
    Weekly Rollup banner's in-memory computation — wider window than
    _week_logged_dates' single-week fetch above, cached separately."""
    start = date.fromisoformat(start_iso)
    today = date.fromisoformat(today_iso)
    return repo.get_repository().get_logged_session_dates(start, today)


@st.cache_data(ttl=1800, show_spinner=False)
def _sync_weekly_rollup_cached() -> tuple[bool, str | None]:
    """Persists ended weeks to the Weekly Rollup Sheet tab, throttled by the
    TTL like _engine_directive above. Non-blocking: the caller never stops
    rendering on failure, since the banner itself is computed in-memory,
    independent of this write succeeding."""
    try:
        result = metrics.sync_weekly_rollup(repo.get_repository())
        return result.ok, result.error
    except Exception as exc:
        return False, str(exc)


@st.cache_data(ttl=1800, show_spinner=False)
def _sync_garmin_daily_cached() -> tuple[bool, str | None]:
    """Throttles the due-check itself (cheap) — the actual Garmin sync only
    ever fires once per calendar day regardless, via Repository.
    sync_garmin_daily_if_due (Garmin's API is rate-limit-sensitive, unlike the
    Weekly Rollup sync above). app.py's Home page also triggers this same
    once/day sync now that Garmin feeds the engine's biometric blend
    (services/biometrics.py) — this call here just means it's covered on the
    Training page too if Home wasn't visited first that day."""
    try:
        return repo.get_repository().sync_garmin_daily_if_due()
    except Exception as exc:
        return False, str(exc)


def _seed_and_get_active_phase(plan_start: date | None) -> tuple[list, object | None]:
    """Reads phases from the Config DB; one-time-seeds Phase 1 from the existing
    plan_start_date if no phases have been configured yet. Returns (phases, active)."""
    r = repo.get_repository()
    phases = r.get_phases()
    if not phases:
        seeded = sess.seed_default_phase(phases, plan_start)
        if seeded:
            r.set_phases(seeded)
            phases = seeded
    return phases, ph.active_phase(phases, date.today())


_MARKER_GREEN   = "#00E874"
_MARKER_PLANNED = "#C7D0D6"
_MARKER_MISSED  = "#B08A3E"
_MARKER_REST    = "#4A555D"
_SELECTED_HL    = "#232B32"

_WEEK_STRIP_BASE_CSS = f"""
[data-testid="stElementContainer"]:has(.stWeekRow) + [data-testid="stElementContainer"] {{
    background: #1A2026;
    border-radius: 16px;
    padding: 12px 16px;
    margin-bottom: 16px;
}}
/* Force the row to stay on one line even on narrow mobile widths (Streamlit's
   default <640px behaviour stacks columns vertically) — same fix nav.py already
   applies to its own row via the marker + :has() pattern. */
[data-testid="stElementContainer"]:has(.stWeekRow) + [data-testid="stElementContainer"]
    [data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important;
    gap: 2px !important;
}}
[data-testid="stElementContainer"]:has(.stWeekRow) + [data-testid="stElementContainer"]
    [data-testid="stColumn"] {{
    min-width: 0 !important;
}}
[data-testid="stElementContainer"]:has(.stWeekRow) + [data-testid="stElementContainer"] button {{
    background: transparent !important;
    border: none !important;
    padding: 6px 2px !important;
    font-size: 11px !important;
    letter-spacing: 0.5px !important;
    color: {_OV_TEXT_SEC} !important;
}}
[data-testid="stElementContainer"]:has(.stWeekRow) + [data-testid="stElementContainer"] button:disabled {{
    opacity: 0.25 !important;
}}
"""


def _marker_glyph_and_color(cell, is_today: bool) -> tuple[str, str]:
    if cell.state == "completed":
        return "✓", _MARKER_GREEN
    if is_today:
        return "●", _MARKER_GREEN
    if cell.state == "missed":
        return "○", _MARKER_MISSED
    if cell.state == "planned":
        return "●", _MARKER_PLANNED
    return "○", _MARKER_REST  # rest


# ─────────────────────────────────────────────────────────────────────────────
#  Weekly Rollup — Perfect/Ultimate Week banner, last-week verdict, and the
#  day-strip's past-week status badge. All computation is metrics_logic.*
#  (pure); this section is presentation only. Reuses the existing accent
#  tokens above — _MARKER_GREEN for positive states, _MARKER_MISSED as the
#  app's established amber (never red), _OV_TEXT_SEC for muted/neutral.
# ─────────────────────────────────────────────────────────────────────────────

_VERDICT_TEXT = {
    "ultimate": "ULTIMATE WEEK",
    "perfect":  "PERFECT WEEK ✓",
    "normal":   "Normal week",
    "failed":   "Failed week",
    "no_plan":  "No plan scheduled",
}
_VERDICT_COLOR = {
    "ultimate": _MARKER_GREEN,
    "perfect":  _MARKER_GREEN,
    "normal":   _OV_TEXT_SEC,
    "failed":   _MARKER_MISSED,
    "no_plan":  _OV_TEXT_SEC,
}


def _streak_label(streak, all_ultimate: bool) -> str:
    n = streak.current_streak
    if n == 0:
        return "No active streak"
    kind = " ultimate" if all_ultimate else ""
    return f"{n} week{kind} streak"


def _current_week_tier(scheduled: int, completed: int) -> tuple[str, str]:
    """(label, color) for the live current-week progress line. Integer math,
    matching metrics_logic.score_week's own thresholds."""
    if scheduled == 0:
        return "No sessions scheduled this week", _OV_TEXT_SEC
    if completed == scheduled:
        return "ULTIMATE WEEK", _MARKER_GREEN
    if completed * 5 >= scheduled * 4:
        return f"PERFECT WEEK — {scheduled - completed} to go for ultimate", _MARKER_GREEN
    needed = -(-(scheduled * 4) // 5)  # ceil(scheduled*4/5)
    remaining = max(1, needed - completed)
    return f"{remaining} more for a perfect week", _OV_TEXT_SEC


def _render_weekly_rollup_banner(history: list, streak) -> None:
    """Elevated-surface banner above the day strip — streak / live current-
    week progress / lifetime tallies — plus, directly under it, last week's
    verdict once at least one week has actually ended."""
    current = next((w for w in history if w.status == "in_progress"), None)
    scheduled = current.scheduled if current else 0
    completed = current.completed if current else 0
    tier_label, tier_color = _current_week_tier(scheduled, completed)
    streak_label = _streak_label(streak, ml.current_streak_is_all_ultimate(history))

    st.markdown(
        f"""
<div style='background:{_OV_BG_ELEV};border-radius:16px;padding:16px 20px;margin-bottom:14px;
            display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;'>
  <div style='flex:1;min-width:120px;'>
    <div style='color:{_OV_TEXT_SEC};font-size:11px;letter-spacing:0.5px;margin-bottom:2px;'>STREAK</div>
    <div style='color:{_OV_TEXT_PRI};font-size:14px;font-weight:700;'>{streak_label}</div>
  </div>
  <div style='flex:2;min-width:160px;text-align:center;'>
    <div style='color:{_OV_TEXT_SEC};font-size:11px;letter-spacing:0.5px;margin-bottom:2px;'>
      THIS WEEK: {completed}/{scheduled} SESSIONS</div>
    <div style='color:{tier_color};font-size:14px;font-weight:700;'>{tier_label}</div>
  </div>
  <div style='flex:1;min-width:120px;text-align:right;'>
    <div style='color:{_OV_TEXT_SEC};font-size:12px;'>
      {streak.perfect_count} perfect · {streak.ultimate_count} ultimate</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    ended = [w for w in history if w.status not in ("in_progress", "no_plan")]
    if ended:
        last_week = max(ended, key=lambda w: w.week_start)
        text = _VERDICT_TEXT[last_week.status]
        color = _VERDICT_COLOR[last_week.status]
        st.markdown(
            f"<div style='color:{_OV_TEXT_SEC};font-size:12px;margin-bottom:12px;'>"
            f"Last week: <span style='color:{color};font-weight:600;'>{text}</span></div>",
            unsafe_allow_html=True,
        )


def _render_week_status_badge(history: list, viewed_week_start) -> None:
    """Small badge shown under the day strip only when paging to a week
    other than the current one — that week's persisted verdict. The current
    week's status is already covered by the banner above, so this renders
    nothing for it."""
    if viewed_week_start is None:
        return
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    if viewed_week_start == current_week_start:
        return
    week = next((w for w in history if w.week_start == viewed_week_start.isoformat()), None)
    if week is None or week.status == "in_progress":
        return
    text = _VERDICT_TEXT[week.status]
    color = _VERDICT_COLOR[week.status]
    st.markdown(
        f"<div style='color:{_OV_TEXT_SEC};font-size:12px;margin:-8px 0 14px 0;'>"
        f"Week of {week.week_start}: <span style='color:{color};font-weight:600;'>{text}</span></div>",
        unsafe_allow_html=True,
    )


def _render_day_strip(active: dict | None) -> None:
    """Universal weekly strip — rendered at the very top of the page in every
    state. Chevrons page one week at a time, clamped to the active phase's week
    range (phase.clamp_week_start). Selection persists in session_state."""
    today = date.today()
    _default_week = today - timedelta(days=today.weekday())

    if "tp_week_start" not in st.session_state:
        st.session_state.tp_week_start = ph.clamp_week_start(_default_week, active) if active else _default_week
    if "tp_selected_date" not in st.session_state:
        st.session_state.tp_selected_date = today

    week_start = st.session_state.tp_week_start

    try:
        logged_dates = _week_logged_dates(week_start.isoformat())
    except Exception:
        logged_dates = set()
    sessions = [{"date": d} for d in logged_dates]
    cells = ph.get_week_view(week_start, active, sessions, today=today)

    at_lo = at_hi = False
    if active:
        lo, hi = ph.phase_week_bounds(active)
        at_lo, at_hi = week_start <= lo, week_start >= hi

    # "Today" jump — small, right-aligned, only when viewing a different week.
    # Rendered with default (secondary) button styling, outside the strip's own
    # scoped CSS below.
    if week_start != _default_week:
        _sp, _today_col = st.columns([5, 1])
        with _today_col:
            if st.button("Today", key="tp_wk_today", use_container_width=True):
                st.session_state.tp_week_start = (
                    ph.clamp_week_start(_default_week, active) if active else _default_week
                )
                st.session_state.tp_selected_date = today
                st.rerun()

    selected_idx = next(
        (i for i, c in enumerate(cells) if c.date == st.session_state.tp_selected_date), None
    )

    # Per-cell marker colour (day columns are nth-child(2)..nth-child(8); the
    # prev/next chevrons occupy 1 and 9) and the selected-slot highlight —
    # computed fresh each render since we already know every cell's state here.
    marker_rules = []
    for i, cell in enumerate(cells):
        is_today = cell.date == today
        _, color = _marker_glyph_and_color(cell, is_today)
        marker_rules.append(
            f"""[data-testid="stElementContainer"]:has(.stWeekRow) + [data-testid="stElementContainer"]
                [data-testid="stColumn"]:nth-child({i + 2}) button p::first-line {{
                color: {color} !important; font-size: 16px !important;
            }}"""
        )
    highlight_rule = ""
    if selected_idx is not None:
        highlight_rule = f"""
        [data-testid="stElementContainer"]:has(.stWeekRow) + [data-testid="stElementContainer"]
            [data-testid="stColumn"]:nth-child({selected_idx + 2}) button {{
            background: {_SELECTED_HL} !important;
            border-radius: 10px !important;
            padding: 6px 10px !important;
        }}"""

    st.markdown(
        f"<style>{_WEEK_STRIP_BASE_CSS}{''.join(marker_rules)}{highlight_rule}</style>",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="stWeekRow" style="display:none"></div>', unsafe_allow_html=True)

    col_prev, *day_cols, col_next = st.columns([1, 3, 3, 3, 3, 3, 3, 3, 1])
    with col_prev:
        if st.button("‹", key="tp_wk_prev", use_container_width=True,
                     disabled=(active is not None and at_lo)):
            candidate = week_start - timedelta(days=7)
            st.session_state.tp_week_start = ph.clamp_week_start(candidate, active) if active else candidate
            st.rerun()
    for i, (col, cell) in enumerate(zip(day_cols, cells)):
        is_today = cell.date == today
        glyph, _ = _marker_glyph_and_color(cell, is_today)
        label = cell.date.strftime("%d/%m") if i == selected_idx else cell.weekday_label
        with col:
            if st.button(f"{glyph}  \n{label}", key=f"tp_day_{cell.date.isoformat()}",
                         use_container_width=True):
                st.session_state.tp_selected_date = cell.date
                st.rerun()
    with col_next:
        if st.button("›", key="tp_wk_next", use_container_width=True,
                     disabled=(active is not None and at_hi)):
            candidate = week_start + timedelta(days=7)
            st.session_state.tp_week_start = ph.clamp_week_start(candidate, active) if active else candidate
            st.rerun()


def _render_workout_card(day_num: int, phase_obj, today_plan: dict,
                          exercises: list, duration_min: int) -> None:
    focus_text = ", ".join(sess.focus_areas(exercises)) or "Full Body"
    n_ex = len(exercises)
    phase_length = phase_obj.length_days
    phase_name = phase_obj.name
    st.markdown(
        f"""
<div style='background:{_OV_BG_ELEV};border-radius:16px;padding:22px 20px;margin-bottom:22px;'>
  <div style='display:flex;justify-content:space-between;gap:16px;'>
    <div style='flex:1;min-width:0;'>
      <div style='color:{_OV_TEXT_SEC};font-size:14px;margin-bottom:2px;'>{phase_name}</div>
      <div style='color:{_OV_TEXT_PRI};font-size:34px;font-weight:800;letter-spacing:0.5px;
                  line-height:1.05;margin-bottom:14px;'>DAY {day_num}</div>
      <div style='display:grid;grid-template-columns:1fr 1fr;gap:10px 14px;'>
        <div style='display:flex;align-items:center;gap:7px;'>
          <span style='font-size:13px;'>⏱</span>
          <span style='color:{_OV_TEXT_PRI};font-size:13px;'>{duration_min} min</span>
        </div>
        <div style='display:flex;align-items:center;gap:7px;'>
          <span style='font-size:13px;'>🔥</span>
          <span style='color:{_OV_TEXT_PRI};font-size:13px;'>RPE ≤{today_plan["session_rpe_target"]}/10</span>
        </div>
        <div style='display:flex;align-items:center;gap:7px;'>
          <span style='font-size:13px;'>🎯</span>
          <span style='color:{_OV_TEXT_PRI};font-size:13px;'>{focus_text}</span>
        </div>
        <div style='display:flex;align-items:center;gap:7px;'>
          <span style='font-size:13px;'>🏠</span>
          <span style='color:{_OV_TEXT_PRI};font-size:13px;'>Bodyweight Only</span>
        </div>
      </div>
    </div>
    <div style='width:112px;flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;'>
      <div style='color:{_OV_TEXT_SEC};font-size:11px;margin-bottom:6px;text-align:right;'>
        {day_num} of {phase_length} sessions</div>
      <div style='width:100%;height:7px;background:rgba(255,255,255,0.10);border-radius:4px;
                  overflow:hidden;margin-bottom:16px;'>
        <div style='width:{day_num / phase_length * 100:.0f}%;height:100%;background:{_OV_ACCENT};
                    border-radius:4px;'></div>
      </div>
      <div style='color:{_OV_TEXT_SEC};font-size:11px;text-align:right;'>{n_ex} exercises</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_exercise_timeline(exercises: list) -> None:
    if not exercises:
        st.caption("No exercises in this section.")
        return
    rows = []
    for ex in exercises:
        icon = sess.type_icon(ex)
        rows.append(
            f"""
<div style='position:relative;padding:14px 0 14px 34px;
            border-left:2px solid rgba(255,255,255,0.10);margin-left:17px;'>
  <div style='position:absolute;left:-11px;top:16px;width:20px;height:20px;border-radius:50%;
              background:{_OV_BG_ELEV};border:2px solid rgba(255,255,255,0.18);display:flex;
              align-items:center;justify-content:center;font-size:10px;'>{icon}</div>
  <div style='color:{_OV_TEXT_PRI};font-size:15px;font-weight:600;'>{ex["name"]}</div>
  <div style='color:{_OV_TEXT_SEC};font-size:12.5px;margin-top:2px;'>{sess.prescription_label(ex)}</div>
</div>
"""
        )
    st.markdown(f"<div>{''.join(rows)}</div>", unsafe_allow_html=True)


def _day_overline(d: date) -> None:
    st.markdown(
        f"<div style='color:{_OV_TEXT_SEC};font-size:12px;letter-spacing:2px;font-weight:600;"
        f"text-transform:uppercase;margin-bottom:14px;'>{d.strftime('%b %d')}</div>",
        unsafe_allow_html=True,
    )


def _render_past_completed(d: date) -> None:
    """Read-only log for a past date that was completed — no Start/complete actions."""
    _day_overline(d)
    try:
        sessions = repo.get_repository().get_recent_sessions(days=(date.today() - d).days + 3)
    except Exception:
        sessions = []
    day_session = next((s for s in sessions if s.session_date == d.isoformat()), None)

    if not day_session or not day_session.exercises:
        # Logged per the day strip's own check, but the detail fetch came back
        # empty (e.g. cache/read race) — say so plainly rather than fabricate rows.
        st.markdown(
            f"<div style='background:{_OV_BG_ELEV};border-radius:16px;padding:28px 24px;"
            f"text-align:center;color:{_OV_TEXT_SEC};font-size:14px;'>"
            f"Session marked complete, but no exercise detail could be loaded.</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
<div style='background:{_OV_BG_ELEV};border-radius:16px;padding:20px;margin-bottom:16px;'>
  <div style='color:{_MARKER_GREEN};font-size:13px;letter-spacing:1px;margin-bottom:6px;'>✓ SESSION LOGGED</div>
  <div style='color:{_OV_TEXT_SEC};font-size:13px;'>
    RPE {day_session.session_rpe if day_session.session_rpe is not None else "—"}/10 ·
    {day_session.session_duration_minutes if day_session.session_duration_minutes is not None else "—"} min ·
    {day_session.session_au if day_session.session_au is not None else "—"} AU</div>
</div>
""",
        unsafe_allow_html=True,
    )
    rows_html = "".join(
        f"<div style='padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.06);'>"
        f"<div style='color:{_OV_TEXT_PRI};font-size:14px;font-weight:600;'>"
        f"✓ {r.name}</div>"
        f"<div style='color:{_OV_TEXT_SEC};font-size:12px;margin-top:2px;'>"
        f"{r.movement_type} · {r.planned_sets if r.planned_sets is not None else '—'} sets"
        f"</div></div>"
        for r in day_session.exercises
    )
    st.markdown(f"<div>{rows_html}</div>", unsafe_allow_html=True)


def _render_past_missed(d: date, active) -> None:
    """Read-only view of what was planned for a past date that wasn't completed."""
    _day_overline(d)
    day_num = ph.day_number_in_phase(active, d)
    st.markdown(
        f"<div style='color:{_MARKER_MISSED};font-size:13px;letter-spacing:1px;"
        f"margin-bottom:16px;'>NOT COMPLETED</div>",
        unsafe_allow_html=True,
    )
    today_plan = tp.PLAN.get(day_num) if active.phase_number == 1 else None
    if not today_plan:
        st.info(f"Day {day_num} of {active.name} has no authored content on record.")
        return
    st.caption(f"Day {day_num} of {active.length_days} — {today_plan['objective']} (planned, not done)")
    _render_exercise_timeline(today_plan["exercises"])


def _render_future_day(d: date, active) -> None:
    """Preview for a future date within the active phase. No Start action — you
    can't begin a day out of sequence."""
    day_num = ph.day_number_in_phase(active, d)
    _day_overline(d)
    today_plan = tp.PLAN.get(day_num) if active.phase_number == 1 else None
    if not today_plan:
        st.markdown(
            f"<div style='color:{_OV_TEXT_SEC};font-size:13px;margin-bottom:12px;'>"
            f"Scheduled for {d.strftime('%B')} {d.day} · Day {day_num} of {active.length_days}</div>",
            unsafe_allow_html=True,
        )
        st.info(f"Day {day_num} of {active.name} has no authored content yet.")
        return
    st.markdown(
        f"""
<div style='color:{_OV_TEXT_PRI};font-size:22px;font-weight:700;margin-bottom:4px;'>{today_plan['objective']}</div>
<div style='color:{_OV_TEXT_SEC};font-size:13px;margin-bottom:18px;'>
    Day {day_num} of {active.length_days} — RPE target ≤{today_plan["session_rpe_target"]}/10<br>
    Scheduled for {d.strftime('%B')} {d.day}</div>
""",
        unsafe_allow_html=True,
    )
    _render_exercise_timeline(today_plan["exercises"])


def _render_rest_day(d: date) -> None:
    _day_overline(d)
    st.markdown(
        f"<div style='background:{_OV_BG_ELEV};border-radius:16px;padding:28px 24px;"
        f"text-align:center;color:{_OV_TEXT_SEC};font-size:14px;'>Rest day.</div>",
        unsafe_allow_html=True,
    )
    suggestion = yg.suggest_for_day("rest_day")
    if suggestion:
        st.markdown(
            f"<div style='margin-top:12px;color:{_OV_TEXT_SEC};font-size:12px;"
            f"letter-spacing:1px;text-transform:uppercase;'>Optional active rest</div>",
            unsafe_allow_html=True,
        )
        if st.button(f"🧘  {suggestion.name}  ·  {suggestion.total_duration_minutes} min",
                      key="tp_rest_day_yoga_suggestion", use_container_width=True):
            st.session_state.tp_yoga_detail = suggestion.slug
            st.session_state.tp_yoga_select = True
            st.rerun()


def _render_no_active_phase(phases: list) -> None:
    """Reassessment gap — no phase covers today. Never shows a placeholder workout."""
    upcoming = sorted(
        (p for p in phases if p.status == "upcoming"),
        key=lambda p: p.start_date,
    )
    next_line = (
        f"Next phase — <strong style='color:{_OV_TEXT_PRI};'>{upcoming[0].name}</strong> "
        f"— starts {upcoming[0].start_date}."
        if upcoming else
        "No upcoming phase configured yet."
    )
    st.markdown(
        f"""
<div style='background:{_OV_BG_ELEV};border-radius:16px;padding:28px 24px;text-align:center;'>
  <div style='color:{_OV_TEXT_PRI};font-size:20px;font-weight:700;margin-bottom:10px;'>
    Reassessment — no phase active</div>
  <div style='color:{_OV_TEXT_SEC};font-size:13px;line-height:1.6;'>{next_line}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_day_detail(d: date, active, phases: list) -> None:
    """Dispatcher for any selected date other than today — active is guaranteed
    non-None here (the 'no active phase at all' case is handled by the caller
    before this is reached)."""
    try:
        is_logged = repo.get_repository().has_logged_session(d)
    except Exception:
        is_logged = False
    state = sess.day_view_state(d, date.today(), active, is_logged)
    if state == "rest":
        _render_rest_day(d)
    elif state == "past_completed":
        _render_past_completed(d)
    elif state == "past_missed":
        _render_past_missed(d, active)
    else:  # "future"
        _render_future_day(d, active)


@st.dialog("Session Adaptation")
def _adapt_session_dialog(readiness_modifier: dict) -> None:
    factor = readiness_modifier.get("volume_factor", 1.0)
    if factor == 1.0:
        st.markdown("**No adaptation today** — your readiness supports the full prescribed volume.")
    else:
        direction = "increased" if factor > 1.0 else "reduced"
        st.markdown(f"**Volume {direction} to {factor:.0%}** of the standard prescription.")
        st.caption(readiness_modifier.get("description", ""))
    st.divider()
    st.caption(
        "Based on your last 3 days of HRV, RHR and sleep. This adjusts reps, hold time and "
        "duration automatically — sets and rest periods stay fixed. Safety ceilings (ACWR, "
        "RPE cap) are never affected by this modifier."
    )
    if st.button("Close", use_container_width=True):
        st.rerun()


_FAB_CSS = f"""<style>
[data-testid="stElementContainer"]:has(.stFabRow) + [data-testid="stElementContainer"] {{
    position: fixed !important;
    left: 20px !important;
    right: 20px !important;
    bottom: 84px !important;
    z-index: 8500 !important;
    margin: 0 !important;
    padding: 0 !important;
}}
[data-testid="stElementContainer"]:has(.stFabRow) + [data-testid="stElementContainer"]
    [data-testid="stHorizontalBlock"] {{
    gap: 10px !important;
}}
[data-testid="stElementContainer"]:has(.stFabRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-secondary"] {{
    background: rgba(42,49,54,0.75) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(245,247,248,0.30) !important;
    color: {_OV_TEXT_PRI} !important;
    border-radius: 28px !important;
    height: 56px !important;
    font-weight: 600 !important;
}}
[data-testid="stElementContainer"]:has(.stFabRow) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-primary"] {{
    background: {_OV_CTA_BG} !important;
    color: {_OV_CTA_TEXT} !important;
    border: none !important;
    border-radius: 28px !important;
    height: 56px !important;
    font-weight: 700 !important;
}}
</style>"""


def _render_overview(day_num: int, active, today_plan: dict,
                      exercises: list, directive: dict, readiness_modifier: dict) -> None:
    """Today's session — coach header, workout card, accordions, floating actions.
    The day strip, phase resolution, and past/future/rest routing all happen once
    in render() before this is ever called; this only ever renders today."""
    today = date.today()
    duration_min       = sess.estimate_duration(exercises)
    headline, subtitle  = sess.coach_message(directive, today_plan)

    st.markdown(
        f"""
<div style='color:{_OV_TEXT_SEC};font-size:12px;letter-spacing:2px;font-weight:600;
            text-transform:uppercase;margin-bottom:10px;'>{today.strftime('%b %d')}</div>
<div style='color:{_OV_TEXT_PRI};font-size:26px;font-weight:700;line-height:1.3;
            margin-bottom:8px;'>{headline}</div>
<div style='color:{_OV_TEXT_SEC};font-size:14px;margin-bottom:20px;'>{subtitle}</div>
""",
        unsafe_allow_html=True,
    )

    _render_workout_card(day_num, active, today_plan, exercises, duration_min)

    release_exercises, main_exercises = sess.split_release_and_main(exercises)

    if release_exercises:
        with st.expander(f"Release Protocol  ·  {len(release_exercises)}", expanded=False):
            _render_exercise_timeline(release_exercises)

    with st.expander(f"Workout  ·  {len(main_exercises)}", expanded=True):
        _render_exercise_timeline(main_exercises)

    # Spacer — keeps the last accordion row from being hidden behind the fixed
    # floating action bar + bottom nav once scrolled to the end.
    st.markdown("<div style='height:150px;'></div>", unsafe_allow_html=True)

    st.markdown(_FAB_CSS, unsafe_allow_html=True)
    st.markdown('<div class="stFabRow" style="display:none"></div>', unsafe_allow_html=True)
    col_adapt, col_start = st.columns(2, gap="small")
    with col_adapt:
        if st.button("Adapt session", use_container_width=True):
            _adapt_session_dialog(readiness_modifier)
    with col_start:
        if st.button("Start", type="primary", use_container_width=True):
            st.session_state.tp_started = True
            _save_checkpoint(day_num)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  "Add Training" — floating + menu (Yoga / Extra Workout) and the Yoga picker.
#  Fixed top-right, mirrors the Home-page FAB's right-edge formula but against
#  this page's 840px column (see _PAGE_CSS above).
# ─────────────────────────────────────────────────────────────────────────────

_ADD_FAB_YOGA_BG  = "linear-gradient(135deg, #6BCB77, #2E8B57)"
_ADD_FAB_EXTRA_BG = "linear-gradient(135deg, #FF7A45, #E8402C)"

_ADD_FAB_CSS = f"""<style>
[data-testid="stElementContainer"]:has(.stAddFabToggle) + [data-testid="stElementContainer"] {{
    position: fixed !important;
    top: 16px !important;
    right: max(20px, calc((100vw - 840px)/2 + 16px)) !important;
    z-index: 900 !important;
    width: 52px !important;
    margin: 0 !important;
    padding: 0 !important;
}}
[data-testid="stElementContainer"]:has(.stAddFabToggle) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-secondary"] {{
    width: 52px !important;
    height: 52px !important;
    border-radius: 50% !important;
    background: {_OV_CTA_BG} !important;
    color: {_OV_CTA_TEXT} !important;
    border: none !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.45) !important;
    font-size: 22px !important;
    font-weight: 400 !important;
    padding: 0 !important;
}}
[data-testid="stElementContainer"]:has(.stAddFabYoga) + [data-testid="stElementContainer"] {{
    position: fixed !important;
    top: 78px !important;
    right: max(20px, calc((100vw - 840px)/2 + 16px)) !important;
    z-index: 900 !important;
    margin: 0 !important;
    padding: 0 !important;
}}
[data-testid="stElementContainer"]:has(.stAddFabYoga) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-secondary"] {{
    background: {_ADD_FAB_YOGA_BG} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 22px !important;
    height: 44px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.35) !important;
}}
[data-testid="stElementContainer"]:has(.stAddFabExtra) + [data-testid="stElementContainer"] {{
    position: fixed !important;
    top: 130px !important;
    right: max(20px, calc((100vw - 840px)/2 + 16px)) !important;
    z-index: 900 !important;
    margin: 0 !important;
    padding: 0 !important;
}}
[data-testid="stElementContainer"]:has(.stAddFabExtra) + [data-testid="stElementContainer"]
    [data-testid="stBaseButton-secondary"] {{
    background: {_ADD_FAB_EXTRA_BG} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 22px !important;
    height: 44px !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.35) !important;
}}
</style>"""


def _render_add_training_fab() -> None:
    """Floating "+" menu, fixed top-right, present across every training-page
    state. Expands to Yoga (→ yoga-picker, same page) and Extra Workout (stub —
    no destination yet)."""
    st.markdown(_ADD_FAB_CSS, unsafe_allow_html=True)

    open_ = st.session_state.get("tp_fab_open", False)

    st.markdown('<div class="stAddFabToggle" style="display:none"></div>', unsafe_allow_html=True)
    if st.button("×" if open_ else "+", key="tp_fab_toggle"):
        st.session_state.tp_fab_open = not open_
        st.rerun()

    if open_:
        st.markdown('<div class="stAddFabYoga" style="display:none"></div>', unsafe_allow_html=True)
        if st.button("🧘  Yoga", key="tp_fab_yoga"):
            st.session_state.tp_yoga_select = True
            st.session_state.tp_fab_open = False
            st.rerun()

        st.markdown('<div class="stAddFabExtra" style="display:none"></div>', unsafe_allow_html=True)
        if st.button("💪  Extra Workout", key="tp_fab_extra"):
            st.session_state.tp_fab_open = False
            st.toast("Extra Workout logging is coming soon.")
            st.rerun()


def _log_yoga_completion(session: yg.YogaSession, note: str = "") -> None:
    """Persist a completed yoga session to Notion — mirrors _auto_log_session's
    shape (one shared session_id/AU/RPE across a row per pose) so it feeds the
    same get_daily_session_au() aggregate the Home strain card and ACWR read from.
    Tagged Type="Yoga" so repo.has_logged_session() (which gates the rehab-plan
    flow) skips it — see that method's docstring. `note` is the whole-session
    note from the completion screen, attached to the last logged pose the same
    way _auto_log_session attaches the rehab flow's session-wide notes."""
    r = repo.get_repository()
    try:
        current_stage = r.get_current_stage()
    except Exception:
        current_stage = 1
    session_info = r.create_training_session(
        session_date=date.today(),
        duration_minutes=session.total_duration_minutes,
        session_rpe=session.estimated_rpe,
    )
    last_id = None
    for pose in session.poses:
        severity, pose_note = yg.effective_safety(pose, current_stage)
        last_id = r.save_training_exercise(
            session_id=session_info["session_id"],
            movement_name=pose.name,
            movement_type="Yoga",
            planned_sets=1,
            planned_reps=1,
            rpe=session.estimated_rpe,
            sets=[{"set_num": 1, "reps": 1, "weight": 0.0,
                   "rest": 10, "tut": pose.hold_seconds, "velocity": "isometric"}],
            note=pose_note if severity != "cleared" else "",
            session_date=session_info["session_date"],
            session_duration_minutes=session_info["duration_minutes"],
            session_rpe=session_info["session_rpe"],
            session_au=session_info["session_au"],
        )
    if note.strip() and last_id:
        r.save_session_notes(last_id, note)


def _render_yoga_detail(session: yg.YogaSession) -> None:
    """Video link + full routine + safety callouts + Complete. Tapping Complete
    logs every pose to today and returns to the training page — same page,
    no navigation."""
    if st.button("← Back", key="tp_yoga_detail_back"):
        st.session_state.tp_yoga_detail = None
        st.rerun()

    st.markdown(
        f"<div style='font-size:22px;font-weight:700;margin:12px 0 4px;'>{session.name}</div>"
        f"<div style='color:{_OV_TEXT_SEC};font-size:13px;margin-bottom:14px;'>"
        f"{session.total_duration_minutes} min · RPE {session.estimated_rpe}/10</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"[Watch on YouTube]({session.video_url})")

    try:
        current_stage = repo.get_repository().get_current_stage()
    except Exception:
        current_stage = 1
    cautions = session.cautions(current_stage)
    if cautions:
        notes_html = "".join(
            f"<div style='margin-top:8px;'><strong style='color:{_OV_TEXT_PRI};'>"
            f"{'⚠ ' if severity == 'contraindicated' else '· '}{pose.name}</strong>"
            f"<div style='color:{_OV_TEXT_SEC};font-size:12px;margin-top:2px;'>{note}</div></div>"
            for pose, severity, note in cautions
        )
        st.markdown(
            f"<div style='background:{_OV_BG_ELEV};border-radius:12px;padding:14px 16px;"
            f"margin:14px 0;'><div style='color:{_OV_AMBER};font-size:12px;letter-spacing:1px;"
            f"font-weight:600;'>FORM NOTES FOR THIS PATIENT</div>{notes_html}</div>",
            unsafe_allow_html=True,
        )

    rows_html = "".join(
        f"<div style='display:flex;justify-content:space-between;padding:8px 0;"
        f"border-bottom:1px solid rgba(255,255,255,0.06);font-size:13px;'>"
        f"<span style='color:{_OV_TEXT_PRI};'>{p.name}</span>"
        f"<span style='color:{_OV_TEXT_SEC};'>{p.hold_seconds}s</span></div>"
        for p in session.poses
    )
    with st.expander(f"Full routine · {len(session.poses)} poses"):
        st.markdown(f"<div>{rows_html}</div>", unsafe_allow_html=True)

    yoga_note = st.text_area(
        "Notes (optional)", key=f"tp_yoga_note_{session.slug}",
        placeholder="e.g. right hip felt tight during pigeon pose, skipped the forward folds...",
        height=80,
    )

    if st.button("Complete", type="primary", key="tp_yoga_complete", use_container_width=True):
        _log_yoga_completion(session, yoga_note)
        st.session_state.tp_yoga_detail = None
        st.session_state.tp_yoga_select = False
        st.toast(f"Logged {session.name} — nice work.")
        st.rerun()


def _render_yoga_select() -> None:
    """Yoga picker — reads services.yoga.YOGA_LIBRARY. Rendered in place of the
    normal training page; "Back" returns via the same tp_yoga_select flag +
    rerun — no separate page/navigation."""
    if st.session_state.get("tp_yoga_detail"):
        session = yg.get(st.session_state.tp_yoga_detail)
        if session:
            _render_yoga_detail(session)
            return
        st.session_state.tp_yoga_detail = None  # stale/unknown slug — fall through to the list

    st.markdown(
        "<div style='font-size:22px;font-weight:700;margin-bottom:16px;'>Select Yoga</div>",
        unsafe_allow_html=True,
    )
    if st.button("← Back", key="tp_yoga_back"):
        st.session_state.tp_yoga_select = False
        st.rerun()

    if not yg.YOGA_LIBRARY:
        st.info("No yoga sessions have been added yet — check back soon.")
        return

    for session in yg.YOGA_LIBRARY:
        if st.button(f"🧘  {session.name}  ·  {session.total_duration_minutes} min",
                      key=f"tp_yoga_pick_{session.slug}", use_container_width=True):
            st.session_state.tp_yoga_detail = session.slug
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  Main render() — entry point for app.py SPA routing
# ─────────────────────────────────────────────────────────────────────────────

def render():
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)

    # ── Session state initialisation — restores from a saved Notion checkpoint
    #     if this is a fresh session (e.g. the browser dropped its connection
    #     while a training session was in progress) ───────────────────────────
    plan_start = _get_plan_start()
    day_num = _get_day_number(plan_start) if plan_start else None
    _init_state(day_num)

    # ── "Add Training" — floating + menu on every state below; the yoga-picker
    #     sub-screen short-circuits everything else (same page, no navigation) ──
    if st.session_state.get("tp_yoga_select"):
        _render_yoga_select()
        nav.inject("training")
        st.stop()
    _render_add_training_fab()

    # ── Readiness modifier — computed once per render, applied to prescriptions ─
    try:
        _rm_bio = _bio_for_readiness()
    except Exception:
        _rm_bio = []
    _readiness_modifier = engine.readiness_training_modifier(_rm_bio)
    _volume_factor = _readiness_modifier.get("volume_factor", 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    #  Main Page
    # ─────────────────────────────────────────────────────────────────────────

    # ── Plan not yet configured ───────────────────────────────────────────────
    if plan_start is None:
        st.title("Training Plan")
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
            repo.get_repository().set_config("plan_start_date", str(start_input))
            st.success(f"Plan starts {start_input}. Come back each day for your session.")
            st.rerun()
        st.stop()

    # ── Universal weekly day strip — top of page, every state ───────────────────
    phases, active = _seed_and_get_active_phase(plan_start)

    # ── Weekly Rollup — banner + last-week verdict, above the day strip in
    #     every state (matching the day strip's own universality) ───────────
    _sync_ok, _sync_err = _sync_weekly_rollup_cached()
    _garmin_sync_ok, _garmin_sync_err = _sync_garmin_daily_cached()
    history: list = []
    if phases:
        _earliest = min(date.fromisoformat(p.start_date) for p in phases)
        try:
            _logged = _all_logged_dates(_earliest.isoformat(), date.today().isoformat())
        except Exception:
            _logged = set()
        history = ml.compute_week_history(date.today(), phases, [{"date": d} for d in _logged])
    streak = ml.compute_streak(history)
    _render_weekly_rollup_banner(history, streak)
    if not _sync_ok and _sync_err:
        st.caption("Weekly rollup sync unavailable — showing live data only.")
    if not _garmin_sync_ok and _garmin_sync_err:
        st.caption("Garmin daily sync unavailable — will retry next visit.")

    _render_day_strip(active)
    _render_week_status_badge(history, st.session_state.get("tp_week_start"))

    if active is None:
        _render_no_active_phase(phases)
        nav.inject("training")
        st.stop()

    _today = date.today()
    _selected = st.session_state.tp_selected_date
    if _selected != _today:
        _render_day_detail(_selected, active, phases)
        nav.inject("training")
        st.stop()

    # ── selected == today: existing day_num-driven flow, unchanged below ────────

    # ── Day-overview screen — shown until "Start" is tapped for today's session ─
    # Upper bound is however many days are actually authored in training_plan.py
    # (originally a hardcoded 14; extended once a 7-day rehab-extension block or
    # any future block adds more PLAN entries) rather than a magic number.
    _plan_days = len(tp.PLAN)
    if (1 <= day_num <= _plan_days and not st.session_state.tp_done_today
            and not st.session_state.tp_started):
        _directive = _engine_directive()
        today_plan = tp.PLAN[day_num]
        exercises  = today_plan["exercises"]
        _render_overview(day_num, active, today_plan, exercises, _directive, _readiness_modifier)
        nav.inject("training")
        st.stop()

    st.title("Training Plan")

    # ── Status strip ──────────────────────────────────────────────────────────
    session_active = (
        1 <= day_num <= _plan_days
        and not st.session_state.tp_done_today
        and st.session_state.tp_ex_idx > 0
    )

    _sc1, _sc2, _sc3 = st.columns(3)
    _sc1.metric("Plan Start", str(plan_start))
    _sc2.metric("Today", str(date.today()))
    if 1 <= day_num <= _plan_days:
        _sc3.metric("Day", f"{day_num} / {_plan_days}")
        _progress_bar("Phase progress", f"{day_num}/{_plan_days}", day_num / _plan_days)

    if session_active:
        st.markdown(
            "<div style='background:#150808;border:1px solid #FF2D44;border-radius:8px;"
            "padding:10px 12px;margin-bottom:8px;'>"
            "<div style='font-size:10px;color:#FF2D44;letter-spacing:1px;margin-bottom:4px;'>"
            "SESSION IN PROGRESS</div>"
            "<div style='font-size:11px;color:#8A99A3;'>Navigate freely — your place is saved.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if st.button("Exit Training", use_container_width=True):
            st.session_state.tp_exit_confirm = True
            st.rerun()

    st.divider()

    # ── Before plan start ─────────────────────────────────────────────────────
    if day_num < 1:
        days_until = (plan_start - date.today()).days
        st.info(f"Your plan starts in {days_until} day(s) on {plan_start}. Come back then.")
        st.stop()

    # ── Plan complete ─────────────────────────────────────────────────────────
    if day_num > _plan_days:
        st.balloons()
        st.success(
            f"**{_plan_days}-Day Stage 1 Rehab Complete.**\n\n"
            "Your objectives: tissue tolerance established, neural desensitisation, "
            "gluteal activation, hip hinge pattern, and spinal stability foundation.\n\n"
            "Open **Autoregulation** to check Stage 1 → 2 progression criteria. "
            "If criteria are met, confirm with your physiotherapist before advancing."
        )
        if st.button("Back to Home", type="primary", use_container_width=True):
            st.session_state["_nav_page"] = "home"
            st.rerun()
        nav.inject("training")
        st.stop()

    # ── Engine directive banner ───────────────────────────────────────────────
    _directive = _engine_directive()
    _sig = _directive["signal_color"]
    if _sig == "red":
        st.error("Rest day recommended today — mobility and walking only. No loaded exercises.")
    elif _sig in ("yellow", "orange"):
        st.warning("Reduced load today — keep this session controlled. Don't push to failure.")
    # green / grey: no banner — train normally, nothing to flag

    # ── Active plan day ───────────────────────────────────────────────────────
    today_plan = tp.PLAN[day_num]
    exercises  = today_plan["exercises"]
    n_ex       = len(exercises)

    # ── EXIT CONFIRMATION SCREEN ──────────────────────────────────────────────
    if st.session_state.tp_exit_confirm:
        ex_done = st.session_state.tp_ex_idx
        st.markdown(
            f"<div style='background:#0E0A0A;border:2px solid #FF2D44;border-radius:12px;"
            f"padding:28px 32px;margin:24px 0;text-align:center;'>"
            f"<div style='font-size:13px;color:#FF2D44;letter-spacing:2px;font-family:monospace;"
            f"margin-bottom:10px;'>EXIT TRAINING</div>"
            f"<div style='font-size:22px;font-weight:700;color:#FFFFFF;margin-bottom:8px;'>"
            f"Are you sure you want to leave?</div>"
            f"<div style='font-size:14px;color:#8A99A3;line-height:1.6;'>"
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
                _reset_session(day_num)
                st.rerun()
        st.stop()

    # Header
    st.markdown(
        f"<h2 style='margin-bottom:2px;'>Day {day_num} of {_plan_days}</h2>"
        f"<p style='color:#E8ECEF;font-family:monospace;font-size:15px;margin-top:0;'>"
        f"{today_plan['objective']}</p>"
        f"<p style='color:#8A99A3;font-size:13px;'>{today_plan['phase']} — RPE target: ≤{today_plan['session_rpe_target']}/10</p>",
        unsafe_allow_html=True,
    )

    # Overall day progress bar
    ex_idx = n_ex if st.session_state.tp_done_today else st.session_state.tp_ex_idx
    _progress_bar("Today's session", f"{ex_idx}/{n_ex}", ex_idx / n_ex)
    st.divider()

    # ── Session done for today ────────────────────────────────────────────────
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
            if st.session_state.tp_session_start_ts > 0:
                elapsed_minutes = max(5, int((time.time() - st.session_state.tp_session_start_ts) / 60))
            else:
                elapsed_minutes = sess.estimate_duration(exercises)
            with st.form("log_session_form"):
                session_rpe = st.slider("Session RPE — how hard did it feel?",
                                        min_value=1, max_value=10, value=5,
                                        help="1 = very easy  ·  10 = maximal effort")
                st.caption(
                    f"Session duration: **{elapsed_minutes} min** (auto-timed)  ·  "
                    f"Estimated AU: **{5 * elapsed_minutes}** (RPE × duration)"
                )
                session_notes = st.text_area(
                    "Session Notes (optional)",
                    placeholder="e.g. Hip flexors felt looser. Slight tightness on last bird-dog set.",
                    height=80,
                )
                save_btn = st.form_submit_button("Save Session to Log",
                                                 type="primary", use_container_width=True)
            if save_btn:
                with st.spinner("Saving session to Notion…"):
                    _auto_log_session(day_num, exercises, session_rpe, elapsed_minutes, session_notes)
                st.session_state.tp_session_logged = True
                _save_checkpoint(day_num)
                st.rerun()

        else:
            st.balloons()
            st.markdown(
                f"<div style='background:#1A2026;"
                f"border-radius:16px;padding:32px 24px;margin-bottom:20px;text-align:center;'>"
                f"<div style='font-size:13px;color:#00E874;font-family:monospace;"
                f"letter-spacing:3px;margin-bottom:10px;'>✓ DAY {day_num} COMPLETE</div>"
                f"<div style='font-size:26px;font-weight:700;color:#FFFFFF;margin-bottom:10px;'>"
                f"Congratulations — session logged.</div>"
                f"<div style='font-size:14px;color:#8A99A3;line-height:1.65;'>"
                f"All {n_ex} exercises done. Record your pain score in Morning Check-In "
                f"and come back tomorrow.</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if day_num < _plan_days:
                next_plan = tp.PLAN[day_num + 1]
                with st.expander(f"Preview: Day {day_num + 1} — {next_plan['objective']}", expanded=False):
                    for nex in next_plan["exercises"]:
                        st.markdown(f"- {sess.type_icon(nex)} **{nex['name']}** — {sess.prescription_label(nex)}")
            if st.button("Back to Home", type="primary", use_container_width=True):
                st.session_state["_nav_page"] = "home"
                st.rerun()

        nav.inject("training")
        st.stop()

    # ── Readiness modifier badge ──────────────────────────────────────────────
    if _volume_factor != 1.0:
        _badge_color = (
            "#E8ECEF" if _volume_factor > 1.0
            else ("#FFD700" if _volume_factor >= 0.75 else "#FF4B4B")
        )
        st.markdown(
            f"<div style='background:#0E1117;border-left:3px solid {_badge_color};"
            f"border-radius:6px;padding:8px 12px;margin-bottom:8px;'>"
            f"<span style='font-size:11px;color:{_badge_color};font-family:monospace;"
            f"letter-spacing:1px;'>SESSION ADAPTED &nbsp;·&nbsp; "
            f"{_readiness_modifier['description']}</span></div>",
            unsafe_allow_html=True,
        )

    # ── Exercise progress list ────────────────────────────────────────────────
    with st.expander("Today's Exercises", expanded=False):
        for i, ex in enumerate(exercises):
            done   = i < st.session_state.tp_ex_idx
            active = i == st.session_state.tp_ex_idx
            icon   = "✅" if done else ("▶" if active else "○")
            color  = "#E8ECEF" if active else ("#666" if done else "#444")
            st.markdown(
                f"<div style='color:{color};font-size:13px;padding:3px 0;'>"
                f"{icon} {ex['name']}</div>",
                unsafe_allow_html=True,
            )

    # ── Active exercise ───────────────────────────────────────────────────────
    if st.session_state.tp_ex_idx >= n_ex:
        st.session_state.tp_done_today = True
        _save_checkpoint(day_num)
        st.rerun()

    ex   = engine.apply_exercise_volume_modifier(
               exercises[st.session_state.tp_ex_idx], _volume_factor)
    ex_n = st.session_state.tp_ex_idx + 1

    # Unique timer keys scoped to this exercise / set / rep / side
    _eidx = st.session_state.tp_ex_idx
    _eset = st.session_state.tp_set
    _erep = st.session_state.tp_rep_in_set
    _side = st.session_state.tp_side
    _hold_key = f"tp_h_{_eidx}_{_eset}_{_erep}_{_side}"
    _rest_key = f"tp_r_{_eidx}_{_eset}"
    _dur_key  = f"tp_d_{_eidx}"

    # Exercise header
    st.markdown(
        f"<div style='background:#1A2026;"
        f"border-radius:16px;padding:16px 20px;margin-bottom:12px;'>"
        f"<div style='font-size:11px;color:#E8ECEF;font-family:monospace;"
        f"text-transform:uppercase;letter-spacing:2px;'>Exercise {ex_n} of {n_ex}</div>"
        f"<div style='font-size:24px;font-weight:700;color:#E8ECEF;margin:4px 0;'>"
        f"{sess.type_icon(ex)} {ex['name']}</div>"
        f"<div style='font-size:13px;color:#8A99A3;font-family:monospace;'>"
        f"{sess.prescription_label(ex)}</div></div>",
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

    # Per-exercise note — one per exercise (keyed on _eidx, not on set/rep),
    # so it persists across every set of this exercise and resets to blank
    # once tp_ex_idx advances to the next one. Read back by _auto_log_session
    # via this same key, independent of the session-wide notes field on the
    # "Save Session to Log" screen at the end.
    with st.expander("📝 Add a note for this exercise"):
        st.text_area(
            "Note", key=f"tp_note_{_eidx}", label_visibility="collapsed",
            placeholder="e.g. right hip felt tight on the last set, form cue worked well...",
            height=68,
        )

    # ── Set progress and timers ───────────────────────────────────────────────
    ex_type    = ex["type"]
    cur_set    = st.session_state.tp_set
    total_sets = ex.get("sets", 1)
    cur_rep    = st.session_state.tp_rep_in_set

    col_prog, col_timer = st.columns([1, 2], gap="large")

    with col_prog:
        if ex_type == "duration":
            st.markdown(
                f"<div style='text-align:center;padding:12px;'>"
                f"<div style='font-size:11px;color:#8A99A3;font-family:monospace;letter-spacing:2px;'>DURATION</div>"
                f"<div style='font-size:48px;font-weight:700;color:#FFD700;'>{ex['duration_minutes']}</div>"
                f"<div style='font-size:13px;color:#8A99A3;'>minutes</div></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='text-align:center;padding:8px;'>"
                f"<div style='font-size:11px;color:#8A99A3;font-family:monospace;letter-spacing:2px;'>SET</div>"
                f"<div style='font-size:56px;font-weight:700;color:#E8ECEF;line-height:1;'>"
                f"{cur_set}<span style='font-size:28px;color:#555;'>/{total_sets}</span></div></div>",
                unsafe_allow_html=True,
            )
            if ex.get("laterality") == "unilateral":
                _side_color = "#FF9800" if _side == "right" else "#4FC3F7"
                st.markdown(
                    f"<div style='text-align:center;margin-top:4px;'>"
                    f"<div style='font-size:10px;color:#8A99A3;font-family:monospace;letter-spacing:2px;'>SIDE</div>"
                    f"<div style='font-size:28px;font-weight:700;color:{_side_color};line-height:1.1;'>"
                    f"{_side.upper()}</div></div>",
                    unsafe_allow_html=True,
                )
            if ex_type == "hold_reps" and ex.get("reps_in_set"):
                st.markdown(
                    f"<div style='text-align:center;'>"
                    f"<div style='font-size:11px;color:#8A99A3;font-family:monospace;letter-spacing:2px;'>REP</div>"
                    f"<div style='font-size:40px;font-weight:700;color:#E8ECEF;line-height:1;'>"
                    f"{cur_rep}<span style='font-size:22px;color:#555;'>/{ex['reps_in_set']}</span></div></div>",
                    unsafe_allow_html=True,
                )
            if ex_type == "reps":
                st.markdown(
                    f"<div style='text-align:center;margin-top:8px;'>"
                    f"<div style='font-size:11px;color:#8A99A3;font-family:monospace;letter-spacing:2px;'>REPS</div>"
                    f"<div style='font-size:48px;font-weight:700;color:#E8ECEF;line-height:1;'>{ex['reps']}</div></div>",
                    unsafe_allow_html=True,
                )
                if ex.get("tempo"):
                    ec, p, cn = (ex["tempo"].split("-") + ["?", "?", "?"])[:3]
                    st.markdown(
                        f"<div style='text-align:center;margin-top:6px;'>"
                        f"<span style='font-size:11px;color:#8A99A3;font-family:monospace;'>"
                        f"TEMPO: {ec}s lower · {p}s pause · {cn}s lift</span></div>",
                        unsafe_allow_html=True,
                    )

    with col_timer:
        phase  = st.session_state.tp_phase
        is_uni = ex.get("laterality") == "unilateral"

        def _mark_start():
            if st.session_state.tp_session_start_ts == 0:
                st.session_state.tp_session_start_ts = time.time()

        if ex_type == "duration":
            _is_garmin_activity = sess.is_run_or_walk(ex) and repo.get_repository().garmin_configured()
            if _is_garmin_activity:
                _lo = max(0, ex["duration_minutes"] - sess.GARMIN_ACTIVITY_BUFFER_MINUTES)
                _hi = ex["duration_minutes"] + sess.GARMIN_ACTIVITY_BUFFER_MINUTES
                st.info(
                    f"🏃 Start **{ex['name']}** on your Garmin watch now. Tap Complete "
                    f"below when you're done — today's most recent Garmin activity "
                    f"lasting {_lo}-{_hi} min is pulled in automatically, however long "
                    f"ago it started."
                )
            else:
                _duration_timer(ex["duration_minutes"], timer_key=_dur_key)
            if st.button("✓ Activity Complete", type="primary", use_container_width=True):
                _mark_start()
                if _is_garmin_activity:
                    r = repo.get_repository()
                    # Matches on the ACTIVITY'S OWN duration (± buffer) rather
                    # than on how recently it started — a 15-min planned walk
                    # matches today's most recent 10-20 min activity, whether
                    # Complete is tapped immediately or after a delay.
                    try:
                        minutes, matched = r.get_recent_garmin_activity_minutes(
                            ex["duration_minutes"], sess.GARMIN_ACTIVITY_BUFFER_MINUTES)
                    except Exception:
                        minutes, matched = 0.0, []
                    if minutes > 0:
                        st.session_state.tp_garmin_minutes[st.session_state.tp_ex_idx] = minutes
                        st.session_state.tp_garmin_activity_detail[st.session_state.tp_ex_idx] = (
                            sess.summarize_garmin_activities(matched)
                        )
                        st.toast(f"Pulled {minutes:.0f} min from Garmin for {ex['name']}.")
                    else:
                        st.toast(
                            f"No Garmin activity today lasting {_lo}-{_hi} min — "
                            f"logged with the planned duration."
                        )
                st.session_state.tp_ex_idx += 1
                st.session_state.tp_set = 1
                st.session_state.tp_rep_in_set = 1
                st.session_state.tp_side = "right"
                st.session_state.tp_phase = "intro"
                _save_checkpoint(day_num)
                st.rerun()

        elif ex_type == "reps":
            if phase == "resting":
                _rest_timer(ex["rest_seconds"], timer_key=_rest_key)
                if st.button("→ Next Set", type="primary", use_container_width=True):
                    st.session_state.tp_side = "right"
                    st.session_state.tp_phase = "intro"
                    _save_checkpoint(day_num)
                    st.rerun()
            else:
                # Clear any stale tp_auto_start from the rest timer — reps exercises have no
                # hold timer to consume it, so it must not leak into the next exercise.
                components.html('<script>try{localStorage.removeItem("tp_auto_start");}catch(e){}</script>', height=0)
                _side_note = f" — {_side.upper()} SIDE" if is_uni else ""
                st.markdown(
                    f"<div style='background:#1A2026;border-radius:8px;padding:20px;text-align:center;'>"
                    f"<div style='color:#8A99A3;font-size:13px;margin-bottom:8px;'>"
                    f"Perform {ex['reps']} reps{_side_note}</div>"
                    f"<div style='color:#E8ECEF;font-size:12px;'>"
                    + (f"Tempo: {ex['tempo'].replace('-','s – ')}s" if ex.get("tempo") else "Control each rep")
                    + "</div></div>",
                    unsafe_allow_html=True,
                )
                _btn_label = "✓ Right Side Done" if (is_uni and _side == "right") else f"✓ Set {cur_set} Complete"
                if st.button(_btn_label, type="primary", use_container_width=True):
                    _mark_start()
                    if is_uni and _side == "right":
                        st.session_state.tp_side = "left"
                    else:
                        st.session_state.tp_side = "right"
                        if cur_set >= total_sets:
                            st.session_state.tp_ex_idx += 1
                            st.session_state.tp_set = 1
                            st.session_state.tp_phase = "intro"
                        else:
                            st.session_state.tp_set += 1
                            st.session_state.tp_phase = "resting"
                    _save_checkpoint(day_num)
                    st.rerun()

        elif ex_type == "hold":
            if phase == "resting":
                _rest_timer(ex["rest_seconds"], timer_key=_rest_key)
                if st.button("→ Next Set", type="primary", use_container_width=True):
                    st.session_state.tp_side = "right"
                    st.session_state.tp_phase = "intro"
                    _save_checkpoint(day_num)
                    st.rerun()
            else:
                _hold_label = f"HOLD — {_side.upper()} SIDE" if is_uni else "HOLD"
                # Right→left side transition has no rest timer, so the hold timer itself
                # must flag the left side's timer to auto-start.
                _set_auto_start = is_uni and _side == "right"
                _hold_timer(ex["hold_seconds"], label=_hold_label, timer_key=_hold_key,
                            set_auto_start=_set_auto_start)
                _btn_label = "✓ Right Side Done" if (is_uni and _side == "right") else f"✓ Set {cur_set} Complete"
                if st.button(_btn_label, type="primary", use_container_width=True):
                    _mark_start()
                    if is_uni and _side == "right":
                        st.session_state.tp_side = "left"
                    else:
                        st.session_state.tp_side = "right"
                        if cur_set >= total_sets:
                            st.session_state.tp_ex_idx += 1
                            st.session_state.tp_set = 1
                            st.session_state.tp_phase = "intro"
                        else:
                            st.session_state.tp_set += 1
                            st.session_state.tp_phase = "resting"
                    _save_checkpoint(day_num)
                    st.rerun()

        elif ex_type == "hold_reps":
            reps_per_set = ex.get("reps_in_set", 5)
            if phase == "resting":
                _rest_timer(ex["rest_seconds"], timer_key=_rest_key)
                if st.button("→ Next Set", type="primary", use_container_width=True):
                    st.session_state.tp_rep_in_set = 1
                    st.session_state.tp_side = "right"
                    st.session_state.tp_phase = "intro"
                    _save_checkpoint(day_num)
                    st.rerun()
            else:
                _side_suffix = f" — {_side.upper()}" if is_uni else ""
                # More reps in this set → next rep's hold timer needs to auto-start.
                # Last rep, side-switch (unilateral right→left) → left side rep 1 needs to auto-start.
                # Last rep, set ends → rest timer will set the flag; don't set it here.
                _set_auto_start = (cur_rep < reps_per_set) or (
                    cur_rep >= reps_per_set and is_uni and _side == "right"
                )
                _hold_timer(ex["hold_seconds"], label=f"REP {cur_rep} of {reps_per_set}{_side_suffix}",
                            timer_key=_hold_key, set_auto_start=_set_auto_start)
                if st.button(f"✓ Rep {cur_rep} Done", type="primary", use_container_width=True):
                    _mark_start()
                    if cur_rep >= reps_per_set:
                        if is_uni and _side == "right":
                            st.session_state.tp_side = "left"
                            st.session_state.tp_rep_in_set = 1
                        else:
                            st.session_state.tp_side = "right"
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
                    _save_checkpoint(day_num)
                    st.rerun()

    # ── Clinical guidance section ─────────────────────────────────────────────
    st.divider()
    col_bio, col_prog_reg = st.columns(2, gap="large")

    with col_bio:
        st.markdown(
            f"<div style='background:#1A2026;border-radius:16px;padding:14px;'>"
            f"<div style='font-size:10px;color:#E8ECEF;font-family:monospace;"
            f"letter-spacing:2px;margin-bottom:6px;'>BIOMECHANICAL FOCUS</div>"
            f"<div style='font-size:13px;color:#C8CAD0;line-height:1.55;'>{ex['biomechanical_focus']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_prog_reg:
        st.markdown(
            f"<div style='background:#1A2026;border-radius:16px;padding:14px;'>"
            f"<div style='font-size:10px;color:#E8ECEF;font-family:monospace;"
            f"letter-spacing:2px;margin-bottom:6px;'>PROGRESSION / REGRESSION</div>"
            f"<div style='font-size:12px;color:#C8CAD0;line-height:1.5;'>"
            f"<span style='color:#E8ECEF;'>▲ Progress if:</span> {ex['progression']}<br><br>"
            f"<span style='color:#FF4B4B;'>▼ Regress if:</span> {ex['regression']}"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    # ── Skip exercise option ──────────────────────────────────────────────────
    with st.expander("Skip this exercise", expanded=False):
        st.caption("Only skip if pain prevents performance. Log the reason in session notes.")
        if st.button("Skip — move to next exercise", use_container_width=True):
            st.session_state.tp_ex_idx += 1
            st.session_state.tp_set = 1
            st.session_state.tp_rep_in_set = 1
            st.session_state.tp_phase = "intro"
            _save_checkpoint(day_num)
            st.rerun()
