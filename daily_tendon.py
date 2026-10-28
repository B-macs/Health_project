"""The daily tendon session (WP-40, 2026-10-28) — the Training tab's second tile.

The athlete, 2026-10-28: "the other tile will be the daily training day ... at
only 10mins per day I will plan to do this at least 8 hours before or after my
normal training day", and "The goal with this is to improve my tendons and
ligaments while I train my muscles". At home, with no weights. "In all cases
follow Baars studies" (Keith Baar, "Physical training, performance and injury
prevention"; the Baar notes, Input_files/baar_tendon_annex.md).

WHAT RUNS. Three rounds, the same every day: the active hang, the half push-up
hold and a calf hold, and a neck set after rounds 1 and 2. Each item rests
while the others work, so the only rest between entries is the change.

BAAR'S RULES, and where each one is in this file:
- Hold length: about 10 s for healthy tissue, about 30 s for a large tendon or
  a long-standing injury. The shoulder has had two surgeries and the Achilles
  is a large tendon, so the hang, the push-up and the calves hold 30 s. The
  neck keeps its own 10-second pushes (his choice, 2026-10-15).
- A slow start (3-5 s): every 30-second hold carries LEAD_IN_SECONDS, which the
  phone runs as a countdown before the hold. The phone holds no rule.
- About half effort, never maximal; the position sets the effort, never a
  weight. In the session note (NOTE), not in each how-to.
- The angle changes between rounds: the calves only. A deeper push-up takes
  the right arm behind the line of the body, his measured limit (a face-down
  arm raise: right 20 cm, left 40 cm, 2026-08-13).
- About 10 minutes, then 6-8 hours to the next tendon load: a reminder on the
  tile (services/daily_session.reminder), never a lock (his words: "Reminder
  only let me make the desicion on when to do it and never locked").

NOTHING IS COPIED (CLAUDE.md Key Rule 25). Every exercise is written here, with
its record in DAILY_PICKS. The neck stretch moved here from the gym days' home
list (his words, 2026-10-28: "Put the neck stretch into this daily training as
well"); its record moved with it. The hang is not training_plan's step-2
object: this one holds 30 s (Baar) where the "+" session's holds 15 s. The
builder `_ex` comes from training_plan.py because it is the shape every view
reads, not an exercise.

⚠ EVIDENCE, recorded rather than resolved: the 6-8 hour gap comes from
engineered ligament and rat bone, and the 30-second hold from tissue
measurements and one case study. docs/training/rest_interval_evidence_review_
2026-08-13.md found short hard efforts better for tendon stiffness in people.
His choice stands: "In all cases follow Baars studies".
"""
from __future__ import annotations

from goal_week import Pick
from training_plan import _ex

#: The session's name on the tile and the overview.
OBJECTIVE = "Daily tendon session"
PHASE = "Daily — Tendons"
#: The session rating the save screen starts at: about half effort.
RPE_TARGET = 4
#: A 30-second hold, Baar's length for a large tendon or a long-standing injury.
HOLD_SECONDS = 30
#: The slow start before every 30-second hold (Baar: 3-5 s), run by the phone
#: as a countdown before the hold timer.
LEAD_IN_SECONDS = 5
#: The change between two entries. Every item rests while the others work, so
#: this is the whole gap. NOT MEASURED: the gym's changeovers (sessions.
#: CHANGEOVER_SECONDS, 74 s to a floor item) were measured walking between
#: stations, and this session never leaves one room. Re-measure from the
#: session's own set times once it has been logged a few weeks.
CHANGE_SECONDS = 15
#: The gap Baar's refractory figure asks for between two tendon loads.
GAP_HOURS = 8

_FOCUS_BAAR = (
    "Baar: a hold of about 30 s lets the strong fibres relax so the load reaches the rest of "
    "the tendon; a slow start keeps the load from arriving fast, which is what injures tendon. "
)


def _hold(**kw) -> dict:
    """A 30-second hold of this session: one set, the change as its rest, and
    the slow start."""
    return {**_ex(ex_type="hold", sets=1, hold_seconds=HOLD_SECONDS, rest_seconds=CHANGE_SECONDS,
                  **kw),
            "lead_in_seconds": LEAD_IN_SECONDS}


