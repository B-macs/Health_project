"""The 12-week block — the goal system's first block, phase 5.

Every decision is in docs/training/goal_system.md, steps 1-8, approved by the
athlete from 2026-10-14 to 2026-10-16. The block replaces Block B and starts on
the Monday after the push (*"When we push this new session block that will be
12 weeks long, it will overwrite all of the current block ... it starts on the
next monday"*).

THE WEEK. Strength on Monday, Tuesday, Thursday and Friday — sessions A, B, C
and D, every one full body — rest on Wednesday and Saturday, and the
flexibility session on Sunday. A, B and C meet the weekly dose; D is the bonus.
No running: running waits for gate 1 (goal A, stage 1).

WHERE THE SESSIONS COME FROM. goal_week.py holds a card for every exercise and
services/placement.py places the cards by fixed rules; the four sessions below
are what those rules produce, written out once so services/sessions.py can
register the block without importing the placement (the placement imports
sessions for its time model). tests/test_goal_block.py fails when a session
here and the placed session differ in any name, order, set, rep, rest,
equipment or side. To change a session, change its card in goal_week.py and
write the placed result here; never move an exercise here by hand.

NOTHING IS COPIED (CLAUDE.md Key Rule 25). Every exercise is written in this
file and has a workflow record in goal_week.PICKS (goal, area, reason, source,
and the check against a better exercise). The builder `_ex` comes from
training_plan.py because it is the shape every view reads, not an exercise.
The Sunday session is built from the flexibility prescription for the last
reading (cluster_a_prescription, pattern D), with each item's how-to taken
from the exercise library — the flexibility goal's own workflow.

LOAD. One rule for every lift with a rep range (engine.range_progression, Key
Rule 23): the weight goes up when every set reached the top of the range or one
set went past it, in every session of that lift within 7 days; then the aim is
the middle-bottom of the range. 8-12 for a compound lift, 10-15 for an
isolation or core item. Starting weights are light on purpose: the athlete sets
the real weight in the first session, and the rule takes over from the second
(his choice, 2026-10-16). Steps: his dumbbells go up in 2.25 kg, so a lift with
a dumbbell in each hand (logged as the total) steps 4.5 kg; machines 5 kg (the
hack squat 2.5 kg a side); the back extension a 2.5 kg plate; cables one unit.

EFFORT (step 4). Machines and cables: working sets 1-2 reps short, the last set
to failure. Dumbbell Romanian deadlift and the back extension: 1-3 short, never
to failure. Single-arm row: 1-2 short, the last set to failure. The Y raise
before a press: 1-2 short (approved 2026-10-16). Abs and the hip airplane:
every set to failure. Strength at length (the adductor machine, the cable hip
flexion): hard, never to failure.
"""
from __future__ import annotations

import re

import cluster_a_mechanics as _mech
import cluster_a_prescription as _rx
from training_plan import _ex

BLOCK_NAME = "12-Week Block — Hips, Back and Strength"
WEEKS = 12
#: The timed plank test (session A, in place of that day's abs) and the rib
#: and pelvis test (Sunday morning): week 1 and week 12.
TEST_WEEKS = (1, 12)
#: The flexibility retest: three Sunday mornings, before the session, so the
#: day-to-day spread is known before a number counts.
FLEX_RETEST_WEEKS = (1, 2, 3)
#: The flexibility reading the Sunday session is prescribed for: the battery of
#: 2026-08-12 read pattern D (the adductors with the knees bent). The retest in
#: weeks 1-3 reads it again; a different pattern brings its own stack.
FLEX_PATTERN = "D"
#: The stage-2 limit on the session's own rating (rules.STAGE_CONSTRAINTS).
SESSION_RPE_TARGET = 8

COMPOUND_RANGE = {"rep_min": 8, "rep_max": 12}
ISOLATION_RANGE = {"rep_min": 10, "rep_max": 15}

#: His dumbbells, 2026-10-16: "all Dumbells go from 2.25 - 40kg in increments
#: of 2.25kg". A lift with one dumbbell steps one size; a lift with one in each
#: hand is logged as the total, so it steps both, 4.5 kg.
DUMBBELL_KG = 2.25
DUMBBELL_PAIR_KG = 4.5
#: Confirmed 2026-10-16 ("Yes all are correct").
MACHINE_KG = 5.0
PLATE_KG = 2.5
CABLE_UNIT = 1.0

_EVERY_SET_TO_FAILURE = "Take every set to failure."
_LAST_SET_TO_FAILURE = "Stop each working set 1-2 reps before failure; take the last set to failure."
_NEVER_TO_FAILURE = "Stop every set 1-3 reps before failure; never take a set to failure."


# ─── The warm-up (step 7) ────────────────────────────────────────────────────
# The 15-minute walk to the gym is the raise; then the march. The ramp sets sit
# on their lifts.

PSOAS_MARCH = _ex(
    name="Standing Psoas March",
    ex_type="reps",
    laterality="alternating",
    sets=2, reps=20, rest_seconds=20,
    mechanics=(
        "Stand tall, one fingertip on a wall for balance if you need it. Lift one knee "
        "above hip height with the front of the hip, then lower it slowly; then the other "
        "knee. Twenty each side, alternating. Your chest stays tall and your lower back "
        "stays still, with no lean back. On the RIGHT, the kneecap points straight ahead or "
        "turns slightly in. No swing: the knee goes only as high as you can lift it and "
        "lower it under control."
    ),
    biomechanical_focus=(
        "Step 7 (approved 2026-10-16): the walk to the gym is the raise, and this opens "
        "every strength session. His words, 2026-10-14: 'required to stretch and wake up "
        "that muscle'. Above 90 degrees of hip flexion the psoas is the only flexor still "
        "working; lifting one knee high tips the pelvis back and lengthens the standing "
        "side. Active range and no swing at Beighton 6/9."
    ),
    progression="Twenty each side with a still back → pause one second at the top.",
    regression="The lower back arches or you lean back → lift the knee only to hip height.",
)


