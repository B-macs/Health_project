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
from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import training_plan as tp
from training_constants import EXERCISE_MOVEMENT_WEIGHT as _EXERCISE_MOVEMENT_WEIGHT
from services import engine
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

#: Garmin activityType.typeKey -> the CANONICAL exercise name the outdoor
#: importer logs. Fixed names, never Garmin's free-text activityName: the
#: exercise NAME is the key into EXERCISE_MOVEMENT_WEIGHT and
#: EXERCISE_BODY_REGION, and a dynamic name would score at the unmapped 1.0
#: barbell tier (the 2026-08-01 Stage 1 bug by another door) and vanish from
#: the leg-day definition. Measured 2026-08-10: a real Alpine hike arrives
#: typed "walking" ("Mittenwald Walking"), which is why the walk family maps
#: to the same tier as hiking rather than being second-guessed by name.
OUTDOOR_EXERCISE_BY_TYPE: dict[str, str] = {
    "hiking": "Outdoor Hike",
    "walking": "Outdoor Walk",
    "casual_walking": "Outdoor Walk",
    "speed_walking": "Outdoor Walk",
    "trail_running": "Outdoor Trail Run",
    "running": "Outdoor Run",
}

#: Any OTHER activity the athlete picks anyway (never a wall — the type
#: filter is advice, the athlete's pick is the decision) logs under this
#: name, with the Garmin type recorded in the session note.
OUTDOOR_FALLBACK_EXERCISE = "Outdoor Activity"


def outdoor_exercise_name(type_key: str | None) -> str:
    """DETERMINISTIC. The canonical exercise name for a Garmin activity
    type — the fallback name for anything outside the outdoor family."""
    return OUTDOOR_EXERCISE_BY_TYPE.get((type_key or "").lower(), OUTDOOR_FALLBACK_EXERCISE)

# The pre-session release protocol (always the same shared exercises inserted
# first in every plan day) — detected by name so this stays in sync with
# whatever training_plan.py's shared release-exercise constants are named.
RELEASE_EXERCISE_NAMES = frozenset({
    "Upper Glute / TFL Self-Release",
    "Right Posterior Hip Capsule Stretch",
    # The revised-cue variant was missing here from the day it was authored,
    # so every Stage 2A gym session has been rendering its capsule stretch in
    # the "Workout" accordion rather than the release block — display-only, but
    # it puts a release item where the working sets are listed. Found 2026-08-14
    # by the Stage 2B block test, which asserts every session OPENS with a
    # release exercise.
    "Right Posterior Hip Capsule Stretch (Revised Cue)",
    # Same omission would put the quadruped version in the "Workout"
    # accordion instead of the release block.
    "Right Posterior Hip Capsule Stretch (Quadruped)",
    "Piriformis Contract-Relax (PNF)",
    "Ischial Tuberosity Hamstring Release",
    "Right Hip Tendon Path Drill (Coxa Saltans)",
    "Anterior Hip Pressure Release",
})

CHECKPOINT_FIELDS = (
    "tp_ex_idx", "tp_set", "tp_rep_in_set", "tp_phase", "tp_started",
    "tp_done_today", "tp_session_logged", "tp_side", "tp_session_start_ts",
    "tp_actuals", "tp_set_log", "tp_garmin_declared", "tp_rest_started_at",
    # Per-exercise notes, {exercise_idx: text}. A PLAIN dict rather than the
    # `tp_note_<idx>` WIDGET keys they are typed into, because Streamlit drops
    # a widget's value from session_state on any run in which that widget is
    # not instantiated — and views/training.py renders exactly ONE exercise
    # per run. Every per-exercise note written before 2026-08-17 was lost that
    # way; see _record_note there for the full mechanism.
    "tp_notes",
    # The accessory session's whole day dict, because unlike a plan day it
    # cannot be looked up again from a day number — it was CHOSEN, from
    # regional strain readings that will have moved by the time a dropped
    # phone reconnects. `None` on a plan session, and it must stay in
    # _init_state's defaults: the checkpoint payload is built by indexing
    # session_state with every name here, and a missing one silently stops
    # the whole checkpoint saving.
    "tp_accessory_plan",
    # The save-in-progress markers. A session's id is minted ONCE, on the first
    # press of Save, and every exercise written under it is remembered here, so
    # a save that stops partway (a Notion 429 twenty rows in, a dropped
    # connection) resumes under the SAME session from the exercise that failed.
    # Before 2026-09-11 every press minted a fresh id and rewrote everything,
    # which is how 2026-09-10 was logged three times: 8, 20 and 2 exercises
    # under three ids, 1,306 AU for one session, strain 17.1 for the day.
    "tp_pending_session",
    "tp_saved_exercise_idx",
    "tp_last_saved_exercise_id",
)

#: Read-time HOLD, the biometrics.HRV_GARMIN_HOLD idiom. `rest_taken_seconds`
#: is RECORDED on every set from the day this ships, and feeds NOTHING —
#: exercise_seconds_from_sets keeps summing the PRESCRIBED `rest`.
#:
#: The reason is key rule 2b's, one level down. Session AU is computed from a
#: duration, and switching the duration's rest term from prescribed to measured
#: would move Strain and ACWR on *whether the field exists* rather than on
#: training: every session before this commit has prescribed rest only, every
#: session after has measured, and the two would sit in the same 7/28-day ACWR
#: window in different units. That is the identical failure the HR-vs-RPE strain
#: split is held for.
#:
#: LIFT IT ON A MEASUREMENT, NOT A DATE: once enough sessions carry real rest,
#: compare measured against prescribed per set — if the two agree closely the
#: switch is a no-op and can just be made; if they diverge, the divergence is
#: itself the finding the rest-interval review wanted, and the series needs
#: re-deriving over a stated window rather than stepping mid-stream.
REST_TAKEN_FEEDS_DURATION = False


def is_working_set(s: dict) -> bool:
    """False for a warm-up / ramp set, True for everything else.

    THE DEFAULT IS 'WORKING'. Every set logged before the flag existed has no
    `is_warmup` key at all, and those were all working sets — so an absent key
    must read as work, never as a warm-up. Getting that backwards would silently
    empty the entire pre-2026-08 tonnage and strength history.

    services/tonnage.py and services/strength.py deliberately import nothing
    from services/, so each repeats this one expression inline rather than
    taking a dependency on this module; tests/test_warmup_sets.py pins that all
    three agree.
    """
    return not s.get("is_warmup")

BAND_TIERS = engine.BAND_TIERS
BAND_TIER_LABELS = engine.BAND_TIER_LABELS


def set_timestamp(now: datetime, tz_name: str = "") -> str:
    """The `ts` written on every per-set record, as an ISO string that CARRIES
    ITS UTC OFFSET.

    Pure, and `now` is an explicit parameter, per this module's contract --
    the clock read stays in the Streamlit layer.

    Why this exists. Sets used to be stamped with a bare
    datetime.now().isoformat(), i.e. the naive wall clock of whatever host
    runs the app. The app does not run where the athlete trains, so on a UTC
    host a set completed at 13:08 local was recorded as "2026-08-06T11:08:27".
    Nothing about that string looks wrong -- an offset-free ISO timestamp
    reads as local -- and the error only surfaced when a session's sets were
    aligned against a Garmin activity and every one of them sat exactly two
    hours early.

    It was never merely cosmetic. services/hr_matching.py attributes heart
    rate to individual exercises by comparing these timestamps against a
    Garmin activity's clock, so a two-hour skew silently produced no overlap
    at all: the per-exercise HR feature could not work and failed quietly
    rather than loudly.

    Two properties, both load-bearing:
      1. The result is TIMEZONE-AWARE. An instant with an offset can always
         be converted; a naive one cannot be recovered without knowing which
         host wrote it.
      2. It is rendered in the ATHLETE's zone when tz_name is given, so the
         stored string also reads correctly to a human scanning Notion.

    `tz_name` is an IANA name so DST is handled; a fixed offset would be an
    hour wrong for half the year. Unknown or blank falls back to the host's
    own zone -- degrading to a still-aware local timestamp rather than
    raising mid-session, because losing a logged set to a bad config string
    would be a far worse outcome than a wrong-looking hour.
    """
    if now.tzinfo is None:
        now = now.astimezone()
    if tz_name:
        try:
            now = now.astimezone(ZoneInfo(tz_name))
        except Exception:
            now = now.astimezone()
    else:
        now = now.astimezone()
    return now.isoformat(timespec="seconds")


def coach_message(directive: dict, today_plan: dict,
                  policy: dict | None = None) -> tuple[str, str]:
    """Dynamic headline sourced from the real engine directive (readiness/
    ACWR-driven), falling back to the day's clinical objective — never
    fabricated copy.

    ⚠ THE HEADLINE MAY NOT ASK FOR LOAD THE CLAMP WILL NOT GIVE. Athlete,
    2026-08-25, holding the two screens side by side: Home read REDUCED LOAD
    while the training screen's headline read "All systems nominal. Apply
    standard progressive overload: +2.5 kg."

    Both were correct about their own input, which is the whole problem. The
    directive is only ONE of load_policy's three arguments — the readiness
    modifier and the volume multiplier can each pull a day down on their own —
    so on a day the traffic light is clear but something else is holding load,
    `directive["action"]` is still the green sentence. That is the 2026-08-06
    contradiction (header said reduced, Lat Pulldown seeded 45x10 -> 47.5x11)
    arriving through the headline instead of through the numbers.

    So when the day is reduced and the directive is nonetheless proposing MORE
    (multiplier > 1.0), the headline drops to the day's clinical objective and
    the banner carries the load decision. Nothing is invented and nothing is
    duplicated: the objective is the same fallback this function already used
    for a directive with no action text.

    `policy` is load_policy's dict. Omitting it keeps the old behaviour, which
    is correct for any caller that has no load decision in hand.
    """
    action = directive.get("action") or ""
    if action and _headline_is_superseded(directive, policy):
        action = ""
    headline = action or today_plan["objective"]
    subtitle = today_plan["phase"]
    return headline, subtitle