ACTIVE_HANG = _hold(
    name="Active Hang",
    mechanics=(
        "Both hands on the bar, overhand grip. Step up to the bar and take your feet off slowly, "
        "over the countdown. Keep the shoulder blades pulled down and back, your ears clear of "
        "your shoulders. If the shoulders creep up before the bell, put your feet down for the "
        "rest of the hold. At the bell, put your feet down slowly."
    ),
    biomechanical_focus=(
        _FOCUS_BAAR + "The shoulder and grip tendons, overhead. Step 2 of the hang ladder "
        "(his words, 2026-10-28: 'Im already at step 2 I can hold on a bar for more than 15 "
        "seconds'); step 3, the passive hang, stays held until four clean weeks at step 2 "
        "(services/accessory.HANG_MAX_STEP). Both hands always: three anterior dislocations, a "
        "capsular repair and a Latarjet on a shallow socket (finding #6)."
    ),
    progression=("Too easy: none. The passive hang is the next step, held until four clean "
                 "weeks at this one."),
    regression="Too hard: feet on a chair, taking some of your weight.",
    warning=(
        "Stop the hang for today on a hard, sudden stop at the end of the range on the right, "
        "on any feeling that the right shoulder may slip, or on apprehension. Never one arm."
    ),
)

HALF_PUSH_UP_HOLD = _hold(
    name="Half Push-Up Hold",
    mechanics=(
        "Hands on the floor under your shoulders, elbows about 45 degrees from your sides, body "
        "straight from head to heels. Lower slowly, over the countdown, until your elbows are "
        "level with your body, and hold there. Never lower. At the bell, push up slowly. If a "
        "wrist hurts, hold on your fists so the wrist stays straight."
    ),
    biomechanical_focus=(
        _FOCUS_BAAR + "The chest and the front of the shoulder, at home. Elbows level with the "
        "body is the right arm's measured limit: a face-down arm raise reached 20 cm right "
        "against 40 cm left (2026-08-13), so a deeper push-up takes the right arm behind the "
        "line of the body."
    ),
    progression="Too easy: feet on a chair.",
    regression="Too hard: hands on a bench or the wall.",
)

_CALF_HOW = (
    "Stand on one foot, fingertips on the wall for balance. Rise slowly, over the countdown, "
    "until your heel is half way up, and hold there. At the bell, lower slowly. Then the other "
    "foot."
)

CALF_HOLD = _hold(
    name="Single-Leg Calf Hold",
    laterality="unilateral",
    mechanics="Knee straight. " + _CALF_HOW,
    biomechanical_focus=(
        _FOCUS_BAAR + "The Achilles tendon, a large tendon, so 30 s. Nothing in the 12-week "
        "block loads the calves, and the Achilles carries most of the load when running "
        "returns (gate 1). Knee straight works the outer calf muscle at its full length."
    ),
    progression="Too easy: on a step edge, with the heel lower.",
    regression="Too hard: on two feet.",
)

CALF_HOLD_BENT = _hold(
    name="Single-Leg Calf Hold (Bent Knee)",
    laterality="unilateral",
    mechanics="Knee a little bent. " + _CALF_HOW,
    biomechanical_focus=(
        _FOCUS_BAAR + "The same tendon from a second angle (Baar: change the angle between "
        "sets). A bent knee shortens the outer calf muscle, so the deep one takes more of the "
        "load."
    ),
    progression="Too easy: on a step edge, with the heel lower.",
    regression="Too hard: on two feet.",
)

NECK_STRETCH = _ex(
    name="Neck Working Stretch (Right)",
    ex_type="hold_reps",
    sets=1, reps_in_set=4, hold_seconds=10, rest_seconds=CHANGE_SECONDS,
    mechanics=(
        "Sit tall. Tilt your head to the left, ear toward the shoulder, until you feel a "
        "stretch on the right side of your neck. Put your right hand on the right side of "
        "your head. Push your head into the hand for 10 seconds at about a third of your "
        "effort; the hand stops it moving. Relax for 5 seconds and let the head sink a little "
        "further. Four pushes is one set."
    ),
    biomechanical_focus=(
        "The right side of the neck (goal B), strength at length: his choice, 2026-10-15. Two "
        "sets a day, one after round 1 and one after round 2, since 2026-10-28 (it was two sets "
        "on the gym days, at home). Baar's length for healthy tissue is about 10 s, which is "
        "its own dose. Contract-relax and static stretching gain about the same range (Konrad "
        "et al. 2024); this one adds a strength part."
    ),
    progression="The stretch eases in the first push → tilt a little further at the start.",
    regression="Any tingling into the arm → stop; tilt less.",
)