# ─── The press block (step 6, S5): the release, then the Y raise, straight
#     before the first chest or shoulder press ───────────────────────────────

SHOULDER_RELEASE = _ex(
    name="Pec & Scar Release (Right)",
    ex_type="hold",
    sets=2, hold_seconds=60, rest_seconds=15,
    mechanics=(
        "First set, the chest: stand facing a wall with a massage ball between the wall "
        "and the front of your RIGHT chest, just below the outer third of the collarbone, "
        "toward the bony point at the front of the shoulder. Pin one tender spot with "
        "steady pressure, then move the arm slowly from your side to reaching forward and "
        "slightly up, palm turning out: five or six slow passes, then the next spot. "
        "Second set, the scar: fingertips beside the scar line, not along it, in small "
        "slow circles that move the skin each way. Pressure stays at 2 out of 10 or less. "
        "Move off at once on any tingling, numbness or ache running into the arm, or on a "
        "pulse under the ball. Never press into the hollow of the armpit."
    ),
    biomechanical_focus=(
        "Range for the front of the right shoulder (goal B), only before a chest or shoulder "
        "press: his words, 2026-10-16, 'It's to release the area before working on it'. The "
        "physiotherapist's 2026-08-10 reading is scar adhesion and high resting tone, not a "
        "short muscle, so pressure with movement rather than a stretch. Its effect is short "
        "(Wilke et al. 2020), which is why it sits straight before the press."
    ),
    progression="Fewer tender spots each week → spend the time on the spot that is left.",
    regression="Any arm symptom → leave the ball out today and do the scar work only.",
)

Y_RAISE = _ex(
    name="Single-Arm Cable Y Raise",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=12, rest_seconds=45,
    equipment_type="cable", weight_kg=2.0,
    increment_size=CABLE_UNIT, increment_unit="unit", **ISOLATION_RANGE,
    mechanics=(
        "Cable at the lowest pulley, one handle. Stand side-on with the cable on the other "
        "side of the working arm, the handle in front of your thighs. Raise the arm up and "
        "out on a diagonal into a Y, thumb up, until the arm is beside your ear or as high "
        "as it goes easily; on the RIGHT, only as high as it goes easily. Lower slowly "
        "across the front of the body. The shoulder stays down, away from the ear. All the "
        "reps on one arm, then the other. Stop every set 1-2 reps before failure: a press "
        "comes next."
    ),
    biomechanical_focus=(
        "The shoulder-blade muscles (lower and middle trapezius), straight after the release "
        "(his decision, 2026-10-15). Replaced the prone Y raise on 2026-10-16 (tier_lists/"
        "shoulder_blades.md): tension with the arm across the body, steps of one unit, one "
        "arm at a time so the left cannot do the right's work (physiotherapist, 2026-08-10: "
        "the right is weaker and the left works too much)."
    ),
    progression="The rep-range rule adds one unit.",
    regression="The right arm stops early → raise it only as far as it goes easily; log what you did.",
)

CHEST_PRESS = _ex(
    name="Machine Chest Press",
    ex_type="reps",
    sets=3, reps=10, rest_seconds=90,
    equipment_type="machine", weight_kg=20.0,
    increment_size=MACHINE_KG, **COMPOUND_RANGE,
    mechanics=(
        "Sit with your back flat on the pad and set the seat so the handles line up with "
        "the middle of your chest. Feet flat. Press the handles forward until the arms are "
        "straight, without locking the elbows hard, then return slowly. On the RIGHT, come "
        "back only as deep as it goes easily; never force the elbows behind the body. "
        "Shoulder blades stay back on the pad. " + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "Gate-1 main lift and the chest's pick (tier_lists/chest.md, S). Elbows not locked "
        "hard: they hyperextend (Beighton 6/9). The depth limit on the right is the measured "
        "limit of the arm behind the body (20 cm against 40 cm, 2026-08-13) after the "
        "Latarjet."
    ),
    progression="The rep-range rule adds 5 kg.",
    regression="The right shoulder objects at the bottom → shorten the range on both sides.",
)

SHOULDER_PRESS = _ex(
    name="Machine Shoulder Press",
    ex_type="reps",
    sets=3, reps=8, rest_seconds=90,
    equipment_type="machine", weight_kg=15.0,
    increment_size=MACHINE_KG, **COMPOUND_RANGE,
    mechanics=(
        "Sit with your back flat on the pad and set the seat so the handles start at "
        "shoulder height. Press up until the arms are straight, without locking the elbows "
        "hard, then lower slowly to shoulder height. The press goes up in front of your "
        "head, never behind it. Your ribs stay down and your lower back stays on the pad. "
        + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "Gate-1 main lift and goal B's training (a 20 kg overhead press): tier_lists/"
        "shoulders.md, A+, the best for the front delts, on a machine by his machine-only "
        "rule. Back supported, in front of the head (rules: 'machine shoulder press')."
    ),
    progression="The rep-range rule adds 5 kg.",
    regression="Shoulder pain at the top → stop the press just short of straight arms.",
)


# ─── The lifts ───────────────────────────────────────────────────────────────