def _headline_is_superseded(directive: dict, policy: dict | None) -> bool:
    """True when the banner has already dealt with the directive's sentence —
    either by PRINTING it or by CONTRADICTING it.

    Two cases, and they are different:

    * DUPLICATION. On a no-reading day the banner text IS the directive's
      action, so letting the headline print it too would say the same thing
      twice, once at 26px.
    * CONTRADICTION. The directive is asking for more load on a day the policy
      has already decided is reduced — the 2026-08-25 report.

    The contradiction test is deliberately keyed on the MULTIPLIER rather than
    on the driver: a directive that reduced the day itself (yellow biometrics,
    an ACWR lock) has an action string that already says the right thing and
    NAMES THE READING, and replacing it would throw away the one place the
    reason appears. Only the "add load" sentence is the contradiction.
    """
    if not policy:
        return False
    if policy.get("banner_text") and policy["banner_text"] == directive.get("action"):
        return True
    if not policy.get("reduced"):
        return False
    try:
        return float(directive.get("multiplier", 1.0) or 1.0) > 1.0
    except (TypeError, ValueError):
        return False


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


# training_constants.EXERCISE_MOVEMENT_WEIGHT category -> display label.
# Only consulted as a FALLBACK, after the keyword cascade below: the two
# answer different questions and must not be collapsed into one. The weight
# table asks "how much load does this cost?" (Pallof Press is isolation,
# 0.3); the label asks "what pattern is this?" (Pallof Press is anti-rotation
# core work). Where they disagree, the pattern answer is the one to display.
_WEIGHT_CATEGORY_LABELS = {
    "squat":               "Squat Pattern",
    "hinge":               "Hip Hinge",
    "pull":                "Upper Body Pull",
    "upper_push":          "Upper Body Push",
    "bodyweight_compound": "Bodyweight Compound",
    "isolation":           "Isolation",
    "mobility_core":       "Mobility",
}


def movement_category(ex: dict) -> str:
    """Display label for an exercise's movement pattern.

    Order matters. Core work is checked BEFORE pushing so "Pallof Press
    Hold" doesn't match the "press" keyword and land in Upper Body Push,
    and pulling is checked before pushing for the same reason in reverse.

    2026-08-01: previously this was a 4-branch cascade whose final `return
    "Mobility"` swallowed everything it didn't recognise -- which meant every
    upper-body lift in the Stage 2 plan (Lat Pulldown, Incline DB Press,
    Single-Arm DB Row, Face Pull) plus Hip Thrust (Loaded) was logged and
    displayed as "Mobility". Fixed by adding the missing patterns and by
    falling back to the movement-weight table's own category before
    defaulting, so an unrecognised name is only ever called Mobility when
    the weight table agrees it is mobility work.

    Display-only: nothing downstream computes from this string (Strain/ACWR
    weighting reads EXERCISE_MOVEMENT_WEIGHT by exercise NAME, never this).
    Historical Notion rows keep whatever label they were written with.
    """
    name = ex["name"].lower()
    # "walk" alone over-matches: a Lateral Band Walk is a banded glute
    # activation drill done on the spot, not conditioning.
    if any(k in name for k in ("walk", "breath", "diaphragm")) and not any(
            k in name for k in ("band walk", "step walk")):
        return "Conditioning"
    if any(k in name for k in ("glute bridge", "rdl", "hinge", "deadlift",
                                "hip thrust", "hip extension")):
        return "Hip Hinge"
    # "side lying"/"side bridge" catch the side-plank family. Deliberately NOT
    # "side-lying", which would also swallow Side-Lying Hip Abduction — an
    # abductor isolation exercise, not core stability.
    if any(k in name for k in ("bird", "plank", "curl-up", "curl up", "side lying",
                                "dead bug", "pallof", "side bridge", "mcgill")):
        return "Core Stability"
    if any(k in name for k in ("squat", "lunge", "step-up", "step up",
                                "sit-to-stand", "wall sit")):
        return "Squat Pattern"
    if any(k in name for k in ("pulldown", "row", "pull-up", "chin-up", "face pull")):
        return "Upper Body Pull"
    if any(k in name for k in ("press", "push-up", "push up", "dip", "overhead")):
        return "Upper Body Push"
    entry = _EXERCISE_MOVEMENT_WEIGHT.get(ex["name"])
    if entry is not None:
        return _WEIGHT_CATEGORY_LABELS.get(entry[0], "Mobility")
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


def build_set_record(ex: dict, set_num: int, actual: dict | None,
                      completed_at: str, rest_taken_seconds: int | None = None) -> dict:
    """One ACTUALLY-COMPLETED set, captured at the moment the user taps the
    set's completion button.

    Same field shape make_sets_data() emits (so every downstream reader --
    Repository.get_recent_sessions' volume math, get_last_session_all_sets,
    services.volume, services.engine.double_progression -- works unchanged)
    plus a "ts" ISO timestamp, which the synthesized rows never had.

    `actual` is this exercise's live stepper entry (views/training.py's
    st.session_state.tp_actuals[idx]) or None for exercises that have no
    steppers at all (bodyweight/release work -- see _seed_actuals_if_needed,
    which only seeds entries for exercises with an equipment_type). Falls
    back to the exercise's own prescription per field, so a set is always
    recorded with real values whether or not steppers were in play.

    Contrast with make_sets_data() below, which this replaces for any
    exercise the guided flow actually captured: that function REPLICATES the
    plan's prescription `sets` times, so all N rows are identical by
    construction and a 10/9/8 session was indistinguishable from 10/10/10.

    THREE OPTIONAL KEYS, all written only when they carry real information, in
    the same omit-when-absent idiom `band_tier` and `ts` already use:

      is_warmup           True when the PLAN authored this exercise as a ramp
                          (training_plan._ex(warmup=True)). It is a property of
                          the authored exercise, not a per-set toggle, because a
                          ramp set is prescribed rather than decided in the
                          moment — see the warm-up review's phase 2. Excluded
                          from weekly tonnage and from every 1RM estimate.
      rest_taken_seconds  Wall-clock rest that FOLLOWED this set, matching the
                          existing `rest` field's own "rest after set N"
                          meaning. Absent on the last set of an exercise, which
                          has no rest phase after it, and absent whenever the
                          rest was never entered. Recorded only — see
                          REST_TAKEN_FEEDS_DURATION.
      reps_left /         The weaker side's own numbers, written ONLY when the
      weight_left         athlete edited the left side to something different
                          from the right. One set record still covers both
                          sides; these say the two were not equal. Without them
                          an "Edit left side" tap overwrote the whole row, so a
                          lighter left arm read as the athlete declining the
                          prescribed weight outright.
    """
    t = ex["type"]
    actual = actual or {}

    if t == "reps":
        reps = actual.get("reps") if actual.get("reps") is not None else (ex.get("reps") or 1)
        velocity, tut = "controlled", 0
    elif t == "hold_reps":
        reps = actual.get("reps") if actual.get("reps") is not None else (ex.get("reps_in_set") or 1)
        velocity, tut = "isometric", ex.get("hold_seconds") or 0
    elif t == "hold":
        reps, velocity, tut = 1, "isometric", ex.get("hold_seconds") or 0
    else:  # duration
        reps, velocity, tut = 1, "continuous", (ex.get("duration_minutes") or 0) * 60

    weight = actual.get("weight_kg")
    if weight is None:
        weight = ex.get("weight_kg") or 0.0

    record = {
        "set_num": set_num,
        "reps": reps,
        "weight": weight,
        "rest": 0 if t == "duration" else ex.get("rest_seconds", 60),
        "tut": tut,
        "velocity": velocity,
        "ts": completed_at,
    }
    band_tier = actual.get("band_tier") or ex.get("band_tier")
    if band_tier:
        record["band_tier"] = band_tier
    if ex.get("warmup"):
        record["is_warmup"] = True
    if rest_taken_seconds is not None:
        record["rest_taken_seconds"] = int(rest_taken_seconds)
    # Only when the sides genuinely differ — equal sides carry no extra keys, so
    # the overwhelmingly common bilateral/symmetric case is byte-identical to
    # what this function produced before the fields existed.
    reps_left = actual.get("reps_left")
    if reps_left is not None and reps_left != reps:
        record["reps_left"] = reps_left
    weight_left = actual.get("weight_kg_left")
    if weight_left is not None and weight_left != weight:
        record["weight_left"] = weight_left
    return record


def upsert_set_record(rows: list[dict], record: dict) -> list[dict]:
    """Add `record` to `rows`, replacing any existing entry with the same
    set_num instead of appending a second one. Mutates and returns `rows`.

    This is what makes the guided flow's "← Back" safe: backing out of an
    accidental completion and redoing that set has to overwrite what was
    logged the first time. Since the whole per-exercise list is written to
    the Notion Sets JSON in one shot at session end, an overwrite here is
    the only thing needed for the corrected value to reach everything
    derived from that JSON -- weekly tonnage (services.volume) and the
    content-weighted Session AU behind strain/ACWR both recompute from it
    rather than storing their own copy.
    """
    for i, existing in enumerate(rows):
        if existing.get("set_num") == record.get("set_num"):
            rows[i] = record
            return rows
    rows.append(record)
    return rows


