"""The accessory session — a short second training, chosen by regional strain.

WHAT THIS IS. One 10-20 minute session offered on the training page's "+"
button, any day, chosen automatically from what the body regions have actually
carried. It is not on the calendar and it is never scheduled: the athlete asks
for it, and this module answers with exactly one session.

THE THREE LAYERS, and this file is the middle one:

    training_plan.py         WHAT  — the exercises and their doses
        |
    services/accessory.py    WHICH — tier, region, and the ordered list
        |
    views/training.py        HOW   — the same guided flow the plan session uses

This file DEFINES NO EXERCISE. It names them from `training_plan` and a test
fails if a dose or a `_ex(...)` call appears here, the same guard the
flexibility cluster runs between its mechanics and its prescription.

WHY IT IS NOT A SIXTH SESSION, which is the first objection to answer.
`rules.STAGE_CONSTRAINTS[2]["session_freq_max"]` is 5 and weeks 3-4 of the
current block already sit at exactly 5. This session does not spend one of
those, because it is authored in the family the athlete already runs before
every session: Block B's moving warm-up, posture items and mobility at their
switching-on dose. Until 2026-10-13 that family was release work at ~50%
effort; the release is out (see the recipe note below). What the regional
strain decides is whether anything gets ACTIVATED beside the warm-up work — and
on a heavy day the answer is nothing, which is what TIER_SHRUNK is: warm-up
class only, never a training dose, and since 2026-08-18 held to a 10-minute
working floor where today's own session leaves enough to fill it.

⚠ IT STILL COUNTS. The session logs like any other, feeds Foster AU and
therefore Strain and ACWR, and appears in the day's regional split. Volume
that the engine cannot see is the failure key rule 2b exists to prevent, and
"it is only mobility" is exactly how the Stage 1 over-count happened. What it
never does is mark a plan day done — that is `Repository`'s
SUPPLEMENTARY_SESSION_TYPES, not this module's business.

TODAY IS PROJECTED, NOT READ, and this is the athlete's own requirement:
*"It should always assume I'll be doing the other training required for that
day if I haven't done it already."* So today's regional load comes from the
PLAN DAY rather than from the log, through the same two primitives the
measured path uses (`session_region_mass` then `split_session_au`), so a
projection and a measurement are computed the same way and can be compared.

REGIONAL ACWR MAY SWAP A REGION AND MAY NEVER REFUSE A SESSION.
`strain_regions.region_acwr` returns `advisory_only=True, hard_locked=False`
unconditionally and by design; building a refusal on it would be a per-region
volume cap by another door. Athlete's decision, 2026-08-16: silently swap,
never refuse — there is always a session, because its easy half is most useful
precisely on the days the numbers look worst.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import training_constants as tc
import training_plan as tp
from services import flexibility as fx
from services import plan as _plan
from services import sessions as sess
from services import strain_regions as sr

__all__ = [
    "ACCESSORY_DAY_KEY", "ACCESSORY_PHASE", "ACCESSORY_TYPE",
    "TIER_FULL", "TIER_SHRUNK", "TIER_RPE",
    "HANG_MAX_STEP", "HANG_STEP", "HEAVY_DAY_RPE_TARGET", "LOW_VOLUME_MULTIPLIER",
    "ACCESSORY_LIBRARY", "AccessoryChoice", "choose", "build_day", "accessory_names",
]


# ─────────────────────────────────────────────────────────────────────────────
#  Identity
# ─────────────────────────────────────────────────────────────────────────────

#: The `day_num` this session checkpoints under. Negative on purpose: every
#: real plan day is >= 1, so an accessory checkpoint can never be mistaken for
#: one and `sessions.restore_from_checkpoint`'s day match keeps them apart.
ACCESSORY_DAY_KEY: int = -1

#: The `Type` written to every logged row. Must also appear in
#: `Repository.SUPPLEMENTARY_SESSION_TYPES`, which is what stops this session
#: marking a plan day done; a test pins that it does.
ACCESSORY_TYPE: str = "Accessory"

ACCESSORY_PHASE: str = "Accessory — Mobility & Activation"


# ─────────────────────────────────────────────────────────────────────────────
#  The two tiers
# ─────────────────────────────────────────────────────────────────────────────
#
# The athlete's rule, 2026-08-16: available EVERY day, but the recipe shrinks
# rather than the button refusing. TIER_SHRUNK is warm-up class only —
# decompress, mobilise, switch on — with nothing at a training dose, so it can
# sit beside a heavy gym day or a rest day without being either. (Release only
# until 2026-10-13.)

TIER_FULL: str = "full"
TIER_SHRUNK: str = "shrunk"

#: Session RPE target per tier. Both are low deliberately: if this session ever
#: rates above about 4 it has stopped being what it says it is.
TIER_RPE: dict[str, int] = {TIER_SHRUNK: 2, TIER_FULL: 3}

#: A plan day at or above this RPE target is a heavy day, and the accessory
#: session shrinks. 6 is a Stage 2B gym day; a run day is 4 and a mobility day
#: is 3, which is where the full recipe belongs.
HEAVY_DAY_RPE_TARGET: int = 6

#: `engine.volume_recommendation(...)["multiplier"]` at or below this means the
#: deterministic engine has already said today is a reduced-volume day — red
#: light, hard lock, or deload. Take it at its word rather than re-deriving it.
LOW_VOLUME_MULTIPLIER: float = 0.75


# ─────────────────────────────────────────────────────────────────────────────
#  The hang ladder
# ─────────────────────────────────────────────────────────────────────────────
#
# `training_plan.ACCESSORY_HANG_LADDER` authors three steps; these two numbers
# decide which one is reachable and which one runs. They are constants rather
# than logic because ADVANCING IS A JUDGEMENT, not a computation: the condition
# is two clean weeks — no apprehension, no instability sensation, no
# right-shoulder ache outlasting the session, no rise in the interscapular
# reading — and nothing in the data can see three of those four.
#
# HANG_MAX_STEP is the hold. Step 3 (Passive Dead Hang) is the only genuinely
# passive end-range loading on a shoulder with three anterior dislocations, a
# failed capsular wrap and a Latarjet on a shallow glenoid, whose stability is
# now muscular rather than ligamentous. The shoulder cluster prescribes it; the
# clinical record argues against it. So it is authored and held, in the
# `cluster_a_mechanics.DEFERRED` idiom — a hold
# on evidence, with the condition that lifts it written down beside it.
#
# RAISE HANG_MAX_STEP TO 3 ONLY AFTER FOUR clean weeks at step 2 - double the
# two that raise HANG_STEP, because step 3 is the one step that is hard to
# undo if it is wrong and no outside opinion is coming to adjudicate it
# (standing decision, 2026-08-17). Raise HANG_STEP on two clean weeks alone. Drop HANG_STEP by one on any of the four signals above; twice
# means back to 1 and an entry in patient_profile's symptom_log.

HANG_MAX_STEP: int = 2
#: 2 since 2026-10-28 (WP-40), on his report: "Im already at step 2 I can hold
#: on a bar for more than 15 seconds". HANG_MAX_STEP stays 2: the passive hang
#: still needs four clean weeks at this step.
HANG_STEP: int = 2

#: On a shrunk day the hang always runs at step 1, whatever HANG_STEP says. The
#: shrunk tier exists because the day is already heavy or already reduced, and
#: full-bodyweight hanging is the one item here that is not trivial.
_SHRUNK_HANG_STEP: int = 1


# ─────────────────────────────────────────────────────────────────────────────
#  The recipes
# ─────────────────────────────────────────────────────────────────────────────
#
# ⚠ NO RELEASE SINCE 2026-10-13 (athlete: "Drop the release", answering whether
# this session should follow Block B, which dropped its release block on
# 2026-09-22 — "I like the program as is without release in it, continue like
# this"). The two release slots became a MOVED front of the hip and a mobility
# slot, both drawn from what Block B already runs before every session. Out of
# the recipe, all still authored in training_plan: the front-of-hip ball, the
# upper-glute release, the piriformis PNF, the standing hip-flexor stretch, and
# the right pec and scar protocol (its two techniques went together — the
# reciprocation is the second half of that one release).
# REVERT with Block B's own signal (docs/hypothesis.md P12): the Wednesday grip
# grade at 2+ on the right, or the hip-crest or front-of-hip symptoms coming
# back, brings the release back here as well; the right upper-chest burning
# coming back brings the pec protocol back.
#
# Four slots, always in this order:
#
#   1  decompress    the hang
#   2  front of hip  moved, not released: the psoas march, his own pick
#   3  mobility      region-dependent, moving or positional
#   4  activate      two items in the freshest region  (FULL only)
#
# ⚠ EVERY SLOT IS AN ORDERED CANDIDATE LIST, AND THAT IS NOT TIDINESS. Block
# B's warm-up runs the march and the 90/90 hip lift on most days, so a rule
# that merely DROPPED a collision would leave a slot empty most days. A slot
# therefore SUBSTITUTES down its list to the first item today's own session is
# not already doing — and when the whole list is already done, the slot stays
# empty: the right answer then is to add less.

#: Slot 2: the front of the hip, MOVED. The march first; the hip lift when
#: today's session already marched.
_FRONT_OF_HIP: tuple[dict, ...] = (tp.STANDING_PSOAS_MARCH, tp.NINETY_NINETY_HIP_LIFT)

#: Slot 3: mobility for the chosen region, first free one.
_MOBILITY: dict[str, tuple[dict, ...]] = {
    "upper_body": (tp.ACC_THORACIC_EXTENSION, tp.BB_THREAD_THE_NEEDLE),
    "core":       (tp.BB_THREAD_THE_NEEDLE, tp.ACC_THORACIC_EXTENSION),
    "lower_body": (tp.HIP_AIRPLANE, tp.NINETY_NINETY_HIP_LIFT, tp.ACC_THORACIC_EXTENSION),
}

_ACTIVATE: dict[str, tuple[dict, ...]] = {
    # Rounded shoulders, and the order is the argument: the segment is
    # mobilised first (slot 3), and only then are the retractors asked to
    # work. Prone Y-Raise is the one scapular item the log
    # shows genuinely lapsing (last run 2026-07-24); the isometric is four
    # 3-second efforts rather than a hold, because the tissue is
    # perfusion-limited left trapezius where a sustained low-level contraction
    # is the PROVOCATIVE mechanism.
    "upper_body": (tp.PRONE_Y_RAISE, tp.SCAPULAR_ISOMETRIC, tp.ACC_THORACIC_EXTENSION,
                   tp.PREP_SCAPULAR),
    # The arched back. The first two ARE the profile's `underactive_weak` list —
    # glute max and the deep core — which is the whole answer to an anterior
    # pelvic tilt held up by short hip flexors. Nothing here holds a corrected
    # posture, which is the one route the record shows failing.
    "lower_body": (tp.PREP_GLUTE_ACTIVATION, tp.PREP_DEAD_BUG, tp.ACC_SIDE_BRIDGE_SHORT),
    "core":       (tp.PREP_DEAD_BUG, tp.ACC_SIDE_BRIDGE_SHORT, tp.ACC_THORACIC_EXTENSION),
}

#: How many activation items the full tier takes. Fewer is a legitimate outcome:
#: if today's own session already did them, the right answer is to add less, not
#: to reach further down the list for something to do.
_ACTIVATE_COUNT: int = 2

#: RETIRED FROM THE RECIPE 2026-10-13, with the rest of the release (see the
#: recipe note above). Kept named so the revert is one line: the battery gate
#: that held the front-of-hip ball protocol until the flexibility battery had
#: a cold baseline went with it, and would come back with it.
_RETIRED_RELEASE: tuple[dict, ...] = (
    tp.ANTERIOR_HIP_RELEASE, tp.ACC_STANDING_HIP_FLEXOR, tp.UPPER_GLUTE_RELEASE_5MIN,
    tp.PIRIFORMIS_PNF_5MIN, tp.PEC_SCAR_RELEASE, tp.ANTERIOR_SHOULDER_RECIPROCATION,
)

#: RETIRED FROM THE RECIPE 2026-08-18 — athlete: "decompression breathing is
#: not training". It closed every accessory session as a down-regulating slot,
#: and on the shrunk tier it was two of about six working minutes: a third of
#: the session was lying still. The exercise itself is untouched in
#: training_plan (Stage 1 uses it twice) and the name stays mapped; what
#: changed is that a session offered as training no longer counts it as such.
#: RESTORE only with a stated reason — this was a deliberate removal, not an
#: oversight.
_RETIRED_DOWN_REGULATE = tp.ACC_BREATHING

#: THE SHRUNK TIER'S FLOOR, in seconds of WORK — athlete, 2026-08-18: "the
#: extra training set is too short it should be at least 10 mins".
#:
#: It was hang + one release + two minutes of breathing, which on a Stage 2B
#: gym day (where the block's own release block had already taken the glute,
#: piriformis and hip items) collapsed to two real exercises. The screen said "about 10
#: min" because estimate_duration counts a per-side item ONCE; the truth was
#: nearer six, and two of those were breathing.
#:
#: Until 2026-10-13 the floor was 600 s of WORK, both sides counted, because
#: the session estimate then counted a per-side item once and charged 30 s a
#: changeover — a floor cannot sit on a number known to read low. Since
#: 2026-09-11 the time model (sessions.session_seconds) counts both sides and
#: the measured changeovers, so the floor now sits on the time the session
#: TAKES, which is what "10 mins" meant. Twelve, for a margin over the ten he
#: named. The work floor had been met by long release holds with few
#: changeovers; with the release gone it pushed a rest day to 22 minutes, past
#: the 10-20 minute ask.
SHRUNK_MIN_MINUTES: int = 12

#: The top of the athlete's ask: "this would be a 10-20 min training". The fill
#: never adds an item that would take the session past it.
SESSION_MAX_MINUTES: int = 20


def modelled_minutes(exercises) -> float:
    """The session's modelled length in minutes — the same measured model the
    plan sessions are timed on, both sides and every changeover counted."""
    return sess.session_seconds(list(exercises)) / 60


#: What the shrunk tier reaches for, in order, after the hang. WARM-UP CLASS
#: ONLY — the tier's contract is "nothing at a training dose": positional and
#: moving mobility first, then Block B's own moving warm-up and posture items,
#: then the switching-on activation items `sessions.PREPARATION_NAMES` already
#: counts as preparation, and last the scapular isometric, the left trapezius's
#: own decongestant (four light 3-second efforts). On a heavy gym day most of
#: the warm-up is already done, so the session comes in short of the floor —
#: and says so — rather than repeating work or reaching for a training dose.
_SHRUNK_FILL: tuple[dict, ...] = (
    tp.ACC_THORACIC_EXTENSION,
    tp.BB_THREAD_THE_NEEDLE,
    tp.STANDING_PSOAS_MARCH,
    tp.NINETY_NINETY_HIP_LIFT,
    tp.HIP_AIRPLANE,
    tp.PRONE_Y_RAISE,
    tp.PREP_SCAPULAR,
    tp.PREP_DEAD_BUG,
    tp.SCAPULAR_ISOMETRIC,
)


#: Deterministic tie-break, and the order is a clinical judgement rather than
#: alphabetical: with nothing to choose between regions, the shoulder work is
#: the one with a standing requirement behind it ("scapular control is a
#: STANDING requirement, not optional conditioning" — finding #6), the trunk
#: is next, and the legs come last because the block already loads them most.
_REGION_PREFERENCE: tuple[str, ...] = ("upper_body", "core", "lower_body")


# ─────────────────────────────────────────────────────────────────────────────
#  Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AccessoryChoice:
    """One decided session. `reasons` is the audit trail, not decoration — it
    is what a test asserts against and what the session note records, so that
    six weeks later it is possible to say why a given region was picked."""

    tier: str
    region: str
    hang_step: int
    exercises: tuple[dict, ...]
    reasons: tuple[str, ...]
    #: ISO date this session was chosen for. Load-bearing, not metadata: the
    #: checkpoint slot is keyed by ACCESSORY_DAY_KEY, which unlike a plan day
    #: number is the SAME every day — so nothing else could tell a session
    #: abandoned yesterday apart from one in progress now, and the app would
    #: reopen a dead session every morning. `views/training.py` checks it on
    #: restore.
    on_date: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(ex["name"] for ex in self.exercises)

    @property
    def estimated_minutes(self) -> int:
        """The minutes the screen states. Since 2026-09-11 the time model
        counts both sides of a per-side item and the measured changeovers; it
        read low before that, which is what the old work floor was built
        around."""
        return sess.estimate_duration(list(self.exercises))


# ─────────────────────────────────────────────────────────────────────────────
#  Choosing
# ─────────────────────────────────────────────────────────────────────────────

def projected_region_au(plan_day: dict | None) -> dict[str, float]:
    """Today's regional load AS IF the plan session happens, whether or not it
    is logged yet.

    Built from the plan day through the same two primitives the measured path
    uses, so a projection and a measurement are the same computation over
    different inputs. An empty or missing plan day projects zero, which is
    correct: there is nothing scheduled to assume.
    """
    zero = {r: 0.0 for r in sr.REGIONS}
    exercises = list((plan_day or {}).get("exercises") or ())
    if not exercises:
        return zero
    seconds = [{"name": ex.get("name", ""),
                "seconds": sess.exercise_duration_seconds(ex)}
               for ex in exercises]
    mass = sr.session_region_mass(seconds)
    au = float(plan_day.get("session_rpe_target") or 0) * sess.estimate_duration(exercises)
    if au <= 0 or not mass.get("regions_known"):
        return zero
    split = sr.split_session_au(au, mass)
    return {r: float(split.get(r, 0.0)) for r in sr.REGIONS}


def _yesterday_region_au(region_rows: list[dict], today: date) -> tuple[dict[str, float], str]:
    """Yesterday's regional load, and how it was arrived at.

    THREE CASES, and they are genuinely different:
      - a row with regions_known  -> use it
      - NO ROW AT ALL             -> a rest day. Absent is not zero in general,
                                     but a day with no session carried no load,
                                     which is the one place the two coincide.
      - a row with regions_known False -> a session whose exercises map to
                                     nothing (a yoga day). Its AU is real and
                                     its distribution is unknown, so reading it
                                     as zero would call a shoulder-heavy yoga
                                     day a rest for the shoulders. Fall back to
                                     the 7-day mean, which at least knows the
                                     shape of a normal week.
    """
    from datetime import timedelta

    row = sr.region_au_for_date(region_rows, today - timedelta(days=1))
    if row is None:
        return {r: 0.0 for r in sr.REGIONS}, "yesterday was a rest day"
    if not row.get("regions_known"):
        week = sr.rolling_prior_region_row(region_rows, today)
        if week is None:
            return {r: 0.0 for r in sr.REGIONS}, (
                "yesterday's session mapped to no region and there is no week to fall "
                "back on — treated as unloaded"
            )
        return ({r: float(week.get(r, 0.0)) for r in sr.REGIONS},
                "yesterday's session mapped to no region — used the 7-day mean instead")
    return ({r: float(row.get(r, 0.0)) for r in sr.REGIONS}, "yesterday's logged regional load")


def _tier(plan_day: dict | None, volume_rec: dict | None) -> tuple[str, str]:
    day_type = (plan_day or {}).get("day_type")
    if day_type == "rest":
        return TIER_SHRUNK, "today is a rest day — mobility and warm-up work only, nothing at a training dose"
    if day_type == "test":
        # The day the block's exit criteria are judged on — final working loads
        # and the functional screen. Extra work beside them is a confound, and
        # the same contamination class the retest rule guards against.
        return TIER_SHRUNK, (
            "today is an assessment day — mobility and warm-up work only, so nothing here "
            "shows up in the numbers the block is judged on"
        )
    rpe_target = int((plan_day or {}).get("session_rpe_target") or 0)
    if rpe_target >= HEAVY_DAY_RPE_TARGET:
        return TIER_SHRUNK, (f"today's session targets RPE {rpe_target} — mobility and "
                             f"warm-up work only")
    mult = (volume_rec or {}).get("multiplier")
    if mult is not None and float(mult) <= LOW_VOLUME_MULTIPLIER:
        return TIER_SHRUNK, (
            f"the engine has today at {float(mult):.2f} of normal volume — mobility and "
            f"warm-up work only"
        )
    return TIER_FULL, "a moderate day — there is room for activation work"


def _region(load: dict[str, float], region_acwr: dict[str, dict] | None) -> tuple[str, tuple[str, ...]]:
    reasons: list[str] = []
    candidates = list(_REGION_PREFERENCE)

    for r in _REGION_PREFERENCE:
        info = (region_acwr or {}).get(r) or {}
        ratio, ceiling = info.get("acwr"), info.get("ceiling")
        if ratio is None or ceiling is None:
            continue
        if float(ratio) > float(ceiling) and len(candidates) > 1:
            candidates.remove(r)
            reasons.append(
                f"{r} ACWR {float(ratio):.2f} is over its {float(ceiling):.2f} ceiling — "
                f"swapped away from it"
            )

    region = min(candidates, key=lambda r: (round(load.get(r, 0.0), 3),
                                            _REGION_PREFERENCE.index(r)))
    reasons.append(
        "least-loaded region over yesterday plus today: "
        + ", ".join(f"{r} {load.get(r, 0.0):.0f} AU" for r in _REGION_PREFERENCE)
    )
    return region, tuple(reasons)


def choose(*,
           plan_day: dict | None,
           region_rows: list[dict] | None = None,
           region_acwr: dict[str, dict] | None = None,
           volume_rec: dict | None = None,
           legs_must_stay_clean: bool = False,
           tomorrow_plan_day: dict | None = None,
           today: date | None = None) -> AccessoryChoice:
    """Decide today's accessory session. Pure, deterministic, and total — it
    always returns a session.

    `plan_day`  today's PLAN day, logged or not. See `projected_region_au`.
    `region_rows`  `Repository.get_daily_region_au(...)["rows"]`.
    `region_acwr`  `strain_regions.region_acwr(...)`. May swap a region; never
                   refuses. `insufficient_regional_load` carries `acwr=None`
                   and is therefore simply not consulted, which is right — the
                   first week of a block has nothing to say yet.
    `volume_rec`   `engine.volume_recommendation(...)`.
    `legs_must_stay_clean`  the next morning is a flexibility retest, so no
                   lower-body item runs at all — the region moves to the trunk
                   and the march and the hip airplane are skipped. A leg day
                   the day before reads as extra tightness in exactly the
                   tissue under test.
    `tomorrow_plan_day`  tomorrow's PLAN day. When it is a flexibility session
                   the legs stay clean too — the plan's own rule, which is why
                   Block B's Wednesday carries no leg work. Before the release
                   left this session its shrunk tier held no leg work at all,
                   so the rule only became needed on 2026-10-13.

    (`battery_baseline_captured` left with the front-of-hip ball protocol it
    gated, 2026-10-13.)
    """
    today = today or date.today()
    rows = list(region_rows or ())
    if (tomorrow_plan_day or {}).get("session_kind") == "flexibility" and not legs_must_stay_clean:
        legs_must_stay_clean = True
        tomorrow_flexibility = True
    else:
        tomorrow_flexibility = False

    tier, tier_reason = _tier(plan_day, volume_rec)
    reasons: list[str] = [tier_reason]

    yesterday, yesterday_reason = _yesterday_region_au(rows, today)
    reasons.append(yesterday_reason)
    projected = projected_region_au(plan_day)
    if any(v > 0 for v in projected.values()):
        reasons.append(
            "today counted as if the planned session happens: "
            + ", ".join(f"{r} {projected[r]:.0f} AU" for r in sr.REGIONS)
        )
    load = {r: yesterday.get(r, 0.0) + projected.get(r, 0.0) for r in sr.REGIONS}

    region, region_reasons = _region(load, region_acwr)
    reasons.extend(region_reasons)

    tomorrow_why = ("tomorrow is the flexibility session" if tomorrow_flexibility
                    else "a flexibility retest falls tomorrow morning")
    if region == "lower_body" and legs_must_stay_clean:
        region = "core"
        reasons.append(
            f"{tomorrow_why} — lower-body work would read as tightness in exactly the "
            f"tissue being stretched or measured, so the trunk takes it instead"
        )

    hang_step = _SHRUNK_HANG_STEP if tier == TIER_SHRUNK else min(HANG_STEP, HANG_MAX_STEP)
    hang_step = max(1, min(hang_step, HANG_MAX_STEP, len(tp.ACCESSORY_HANG_LADDER)))
    hang = tp.ACCESSORY_HANG_LADDER[hang_step - 1]

    # Never dose the same exercise twice in one day: Block B's warm-up already
    # runs the march and the 90/90 hip lift on most days. Every slot below
    # therefore SUBSTITUTES past a collision rather than dropping it — see the
    # note on the recipe tables.
    taken: set[str] = set()
    planned_today = {ex.get("name") for ex in ((plan_day or {}).get("exercises") or ())}
    substituted: list[str] = []
    kept_off_legs: list[str] = []

    def _free(candidates, limit: int | None = 1) -> list[dict]:
        """First `limit` candidates today's own session is not already doing."""
        out: list[dict] = []
        for ex in candidates:
            if limit is not None and len(out) >= limit:
                break
            name = ex["name"]
            if name in taken:
                continue
            if name in planned_today:
                substituted.append(name)
                continue
            if legs_must_stay_clean and tc.EXERCISE_BODY_REGION.get(name) == "lower_body":
                kept_off_legs.append(name)
                continue
            taken.add(name)
            out.append(ex)
        return out

    items: list[dict] = [*_free((hang,))]

    if tier == TIER_FULL:
        items.extend(_free(_FRONT_OF_HIP))
        items.extend(_free(_MOBILITY[region]))
        activation = _free(_ACTIVATE[region], limit=_ACTIVATE_COUNT)
        items.extend(activation)
        if len(activation) < _ACTIVATE_COUNT:
            reasons.append(
                f"only {len(activation)} activation item(s) left after today's own session — "
                f"the right answer there is to add less, not to reach further down the list"
            )
    else:
        # FILL TO THE FLOOR, from warm-up-class work only, in a fixed order, and
        # stop the moment the floor is cleared rather than emptying the pool.
        for candidate in _SHRUNK_FILL:
            if modelled_minutes(items) >= SHRUNK_MIN_MINUTES:
                break
            if modelled_minutes([*items, candidate]) > SESSION_MAX_MINUTES:
                continue
            items.extend(_free((candidate,)))
        short_by = SHRUNK_MIN_MINUTES - modelled_minutes(items)
        if short_by > 0:
            reasons.append(
                f"today's own session already does most of the warm-up work, so this "
                f"comes in {short_by:.0f} min under the {SHRUNK_MIN_MINUTES}-minute "
                f"floor — the honest outcome, since the alternative is repeating work "
                f"already done today or reaching for a training dose this tier exists to "
                f"exclude"
            )

    if kept_off_legs:
        reasons.append(
            f"{tomorrow_why}, so no leg work runs here: "
            + ", ".join(dict.fromkeys(kept_off_legs))
        )

    if substituted:
        reasons.append(
            "already in today's own session, so substituted past rather than repeated: "
            + ", ".join(dict.fromkeys(substituted))
        )

    return AccessoryChoice(tier=tier, region=region, hang_step=hang_step,
                           exercises=tuple(items), reasons=tuple(reasons),
                           on_date=today.isoformat())