WALKING_LUNGE = _ex(
    name="Walking Lunge (DB)",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=10, rest_seconds=90,
    equipment_type="dumbbell", weight_kg=13.5,
    increment_size=DUMBBELL_PAIR_KG, **COMPOUND_RANGE,
    mechanics=(
        "A dumbbell in each hand at your sides. Step forward into a long stride and lower "
        "until the back knee is just above the floor, front shin close to upright, then "
        "push through the front foot and step the back leg through into the next stride. "
        "The knees follow the line of the toes; on the RIGHT the kneecap points straight "
        "ahead. The reps shown are for each leg: log each leg's reps. Log the weight as "
        "both dumbbells together. " + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "Glute max (goal A, priority 1), quads second: tier_lists/glutes.md, S+, the best "
        "overall. A long stride keeps the work in the glutes at length. Dumbbells by his "
        "rule; logged as the total, so one step is both dumbbells one size up (4.5 kg)."
    ),
    progression="The rep-range rule adds 4.5 kg (both dumbbells one size up).",
    regression="Balance goes before the legs tire → do it as a static split squat by a rack.",
)

RDL = _ex(
    name="Romanian Deadlift (DB)",
    ex_type="reps",
    sets=3, reps=10, rest_seconds=90,
    equipment_type="dumbbell", weight_kg=27.0,
    increment_size=DUMBBELL_PAIR_KG, **COMPOUND_RANGE,
    mechanics=(
        "Stand tall with a dumbbell in each hand in front of your thighs, feet hip-width, "
        "knees soft. Push your hips back and let the dumbbells slide down the front of your "
        "legs, back flat, until you feel a strong stretch in the back of your thighs, about "
        "mid-shin. Drive your hips forward to stand tall again. The dumbbells stay close to "
        "your legs all the way. Log the weight as both dumbbells together. "
        + _NEVER_TO_FAILURE
    ),
    biomechanical_focus=(
        "The hamstrings and the lower glutes (goal A, priority 1): tier_lists/glutes.md "
        "second list, S, the best hip hinge. Never to failure (step 4: his one squat injury "
        "came from overload and fatigue). Logged as the total of both dumbbells, as his log "
        "has always been."
    ),
    progression="The rep-range rule adds 4.5 kg (both dumbbells one size up).",
    regression="The stretch arrives before mid-shin → stop where it arrives; that is your range.",
)

HACK_SQUAT = _ex(
    name="Hack Squat",
    ex_type="reps",
    sets=3, reps=10, rest_seconds=90,
    equipment_type="machine", weight_kg=20.0,
    increment_size=MACHINE_KG, **COMPOUND_RANGE,
    mechanics=(
        "Back flat on the pad, shoulders under the shoulder pads, feet hip-width in the "
        "middle of the platform. Release the safety handles. Bend the knees and lower "
        "slowly as deep as your back and hips stay on the pad, then press up through the "
        "whole foot until the legs are straight, without locking the knees hard. The knees "
        "follow the line of the toes; on the RIGHT the kneecap points straight ahead. Log "
        "the plates you add, both sides together. " + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "Gate-1 main lift for the legs (the quads, glute max second): tier_lists/quads.md, "
        "S, named the list's best, on a machine by his machine-only rule. Right kneecap "
        "straight ahead above 60 degrees of hip flexion (finding #4, key rule 7)."
    ),
    progression="The rep-range rule adds 5 kg (2.5 kg a side).",
    regression="The hips lift off the pad at the bottom → stop the descent just above that point.",
)

BACK_EXTENSION = _ex(
    name="45° Back Extension",
    ex_type="reps",
    sets=3, reps=12, rest_seconds=75,
    equipment_type="machine", weight_kg=0.0,
    increment_size=PLATE_KG, **COMPOUND_RANGE,
    mechanics=(
        "Set the pad just below the front of your hips so you can bend at the hips freely, "
        "heels against the foot plate. Arms crossed on your chest; when the app shows a "
        "weight, hold a plate against your chest. Keep your back straight from head to hips "
        "and lower your upper body by bending at the hips until you feel a stretch in the "
        "back of your thighs, then lift back up until your body is one straight line, not "
        "past it. " + _NEVER_TO_FAILURE
    ),
    biomechanical_focus=(
        "The deep back muscles (goal A, priority 1), glute max second: tier_lists/"
        "deep_back.md, approved 2026-10-16. Back kept straight, so the hips move and the back "
        "muscles hold. Not past the straight line: extension past it closes the narrowed "
        "right L5/S1 foramen (rules: 'back extension', caution). Starts at body weight; the "
        "rule adds a 2.5 kg plate."
    ),
    progression="The rep-range rule adds a 2.5 kg plate.",
    regression="Any leg symptom on the right → stop the set; log it.",
)

ROW = _ex(
    name="Single-Arm DB Row",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=10, rest_seconds=60,
    equipment_type="dumbbell", weight_kg=22.5,
    increment_size=DUMBBELL_KG, **COMPOUND_RANGE,
    mechanics=(
        "One hand and the same-side knee on a flat bench, back flat and level, the other "
        "foot on the floor. Hold the dumbbell straight under the shoulder. Pull it up toward "
        "your hip, elbow close to your body, then lower it slowly to a full stretch. On the "
        "RIGHT, the elbow goes behind the body only as far as it goes easily. All the reps "
        "on one arm, then the other. " + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "Gate-1 main lift for the back (shoulder-blade muscles second): tier_lists/back.md, "
        "S. One arm at a time so the left cannot do the right's work. The right elbow's "
        "limit is the measured limit of the arm behind the body (2026-08-13)."
    ),
    progression="The rep-range rule adds 2.25 kg (one dumbbell size).",
    regression="The right shoulder pinches at the top → stop the pull with the elbow level with your back.",
)

