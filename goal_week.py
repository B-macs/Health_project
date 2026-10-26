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
from dataclasses import dataclass, replace

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
#: the hip airplane's 3 sets on two days; the adductors' 6 is the adductor
#: machine's 3 sets on two days (the ladder at home until 2026-10-16).
REQUIRED = {
    "glute max": 6, "abs": 6, "deep back": 6, "hamstrings": 6,
    "quads": 4, "chest": 4, "back": 4, "press muscles": 4, "shoulder-blade muscles": 4,
    "side delts": 4, "rear delts": 4,
    "hip rotators": 6, "hip flexors": 3, "adductors": 6,
}
MINIMUMS = REQUIRED

#: Every area on 2 or more days (step 3), with one exception: the hip flexors'
#: 3 required sets are one appearance, so the core trains them on one day and
#: the bonus gives the second (the daily psoas march works them too). APPROVED
#: 2026-10-16 ("Approved all recommendations").
MIN_DAYS = {"hip flexors": 1}

SPEC = WeekSpec(days=CORE_DAYS, in_a_row=frozenset({("Mon", "Tue")}), minimums=REQUIRED,
                min_days=MIN_DAYS)

#: The press days: the right-shoulder release, then the Y raise (stopping 1-2
#: reps short of failure there, approved 2026-10-16), straight before a press.
PRESS_DAYS = ("Mon", "Thu")

#: The warm-up (step 7, 2026-10-16): the 15-minute walk to the gym is the raise,
#: then the psoas march; the ramp sets sit on their lifts. The 90/90 hip lift was
#: carried over from Block B without being checked and is OUT (athlete,
#: 2026-10-16: "It doesnt warm up anything and the evidence it fixes the issue
#: is weak") — the abs work covers the lower ribs.
WARMUP = [
    Card("Standing Psoas March", sets=2, reps=20, rest_seconds=20, laterality="alternating",
         section="warmup", fixed_days=CORE_DAYS),
]
RELEASE = Card("Pec & Scar Release (Right)", sets=2, type="hold", reps=None, hold_seconds=60,
               rest_seconds=15, section="block", fixed_days=PRESS_DAYS)
#: The shoulder-blade pick after the release (step 8's check, approved 2026-10-16:
#: "1 yes"): the single-arm cable Y raise in place of the prone Y raise.
Y_RAISE = Card("Single-Arm Cable Y Raise", area="shoulder-blade muscles", reps=12, rest_seconds=45,
               equipment_type="cable", laterality="unilateral", section="block",
               fixed_days=PRESS_DAYS)

SHOULDER_PRESS = Card("Machine Shoulder Press", area="press muscles", second="side delts", reps=8,
                      equipment_type="machine", kind="compound", demand=2, is_press=True,
                      fixed_days=("Mon",))
CHEST_PRESS = Card("Machine Chest Press", area="chest", second="press muscles",
                   equipment_type="machine", kind="compound", demand=2, is_press=True,
                   fixed_days=PRESS_DAYS)
HACK = Card("Hack Squat", area="quads", second="glute max", equipment_type="machine",
            kind="compound", demand=3, ramp=True, days=1, pattern="knee")
#: One set is both legs, one stride after the other (his note, 2026-10-22:
#: "walking lunge you walk so you do both right and left at the same time").
LUNGE = Card("Walking Lunge (DB)", area="glute max", second="quads", equipment_type="dumbbell",
             laterality="alternating", kind="compound", demand=3, priority=1, days=1, pattern="knee")
RDL = Card("Romanian Deadlift (DB)", area="hamstrings", second="glute max", equipment_type="dumbbell",
           kind="compound", demand=3, priority=1, ramp=True, days=2)
CURL = Card("Seated Leg Curl", area="hamstrings", reps=12, rest_seconds=75, equipment_type="machine",
            priority=1, days=1)