# ─────────────────────────────────────────────────────────────────────────────
#  Rendering hand-off
# ─────────────────────────────────────────────────────────────────────────────

def build_day(choice: AccessoryChoice) -> dict:
    """The choice, in the exact shape `views/training.py` reads a plan day in.

    That shape is the whole point: it is what lets the accessory session run
    through the SAME guided flow as the plan session — same timers, same set
    logging, same completion screen — instead of a second screen that would
    drift away from the first one.

    `day_type` is "stretch" in `scheduling.SESSION_PRIORITY` terms. Nothing
    reschedules this session (it is not on the calendar), but the key is
    authored rather than omitted because a day dict without one is the partial
    adoption that silently kills the readiness auto-shift.
    """
    # ⚠ THE SHRUNK TIER DOES NOT NAME THE REGION, and that is not cosmetic.
    # A shrunk session is a hang and warm-up-class work drawn from one fixed
    # list until it clears its floor — so it contains no region-specific
    # PROGRAMME, and a heading of "Shoulders & Posture" would promise work the
    # session does not centre on. The region is still CHOSEN and still
    # recorded, it is simply not claimed on screen.
    if choice.tier == TIER_SHRUNK:
        objective = "Accessory — Mobility & Warm-Up"
    else:
        objective = "Accessory — " + {"upper_body": "Shoulders & Posture",
                                      "core": "Trunk",
                                      "lower_body": "Hips & Glutes"}[choice.region]
    return {
        "objective": objective,
        "phase": ACCESSORY_PHASE,
        "session_rpe_target": TIER_RPE[choice.tier],
        "is_gym_session": False,
        "day_type": "stretch",
        "exercises": list(choice.exercises),
        # Not read by the renderer. Carried so the completion screen can write
        # the reasoning into the session note, which is what makes a region
        # choice auditable six weeks later instead of merely plausible.
        "accessory_date": choice.on_date,
        "accessory_tier": choice.tier,
        "accessory_region": choice.region,
        "accessory_hang_step": choice.hang_step,
        "accessory_reasons": list(choice.reasons),
        "accessory_note": session_note(choice),
    }


