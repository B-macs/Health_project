"""The goal system's week — DRAFT, the cards that services/placement.py places.

docs/training/goal_system.md, steps 3-6. Every card is a pick made in step 5
(the tier lists, his decisions) with the dose of steps 3 and 4: 3 working sets,
and the number of days its areas need to reach their weekly minimum. Changing a
pick means changing a card here; the week is then placed again by the rules,
never by hand. `python scripts/draft_week.py` prints it.

DRAFT until he approves step 6. Open on 2026-10-16: the back and chest picks
(the single-arm dumbbell row, the machine chest press), the prone Y raise's
effort before a press, the adductor ladder's move off the gym days, and how the
sessions reach the 60-minute target (70 is the limit): the ramp sets, the neck
work and the holds are the parts that can leave the gym sessions.
"""
from services.placement import Card, WeekSpec

#: Strength days A-D (approved 2026-10-16: Monday, Tuesday, Thursday, Friday;
#: Wednesday and Saturday rest; Sunday the flexibility day).
DAYS = ("Mon", "Tue", "Thu", "Fri")
LETTERS = {"Mon": "A", "Tue": "B", "Thu": "C", "Fri": "D"}
IN_A_ROW = frozenset({("Mon", "Tue"), ("Thu", "Fri")})

#: Step 3, weekly hard sets (priority 1: 10; priority 2 and the rest: 6). The
#: hip rotators' 6 is the hip airplane's 3 x max on two days.
MINIMUMS = {
    "glute max": 10, "abs": 10, "deep back": 10, "hamstrings": 10,
    "quads": 6, "chest": 6, "back": 6, "press muscles": 6, "shoulder-blade muscles": 6,
    "side delts": 6, "rear delts": 6,
    "hip rotators": 6, "hip flexors": 6, "adductors": 6,
}

SPEC = WeekSpec(days=DAYS, in_a_row=IN_A_ROW, minimums=MINIMUMS)

#: The press block (step 6, 2026-10-16): the release only before a press, the
#: Y raise straight after the release. Two days not in a row.
PRESS_DAYS = ("Mon", "Thu")

CARDS = [
    # warm-up (step 7 decides its final content)
    Card("Standing Psoas March", sets=2, reps=20, rest_seconds=20, laterality="alternating",
         section="warmup", fixed_days=DAYS),
    Card("90/90 Hip Lift", sets=2, reps=5, rest_seconds=20, section="warmup", fixed_days=DAYS),
    Card("Neck Working Stretch (Right)", sets=2, type="hold_reps", reps=None, hold_seconds=10,
         reps_in_set=4, rest_seconds=30, section="warmup", fixed_days=("Mon", "Tue", "Thu")),
    # the press block
    Card("Pec & Scar Release (Right)", sets=2, type="hold", reps=None, hold_seconds=60,
         rest_seconds=15, section="block", fixed_days=PRESS_DAYS),
    Card("Prone Y-Raise (Scapular)", area="shoulder-blade muscles", rest_seconds=45,
         section="block", fixed_days=PRESS_DAYS),
    Card("Machine Shoulder Press", area="press muscles", second="side delts", reps=8,
         equipment_type="machine", kind="compound", demand=2, fixed_days=PRESS_DAYS, is_press=True),
    Card("Machine Chest Press", area="chest", second="press muscles", equipment_type="machine",
         kind="compound", demand=2, fixed_days=PRESS_DAYS, is_press=True),
    # the lifts
    Card("Hack Squat", area="quads", second="glute max", equipment_type="machine",
         kind="compound", demand=3, pattern="knee", ramp=True),
    Card("Walking Lunge (DB)", area="glute max", second="quads", equipment_type="dumbbell",
         laterality="unilateral", kind="compound", demand=3, priority=1, pattern="knee"),
    Card("Romanian Deadlift (DB)", area="hamstrings", second="glute max", equipment_type="dumbbell",
         kind="compound", demand=3, priority=1, pattern="hip", ramp=True),
    Card("Seated Leg Curl", area="hamstrings", reps=12, rest_seconds=75, equipment_type="machine",
         priority=1, pattern="hip"),
    Card("45° Back Extension", area="deep back", second="glute max", reps=12, rest_seconds=75,
         equipment_type="machine", kind="compound", demand=2, priority=1, days=4),
    Card("Single-Arm DB Row", area="back", second="shoulder-blade muscles", rest_seconds=60,
         equipment_type="dumbbell", laterality="unilateral", kind="compound", demand=2),
    Card("Reverse Cable Crossover", area="rear delts", reps=15, rest_seconds=45, equipment_type="cable"),
    Card("Cable Lateral Raise", area="side delts", reps=15, rest_seconds=45, equipment_type="cable",
         laterality="unilateral"),
    # the abs rotate, one a day, in rank order
    Card("Lat-Pulldown Cable Crunch (Facing Away)", area="abs", reps=12, rest_seconds=60,
         equipment_type="cable", priority=1, section="last", rotation="abs"),
    Card("Reverse Crunch (Ab Mat)", area="abs", reps=12, rest_seconds=60, priority=1,
         section="last", rotation="abs"),
    Card("High-to-Low Cable Woodchop", area="abs", reps=12, rest_seconds=45, equipment_type="cable",
         laterality="unilateral", priority=1, section="last", rotation="abs"),
    Card("Side Plank with Hip Raises", area="abs", reps=12, rest_seconds=45, laterality="unilateral",
         priority=1, section="last", rotation="abs"),
    # holds last
    Card("Hip Airplane", area="hip rotators", reps=6, rest_seconds=60, laterality="unilateral",
         section="last"),
    Card("End-Range Psoas Isometric", area="hip flexors", type="hold_reps", reps=None,
         hold_seconds=5, reps_in_set=4, rest_seconds=45, laterality="unilateral", section="last"),
]

#: Off the gym days (proposed 2026-10-16, for his approval): the adductor
#: ladder on Wednesday and on the Sunday flexibility day. It needs no gym, and
#: the adductors are the flexibility goal's blocker. Kept in the gym it puts
#: two sessions 2-3 minutes over the 70-minute limit.
OFF_GYM = {"Adductor Ladder (current rung)": {"area": "adductors", "sets": 3, "days": ("Wed", "Sun")}}
EXTRA_SETS = {v["area"]: v["sets"] * len(v["days"]) for v in OFF_GYM.values()}
EXTRA_DAYS = {v["area"]: len(v["days"]) for v in OFF_GYM.values()}