BACK_EXT = Card("45° Back Extension", area="deep back", second="glute max", reps=12, rest_seconds=75,
                equipment_type="machine", kind="compound", demand=2, priority=1, days=2)
ROW = Card("Single-Arm DB Row", area="back", second="shoulder-blade muscles", rest_seconds=60,
           equipment_type="dumbbell", laterality="unilateral", kind="compound", demand=2, days=2)
#: One arm at a time (his gym, 2026-10-22: "Reverse cross over cable can only be
#: done single hand"), and 15 s rest after both arms (his answer, 2026-10-22):
#: each arm rests while the other works, and session C stays under 70 minutes.
CROSSOVER = Card("Reverse Cable Crossover", area="rear delts", reps=15, rest_seconds=15,
                 equipment_type="cable", laterality="unilateral", days=2)
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
#: Kept by his choice over the prone cable hip rotation (step 8's check,
#: 2026-10-16: "we can add weight to this by holding it around the back but I
#: like the balance part of this as well as the rotation"): a weight held behind
#: the back, and the rep range of a compound lift. Its own name, so the
#: weighted lift starts its own history: Block B's "Hip Airplane" was body
#: weight at 5-6 reps and is a warm-up item there (sessions.PREPARATION_NAMES).
AIRPLANE = Card("Hip Airplane (Weighted)", area="hip rotators", reps=10, rest_seconds=60,
                equipment_type="dumbbell", laterality="unilateral", section="last", days=2)
#: The hip-flexor pick (step 8's check, approved 2026-10-16: "3 yes"): strength
#: with the hip flexors long, done standing — lying on the back is where the
#: right hip clicked (finding #4).
HIP_FLEXION = Card("Standing Cable Hip Flexion", area="hip flexors", reps=12, rest_seconds=45,
                   equipment_type="cable", laterality="unilateral", section="last", days=1)
#: The adductor pick (step 8's check, approved 2026-10-16: "4 yes the gym has the
#: machine"): knees bent, starting wide under load, in place of the ladder at home.
ADDUCTOR = Card("Adductor Machine (Seated)", area="adductors", reps=12, rest_seconds=60,
                equipment_type="machine", days=2)

#: The core cards: each runs on the days its areas need for the REQUIRED dose.
CARDS = WARMUP + [RELEASE, Y_RAISE, SHOULDER_PRESS, CHEST_PRESS, HACK, LUNGE, RDL, BACK_EXT,
                  ROW, CROSSOVER, LATERAL, ADDUCTOR, CRUNCH, REVERSE_CRUNCH, AIRPLANE, HIP_FLEXION]

#: The drop order (approved 2026-10-16), as the bonus session reads it: goal A's
#: priority areas, then the hip work, then the gate-1 main lifts, then goal B.
#: The abs take their next picks; the hip airplane's dose stays at two days.
BONUS_ORDER = [RDL, BACK_EXT, LUNGE, CURL, WOODCHOP, SIDE_PLANK, HIP_FLEXION, HACK, SHOULDER_PRESS,
               CHEST_PRESS, ROW, Y_RAISE, CROSSOVER, LATERAL, ADDUCTOR]

#: Off the gym days: nothing since 2026-10-16. The adductor ladder (Wednesday and
#: Sunday at home) was replaced by the adductor machine in the gym sessions.
OFF_GYM: dict = {}

#: At home, on the core days (approved 2026-10-16): the neck working stretch,
#: 2 sets of 4 efforts (10 s on, 5 s off). It trains no required area, and
#: doing it at home brings Tuesday and Thursday back toward the 60-minute target.
HOME = {"Neck Working Stretch (Right)": {"sets": 2, "dose": "4 efforts of 10 s, 5 s off",
                                         "days": CORE_DAYS}}
EXTRA_SETS = {v["area"]: v["sets"] * len(v["days"]) for v in OFF_GYM.values()}
EXTRA_DAYS = {v["area"]: len(v["days"]) for v in OFF_GYM.values()}


