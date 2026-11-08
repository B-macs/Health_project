"""The EGYM circuit (2026-11-08) — the fourth item of the Training tab's "+" menu.

The athlete, 2026-11-08: "I want to be able to do a egym circuit at any time in
training by pressing the plus button at the top right of the training, it is a
two round circuit, I should be presented a order but I can change it up as I
please, The numbers I calculate at the end is the tonage that I do per
exercise." His answers the same day: "I don't want to add in the sets and
reps. All I want to add in is the tonnage ... the tonnage is presented to me on
the machine", "I can go classic. So the tonnage is exact", "they're all
different machines, so keep them apart", "round two always follows round one
... if I switch them around in round one, then in round two, they should be the
same", "the weight doesn't change, all your recording is tonnage", "add it to
the weekly tonnage".

WHAT RUNS. His gym's fourteen EGYM machines, two rounds, one set on each
machine in each round. EGYM sets the weight from its own strength test and
counts the set; the app records the one number the machine shows at the end of
the set, the tonnage (reps x kg in the Classic method, where the weight is the
same for the whole set). The app prescribes no weight and no reps.

HOW A TONNAGE IS STORED. Each set is one rep at the tonnage, in kg: the stored
set's reps x weight IS the tonnage, so every reader of the log's work —
services/tonnage.py's weekly tonnage, an exercise's total_volume_kg, services/
volume.py — counts it without a new column. No strength reader may read it as a
lift: services/strength.qualifying_rows leaves out every name in TONNAGE_ONLY,
so no 1RM is ever estimated from "1 rep at 1,240 kg" (tests/test_egym_circuit.py).

THE ORDER. Lower and upper body take turns, so each muscle rests; the biggest
machines come first and the core comes last, as in the 12-week block. He may
change it in round 1; round 2 then follows the order he used in round 1
(services/egym_session.move_groups).

THE THREE LAYERS, the "+" session's pattern (services/accessory.py):

    egym_circuit.py             WHAT  — the machines, the rounds, the records
        |
    services/egym_session.py    WHICH — the moves, the time, the last tonnage
        |
    services/training_session   HOW   — the same guided flow and save

NOTHING IS COPIED (CLAUDE.md Key Rule 25): every entry is written here with its
record in EGYM_PICKS. These are his gym's EGYM machines, apart from the block's
machines of the same kind (his answer: "they're all different machines"), so
every name starts with "EGYM" and keeps its own history.
"""
from __future__ import annotations

from goal_week import Pick
from training_plan import _ex

#: The session's name on the menu and the overview.
OBJECTIVE = "EGYM circuit"
PHASE = "EGYM — Circuit"
#: The session rating the save screen starts at.
RPE_TARGET = 6
#: Two rounds, one set on each machine in each round.
ROUNDS = 2
#: One EGYM set, in seconds: 15 reps at 2 s up and 2 s down, EGYM's own
#: program (knowledge.egym.com, training programs, read 2026-11-08). The time
#: model's only use of it (services/egym_session.modelled_seconds).
SET_SECONDS = 60

#: Every set's last line of the how-to.
_TAIL = ("Log in with your wristband and use the Classic method. At the end of the set, "
         "type the tonnage the screen shows.")


def _machine(name: str, position: str, focus: str) -> dict:
    """One machine: a one-set entry whose single "rep" carries the tonnage."""
    ex = _ex(
        name=name,
        ex_type="reps",
        sets=1, reps=1, rest_seconds=0,
        mechanics=f"{position} {_TAIL}",
        biomechanical_focus=focus,
        progression="EGYM sets the weight from its own strength test.",
        regression="Lower the weight on the screen before the set.",
    )
    # The phone asks for the tonnage the machine shows, never reps or weight.
    ex["tonnage_entry"] = True
    return ex


SQUAT = _machine(
    "EGYM Squat",
    "Stand on the platform with the pads on your shoulders, feet hip-width apart.",
    "Quads and glutes, standing squat pattern.")
LAT_PULLDOWN = _machine(
    "EGYM Lat Pulldown",
    "Sit with the thigh pad on your thighs. Pull the handles down to your upper chest.",
    "Lats and upper back, vertical pull.")
LEG_CURL = _machine(
    "EGYM Leg Curl",
    "Sit with the thigh pad on your thighs and the lower pad above your heels. Bend the "
    "knees against the pad.",
    "Hamstrings, knee bend with the hips bent.")
CHEST_PRESS = _machine(
    "EGYM Chest Press",
    "Sit with your back on the pad. Press the handles forward. On the way back, the right "
    "arm goes only as deep as is easy.",
    "Chest and front of the shoulders, horizontal press; the right arm's depth as on the "
    "block's chest press.")
LEG_PRESS = _machine(
    "EGYM Leg Press",
    "Sit with your back on the pad and your feet on the plate, hip-width apart. Press the "
    "plate away.",
    "Quads and glutes, seated press.")
ROW = _machine(
    "EGYM Row",
    "Sit with your chest on the pad. Pull the handles to your ribs.",
    "Mid-back and lats, horizontal pull.")