def make_sets_data(ex: dict) -> list[dict]:
    """Synthesized fallback: the prescription replicated `sets` times, used
    only for exercises the guided flow captured no real sets for (a session
    logged straight from the day-overview screen, or a checkpoint restored
    from before per-set capture existed). Every row is identical by
    construction — prefer build_set_record() above, which records what
    actually happened per set."""
    t, sets, rest = ex["type"], ex.get("sets", 1), ex.get("rest_seconds", 60)
    weight = ex.get("weight_kg") or 0.0
    band_tier = ex.get("band_tier")
    extra = {"band_tier": band_tier} if band_tier else {}
    # A ramp exercise stays a ramp however it was logged — a session saved
    # straight from the day-overview screen must not launder its warm-up sets
    # into working ones. No rest_taken_seconds here: nothing was measured.
    if ex.get("warmup"):
        extra = {**extra, "is_warmup": True}
    out = []
    if t == "duration":
        out.append({"set_num": 1, "reps": 1, "weight": weight, "rest": 0,
                    "tut": (ex.get("duration_minutes") or 0) * 60, "velocity": "continuous", **extra})
    elif t == "reps":
        for i in range(1, sets + 1):
            out.append({"set_num": i, "reps": ex.get("reps") or 1, "weight": weight,
                        "rest": rest, "tut": 0, "velocity": "controlled", **extra})
    elif t == "hold":
        for i in range(1, sets + 1):
            out.append({"set_num": i, "reps": 1, "weight": weight,
                        "rest": rest, "tut": ex.get("hold_seconds") or 0, "velocity": "isometric", **extra})
    elif t == "hold_reps":
        for i in range(1, sets + 1):
            out.append({"set_num": i, "reps": ex.get("reps_in_set") or 1, "weight": weight,
                        "rest": rest, "tut": ex.get("hold_seconds") or 0, "velocity": "isometric", **extra})
    return out


# ─── Live-session reps/weight/band-tier steppers ───────────────────────────

def step_reps(current_reps: int, direction: int, floor: int = 1) -> int:
    """+/-1 rep per tap. Floored at 1 -- an exercise can't be prescribed
    zero reps. `direction` is +1 or -1."""
    return max(floor, int(current_reps) + direction)


def step_weight_kg(current_weight_kg: float, direction: int,
                    increment: float = 2.5, floor: float = 0.0) -> float:
    """+/-one `increment` per tap -- a flat 2.5kg for every loaded
    equipment type in this app (dumbbell, cable, plate). Snaps to the
    nearest valid increment multiple first (protects against float drift
    across repeated taps), then floors at 0 (can't lift negative weight)."""
    stepped = round((current_weight_kg + direction * increment) / increment) * increment
    return round(max(floor, stepped), 2)


def step_band_tier(current_tier: str, direction: int) -> str:
    """Moves one position through BAND_TIERS (Green..Black), clamped at
    both ends -- can't go lighter than Green or heavier than Black."""
    idx = BAND_TIERS.index(current_tier) if current_tier in BAND_TIERS else 0
    idx = max(0, min(len(BAND_TIERS) - 1, idx + direction))
    return BAND_TIERS[idx]


def seed_actual_entry(
    ex: dict,
    last_performance: dict | None,
    streak_label: str,
    allow_increase: bool,
    weight_increment: float = 2.5,
    last_session_sets: list[dict] | None = None,
) -> dict:
    """Decide the starting {"reps", "weight_kg", "band_tier", "source",
    "last_seen_date"} entry for one exercise's live-session steppers.

    Priority order:
      1. Double progression (engine.double_progression) -- fires only when
         ex has both "rep_min" and "rep_max" set AND last_session_sets is
         given AND every set in it hit the top of the range. When it
         fires, its (weight, reps) become the seed and everything below is
         skipped for weight/reps -- double progression takes priority over
         last_performance/readiness seeding, not merely a nudge on top of it.
      2. last_performance (Repository.get_last_performance's shape) if
         present, else the exercise's own (already volume-adjusted --
         caller passes the post apply_exercise_volume_modifier `ex`) plan
         prescription. The readiness engine's streak_label then nudges the
         weight/band-tier by one step on top -- reps are already readiness-
         adjusted upstream by apply_exercise_volume_modifier, so they are
         NOT nudged again here.

    "reps" is only populated for ex_type == "reps" -- hold_reps exercises
    (currently only Prone Y-Raise) keep their reps_in_set exactly as shown
    by the existing live per-rep hold-timer counter; only their weight is
    steppable, to avoid a stepper silently disagreeing with that counter.

    allow_increase is forced off by the caller when there's no existing
    load to build on (seed weight/tier absent), or on a red-signal engine-
    directive day -- a good readiness day must never auto-introduce load
    on an exercise the plan or history has deliberately kept bodyweight
    (e.g. Bulgarian Split Squat, weeks 1-2). Reducing load is never
    suppressed. Also gates double progression's own upward move.
    """
    entry = {"reps": None, "weight_kg": None, "band_tier": None,
              "source": "plan_default", "last_seen_date": None}
    equip = ex.get("equipment_type")
    if not equip:
        return entry
    if ex["type"] == "reps":
        entry["reps"] = planned_reps(ex)
    if equip == "band":
        entry["band_tier"] = ex.get("band_tier")
    else:
        entry["weight_kg"] = ex.get("weight_kg") if ex.get("weight_kg") is not None else 0.0

    rep_min, rep_max = ex.get("rep_min"), ex.get("rep_max")
    if (
        rep_min is not None and rep_max is not None
        and equip != "band" and entry["weight_kg"] is not None and entry["reps"] is not None
    ):
        progressed_weight, progressed_reps = engine.double_progression(
            entry["weight_kg"], entry["reps"], rep_min, rep_max,
            last_session_sets, prescribed_sets=ex.get("sets", 1),
            increment=weight_increment, allow_increase=allow_increase,
        )
        if (progressed_weight, progressed_reps) != (entry["weight_kg"], entry["reps"]):
            entry["weight_kg"] = progressed_weight
            entry["reps"] = progressed_reps
            entry["source"] = "double_progression"
            # The date is recorded on THIS branch too. Double progression only
            # fires BECAUSE there is a logged session behind it -- every
            # prescribed set hit the top of the rep range -- so leaving
            # last_seen_date None made actual_caption fall through to its
            # "No prior record" wording on the one branch where the history is
            # most load-bearing, and it is the branch that raises the weight.
            entry["last_seen_date"] = (last_performance or {}).get("session_date")
            return entry

    if last_performance:
        entry["source"] = "last_time"
        entry["last_seen_date"] = last_performance.get("session_date")
        if entry["reps"] is not None and last_performance.get("reps") is not None:
            entry["reps"] = last_performance["reps"]
        if equip == "band" and last_performance.get("band_tier"):
            entry["band_tier"] = last_performance["band_tier"]
        elif equip != "band" and last_performance.get("weight_kg") is not None:
            entry["weight_kg"] = last_performance["weight_kg"]

    if equip == "band" and entry["band_tier"]:
        entry["band_tier"] = engine.suggested_band_tier(
            entry["band_tier"], streak_label, allow_increase=allow_increase,
        )
    elif equip != "band" and entry["weight_kg"] is not None:
        entry["weight_kg"] = engine.suggested_weight_kg(
            entry["weight_kg"], streak_label, increment=weight_increment,
            allow_increase=(allow_increase and entry["weight_kg"] > 0),
        )
    return entry


# ─────────────────────────────────────────────────────────────────────────────
#  LOAD RESOLUTION — progression PROPOSES, autoregulation CLAMPS
#
#  The bug this section exists to make structurally impossible (observed
#  2026-08-06): the session header read "Reduced load today — don't push to
#  failure" while every prescribed number went UP. Lat Pulldown moved 45kg x 10
#  -> 47.5kg x 11 on a day the engine had flagged as reduced.
#
#  It was not a display bug. The header and the numbers were computed from two
#  DIFFERENT signals that read different inputs and are free to disagree:
#
#    header  <- engine.traffic_light (HRV/RHR/sleep/temperature vs baselines)
#                 -> volume_recommendation -> signal_color
#    numbers <- engine.readiness_training_modifier (the compute_readiness
#                 composite) -> volume_factor (reps, holds, durations)
#                            -> streak_label   (weight, band tier)
#
#  The directive reached the prescription through exactly ONE wire --
#  `allow_increase=(signal_color != "red")` -- and "yellow"/"orange", the two
#  colours that RENDER the reduced-load banner, are not "red". So on precisely
#  the day the header said hold back, the upward nudge was allowed. Reps never
#  consulted the directive at all.
#
#  The fix is an ORDER, not a patch:
#
#    1. load_policy()  decides ONCE whether today is a reduced-load day, and
#       owns the banner text. There is no second flag anywhere -- the string
#       the athlete reads and the clamp applied to the numbers come out of the
#       same object, so they cannot describe different days.
#    2. Progression proposes freely (seed_actual_entry, unchanged).
#    3. clamp_to_ceiling() applies the policy AFTER, and can only move a
#       number DOWN. There is no code path by which autoregulation raises one.
#    4. assert_within_ceiling() re-checks the invariant on the FINAL numbers
#       and raises PrescriptionContradiction if it was violated. That is a hard
#       error by design: a reduced-load day that prescribes an increase is the
#       app lying to the athlete about its own safety reasoning, and silently
#       passing it is worse than crashing.
#
#  Note engine.apply_volume_recommendation already encoded the right semantics
#  ("0.75 -> reduce sets, preserve weight, hold intensity") and was called by
#  nothing but its own test. It is left alone; this is the live path.
# ─────────────────────────────────────────────────────────────────────────────