# ─── The workflow record — no exercise enters the block by copying ──────────
#
# The athlete, 2026-10-16: "Can you ensure that there is never copying, it needs
# to run through the workflow. If I ask for a exercise there needs to be reasons
# for to and goals attached, and even then it can be overwritten with a better
# exercise to get the same goal quicker." It followed the 90/90 hip lift, which
# reached this week by being copied from Block B's warm-up. Every exercise in the
# week, at home and off the gym days has a record here, and
# tests/test_workflow_picks.py fails on one that does not.

@dataclass(frozen=True)
class Pick:
    """Why one exercise is in the block.

    goal       "A" (hips and back, the main goal), "B" (the press), "C"
               (flexibility) or "warm-up"; several are comma-separated.
    area, job  the step-2 area it trains, and its job there.
    reason     why this exercise, in plain words.
    source     where the pick came from: a tier-list file and the exercise's
               tier, or his words with their date.
    listed_as  the exercise's name in its tier-list file ("" without one).
    better     how it was checked against a better exercise for the same goal;
               None = not checked yet. The block is not registered while any
               pick is unchecked (his rule: even his own picks can be replaced).
    """

    goal: str
    area: str
    job: str
    reason: str
    source: str
    listed_as: str = ""
    better: str | None = None


_TIER_FIRST = "step 5: the best tier in its list that passes the five filters"

def _flexibility_test_names() -> tuple[str, ...]:
    """The retest's entries, one per test of the battery, named as goal_block
    names them (WP-33); tests/test_goal_block.py keeps the two equal."""
    import cluster_a_battery as cab
    return tuple(f"Flexibility Test: {cab.TESTS[k].label} (Test)" for k in cab.AVAILABLE_TESTS)