LEG_CURL = _ex(
    name="Seated Leg Curl",
    ex_type="reps",
    sets=3, reps=12, rest_seconds=75,
    equipment_type="machine", weight_kg=20.0,
    increment_size=MACHINE_KG, **ISOLATION_RANGE,
    mechanics=(
        "Sit with your back on the pad and your knees in line with the machine's pivot, the "
        "lower pad just above your heels and the thigh pad snug. Lean your chest slightly "
        "forward. Curl your heels down and back as far as they go, then return slowly until "
        "the legs are almost straight. " + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "The hamstrings at length, in the bonus session: tier_lists/hamstrings.md, A, kept "
        "over the lying curl by the two-list rule's trial clause (more hamstring growth with "
        "the seated curl in a 12-week trial, Maeo et al. 2021)."
    ),
    progression="The rep-range rule adds 5 kg.",
    regression="A cramp at the back of the thigh → stop the set; lower the weight next time.",
)

CROSSOVER = _ex(
    name="Reverse Cable Crossover",
    ex_type="reps",
    sets=3, reps=15, rest_seconds=45,
    equipment_type="cable", weight_kg=3.0,
    increment_size=CABLE_UNIT, increment_unit="unit", **ISOLATION_RANGE,
    mechanics=(
        "Two cables at shoulder height, no handles. Hold the cable ends crossed in front of "
        "you: the right cable in the left hand, the left cable in the right hand. Stand in "
        "the middle. Pull both arms out and back in a wide arc, arms almost straight, until "
        "your hands are out to the sides in line with your body; on the RIGHT, not behind "
        "it. Return slowly across the front. " + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "The rear delts (goal B): tier_lists/shoulders.md, S, the best for the rear delts. "
        "The right arm stops at the line of the body (rules: 'reverse cable crossover', the "
        "measured limit of 2026-08-13)."
    ),
    progression="The rep-range rule adds one unit.",
    regression="The right shoulder objects at the end → finish the arc in front of the body.",
)

LATERAL_RAISE = _ex(
    name="Cable Lateral Raise",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=15, rest_seconds=45,
    equipment_type="cable", weight_kg=2.0,
    increment_size=CABLE_UNIT, increment_unit="unit", **ISOLATION_RANGE,
    mechanics=(
        "Cable at the lowest pulley, one handle. Stand side-on with the cable on the side "
        "away from the working arm, the handle in front of your thighs. Raise the arm out to "
        "the side, elbow slightly bent, to shoulder height and no higher, then lower slowly "
        "across the front of the body. The shoulder stays down. All the reps on one arm, then "
        "the other. " + _LAST_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "The side delts (goal B): tier_lists/shoulders.md, S+, the best overall, with tension "
        "at the stretch. The 2025 log notes the shoulder injury came back with a dumbbell "
        "lateral raise over 7 kg; the cable starts light and steps one unit (about 0.5 kg)."
    ),
    progression="The rep-range rule adds one unit.",
    regression="Pain at the front of the shoulder → stop at a lower height; log it.",
)

ADDUCTOR_MACHINE = _ex(
    name="Adductor Machine (Seated)",
    ex_type="reps",
    sets=3, reps=12, rest_seconds=60,
    equipment_type="machine", weight_kg=20.0,
    increment_size=MACHINE_KG, **ISOLATION_RANGE,
    mechanics=(
        "Sit with your back on the pad, knees bent, the pads on the inside of your knees. Set "
        "the start width so the legs open only as wide as you can control. Squeeze the legs "
        "together until the pads meet, then let them open slowly back to the start, with no "
        "bounce at the open end. Hard sets, but never to failure: stop 1-2 reps before."
    ),
    biomechanical_focus=(
        "The flexibility goal's blocker, the adductors with the knees bent (pattern D: 21.5 cm "
        "against 10 cm, 2026-08-12): strength from a wide start, in the tested position. "
        "tier_lists/adductors.md, S; replaced the adductor ladder on 2026-10-16. Controlled "
        "range at Beighton 6/9 (rules: 'adductor machine')."
    ),
    progression="The rep-range rule adds 5 kg.",
    regression="A pull high in the groin → narrow the start width.",
)

HIP_FLEXION = _ex(
    name="Standing Cable Hip Flexion",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=12, rest_seconds=45,
    equipment_type="cable", weight_kg=2.0,
    increment_size=CABLE_UNIT, increment_unit="unit", **ISOLATION_RANGE,
    mechanics=(
        "Ankle cuff on, cable at the lowest pulley. Stand facing away from the machine and "
        "hold a support. Start with the working leg a step behind you, knee straight, so the "
        "front of the hip is long. Lift the leg forward to about hip height, slowly and with "
        "no swing, then lower it slowly back behind you. Chest tall, no lean back. On the "
        "RIGHT, the kneecap points straight ahead. All the reps on one leg, then the other. "
        "Hard sets, but never to failure: stop when the position starts to slip."
    ),
    biomechanical_focus=(
        "Strength at length for the hip flexors (his rule, 2026-08-24: 'more time on holds "
        "and strengthing to get the real benefits'): tier_lists/hip_flexors.md, S; replaced "
        "the end-range psoas isometric on 2026-10-16. Standing, not lying: lying on his back "
        "is where the right hip clicked at about 45 degrees (finding #4)."
    ),
    progression="The rep-range rule adds one unit.",
    regression="A click at the right hip → start the lift from less far behind you.",
)


