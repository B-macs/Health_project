"""
rules.py — Deterministic Movement Safety Rules.

Hard clinical constraints derived directly from the MRI report (10.11.2025)
and established sports medicine guidelines for lumbar disc pathology.

These rules fire before and independently of any AI call.
No LLM should override a "contraindicated" ruling — that is a hard stop.

MRI reference summary:
  L5/S1: activated osteochondrosis, retrolisthesis, right dorsolateral disc
         protrusion, moderate right foraminal stenosis.
  L4/5:  flat protrusion left dorsolateral, covered annulus tear, retrolisthesis,
         mild foraminal stenosis.
  L3/4:  flat protrusion left dorsolateral, covered annulus tear, mild foraminal
         stenosis.
  Cleared: spinal canal, facet joints, ISG, back musculature (no atrophy).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MovementRule:
    movement: str           # name or keyword (matched case-insensitively)
    reason: str             # clinical justification
    stage_cap: int          # safest from this stage onwards (1=always, 3=perf only)
    severity: str           # "contraindicated" | "caution" | "cleared"
    laterality: str = "bilateral"  # "left" | "right" | "bilateral" | "axial"


# ─────────────────────────────────────────────────────────────────────────────
#  Name normalisation
# ─────────────────────────────────────────────────────────────────────────────

def normalise_movement(name: str) -> str:
    """Lowercase, punctuation and hyphens to spaces, whitespace collapsed.

    WHY THIS EXISTS. `check_movement` matches by substring, and a raw substring
    test is defeated by a single punctuation mark. Measured 2026-08-06 against
    the Cluster A source documents:

        check_movement("good morning", 2)   -> contraindicated (cap 3 vs stage 2)
        check_movement("good-mornings", 2)  -> unknown

    "Seated straddle good-mornings holding a plate" is a loaded lumbar-flexion
    movement over two covered annulus tears, and one hyphen was the difference
    between a hard block and silence. `unknown` is not a block — services/yoga.py
    discards it entirely — so a false negative here is indistinguishable from
    "no rule applies".

    Possessives are also stripped ("tailor's pose" -> "tailors pose") so a rule
    can be authored either way round without a second entry.
    """
    lowered = name.lower().replace("'", "").replace("’", "")
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", spaced).strip()


def _heads_the_name(name: str, keyword: str) -> bool:
    """True when `keyword` is the head of `name`, tolerating a plural 's'.

    Used only for CLEARED rules, where a fragment match is dangerous. Token-wise
    rather than by string prefix, because a string prefix is defeated by exactly
    the plural these names carry: "adductor squeezes at width" does not start
    with "adductor squeeze " (the 's' lands where the space should be).
    """
    name_tokens, kw_tokens = name.split(), keyword.split()
    if len(name_tokens) < len(kw_tokens):
        return False
    for got, want in zip(name_tokens, kw_tokens):
        if got != want and got != want + "s" and want != got + "s":
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  Hard movement rules (derived from MRI + clinical guidelines)
# ─────────────────────────────────────────────────────────────────────────────

MOVEMENT_RULES: list[MovementRule] = [
    # ── Contraindicated (any stage) ──────────────────────────────────────────
    MovementRule(
        movement="heavy deadlift",
        reason="High axial compression on L5/S1 osteochondrosis. Retrolisthesis risks further posterior shear.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="barbell deadlift",
        reason="High axial compression on L5/S1 osteochondrosis.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="conventional deadlift",
        reason="High axial compression on L5/S1 osteochondrosis.",
        stage_cap=1, severity="contraindicated", laterality="axial",
    ),
    MovementRule(
        movement="hyperextension",
        reason="L5/S1 retrolisthesis — lumbar hyperextension compresses already-narrowed right foramen."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. No goal loads end-range lumbar extension, so exposure stays rare by content rather than by ban. REVERT on any right-leg neural sign or foraminal symptom under extension.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="back extension",
        reason="L5/S1 retrolisthesis — lumbar hyperextension compresses already-narrowed right foramen."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. No goal loads end-range lumbar extension, so exposure stays rare by content rather than by ban. REVERT on any right-leg neural sign or foraminal symptom under extension.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="seated forward fold",
        reason="End-range lumbar flexion loads covered annulus tears at L3/4 and L4/5."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. Measured the same day: five unloaded seated folds, zero releases, zero pain. Build any load gradually. REVERT to contraindicated on any lumbar-base release or pain under flexion load.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="forward fold",
        reason="End-range lumbar flexion loads covered annulus tears at L3/4 and L4/5. "
               "Generalizes 'seated forward fold' to catch named variants (e.g. yoga poses)."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. Measured the same day: five unloaded seated folds, zero releases, zero pain. Build any load gradually. REVERT to contraindicated on any lumbar-base release or pain under flexion load.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="toe touch",
        reason="End-range lumbar flexion loads covered annulus tears at L3/4 and L4/5."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. Measured the same day: five unloaded seated folds, zero releases, zero pain. Build any load gradually. REVERT to contraindicated on any lumbar-base release or pain under flexion load.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="leg press",
        reason="Hip flexion at end-range under load increases intradiscal pressure at L3-L5."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. Unused by any plan; the squat pattern covers the goal. REVERT on any lumbar signal under deep loaded hip flexion.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="sit up",
        reason="Spinal flexion under load — contraindicated with covered annulus tears."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. Measured the same day: five unloaded seated folds, zero releases, zero pain. Build any load gradually. REVERT to contraindicated on any lumbar-base release or pain under flexion load.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="crunch",
        reason="Spinal flexion under load — contraindicated with covered annulus tears."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. Measured the same day: five unloaded seated folds, zero releases, zero pain. Build any load gradually. REVERT to contraindicated on any lumbar-base release or pain under flexion load.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="impact",
        reason="Axial impact loads activate L5/S1 osteochondrosis."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. The six-run progression is the live graded impact trial; keep impact doses low until it completes clean. REVERT on any lumbar signal from running or impact.",
        stage_cap=1, severity="caution", laterality="axial",
    ),
    MovementRule(
        movement="jumping",
        reason="Axial impact loads activate L5/S1 osteochondrosis."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. The six-run progression is the live graded impact trial; keep impact doses low until it completes clean. REVERT on any lumbar signal from running or impact.",
        stage_cap=1, severity="caution", laterality="axial",
    ),
    MovementRule(
        movement="box jump",
        reason="Axial impact loads activate L5/S1 osteochondrosis."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. The six-run progression is the live graded impact trial; keep impact doses low until it completes clean. REVERT on any lumbar signal from running or impact.",
        stage_cap=1, severity="caution", laterality="axial",
    ),
    # RUNNING: contraindicated below Stage 2, CAUTION from Stage 2 on.
    #
    # Corrected 2026-08-14, with the athlete's sign-off, and it is a correction
    # rather than a relaxation. check_movement only ever UPGRADES a verdict to
    # contraindicated when the stage is too low — `severity if stage_ok else
    # "contraindicated"` — so a rule already written at that severity can never
    # lift, whatever its stage_cap says. This rule carried stage_cap=2 and its
    # own reason text said "contraindicated in Stage 1", both of which say the
    # block was meant to end at Stage 2; the code could not express it, and
    # returned contraindicated at Stage 2 AND Stage 3 alike.
    #
    # It surfaced because Stage 2B introduces running (physio-confirmed
    # 2026-08-12; 10 km on 2026-10-11). The alternative — naming the sessions so
    # they miss the keyword — is the vocabulary failure this file has already
    # been burned by, where one hyphen turned a hard block into silence.
    #
    # REVERT CONDITION: any recurrence of the left Sartorius strain (twice, from
    # running overuse) or lumbar symptoms that track running volume. Then this
    # goes back to stage_cap=3, which is a real block again rather than a
    # no-op, and the running days come out of the plan.
    MovementRule(
        movement="running",
        reason=("Repetitive axial impact — contraindicated in Stage 1 with active "
                "osteochondrosis. From Stage 2: cleared with monitoring, and volume "
                "progresses conservatively given the twice-recurred left hip flexor."),
        stage_cap=2, severity="caution", laterality="axial",
    ),

    # ── Caution: Stage 1 — cleared from Stage 2 with monitoring ─────────────
    MovementRule(
        movement="bunkie",
        reason="Timed capacity holds to FORM failure, not burn — added 2026-08-17 with the "
               "day-28 Bunkie baseline so these five names cannot read as unknown, which "
               "looks exactly like cleared. The anterior power line is a feet-elevated "
               "front support: the brace must hold the low back neutral over the two "
               "annular tears, so the stop rule is the line breaking at the low back, "
               "instantly. All five lines: stop at line break, log the seconds, both sides.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="romanian deadlift",
        reason="Hip hinge with light load acceptable. Watch for right-side L5/S1 symptoms. No lumbar rounding.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="hip hinge",
        reason="Neutral-spine hip hinge is a rehab fundamental. Heavy versions require Stage 2+.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="squat",
        reason="Axial load in spinal flexion. Light goblet squat acceptable Stage 1; barbell squat Stage 3 only.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="good morning",
        reason="Loads the lumbar spine in flexion under load — annulus tear risk.",
        stage_cap=3, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="right lateral",
        reason="Right foraminal stenosis at L5/S1 — right lateral flexion narrows foramen further.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="left lateral",
        reason="Left dorsolateral protrusions L3-L5 — left lateral flexion under load risks annulus progression.",
        stage_cap=1, severity="caution", laterality="left",
    ),
    MovementRule(
        movement="side bend",
        reason="Lateral flexion in either direction has a mechanism here — right narrows the "
               "stenotic L5/S1 foramen, left loads the dorsolateral protrusions at L3/4 and L4/5. "
               "Generalises 'right lateral'/'left lateral' to catch named variants that don't "
               "spell out the word (e.g. yoga poses), the same way 'forward fold' generalises "
               "'seated forward fold'.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="rotation under load",
        reason="Rotational shear with active disc pathology at L3-L5.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="overhead press",
        reason="Lumbar extension moment under load compresses L5/S1 foramen.",
        stage_cap=2, severity="caution", laterality="axial",
    ),
    MovementRule(
        movement="bulgarian split squat",
        reason="Hip flexion loading — acceptable if neutral lumbar maintained. Monitor right-side symptoms.",
        stage_cap=2, severity="caution", laterality="right",
    ),

    # ── Cleared: safe across stages with correct technique ───────────────────
    MovementRule(
        movement="cat-cow",
        reason="Gentle controlled spinal mobility — standard L-spine rehab movement.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="bird-dog",
        reason="Neutral spine, contralateral stabilisation — primary rehab movement for L5/S1.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="dead bug",
        reason="Neutral spine core activation — no lumbar loading.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="glute bridge",
        reason="Hip extension without spinal compression — primary rehab movement.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="clamshell",
        reason="Glute medius activation — unloaded hip external rotation.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="pallof press",
        reason="Anti-rotation core — neutral spine, no compressive load.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="walking",
        reason="Low-impact movement — maintains tissue health without axial impact.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="swimming",
        reason="Unloaded spinal movement — ideal for active recovery.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="stationary cycling",
        reason="Cardiovascular without axial impact. Maintain neutral lumbar position.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="mcgill",
        reason="McGill Big 3 — evidence-based protocol for lumbar disc pathology.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="hip flexor stretch",
        reason="Psoas release — directly addresses L1-L4 tightness driving L5/S1 compression.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="piriformis stretch",
        reason="Piriformis release — reduces hip lateral rotator tension downstream of L-spine.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="face pull",
        reason="Posterior shoulder without lumbar load. Maintain upright posture.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="lateral band walk",
        reason="Glute medius activation — minimal spinal load.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),

    # ── Flexibility-skill vocabulary (added 2026-08-06) ──────────────────────
    #
    # WHY THESE EXIST. The rules above speak MOVEMENT DESCRIPTIONS; flexibility
    # source material speaks SKILL NAMES, and nothing bridged the two. Measured
    # across the Cluster A documents on 2026-08-06:
    #
    #     check_movement("Straddle Forward Fold", 2) -> contraindicated
    #     check_movement("Pancake", 2)               -> unknown
    #
    # The same movement, under two names, with opposite verdicts. 70 of 78
    # names in those documents returned `unknown`, and `unknown` is not a block
    # — services/yoga.py discards it. Every entry below is a bridge from a
    # skill name to a mechanism already ruled on above.
    #
    # SEVERITY IS CHOSEN FOR THE MOVEMENT AS NAMED, and most of these are
    # `caution` rather than contraindicated on purpose: the skill is trainable,
    # the DEFAULT EXECUTION is not, and the reason string carries the cue that
    # makes the difference. A blanket contraindication on "pancake" would block
    # the flat-back version this athlete is specifically training toward, which
    # is the wrong answer to the right worry.
    MovementRule(
        movement="weight behind",
        reason="Axial load carried behind the neck or across the shoulders while seated "
               "and folding. The load, not the athlete's own tilt, produces the depth — "
               "over covered annulus tears at L3/4 and L4/5, and with a placement the "
               "post-Latarjet right shoulder should not be holding either."
               " DOWNGRADED contraindicated -> caution 2026-08-17, the athlete's final decision: the MRI is ~1 year old (Nov 2025) and no longer determining. The seated-fold placement also sits on the post-Latarjet right shoulder, which is why this stays a LOUD caution. REVERT on any shoulder or lumbar signal.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="pancake",
        reason="Seated wide-leg fold. Trainable ONLY as a flat-back hinge from an "
               "elevated seat — the rounded-spine version is a seated forward fold and "
               "loads the covered annulus tears at L3/4 and L4/5. The elevation supplies "
               "the pelvic tilt; the spine must not. Never loaded, never strap-assisted.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="straddle",
        reason="Wide-leg seated position. Safe sitting tall or hinging with a flat back; "
               "the folded version is a seated forward fold. Also a wide-stance position "
               "— introduce slowly per the anterior hip capsule / pubic symphysis finding.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="pike",
        reason="Named in the source material as 'touching your toes; forward fold'. That "
               "execution is contraindicated end-range lumbar flexion. Trainable only as a "
               "flat-back hip hinge.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="lift off",
        reason="Repeated concentric lift out of a deep seated fold. From a rounded spine "
               "this is a bodyweight seated good-morning over two annulus tears. Only "
               "permissible from a flat back, and it is active hip flexion under iliopsoas "
               "load — cue neutral or slight internal rotation on the right.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="side split",
        reason="Wide-stance hip abduction under full bodyweight. Align the joint by "
               "EXTERNAL ROTATION, never by arching the lumbar spine — both routes reach "
               "the same joint position and only one collides with the L5/S1 "
               "retrolisthesis and narrowed right foramen.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="anterior tilt",
        reason="Forward pelvic tilt drives lumbar extension, which compresses the already "
               "narrowed right L5/S1 foramen. Already this athlete's habitual standing "
               "posture. Train the movement, never the end range, and never held under "
               "bodyweight at depth.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="pelvic rock",
        reason="Mid-range pelvic tilt drill. Safe as a movement rehearsal; the arched end "
               "of it is lumbar extension against the L5/S1 retrolisthesis. Train the "
               "movement, not the depth.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="horse stance",
        reason="Wide stance with the feet turned out, loaded, at depth. Active hip flexion "
               "in external rotation is the contractile trigger for the right snapping hip "
               "— cue neutral or slight internal rotation. Also a squat pattern under the "
               "wide-stance caution.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="cossack",
        reason="Deep unilateral squat in abduction and external rotation. Active, loaded "
               "right hip flexion past 60° — the snapping-hip trigger. Trailing leg "
               "straight also loads the proximal hamstring at the ischial tuberosity.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="tailors pose",
        reason="Seated butterfly against a wall. Passive floor-supported external rotation "
               "is NOT a snapping-hip risk position. Unloaded only: external load onto a "
               "passively held end-range hip is the practice the hypermobility profile "
               "specifically rules out, and the anterior-hip sensation reported here on "
               "2026-08-05 is an open question.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="butterfly",
        reason="Supine or seated soles-together hip abduction. Floor-supported and "
               "unloaded it is safe. The 2026-08-05 report of anterior HIP FLEXOR "
               "sensation rather than adductor stretch is unresolved — do not add load "
               "until that is answered.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="frog",
        reason="Deep hip flexion with abduction. Floor-supported and self-limited, but it "
               "is the same anterior-hip compression question as the butterfly position.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="nerve glide",
        reason="Neurodynamic technique. Legitimate, but this athlete has moderate right "
               "L5/S1 foraminal stenosis and every symptom log to date records no neural "
               "signs — electric or burning sensations are an escalation to the "
               "physiotherapist, never a training variable. Physio-directed only.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="copenhagen",
        reason="Side-lying adductor plank. Clean mechanically — spine neutral, no lumbar "
               "flexion or extension, no axial load. The caution is dose: last performed "
               "May/June 2025 at 30 s × 3, and a back injury plus a full rehab block sit "
               "between then and now.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="adductor squeeze",
        reason="Isometric adduction at a controlled width. No spinal load, no end-range "
               "passive hold — the controlled-range strength work the hypermobility "
               "profile asks for in place of passive stretching.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="side leg raise",
        reason="Active hip abduction, spine neutral. Loads glute medius, which the "
               "biomechanical assessment lists as overactive and right-dominant — release "
               "before activating, per the pre-session protocol.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="banded abduction",
        reason="Resisted hip abduction. Same glute medius sequencing note as the side leg "
               "raise: inhibit before you activate.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="hip abduction",
        reason="Active or resisted hip abduction, spine neutral. Loads glute medius, listed "
               "as overactive and right-dominant and named as the primary anchor driving "
               "joint compression through the chain — release before activating.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="external rotation",
        reason="At the HIP: passive, floor- or seat-supported external rotation is NOT a "
               "snapping-hip risk position — confirmed 2026-08-05 — but it becomes one the "
               "moment the hip flexes past 60° under its own muscular effort. At the "
               "SHOULDER: external rotation combined with abduction is the apprehension "
               "position for the anterior-stabilised right side.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="abduction",
        reason="Moving a limb away from the midline. At the hip this loads glute medius, "
               "listed as overactive and right-dominant — release before activating. At the "
               "shoulder, abduction with external rotation is the apprehension position "
               "post-Latarjet.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="triangle",
        reason="The triangle side-split position — hips on a separate line to the feet. "
               "Align the joint by turning the legs out, never by arching the lower back.",
        stage_cap=1, severity="caution", laterality="right",
    ),

    # ── The mandatory pre-session release protocol ───────────────────────────
    # From patient_profile.py, not from any flexibility source. Named here so
    # the protocol that must precede EVERY session resolves like anything else
    # — it appears at the head of every cluster stack and returned `unknown`.
    # Named by their HEADS as the protocol writes them, because a cleared rule
    # must head the name it clears — it may not match a fragment buried inside
    # one. "self release" alone would never fire on "Upper glute / TFL
    # self-release".
    MovementRule(
        movement="upper glute",
        reason="Upper glute / TFL self-release. Inhibitory, unloaded, and the first half "
               "of the mandatory inhibit-then-activate sequence. Right side runs tighter.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="piriformis contract",
        reason="Piriformis contract-relax (PNF). Self-generated and controlled; part of "
               "the mandatory pre-session release protocol.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="ischial tuberosity",
        reason="Ischial tuberosity hamstring release. Targets the proximal hamstring "
               "attachment listed as overactive; inhibitory rather than loading.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="self release",
        reason="Soft-tissue self-release. Inhibitory, unloaded, and the first half of the "
               "mandatory inhibit-then-activate sequence.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="contract relax",
        reason="PNF contract-relax. Self-generated, controlled, and part of the mandatory "
               "pre-session release protocol.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="hip capsule stretch",
        reason="Right posterior hip capsule mobilisation, cross-body. UNILATERAL — right "
               "side only, per the biomechanical assessment.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="hamstring release",
        reason="Ischial tuberosity soft-tissue release. Targets the proximal hamstring "
               "attachment listed as overactive; inhibitory rather than loading.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="tendon path",
        reason="Coxa Saltans tendon-path drill — takes the right iliopsoas through its "
               "path deliberately rather than letting it snap. Right side only, and only "
               "when the session loads the right hip.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="hip tilt",
        reason="Pelvic tilt drill. Forward tilt drives lumbar extension against the L5/S1 "
               "retrolisthesis and the narrowed right foramen. Mid-range only; never held "
               "at the arched end.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="terminal knee extension",
        reason="Banded knee extension for VMO. Knee-local, no spinal or hip load. Named "
               "here so it is not caught by the lumbar 'back extension' rule.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),

    # ── The accessory session ────────────────────────────────────────────────
    # Added 2026-08-16 with services/accessory.py. Every one of these movements
    # returned `unknown` before this block existed, and `unknown` is not a block
    # — the same silence that let a loaded lumbar-flexion movement through on a
    # single hyphen. A hang in particular is a shoulder prescription on a twice-
    # operated joint, so it is ruled before it is ever offered.
    MovementRule(
        movement="hang",
        reason="Hanging from a bar. BOTH ARMS ALWAYS — a single-arm hang is never "
               "prescribed. The right shoulder has had three anterior dislocations, a "
               "failed capsular wrap and a Latarjet on a shallow glenoid, and its "
               "stability is now muscular rather than ligamentous, so a passive hang asks "
               "the restraint that is not there to hold the joint. Enter with the "
               "shoulders ACTIVE and the feet taking weight; never a shrug-and-drop into "
               "the bottom of the sag. Stop on the right for the session at any hard, "
               "abrupt, unspringy end-feel, any apprehension, or any instability "
               "sensation. Cleared to progress only on two clean weeks per step.",
        stage_cap=2, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="pec scar release",
        reason="Pectoral and surgical-scar self-release, right side. Physio-cleared "
               "2026-08-10 for self-directed use and expected to OUTPERFORM stretching "
               "here — the diagnosis is scar adhesion plus high resting tone in a "
               "shortened range, not a short muscle. Inhibitory and unloaded. Never press "
               "into the hollow of the armpit, and move off anything that pulses or sends "
               "sensation into the arm.",
        stage_cap=1, severity="cleared", laterality="right",
    ),
    MovementRule(
        movement="anterior shoulder reciprocation",
        reason="Active anterior-wall work on the stabilised right shoulder — press in, "
               "then rotate out under its own power and hold. THE ARM STAYS LOW "
               "THROUGHOUT: elbow on knee, elbow and shoulder in one vertical line. Never "
               "external rotation at 90° abduction, which is the apprehension position "
               "the Latarjet exists to protect. Ramp in and out over 3-5 s at ~50% "
               "effort. Stop on any hard, abrupt end-feel on the outward rotation — on a "
               "stabilised shoulder that restriction may be doing load-bearing work.",
        stage_cap=1, severity="caution", laterality="right",
    ),
    MovementRule(
        movement="standing hip flexor",
        reason="Standing hip-flexor release. Lengthens the deep right hip flexors and "
               "psoas, which the imaging names as amplifying the L5/S1 compression. Keep "
               "the pelvis TUCKED — the range comes from the hip, and letting it come "
               "from the lower back is the arch this exercise exists to undo.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="thoracic extension",
        reason="Extension over a support, THORACIC ONLY. The mid-back is the target; the "
               "lower back is not, and end-range lumbar extension is contraindicated "
               "against the L5/S1 retrolisthesis and the narrowed right foramen. Ribs "
               "down, no rib flare, and stop where the lower back starts to take it.",
        stage_cap=1, severity="caution", laterality="axial",
    ),
    MovementRule(
        movement="prone decompression",
        reason="Prone decompression breathing. Unloaded, position-only, and the "
               "down-regulating close to a session rather than a stressor in it.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    # Five names the accessory session emits that were already live in the block
    # and already returning `unknown`. They are ruled here because this session
    # offers them, not because they are new. ⚠ Sixteen OTHER Stage 2B names are
    # still unknown — a pre-existing gap, out of scope here, and tracked
    # separately rather than half-closed.
    MovementRule(
        movement="anterior hip pressure",
        reason="Sustained pressure at the front of the hip. Inhibitory rather than "
               "loading, and prescribed by the physiotherapist on 2026-08-10 to release "
               "what sitting holds short. CAUTION rather than cleared for one reason: the "
               "inner front of the hip carries the leg's main artery and nerve. Stay on "
               "the OUTER half, never press where you feel a pulse, and stop on any "
               "tingling, numbness or electric sensation down the leg.",
        stage_cap=1, severity="caution", laterality="bilateral",
    ),
    MovementRule(
        movement="single leg glute bridge",
        reason="Single-leg glute bridge. Glute max activation — the primary underactive "
               "muscle in the profile — unloaded, supine, spine neutral. Named separately "
               "because a cleared rule must head the name it clears, and 'glute bridge' "
               "does not head this one.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="full side bridge",
        reason="Full side bridge. Lateral trunk endurance in a neutral spine, one of "
               "McGill's own three, with no flexion and no rotation under load. Named "
               "separately from the modified version for the same heading reason.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="side bridge",
        reason="Side bridge, any variant. Lateral trunk endurance in a neutral spine — "
               "the flexion-free alternative to the contraindicated sit-up and crunch.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="prone y raise",
        reason="Prone Y-raise. Lower-trapezius strengthening, which is the standing "
               "requirement for maintaining the Latarjet repair's stability, and the one "
               "scapular item the log shows genuinely lapsing. Keep the low back relaxed "
               "— this is a shoulder-blade movement, not a back extension.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="scapular wall slide",
        reason="Scapular wall slide. Upward rotation and lower trapezius against a wall, "
               "unloaded, arms tracking within contact. Stop where contact is lost rather "
               "than arching off neutral to get the arms higher.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
    MovementRule(
        movement="scapular retraction",
        reason="Scapular retraction isometric. Physio-approved 2026-08-10, both sides, "
               "right-biased. LOAD IN NEUTRAL ONLY, never in the head-down-and-right "
               "position that provokes the symptom, and as short repeated efforts rather "
               "than a sustained hold — the left trapezius is perfusion-limited, where "
               "sustained low-level contraction is the provocative mechanism.",
        stage_cap=1, severity="cleared", laterality="bilateral",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Stage-specific volume caps and ACWR ceilings (single source of truth)
#  engine.py references these via get_stage_constraints()
# ─────────────────────────────────────────────────────────────────────────────

STAGE_CONSTRAINTS: dict[int, dict] = {
    1: {
        "label":            "Rehab — Tissue Tolerance",
        "acwr_ceiling":     1.2,
        "volume_cap_pct":   0.70,   # max 70% of projected baseline volume
        "rpe_ceiling":      7,      # RPE hard cap per session
        "session_freq_max": 4,      # max sessions per week
        "description":      "Conservative tissue tolerance phase. Strict ACWR ceiling.",
    },
    2: {
        "label":            "Transition — Work Capacity",
        "acwr_ceiling":     1.3,
        "volume_cap_pct":   0.90,
        "rpe_ceiling":      8,
        "session_freq_max": 5,
        "description":      "Graduated loading. Rehab movements blend into training.",
    },
    3: {
        "label":            "Performance & Growth",
        "acwr_ceiling":     1.5,
        "volume_cap_pct":   1.0,
        "rpe_ceiling":      10,
        "session_freq_max": 6,
        "description":      "Full performance focus. Injury baseline passive background watcher.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def check_movement(movement_name: str, current_stage: int) -> dict:
    """
    Evaluate a movement against the deterministic rule set.

    Returns:
        {
            severity:  "contraindicated" | "caution" | "cleared" | "unknown",
            reason:    str,
            laterality: str,
            stage_available: int | None,  (which stage it becomes appropriate)
        }
    """
    name_lower = normalise_movement(movement_name)

    # Find the strictest matching rule.
    #
    # A CLEARED rule must NAME the movement — it may match the whole name or
    # head it, never appear as a fragment buried inside a description.
    # Measured 2026-08-06: the assessment battery's most flexion-loaded item
    # reads "hands walking forward on the floor", which contains the substring
    # "walking" and therefore matched the `walking` CLEARED rule — returning an
    # affirmative "Low-impact movement — maintains tissue health" on a movement
    # that loads two covered annulus tears. A wrong green light is worse than
    # silence, because silence at least reads as "apply clinical judgment".
    #
    # Head-matching, not exact, so ordinary variants keep their clearance:
    # "Glute Bridge (Single Leg)" and "Pallof Press Hold (Doorframe)" still
    # clear. A cleared rule that fails to fire degrades to `unknown`, which is
    # the safe direction; a cleared rule that fires wrongly is not.
    #
    # Contraindicated and caution rules keep the permissive substring match:
    # over-catching there fails safe, and the generalising keywords
    # ("forward fold" catching named variants) depend on it.
    matched: list[MovementRule] = []
    for rule in MOVEMENT_RULES:
        keyword = normalise_movement(rule.movement)
        if rule.severity == "cleared":
            hit = _heads_the_name(name_lower, keyword)
        else:
            hit = keyword in name_lower or name_lower in keyword
        if hit:
            matched.append(rule)

    if not matched:
        return {
            "severity":        "unknown",
            "reason":          "No matching rule found. Apply clinical judgment.",
            "laterality":      "bilateral",
            "stage_available": None,
        }

    # Take the most conservative matched rule
    priority = {"contraindicated": 0, "caution": 1, "cleared": 2, "unknown": 3}
    strictest = min(matched, key=lambda r: priority.get(r.severity, 3))

    # Check if this movement is available in the current stage
    stage_ok = current_stage >= strictest.stage_cap

    return {
        "severity":        strictest.severity if stage_ok else "contraindicated",
        "reason":          strictest.reason,
        "laterality":      strictest.laterality,
        "stage_available": strictest.stage_cap,
        "stage_ok":        stage_ok,
    }


def get_contraindicated_always() -> list[str]:
    """Movements that are contraindicated regardless of stage."""
    return [r.movement for r in MOVEMENT_RULES if r.severity == "contraindicated" and r.stage_cap == 1]


def get_cleared_for_stage(stage: int) -> list[str]:
    """Movements explicitly cleared at or below the given stage."""
    return [r.movement for r in MOVEMENT_RULES if r.severity == "cleared" and r.stage_cap <= stage]


def get_caution_movements(stage: int) -> list[str]:
    """Movements in the caution zone for the given stage."""
    return [
        r.movement for r in MOVEMENT_RULES
        if r.severity == "caution" and r.stage_cap <= stage
    ]


def get_stage_constraints(stage: int) -> dict:
    """Return stage-specific volume/load constraints."""
    return STAGE_CONSTRAINTS.get(stage, STAGE_CONSTRAINTS[1])


def movement_safety_summary(stage: int) -> dict:
    """
    Return a full safety summary for the given stage.
    Used by the Autoregulation page and as context for AI movement risk assessment.
    """
    return {
        "stage":              stage,
        "constraints":        get_stage_constraints(stage),
        "always_contraindicated": get_contraindicated_always(),
        "cleared":            get_cleared_for_stage(stage),
        "caution":            get_caution_movements(stage),
    }

# ═════════════════════════════════════════════════════════════════════════════
#  CONTRAINDICATION EXITS — added 2026-08-17, on the athlete's challenge.
# ═════════════════════════════════════════════════════════════════════════════
#
# He asked two questions the list could not answer: "at what stage do any of
# these items get opened?" (answer: NEVER — no stage, date or measurement
# re-opens a contraindicated rule) and "there is no physio appointment, so
# these will just stay unanswered — we need a better way."
#
# Both stick. The 15 contraindicated rules rest on one undated MRI, the block
# is authored under them (so they are invisible and self-confirming), and by
# the standard the findings now meet — every claim carries a test — they were
# unfalsifiable. This table is the fix: every contraindicated movement carries
# what it rests on, what it costs against the athlete's actual goals, and the
# EXIT — evidence obtainable by the athlete ALONE, no physio required, that
# would downgrade it. The template is the running rule: graded exposure with a
# pre-declared stop condition, downgraded on the result with the decision
# recorded.
#
# THIS TABLE CHANGES NO VERDICT. check_movement never reads it. A downgrade
# happens the way running's did — an explicit severity edit, with the exit
# evidence quoted in the commit — never as a side effect. That is what keeps
# "never weaken a guardrail" true while ending "held forever by default":
# rules are now held ON somеthing, and each one says what.
#
# Shared exit protocols. After the 2026-08-17 downgrade only the deadlift
# family still uses one; _EXIT_FLEXION and _EXIT_IMPACT are retained as the
# DESIGNS of the graded trials the downgraded rules now recommend in their
# own reason texts (the flexion exposure has a start decision pending, the
# impact trial is the running block already underway).
_EXIT_FLEXION = (
    "GRADED LUMBAR-FLEXION EXPOSURE, 4 weeks, the conservative-care standard "
    "for covered annular tears: (1) unloaded seated folds — ALREADY TOLERATED, "
    "measured 2026-08-17: five slow folds, zero releases, zero pain; "
    "(2) 2 weeks of daily bodyweight fold-and-return, 10 slow reps; "
    "(3) 2 weeks adding light load held at the chest. STOP: any lumbar-base "
    "release or pain — finding #3's own test is the instrument, re-run weekly "
    "during the trial. Clean at 4 weeks → downgrade to caution with a load "
    "ceiling, which also unblocks Cluster B's pike via the flat-back route "
    "the pancake already took."
)
_EXIT_LOAD_CEILING = (
    "THE RULE IS REALLY A LOAD CEILING WEARING A NAME. The athlete already "
    "hinges 45 kg and a 52.5 kg top set is authored for day 22 — 'deadlift' "
    "is not banned, the barbell magnitudes are. EXIT: symptom-free top-set "
    "progression across blocks (the day-22 sets are the first data point); "
    "when loads exceed what dumbbells carry, the barbell enters at the same "
    "weight the dumbbells left, stepped, with the RDL's existing stop "
    "condition (any back signal ends the set). Downgrade then names the "
    "ceiling instead of the implement."
)
_EXIT_IMPACT = (
    "THE SIX-RUN PROGRESSION IS THE GRADED IMPACT TRIAL, already running. "
    "Running is axial impact at ~2.5x bodyweight per stride, thousands of "
    "strides per session — a completed block of it with zero lumbar signal "
    "is stronger impact evidence than any single jump test. EXIT: the "
    "running introduction completes clean (stage_2b_exit_criteria's own "
    "running_tolerance line) → downgrade jumping/impact to caution with "
    "dose limits. Note the 10 km build needs no plyometrics, so this exit "
    "is about honesty, not access."
)
_EXIT_ZERO_COST = (
    "NO EXIT PROTOCOL, BY CHOICE NOT NEGLECT: no goal on record wants this "
    "movement, so running a graded-exposure trial to earn it back would be "
    "risk spent on nothing. Held at zero cost. If a goal ever names it, an "
    "exit is designed then — this entry is re-visited at every block build."
)

#: movement (must match a contraindicated MOVEMENT_RULES entry exactly) →
#: {rests_on, cost_today, exit, single_person}. Pinned both ways by
#: tests/test_contraindication_exits.py: every contraindicated rule needs an
#: entry here, and every entry here must name a contraindicated rule.
CONTRAINDICATION_EXITS: dict[str, dict] = {
    "heavy deadlift": {
        "rests_on": "L5/S1 osteochondrosis + retrolisthesis (MRI, Nov 2025)",
        "cost_today": "None — DB RDL at 45 kg runs freely; only barbell magnitudes are held.",
        "exit": _EXIT_LOAD_CEILING, "single_person": True,
    },
    "barbell deadlift": {
        "rests_on": "L5/S1 osteochondrosis + retrolisthesis (MRI, Nov 2025)",
        "cost_today": "None yet — becomes real when progression outgrows dumbbells.",
        "exit": _EXIT_LOAD_CEILING, "single_person": True,
    },
    "conventional deadlift": {
        "rests_on": "L5/S1 osteochondrosis + retrolisthesis (MRI, Nov 2025)",
        "cost_today": "None yet — same ceiling as the barbell entry.",
        "exit": _EXIT_LOAD_CEILING, "single_person": True,
    },
}

#: The twelve that LEFT this table on 2026-08-17, the athlete's final decision:
#: "Keep 1-3, remove everything else from the list." Each was downgraded to
#: caution — never deleted — with its mechanism text intact and a dated REVERT
#: condition written into its own reason string, which is where the exit
#: knowledge now lives. The deadlift family stays contraindicated at his own
#: instruction, which is worth noticing: shown the full list, he kept the
#: three with the highest axial load on the L5/S1 segment.
DOWNGRADED_2026_08_17: tuple[str, ...] = (
    "hyperextension", "back extension",
    "seated forward fold", "forward fold", "toe touch",
    "sit up", "crunch", "leg press",
    "impact", "jumping", "box jump",
    "weight behind",
)


