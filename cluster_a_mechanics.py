"""
cluster_a_mechanics.py — Cluster A: WHY. Side split and pancake.

The machine-readable form of `Input_files/cluster_a_mechanics.md`, adapted for
this athlete on 2026-08-06. That document is the prose; this is what the code
reads. Where they disagree, the document is the source and this file is wrong.

THE LAYER RULE, WHICH IS ENFORCED BY A TEST
-------------------------------------------
Three layers, one direction:

    MECHANICS  (this file)  why  — limiters, and the exercise library
        ↓
    BATTERY    how to test  — four slots, one pattern label out
        ↓
    PRESCRIPTION  what to do  — pattern label in, ordered stack out

This file therefore contains NO TESTS and NO DOSES. It names what can stop
these skills and what tools exist; it never says how to measure yourself or how
many sets to do. tests/test_cluster_a.py fails if a dose or a pattern label
appears here, and fails if the Prescription names an exercise this file does
not define.

WHY THE TWO SKILLS ARE ONE CLUSTER
----------------------------------
Both abduct the hip against the adductor group, and both need the same forward
pelvic tilt to clear the joint. Training either moves the other — but they load
the group differently, so they are not interchangeable. The side split with a
straight knee is the gracilis tool; the pancake is the adductor magnus tool.
"""

from __future__ import annotations

from dataclasses import dataclass

import flexibility_baselines as _fb

CLUSTER_KEY = "a"
CLUSTER_LABEL = "Side split & pancake"
SKILLS: tuple[str, ...] = ("side split", "pancake")


# ── limiters ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Limiter:
    """One thing that can stop this cluster, and what it responds to."""
    key: str
    label: str
    responds_to: str
    detail: str


#: FIVE, not the source's four. The fifth is this athlete's dominant restriction
#: and the general set does not name it cleanly — the source treats the tilt as
#: a prerequisite you either have or don't, checked once, rather than as a thing
#: with components that need different work.
LIMITERS: tuple[Limiter, ...] = (
    Limiter(
        key="bone", label="Bone",
        responds_to="Orientation. Not trainable.",
        detail="The neck of the femur contacts the rim of the hip socket and stops you. "
               "Where that happens is individual — normal femoral inclination spans about "
               "20° between two healthy people — and forcing it causes joint microtrauma "
               "rather than progress. Two routes reach the same clearance: turning the leg "
               "out, or tilting the pelvis. Neither is more correct. For this athlete only "
               "the turn-out is available, because the tilt route means lumbar extension "
               "against an L5/S1 retrolisthesis and a narrowed right foramen.",
    ),
    Limiter(
        key="adductor_length", label="Adductor length",
        responds_to="Stretching, at the right leverage.",
        detail="Adductor magnus, longus, pectineus and gracilis. Gracilis is the one that "
               "changes the picture, because it is the ONLY adductor crossing the knee — so "
               "knee angle decides which part of the group is loaded. Straight knee puts "
               "gracilis under relatively greater stretch; a bent knee slackens it and "
               "shifts load to the rest. That is the crossing rule, and it is why length is "
               "tested at more than one leverage.",
    ),
    Limiter(
        key="end_range_strength", label="End-range strength",
        responds_to="Loaded work at depth.",
        detail="The side split is a heavy skill: the adductors support full bodyweight in a "
               "mechanically poor position. The consequence is the important part — the "
               "body will not allow a muscle to relax into a position it cannot support. "
               "End-range strength is not a goal running alongside flexibility; it is what "
               "PERMITS the flexibility.",
    ),
    Limiter(
        key="puller_strength", label="Puller strength",
        responds_to="Isolated strengthening of the antagonists.",
        detail="Something has to pull the legs apart. For the side split that is glute "
               "medius, minimus and TFL; if they cannot open the legs, the adductors do not "
               "release and the split stalls. Strength on one side gates relaxation on the "
               "other — a mechanism by which stretching fails, not merely a missing "
               "accessory. NOTE for this athlete: glute medius is listed as overactive and "
               "right-dominant, so it is released before it is strengthened.",
    ),
    Limiter(
        key="seated_tilt", label="Seated tilt capacity",
        responds_to="Two different fixes — see components.",
        detail="ADDED FOR THIS ATHLETE and his dominant restriction. The pelvis will not "
               "rotate forward in sitting. The lumbar rounding everyone notices is the "
               "COMPENSATION, not the problem: he rounds because the tilt is unavailable. "
               "That distinction decides the whole programme — the answer is not to fold "
               "more carefully, it is to build the tilt until there is no reason to "
               "compensate. It has two components and they need different work.",
    ),
)

LIMITERS_BY_KEY: dict[str, Limiter] = {l.key: l for l in LIMITERS}