# ─── The abs, and the hip airplane (last in the session, step 6 S4) ──────────

CABLE_CRUNCH = _ex(
    name="Lat-Pulldown Cable Crunch (Facing Away)",
    ex_type="reps",
    sets=3, reps=12, rest_seconds=60,
    equipment_type="cable", weight_kg=10.0,
    increment_size=CABLE_UNIT, increment_unit="unit", **ISOLATION_RANGE,
    mechanics=(
        "Sit on the lat-pulldown seat facing away from the machine, knees under the pad. Hold "
        "the bar or rope behind your head, hands beside your ears. Curl your ribs down toward "
        "your hips, rounding the upper back, and pull with the abs, not the arms; then return "
        "slowly until you sit upright and the abs are long. " + _EVERY_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "The upper abs (goal A, priority 1), to failure (his decision, 2026-10-14): "
        "tier_lists/abs.md, S; within the S tier picked by safety margin (approved "
        "2026-10-15). The stretch at the top is what puts it in S."
    ),
    progression="The rep-range rule adds one unit.",
    regression="The hip flexors take over → sit more upright at the start and curl less far.",
)

REVERSE_CRUNCH = _ex(
    name="Reverse Crunch (Ab Mat)",
    ex_type="reps",
    sets=3, reps=12, rest_seconds=60,
    mechanics=(
        "Lie on your back with an ab mat under your lower back, hands holding a bench or post "
        "behind your head, knees bent at a right angle above your hips, knees together and "
        "pointing up. Curl your hips up off the floor, bringing the knees toward your chest, "
        "then lower slowly until your hips touch down. Your knees stay above your hips the "
        "whole set; the legs do not kick. " + _EVERY_SET_TO_FAILURE + " Log the reps you did."
    ),
    biomechanical_focus=(
        "The lower abs (goal A, priority 1), to failure: tier_lists/abs.md, S. Knees kept "
        "above the hips: the right hip clicked lying on the back with the leg lowering "
        "through about 45 degrees (finding #4: the dead bug, 2026-07-08; the Thomas test, "
        "2026-10-05), a range this exercise never enters."
    ),
    progression="Every set past 15 → hold the top for one second.",
    regression="The lower back arches off the mat → curl less far.",
)

WOODCHOP = _ex(
    name="High-to-Low Cable Woodchop",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=12, rest_seconds=45,
    equipment_type="cable", weight_kg=5.0,
    increment_size=CABLE_UNIT, increment_unit="unit", **ISOLATION_RANGE,
    mechanics=(
        "Cable at the highest pulley, one handle. Stand side-on, feet wide, and hold the "
        "handle with both hands above the shoulder nearest the machine. Pull it down and "
        "across your body to the outside of the far knee, arms nearly straight, turning from "
        "the hips and the upper back together; then return slowly. Your lower back does not "
        "twist on its own. All the reps on one side, then the other. " + _EVERY_SET_TO_FAILURE
    ),
    biomechanical_focus=(
        "The sides of the abs (goal A), to failure: his words, 2026-10-15, 'lets go for "
        "something like a high to low woodchop instead'; tier_lists/abs_sides.md, A, the best "
        "tier there. The turn from the hips and the upper back is the rule for turning under "
        "load at L3-L5 (rules: 'woodchop')."
    ),
    progression="The rep-range rule adds one unit.",
    regression="You feel the turn in the lower back → turn less far.",
)

SIDE_PLANK = _ex(
    name="Side Plank with Hip Raises",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=12, rest_seconds=45,
    mechanics=(
        "Lie on your side on a mat, forearm under the shoulder, legs straight and stacked. "
        "Lift your hips until your body makes one straight line, then lower your hips toward "
        "the floor and lift them back up above the line. That is one rep. All the reps on one "
        "side, then the other. " + _EVERY_SET_TO_FAILURE + " The set ends when your hips can "
        "no longer lift above the line. Log the reps you did."
    ),
    biomechanical_focus=(
        "The sides of the abs (goal A), to failure: his pick, 2026-10-15, a side plank made "
        "harder with a hip raise; tier_lists/abs_sides.md, A. Lowering and lifting the hips "
        "is a side bend under body weight (rules: 'side plank with hip raise', caution)."
    ),
    progression="Every set past 15 → hold a 2 kg plate on the top hip.",
    regression="The support shoulder objects → do it from the knees.",
)

HIP_AIRPLANE = _ex(
    name="Hip Airplane (Weighted)",
    ex_type="reps",
    laterality="unilateral",
    sets=3, reps=10, rest_seconds=60,
    equipment_type="dumbbell", weight_kg=4.5,
    increment_size=DUMBBELL_KG, **COMPOUND_RANGE,
    mechanics=(
        "Hold one dumbbell behind your back in both hands, against the base of your back. "
        "Stand on one leg, knee slightly bent. Bow forward a little from the hip; your chest "
        "stays well up. Slowly turn your pelvis open, so the free hip turns up and away, as "
        "far as you can turn under control; then turn it back past the start, so the free hip "
        "turns forward and in. Open and back is one rep. Your standing knee and foot stay "
        "still and the kneecap points straight ahead: the turn happens at the standing hip. "
        "On the RIGHT leg, start with a small turn, and make it smaller at any click or snap "
        "in the groin or at the sit bone. All the reps on one leg, then the other. "
        + _EVERY_SET_TO_FAILURE + " The set ends when you lose your balance or can no longer "
        "turn under control."
    ),
    biomechanical_focus=(
        "The hip rotators and the pelvis twist he noticed on 2026-10-05 (finding #7). Kept by "
        "his choice over the prone cable hip rotation (tier_lists/hip_rotators.md, 2026-10-16: "
        "'I like the balance part of this as well as the rotation'), with a weight held behind "
        "the back and the compound range so the one rule adds weight. Slight bow: the right "
        "hip stays under 60 degrees of flexion (rules: 'hip airplane', key rule 7)."
    ),
    progression="The rep-range rule adds 2.25 kg (one dumbbell size).",
    regression="A click on the right → smaller turn; no click at a smaller turn is the range.",
)


