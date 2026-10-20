# -*- coding: utf-8 -*-
"""A made-up training session for the phone app's mock engine (rebuild Phase 6).

    python scripts/make_session_fixture.py           # write app/dev/session_fixture.json
    python scripts/make_session_fixture.py --check   # 1 when the file is not this output

The phone walks the engine's pre-walked guided flow (services/guided_flow.walk)
and holds no step rule. So the mock's session is made by the SAME walk: one
made-up exercise of every kind the flow has (reps on both sides and on one,
a ramp set before its lift, a hold, held reps, a band, the timed plank test,
a walk), dosed as the engine doses them, then shaped by the engine's response
model. A phone test that walks this file walks exactly what the engine would
send. Every name and number is invented.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for extra in (ROOT, ROOT / "api"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

OUT = ROOT / "app" / "dev" / "session_fixture.json"
DAY = "2026-10-20"
FIRST = "left"


def _exercises() -> list[dict]:
    """Made-up exercises, one per kind the guided flow walks."""
    return [
        {"name": "Made-up march", "type": "reps", "laterality": "unilateral", "sets": 2, "reps": 6,
         "rest_seconds": 20, "warmup": True},
        {"name": "Made-up squat ramp", "type": "reps", "laterality": "bilateral", "sets": 1, "reps": 5,
         "rest_seconds": 30, "equipment_type": "dumbbell", "increment_size": 2.25,
         "increment_unit": "kg", "weight_kg": 13.5, "warmup": True},
        {"name": "Made-up squat", "type": "reps", "laterality": "bilateral", "sets": 3, "reps": 9,
         "rep_min": 8, "rep_max": 12, "rest_seconds": 40, "tempo": "3-1-1",
         "equipment_type": "dumbbell", "increment_size": 2.25, "increment_unit": "kg", "weight_kg": 22.5},
        {"name": "Made-up split squat", "type": "reps", "laterality": "unilateral", "sets": 2, "reps": 8,
         "rest_seconds": 30, "equipment_type": "dumbbell", "increment_size": 2.25,
         "increment_unit": "kg", "weight_kg": 9.0},
        {"name": "Made-up side plank", "type": "hold", "laterality": "unilateral", "sets": 2,
         "hold_seconds": 6, "rest_seconds": 15},
        {"name": "Made-up dead bug", "type": "hold_reps", "laterality": "bilateral", "sets": 2,
         "reps_in_set": 3, "hold_seconds": 3, "rest_seconds": 15},
        {"name": "Made-up band row", "type": "reps", "laterality": "bilateral", "sets": 2, "reps": 12,
         "rest_seconds": 20, "equipment_type": "band", "band_tier": "Red"},
        {"name": "Made-up plank (Timed)", "type": "hold", "laterality": "bilateral", "sets": 1,
         "hold_seconds": 30, "rest_seconds": 0},
        {"name": "Made-up walk", "type": "duration", "laterality": "bilateral", "sets": 1,
         "duration_minutes": 1, "rest_seconds": 0},
    ]


def build() -> dict:
    from healthapi.schemas_training import SessionPlanOut
    from services import guided_flow
    from services import sessions as sess
    from services import training_session as ts

    exercises = _exercises()
    out = []
    for i, ex in enumerate(exercises):
        entry = None
        if ex.get("weight_kg") is not None or ex.get("band_tier"):
            entry = {"reps": ex.get("reps"), "weight_kg": ex.get("weight_kg"),
                     "band_tier": ex.get("band_tier"), "source": "range",
                     "next_step": "The weight goes up after every set reaches 12." if i == 2 else ""}
        out.append({
            "index": i, **{k: ex.get(k) for k in ts.EXERCISE_FIELDS},
            "icon": sess.type_icon(ex), "warmup": bool(ex.get("warmup")),
            "timed_test": sess.is_timed_test(ex), "timer": ts.timer_kind(ex),
            "prescription": sess.prescription_label(ex),
            "mechanics": f"How to do the {ex['name'].lower()}: made-up words for the tests.",
            "warning": "Made-up warning: shown only because the engine sent it." if i == 3 else "",
            "ramp_for": 2 if i == 1 else None,
            "reps_editable": sess.reps_are_editable(ex),
            "entry": entry, "previous": {"reps": 9, "weight_kg": 20.25} if i == 2 else None,
            "previous_caption": "Last: 3 × 9 at 20.25 kg" if i == 2 else "",
            "delta": "+2.25 kg" if i == 2 else "", "delta_direction": "up" if i == 2 else "",
            "entry_caption": "Every set reached the top of the range, so the weight goes up one step today." if i == 2 else "",
            "contradiction": None, "garmin_pull": False, "garmin_window": None,
            "estimated_minutes": max(1, round(sess.exercise_duration_seconds(ex) / 60)),
        })
    model = sess.estimate_duration(exercises)
    plan = {
        "kind": "plan", "date": DAY, "day_num": 2, "objective": "Made-up objective for the tests.",
        "phase": "Made-up block", "rpe_target": 7, "first_side": FIRST,
        "banner": {"kind": "", "text": "", "cause": "", "acwr_advisory": ""},
        "adaptation": {"volume_factor": 1.0, "reduced": False, "banner_kind": "", "volume_note": "",
                       "badge_shown": False},
        "exercises": out,
        "steps": guided_flow.walk(exercises, FIRST),
        "model_minutes": model, "min_minutes": sess.MIN_SESSION_MINUTES,
        "ask_length_above_minutes": sess.DURATION_CHECK_RATIO * model,
        "rest_taken_max_seconds": guided_flow.REST_TAKEN_MAX_SECONDS,
        "garmin_configured": False,
        "band_tiers": [{"tier": t, "label": sess.BAND_TIER_LABELS.get(t, "")} for t in sess.BAND_TIERS],
        "reasons": [],
        "next_day": {"day_num": 3, "objective": "Made-up next day.", "exercises": []},
        "note": "",
    }
    return SessionPlanOut(**plan).model_dump(mode="json")


def text() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 when the file is not this output")
    args = ap.parse_args()
    fresh = text()
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == fresh
        print("session_fixture.json is current" if same else "session_fixture.json is stale: run the script")
        return 0 if same else 1
    OUT.write_text(fresh, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