@dataclass(frozen=True)
class TiltComponent:
    key: str
    label: str
    evidence: str
    fix: str


#: The two halves of limiter 5. They map exactly onto the battery's slot 2
#: Range/Production split, which is why that slot is the operative one here and
#: why the expected pattern is F or G.
TILT_COMPONENTS: tuple[TiltComponent, ...] = (
    TiltComponent(
        key="hamstring_reserve", label="Hamstring reserve",
        evidence="89° left / 86° right on the January 2025 goniometry, called Normal. But "
                 "long-sitting upright with a straight knee is already about 90° of hip "
                 "flexion — so he is at the limit JUST SITTING UP, before any fold begins. "
                 "This is not short hamstrings; it is normal length with no reserve.",
        fix="Raise the ceiling by hinging with a flat back, never folding. Or sit above it: "
            "elevation removes the requirement entirely.",
    ),
    TiltComponent(
        key="hip_flexor_production", label="Hip flexor production",
        evidence="Untested. The source's own line: 'you need end-range hip flexor strength "
                 "to pull yourself into the anterior tilt.'",
        fix="Resisted work — lift-offs from a flat back.",
    ),
)


# ── the exercise library ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Exercise:
    """One tool. NO DOSE — sets and reps belong to the Prescription.

    `spectrum` places it on the assisted↔resisted line so a stack can be built
    by zone rather than by name. `adapted_from` records a substitution made for
    this athlete, and `reverts_when` the condition that undoes it: these are
    holds on evidence, not permanent deletions, in the same idiom as
    biometrics.HRV_GARMIN_HOLD.
    """
    key: str
    name: str
    spectrum: str
    limiters: tuple[str, ...]
    #: The WHY — mechanism and rationale. Background: correct, but not what the
    #: athlete needs mid-session. Anatomy is allowed here and only here.
    note: str = ""
    #: THE HOW, five fields, all patient-facing and all mandatory (a test fails
    #: on any empty one). Added 2026-08-07 on the athlete's direction: knowing
    #: why is assumed correct in the background — understanding HOW is the part
    #: the user actually needs, and the notes alone did not provide it.
    position: str = ""      #: where your body is — standing/sitting/lying, legs, equipment
    movement: str = ""      #: what you actually do, incl. what resists you and rep/hold shape
    feel: str = ""          #: what you should feel, and where
    stop: str = ""          #: what ends the set or voids the rep
    progress: str = ""      #: the thing that should move, so effort has a target
    adapted_from: str = ""
    reverts_when: str = ""
    deferred_until: str = ""

    @property
    def adapted(self) -> bool:
        return bool(self.adapted_from)

    @property
    def available(self) -> bool:
        return not self.deferred_until


_A = _fb.ASSISTED
_U = _fb.UNASSISTED
_R = _fb.RESISTED

