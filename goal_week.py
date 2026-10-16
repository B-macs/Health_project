"""The goal system's week — the cards that services/placement.py places.

docs/training/goal_system.md, steps 3-6, as approved on 2026-10-16:

- **Three core sessions meet the REQUIRED weekly dose; the fourth is a bonus**
  (*"I'd like to aim for a 3 day week meets the required goal and a 4th day is
  a bonus"*). Required: priority-1 areas 6 hard sets a week on 2 days,
  priority-2 areas 4 counting half-sets, the hip flexors' strength-at-length
  work 3 — the evidence is docs/training/weekly_volume_minimum_2026-10-16.md.
- **The sessions run in order, A, B, C, then D**: a missed day moves the rest
  along, and gate 1 counts the 3 core sessions.
- **The bonus is filled in the drop order** (goal A's priority areas, then the
  hip work, then the gate-1 main lifts, then goal B), up to 60 minutes, never
  with a heavy lift from the day before.
- Every exercise has 3 working sets; 60 minutes is the target and 70 the limit.

Changing a pick means changing a card here; the week is then placed again by
the rules, never by hand. `python scripts/draft_week.py` prints it.
"""
from dataclasses import replace

from services.placement import Card, WeekSpec, fill_bonus, place

#: The usual week (approved 2026-10-16): strength Monday, Tuesday, Thursday and
#: Friday; Wednesday and Saturday rest; Sunday the flexibility day. A, B and C
#: are the core sessions, D the bonus.
CORE_DAYS = ("Mon", "Tue", "Thu")
BONUS_DAY = "Fri"
DAYS = CORE_DAYS + (BONUS_DAY,)
LETTERS = {"Mon": "A", "Tue": "B", "Thu": "C", "Fri": "D"}
IN_A_ROW = frozenset({("Mon", "Tue"), ("Thu", "Fri")})

#: The required weekly hard sets (approved 2026-10-16). The hip rotators' 6 is
#: the hip airplane's 3 x max on two days; the adductors' 6 is the ladder at home.
REQUIRED = {
    "glute max": 6, "abs": 6, "deep back": 6, "hamstrings": 6,
    "quads": 4, "chest": 4, "back": 4, "press muscles": 4, "shoulder-blade muscles": 4,
    "side delts": 4, "rear delts": 4,
    "hip rotators": 6, "hip flexors": 3, "adductors": 6,
}
MINIMUMS = REQUIRED

#: Every area on 2 or more days (step 3), with one exception: the hip flexors'
#: 3 required sets are one appearance, so the core trains them on one day and
#: the bonus gives the second (the daily psoas march works them too). OPEN for
#: his confirmation, 2026-10-16.
MIN_DAYS = {"hip flexors": 1}

SPEC = WeekSpec(days=CORE_DAYS, in_a_row=frozenset({("Mon", "Tue")}), minimums=REQUIRED,
                min_days=MIN_DAYS)

#: The press days: the right-shoulder release, then the Y raise (stopping 1-2
#: reps short of failure there, approved 2026-10-16), straight before a press.
PRESS_DAYS = ("Mon", "Thu")

WARMUP = [
    Card("Standing Psoas March", sets=2, reps=20, rest_seconds=20, laterality="alternating",
         section="warmup", fixed_days=CORE_DAYS),
    Card("90/90 Hip Lift", sets=2, reps=5, rest_seconds=20, section="warmup", fixed_days=CORE_DAYS),
]
NECK = Card("Neck Working Stretch (Right)", sets=2, type="hold_reps", reps=None, hold_seconds=10,
            reps_in_set=4, rest_seconds=30, section="warmup", fixed_days=CORE_DAYS)
RELEASE = Card("Pec & Scar Release (Right)", sets=2, type="hold", reps=None, hold_seconds=60,
               rest_seconds=15, section="block", fixed_days=PRESS_DAYS)
Y_RAISE = Card("Prone Y-Raise (Scapular)", area="shoulder-blade muscles", rest_seconds=45,
               section="block", fixed_days=PRESS_DAYS)

SHOULDER_PRESS = Card("Machine Shoulder Press", area="press muscles", second="side delts", reps=8,
                      equipment_type="machine", kind="compound", demand=2, is_press=True,
                      fixed_days=("Mon",))
CHEST_PRESS = Card("Machine Chest Press", area="chest", second="press muscles",
                   equipment_type="machine", kind="compound", demand=2, is_press=True,
                   fixed_days=PRESS_DAYS)
HACK = Card("Hack Squat", area="quads", second="glute max", equipment_type="machine",
            kind="compound", demand=3, ramp=True, days=1, pattern="knee")
