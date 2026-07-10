"""
services/sessions.py — pure training-session logic + orchestration.

Extracted from views/training.py's private module-level functions (checkpoint
payload shape, coach-message derivation, movement categorization, volume/
duration estimation, exercise-set-data construction, and the day-view routing
decision). All pure: data in, data out, no st.session_state, no I/O, no hidden
clock reads — `today` is always an explicit parameter where relevant.

The Streamlit layer still owns st.session_state itself (reading/writing
tp_ex_idx etc.) and calls these functions with plain values pulled out of it.
"""

from __future__ import annotations

import re
from datetime import date

from services import plan as _plan
from services.models import Phase

_RUN_WALK_PATTERN = re.compile(r"\b(walk|run)\w*")

# +/- minutes around an exercise's own planned duration when the training
# page's Complete button searches today's Garmin activities for one whose
# OWN duration matches (a 15-min planned walk matches any activity lasting
# 10-20 min, regardless of when it started). Was a per-user Sync-page
# setting; hardcoded by request. Change this single value if 5 minutes
# turns out to be too tight/loose — nothing else needs to stay in sync
# (grep GARMIN_ACTIVITY_BUFFER_MINUTES to confirm both call sites:
# views/training.py's Garmin info banner and its "✓ Activity Complete" handler).
GARMIN_ACTIVITY_BUFFER_MINUTES = 5

# The pre-session release protocol (always the same shared exercises inserted
# first in every plan day) — detected by name so this stays in sync with
# whatever training_plan.py's shared release-exercise constants are named.
RELEASE_EXERCISE_NAMES = frozenset({
    "Upper Glute / TFL Self-Release",
    "Right Posterior Hip Capsule Stretch",
    "Piriformis Contract-Relax (PNF)",
    "Ischial Tuberosity Hamstring Release",
    "Right Hip Tendon Path Drill (Coxa Saltans)",
})

CHECKPOINT_FIELDS = (
    "tp_ex_idx", "tp_set", "tp_rep_in_set", "tp_phase", "tp_started",
    "tp_done_today", "tp_session_logged", "tp_side", "tp_session_start_ts",
)


def coach_message(directive: dict, today_plan: dict) -> tuple[str, str]:
    """Dynamic headline sourced from the real engine directive (readiness/
    ACWR-driven), falling back to the day's clinical objective — never
    fabricated copy."""
    headline = directive.get("action") or today_plan["objective"]
    subtitle = today_plan["phase"]
    return headline, subtitle


def is_run_or_walk(ex: dict) -> bool:
    """Word-boundary match on "walk"/"run" (plus suffixes: walking, running) —
    a plain substring check would false-positive on names like "Trunk Rotation"."""
    return bool(_RUN_WALK_PATTERN.search(ex["name"].lower()))


def summarize_garmin_activities(matched: list[dict]) -> dict:
    """Collapse the (usually one, occasionally several) Garmin activities
    matched within the Complete-button's search window into the fields
    logged alongside the Garmin-verified duration: avg_hr and distance/
    calories are summed/averaged across all matched activities (duration-
    weighted for avg_hr), max_hr is the max across them. Returns None for
    any field with nothing to compute (e.g. a Stopwatch-type activity with
    no HR data) rather than 0, so a blank Notion cell isn't mistaken for
    a real zero reading."""
    total_duration = sum((a.get("duration") or 0) for a in matched)
    hr_weighted = sum((a.get("averageHR") or 0) * (a.get("duration") or 0) for a in matched)
    max_hr_vals = [a["maxHR"] for a in matched if a.get("maxHR")]
    distance_total = sum((a.get("distance") or 0) for a in matched)
    calories_total = sum((a.get("calories") or 0) for a in matched)
    return {
        "avg_hr": round(hr_weighted / total_duration) if total_duration and hr_weighted else None,
        "max_hr": max(max_hr_vals) if max_hr_vals else None,
        "distance_km": round(distance_total / 1000, 2) if distance_total else None,
        "calories": round(calories_total) if calories_total else None,
    }


def movement_category(ex: dict) -> str:
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


def focus_areas(exercises: list[dict]) -> list[str]:
    seen: list[str] = []
    for ex in exercises:
        cat = movement_category(ex)
        if cat not in seen:
            seen.append(cat)
    return seen


def split_release_and_main(exercises: list[dict]) -> tuple[list[dict], list[dict]]:
    release = [ex for ex in exercises if ex["name"] in RELEASE_EXERCISE_NAMES]
    main    = [ex for ex in exercises if ex["name"] not in RELEASE_EXERCISE_NAMES]
    return release, main


def type_icon(ex: dict) -> str:
    return {"hold": "⏱", "hold_reps": "⏱", "reps": "↕", "duration": "🚶"}.get(ex["type"], "•")


def prescription_label(ex: dict) -> str:
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


def planned_reps(ex: dict) -> int:
    t = ex["type"]
    if t == "reps":      return ex.get("reps") or 1
    if t == "hold_reps": return ex.get("reps_in_set") or 1
    return 1


def make_sets_data(ex: dict) -> list[dict]:
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


def estimate_duration(exercises: list[dict]) -> int:
    total = 120
    for ex in exercises:
        t, sets, rest = ex["type"], ex.get("sets", 1), ex.get("rest_seconds", 60)
        if t == "duration":    total += (ex.get("duration_minutes") or 0) * 60 + 30
        elif t == "hold":      total += sets * (ex.get("hold_seconds") or 0) + (sets - 1) * rest + 30
        elif t == "hold_reps": total += sets * (ex.get("hold_seconds") or 0) * (ex.get("reps_in_set") or 1) + (sets - 1) * rest + 30
        elif t == "reps":      total += sets * 20 + (sets - 1) * rest + 30
    return max(10, round(total / 60))


def checkpoint_payload(day_num: int, state: dict) -> dict:
    """state: a plain dict of the CHECKPOINT_FIELDS pulled from st.session_state
    by the caller. Returns the exact dict to JSON-encode and persist."""
    data = {"day_num": day_num}
    data.update({k: state[k] for k in CHECKPOINT_FIELDS})
    return data


def restore_from_checkpoint(checkpoint: dict | None, day_num: int) -> dict | None:
    """None if there's no checkpoint or it's for a different day (a stale/
    prior-day checkpoint must never resurrect into today's — or any other
    currently-viewed day's — state)."""
    if not checkpoint or checkpoint.get("day_num") != day_num:
        return None
    return {k: checkpoint[k] for k in CHECKPOINT_FIELDS if k in checkpoint}


def seed_default_phase(phases: list[Phase], plan_start: date | None) -> list[Phase]:
    """If no phases are configured yet and a plan start date exists, seed
    Phase 1 from it. Returns the phases list unchanged otherwise. Caller is
    responsible for persisting the result if it changed."""
    if phases or plan_start is None:
        return phases
    return [_plan.default_phase(plan_start)]


def day_view_state(selected: date, today: date, active: Phase | None, is_logged: bool) -> str:
    """Which of the day-detail views applies for `selected`:
    "today" | "past_completed" | "past_missed" | "future" | "rest" | "no_phase".
    "today" only ever means selected == today AND a phase is active; the
    Streamlit layer still owns what "today" actually renders (the live
    overview/guided-flow/done screens), this only decides routing."""
    if active is None:
        return "no_phase"
    day_num = _plan.day_number_in_phase(active, selected)
    in_phase = 1 <= day_num <= active.length_days
    if not in_phase:
        return "rest"
    if selected == today:
        return "today"
    if selected < today:
        return "past_completed" if is_logged else "past_missed"
    return "future"