# Every signal_color that renders a hold-back banner in the training view.
# "yellow" is volume_recommendation's injury-weight branch, "orange" its
# below-baseline-biometrics branch, "red" its rest branch -- the colour names
# do not line up with the traffic light's own, which is exactly why testing
# for one of them by hand (`!= "red"`) went wrong.
REDUCED_LOAD_SIGNALS = ("red", "orange", "yellow")

_REDUCED_BANNER = (
    "Reduced load today — keep this session controlled and don't push to "
    "failure. Every weight and rep below is held at or under your last "
    "session; the app will not ask you to add load."
)
# ⚠ "No loaded exercises" WAS NOT TRUE, and this banner is the one place the
# athlete read it. A red day does two real things -- clamp_to_ceiling holds
# every weight, rep and band tier to the last completed session, and
# volume_factor is capped at 1.0 -- but it does not remove an exercise, gate
# the Start button or zero anything. The 0.0 multiplier on the engine's red
# branch is read by load_policy as a REASON (see the `reasons` list above),
# never as a factor. So the screen said "no loaded exercises" and then handed
# over the full loaded session.
#
# Athlete, 2026-08-23: soften the message, do not change the loaded work. The
# recommendation is unchanged and still leads -- what changed is that the
# second sentence now describes what actually happens below it, in the same
# shape as the other two banners.
_REST_BANNER = (
    "Rest is the better call today — mobility and walking. If you train "
    "anyway, every weight and rep below is held at your last session and "
    "nothing will ask you to add load."
)
# THE SAME CLAMP, TOLD TRUTHFULLY. Athlete, 2026-08-17: "if my strain is at 2.3
# then it shouldn't say reduced load in training, that is a contradiction."
#
# _REDUCED_BANNER is a statement about how he IS -- keep it controlled, don't
# push. On an injury-cap day that is simply false: the biometrics are green and
# the engine agrees they are. What is true is that the numbers are held at his
# last session because tissue is still healing, which is a standing constraint
# and not news about this morning.
#
# ⚠ The numbers are clamped identically either way. This changes the sentence
# and the colour, never the ceiling -- see load_policy.
_CAPPED_BANNER = (
    "Your recovery metrics are green. Volume is still held at your last "
    "session because the injury cap is active — this is the healing timeline, "
    "not today's readings. Nothing below will ask you to add load."
)


# Fallback only. engine.volume_recommendation authors the real sentence with
# the dates in it; this is what a directive that lost its action string would
# say, and it must never read as an all-clear.
_NO_READING_BANNER = (
    "No reading for today yet, so nothing below has been judged against how "
    "you are. Train to feel, and the guidance returns once a reading arrives."
)


class PrescriptionContradiction(RuntimeError):
    """The resolved prescription exceeds the previous session on a day the
    engine flagged as reduced load.

    Raised by assert_within_ceiling. This is an internal-invariant failure,
    not a user error: by the time it fires, clamp_to_ceiling should already
    have made it impossible. It exists so the contradiction can never again
    reach the screen unnoticed -- the 2026-08-06 report was a human spotting
    it by eye, which is not a control.
    """


def load_policy(directive: dict | None, readiness_modifier: dict | None) -> dict:
    """TODAY'S ONE LOAD DECISION -- the single source both the banner text and
    the numeric clamp are read from.

    Takes the two signals that were previously allowed to disagree and folds
    them into one verdict. Any of the three saying "hold back" is enough;
    they are OR-ed, never averaged, because each is a different reason to not
    add load and a good reason does not cancel a bad one.

    Returns:
        reduced        : bool -- today is a reduced-load day
        reasons        : list[str] -- every input that said so, in plain words
        volume_factor  : float -- the factor the view must ACTUALLY apply to
                          reps/holds/durations. Capped at 1.0 whenever reduced,
                          so a "+12% volume" readiness streak cannot inflate
                          reps on a day the traffic light is holding load down.
                          This is the number to use; readiness_modifier's own
                          volume_factor is the raw proposal.
        volume_note    : str -- the caption for the SESSION ADAPTED badge,
                          describing the resolved factor rather than the raw one
        banner_kind    : "error" | "warning" | "" -- how the view renders it
        banner_text    : str -- what it says, "" for no banner

    Both inputs are optional and tolerate None/missing keys: a failed engine
    lookup must degrade to "no opinion", never to a silent green light.
    """
    directive          = directive or {}
    readiness_modifier = readiness_modifier or {}

    signal    = directive.get("signal_color") or "grey"
    raw_factor = readiness_modifier.get("volume_factor")
    raw_factor = 1.0 if raw_factor is None else float(raw_factor)
    try:
        multiplier = float(directive.get("multiplier", 1.0) or 1.0)
    except (TypeError, ValueError):
        multiplier = 1.0

    reasons: list[str] = []
    if signal in REDUCED_LOAD_SIGNALS:
        label = directive.get("label") or signal.upper()
        reasons.append(f"engine directive: {label}")
    if multiplier < 1.0:
        reasons.append(f"volume multiplier {multiplier:g}")
    if raw_factor < 1.0:
        reasons.append(readiness_modifier.get("description")
                       or f"readiness volume factor {raw_factor:g}")

    reduced = bool(reasons)
    factor  = min(raw_factor, 1.0) if reduced else raw_factor

    if reduced and raw_factor > 1.0:
        # The contradiction itself, said out loud rather than resolved in
        # silence -- readiness wanted more volume, the directive said no.
        note = (f"Readiness suggested +{(raw_factor - 1) * 100:.0f}% volume; "
                f"held at 100% — {reasons[0]}")
    elif reduced:
        note = "; ".join(reasons)
    else:
        note = readiness_modifier.get("description", "") or ""

    # WHICH SENTENCE, AND WHICH COLOUR. `reduced` and the clamp below it are
    # unchanged — a capped day is still capped, whatever drove it. What the
    # driver decides is whether the athlete is told he is under-recovered,
    # because on a green-metrics injury-cap day that would be untrue.
    #
    # An unknown or missing driver falls through to the WARNING wording. That
    # is the conservative default: under-warning about fatigue is the worse
    # error, and a directive that cannot say what drove it has not earned the
    # reassurance.
    driver = directive.get("driver")
    standing_cap = driver in engine.STANDING_CAP_DRIVERS

    if signal == "red":
        kind, text = "error", _REST_BANNER
    elif reduced and standing_cap:
        kind, text = "info", _CAPPED_BANNER
    elif reduced:
        kind, text = "warning", _REDUCED_BANNER
    elif driver == engine.DRIVER_NO_DATA:
        # ⚠ NOTHING TO JUDGE IS ITSELF SOMETHING TO SAY, AND BOTH SCREENS MUST
        # SAY IT. Athlete, 2026-08-25: "when there is no data in the home page,
        # then no data is message is presented in the training page."
        #
        # Silence was the wrong shape for this. Home's card says "Awaiting
        # Data" because readiness has its own no-score render; the training
        # screen had no equivalent, so a day with nothing to judge fell through
        # to whatever the directive's action string happened to be — which on
        # a grey day is not a load statement at all, and read as normal
        # training. Two screens inferring the same absence separately is how
        # they came to disagree about it.
        #
        # ⚠ IT IS NOT A LOAD DECISION. `reduced` stays False and volume_factor
        # is untouched — this branch is only reached when nothing else had an
        # opinion, so it can never mask one. A day where readiness computed and
        # asked for less is still `warning`, because that is a reduction off
        # real data even when the traffic light has none.
        #
        # The text is the ENGINE'S OWN sentence rather than a constant authored
        # here: it names the date and the date of the most recent reading, and
        # those are the two facts that make the message actionable rather than
        # merely apologetic.
        kind = "neutral"
        text = directive.get("action") or _NO_READING_BANNER
    else:
        kind, text = "", ""

    return {
        "reduced":       reduced,
        "reasons":       reasons,
        "volume_factor": factor,
        "volume_note":   note,
        "banner_kind":   kind,
        "banner_text":   text,
        # Named so the view can colour by what is actually true, and so a test
        # can assert the fatigue wording never appears on a green day.
        "driver":        driver,
        "standing_cap":  standing_cap,
    }


def last_completed_ceiling(last_performance: dict | None,
                            last_session_sets: list[dict] | None) -> dict:
    """The most a reduced-load day is allowed to prescribe: the TOP completed
    set of the most recent logged session for this movement.

    Returns {"weight_kg": float|None, "reps": int|None, "band_tier": str|None,
    "session_date": str|None}. None on an axis means NO RECORD -- there is
    nothing to clamp against, and clamp_to_ceiling leaves that axis alone
    rather than inventing a limit.

    Reps are taken from the sets at the TOP weight, not the maximum reps
    across all sets. 45x10, 45x10, 47.5x8 yields (47.5, 8) -- repeat your top
    set -- and never (47.5, 10), a combination that was not completed. Falls
    back to the max reps overall when the top-weight sets carry no rep count
    (a hold logged as reps=1 with the work in `tut`).

    last_performance is the fallback when the full per-set array is
    unavailable; it holds the LAST set rather than the top one, which is a
    lower or equal ceiling and therefore safe in the same direction.
    """
    out = {"weight_kg": None, "reps": None, "band_tier": None,
            "session_date": None}
    sets = list(last_session_sets or [])
    if not sets and last_performance:
        sets = [{"reps": last_performance.get("reps"),
                  "weight": last_performance.get("weight_kg"),
                  "band_tier": last_performance.get("band_tier")}]
    if last_performance:
        out["session_date"] = last_performance.get("session_date")
    if not sets:
        return out

    weights = [s.get("weight") for s in sets if s.get("weight") is not None]
    if weights:
        top = max(float(w) for w in weights)
        out["weight_kg"] = top
        at_top = [s.get("reps") for s in sets
                  if s.get("weight") is not None and float(s["weight"]) >= top
                  and s.get("reps") is not None]
    else:
        at_top = []
    if not at_top:
        at_top = [s.get("reps") for s in sets if s.get("reps") is not None]
    if at_top:
        out["reps"] = int(max(at_top))

    tiers = [s.get("band_tier") for s in sets
             if s.get("band_tier") in engine.BAND_TIERS]
    if tiers:
        out["band_tier"] = max(tiers, key=engine.BAND_TIERS.index)
    return out