LIBRARY: tuple[Exercise, ...] = (
    # ── adductors, fully bent knee ──────────────────────────────────────────
    Exercise("frog_rocks", "Frog rocks", _A, ("adductor_length",),
             note="Deep flexion with abduction, floor-supported and self-limited.",
             position="On all fours on a mat, knees spread wide, feet in line with the "
                      "knees, shins flat on the floor. Drop to your forearms if that is "
                      "more comfortable.",
             movement="Rock your hips slowly backward toward your heels until the stretch "
                      "arrives, pause for a breath, rock forward again. Small, slow rocks "
                      "— the floor carries your weight the whole time.",
             feel="A stretch along the inside of both thighs, deepening as the hips "
                  "travel back.",
             stop="Rock only as far as stays comfortable. A pinch at the front of a hip "
                  "ends the set — come forward and keep later rocks shallower.",
             progress="The hips travel further back before the stretch arrives."),
    Exercise("butterfly_pir", "Butterfly PIR", _A, ("adductor_length",),
             note="Press the knees up into your hands for 5 s, relax, sink. Contract-relax; "
                  "the same family as the piriformis PNF already in the release protocol.",
             position="Sit on the floor with your back against a wall, soles of your feet "
                      "together, knees dropped out to the sides, hands resting on top of "
                      "your knees.",
             movement="Press your knees UP into your hands for about five seconds — the "
                      "hands hold still, the legs push against them. Then let the effort "
                      "go completely and let the knees sink for about fifteen seconds. "
                      "That is one round.",
             feel="Work on the inside of the thighs during the press; a deeper, easier "
                  "sink just after you let go.",
             stop="The hands only resist — they never push the knees down. When a sink "
                  "gains nothing over the one before, the set is done.",
             progress="The knees rest lower at the start of a session than they did last "
                      "session."),
    Exercise("tailors_pose", "Tailor's pose, unloaded", _U, ("adductor_length",),
             note="Back flat to a wall, soles together, knees pressed down under your own "
                  "power. Passive floor-supported external rotation is NOT a snapping-hip "
                  "risk position — that was confirmed 2026-08-05.",
             position="Sit with your back flat against a wall, soles of your feet "
                      "together, heels pulled in to your recorded heel distance.",
             movement="Press your knees down toward the floor using only your leg muscles "
                      "— no hands — and hold the press steady while you breathe.",
             feel="Working effort along the inside of the thighs. It is an exercise, not "
                  "a passive sit.",
             stop="Your back stays flat on the wall. A sharp pinch at the front of a hip "
                  "ends the set — record it.",
             progress="The knees sit closer to the floor at the same heel distance — the "
                      "same number the assessment measures.",
             adapted_from="Tailor's pose with weight plates on the knees",
             reverts_when="the anterior-hip sensation reported in a deep butterfly on "
                          "2026-08-05 has been re-tested unloaded and does not reappear. "
                          "Adding external load to a position that produced an unexplained "
                          "anterior sensation is the one order that cannot be undone"),
    Exercise("butterfly_active", "Butterfly, knees pressed down under own power", _U,
             ("adductor_length",),
             note="No hands. Active and controlled — the pattern the hypermobility profile "
                  "prefers over a passive hold.",
             position="The same wall-backed butterfly: back flat on the wall, soles "
                      "together, heels at your recorded distance.",
             movement="Let the knees drop as far as they go on their own, then actively "
                      "press them a little lower and hold for a few breaths. No hands at "
                      "any point.",
             feel="Inside of the thighs working; nothing forced.",
             stop="Back stays on the wall; any front-of-hip pinch ends the set.",
             progress="The unaided resting height of the knees comes down."),
    Exercise("butterfly_press_downs", "Butterfly knee press-downs for reps", _R,
             ("adductor_length", "end_range_strength"),
             note="Three seconds each. Reps beat one long hold: each rep goes deeper "
                  "because fatigue has not accumulated mid-position.",
             position="The same wall-backed butterfly setup.",
             movement="Press the knees down hard for about three seconds, release, let "
                      "them settle, press again. Each press is one rep — fresh presses "
                      "beat one long tiring hold.",
             feel="Strong effort on the inside of the thighs. This is strength work done "
                  "in the stretch position.",
             stop="When a press no longer reaches as low as the first one, the set is "
                  "done.",
             progress="Each press reaches lower, and the first press of a session starts "
                      "lower."),
    Exercise("copenhagen", "Copenhagen plank", _R, ("end_range_strength",),
             note="Mechanically the cleanest item in the cluster — side-lying, spine "
                  "neutral, no lumbar flexion or extension, no axial load. The caution is "
                  "DOSE: last performed May/June 2025 at 30 s × 3, with a back injury and a "
                  "full rehab block since. That number is history, not a starting point.",
             position="Lie on your side, propped on your forearm, with your top foot up "
                      "on a bench or sturdy chair and the bottom leg resting beneath it.",
             movement="Press down through the top foot to lift your hips off the floor "
                      "until your body makes one straight line, and hold. The inside of "
                      "the top thigh is what holds you up.",
             feel="Hard work along the inside of the top thigh. Nothing in the lower "
                  "back — the body stays one straight line.",
             stop="When the hips start to sag or shake, lower down — the hold is over.",
             progress="Longer clean holds; later, the bottom leg held straight out for "
                      "more load."),

    # ── adductors, 90° knee — deferred as a group ───────────────────────────
    Exercise("horse_stance", "Horse stance squat", _U, ("adductor_length",),
             note="Feet wide, toes slightly out, knees to 90°.",
             position="Standing, feet wide apart, toes turned slightly out.",
             movement="Sink straight down until your knees reach a right angle, knees "
                      "tracking out over the feet, chest tall. Hold, then stand back up.",
             feel="Inside of the thighs and front of the thighs working together.",
             stop="If a knee drifts inward or the chest drops forward, stand up — the "
                  "rep is over.",
             progress="Deeper comfortable sits at the same width; later, wider stances.",
             deferred_until="the block's own loaded squat work has run clean",
             reverts_when="the gym block's own loaded squat work has run without a "
                          "change in right-hip snapping. Held because that question is "
                          "already being answered by squat work in the block, and adding a "
                          "second new externally-rotated squat now would make it impossible "
                          "to attribute a change to either. A measurement argument, not a "
                          "permission one"),
    Exercise("horse_stance_weighted", "Horse stance hold, weighted", _R,
             ("end_range_strength",),
             position="The same wide stance, holding a weight against your chest with "
                      "both hands.",
             movement="Sink to the right angle and hold there with the weight. The weight "
                      "makes the inner thighs hold harder in the same position.",
             feel="Inner thighs working distinctly harder than the unweighted version.",
             stop="The same tells: a knee drifting inward or the chest dropping ends the "
                  "hold.",
             progress="Longer holds before the tells appear; later, a little more weight.",
             deferred_until="the block's own loaded squat work has run clean",
             reverts_when="as horse_stance"),
    Exercise("cossack_bent", "Cossack squat, bent leg emphasis", _R, ("adductor_length",),
             position="Standing, feet very wide apart, toes slightly out.",
             movement="Sit down over one leg, bending that knee fully while the other leg "
                      "stays out to the side. The bent side carries you; push back up "
                      "through it and repeat, then change sides.",
             feel="The bent side working; a stretch along the inside of the other thigh.",
             stop="The heel of the bent side stays down. If it lifts, you have gone "
                  "deeper than today allows.",
             progress="Deeper sits with the heel staying down.",
             deferred_until="the block's own loaded squat work has run clean",
             reverts_when="as horse_stance"),
    Exercise("cossack_straight", "Cossack squat, trailing leg straight", _R,
             ("adductor_length",),
             note="The straight trailing leg also loads the proximal hamstring at the "
                  "ischial tuberosity, which is listed as overactive.",
             position="The same very wide stance. This time the trailing leg stays "
                      "completely straight, toes pulled up toward the ceiling.",
             movement="Sit over the bent side while the trailing leg stays straight the "
                      "whole way — its straightness is the point of the exercise. Push "
                      "back up and repeat, then change sides.",
             feel="A strong stretch along the whole inside and back of the straight leg.",
             stop="The moment the straight knee bends, the rep stops counting — reset "
                  "and go less deep.",
             progress="Deeper sits with the trailing knee never bending.",
             deferred_until="the block's own loaded squat work has run clean",
             reverts_when="as horse_stance"),

    # ── adductors, straight knee (gracilis) ─────────────────────────────────
    Exercise("wall_straddle", "Supine wall straddle, unloaded", _A, ("adductor_length",),
             note="Backside to the wall, legs up it, knees straight, kneecaps to the "
                  "ceiling, let the legs slide apart. Spine unloaded throughout.",
             position="Lie on your back with your backside close against a wall and both "
                      "legs straight up it, knees locked straight, kneecaps facing the "
                      "ceiling.",
             movement="Let the legs slide apart under their own weight and stay there — "
                      "no pushing, no pulling. Gravity does the stretching; you only "
                      "breathe.",
             feel="A gentle widening stretch along the inside of both thighs. It should "
                  "feel easy to stay in.",
             stop="Knees stay straight and the backside stays at the wall. Come out when "
                  "it stops feeling easy — this one is never forced.",
             progress="The legs rest wider on their own — the same ankle-to-ankle number "
                      "the assessment measures.",
             adapted_from="Supine wall straddle with ankle weights",
             reverts_when="as tailors_pose — the same loaded-passive-end-range question"),
    Exercise("triangle_split", "Triangle side split, external-rotation cue", _A,
             ("bone", "adductor_length"),
             note="Hips on a separate line to the feet. Turn the legs out from the hips to "
                  "clear the joint; sit the hips back, weight in the heels, chest high. "
                  "Train the triangle before any inline work.",
             position="Standing, then sliding the feet wide apart with your hips kept "
                      "BACK behind the line of the feet — hips and feet make a triangle "
                      "seen from above, not one line. Hands on blocks or the floor in "
                      "front of you, chest high, legs straight.",
             movement="Turn both legs out from the hips — kneecaps rotating toward the "
                      "ceiling — then slide the feet apart, sitting the hips back with "
                      "the weight in the heels. Go to where it stops. The turn-out is "
                      "what makes the room; never arch the back to find more.",
             feel="A stretch along the inside of the thighs, with the hips feeling "
                  "clear, not pinched.",
             stop="A sharp pinch at the front of a hip with a hard, sudden stop ends "
                  "today's depth work — record it.",
             progress="Lower hips at the same stance, without the pinch.",
             adapted_from="Triangle side split cued by tilting the hip down and arching the "
                          "back",
             reverts_when="never — the source calls the two routes equivalent, so this is "
                          "the other of two equal options rather than a lesser version"),
    Exercise("inline_split", "Inline side split, external-rotation cue", _A,
             ("bone", "adductor_length"),
             note="Only once the triangle is comfortable.",
             position="The same wide position with straight legs, but now the hips press "
                      "forward onto the same line as the feet.",
             movement="The same turn-out and the same slide, keeping the hips on the "
                      "line. Only once the triangle version is comfortable.",
             feel="Inside of the thighs, deeper than the triangle at the same width.",
             stop="Same as the triangle: a sharp front-of-hip pinch with a hard stop "
                  "ends it, and the back is never arched to find room.",
             progress="Lower hips while staying on the line.",
             adapted_from="Inline side split with the arch cue",
             reverts_when="as triangle_split"),
    Exercise("isometric_split", "Isometric side split, hands off", _R,
             ("end_range_strength",),
             note="At depth, holding your own weight, knees straight.",
             position="In your side split at a depth you can hold, legs straight, hands "
                      "off the floor and off your legs.",
             movement="Hold your own weight with the legs for a few seconds — the inner "
                      "thighs actively grip the floor to stop you sliding wider. Come "
                      "out, rest fully, repeat.",
             feel="Hard work along the inside of both thighs. It should feel like "
                  "effort, not like a stretch.",
             stop="The moment a hand has to come down, the hold is over. If a hold "
                  "feels as easy as resting, you are too high to be working.",
             progress="Holds at lower heights — the same floor-to-crotch number the "
                      "assessment measures."),

    # ── the tilt group — where limiter 5 lives ──────────────────────────────
    Exercise("pelvic_rock", "Seated pelvic rock, mid-range", _U, ("seated_tilt",),
             note="Hands behind you, rock the pelvis forward and back through MID-RANGE. "
                  "Train the movement, not the depth, and not the arched end of it. You "
                  "cannot train a position through a joint action you cannot perform on "
                  "its own.",
             position="Sit on the floor with your legs crossed or in a small straddle, "
                      "hands on the floor behind you taking some of your weight.",
             movement="Tip your pelvis forward and back through the middle of its range — "
                      "your waistband is a bowl of water: pour a little out the front, "
                      "then a little out the back. The chest stays where it is; nothing "
                      "else moves.",
             feel="Low effort around the hips and lower belly. This is a coordination "
                  "drill, not a stretch.",
             stop="Stay in the middle of the range — never push into the arched-back "
                  "end, and stop if the tipping turns into leaning.",
             progress="A bigger, smoother arc — the tipping becomes something you can do "
                      "on demand.",
             adapted_from="Seated pelvic rock taken to the arched end",
             reverts_when="never — the arched end is lumbar extension against a "
                          "retrolisthesis, and the drill's purpose is the movement anyway"),
    Exercise("elevated_hinge", "Elevated flat-back straddle hinge", _A,
             ("seated_tilt", "adductor_length"),
             note="Sit on a block or bench, no added weight, and hinge with a flat back. "
                  "The elevation is the whole point: sitting above foot level rotates the "
                  "pelvis forward on its own, so the block is the assist device for the "
                  "TILT specifically. Lowering the block over months is the progression — "
                  "reaching further at a fixed height is not.",
             position="Sit on a block or low bench with your legs straight and open to "
                      "your recorded straddle width, kneecaps and toes pointing up.",
             movement="Sit tall, then tip your whole torso forward from the hips — chest "
                      "proud, spine long — a few centimetres, to the point just before "
                      "the lower back rounds, and hold there. Sitting above your feet "
                      "tips the pelvis forward for you: the block is doing what your hip "
                      "muscles cannot yet.",
             feel="A stretch down the back of the thighs and inside of the legs, with "
                  "the back working lightly to stay long.",
             stop="The moment the lower back rounds you have left the exercise — come "
                  "back up to where it stays flat.",
             progress="The block gets lower over months. Reaching further at the same "
                      "height is not progress here.",
             adapted_from="Elevated-hip pancake with a weight behind the neck",
             reverts_when="never as written. The weight supplied depth through a spine that "
                          "had not tilted, which is the opposite of what the elevation "
                          "does. When the tilt is producible unaided, no assist is needed"),
    Exercise("pancake_own_power", "Pancake, own power, arms crossed", _U,
             ("seated_tilt", "adductor_length"),
             note="No hands, no strap. Stop at the first loss of a flat back — that point "
                  "is the measurement, not the floor.",
             position="Sit on the floor with your legs straight and open to your "
                      "recorded straddle width, kneecaps and toes up, arms crossed on "
                      "your chest.",
             movement="Tip forward from the hips as far as you can under your own power "
                      "and hold for a breath or two. No hands, no strap — your hip "
                      "muscles do all the pulling.",
             feel="Working effort deep at the front of the hips doing the pulling; "
                  "stretch behind the legs resisting it.",
             stop="Stop at the first loss of the flat back — that point is the end of "
                  "the exercise, not the floor.",
             progress="More tip before the back rounds — the same angle the assessment "
                      "measures.",
             adapted_from="Pancake with a strap anchored in front",
             reverts_when="never — a strap supplies force past the point he would "
                          "self-limit, which is the mechanism the annulus tears cannot take"),
    Exercise("straddle_lift_offs", "Straddle lift-offs from a flat back", _R,
             ("seated_tilt", "puller_strength"),
             note="Hip flexor strength to PRODUCE the tilt rather than be placed into it. "
                  "Active hip flexion under iliopsoas load — cue neutral or slight internal "
                  "rotation on the right.",
             position="Sit with your legs straight and open to your recorded straddle "
                      "width — on the block while the tilt is new, on the floor once it "
                      "is not. Arms crossed on your chest; hands never touch the floor.",
             movement="Pull yourself forward from the hips to your flat-back limit. "
                      "Gravity is not the resistance here — your own leg tissue is, and "
                      "the muscles at the front of the hips must out-pull it. At the "
                      "limit, lift the chest five to ten centimetres, then pull back "
                      "down. That cycle is one rep.",
             feel="Distinct working effort deep at the front of the hips — this is "
                  "strength work, and it can cramp there at first. On the right, keep "
                  "the kneecap pointing up or slightly inward.",
             stop="When you can no longer reach the same depth with a flat back, the "
                  "set is over. A hand coming down voids the rep.",
             progress="More degrees of tip produced on your own — the number the "
                      "assessment's own-power test measures.",
             adapted_from="Pancake lift-offs from a rounded fold",
             reverts_when="when a flat back holds through the full lift, at which point the "
                          "two are the same exercise"),
    Exercise("flat_back_hinge", "Flat-back hip hinge, legs together", _R,
             ("seated_tilt",),
             note="Raises the hamstring ceiling that currently caps the tilt at about 90°, "
                  "without a fold. Hinge, never round.",
             position="Standing, feet together or hip-width apart, knees soft — a slight "
                      "bend, not locked. No weight.",
             movement="Push your hips straight back and tip the torso forward with a "
                      "long, flat back until the back of the thighs stops you. Stand "
                      "back up by driving the hips forward.",
             feel="A building stretch down the back of the thighs on the way down; the "
                  "back of the legs and backside working on the way up.",
             stop="The moment the lower back wants to round to go lower, that is the "
                  "bottom — turn around there. Never round for depth.",
             progress="A deeper hinge before the rounding wants to happen — this is the "
                      "ceiling the exercise exists to raise."),
    Exercise("loaded_flat_back_hinge", "Flat-back straddle hinge holding a light weight at "
                                       "the chest", _R,
             ("seated_tilt", "puller_strength"),
             note="At the chest, never behind the neck.",
             position="Seated on the block in your straddle at the recorded width, legs "
                      "straight, holding a light weight against your chest with both "
                      "hands.",
             movement="The same hinge as the elevated version, now with the weight making "
                      "the back and hips work harder to stay long. Tip to the flat-back "
                      "limit, return. Moving through it, not holding.",
             feel="The whole back of the body working to keep the spine long; stretch "
                  "behind the legs.",
             stop="The first loss of the flat back ends the set. The weight stays at "
                  "the chest — never behind the neck.",
             progress="The same depth with the weight feeling lighter; later, a little "
                      "more weight.",
             adapted_from="Seated straddle good-mornings holding a plate",
             reverts_when="stage 3, AND a hinge that no longer rounds. The original started "
                          "from a position already at his hamstring limit, so the spine had "
                          "to round before anything moved; services.rules also caps "
                          "good-mornings at stage 3 and he is stage 2"),

    # ── pullers ─────────────────────────────────────────────────────────────
    Exercise("side_leg_raise", "Standing side leg raises", _R, ("puller_strength",),
             note="Slow, no swing. Loads glute medius — release before activating.",
             position="Standing tall with no support, hands on your hips.",
             movement="Lift one leg straight out to the side as high as it goes without "
                      "leaning, pause at the top, lower slowly. Slow up, slow down — no "
                      "swing.",
             feel="Work on the outside of the hip of the lifting leg. If you feel it "
                  "mostly in the lower back, you are leaning.",
             stop="The torso stays upright: the moment you lean away from the lifting "
                  "leg, the rep does not count.",
             progress="Higher lifts with a still torso — the same angle the assessment's "
                      "active test measures."),
    Exercise("side_lying_abduction", "Side-lying hip abduction with ankle weight", _R,
             ("puller_strength",),
             position="Lie on your side, legs straight and stacked one on the other, an "
                      "ankle weight on the top leg.",
             movement="Lift the top leg toward the ceiling, pause at the top, lower "
                      "slowly.",
             feel="Outside of the top hip working.",
             stop="The hips stay stacked — if the top hip rolls backward to lift "
                  "higher, you have over-reached the rep.",
             progress="Higher clean lifts; later, more weight."),
    Exercise("banded_abduction", "Banded end-range abduction", _R, ("puller_strength",),
             position="Sit or lie with a band around your ankles and your legs already "
                      "opened toward the wide end of your range.",
             movement="Open the legs the last few centimetres against the band, pause, "
                      "come back slowly. The work lives at the very end of the range, "
                      "where you are weakest.",
             feel="Outside of the hips working hardest right at the widest point.",
             stop="When you can no longer reach the same width against the band, the "
                  "set is done.",
             progress="A stronger push through the last few centimetres, and a longer "
                      "pause at the widest point."),
    Exercise("wall_straddle_active", "Supine wall straddle, actively opening", _R,
             ("puller_strength",), note="Heels off the wall.",
             position="The same wall position — on your back, legs straight up the wall "
                      "— but now the heels come slightly off the wall.",
             movement="Open the legs as wide as they go using the outside of your hips, "
                      "heels hovering so the wall carries nothing, hold a few seconds, "
                      "close a little, open again.",
             feel="Outside of the hips working to hold the width.",
             stop="Knees stay straight and heels stay off the wall — when they touch "
                  "back down, the set is over.",
             progress="The width you can hold unaided gets closer to the width you rest "
                      "at."),
    Exercise("side_leg_raise_eccentric", "Side leg raises with eccentric overload", _R,
             ("puller_strength",),
             note="Lift bent, straighten, lower slow. You are stronger eccentrically, so "
                  "this loads the top of the range you cannot otherwise reach.",
             position="Standing tall with no support.",
             movement="Lift the leg out to the side with the knee bent — bent, it goes "
                      "higher — straighten the knee at the top, then lower the straight "
                      "leg as slowly as you can. The slow lowering is the exercise.",
             feel="Outside of the hip loading hardest on the way down.",
             stop="No leaning, same as the other raises. When the lowering stops being "
                  "slow, stop.",
             progress="Slower lowers from greater heights — this trains the very top of "
                      "the range you cannot yet lift into."),
    Exercise("rotations_90_90", "90/90 hip rotations with lift-offs", _R,
             ("puller_strength",),
             note="Cue neutral or slight internal rotation on the right — the lift-off is "
                  "active hip flexion, which is the contractile trigger.",
             position="Sit on the floor with the front leg bent to a right angle in "
                      "front of you and the back leg bent to a right angle out to the "
                      "side.",
             movement="Sweep both knees together across to the other side so the legs "
                      "swap roles, and at each side lift the back knee off the floor "
                      "for a second before travelling on.",
             feel="Work deep around the hips doing the rotating and the lifting. "
                  "Nothing sharp.",
             stop="On the right, the kneecap stays neutral or slightly inward on every "
                  "lift. A snap or click at the right hip ends the set — record it.",
             progress="Higher lifts and smoother sweeps."),
    Exercise("er_holds", "Seated external rotation holds", _U, ("puller_strength",),
             note="Seat-supported and passive, so not a snapping-hip risk position.",
             position="Sit on a chair or bench, feet flat on the floor.",
             movement="Turn one leg out from the hip — the whole thigh rolls so the "
                      "kneecap points outward — as far as it goes under its own power, "
                      "hold a few seconds, return. The seat carries your weight "
                      "throughout.",
             feel="Work around the outside and back of the hip doing the turning.",
             stop="The turn comes from the hip, not the foot: if only the foot is "
                  "rotating, reset. Any snap at the right hip ends the set.",
             progress="More turn-out, held longer — the capacity the split position "
                      "spends."),
    Exercise("hip_tilt_drill", "Standing hip tilt drill, mid-range", _U, ("seated_tilt",),
             note="Mid-range only, never held at the arched end.",
             position="Standing, feet hip-width apart, hands on the bony rim of your "
                      "pelvis.",
             movement="Tip the pelvis forward and back through the middle of its range — "
                      "the standing version of the seated rock. Small and controlled; "
                      "your hands feel the rim tipping.",
             feel="Light work around the waist and hips.",
             stop="Middle of the range only — never hold the arched end.",
             progress="The tipping becomes available on demand standing, as well as "
                      "sitting.",
             adapted_from="Standing anterior tilt drill held at end range",
             reverts_when="never — 5 × 20 s of held lumbar extension against a "
                          "retrolisthesis was the original, and the external-rotation "
                          "variant already trains the same joint clearance"),
    Exercise("adductor_squeeze", "Adductor squeezes at width", _R,
             ("end_range_strength",),
             note="Isometric adduction at a controlled width. No spinal load and no passive "
                  "end-range hold — the single best-aligned item in the cluster against "
                  "this athlete's hypermobility guidance.",
             position="Sit on the floor in a straddle at a width you fully control — "
                      "well inside your maximum — legs straight, hands behind you for "
                      "support.",
             movement="Press both heels down and inward as if dragging them toward each "
                      "other. The floor does not move, so the inner thighs work hard "
                      "while the legs stay still. Hold each press about five seconds, "
                      "rest, repeat.",
             feel="Strong effort along the inside of both thighs, with no movement "
                  "anywhere.",
             stop="If a press brings on a hard cramp, come in narrower and press "
                  "softer.",
             progress="Harder presses at wider widths."),

    # ── knee ────────────────────────────────────────────────────────────────
    Exercise("tke", "Terminal knee extension with a band", _R, (),
             note="VMO. Resists the knee collapsing inward, which is the direction gravity "
                  "pulls it in a split.",
             position="Standing with a band anchored in front of you at knee height, "
                      "looped behind one knee, that foot slightly forward and the knee "
                      "slightly bent.",
             movement="Straighten the knee fully against the band's pull, pause, let it "
                      "bend slightly, straighten again. Slow and controlled.",
             feel="The muscle just above the inside of the kneecap doing the "
                  "straightening.",
             stop="The knee straightens smoothly; it never snaps back.",
             progress="Stronger, steadier lockouts — the knee stops wanting to collapse "
                      "inward in the split."),
    Exercise("spanish_squat", "Spanish squat", _R, (),
             note="Knee-dominant, torso vertical.",
             position="Standing with a thick band looped behind both knees, anchored "
                      "behind you, feet hip-width apart.",
             movement="Sit straight down against the band with the torso staying "
                      "vertical, to a comfortable depth, and stand back up. The band "
                      "lets the knees travel without the torso tipping.",
             feel="Front of the thighs working, the kneecaps loaded evenly.",
             stop="The torso stays vertical and the depth stays comfortable.",
             progress="Deeper, slower reps."),
)

