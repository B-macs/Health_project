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
"""

from __future__ import annotations

from dataclasses import dataclass, field

from services import rules as _rules

_SEVERITY_RANK = {"contraindicated": 0, "caution": 1, "cleared": 2, "unknown": 3}


@dataclass
class YogaPose:
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
            YogaPose("Spine Mobilisation", _t("00:20"), 30, "cleared"),
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
                "Passes the right hip through flexion + external rotation — the exact "
                "position that triggers the documented right-hip snap (Coxa Saltans, "
                "patient_profile.py finding #4). Bias toward neutral/internal rotation "
                "on the right side.",
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
                "Hip flexor / psoas stretch — directly addresses the psoas hypertonicity "
                "noted in the MRI findings. Keep the pelvis neutral, avoid arching the low back.",
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
                "rotation bias; ease out if it snaps or pinches.",
            ),
            YogaPose("Seated Twist (Left)", _t("06:20"), 30, "cleared",
                      "Gentle unloaded rotation — same family as the thread-the-needle "
                      "stretch already used in the release protocol. Keep it gentle."),
            YogaPose(
                "Down Dog", _t("07:00"), 30, "caution",
                "Mild spinal flexion under bodyweight load. Keep knees soft and back flat.",
            ),
            YogaPose(
                "Deep Lunge (Left)", _t("07:40"), 30, "cleared",
                "Hip flexor / psoas stretch. Keep the pelvis neutral, avoid arching the low back.",
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