def clamp_to_ceiling(entry: dict, ceiling: dict) -> dict:
    """Apply the ceiling to a proposed entry. DOWNWARD ONLY -- this function
    has no branch that raises a number, which is the property that makes the
    header/numbers contradiction structurally impossible rather than merely
    fixed.

    Returns a copy. Records what it moved in entry["clamped"], a dict of
    axis -> {"from": proposed, "to": final}, empty when nothing was held. That
    dict is what the per-exercise caption is rendered from, so the athlete is
    told the number was held rather than left to wonder why it did not move.
    """
    out = dict(entry)
    moved: dict[str, dict] = {}

    cw = ceiling.get("weight_kg")
    if cw is not None and out.get("weight_kg") is not None and out["weight_kg"] > cw:
        moved["weight_kg"] = {"from": out["weight_kg"], "to": round(float(cw), 2)}
        out["weight_kg"] = round(float(cw), 2)

    cr = ceiling.get("reps")
    if cr is not None and out.get("reps") is not None and out["reps"] > cr:
        moved["reps"] = {"from": out["reps"], "to": int(cr)}
        out["reps"] = int(cr)

    ct = ceiling.get("band_tier")
    if (ct in engine.BAND_TIERS and out.get("band_tier") in engine.BAND_TIERS
            and engine.BAND_TIERS.index(out["band_tier"]) > engine.BAND_TIERS.index(ct)):
        moved["band_tier"] = {"from": out["band_tier"], "to": ct}
        out["band_tier"] = ct

    out["clamped"] = moved
    return out


def assert_within_ceiling(entry: dict, ceiling: dict, policy: dict,
                           exercise_name: str = "") -> None:
    """Hard invariant on the FINAL resolved prescription. No-op unless
    policy["reduced"].

    On a reduced-load day the resolved weight must be <= the last completed
    working weight and the resolved reps <= the last completed reps. Raises
    PrescriptionContradiction naming the exercise and both numbers if not.

    Deliberately re-derived from the final entry rather than trusting
    clamp_to_ceiling's own output: an assertion that reads the value the
    clamp just wrote would pass by construction and check nothing.
    """
    if not policy.get("reduced"):
        return
    name = exercise_name or "this exercise"
    cw, cr = ceiling.get("weight_kg"), ceiling.get("reps")
    w, r   = entry.get("weight_kg"), entry.get("reps")
    if cw is not None and w is not None and w > cw:
        raise PrescriptionContradiction(
            f"{name}: reduced-load day prescribes {w} kg, above the last "
            f"completed working weight of {cw} kg ({'; '.join(policy.get('reasons') or [])})"
        )
    if cr is not None and r is not None and r > cr:
        raise PrescriptionContradiction(
            f"{name}: reduced-load day prescribes {r} reps, above the last "
            f"completed {cr} reps ({'; '.join(policy.get('reasons') or [])})"
        )
    ct, t = ceiling.get("band_tier"), entry.get("band_tier")
    if (ct in engine.BAND_TIERS and t in engine.BAND_TIERS
            and engine.BAND_TIERS.index(t) > engine.BAND_TIERS.index(ct)):
        raise PrescriptionContradiction(
            f"{name}: reduced-load day prescribes the {t} band, above the last "
            f"completed {ct} band ({'; '.join(policy.get('reasons') or [])})"
        )


def resolve_prescription(
    ex: dict,
    last_performance: dict | None,
    streak_label: str,
    policy: dict,
    weight_increment: float = 2.5,
    last_session_sets: list[dict] | None = None,
) -> dict:
    """THE single ordered resolution. Every prescribed number the live training
    screen shows comes out of here, and the banner above them comes out of the
    same `policy` argument.

    Order, and the order is the whole point:
      1. seed_actual_entry proposes -- double progression, then last
         performance, then the readiness nudge. It is handed
         allow_increase=True so progression is free to want more; suppressing
         it here would put autoregulation BEFORE progression and reintroduce
         the two-signals-two-answers shape this replaced.
      2. clamp_to_ceiling holds it to the last completed session, but only on
         a reduced-load day, and only downward.
      3. assert_within_ceiling verifies the result.

    On a reduced-load day with NO logged history the ceiling is empty and
    nothing is clamped -- but the view has already capped policy["volume_factor"]
    at 1.0 before building `ex`, so the plan's authored reps are what gets
    proposed, not an inflated version of them.
    """
    proposed = seed_actual_entry(
        ex, last_performance, streak_label,
        allow_increase=True,
        weight_increment=weight_increment,
        last_session_sets=last_session_sets,
    )
    ceiling = last_completed_ceiling(last_performance, last_session_sets)
    final = clamp_to_ceiling(proposed, ceiling) if policy.get("reduced") else dict(proposed)
    final.setdefault("clamped", {})
    assert_within_ceiling(final, ceiling, policy, ex.get("name", ""))
    return final


def displayed_prescription(ex: dict, actual: dict | None) -> dict:
    """`ex` overlaid with the live resolved entry, for every place the screen
    PRINTS the prescription rather than steps it.

    The training screen shows a rep target in three places: the exercise
    header's prescription_label, the "Perform N reps" instruction, and the
    +/- stepper. Only the stepper read the resolved entry -- the other two
    printed ex["reps"], which is the plan value after the readiness volume
    modifier and nothing else. On 2026-08-06 that is what put "11" on screen
    while the stepper underneath it said 10.

    Returns ex unchanged when there is no resolved entry to overlay (an
    unloaded exercise has no stepper, so the plan value IS the prescription).
    """
    if not actual:
        return ex
    out = dict(ex)
    # "reps" only. hold_reps' reps_in_set is deliberately NOT overlaid: it is
    # driven by the live per-rep hold-timer counter, and seed_actual_entry
    # leaves entry["reps"] None for that type precisely so the two can never
    # disagree. Overlaying it here would reintroduce that from the other end.
    if out.get("type") == "reps" and actual.get("reps") is not None:
        out["reps"] = actual["reps"]
    if actual.get("weight_kg") is not None:
        out["weight_kg"] = actual["weight_kg"]
    if actual.get("band_tier"):
        out["band_tier"] = actual["band_tier"]
    return out


def actual_caption(entry: dict) -> str:
    """Where today's numbers CAME FROM, and whether they were held down. Pure,
    so it's unit-testable without Streamlit.

    IT PRINTS NO NUMBERS, DELIBERATELY. It used to render entry["reps"] and
    entry["weight_kg"] under a "Last time:" label -- but by the time an entry
    reaches here those fields have been through seed_actual_entry's readiness
    nudge and clamp_to_ceiling, so the line reported TODAY'S PROPOSAL as last
    session's reading. A real +2.5 kg step displayed as "Last time: 25.0 kg"
    beside a prescribed 25.0 kg, i.e. as no change at all -- destroying exactly
    the comparison the caption existed to support. The previous session's real
    numbers come from previous_performance()/previous_caption(), which read the
    log and nothing else, and the difference between the two is
    prescription_delta().
    """
    held = entry.get("clamped") or {}
    source = entry.get("source")
    date_part = f" ({entry['last_seen_date']})" if entry.get("last_seen_date") else ""
    if source == "double_progression":
        base = ("Double progression — every prescribed set hit the top of the "
                f"rep range last session{date_part}.")
    elif source == "last_time":
        base = f"Starting from your last logged session{date_part}."
    else:
        base = "No prior record — using plan default."
    return f"{base} {_held_caption(held)}" if held else base


# ─── The previous session, shown beside today's prescription ─────────────

#: Rendered when a movement has no logged history at all. The athlete's rule:
#: an absent previous session is said in WORDS -- never 0, never "-" in a
#: numeric slot, never an interpolated value, each of which reads as a genuine
#: reading of zero rather than as the absence of one.
PREVIOUS_NONE_TEXT = "No previous data"

#: Rendered when there IS a previous session and today's prescription matches it
#: on every axis. A blank would read as "not computed"; this reads as "no
#: change", which is the fact.
DELTA_NONE_TEXT = "—"