LIBRARY_BY_KEY: dict[str, Exercise] = {e.key: e for e in LIBRARY}
LIBRARY_BY_NAME: dict[str, Exercise] = {e.name: e for e in LIBRARY}

#: Everything held back, with the condition that restores it. Read this at every
#: four-week re-test — a hold is meant to be lifted, not to become permanent by
#: nobody looking.
DEFERRED: tuple[Exercise, ...] = tuple(e for e in LIBRARY if e.deferred_until)
ADAPTED: tuple[Exercise, ...] = tuple(e for e in LIBRARY if e.adapted)


# ── what was removed outright ────────────────────────────────────────────────

@dataclass(frozen=True)
class Removal:
    """An exercise from the source that is not in the library at all.

    Recorded rather than silently dropped, so a future reader can see what was
    taken out, why, and what would put it back. An unexplained absence is
    indistinguishable from an oversight.
    """
    name: str
    mechanism: str
    reverts_when: str


REMOVED: tuple[Removal, ...] = (
    Removal("Tailor's pose with weight plates on the knees",
            "External load onto a passively held end-range hip — the practice the "
            "hypermobility profile rules out. The source asked for up to 4 × 90 s, six "
            "minutes, the highest loaded-end-range dose in the material.",
            "the anterior-hip sensation has been re-tested unloaded and does not "
            "reappear"),
    Removal("Supine wall straddle with ankle weights",
            "Same mechanism, lower magnitude.",
            "as above"),
    Removal("Elevated-hip pancake with weight behind the neck",
            "Axial load in a seated fold over covered annulus tears at L3/4 and L4/5, with "
            "a placement that also loads a post-Latarjet shoulder. The load produced the "
            "depth instead of the tilt.",
            "when the tilt is producible unaided, at which point no assist is needed"),
    Removal("Pancake with a strap anchored in front",
            "The strap supplies external force past the point he would self-limit.",
            "as above"),
    Removal("Pancake lift-offs from a rounded fold",
            "Repeated concentric lift out of maximum seated flexion — mechanically a "
            "bodyweight seated good-morning.",
            "when a flat back holds through the full lift"),
    Removal("Seated straddle good-mornings holding a plate",
            "Loaded lumbar flexion from a position already at his hamstring limit. "
            "services.rules caps good-mornings at stage 3; he is stage 2.",
            "stage 3, and a hinge that no longer rounds"),
    Removal("Standing anterior tilt drill held at end range",
            "5 × 20 s of held lumbar extension against an L5/S1 retrolisthesis and a "
            "narrowed right foramen.",
            "never as written — the external-rotation variant trains the same clearance"),
)


def exercise(key_or_name: str) -> Exercise | None:
    """Look up by key or by display name. The Prescription references by NAME,
    which is what makes the layer boundary checkable: a name that does not
    resolve here is a Prescription defining an exercise, which it may not do."""
    return LIBRARY_BY_KEY.get(key_or_name) or LIBRARY_BY_NAME.get(key_or_name)