# ─── At home on the core days (step 6, approved 2026-10-16) ─────────────────

NECK_STRETCH = _ex(
    name="Neck Working Stretch (Right)",
    ex_type="hold_reps",
    sets=2, reps_in_set=4, hold_seconds=10, rest_seconds=30,
    mechanics=(
        "Sit tall. Tilt your head to the left, ear toward the shoulder, until you feel a "
        "stretch on the right side of your neck. Put your right hand on the right side of "
        "your head. Push your head into the hand for 10 seconds at about a third of your "
        "effort; the hand stops it moving. Relax for 5 seconds and let the head sink a little "
        "further. Four pushes is one set."
    ),
    biomechanical_focus=(
        "The right side of the neck (goal B), strength at length: his choice, 2026-10-15, at "
        "home from 2026-10-16. Contract-relax and static stretching gain about the same range "
        "(Konrad et al. 2024); this one adds a strength part."
    ),
    progression="The stretch eases in the first push → tilt a little further at the start.",
    regression="Any tingling into the arm → stop; tilt less.",
)
HOME = (NECK_STRETCH,)


# ─── The ramp sets (step 7): one light set straight before its own lift ──────

def _ramp(name: str, lift: dict) -> dict:
    """A ramp set has no weight of its own: the training page shows about 60% of
    the lift's weight for the day (sessions.ramp_weight_kg), so it follows the
    lift as the rule raises it. Its name is the lift's name without an
    equipment tag, plus the role — "Romanian Deadlift (Ramp Set)", as Block B
    named it — so services/sessions.base_name reads the ramp and its lift as
    one station."""
    return _ex(
        name=name,
        ex_type="reps",
        sets=1, reps=6, rest_seconds=60,
        equipment_type=lift["equipment_type"], weight_kg=None,
        increment_size=lift["increment_size"], increment_unit=lift["increment_unit"],
        warmup=True,
        mechanics=(
            "One light set of six at the weight shown, the same movement as the working "
            "sets that follow."
        ),
        biomechanical_focus=(
            "His choice, 2026-10-16: 'Let's keep the ramp set it, I think it will help with "
            "injury prevention.' About 60% of the day's working weight. It counts toward no "
            "weekly dose and no strength estimate (warmup=True)."
        ),
        progression="Follows the lift's weight.",
        regression="Follows the lift's weight.",
    )


RDL_RAMP = _ramp("Romanian Deadlift (Ramp Set)", RDL)
HACK_RAMP = _ramp("Hack Squat (Ramp Set)", HACK_SQUAT)


# ─── The four sessions, as placed (goal_week.week(), see the docstring) ─────

SESSIONS: dict[str, list[dict]] = {
    "A": [PSOAS_MARCH, WALKING_LUNGE, SHOULDER_RELEASE, Y_RAISE, CHEST_PRESS, SHOULDER_PRESS,
          CROSSOVER, ADDUCTOR_MACHINE, CABLE_CRUNCH, HIP_AIRPLANE],
    "B": [PSOAS_MARCH, RDL_RAMP, RDL, HACK_RAMP, HACK_SQUAT, BACK_EXTENSION, ROW, LATERAL_RAISE,
          REVERSE_CRUNCH, HIP_FLEXION],
    "C": [PSOAS_MARCH, RDL_RAMP, RDL, BACK_EXTENSION, ROW, SHOULDER_RELEASE, Y_RAISE, CHEST_PRESS,
          CROSSOVER, ADDUCTOR_MACHINE, HIP_AIRPLANE],
    "D": [PSOAS_MARCH, WALKING_LUNGE, HACK_RAMP, HACK_SQUAT, BACK_EXTENSION, LEG_CURL, WOODCHOP,
          SIDE_PLANK, HIP_FLEXION],
}
#: The core sessions meet the weekly dose; D is the bonus.
CORE_LETTERS = ("A", "B", "C")
#: Weekday (Monday = 0) → session letter.
LETTER_BY_WEEKDAY = {0: "A", 1: "B", 3: "C", 4: "D"}
REST_WEEKDAYS = (2, 5)
FLEXIBILITY_WEEKDAY = 6


# ─── The test items ──────────────────────────────────────────────────────────

def _bunkie(name: str, position: str, focus: str) -> dict:
    return _ex(
        name=name,
        ex_type="hold",
        laterality="unilateral",
        sets=1, hold_seconds=40, rest_seconds=60,
        mechanics=(
            position + " Hold until the line breaks, then stop the clock; the 40 seconds "
            "shown is a reference, not a target. Time each side and enter the seconds you held."
        ),
        biomechanical_focus=(
            focus + " The timed plank test (his decision, 2026-10-16): week 1 and week 12, at "
            "the end of session A in place of that day's abs work. Held to the line breaking, "
            "never to the burn; the worse side counts."
        ),
        progression="A measurement: nothing to progress.",
        regression="A cramp or any back symptom → stop and enter the seconds you held.",
    )