LUNGE = Card("Walking Lunge (DB)", area="glute max", second="quads", equipment_type="dumbbell",
             laterality="unilateral", kind="compound", demand=3, priority=1, days=1, pattern="knee")
RDL = Card("Romanian Deadlift (DB)", area="hamstrings", second="glute max", equipment_type="dumbbell",
           kind="compound", demand=3, priority=1, ramp=True, days=2)
CURL = Card("Seated Leg Curl", area="hamstrings", reps=12, rest_seconds=75, equipment_type="machine",
            priority=1, days=1)
BACK_EXT = Card("45° Back Extension", area="deep back", second="glute max", reps=12, rest_seconds=75,
                equipment_type="machine", kind="compound", demand=2, priority=1, days=2)
ROW = Card("Single-Arm DB Row", area="back", second="shoulder-blade muscles", rest_seconds=60,
           equipment_type="dumbbell", laterality="unilateral", kind="compound", demand=2, days=2)
CROSSOVER = Card("Reverse Cable Crossover", area="rear delts", reps=15, rest_seconds=45,
                 equipment_type="cable", days=2)
LATERAL = Card("Cable Lateral Raise", area="side delts", reps=15, rest_seconds=45, equipment_type="cable",
               laterality="unilateral", days=1)
CRUNCH = Card("Lat-Pulldown Cable Crunch (Facing Away)", area="abs", reps=12, rest_seconds=60,
              equipment_type="cable", priority=1, section="last", pattern="abs", days=1)
REVERSE_CRUNCH = Card("Reverse Crunch (Ab Mat)", area="abs", reps=12, rest_seconds=60, priority=1,
                      section="last", pattern="abs", days=1)
WOODCHOP = Card("High-to-Low Cable Woodchop", area="abs", reps=12, rest_seconds=45, equipment_type="cable",
                laterality="unilateral", priority=1, section="last", days=1)
SIDE_PLANK = Card("Side Plank with Hip Raises", area="abs", reps=12, rest_seconds=45,
                  laterality="unilateral", priority=1, section="last", days=1)
AIRPLANE = Card("Hip Airplane", area="hip rotators", reps=6, rest_seconds=60, laterality="unilateral",
                section="last", days=2)
PSOAS_ISO = Card("End-Range Psoas Isometric", area="hip flexors", type="hold_reps", reps=None,
                 hold_seconds=5, reps_in_set=4, rest_seconds=45, laterality="unilateral",
                 section="last", days=1)

#: The core cards: each runs on the days its areas need for the REQUIRED dose.
CARDS = WARMUP + [NECK, RELEASE, Y_RAISE, SHOULDER_PRESS, CHEST_PRESS, HACK, LUNGE, RDL, BACK_EXT,
                  ROW, CROSSOVER, LATERAL, CRUNCH, REVERSE_CRUNCH, AIRPLANE, PSOAS_ISO]

#: The drop order (approved 2026-10-16), as the bonus session reads it: goal A's
#: priority areas, then the hip work, then the gate-1 main lifts, then goal B.
#: The abs take their next picks; the hip airplane's dose stays at two days.
BONUS_ORDER = [RDL, BACK_EXT, LUNGE, CURL, WOODCHOP, SIDE_PLANK, PSOAS_ISO, HACK, SHOULDER_PRESS,
               CHEST_PRESS, ROW, Y_RAISE, CROSSOVER, LATERAL]

#: Off the gym days: the adductor ladder on Wednesday and on the Sunday
#: flexibility day (it needs no gym, and the adductors are the flexibility
#: goal's blocker).
OFF_GYM = {"Adductor Ladder (current rung)": {"area": "adductors", "sets": 3, "days": ("Wed", "Sun")}}
EXTRA_SETS = {v["area"]: v["sets"] * len(v["days"]) for v in OFF_GYM.values()}
EXTRA_DAYS = {v["area"]: len(v["days"]) for v in OFF_GYM.values()}


def week() -> dict:
    """The full week: the three core sessions placed by the rules, then the
    bonus filled after them."""
    core = place(CARDS, SPEC)
    warm = [Card(c.name, sets=c.sets, reps=c.reps, rest_seconds=c.rest_seconds,
                 laterality=c.laterality, section="warmup") for c in WARMUP]
    block = [Card(c.name, area=c.area, sets=c.sets, type=c.type, reps=c.reps,
                  hold_seconds=c.hold_seconds, rest_seconds=c.rest_seconds, section="block")
             for c in (RELEASE, Y_RAISE)]
    candidates = [replace(c, fixed_days=(), pattern="", rotation="")
                  for c in BONUS_ORDER if c.name not in (RELEASE.name, Y_RAISE.name)]
    bonus = fill_bonus(core["Thu"], warm, candidates, block)
    return {**core, BONUS_DAY: bonus}