def session_note(choice: AccessoryChoice) -> str:
    """The line written to the session log. Names the tier, the region and why.

    ⚠ It also names the upper-body activation explicitly, because that work
    confounds the `interscapular` Stage 2B exit criterion — whose own text says
    the intervention under test is the DESK HEIGHT, not the training. Recording
    it here is what makes the confound visible at the reassessment rather than
    discovered after it.
    """
    head = f"Accessory session ({choice.tier}, {choice.region})."
    body = " ".join(f"{i}. {r}" for i, r in enumerate(choice.reasons, start=1))
    tail = ""
    if choice.region == "upper_body" and choice.tier == TIER_FULL:
        tail = (" NOTE: scapular work today — relevant to the interscapular exit criterion, "
                "which is testing the desk height rather than the training.")
    return f"{head} {body}{tail}"


#: Every exercise this module can ever emit. Exists so a test can assert the
#: accounting maps cover all of it — an unmapped name would be counted as
#: fully-loaded barbell work at `content_weighting.UNMAPPED_EXERCISE_WEIGHT`,
#: which is the Stage 1 over-count arriving by a new door.
ACCESSORY_LIBRARY: tuple[dict, ...] = (
    *tp.ACCESSORY_HANG_LADDER,
    *_FRONT_OF_HIP,
    *(ex for group in _MOBILITY.values() for ex in group),
    *(ex for group in _ACTIVATE.values() for ex in group),
    *_SHRUNK_FILL,
)