#: The entries in the order they run: three rounds, a neck set after rounds 1
#: and 2, the calves' knee straight in rounds 1 and 3 and bent in round 2.
ROUNDS: tuple[tuple[dict, ...], ...] = (
    (ACTIVE_HANG, HALF_PUSH_UP_HOLD, CALF_HOLD, NECK_STRETCH),
    (ACTIVE_HANG, HALF_PUSH_UP_HOLD, CALF_HOLD_BENT, NECK_STRETCH),
    (ACTIVE_HANG, HALF_PUSH_UP_HOLD, CALF_HOLD),
)


def entries() -> list[dict]:
    """The session's entries in order, each a fresh copy (one object is
    authored once and runs in up to three rounds)."""
    return [dict(ex) for rnd in ROUNDS for ex in rnd]


#: Every exercise this session can emit, once each.
LIBRARY: tuple[dict, ...] = (ACTIVE_HANG, HALF_PUSH_UP_HOLD, CALF_HOLD, CALF_HOLD_BENT, NECK_STRETCH)


def names() -> tuple[str, ...]:
    return tuple(ex["name"] for ex in LIBRARY)


#: The session note, shown on the overview before Start and stored with the
#: session: Baar's conduct rules, which belong to every item at once.
NOTE = (
    "Effort about half, never maximal: you feel the target working, without shaking, and the "
    "hold is hard by the end. Change the position to set the effort, never add weight. Take the "
    "weight slowly during the countdown and let it go slowly at the bell. Pain up to 2 out of 10 "
    "is acceptable; a warm ache that spreads is normal. A sharp pain at one point: stop that "
    "item for today."
)


# ─── The workflow record — no exercise enters by copying (Key Rule 25) ───────

#: goal "tendons" (WP-40: "improve my tendons and ligaments while I train my
#: muscles") or "B" (the press goal, whose blocker the neck stretch works on).
DAILY_PICKS: dict[str, Pick] = {
    "Active Hang": Pick(
        "tendons", "shoulders and grip", "tendon load, overhead",
        "Loads the shoulder and grip tendons overhead, with the shoulder muscles doing the "
        "holding: stability on his right shoulder is muscular since the Latarjet.",
        "his words, 2026-10-28: 'I also have pull up bar for dead hangs', 'isometic dead hangs', "
        "'Im already at step 2'; Input_files/cluster_d_prescription.md §A (hanging, daily short "
        "exposures)",
        better="checked 2026-10-28: the passive hang (step 3) loads the loose shoulder tissue "
               "rather than the muscles and stays held; the scapular pull-up carries more load "
               "than the ladder allows; so the active hang"),
    "Half Push-Up Hold": Pick(
        "tendons", "chest and front of the shoulder", "tendon load, held",
        "A held push-up loads the chest, front-of-shoulder and arm tendons at home with no "
        "weights; half depth keeps the right arm at the line of the body.",
        "his words, 2026-10-28: 'half push up holds'",
        better="checked 2026-10-28: a band chest-press hold does not reach half effort with a "
               "home band; a full-depth push-up passes the right arm's measured limit; so the "
               "half push-up hold"),
    "Single-Leg Calf Hold": Pick(
        "tendons", "calves (Achilles)", "tendon load, held",
        "The Achilles before running returns: nothing in the gym week loads the calves.",
        "his answer, 2026-10-28: 'keep the calf holds'",
        better="checked 2026-10-28: slow single-leg calf raises are the next step, before "
               "running returns; a two-leg hold is too easy; so the single-leg hold now"),
    "Single-Leg Calf Hold (Bent Knee)": Pick(
        "tendons", "calves (Achilles)", "tendon load, second angle",
        "The same tendon from a second angle, Baar's angle change between sets.",
        "his answer, 2026-10-28: 'keep the calf holds'",
        better="checked 2026-10-28: as the straight-knee hold; the bent knee moves the load to "
               "the deep calf muscle, which the straight knee leaves light"),
    "Neck Working Stretch (Right)": Pick(
        "B", "neck, right side", "strength at length",
        "Head tilted to the left, 10-second pushes into the hand; every day in this session.",
        "his choice, 2026-10-15; in the daily session from 2026-10-28 ('Put the neck stretch "
        "into this daily training as well')",
        better="checked 2026-10-15: contract-relax and static stretching gain about the same "
               "range (Konrad et al. 2024), and this one adds a strength part"),
}
