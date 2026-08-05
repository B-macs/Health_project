"""
services/yoga.py — Yoga catalogue: poses, clinical safety tags, and the
deterministic rest-day suggestion rule. Framework-agnostic (no Streamlit, no I/O).

Every pose is cross-checked against services.rules.MOVEMENT_RULES (the app's
single source of truth for movement safety) and, where a pose's laterality
matters, against the patient's biomechanical findings in patient_profile.py —
see docs/training/Yoga_Library.md for the full pose-by-pose clinical rationale.

Unlike services.rules, a "contraindicated" tag here does not block anything —
these are externally-sourced videos the user chooses to follow, not exercises
this app prescribes. The tags exist so the UI can surface an informed caution
before the user starts.

LATERALITY CONVENTION — a "(Right)"/"(Left)" suffix names the FRONT (or worked)
leg, never the side receiving the stretch. For a pigeon those are the same leg;
for a LUNGE they are OPPOSITE legs — "Deep Lunge (Right)" is right-foot-forward
and therefore stretches the LEFT hip flexor. Getting this backwards silently
moves every laterality-specific caution onto the wrong side, which matters here
because the Coxa Saltans mechanism (patient_profile.py finding #4) and the
post-Latarjet shoulder (finding #6) are both RIGHT-only. Resolved 2026-08-05
against the athlete's own account of the video; the `option_note` fields are the
internal evidence ("grab your left foot" appears on the Right hip opener, i.e.
the left leg is the trailing one).

ROM tags are SAFETY, not difficulty. A pose being `cleared` says nothing about
how far into it this athlete can get — that was measured separately on
2026-08-05 and lives in docs/training/Yoga_Library.md, because it is
observational data about one person rather than a rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from services import rules as _rules

_SEVERITY_RANK = {"contraindicated": 0, "caution": 1, "cleared": 2, "unknown": 3}


@dataclass
class YogaPose:
    # A "(Right)"/"(Left)" suffix names the FRONT/worked leg — see the module
    # docstring's LATERALITY CONVENTION. For lunges that is the OPPOSITE leg to
    # the one being stretched; do not author a side-specific safety_note without
    # checking which leg the mechanism actually lands on.
    name: str
    start_seconds: int
    hold_seconds: int
    safety: str            # "cleared" | "caution" | "contraindicated"
    safety_note: str = ""  # rationale — required for caution/contraindicated, optional otherwise
    option_note: str = ""  # e.g. "Option to grab your left foot"


@dataclass
class YogaSession:
    slug: str
    name: str
    video_url: str
    estimated_rpe: int          # 1-10, feeds session_au = rpe * duration_minutes
    primary_focus: list[str]    # e.g. ["spine_mobility", "hip_opening", "relaxation"]
    intensity: str              # "low" | "moderate" | "high"
    suitable_for: list[str]     # subset of "rest_day", "active_rest_day"
    poses: list[YogaPose] = field(default_factory=list)

    @property
    def total_duration_minutes(self) -> int:
        last = self.poses[-1]
        return -(-(last.start_seconds + last.hold_seconds) // 60)  # ceil division

    @property
    def session_au(self) -> float:
        return float(self.estimated_rpe * self.total_duration_minutes)

    def cautions(self, stage: int = 1) -> list[tuple[YogaPose, str, str]]:
        """(pose, severity, note) for every pose whose effective safety != cleared."""
        out = []
        for pose in self.poses:
            severity, note = effective_safety(pose, stage)
            if severity != "cleared":
                out.append((pose, severity, note))
        return out


def effective_safety(pose: YogaPose, stage: int = 1) -> tuple[str, str]:
    """Stricter of the pose's authored tag and services.rules' keyword match —
    defense in depth so a future services.rules addition is picked up here too
    without needing this catalogue to be re-authored."""
    candidates = [(pose.safety, pose.safety_note)]
    rule_result = _rules.check_movement(pose.name, stage)
    if rule_result["severity"] != "unknown":
        candidates.append((rule_result["severity"], rule_result["reason"]))
    return min(candidates, key=lambda c: _SEVERITY_RANK.get(c[0], 3))


def _t(mm_ss: str) -> int:
    m, s = mm_ss.split(":")
    return int(m) * 60 + int(s)


YOGA_LIBRARY: list[YogaSession] = [
    YogaSession(
        slug="hip_spine_flow_15min",
        name="15-Minute Hip & Spine Mobility Flow",
        video_url="https://www.youtube.com/watch?v=HzXkMnvqojE",
        estimated_rpe=3,
        primary_focus=["spine_mobility", "hip_opening", "hamstring", "relaxation"],
        intensity="low",
        suitable_for=["rest_day", "active_rest_day"],
        poses=[
            YogaPose(
                "Seated Cross-Legged Side Bend (Shoulder Drop)", _t("00:20"), 30, "caution",
                "Seated lateral flexion with rotation — the SAME mechanism as the two "
                "Seated Side Stretches below, and it carries the same caution: bending "
                "right narrows the stenotic right L5/S1 foramen, bending left loads the "
                "dorsolateral protrusions at L3/4 and L4/5. Keep it light and "
                "self-supported. Corrected 2026-08-05 — this was authored as "
                "'Spine Mobilisation' and tagged `cleared` on the assumption it was a "
                "cat-cow-family spinal mobilisation. It is not. Per the athlete: "
                "cross-legged, hand resting on the knee, drawing the shoulder down "
                "toward it, repeated on the other side.",
            ),
            YogaPose(
                "Seated Side Stretch (Right)", _t("01:00"), 30, "caution",
                "Gentle lateral flexion — right foraminal stenosis at L5/S1. "
                "Keep it light and self-supported; don't force the reach.",
            ),
            YogaPose(
                "Seated Side Stretch (Left)", _t("01:40"), 30, "caution",
                "Gentle lateral flexion — left dorsolateral protrusions at L3/4, L4/5. "
                "Keep it light and self-supported.",
            ),
            YogaPose(
                "90/90 Hip Rotation", _t("02:20"), 30, "caution",
                "Passes the right hip through flexion + external rotation — the position "
                "family that triggers the documented right-hip snap (Coxa Saltans, "
                "patient_profile.py finding #4). Bias toward neutral/internal rotation "
                "on the right side. Kept at `caution` rather than downgraded even though "
                "the athlete measured this as one of the EASIEST poses in the flow on "
                "2026-08-05 with no snap: finding #4's trigger is ACTIVE hip flexion "
                "under iliopsoas load (standing knee lift, dead bug), and a passive "
                "floor-supported position does not reproduce it. The mechanism is "
                "unchanged, this position just does not load it.",
            ),
            YogaPose(
                "Butterfly Forward Fold", _t("03:00"), 30, "contraindicated",
                "Seated forward fold — end-range lumbar flexion loads the covered "
                "annulus tears at L3/4 and L4/5. Sit tall instead, or hinge only from "
                "the hips with a flat back.",
            ),
            YogaPose(
                "Walk the Dog (Down Dog pedaling)", _t("03:40"), 30, "caution",
                "Mild spinal flexion under bodyweight load. Keep knees soft and back "
                "flat rather than forcing a hamstring-driven round.",
            ),
            YogaPose(
                "Deep Lunge (Right)", _t("04:20"), 30, "cleared",
                "Right foot FORWARD, so this stretches the LEFT hip flexor / psoas — "
                "addresses the psoas hypertonicity noted in the MRI findings. Keep the "
                "pelvis neutral; arching the low back is how depth gets bought here, and "
                "the athlete's sense of 'neutral' is calibrated to a habitual anterior "
                "tilt (symptom_log 2026-07-06).",
            ),
            YogaPose(
                "Deep Lunge Hip Opener (Right)", _t("05:00"), 30, "caution",
                "Reach/backbend combination risks end-range lumbar extension and rotation. "
                "Keep the reach modest.",
                option_note="Option to grab your left foot",
            ),
            YogaPose(
                "Half Pigeon Pose (Right)", _t("05:40"), 30, "caution",
                "Front-leg hip flexion + external rotation on the right — the documented "
                "Coxa Saltans mechanism (finding #4). Keep a neutral/slight-internal-"
                "rotation bias; ease out if it snaps or pinches. Athlete reported NO "
                "pinch or click here on 2026-08-05 and scored it identically to the left "
                "side, consistent with the 90/90 note above — passive positioning does "
                "not load the tendon path. Retained as `caution` on the same reasoning.",
            ),
            YogaPose("Seated Twist (Left)", _t("06:20"), 30, "cleared",
                      "Gentle unloaded rotation — same family as the thread-the-needle "
                      "stretch already used in the release protocol. Keep it gentle."),
            YogaPose(
                "Down Dog", _t("07:00"), 30, "caution",
                "The load here is SHOULDER GIRDLE, not hamstring or spine — 30s of "
                "bodyweight through a post-Latarjet right shoulder (finding #6) and the "
                "left scapular retractors already flagged in the interscapular endurance "
                "pattern (symptom_log 2026-08-03). Athlete reports the right shoulder "
                "reaching back with a small whole-body twist to the right, i.e. the same "
                "compensation finding #6 describes. Measured burn onset is 50-60s, so a "
                "30s hold sits BELOW threshold — this is why the pose is tolerable, and "
                "why lengthening it would change its character. Keep knees soft and back "
                "flat for the secondary spinal-flexion component.",
            ),
            YogaPose(
                "Deep Lunge (Left)", _t("07:40"), 30, "cleared",
                "Left foot FORWARD, so this stretches the RIGHT hip flexor / TFL — the "
                "side listed as overactive in patient_profile.py's imbalances. The "
                "previous note here ('no right-side-specific concern on this leg') was "
                "written against the opposite laterality convention and was backwards; "
                "corrected 2026-08-05. Measured the same as the right-foot-forward "
                "version by the athlete, i.e. the asymmetry does NOT appear in a passive "
                "lunge — keep the pelvis neutral rather than arching for depth.",
            ),
            YogaPose(
                "Deep Lunge Hip Opener (Left)", _t("08:20"), 30, "caution",
                "Reach/backbend combination risks end-range lumbar extension and rotation. "
                "Keep the reach modest.",
                option_note="Option to grab your right foot",
            ),
            YogaPose(
                "Half Pigeon Pose (Left)", _t("09:00"), 30, "cleared",
                "No right-hip-specific mechanism on this side. Still avoid forcing external "
                "rotation to end range.",
            ),
            YogaPose("Seated Twist (Right)", _t("09:40"), 30, "cleared",
                      "Gentle unloaded rotation. Keep it gentle."),
            YogaPose(
                "Straddle Forward Fold", _t("10:20"), 30, "contraindicated",
                "Seated wide-leg forward fold — end-range lumbar flexion loads the covered "
                "annulus tears. Sit tall, or hinge only from the hips with a flat back.",
            ),
            YogaPose(
                "Knee to Chest (Right)", _t("11:00"), 30, "cleared",
                "Supine, unloaded flexion — decompressive for the L5/S1 facet base "
                "(finding #3's training implication).",
            ),
            YogaPose(
                "Lying Twist (Right)", _t("11:40"), 30, "cleared",
                "Supine, unloaded rotation — decompressive, same family as thread-the-needle.",
                option_note="Option to extend your right leg",
            ),
            YogaPose(
                "Knee to Chest (Left)", _t("12:20"), 30, "cleared",
                "Supine, unloaded flexion — decompressive.",
            ),
            YogaPose(
                "Lying Twist (Left)", _t("13:00"), 30, "cleared",
                "Supine, unloaded rotation — decompressive.",
                option_note="Option to extend your left leg",
            ),
            YogaPose(
                "Happy Baby", _t("13:40"), 30, "cleared",
                "Supine hip flexion, fully supported — decompressive for the low back.",
            ),
            YogaPose("Deep Relaxation (Savasana)", _t("14:20"), 30, "cleared"),
        ],
    ),
]


def get(slug: str) -> YogaSession | None:
    return next((y for y in YOGA_LIBRARY if y.slug == slug), None)


def suggest_for_day(day_kind: str) -> YogaSession | None:
    """day_kind: 'rest_day' | 'active_rest_day'. First catalogue entry tagged
    for that day kind — deterministic; becomes a real ranking once there's more
    than one candidate worth ranking."""
    return next((y for y in YOGA_LIBRARY if day_kind in y.suitable_for), None)
