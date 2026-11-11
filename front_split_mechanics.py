"""
front_split_mechanics.py — the front split: WHY. Limiters and the exercise library.

The athlete, 2026-11-11: "I want to change the mobility plan from the pancake to
the front split as the objective". His four answers the same day ("Yes, all
four"): the front split only (it replaces the side split and the pancake as the
flexibility goal); one cold test morning to find the weaker part first; this
plan written here from the blueprint's method, the tier lists and his record,
every exercise with its workflow record (goal_week.PICKS, Key Rule 25); and the
adductor machine stays in the strength sessions to the end of the block.

There is no source document for this skill like the Cluster A ones in
Input_files/. The blueprint (Input_files/flexibility_blueprint.md) names the
front split as skill 4, "one leg forward, one back", and gives the method: find
the lowest rung, isolate one structure by changing the one thing true of it
alone, measure passive against active, stack small isolated work first and the
skill last, and, for a hypermobile body, weight the work to the resisted end.
Its one line on the skill itself is the technique rule: "Front splits want the
hips square for long-term progress rather than a rotated cheat."

THE SAME THREE LAYERS AS CLUSTER A, ONE DIRECTION
-------------------------------------------------
    MECHANICS  (this file)                 why  — limiters and the exercise library
        |
    BATTERY    front_split_battery.py      how to test — slots, one pattern label out
        |
    PRESCRIPTION front_split_prescription.py  what to do — pattern in, stack out

This file holds NO TESTS and NO DOSES; tests/test_front_split.py checks it.

THE SIDE IS THE FRONT LEG
-------------------------
A front split has two sides, and the two legs do different jobs: the front leg
needs its hamstrings long with the knee straight, the back leg needs its hip
flexors long with the hip straight. "Left" means the left leg is in front: the
left hamstrings and the RIGHT hip flexors. The component tests name the leg
they test; the split names the leg in front (services/yoga.py's laterality
rule: the suffix names the front, worked leg).

WHAT HIS RECORD SAYS BEFORE ANY TEST, written down so a reading cannot be read
toward it: the hamstrings read 89° left and 86° right on the January 2025 gym
goniometry, "normal with no reserve" (flexibility_baselines.LEGACY_GYM_READINGS);
the sit-bone tightness of 2026-10-05 reads as the hamstring origin working short
on both sides (patient_profile finding #7); and the Thomas test of the same day
read the hip flexors normal and equal on both sides, warm. So the front leg is
the expected limiter (front_split_battery.EXPECTED_PATTERN).
"""

from __future__ import annotations

from cluster_a_mechanics import Exercise, Limiter
import flexibility_baselines as _fb

CLUSTER_KEY = "front_split"
CLUSTER_LABEL = "Front split"
SKILLS: tuple[str, ...] = ("front split",)


# ── limiters ─────────────────────────────────────────────────────────────────

LIMITERS: tuple[Limiter, ...] = (
    Limiter(
        key="front_hamstrings", label="Front leg: hamstrings",
        responds_to="Stretching with the knee straight and the back flat, then strength "
                    "at that length.",
        detail="The hamstrings cross both the hip and the knee, so a straight knee loads "
               "them and a bent knee slackens them. That is the isolation: a straight-leg "
               "raise reads them, and the knee-to-chest he rates 85-88/100 (2026-08-05) "
               "says the hip itself bends freely. His record reads normal length with no "
               "reserve (89/86°, January 2025) and the sit-bone tightness of 2026-10-05 as "
               "the hamstring origin working short.",
    ),
    Limiter(
        key="front_nerve", label="Front leg: the nerve behind it",
        responds_to="Nerve slides, never stretching. No stack is built for it.",
        detail="The sciatic nerve runs behind the hip and the knee and slides in its "
               "sheath rather than stretching. Pulling the toes toward the shin tensions "
               "it without changing the hamstrings' length, so a change at that moment is "
               "the nerve. No log has ever recorded a neural sign, and the right L5/S1 "
               "nerve exit is narrowed: an electric or burning sensation is a finding to "
               "stop and record, never a training variable (rules.py 'nerve glide').",
    ),
    Limiter(
        key="back_deep_hip_flexors", label="Back leg: deep hip flexors",
        responds_to="Stretching with the pelvis tucked, then strength at that length.",
        detail="Iliopsoas crosses the hip only. With the knee bent the two-joint "
               "front-of-thigh muscle is slack, so a hanging thigh reads the deep group "
               "alone (the Thomas test). Read normal and equal on 2026-10-05, warm; the "
               "front split test reads it cold. The psoas attaches along L1-L4, so its "
               "range comes from the hip and never from an arched lower back.",
    ),
    Limiter(
        key="back_front_thigh", label="Back leg: the front of the thigh",
        responds_to="Stretching with the knee bent and the pelvis tucked.",
        detail="Rectus femoris crosses the hip and the knee. With the thigh hanging, a "
               "short one straightens the knee and swings the foot forward, which is what "
               "the hanging-shin reading measures. Never measured on his record.",
    ),
    Limiter(
        key="square_hips", label="Square hips",
        responds_to="Technique drills, before volume.",
        detail="The two cheats of a front split are the back hip swinging open and the "
               "lower back arching. Both buy depth the hips did not give, and both move "
               "the load: the arch onto the L5/S1 retrolisthesis and the narrowed right "
               "foramen, the open hip onto the front of the hip joint. The blueprint: "
               "'Front splits want the hips square for long-term progress rather than a "
               "rotated cheat.'",
    ),
    Limiter(
        key="strength_at_length", label="Strength at length",
        responds_to="Active lifts, isometric holds for reps and slow lowering.",
        detail="Range he reaches with help and cannot reach under his own power is the "
               "hypermobile failure mode (Beighton 6/9): the passive-to-active gap is the "
               "number to move, not the passive value. The blueprint's adaptation for "
               "him weights the work to the resisted end.",
    ),
)

