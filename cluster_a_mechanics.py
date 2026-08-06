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
    note: str = ""
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
             note="Deep flexion with abduction, floor-supported and self-limited."),
    Exercise("butterfly_pir", "Butterfly PIR", _A, ("adductor_length",),
             note="Press the knees up into your hands for 5 s, relax, sink. Contract-relax; "
                  "the same family as the piriformis PNF already in the release protocol."),
    Exercise("tailors_pose", "Tailor's pose, unloaded", _U, ("adductor_length",),
             note="Back flat to a wall, soles together, knees pressed down under your own "
                  "power. Passive floor-supported external rotation is NOT a snapping-hip "
                  "risk position — that was confirmed 2026-08-05.",
             adapted_from="Tailor's pose with weight plates on the knees",
             reverts_when="the physiotherapist answers the anterior-hip sensation question "
                          "raised 2026-08-05, where a deep butterfly produced hip-flexor "
                          "rather than adductor sensation"),
    Exercise("butterfly_active", "Butterfly, knees pressed down under own power", _U,
             ("adductor_length",),
             note="No hands. Active and controlled — the pattern the hypermobility profile "
                  "prefers over a passive hold."),
    Exercise("butterfly_press_downs", "Butterfly knee press-downs for reps", _R,
             ("adductor_length", "end_range_strength"),
             note="Three seconds each. Reps beat one long hold: each rep goes deeper "
                  "because fatigue has not accumulated mid-position."),
    Exercise("copenhagen", "Copenhagen plank", _R, ("end_range_strength",),
             note="Mechanically the cleanest item in the cluster — side-lying, spine "
                  "neutral, no lumbar flexion or extension, no axial load. The caution is "
                  "DOSE: last performed May/June 2025 at 30 s × 3, with a back injury and a "
                  "full rehab block since. That number is history, not a starting point."),

    # ── adductors, 90° knee — deferred as a group ───────────────────────────
    Exercise("horse_stance", "Horse stance squat", _U, ("adductor_length",),
             note="Feet wide, toes slightly out, knees to 90°.",
             deferred_until="2026-08-16",
             reverts_when="the Day 28 reassessment has been read. Held because an open "
                          "Stage 2 exit criterion is 'no increase in Coxa Saltans frequency "
                          "under loaded squat/split-squat work', judged on that date — "
                          "introducing an externally-rotated loaded squat inside the "
                          "assessment window would confound the criterion he is about to be "
                          "assessed on. A measurement cost as much as a safety one"),
    Exercise("horse_stance_weighted", "Horse stance hold, weighted", _R,
             ("end_range_strength",),
             deferred_until="2026-08-16",
             reverts_when="as horse_stance"),
    Exercise("cossack_bent", "Cossack squat, bent leg emphasis", _R, ("adductor_length",),
             deferred_until="2026-08-16",
             reverts_when="as horse_stance"),
    Exercise("cossack_straight", "Cossack squat, trailing leg straight", _R,
             ("adductor_length",),
             note="The straight trailing leg also loads the proximal hamstring at the "
                  "ischial tuberosity, which is listed as overactive.",
             deferred_until="2026-08-16",
             reverts_when="as horse_stance"),

    # ── adductors, straight knee (gracilis) ─────────────────────────────────
    Exercise("wall_straddle", "Supine wall straddle, unloaded", _A, ("adductor_length",),
             note="Backside to the wall, legs up it, knees straight, kneecaps to the "
                  "ceiling, let the legs slide apart. Spine unloaded throughout.",
             adapted_from="Supine wall straddle with ankle weights",
             reverts_when="as tailors_pose — the same loaded-passive-end-range question"),
    Exercise("triangle_split", "Triangle side split, external-rotation cue", _A,
             ("bone", "adductor_length"),
             note="Hips on a separate line to the feet. Turn the legs out from the hips to "
                  "clear the joint; sit the hips back, weight in the heels, chest high. "
                  "Train the triangle before any inline work.",
             adapted_from="Triangle side split cued by tilting the hip down and arching the "
                          "back",
             reverts_when="never — the source calls the two routes equivalent, so this is "
                          "the other of two equal options rather than a lesser version"),
    Exercise("inline_split", "Inline side split, external-rotation cue", _A,
             ("bone", "adductor_length"),
             note="Only once the triangle is comfortable.",
             adapted_from="Inline side split with the arch cue",
             reverts_when="as triangle_split"),
    Exercise("isometric_split", "Isometric side split, hands off", _R,
             ("end_range_strength",),
             note="At depth, holding your own weight, knees straight."),

    # ── the tilt group — where limiter 5 lives ──────────────────────────────
    Exercise("pelvic_rock", "Seated pelvic rock, mid-range", _U, ("seated_tilt",),
             note="Hands behind you, rock the pelvis forward and back through MID-RANGE. "
                  "Train the movement, not the depth, and not the arched end of it. You "
                  "cannot train a position through a joint action you cannot perform on "
                  "its own.",
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
             adapted_from="Elevated-hip pancake with a weight behind the neck",
             reverts_when="never as written. The weight supplied depth through a spine that "
                          "had not tilted, which is the opposite of what the elevation "
                          "does. When the tilt is producible unaided, no assist is needed"),
    Exercise("pancake_own_power", "Pancake, own power, arms crossed", _U,
             ("seated_tilt", "adductor_length"),
             note="No hands, no strap. Stop at the first loss of a flat back — that point "
                  "is the measurement, not the floor.",
             adapted_from="Pancake with a strap anchored in front",
             reverts_when="never — a strap supplies force past the point he would "
                          "self-limit, which is the mechanism the annulus tears cannot take"),
    Exercise("straddle_lift_offs", "Straddle lift-offs from a flat back", _R,
             ("seated_tilt", "puller_strength"),
             note="Sit tall, hinge to your flat-back limit, lift the chest 5-10 cm, lower. "
                  "Hip flexor strength to PRODUCE the tilt rather than be placed into it. "
                  "Active hip flexion under iliopsoas load — cue neutral or slight internal "
                  "rotation on the right.",
             adapted_from="Pancake lift-offs from a rounded fold",
             reverts_when="when a flat back holds through the full lift, at which point the "
                          "two are the same exercise"),
    Exercise("flat_back_hinge", "Flat-back hip hinge, legs together", _R,
             ("seated_tilt",),
             note="Raises the hamstring ceiling that currently caps the tilt at about 90°, "
                  "without a fold. Hinge, never round."),
    Exercise("loaded_flat_back_hinge", "Flat-back straddle hinge holding a light weight at "
                                       "the chest", _R,
             ("seated_tilt", "puller_strength"),
             note="At the chest, never behind the neck.",
             adapted_from="Seated straddle good-mornings holding a plate",
             reverts_when="stage 3, AND a hinge that no longer rounds. The original started "
                          "from a position already at his hamstring limit, so the spine had "
                          "to round before anything moved; services.rules also caps "
                          "good-mornings at stage 3 and he is stage 2"),

    # ── pullers ─────────────────────────────────────────────────────────────
    Exercise("side_leg_raise", "Standing side leg raises", _R, ("puller_strength",),
             note="Slow, no swing. Loads glute medius — release before activating."),
    Exercise("side_lying_abduction", "Side-lying hip abduction with ankle weight", _R,
             ("puller_strength",)),
    Exercise("banded_abduction", "Banded end-range abduction", _R, ("puller_strength",)),
    Exercise("wall_straddle_active", "Supine wall straddle, actively opening", _R,
             ("puller_strength",), note="Heels off the wall."),
    Exercise("side_leg_raise_eccentric", "Side leg raises with eccentric overload", _R,
             ("puller_strength",),
             note="Lift bent, straighten, lower slow. You are stronger eccentrically, so "
                  "this loads the top of the range you cannot otherwise reach."),
    Exercise("rotations_90_90", "90/90 hip rotations with lift-offs", _R,
             ("puller_strength",),
             note="Cue neutral or slight internal rotation on the right — the lift-off is "
                  "active hip flexion, which is the contractile trigger."),
    Exercise("er_holds", "Seated external rotation holds", _U, ("puller_strength",),
             note="Seat-supported and passive, so not a snapping-hip risk position."),
    Exercise("hip_tilt_drill", "Standing hip tilt drill, mid-range", _U, ("seated_tilt",),
             note="Mid-range only, never held at the arched end.",
             adapted_from="Standing anterior tilt drill held at end range",
             reverts_when="never — 5 × 20 s of held lumbar extension against a "
                          "retrolisthesis was the original, and the external-rotation "
                          "variant already trains the same joint clearance"),
    Exercise("adductor_squeeze", "Adductor squeezes at width", _R,
             ("end_range_strength",),
             note="Isometric adduction at a controlled width. No spinal load and no passive "
                  "end-range hold — the single best-aligned item in the cluster against "
                  "this athlete's hypermobility guidance."),

    # ── knee ────────────────────────────────────────────────────────────────
    Exercise("tke", "Terminal knee extension with a band", _R, (),
             note="VMO. Resists the knee collapsing inward, which is the direction gravity "
                  "pulls it in a split."),
    Exercise("spanish_squat", "Spanish squat", _R, (),
             note="Knee-dominant, torso vertical."),
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
            "the physiotherapist answers the anterior-hip sensation question"),
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