PLANK_TEST = [
    _bunkie(
        "Bunkie — Posterior Power Line (Timed)",
        "Lie on your back with both heels on a bench or chair about 40 cm high, arms crossed on "
        "your chest. Lift your hips until shoulders, hips and heels make one straight line, "
        "then lift one leg off the bench and hold on the other.",
        "Glute max and the hamstrings on one leg.",
    ),
    _bunkie(
        "Bunkie — Anterior Power Line (Timed)",
        "Front support on your forearms with both feet on the bench, one straight line from "
        "shoulders to heels; the low back neither sags nor arches. Lift one leg a few "
        "centimetres and hold.",
        "The front of the trunk and the hip, held on a clock.",
    ),
    _bunkie(
        "Bunkie — Posterior Stabilizing Line (Timed)",
        "On your back, hips lifted, one heel on the bench with that knee straight and the toes "
        "pulled toward you. Lift the other leg and hold.",
        "The hamstring alone, at the sit-bone attachment (finding #2).",
    ),
    _bunkie(
        "Bunkie — Lateral Stabilizing Line (Timed)",
        "Side support on one forearm with both feet stacked on the bench, the body one "
        "straight line seen from the front. Lift the top leg and hold.",
        "The side of the hip (glute medius): one of the two lines the core hold score reads.",
    ),
    _bunkie(
        "Bunkie — Medial Stabilizing Line (Timed)",
        "Side support on one forearm with the TOP foot on the bench and the lower leg hanging "
        "free, the body one straight line. Hold; the inner thigh of the bench leg does the work.",
        "The adductors: the other line the core hold score reads.",
    ),
]

RIB_AND_PELVIS_TEST = _ex(
    name="Rib and Pelvis Test (Test)",
    ex_type="duration",
    sets=1, duration_minutes=10, rest_seconds=0,
    mechanics=(
        "Cold, before anything else today. Write each reading in the note. (1) Pelvis: lie on "
        "your back on a firm floor, legs straight, arms by your sides, and take five slow "
        "breaths. Fingertips on the bony point at the front of each hip: which one sits "
        "higher off the floor? Grade 0 (level), 1 (slight) or 2 (clear), and name the side. "
        "(2) Heel drive: same position. Press one heel into the floor for five seconds and "
        "rate the stretch at the front of that hip 0-10; then the other heel. (3) Ribs: stand "
        "in front of a mirror, shirt off, arms relaxed, and breathe out normally. Which side's "
        "lower ribs stick forward more? Grade 0-2 and name the side. (4) Thomas test: lie on "
        "your back with your hips at the end of a firm bed. Hug your left knee to your chest "
        "and let the right leg hang; note where the right thigh settles against the level of "
        "the bed, and any click. Then the other side. When you hug the right knee, keep it "
        "pointing straight up."
    ),
    biomechanical_focus=(
        "Finding #7's test (patient_profile), first observed 2026-10-05 and never graded: this "
        "is its baseline (week 1) and its re-read (week 12). His answer, 2026-10-16: week 1 and "
        "week 12, on the test Sunday morning. In week 1 it follows the flexibility retest, so "
        "the retest's three mornings stay identical."
    ),
    progression="A measurement: nothing to progress.",
    regression="Any symptom → stop and write what you have.",
)

#: Key Rule 6's measurement: the hip release came out of the sessions on
#: 2026-09-22 and comes back when this grade reads 2 or more on the right.
#: Block B read it on Wednesday, a rest day in this block, so it moves to the
#: Sunday morning, first and cold — PROPOSED 2026-10-16, his answer asked.
GRIP_GRADE = _ex(
    name="Upper Glute Grip Grade (Test)",
    ex_type="reps",
    laterality="unilateral",
    sets=1, reps=1, rest_seconds=0,
    mechanics=(
        "First thing, cold. Stand side-on to a wall corner and press the shelf of the upper "
        "outer hip, just below the crest, into it: one side, then the other. Grade what you "
        "feel 0-3: 0 nothing, 1 slight grip, 2 clear grip, 3 marked. Write both grades in the "
        "note, right first."
    ),
    biomechanical_focus=(
        "Key Rule 6: the release block was suspended on 2026-09-22 ('there isn't that much "
        "gripping anymore'), and a right grade of 2 or more brings it back (docs/hypothesis.md "
        "P12). The grade is what makes that a measurement rather than a feeling."
    ),
    progression="A measurement: nothing to progress.",
    regression="Grade 2 or more on the right → say so; the release comes back.",
)

FLEXIBILITY_RETEST = _ex(
    name="Flexibility Retest (Test)",
    ex_type="duration",
    sets=1, duration_minutes=20, rest_seconds=0,
    mechanics=(
        "Cold, before anything else today. Open Insights, then Flexibility, and run the test "
        "there; the readings are entered on that page. This entry keeps the time for it."
    ),
    biomechanical_focus=(
        "The 12-week flexibility retest (goal C), on three Sunday mornings, weeks 1-3, so the "
        "day-to-day spread is known before a number counts (his answer, 2026-10-16: 'Sunday "
        "morning before'). Sunday follows Saturday's rest: a retest is never the morning after "
        "leg work (his rule, 2026-08-07)."
    ),
    progression="A measurement: nothing to progress.",
    regression="Short of time → run it next Sunday rather than warm.",
)


# ─── The Sunday session: the flexibility prescription for the last reading ──

