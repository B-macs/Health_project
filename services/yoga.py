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
    # An open question this pose is the natural instrument for — surfaced when
    # the pose comes up so the answer is captured in the position that produced
    # it, rather than recalled afterwards. A finding measured ONCE is a snapshot;
    # this is what turns it into a re-measurement. Empty for most poses: a retest
    # on every pose is a retest on none.
    retest: str = ""


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

    def retests(self) -> list[tuple[YogaPose, str]]:
        """(pose, question) for every pose carrying an open question to re-answer.

        Deliberately separate from cautions(): a caution is a standing safety
        statement, a retest is a one-shot measurement request that should be
        closed out or re-dated once answered. Ordered by pose sequence so the
        UI can surface each one at the moment it is answerable.
        """
        return [(p, p.retest) for p in self.poses if p.retest]

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
                retest="Is the restriction still in the HIPS rather than the spine, and is "
                       "the arm still unable to straighten? Baseline 2026-08-05: 40/100, "
                       "'only can go about 60-70 percent down, restriction in hips', arm "
                       "would not straighten at all. This is the pose that first showed "
                       "the seated posterior-tilt pattern, so it is the cheapest place to "
                       "see whether that pattern is moving. Also confirm the movement is "
                       "still as described — the whole re-tag depends on it.",
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
                retest="Time the burn. Baseline 2026-08-05: onset 50-60s, with the right "
                       "shoulder reaching back and a small whole-body twist to the right. "
                       "This is the ONLY quantified endurance figure for the interscapular "
                       "gap (symptom_log 2026-08-03) and physio_brief_2026-08-16.md §11 "
                       "asks for the hold prescription to be set against it — so a second "
                       "reading is worth more here than anywhere else in the flow. Note "
                       "whether onset moves and whether the rightward twist persists.",
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
                "Keep the reach modest. This is the pose where the RIGHT arm reaches back "
                "into extension + external rotation — the apprehension-adjacent position "
                "for the post-Latarjet shoulder (finding #6). It was predicted to be "
                "range-limited on 2026-08-05 and was not ('right arm can reach the back "
                "leg with ease'), so the range question is settled; what is NOT settled is "
                "that finding #6 calls that stability maintenance-dependent.",
                option_note="Option to grab your right foot",
                retest="Does the right shoulder still reach the back foot with ease, and "
                       "does the front of the joint feel stable there? Baseline 2026-08-05: "
                       "reaches easily, no instability reported, quad is the limiter at "
                       "46/100. Finding #6 says right-shoulder stability is "
                       "maintenance-dependent and regresses when training lapses — so this "
                       "is a cheap unloaded check on whether that has started, and a change "
                       "here is a signal well before a loaded one appears.",
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
    YogaSession(
        slug="shoulder_scapula_neck_flow_16min",
        name="16-Minute Shoulder, Scapula & Neck Flow",
        video_url="",
        estimated_rpe=3,
        primary_focus=["shoulder_flexion", "thoracic_extension", "scapular_control",
                        "cervical", "relaxation"],
        intensity="low",
        suitable_for=["rest_day", "active_rest_day"],
        # ── AUTHORED 2026-08-05, and the hold durations are the whole story ──
        #
        # Every scapular-loading hold here is kept UNDER 30 SECONDS, deliberately
        # and against the first draft, which used 55s holds pitched at the
        # measured 50-60s interscapular fatigue onset.
        #
        # That draft was blocked in review against patient_profile.py's own
        # symptom_log 2026-08-03 plan: "No self-directed exercise changes —
        # endurance-biased scapular loading (long isometric holds rather than
        # more reps) is an exercise-prescription change and goes to the
        # physiotherapist at the Day 28 reassessment (2026-08-16)."
        #
        # A session of 55s scapular holds IS that prescription. Authoring one
        # here would have had the app quietly make a call reserved for the
        # physio. Under 30s sits clearly below the measured threshold, so this
        # session trains nothing of the endurance capacity and prejudges
        # nothing. If the holds are approved on 2026-08-16, lengthen them then
        # — and record that it was approved.
        #
        # There is also NO second timed Down Dog here. The first draft placed
        # one at 14:05 to re-read the 50-60s burn onset, but it sat after three
        # 55s holds and would have measured fatigue on top of fatigue while
        # reporting it as a clean re-reading. The retest already lives on the
        # 15-minute flow's Down Dog at 30s, uncontaminated; duplicating the
        # instrument corrupts both.
        poses=[
            YogaPose(
                "Supported Diaphragmatic Breathing (Supine, Knees Bent)",
                _t("00:20"), 60, "cleared",
                "Sets the rib position the rest of the session works from. Nothing here "
                "loads the shoulder or the neck.",
            ),
            YogaPose(
                "Supine Arms-Overhead Reach (Elbows Toward the Floor)",
                _t("01:30"), 45, "caution",
                "The athlete's own failed test — he cannot rest both elbows on the floor "
                "with the arms overhead. Unloaded and self-limited: never a partner "
                "pressing the elbows down, which would put passive end-range pressure "
                "into a post-Latarjet shoulder whose stability is muscular rather than "
                "ligamentous (finding #6). Keep the low back flat; arching is how the "
                "lumbar spine buys fake overhead range.",
                option_note="A folded towel under the low back tells you the moment you arch",
            ),
            YogaPose(
                "Cat-Cow (Mid-Range, Thoracic-Biased)", _t("02:25"), 45, "cleared",
                "MID-RANGE only, and biased to the thoracic spine. The extension half stops "
                "well short of end range — L5/S1 retrolisthesis plus activated "
                "osteochondrosis means end-range lumbar extension is contraindicated.",
            ),
            YogaPose(
                "Thoracic Extension over a Rolled Towel", _t("03:20"), 60, "caution",
                "The towel goes at mid-thoracic (T6-T10), the region finding #3 identifies "
                "as sitting-stiffened, and NOT at the lumbar spine. Placement is the whole "
                "safety margin: too low and this becomes the end-range lumbar extension "
                "that is contraindicated.",
            ),
            YogaPose(
                "Thread the Needle (Right Arm Under)", _t("04:30"), 45, "cleared",
                "Unloaded thoracic rotation — the same family already used in the "
                "pre-session release protocol.",
            ),
            YogaPose(
                "Thread the Needle (Left Arm Under)", _t("05:25"), 45, "cleared",
                "As above, other side.",
            ),
            YogaPose(
                "Extended Puppy Pose", _t("06:20"), 45, "caution",
                "Passive shoulder flexion with the lats on stretch — the one pose here "
                "that reaches the lat, which is otherwise the gap in this athlete's "
                "overhead ladder. Let the chest sink rather than pushing into it.",
            ),
            YogaPose(
                "Prone Scapular Retraction Hold (Arms Low, Palms Down)",
                _t("07:15"), 25, "caution",
                "ARMS LOW, not a prone T — arms at 90 degrees of abduction would put the "
                "post-Latarjet shoulder toward the apprehension position. 25s is "
                "deliberately BELOW the measured 50-60s interscapular fatigue onset: this "
                "is a positioning drill, not the endurance prescription, which is the "
                "physiotherapist's call on 2026-08-16.",
            ),
            YogaPose(
                "Wall Forearm Press Hold (Elbows Below Shoulder Height)",
                _t("08:00"), 25, "caution",
                "Elbows stay BELOW shoulder height — above it the same drill drifts toward "
                "abduction plus external rotation. Serratus-biased. 25s, below threshold, "
                "for the same reason as the pose above.",
            ),
            YogaPose(
                "Supported Chest Opening over a Rolled Towel (Arms at 45 Degrees)",
                _t("08:45"), 60, "caution",
                "Arms at 45 degrees, NOT a supine 90/90 T — 90 degrees of abduction with "
                "external rotation is the apprehension position for anterior instability. "
                "The towel runs along the spine so the load is gravity on an open chest "
                "rather than an external frame levering the joint.",
            ),
            YogaPose(
                "Seated Neck Tilt — Right Ear Toward Right Shoulder",
                _t("09:55"), 40, "caution",
                "Self-generated only, NO hand overpressure — at Beighton 6/9 the cervical "
                "spine is the last place to hang on ligament, and symptom_log 2026-07-31 "
                "records asymmetric flexion tightness with mechanical crepitus.",
            ),
            YogaPose(
                "Seated Neck Tilt — Left Ear Toward Left Shoulder",
                _t("10:45"), 40, "caution",
                "As above. The LEFT side is the documented dominant side of the "
                "interscapular and cervical pattern, so expect asymmetry here and do not "
                "chase it into end range.",
            ),
            YogaPose(
                "Levator Scapulae Stretch (Left Side)", _t("11:35"), 40, "caution",
                "Levator scapulae is the anatomical bridge between the cervical spine and "
                "the superior medial scapular angle — the corridor the ache migrates along "
                "in symptom_log 2026-08-03. Released BEFORE the scapular work would be "
                "ideal; here it follows, because the holds above are positioning rather "
                "than loading.",
            ),
            YogaPose(
                "Levator Scapulae Stretch (Right Side)", _t("12:25"), 40, "caution",
                "Not merely the other side. symptom_log 2026-08-03's CORRECTION 2 records "
                "the pattern as BILATERAL with left dominance — right on 2026-07-16 and "
                "2026-07-23, left from 2026-07-21 — and it was the left-lateralised framing "
                "that obscured a postural-endurance driver. Treating the right as an "
                "afterthought would reintroduce exactly that error. Same rule as the left: "
                "self-generated, no hand overpressure.",
            ),
            YogaPose(
                "Supine Rest with Arms Overhead on a Cushion", _t("13:15"), 60, "cleared",
                "Supported overhead position with no reach demand — the shoulder rests at "
                "range rather than working to get there.",
            ),
            YogaPose("Deep Relaxation (Savasana)", _t("14:25"), 60, "cleared"),
        ],
    ),
]