PICKS: dict[str, Pick] = {
    "Standing Psoas March": Pick(
        "warm-up", "hip flexors", "warm-up",
        "Opens every strength session: it stretches and wakes up the psoas.",
        "his words, 2026-10-14: 'required to stretch and wake up that muscle'; 2026-09-22: "
        "'I feel more of stretch from that than any other stretch'",
        better="checked 2026-10-16: no warm-up drill is shown better than another for the hip "
               "flexors; a leg swing (a swing) and a held hip-flexor stretch (passive end range) "
               "are out by his hypermobility rule; kept"),
    "Ramp set": Pick(
        "warm-up", "the lift that follows", "warm-up",
        "One light set straight before the Romanian deadlift and the hack squat.",
        "his words, 2026-10-16: 'Let's keep the ramp set it, I think it will help with injury "
        "prevention'",
        better="checked 2026-10-16: no trial shows a warm-up set prevents injury in weight "
               "training, and at 8-12 reps it adds nothing to the working sets (warm-up review "
               "§1.4); kept by his choice"),
    "Pec & Scar Release (Right)": Pick(
        "B", "front of the right shoulder", "range",
        "Releases the front of the right shoulder straight before a chest or shoulder press.",
        "physiotherapist, 2026-08-10; his words, 2026-10-16: 'The shoulder release is only needed "
        "when doing chest presses or shoulder press. It's to release the area before working on it'",
        better="checked 2026-10-16: the corner and doorway chest stretches take the right arm "
               "behind the body, past his measured right-arm limit (20 cm against 40 cm, "
               "2026-08-13); rolling and pressure gain range for a short time, about as much as "
               "stretching (Wilke et al. 2020), which is how he uses it; kept"),
    "Single-Arm Cable Y Raise": Pick(
        "B", "shoulder-blade muscles", "strength and size",
        "Back-muscle work straight after the release, before the press, one arm at a time; "
        "1-2 reps short of failure.",
        "tier_lists/shoulder_blades.md #5, A (the decider's list); his decision, 2026-10-15: "
        "release, then back-muscle activation",
        listed_as="Single-arm cable Y raise",
        better="checked 2026-10-16: the S rows and the face pull end with the arm behind the body, "
               "where his right arm stops early; the scapular pulldowns load pec minor; it "
               "replaced the prone Y raise (B) — approved 2026-10-16 ('1 yes')"),
    "Machine Shoulder Press": Pick(
        "A, B", "press muscles", "strength and size",
        "Gate-1 main lift and the press goal's training, on a machine (his machine-only rule).",
        "tier_lists/shoulders.md #8, A+ — the list's best for the front delts",
        listed_as="Machine shoulder press",
        better=_TIER_FIRST + "; the S tiers above it train the side and rear delts, which have "
               "their own picks"),
    "Machine Chest Press": Pick(
        "A, B", "chest", "strength and size",
        "Gate-1 main lift; a press, because the chest is a main lift.",
        "tier_lists/chest.md #4, S (the decider's list); approved 2026-10-16",
        listed_as="Machine chest press",
        better=_TIER_FIRST + "; the S press confirmed in his gym"),
    "Hack Squat": Pick(
        "A", "quads", "strength and size",
        "Gate-1 main lift for the legs, on a machine (his machine-only rule).",
        "tier_lists/quads.md #6, S — named the list's best",
        listed_as="Hack squat",
        better=_TIER_FIRST + "; the pendulum squat is also S, and the list names the hack squat best"),
    # The hack squat's swap when its machine is in use (goal_block.ALTERNATIVES, WP-28).
    "V Squat": Pick(
        "A", "quads", "strength and size",
        "The hack squat's place when its machine is in use: a squat machine with a back pad, "
        "the quads first and glute max second.",
        "his note, 2026-10-22: 'hack squat change to V squat'",
        listed_as="",
        better="Checked 2026-10-22 against tier_lists/quads.md: the pendulum squat (S) is not "
               "in his gym (his answer 9, 2026-10-22), and the 45° leg press (A) is a lower tier "
               "with less depth; the V squat keeps the hack squat's back-supported squat"),
    "Walking Lunge (DB)": Pick(
        "A", "glute max", "strength and size",
        "The glutes' best exercise, with the quads second; one set is both legs, as he "
        "walks (2026-10-22).",
        "tier_lists/glutes.md #16, S+ — best overall",
        listed_as="Walking lunge",
        better=_TIER_FIRST + "; the top of its list"),
    "Romanian Deadlift (DB)": Pick(
        "A", "hamstrings", "strength and size",
        "The best hip hinge, for the hamstrings and the lower glutes; dumbbells (his rule).",
        "tier_lists/glutes.md second list #1, S — the best hip hinge",
        listed_as="Romanian deadlift",
        better=_TIER_FIRST + "; the top hinge in both of its lists"),
    "Seated Leg Curl": Pick(
        "A", "hamstrings", "strength and size",
        "Hamstring isolation at length, in the bonus session.",
        "tier_lists/hamstrings.md #7, A; the two-list rule's trial clause (approved 2026-10-16)",
        listed_as="Seated leg curl",
        better="checked 2026-10-15: the list's S lying curl is ranked on feel; a 12-week trial "
               "found more hamstring growth with the seated curl (Maeo et al. 2021)"),
    "45° Back Extension": Pick(
        "A", "deep back", "strength and size",
        "Trains the deep back muscles, with the glutes second; back kept straight.",
        "tier_lists/deep_back.md, approved 2026-10-16; ranked S in tier_lists/glutes.md #23",
        listed_as="45° back extension",
        better=_TIER_FIRST + "; the only S-ranked deep-back exercise in his gym"),
    "Single-Arm DB Row": Pick(
        "A, B", "back", "strength and size",
        "Gate-1 main lift for the back; one arm at a time, so the left cannot do the right's work.",
        "tier_lists/back.md #9, S (the decider's list); approved 2026-10-16",
        listed_as="Single-arm dumbbell row",
        better=_TIER_FIRST + "; among the S rows his single-arm rule and known tolerance break "
               "the tie"),
    "Reverse Cable Crossover": Pick(
        "B", "rear delts", "strength and size",
        "Rear delts, through a long range, one arm at a time (his gym, 2026-10-22: "
        "'can only be done single hand').",
        "tier_lists/shoulders.md #21, S — best for the rear delts",
        listed_as="Reverse cable crossover",
        better=_TIER_FIRST + "; the list's best for the rear delts. Checked again for one arm "
               "at a time (2026-10-22) against the reverse pec deck sideways, one arm (#18, S): "
               "not better for the same goal, so the crossover stays"),
    "Cable Lateral Raise": Pick(
        "B", "side delts", "strength and size",
        "Side delts, with tension at the stretch.",
        "tier_lists/shoulders.md #13, S+ — best overall",
        listed_as="Cable lateral raise",
        better=_TIER_FIRST + "; the top of its list"),
    "Lat-Pulldown Cable Crunch (Facing Away)": Pick(
        "A", "abs", "strength and size",
        "Upper abs, to failure, at the end of the session.",
        "tier_lists/abs.md #30, S",
        listed_as="Lat-pulldown cable crunch, facing away",
        better=_TIER_FIRST + "; within the S tier, picked by safety margin (approved 2026-10-15)"),
    "Reverse Crunch (Ab Mat)": Pick(
        "A", "abs", "strength and size",
        "Lower abs, to failure, at the end of the session.",
        "tier_lists/abs.md #19, S",
        listed_as="Reverse crunch with an ab mat",
        better=_TIER_FIRST + "; within the S tier, picked by safety margin (approved 2026-10-15)"),
    "High-to-Low Cable Woodchop": Pick(
        "A", "abs", "strength and size",
        "The sides of the abs under load, to failure.",
        "his words, 2026-10-15 (tier_lists/abs.md): 'lets go for something like a high to low "
        "woodchop instead'",
        listed_as="woodchop",
        better="checked 2026-10-16 (tier_lists/abs_sides.md): A, the list's best tier (no S); "
               "within A the safety margin keeps it over the side bends; kept"),
    "Side Plank with Hip Raises": Pick(
        "A", "abs", "strength and size",
        "The sides of the abs, made harder with a hip raise, to failure.",
        "his pick, 2026-10-15 (tier_lists/abs.md): a side plank made harder with a hip raise",
        listed_as="side plank",
        better="checked 2026-10-16 (tier_lists/abs_sides.md): A, the list's best tier (no S); "
               "within A the safety margin keeps it over the side bends; kept"),
    "Hip Airplane (Weighted)": Pick(
        "A", "hip rotators", "strength and size",
        "Trains the pelvis twist he noticed on 2026-10-05: 3 x max, two days, not every day.",
        "his decision, 2026-10-14: hip airplane 3 x max, to failure, not every day",
        better="checked 2026-10-16 (tier_lists/hip_rotators.md): the prone cable hip rotation (S) "
               "ranks higher; kept by his choice — 'we can add weight to this by holding it "
               "around the back but I like the balance part of this as well as the rotation'"),
    "Standing Cable Hip Flexion": Pick(
        "A", "hip flexors", "strength at length",
        "Strength with the hip flexors long: the leg starts behind the body, under load.",
        "tier_lists/hip_flexors.md #2, S (the decider's list); his rule, 2026-08-24: 'more time "
        "on holds and strengthing to get the real benefits'",
        listed_as="Cable hip flexion from behind the body",
        better="checked 2026-10-16: it replaced the end-range psoas isometric (B), which worked "
               "the psoas at its shortest; standing, not lying — the bench-edge version is the "
               "Thomas-test position, where the right hip clicked; approved 2026-10-16 ('3 yes')"),
    "Neck Working Stretch (Right)": Pick(
        "B", "neck, right side", "strength at length",
        "Head tilted to the left, 10-second pushes into the hand, at home on the core days.",
        "his choice, 2026-10-15; at home from 2026-10-16",
        better="checked 2026-10-15: contract-relax and static stretching gain about the same range "
               "(Konrad et al. 2024), and this one adds a strength part"),
    "Adductor Machine (Seated)": Pick(
        "C", "adductors", "strength at length",
        "The flexibility goal's blocker, the adductors with the knees bent (21.5 cm against "
        "10 cm, 2026-08-12): strength from a wide start, in the tested position.",
        "tier_lists/adductors.md #1, S (the decider's list); step 2, goal C",
        listed_as="Adductor machine",
        better="checked 2026-10-16: it replaced the adductor ladder (best rung A); approved "
               "2026-10-16 ('4 yes the gym has the machine')"),

    # ── The block's measurements and its Sunday session (goal_block.py) ─────
    "Timed plank test": Pick(
        "A", "trunk and hips", "measurement",
        "The five Bunkie lines, each held until the line breaks, in week 1 and week 12; the "
        "lateral and medial lines feed the core hold score.",
        "his decision, 2026-10-16: the timed plank test in week 1 and week 12, at the end of "
        "session A in place of that day's abs work",
        better="a measurement: the protocol stays the same, so week 1 and week 12 compare"),
    **{name: Pick(
        "C", "the flexibility skills", "measurement",
        "One test of the 12-week flexibility retest, on three Sunday mornings, so the "
        "day-to-day spread is known before a number counts; one reading per entry (WP-33).",
        "his answers, 2026-10-14 ('three mornings once'), 2026-10-16 ('Sunday morning before') "
        "and 2026-10-26 ('Always split a retest into its individual items')",
        better="a measurement: the battery's own protocol")
       for name in _flexibility_test_names()},
    **{name: Pick(
        "C", "adductors and hip rotators", "range",
        f"Item {i} of the flexibility prescription for the last reading (pattern D: the "
        "adductors with the knees bent).",
        "cluster_a_prescription.py, pattern D, from the flexibility battery of 2026-08-12",
        better="checked 2026-10-16: the prescription chooses the stack from the battery's "
               "pattern; the retest in weeks 1-3 reads the pattern again, and a new pattern "
               "brings its own stack")
       for i, name in enumerate((
           "Tailor's pose, unloaded", "Frog rocks", "Butterfly PIR",
           "90/90 hip rotations with lift-offs", "Triangle side split, external-rotation cue"),
           start=1)},
}