LIMITERS_BY_KEY: dict[str, Limiter] = {lim.key: lim for lim in LIMITERS}


# ── the exercise library ─────────────────────────────────────────────────────
#
# Written fresh for the front split (Key Rule 25): no exercise is copied from a
# block. The back-knee hover is his own specification of 2026-08-24, the source
# its workflow record names. Every how-to field is patient-facing and read on
# the floor mid-session: plain words, the body position stated, no hedging.

_A = _fb.ASSISTED
_U = _fb.UNASSISTED
_R = _fb.RESISTED

LIBRARY: tuple[Exercise, ...] = (
    # ── the front leg ───────────────────────────────────────────────────────
    Exercise("slr_lifts", "Straight-leg raise lifts", _R,
             ("strength_at_length", "front_hamstrings"),
             note="Method 4, active lifts: the muscles that SHORTEN pull the leg into the "
                  "range, so it builds the range he can use. The hamstrings also relax "
                  "while the muscles opposite them work, which opens the next item. On "
                  "the right, active hip flexion turned out is the snapping trigger "
                  "(finding #4, Key Rule 7), so the kneecap points straight up.",
             position="Lie on your back on a mat, both legs straight, arms by your sides. "
                      "The leg you are not lifting stays straight and pressed into the mat "
                      "the whole set.",
             movement="Tighten the front of the thigh so the knee is straight, kneecap and "
                      "toes pointing straight up, not turned out. Lift the straight leg as "
                      "high as it goes under its own power, hold the top for 2 seconds, "
                      "then lower it over 3 seconds. Only your own hip muscles lift it; "
                      "nothing helps.",
             feel="Hard work at the front of the hip and the top of the thigh, and a "
                  "stretch at the back of the lifted thigh near the top.",
             stop="The other leg lifts or bends, the lifted knee bends, or your lower back "
                  "comes off the mat: the rep is over. A click or a snap at the front of "
                  "the right hip ends the set on that side.",
             progress="The top of the lift gets higher, the same angle the test reads with "
                      "the leg lifted under its own power."),
    Exercise("slr_lowers", "Straight-leg lowers from the top", _R,
             ("strength_at_length", "front_hamstrings"),
             note="Method 5, active lifts with eccentric overload: get to the top in the "
                  "easier shape (knee bent), then straighten and lower slowly, because "
                  "the muscle is stronger lowering than lifting. It loads the top of the "
                  "range the straight lift cannot reach yet.",
             position="Lie on your back on a mat, the leg you are not working straight and "
                      "pressed into the mat.",
             movement="Bend the working knee and bring it toward your chest with your hip "
                      "muscles, no hands. At the top, straighten the knee so the leg points "
                      "up as high as it will go. Then lower the straight leg to the floor "
                      "as slowly as you can, about 5 seconds, knee straight. Your hip "
                      "muscles slow the leg while gravity pulls it down.",
             feel="The front of the hip working hardest at the top and easing as the leg "
                  "comes down; a stretch at the back of the thigh at the top.",
             stop="The knee bends on the way down, or the leg drops faster than you can "
                  "slow it: the rep is over. A click at the front of the right hip ends "
                  "that side.",
             progress="The leg points higher at the top, and the lowering lasts the full "
                      "5 seconds."),
    Exercise("half_split_pir", "Half split contract-relax", _A, ("front_hamstrings",),
             note="Method 1, post-isometric relaxation: contract the stretched muscle, "
                  "then let go and sink, for more range where the front leg is short. The "
                  "back stays flat because a rounded reach is the forward-fold rule's "
                  "mechanism over the covered tears at L3/4 and L4/5.",
             position="Kneel on a mat with one knee down and the other leg straight out in "
                      "front, heel on the floor and toes pointing up. Put your hands on two "
                      "blocks or two stacks of books, one each side of the front leg. Start "
                      "with your hips stacked over the back knee and your back flat.",
             movement="Lean forward from the hips, back flat, until you feel the stretch "
                      "at the back of the front thigh. Press the front heel down into the "
                      "floor for about 5 seconds: the leg pushes and nothing moves. Then let "
                      "the effort go completely, breathe out, and lean a little further "
                      "forward for about 15 seconds, back still flat. That is one round.",
             feel="Effort at the back of the front thigh during the press, and a deeper, "
                  "easier stretch just after you let go.",
             stop="Your back rounds to reach further: come up until it is flat again. Keep "
                  "the front knee straight but never forced. Tingling or a burning line "
                  "down the leg ends the set; write it down.",
             progress="Your chest is closer to the front thigh, with a flat back, at the "
                      "start of each session."),

    # ── the back leg ────────────────────────────────────────────────────────
    Exercise("hip_flexor_tucked", "Kneeling hip flexor stretch, pelvis tucked", _A,
             ("back_deep_hip_flexors", "square_hips"),
             note="The deep hip flexors with the knee bent, so the front-of-thigh muscle "
                  "is slack. The tuck does the stretching: it tips the pelvis back so the "
                  "range comes from the hip, the opposite of the arched lower back that "
                  "buys false range over L5/S1.",
             position="Kneel on a mat or a cushion with one knee down and the other foot "
                      "flat in front, the front knee over the ankle. Torso tall, hands on "
                      "your hips.",
             movement="Tuck your tailbone under and squeeze the buttock of the back leg, so "
                      "your belt line tips up at the front. Keep the tuck and keep your ribs "
                      "down while you move your hips slowly forward until you feel the "
                      "stretch at the front of the back hip. Hold still and breathe slowly.",
             feel="A stretch at the front of the back hip and the top of that thigh.",
             stop="Your lower back arches or your ribs push forward: come back until the "
                  "tuck holds again. The stretch belongs in the hip, never the lower back.",
             progress="You hold the tuck with the hips further forward."),
    Exercise("front_thigh_kneeling", "Kneeling front-of-thigh stretch, heel to hand", _A,
             ("back_front_thigh",),
             note="Rectus femoris crosses the knee, so bending the back knee is what loads "
                  "it; the same tuck keeps the range out of the lower back.",
             position="Kneel as for the hip flexor stretch, the back knee on a folded "
                      "towel. Reach back with the hand on the back-leg side and hold the top "
                      "of the back foot or the ankle. If you cannot reach it, loop a towel "
                      "round the ankle and hold the towel.",
             movement="Tuck your tailbone under and keep your ribs down, as in the hip "
                      "flexor stretch. Then draw the back heel gently toward your buttock "
                      "and hold it there while you breathe. Bring the heel in only as far "
                      "as the tuck holds.",
             feel="A stretch along the front of the back thigh, from the hip to just above "
                  "the knee.",
             stop="Your lower back arches or the tuck lets go: let the heel out until the "
                  "tuck holds. Pain on the back kneecap from the floor: pad it more, or "
                  "stop.",
             progress="The heel comes closer to your buttock with the tuck held."),
    Exercise("knee_hover", "Back-knee hover hold", _R,
             ("strength_at_length", "back_deep_hip_flexors"),
             note="His own specification (2026-08-24): the front knee over the ankle and "
                  "the back knee HOVERING, never touching down, so that hip's flexors "
                  "carry the back leg while the hip sits straight: strength at length, "
                  "which is what keeps the range the stretches give.",
             position="A split stance: the front foot flat with the front knee over the "
                      "ankle, the back knee a hand's width above a cushion and the back heel "
                      "lifted. Torso tall; one hand lightly on a wall if you need it for "
                      "balance.",
             movement="Tuck your tailbone under and squeeze the buttock of the back leg so "
                      "the front of the back hip is long. Hold the hover still while you "
                      "breathe. The back knee never touches down during the hold.",
             feel="Work at the front of the back hip and in the front of both thighs.",
             stop="The back knee touches down, your lower back arches or your ribs push "
                  "forward: the hold is over.",
             progress="Longer clean holds; later, a slightly longer split stance."),

    # ── the split ───────────────────────────────────────────────────────────
    Exercise("split_slides", "Front split slides, hips square", _U, ("square_hips",),
             note="Method 10, a technique drill: it teaches the square-hip position at a "
                  "depth that costs little, before volume builds the rotated cheat.",
             position="Hands on two blocks or two stacks of books, one each side of your "
                      "hips. One leg forward with the heel on the floor; the back knee down "
                      "on a cushion. Both hip points face straight ahead.",
             movement="Slide the front heel forward and the back knee back a few "
                      "centimetres, then draw them back in, slowly, about 3 seconds each "
                      "way. Keep both hips facing straight ahead the whole time: the back "
                      "kneecap faces the floor and the back hip does not swing out. Your "
                      "hands take as much weight as you need.",
             feel="A moving stretch at the back of the front thigh and the front of the "
                  "back hip, with little effort.",
             stop="A hip turns out or your lower back arches: slide back in until both "
                  "hips face forward again. Never bounce.",
             progress="The slide reaches further with the hips still square."),
    Exercise("split_on_blocks", "Front split on blocks, hips square", _A,
             ("front_hamstrings", "back_deep_hip_flexors", "square_hips"),
             note="The skill itself, last in the stack, when the work before it has "
                  "opened each part. The blocks take the weight a hypermobile hip should "
                  "not hang on.",
             position="Hands on two blocks or two stacks of books, one each side of your "
                      "hips. The front leg straight with the heel on the floor and the toes "
                      "up; the back leg straight behind you with the toes tucked under. "
                      "Both hip points face straight ahead.",
             movement="Slide your legs apart slowly until you reach a firm stretch, with "
                      "your hands on the blocks taking the weight you need. Hold still at "
                      "that depth and breathe. Do not push deeper during the hold.",
             feel="A strong stretch at the back of the front thigh and the front of the "
                  "back hip.",
             stop="Your hips turn, your lower back arches or your back rounds: come up a "
                  "little until all three are right. A sharp pinch at the front of either "
                  "hip, or tingling down a leg, ends the set; write it down.",
             progress="Lower blocks over the weeks, and a longer gap between your front "
                      "heel and your back toes with the hips square, the same distance the "
                      "test reads."),
    Exercise("split_heel_press", "Front split heel-press holds", _R,
             ("strength_at_length",),
             note="Methods 2 and 3, isometric holds for reps at depth: short presses go "
                  "deeper than one long hold because fatigue does not build mid-position, "
                  "and they make the depth strong rather than only reached.",
             position="The front split on blocks, hips square, at about three quarters of "
                      "your deepest depth.",
             movement="Press the front heel down into the floor and drag the back toes "
                      "toward the front foot, as if pulling your legs together, at about "
                      "half effort for 3 seconds. Nothing moves. Relax for 3 seconds. Each "
                      "press is one rep.",
             feel="Work at the back of the front thigh and the front of the back hip, "
                  "inside the stretch.",
             stop="Your hips turn or your lower back arches during a press: ease the effort "
                  "or come up. Shaking you cannot control ends the set.",
             progress="Each press starts a little deeper, at the same effort."),
)

LIBRARY_BY_KEY: dict[str, Exercise] = {e.key: e for e in LIBRARY}
LIBRARY_BY_NAME: dict[str, Exercise] = {e.name: e for e in LIBRARY}
DEFERRED: tuple[Exercise, ...] = tuple(e for e in LIBRARY if e.deferred_until)


def exercise(key_or_name: str) -> Exercise | None:
    """An exercise by key or by its exact name; None when it is not in the library."""
    return LIBRARY_BY_KEY.get(key_or_name) or LIBRARY_BY_NAME.get(key_or_name)