def previous_performance(last_performance: dict | None,
                          last_session_sets: list[dict] | None) -> dict:
    """The previous session's ACTUAL COMPLETED WORK, raw.

    Nothing in here has been through seed_actual_entry, the readiness nudge or
    clamp_to_ceiling. That is the whole point: this is the number the athlete
    checks the engine's proposal against, so it must be a reading of the log
    and not a second view of the proposal.

    Returns
      have          False when the movement has never been logged. The caller
                    renders PREVIOUS_NONE_TEXT and no delta.
      session_date  the date the work was done, or None.
      sets          the full per-set array, normalised onto this module's own
                    field names ("weight" -> "weight_kg"). EMPTY when only the
                    single-reading fallback was available.
      top           last_completed_ceiling's top working set -- top weight, and
                    the reps actually completed AT that weight. This is what
                    the delta is measured against, and it is already the
                    quantity a reduced-load day is clamped to, so the number
                    shown and the number enforced are one number.
      per_set       True when `sets` is populated, i.e. when a per-set line can
                    be rendered rather than the top set alone.

    WARM-UP SETS ARE NOT FILTERED, matching Repository.get_last_session_all_sets'
    own decision and for its reason: a ramp is authored as its OWN exercise
    beside the lift it prepares, so a movement's sets are all ramp or none, and
    filtering would blank a ramp exercise's own history -- the one place its
    stepper needs a previous reading.
    """
    top = last_completed_ceiling(last_performance, last_session_sets)
    sets = [
        {
            "reps":      s.get("reps"),
            "weight_kg": s.get("weight"),
            "band_tier": s.get("band_tier"),
            "tut":       s.get("tut"),
            "is_warmup": bool(s.get("is_warmup")),
        }
        for s in (last_session_sets or [])
    ]
    top_only = {k: top.get(k) for k in ("weight_kg", "reps", "band_tier")}
    have = bool(sets) or any(v is not None for v in top_only.values())
    return {
        "have":         have,
        "session_date": top.get("session_date"),
        "sets":         sets,
        "top":          top_only,
        "per_set":      bool(sets),
    }


def _previous_set_token(s: dict) -> str:
    """One completed set as "45kg × 10" / "Blue × 12" / "20kg × 45s" / "45s" /
    "10 reps". A load carries the rep count for it; a bare rep count spells the
    word out, so a lone integer is never left to be read as a weight."""
    reps   = s.get("reps")
    weight = s.get("weight_kg")
    tier   = s.get("band_tier")
    tut    = s.get("tut")
    load = tier or (f"{float(weight):g}kg" if weight else None)
    # A hold is logged as reps=1 with the work in `tut` (see make_sets_data), so
    # printing its rep count would render a 45-second plank as "1".
    if tut and (reps is None or int(reps) <= 1):
        work, bare = f"{float(tut):g}s", f"{float(tut):g}s"
    elif reps is not None:
        work, bare = f"{int(reps)}", f"{int(reps)} reps"
    else:
        return load or ""
    return f"{load} × {work}" if load else bare


def previous_caption(previous: dict | None) -> str:
    """previous_performance()'s output as one line. Per set when the per-set
    array exists, the top working set otherwise, PREVIOUS_NONE_TEXT when there
    is no history."""
    if not previous or not previous.get("have"):
        return PREVIOUS_NONE_TEXT
    date_part = f" ({previous['session_date']})" if previous.get("session_date") else ""
    tokens = [t for t in (_previous_set_token(s) for s in previous.get("sets") or []) if t]
    if tokens:
        return f"Last: {', '.join(tokens)}{date_part}"
    token = _previous_set_token(previous.get("top") or {})
    return f"Last: {token}{date_part}" if token else PREVIOUS_NONE_TEXT


def prescription_delta(entry: dict | None, previous: dict | None) -> str:
    """Today's RESOLVED prescription minus the previous session's top working
    set, stated explicitly: "+2.5kg", "+1 rep", "+2.5kg, -1 rep",
    "Green → Blue band", or DELTA_NONE_TEXT when nothing moved.

    `entry` is the live stepper entry, so the delta tracks the athlete's own
    taps as well as the engine's proposal -- the number on screen is always the
    difference between what is about to be performed and what was performed.

    Empty string when there is no history: the caller has already said
    PREVIOUS_NONE_TEXT, and "+25kg against nothing" is exactly the interpolated
    value that must never be rendered.
    """
    if not previous or not previous.get("have"):
        return ""
    top   = previous.get("top") or {}
    entry = entry or {}
    parts: list[str] = []

    pw, cw = top.get("weight_kg"), entry.get("weight_kg")
    if pw is not None and cw is not None:
        d = round(float(cw) - float(pw), 2)
        if d:
            parts.append(f"{d:+g}kg")

    pr, cr = top.get("reps"), entry.get("reps")
    if pr is not None and cr is not None:
        d = int(cr) - int(pr)
        if d:
            parts.append(f"{d:+d} rep" + ("" if abs(d) == 1 else "s"))

    pt, ct = top.get("band_tier"), entry.get("band_tier")
    if pt and ct and pt != ct:
        parts.append(f"{pt} → {ct} band")

    return ", ".join(parts) if parts else DELTA_NONE_TEXT


def delta_direction(entry: dict | None, previous: dict | None) -> str:
    """"up" | "down" | "mixed" | "same" | "" -- FOR COLOURING ONLY. The text
    prescription_delta() returns is the statement; this only decides whether it
    is drawn as a step up, a step down or neither, and "" means there is nothing
    to draw."""
    if not previous or not previous.get("have"):
        return ""
    top   = previous.get("top") or {}
    entry = entry or {}
    signs: list[int] = []

    pw, cw = top.get("weight_kg"), entry.get("weight_kg")
    if pw is not None and cw is not None and float(cw) != float(pw):
        signs.append(1 if float(cw) > float(pw) else -1)

    pr, cr = top.get("reps"), entry.get("reps")
    if pr is not None and cr is not None and int(cr) != int(pr):
        signs.append(1 if int(cr) > int(pr) else -1)

    pt, ct = top.get("band_tier"), entry.get("band_tier")
    if pt in engine.BAND_TIERS and ct in engine.BAND_TIERS and pt != ct:
        signs.append(1 if engine.BAND_TIERS.index(ct) > engine.BAND_TIERS.index(pt) else -1)

    if not signs:
        return "same"
    if all(s > 0 for s in signs):
        return "up"
    if all(s < 0 for s in signs):
        return "down"
    return "mixed"


def _held_caption(held: dict) -> str:
    """Renders clamp_to_ceiling's ledger into the caption. The athlete is told
    the number was held DOWN and by how much -- a prescription that silently
    fails to move looks identical to one the app forgot to progress."""
    bits = []
    if "weight_kg" in held:
        bits.append(f"{held['weight_kg']['from']:g} → {held['weight_kg']['to']:g} kg")
    if "reps" in held:
        bits.append(f"{held['reps']['from']} → {held['reps']['to']} reps")
    if "band_tier" in held:
        bits.append(f"{held['band_tier']['from']} → {held['band_tier']['to']} band")
    return f"· Held down ({', '.join(bits)}) — reduced-load day." if bits else ""


def exercise_duration_seconds(ex: dict) -> int:
    """Estimated active time for a single exercise — sets x hold/rep time +
    rest between sets. Same per-type formulas as estimate_duration's inner
    loop, but scoped to one exercise (no session-level base/transition
    buffer), for labeling one exercise in a day's review rather than sizing
    the whole session."""
    t, sets, rest = ex["type"], ex.get("sets", 1), ex.get("rest_seconds", 60)
    if t == "duration":    return (ex.get("duration_minutes") or 0) * 60
    if t == "hold":        return sets * (ex.get("hold_seconds") or 0) + (sets - 1) * rest
    if t == "hold_reps":   return sets * (ex.get("hold_seconds") or 0) * (ex.get("reps_in_set") or 1) + (sets - 1) * rest
    if t == "reps":        return sets * 20 + (sets - 1) * rest
    return 0


def exercise_seconds_from_sets(sets: list[dict]) -> int:
    """Reconstructs one exercise's total logged/active seconds from its
    persisted Sets JSON (make_sets_data's own per-row shape, already
    json.loads'd by the caller) -- the read-time analog of
    exercise_duration_seconds above, which computes the equivalent
    planning-time estimate from a plan dict instead of logged rows.
    Produces identical output to exercise_duration_seconds(ex) whenever
    `sets` is exactly make_sets_data(ex)'s own output for that ex -- this
    identity is what lets content-aware Strain/ACWR weighting
    (services.content_weighting) be computed from live logged data rather
    than a static per-session-type lookup.

    Per-row active time:
      velocity == "isometric"  (hold / hold_reps) -> tut * reps
        hold_reps' tut is the PER-REP hold duration (make_sets_data does
        NOT multiply it by reps_in_set) while its "reps" field IS
        reps_in_set -- so this multiplication is required to recover the
        true total. hold-type rows always have reps == 1, so the same
        formula is a safe no-op there.
      velocity == "continuous" (duration) -> tut
        (single row; reps is always 1 for this type)
      anything else (velocity == "controlled", reps-type) -> 20
        flat per-set estimate -- reps-type rows never record a real
        duration (tut is always 0), matching exercise_duration_seconds'
        own `sets * 20` term exactly.

    Rest: summed across every row except the last (mirrors
    exercise_duration_seconds' `(sets - 1) * rest`). This is the PRESCRIBED
    `rest`, deliberately, even on rows that now also carry a measured
    `rest_taken_seconds` — see REST_TAKEN_FEEDS_DURATION for why switching it
    mid-series would move Strain and ACWR on the field's existence rather than
    on training. Warm-up rows ARE counted here: a ramp set takes real time and
    the session really was that long. Excluding them belongs to tonnage and to
    1RM estimation, which are claims about work and about strength."""
    if not sets:
        return 0
    active = 0
    for row in sets:
        velocity = row.get("velocity")
        if velocity == "isometric":
            active += (row.get("tut") or 0) * (row.get("reps") or 1)
        elif velocity == "continuous":
            active += row.get("tut") or 0
        else:
            active += 20
    rest = sum((row.get("rest") or 0) for row in sets[:-1])
    return active + rest