_DOSE_HOLD = re.compile(r"^(\d+) × (\d+) s$")
_DOSE_REPS = re.compile(r"^(\d+) × (\d+)( per side)?$")
_DOSE_ROUNDS = re.compile(r"^(\d+) rounds of (\d+) s contract, (\d+) s relax$")


def _stack_entry(item) -> dict:
    """One prescribed line as a plan exercise: the dose from the prescription,
    the how-to from the exercise library. Raises on a dose it cannot read, so a
    new stack cannot slip in with a guessed dose."""
    lib = _mech.exercise(item.exercise)
    if lib is None:
        raise ValueError(f"{item.exercise!r} is not in the exercise library")
    mechanics = f"{lib.position} {lib.movement} FEEL: {lib.feel} STOP: {lib.stop}"
    if item.note:
        mechanics += f" {item.note}"
    common = dict(
        name=lib.name, mechanics=mechanics,
        biomechanical_focus=(
            f"Goal C, the flexibility session: cluster_a_prescription pattern {FLEX_PATTERN} "
            f"(the battery of 2026-08-12), prescribed dose {item.dose}. {lib.note}"
        ),
        progression=lib.progress,
        regression=lib.stop,
    )
    if m := _DOSE_HOLD.match(item.dose):
        return _ex(ex_type="hold", sets=int(m[1]), hold_seconds=int(m[2]), rest_seconds=30, **common)
    if m := _DOSE_ROUNDS.match(item.dose):
        return _ex(ex_type="hold_reps", sets=1, reps_in_set=int(m[1]), hold_seconds=int(m[2]),
                   rest_seconds=int(m[3]), **common)
    if m := _DOSE_REPS.match(item.dose):
        return _ex(ex_type="reps", sets=int(m[1]), reps=int(m[2]), rest_seconds=45,
                   laterality="unilateral" if m[3] else "bilateral", **common)
    raise ValueError(f"{item.exercise!r}: cannot read the dose {item.dose!r}")


FLEX_STACK = [_stack_entry(i) for i in _rx.prescribe(FLEX_PATTERN).live_items]


# ─── The days ────────────────────────────────────────────────────────────────

def _with_plank_test(exercises: list[dict]) -> list[dict]:
    """Session A in a test week: the five timed lines in the place of the day's
    abs work (his decision, 2026-10-16), and the walking lunge out. The test
    puts the session over the 70-minute limit, and step 6's L3 then takes out
    the lowest-ranked exercise whose areas all keep their weekly minimum
    without it: the lunge (glute max and quads stay far above theirs).
    tests/test_goal_block.py checks both."""
    out: list[dict] = []
    for ex in exercises:
        if ex is CABLE_CRUNCH:
            out.extend(PLANK_TEST)
        elif ex is not WALKING_LUNGE:
            out.append(ex)
    return out


def _strength_day(letter: str, week: int) -> dict:
    exercises = list(SESSIONS[letter])
    objective = f"Session {letter} — Full Body (week {week})"
    if letter == "A" and week in TEST_WEEKS:
        exercises = _with_plank_test(exercises)
        objective = f"Session A — Full Body + Timed Plank Test (week {week})"
    return {
        "objective": objective,
        "phase": BLOCK_NAME,
        "session_rpe_target": SESSION_RPE_TARGET,
        "is_gym_session": True,
        "day_type": "main",
        # Key Rule 21's six-exercise cap is replaced on a full-body day by at
        # most 8 hard sets per area (sessions.session_shape_violations).
        "shape": "full_body",
        "session_letter": letter,
        "exercises": exercises,
        "home": list(HOME) if letter in CORE_LETTERS else [],
    }


def _rest_day(week: int) -> dict:
    return {
        "objective": f"Rest day (week {week})",
        "phase": BLOCK_NAME,
        "session_rpe_target": 0,
        "is_gym_session": False,
        "day_type": "rest",
        "exercises": [],
        "home": [],
    }


def _flexibility_day(week: int) -> dict:
    """The tests come first, cold, in a fixed order, so each one sits in the
    same conditions every time it runs: the grip grade (a few seconds of
    pressure, every Sunday), then the flexibility retest on its three mornings,
    then the rib and pelvis test. The retest goes before the rib and pelvis
    test because its own rule is that passive work loosens tissue for an hour
    or more, and the Thomas test is passive."""
    tests = [GRIP_GRADE] + ([FLEXIBILITY_RETEST] if week in FLEX_RETEST_WEEKS else []) \
        + ([RIB_AND_PELVIS_TEST] if week in TEST_WEEKS else [])
    objective = f"Flexibility — Adductors and Hip Rotators (week {week})"
    if len(tests) > 1:
        objective += " — test morning"
    return {
        "objective": objective,
        "phase": BLOCK_NAME,
        "session_rpe_target": 4,
        "is_gym_session": False,
        "day_type": "stretch",
        "session_kind": "flexibility",
        "exercises": tests + list(FLEX_STACK),
        "home": [],
    }


def _day(day: int) -> dict:
    week, weekday = (day - 1) // 7 + 1, (day - 1) % 7
    if weekday in LETTER_BY_WEEKDAY:
        return _strength_day(LETTER_BY_WEEKDAY[weekday], week)
    if weekday == FLEXIBILITY_WEEKDAY:
        return _flexibility_day(week)
    return _rest_day(week)


#: Day number (1 = the first Monday) → that day's content, 84 days.
PLAN_GOAL_BLOCK: dict[int, dict] = {d: _day(d) for d in range(1, WEEKS * 7 + 1)}