def accessory_names() -> tuple[str, ...]:
    """Sorted, deduplicated names of everything emittable."""
    return tuple(sorted({ex["name"] for ex in ACCESSORY_LIBRARY}))


# ─── The choice's inputs, read (move TRN-14, 2026-10-19) ─────────────────────

#: Days of regional load read back for the choice.
REGION_HISTORY_DAYS = 31


def read_choice(repo, active, day_num: int | None, volume_rec: dict | None, today: date,
                *, region_rows: list[dict] | None = None) -> AccessoryChoice:
    """Everything `choose` needs, read defensively, then the choice.

    Every read degrades to the conservative side rather than to an error: no
    regional history means the tie-break decides, an unreadable stage means
    no regional ACWR, and an unreadable retest history leaves the legs to
    tomorrow's plan day alone. A health page that fails because a read timed
    out is worse than one that offers a slightly blunter session. `today` is
    the caller's day; a caller with its own cached region rows passes them."""
    plan_day = tomorrow_day = None
    if active is not None and day_num is not None:
        calendar = sess.calendar_plan(active)
        plan_day, tomorrow_day = calendar.get(day_num), calendar.get(day_num + 1)

    rows = region_rows
    if rows is None:
        try:
            rows = repo.get_daily_region_au(days=REGION_HISTORY_DAYS, today=today)["rows"]
        except Exception:
            rows = []

    region_acwr = None
    try:
        # PHASE_META's stage, never the phase number: Phase 3 is Stage 2B at
        # clinical stage 2, and indexing STAGE_CONSTRAINTS by the phase number
        # would read it as a Stage 3 ceiling.
        stage = int(sess.PHASE_META.get(getattr(active, "phase_number", 0), {}).get("stage")
                    or repo.get_current_stage())
        region_acwr = sr.region_acwr(
            rows, stage, today=today,
            stage_start=_plan.current_stage_start(repo.get_phases(), today))
    except Exception:
        region_acwr = None

    legs_clean = False
    try:
        stored = repo.get_flexibility_assessments()
        if stored:
            status, _ = fx.retest_readiness(
                stored[-1].taken_on, today,
                fx.leg_loading_days(repo.get_recent_sessions(days=3, today=today)))
            legs_clean = status == fx.RETEST_TOMORROW
    except Exception:
        legs_clean = False

    return choose(plan_day=plan_day, region_rows=rows, region_acwr=region_acwr,
                  volume_rec=volume_rec, legs_must_stay_clean=legs_clean,
                  tomorrow_plan_day=tomorrow_day, today=today)