# ── SESSION TIME MODEL, RE-BASED ON MEASUREMENT (2026-09-11) ─────────────────
#
# The old estimate charged 30 s per exercise change and read no laterality.
# Measured from the per-set timestamps of every logged session that carries
# them (13 sessions, 109 exercise changes, 2026-07-31 -> 2026-09-10): the time
# from the last set of one exercise to the START of the first set of the next,
# with that set's own work subtracted, was
#
#     next station is a mat or floor item          median  74 s  (p25 52,  p75 114)
#     next station is a rack, plates or a cable    median 117 s  (p25 60,  p75 161)
#     next station is a band set-up                median 158 s  (p25 96,  p75 212)
#
# So a 20-entry session carried 20-30 minutes of changeover the estimate never
# saw. Stage 2B day 22 (2026-09-10) was estimated at 54 min and took 81; costed
# from its timestamps the three main lifts took 28 min, the five add-on
# exercises 33, and preparation 19. The athlete's own description of the same
# session: "nearly 40 mins in when I finished just the first two real training
# exercises" — which the timestamps put at 39.
#
# Consecutive entries of the SAME LIFT — a ramp set, a heavy top set and the
# working sets of one exercise — share a station and cost one weight change,
# not a changeover. That is also why a ramp belongs immediately before the lift
# it prepares and nowhere else: the 2026-09-10 session ran squat ramp, RDL
# ramp, squat top, RDL top, squat, RDL, i.e. six weight changes across two
# stations, and the athlete logged all four singles in an eleven-second burst
# because he had not followed that order anyway. See session_shape_violations.
#
# These are MEDIANS of his own changeovers. They will drift as the sessions
# get shorter (fewer stations, less walking) — re-measure them from the
# timestamps rather than tuning them by hand: scripts/measure_changeovers.py
# is the measurement and prints these three numbers.
CHANGEOVER_SECONDS: dict[str, int] = {"floor": 74, "gym": 117, "band": 158}
#: One weight change at a station the previous entry already occupied.
CHANGEOVER_SAME_STATION_SECONDS = 20
#: Getting to the first item — the old estimate's 120 s, kept.
SESSION_SETUP_SECONDS = 120
#: Per rep when an exercise carries no tempo. Measured 2026-09-10: Hip Thrust
#: ten reps in ~46 s, Pallof Press ten reps in ~26 s a side, RDL ten at 3-1-1
#: in ~44 s. The old formula charged a flat 20 s per SET regardless of reps.
REPS_SECONDS_DEFAULT = 4
#: Seconds between the reps of a hold_reps set — reset, breathe, go again.
HOLD_REPS_GAP_SECONDS = 2
#: Coded laterality="unilateral" but having only ONE side. Counting them twice
#: is what inflated an earlier estimate of the right/left split's cost.
SINGLE_SIDED_NAMES = frozenset({
    "Right Posterior Hip Capsule Stretch (Revised Cue)",
    "Right Posterior Hip Capsule Stretch (Quadruped)",
    "Right Hip Tendon Path Drill (Coxa Saltans)",
})
_GYM_EQUIPMENT = frozenset({"dumbbell", "plate", "cable", "barbell", "machine"})
#: No equipment_type, but a station you walk to and set up all the same.
_GYM_STATION_NAMES = frozenset({"Walking Raise (Incline)"})