#: The picks whose check is not closed. Step 8 checked all eight on 2026-10-16
#: (the files in docs/training/tier_lists/); for these four a better exercise
#: ranks higher and his decision is asked, so each stays open until it is
#: replaced or kept by his choice. tests/test_workflow_picks.py keeps this list
#: equal to the picks whose `better` is None, and refuses to let the block be
#: registered while it is not empty.
BETTER_CHECK_OPEN: tuple[str, ...] = ()


def pick_for(name: str) -> Pick | None:
    """The workflow record for an exercise name in the week; a ramp set reads
    the shared "Ramp set" record, and a Bunkie line the "Timed plank test"
    record."""
    if name.endswith("(Ramp Set)"):
        return PICKS.get("Ramp set")
    if name.startswith("Bunkie — ") and name.endswith("(Timed)"):
        return PICKS.get("Timed plank test")
    return PICKS.get(name)


def week() -> dict:
    """The full week: the three core sessions placed by the rules, then the
    bonus filled after them."""
    core = place(CARDS, SPEC)
    warm = [replace(c, fixed_days=()) for c in WARMUP]
    block = [replace(c, fixed_days=()) for c in (RELEASE, Y_RAISE)]
    candidates = [replace(c, fixed_days=(), pattern="", rotation="")
                  for c in BONUS_ORDER if c.name not in (RELEASE.name, Y_RAISE.name)]
    bonus = fill_bonus(core["Thu"], warm, candidates, block)
    return {**core, BONUS_DAY: bonus}