GLUTE_PRESS = _machine(
    "EGYM Glute Press",
    "Set the waist pad at your hips. Push the hip open to straight, then come back under "
    "control.",
    "Glutes, hip extension.")
TRICEPS_DIP = _machine(
    "EGYM Triceps Dip",
    "Sit tall and hold the handles at your sides. Push down until the arms are straight. "
    "The elbows stay at or in front of the line of the body.",
    "Triceps, downward press; the elbows never behind the body, the right shoulder's "
    "direction of instability (his answer 4, 2026-11-08: keep it).")
LEG_EXTENSION = _machine(
    "EGYM Leg Extension",
    "Sit with your back on the pad and the shin pad above your ankles. Straighten the knees.",
    "Quads, knee straightening.")
BICEPS_CURL = _machine(
    "EGYM Biceps Curl",
    "Sit with your upper arms on the pad. Curl the handles up.",
    "Biceps, elbow bend.")
HIP_ABDUCTOR = _machine(
    "EGYM Hip Abductor",
    "Sit with the pads on the outside of your knees. Push the knees out.",
    "Outer hip (glute medius), hip opening.")
HIP_ADDUCTOR = _machine(
    "EGYM Hip Adductor",
    "Sit with the pads on the inside of your knees. Start only as wide as you control, then "
    "squeeze the knees in.",
    "Inner thigh, hip closing; the start width as on the block's adductor machine.")
BACK_EXTENSION = _machine(
    "EGYM Back Extension",
    "Sit with the pad on your upper back and your hips held by the pad. Push back to upright.",
    "Back extensors, seated extension.")
ABDOMINAL_CRUNCH = _machine(
    "EGYM Abdominal Crunch",
    "Sit with your feet under the bars and your chest on the pads. Curl the chest toward "
    "the hips.",
    "Abs, trunk curl; last, as the abs are in the block.")

#: The suggested order of one round.
MACHINES: tuple[dict, ...] = (
    SQUAT, LAT_PULLDOWN, LEG_CURL, CHEST_PRESS, LEG_PRESS, ROW, GLUTE_PRESS, TRICEPS_DIP,
    LEG_EXTENSION, BICEPS_CURL, HIP_ABDUCTOR, HIP_ADDUCTOR, BACK_EXTENSION, ABDOMINAL_CRUNCH,
)


def entries() -> list[dict]:
    """The session's entries in order: round 1, then round 2 in the same order,
    each a fresh copy (one object runs in both rounds)."""
    return [dict(ex) for _ in range(ROUNDS) for ex in MACHINES]


def names() -> tuple[str, ...]:
    return tuple(ex["name"] for ex in MACHINES)


#: Names whose stored set is a tonnage, never a lift (see the module note);
#: training_constants.TONNAGE_ONLY_EXERCISES holds the same names for the
#: strength readers (tests/test_egym_circuit.py keeps the two equal).
TONNAGE_ONLY: frozenset[str] = frozenset(names())


#: The session note, shown on the overview before Start and stored with the session.
NOTE = (
    "Two rounds, one set on each machine. Log in with your wristband and use the Classic "
    "method, so the tonnage is exact. After each set, type the tonnage the screen shows. "
    "In round 1 you can change the order; round 2 follows the order you used."
)


# ─── The workflow record — no exercise enters by copying (Key Rule 25) ───────

_SOURCE = ("his words, 2026-11-08: 'Above are the EGYM Machines, in my gym, I want to be able "
           "to do a egym circuit at any time in training'")
_BETTER = ("checked 2026-11-08: the circuit is his gym's EGYM line, so a better exercise "
           "can only be another EGYM machine; he named all fourteen")

#: goal "egym": the extra full-body circuit on his gym's EGYM machines.
EGYM_PICKS: dict[str, Pick] = {
    ex["name"]: Pick("egym", area, "one set a round, Classic", reason, _SOURCE, better=_BETTER)
    for ex, area, reason in (
        (SQUAT, "quads and glutes", "His gym's EGYM squat; the circuit's biggest lift, first."),
        (LAT_PULLDOWN, "lats", "The circuit's vertical pull."),
        (LEG_CURL, "hamstrings", "The circuit's knee bend for the back of the thigh."),
        (CHEST_PRESS, "chest", "The circuit's horizontal press."),
        (LEG_PRESS, "quads and glutes", "The circuit's second leg press pattern."),
        (ROW, "mid-back", "The circuit's horizontal pull."),
        (GLUTE_PRESS, "glutes", "The circuit's hip extension."),
        (TRICEPS_DIP, "triceps", "The circuit's arm press; he keeps it (answer 4, 2026-11-08)."),
        (LEG_EXTENSION, "quads", "The circuit's knee straightening."),
        (BICEPS_CURL, "biceps", "The circuit's arm curl."),
        (HIP_ABDUCTOR, "outer hip", "The circuit's hip opening."),
        (HIP_ADDUCTOR, "inner thigh", "The circuit's hip closing."),
        (BACK_EXTENSION, "back extensors", "The circuit's back extension."),
        (ABDOMINAL_CRUNCH, "abs", "The circuit's trunk curl, last."),
    )
}