def base_name(name: str) -> str:
    """'Goblet Squat (Ramp Set)' -> 'Goblet Squat'. The bracketed suffix names
    a set's ROLE (ramp, top set, test); the base names the lift, which is the
    station the athlete is standing at."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", name or "").strip()


def station_kind(ex: dict) -> str:
    """'gym' for a rack, plates, a cable or a treadmill; 'band' for a band
    set-up; 'floor' for a mat item. Keys CHANGEOVER_SECONDS."""
    eq = ex.get("equipment_type")
    if eq == "band":
        return "band"
    if eq in _GYM_EQUIPMENT or ex.get("name") in _GYM_STATION_NAMES:
        return "gym"
    return "floor"


def sides(ex: dict) -> int:
    """2 for a two-sided unilateral item, otherwise 1. 'alternating' is 1:
    its reps already alternate inside the set."""
    if ex.get("laterality") == "unilateral" and ex.get("name") not in SINGLE_SIDED_NAMES:
        return 2
    return 1


def tempo_seconds(tempo: str | None) -> int:
    """'3-1-1' -> 5 seconds per rep. No tempo -> REPS_SECONDS_DEFAULT."""
    if not tempo:
        return REPS_SECONDS_DEFAULT
    try:
        return max(1, sum(int(part) for part in str(tempo).split("-")))
    except ValueError:
        return REPS_SECONDS_DEFAULT


def set_work_seconds(ex: dict) -> int:
    """Working time of ONE set on ONE side."""
    t = ex.get("type")
    if t == "duration":
        return (ex.get("duration_minutes") or 0) * 60
    if t == "hold":
        return ex.get("hold_seconds") or 0
    if t == "hold_reps":
        return (ex.get("reps_in_set") or 1) * ((ex.get("hold_seconds") or 0) + HOLD_REPS_GAP_SECONDS)
    if t == "reps":
        return (ex.get("reps") or 0) * tempo_seconds(ex.get("tempo"))
    return 0


def exercise_work_seconds(ex: dict) -> int:
    """Work plus the rest BETWEEN its sets, both sides counted. The rest is
    not doubled: the guided flow runs no timer on the right-to-left switch,
    so the other side's working time is the first side's rest."""
    n = ex.get("sets", 1) or 1
    rest = ex.get("rest_seconds", 60) or 0
    if ex.get("type") == "duration":
        return set_work_seconds(ex)
    return n * set_work_seconds(ex) * sides(ex) + (n - 1) * rest


def changeover_seconds(prev: dict | None, cur: dict) -> int:
    """Getting from the last set of `prev` to the first set of `cur`."""
    if prev is None:
        return 0
    if base_name(prev.get("name", "")) == base_name(cur.get("name", "")):
        return CHANGEOVER_SAME_STATION_SECONDS
    return CHANGEOVER_SECONDS[station_kind(cur)]


def gap_seconds(prev: dict | None, cur: dict) -> int:
    """From the last set of `prev` to the first set of `cur`: the LONGER of
    prev's prescribed rest and the changeover. After a heavy top set the
    athlete rests 150 s whether the next entry is the same lift or a walk to
    another station — the walk happens inside the rest, it does not add to
    it. A release item with 15 s of rest is bounded by the 74 s it takes to
    get onto the next mat; a ramp with 60 s of rest at the same rack is
    bounded by the rest."""
    if prev is None:
        return 0
    return max(prev.get("rest_seconds", 0) or 0, changeover_seconds(prev, cur))


def session_seconds(exercises: list[dict]) -> int:
    """The whole session: set-up, every entry's work and between-set rest,
    and the gap between every consecutive pair."""
    total, prev = SESSION_SETUP_SECONDS, None
    for ex in exercises:
        total += gap_seconds(prev, ex) + exercise_work_seconds(ex)
        prev = ex
    return total


def estimate_duration(exercises: list[dict]) -> int:
    """Minutes, floored at 10. Built on session_seconds — the measured model
    above — since 2026-09-11; before that it was exercise_duration_seconds
    plus 30 s per entry, which read Stage 2B day 22 as 54 min against a
    measured 81."""
    return max(10, round(session_seconds(exercises) / 60))


# ── SESSION SHAPE — what a gym session is authored to (CLAUDE.md Key Rule 21)
#
# Athlete, 2026-09-11, after the 81-minute session: "Limit the number of
# exercises — it seems to be just increasing and increasing"; "limit the number
# of 1 set exercises"; "ramp sets must only arrive before the real exercises";
# "84 is too long for what feels like three main exercises". Each addition to
# Stage 2B had been individually justified and nobody was counting the total:
# Stage 2A gym days ran 10 exercises and 58-67 min, Stage 2B week 1 ran 14
# entries at 75-77 min, and by week 4 two appended isometrics took it to 20
# entries and 81 min.
#
# Published anchors for an hour: ACSM's whole-body prescription is 8-10
# exercises at 2-4 sets, with one set of it taking ~20 min and three ~50, and
# dropout rising once sessions pass 60 min; NSCA's program design puts the
# core lifts first with 2-3 min rest and assistance after, which fits 4-6
# exercises and 15-22 working sets in an hour. Day 22 had 8 exercises at three
# sets, 24 working sets, before four singles and eight preparation items.
#
# These rules apply to every plan registered from SESSION_SHAPE_RULES_FROM_PHASE
# on. Stage 2B (phase 3) is the block that produced them and is exempt because
# it ends 2026-09-13 and its content is history. session_shape_violations is
# the check; tests/test_session_shape_rules.py runs it over every registered
# block, so a future block cannot be authored past these numbers without
# either fixing the block or changing this constant deliberately.
SESSION_SHAPE_RULES_FROM_PHASE = 4
SESSION_SHAPE: dict[str, int] = {
    # Distinct lifts outside preparation. 3 main + core + hip work; 6 leaves
    # room for the press day's clinical face-pull pairing.
    "max_working_families": 6,
    # A one-set exercise outside the release block, a ramp/top set of a lift
    # that follows, or a measurement, trains nothing and costs a changeover.
    "max_single_set_training_entries": 0,
    # session_seconds / 60, with the measured changeovers. The athlete's line:
    # over 60 is fine, 84 is not. Block B's squat day — three heavy lifts with
    # a ramp and a top set nested under two of them — models at 68 with every
    # prescribed rest taken in full (150 s after a top set, 120 s between
    # working sets), which he cut short on 2026-09-10; the press day at 56.
    "max_gym_minutes": 70,
    # Release items, the raise and ONE activation item.
    "max_preparation_entries": 7,
    # A flexibility day (session_kind == "flexibility"): the release block,
    # the prescribed stack (cluster_a_prescription.LENGTH caps it at five)
    # and at most one appended item. Block B's cluster day was found at 13
    # entries / 61 modelled minutes on 2026-09-11 — a raise the phase-2 lock
    # does not ask of a stretching session, plus two isometrics appended for
    # frequency — and the athlete's answer was "fix that as well".
    "max_flexibility_entries": 10,
    "max_flexibility_minutes": 50,
}
RAMP_SUFFIX = "(Ramp Set)"
TOP_SET_SUFFIX = "(Heavy Top Set)"
#: The preparation vocabulary: the release block, the raise and the activation
#: items. Everything after the last of these in a session is load.
PREPARATION_NAMES = RELEASE_EXERCISE_NAMES | frozenset({
    "Walking Raise (Incline)", "Single-Leg Glute Bridge", "Dead Bug",
    "Scapular Wall Slide", "Prone Y-Raise (Scapular)",
})


def is_measurement(name: str) -> bool:
    """Finding tests and trials carry a suffix and may lead a session."""
    return any(tag in (name or "") for tag in ("(Test)", "(Timed Test)", "(Trial)"))


def is_ramp_or_top(name: str) -> bool:
    return (name or "").endswith(RAMP_SUFFIX) or (name or "").endswith(TOP_SET_SUFFIX)


def preparation_entries(exercises: list[dict]) -> list[dict]:
    """The leading run of measurement and preparation items."""
    out = []
    for ex in exercises:
        if is_measurement(ex.get("name", "")) or ex.get("name") in PREPARATION_NAMES:
            out.append(ex)
        else:
            break
    return out


def working_families(exercises: list[dict]) -> list[str]:
    """Distinct base names of everything that is not preparation or a
    measurement, in first-seen order. A ramp, its top set and the working
    sets of one lift are one family."""
    seen: list[str] = []
    for ex in exercises:
        name = ex.get("name", "")
        if is_measurement(name) or name in PREPARATION_NAMES:
            continue
        b = base_name(name)
        if b not in seen:
            seen.append(b)
    return seen


def session_shape_violations(day: dict, rules: dict[str, int] | None = None) -> list[str]:
    """Every way a plan day breaks the session-shape rules, as readable
    reasons. Empty for a day that fits. Only `day_type == "main"` (a gym
    session) is held to the counts and the clock; every day is held to the
    ramp-nesting rule, because a ramp anywhere else is a changeover for
    nothing."""
    rules = dict(SESSION_SHAPE, **(rules or {}))
    exercises = day.get("exercises") or []
    names = [ex.get("name", "") for ex in exercises]
    out: list[str] = []

    for i, name in enumerate(names):
        if not is_ramp_or_top(name):
            continue
        lift = base_name(name)
        nxt = names[i + 1] if i + 1 < len(names) else None
        if nxt is None or base_name(nxt) != lift:
            out.append(f"{name!r} is not immediately followed by its own lift "
                       f"({lift!r}); ramp and top sets sit right before the lift they prepare")
        if name.endswith(RAMP_SUFFIX) and not exercises[i].get("warmup"):
            out.append(f"{name!r} is a ramp set but is not flagged warmup=True, so its "
                       f"reps and weight would count as work")

    if day.get("session_kind") == "flexibility":
        if len(exercises) > rules["max_flexibility_entries"]:
            out.append(f"{len(exercises)} entries on a flexibility day; the ceiling is "
                       f"{rules['max_flexibility_entries']}")
        minutes = session_seconds(exercises) / 60
        if minutes > rules["max_flexibility_minutes"]:
            out.append(f"{minutes:.0f} min on a flexibility day with measured changeovers; "
                       f"the ceiling is {rules['max_flexibility_minutes']}")
        return out
    if day.get("day_type") != "main":
        return out

    fams = working_families(exercises)
    if len(fams) > rules["max_working_families"]:
        out.append(f"{len(fams)} working exercises ({', '.join(fams)}); the ceiling is "
                   f"{rules['max_working_families']}")

    singles = [n for ex, n in zip(exercises, names)
               if (ex.get("sets", 1) or 1) == 1
               and not is_measurement(n) and n not in PREPARATION_NAMES
               and not is_ramp_or_top(n)]
    if len(singles) > rules["max_single_set_training_entries"]:
        out.append(f"one-set training entries {singles}; the ceiling is "
                   f"{rules['max_single_set_training_entries']}")

    prep = preparation_entries(exercises)
    if len(prep) > rules["max_preparation_entries"]:
        out.append(f"{len(prep)} preparation entries; the ceiling is "
                   f"{rules['max_preparation_entries']}")

    minutes = session_seconds(exercises) / 60
    if minutes > rules["max_gym_minutes"]:
        out.append(f"{minutes:.0f} min with measured changeovers; the ceiling is "
                   f"{rules['max_gym_minutes']}")
    return out


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


_PLAN_BY_PHASE_NUMBER: dict[int, dict[int, dict]] = {
    1: tp.PLAN, 2: tp.PLAN_STAGE2, 3: tp.PLAN_STAGE2B, 4: tp.PLAN_BLOCK_B,
}

#: Everything needed to CREATE a phase, per phase number. Only consulted when a
#: new block is being started, so it never renames a phase already stored.
#:
#: `stage` is the CLINICAL stage (services/rules.py's ceilings), and it is a
#: separate number from the phase on purpose. Phase 3 is Stage 2B — a different
#: block at the SAME clinical stage 2, because the content changes while the
#: ACWR ceiling, the RPE cap and the volume cap do not. Reading "2B" as "stage
#: 3" would hand the athlete Performance-and-Growth ceilings (ACWR 1.5, RPE 10)
#: on the strength of a block name.
PHASE_META: dict[int, dict] = {
    1: {"name": "Stage 1 Rehab", "stage": 1,
        "button": "Begin Stage 1 — Rehab Block"},
    2: {"name": "Stage 2 — Transition (Work Capacity)", "stage": 2,
        "button": "Begin Stage 2 — 4-Week Transition Block"},
    3: {"name": "Stage 2B — Strength + Running Build", "stage": 2,
        "button": "Begin Stage 2B — 4-Week Block"},
    # Block B is a new BLOCK at the same clinical stage, for the same reason
    # 2B was: the content changes (race build, the session shape of Key Rule
    # 21), the ceilings do not. Block A's exit criteria gate a STAGE change
    # and are mostly untested (docs/hypothesis.md, 2026-09-11); no criterion
    # is needed to start the next block of the same stage.
    4: {"name": "Block B — Race Build", "stage": 2,
        "button": "Begin Block B — 4-Week Race Build"},
}


def plan_dict_for_phase(phase_number: int) -> dict[int, dict] | None:
    """The day-number-keyed PLAN dict authored for this phase, or None if
    nothing's been authored for it yet (legitimate — not every phase has
    content written)."""
    return _PLAN_BY_PHASE_NUMBER.get(phase_number)


def next_phase_offer(phases: list[Phase]) -> int | None:
    """The phase number the athlete can start next, or None if there isn't one.

    Generalises what used to be a hard-wired Stage-1-to-2 check. That check read
    `1 in existing and 2 not in existing`, which meant that on the day Stage 2A
    lapsed there was NO route to a Phase 3 at all: the app simply had no active
    phase, rendered every day as rest, and quietly dropped the ACWR chronic
    window back to a flat calendar window.

    Three conditions, all of which have to hold:
      - the phase does not already exist (never re-offer a block)
      - its PREDECESSOR does exist (blocks are not skippable — a Phase 4 with no
        Phase 3 would leave the day numbering and the stage history with a hole)
      - its content is authored (plan_dict_for_phase is not None)

    Returns None for an empty phase list: seeding the very first phase is
    seed_default_phase's job and goes through the plan-start screen, which
    collects a start date this function has no way to ask for."""
    if not phases:
        return None
    existing = {p.phase_number for p in phases}
    for number in sorted(PHASE_META):
        if number in existing:
            continue
        if (number - 1) not in existing:
            return None
        return number if plan_dict_for_phase(number) is not None else None
    return None


def begin_new_phase(phases: list[Phase], new_phase: Phase) -> list[Phase]:
    """Append a new phase, marking any prior phase whose date range has
    already ended as 'completed' (a data-hygiene step — active_phase()'s own
    date check already excludes lapsed phases regardless, so this doesn't
    change behavior, just keeps stored status honest). Caller persists via
    repo.set_phases(); this stays a pure list transform.

    Uses dataclasses.replace (only touching status) rather than
    reconstructing each Phase field-by-field — the latter silently dropped
    date_overrides/shift_reasons back to {} on every transition (both
    default to {} when omitted), erasing a phase's entire manual-reschedule
    and readiness-auto-shift history the moment it got marked completed.
    Confirmed by adversarial review; regression-guarded in
    tests/test_sessions.py."""
    today = date.today()
    updated = [
        replace(p, status="completed") if p.status == "active" and _plan.phase_end_date(p) < today else p
        for p in phases
    ]
    updated.append(new_phase)
    return updated


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