def get(slug: str) -> YogaSession | None:
    return next((y for y in YOGA_LIBRARY if y.slug == slug), None)


#: Intensity as an orderable number, so the ranking below is a total order
#: rather than a string comparison that happens to sort "high" before "low".
_INTENSITY_RANK: dict[str, int] = {"low": 0, "moderate": 1, "high": 2}


def suggest_for_day(
    day_kind: str,
    *,
    focus_hint: frozenset[str] | set[str] = frozenset(),
    recent_slugs: tuple[str, ...] = (),
) -> YogaSession | None:
    """day_kind: 'rest_day' | 'active_rest_day'.

    A real ranking, as this function's previous docstring promised once a second
    session existed. Deterministic lexicographic sort over a key tuple in which
    every element is smaller-is-better, with the slug last so the result never
    depends on YOGA_LIBRARY's list order:

      1. focus_hint miss count — a caller asking for shoulder work gets the
         shoulder session, which is the whole reason a second session exists.
      2. repeat penalty — a session in `recent_slugs` sorts later, so alternating
         is the default rather than always returning the first match.
      3. intensity, direction depending on the day. An ACTIVE rest day prefers
         the higher-intensity option; a plain rest day prefers the lower one.
      4. slug, for a strict total order.

    No argument is required, so the existing single-argument call sites keep
    working unchanged.
    """
    eligible = [y for y in YOGA_LIBRARY if day_kind in y.suitable_for]
    if not eligible:
        return None

    wants_harder = day_kind == "active_rest_day"

    def key(session: YogaSession) -> tuple:
        missed = len(set(focus_hint) - set(session.primary_focus))
        repeat = 1 if session.slug in recent_slugs else 0
        rank = _INTENSITY_RANK.get(session.intensity, 0)
        return (missed, repeat, -rank if wants_harder else rank, session.slug)

    return min(eligible, key=key)
