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
those, because it is authored in the family the physiotherapist already
cleared and the athlete already runs daily: release work at ~50% effort inside
a ~10 minute dose, which docs/training/release_protocols_2026-08-10.md states
in terms is "not a training stressor". What the regional strain decides is
whether anything gets ACTIVATED beside the release — and on a heavy day the
answer is nothing, which is what TIER_SHRUNK is — release only, never adaptation-seeking, and since 2026-08-18 held to a 10-minute working floor.

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
never refuse — there is always a session, because the release half of it is
most useful precisely on the days the numbers look worst.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import training_plan as tp
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

ACCESSORY_PHASE: str = "Accessory — Release & Activation"


# ─────────────────────────────────────────────────────────────────────────────
#  The two tiers
# ─────────────────────────────────────────────────────────────────────────────
#
# The athlete's rule, 2026-08-16: available EVERY day, but the recipe shrinks
# rather than the button refusing. TIER_SHRUNK is release only — decompress,
# release, breathe — with no adaptation-seeking work at all, so it can sit
# beside a heavy gym day or a rest day without being either.

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
# clinical record argues against it; nobody has asked the physiotherapist. So
# it is authored and held, in the `cluster_a_mechanics.DEFERRED` idiom — a hold
# on evidence, with the condition that lifts it written down beside it.
#
# RAISE HANG_MAX_STEP TO 3 ONLY AFTER: two clean weeks at step 2, AND the
# question has been put to the physiotherapist. Raise HANG_STEP on two clean
# weeks alone. Drop HANG_STEP by one on any of the four signals above; twice
# means back to 1 and an entry in patient_profile's symptom_log.

HANG_MAX_STEP: int = 2
HANG_STEP: int = 1

#: On a shrunk day the hang always runs at step 1, whatever HANG_STEP says. The
#: shrunk tier exists because the day is already heavy or already reduced, and
#: full-bodyweight hanging is the one item here that is not trivial.
_SHRUNK_HANG_STEP: int = 1


# ─────────────────────────────────────────────────────────────────────────────
#  The recipes
# ─────────────────────────────────────────────────────────────────────────────
#
# Five slots, always in this order, because INHIBIT THEN ACTIVATE is the
# profile's own sequencing rule and running it the other way round trains the
# compensation:
#
#   1  decompress    the hang
#   2  release A     the front of the hip — the athlete's explicit ask, and a
#                    release, so it never adds load
#   3  release B     region-dependent
#   4  activate      two items in the freshest region  (FULL only)
#   5  down-regulate breathing
#
# Six items, except upper, which runs to seven: Techniques A and B of the pec
# protocol are ONE physiotherapist prescription in two parts, and splitting
# them across days would be running half a protocol.
#
# ⚠ EVERY SLOT IS AN ORDERED CANDIDATE LIST, AND THAT IS NOT TIDINESS.
# The block's own release block runs Upper Glute / TFL Self-Release and the
# Piriformis PNF in 28 of 28 days, and Single-Leg Glute Bridge in 11 — so a
# rule that merely DROPS a collision would leave the release slot empty on
# every single day, i.e. would delete the half of this session that justifies
# it. A slot therefore SUBSTITUTES down its list to the first item today's own
# session is not already doing. Standing Hip Flexor Release and Prone
# Decompression Breathing appear in 0 of 28 days, which is why each list ends
# somewhere that can always be reached.

_RELEASE_B: dict[str, tuple[dict, ...]] = {
    # Both, always — Techniques A and B are one prescription.
    "upper_body": (tp.PEC_SCAR_RELEASE, tp.ANTERIOR_SHOULDER_RECIPROCATION),
    # First free one.
    "lower_body": (tp.ACC_STANDING_HIP_FLEXOR, tp.UPPER_GLUTE_RELEASE_5MIN,
                   tp.PIRIFORMIS_PNF_5MIN),
    "core":       (tp.ACC_THORACIC_EXTENSION, tp.PIRIFORMIS_PNF_5MIN),
}

#: Slot 3 takes every candidate for upper (one protocol) and only the first
#: free candidate for the others.
_RELEASE_B_TAKE_ALL: frozenset[str] = frozenset({"upper_body"})

_ACTIVATE: dict[str, tuple[dict, ...]] = {
    # Rounded shoulders, and the order is the argument: the front wall is
    # released first, the segment is mobilised second, and only then are the
    # retractors asked to work. Prone Y-Raise is the one scapular item the log
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

#: Slot 2, in order. The anterior-hip item is the physiotherapist's own
#: 2026-08-10 recommendation and the one overactive structure that had no
#: release anywhere in the block until week 3 — so it leads whenever it is
#: allowed. Standing Hip Flexor Release is the fallback and appears in 0 of the
#: block's 28 days, which is what makes this slot always fillable.
_RELEASE_A: tuple[dict, ...] = (tp.ANTERIOR_HIP_RELEASE, tp.ACC_STANDING_HIP_FLEXOR,
                                tp.UPPER_GLUTE_RELEASE_5MIN)

#: What slot 2 falls back to before the flexibility battery has a cold baseline.
#: NOT a preference — release_protocols_2026-08-10.md is explicit that the
#: SUSTAINED-PRESSURE protocol must not start until the three baseline mornings
#: are captured, because the seated tilt is the battery's central measurement
#: and starting an intervention first contaminates the one number this project
#: has been protecting for weeks. That is the pre-declared failure mode, so the
#: code refuses to walk into it.
#:
#: The standing stretch is NOT held by that gate, and the distinction is the
#: document's own: what it sequences is Protocol 2, a daily sustained-pressure
#: course whose claimed mechanism is an adjunct multiplier on the tilt. A hip
#: flexor stretch is a different technique on a different timescale, it was a
#: Stage 1 staple, and short hip flexors do not limit the seated forward tilt —
#: if anything they assist it. So the athlete's explicit ask for a hip-flexor
#: release is still answered before the baseline exists, by the item the gate
#: does not cover.
_RELEASE_A_PRE_BASELINE: tuple[dict, ...] = (tp.ACC_STANDING_HIP_FLEXOR,
                                             tp.UPPER_GLUTE_RELEASE_5MIN)

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
#: It was hang + one release + two minutes of breathing, which on a gym day
#: (where the block's own release block has already taken the glute, piriformis
#: and hip items) collapsed to two real exercises. The screen said "about 10
#: min" because estimate_duration counts a per-side item ONCE; the truth was
#: nearer six, and two of those were breathing.
#:
#: Measured in laterality-aware working time, which is what the athlete
#: experiences and what estimate_duration under-reports. The tier fills from
#: release-only candidates until it clears this, so a thin day extends the
#: session rather than shortening it.
SHRUNK_MIN_WORK_SECONDS: int = 600

def work_seconds(exercises) -> int:
    """Working time with BOTH SIDES counted.

    services.sessions.estimate_duration deliberately does not do this (a
    recorded open issue), and the accessory screen even says so out loud —
    "reads low — per-side work is counted once". A duration FLOOR cannot be
    built on a number known to read low, so this counts what the athlete
    actually performs. Every unilateral item in the accessory pools genuinely
    runs both sides; the block's right-only items are not in them.
    """
    total = 0
    for ex in exercises:
        secs = sess.exercise_duration_seconds(ex)
        if ex.get("laterality") == "unilateral":
            secs *= 2
        total += secs
    return total


#: What the shrunk tier reaches for, in order, once its two fixed slots are
#: placed. RELEASE ONLY — the tier's contract is "no adaptation-seeking work",
#: so filling it must never reach into _ACTIVATE. Ordered: the chosen region's
#: own release work first, then the other regions', then whatever is left of
#: slot 2. Each list ends somewhere the block does not use, which is what keeps
#: it fillable on a gym day when the release block has already taken the hip
#: items.
_SHRUNK_FILL: tuple[dict, ...] = (
    *_RELEASE_B["upper_body"],
    *_RELEASE_B["core"],
    *_RELEASE_B["lower_body"],
    *_RELEASE_A,
    tp.ACC_THORACIC_EXTENSION,
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
        """⚠ Reads LOW on this session. `sessions.estimate_duration` does not
        read `laterality`, so every per-side item counts once — a known gap
        recorded in the rest-interval review, not introduced here."""
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
        return TIER_SHRUNK, "today is a rest day — release only, no adaptation-seeking work"
    if day_type == "test":
        # The day the block's exit criteria are judged on — final working loads
        # and the functional screen. Extra work beside them is a confound, and
        # the same contamination class the retest rule guards against.
        return TIER_SHRUNK, (
            "today is an assessment day — release only, so nothing here shows up in the "
            "numbers the block is judged on"
        )
    rpe_target = int((plan_day or {}).get("session_rpe_target") or 0)
    if rpe_target >= HEAVY_DAY_RPE_TARGET:
        return TIER_SHRUNK, f"today's session targets RPE {rpe_target} — release only"
    mult = (volume_rec or {}).get("multiplier")
    if mult is not None and float(mult) <= LOW_VOLUME_MULTIPLIER:
        return TIER_SHRUNK, (
            f"the engine has today at {float(mult):.2f} of normal volume — release only"
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
           battery_baseline_captured: bool = False,
           legs_must_stay_clean: bool = False,
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
    `battery_baseline_captured`  whether the flexibility battery has a cold
                   baseline. False withholds the anterior-hip release, because
                   starting it first contaminates the tilt measurement.
    `legs_must_stay_clean`  the next morning is a flexibility retest, so
                   lower-body activation is suppressed — a leg day the day
                   before reads as extra tightness in exactly the tissue under
                   test.
    """
    today = today or date.today()
    rows = list(region_rows or ())

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

    if region == "lower_body" and legs_must_stay_clean:
        region = "core"
        reasons.append(
            "a flexibility retest falls tomorrow morning — lower-body work would read as "
            "tightness in exactly the tissue being measured, so the trunk takes it instead"
        )

    hang_step = _SHRUNK_HANG_STEP if tier == TIER_SHRUNK else min(HANG_STEP, HANG_MAX_STEP)
    hang_step = max(1, min(hang_step, HANG_MAX_STEP, len(tp.ACCESSORY_HANG_LADDER)))
    hang = tp.ACCESSORY_HANG_LADDER[hang_step - 1]

    # Never dose the same exercise twice in one day: the block's own release
    # block already runs two of these in 28 of 28 days, and the anterior-hip
    # item from day 15. Every slot below therefore SUBSTITUTES past a collision
    # rather than dropping it — see the note on the recipe tables.
    taken: set[str] = set()
    planned_today = {ex.get("name") for ex in ((plan_day or {}).get("exercises") or ())}
    substituted: list[str] = []

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
            taken.add(name)
            out.append(ex)
        return out

    items: list[dict] = [*_free((hang,))]

    if battery_baseline_captured:
        items.extend(_free(_RELEASE_A))
    else:
        items.extend(_free(_RELEASE_A_PRE_BASELINE))
        reasons.append(
            "the flexibility battery has no cold baseline yet, so the sustained front-of-hip "
            "protocol is held — starting it first would contaminate the seated tilt it is "
            "judged on. The standing hip-flexor release covers the same tissue meanwhile"
        )

    if tier == TIER_FULL:
        b_limit = None if region in _RELEASE_B_TAKE_ALL else 1
        items.extend(_free(_RELEASE_B[region], limit=b_limit))
        activation = _free(_ACTIVATE[region], limit=_ACTIVATE_COUNT)
        items.extend(activation)
        if len(activation) < _ACTIVATE_COUNT:
            reasons.append(
                f"only {len(activation)} activation item(s) left after today's own session — "
                f"the right answer there is to add less, not to reach further down the list"
            )
    else:
        # FILL TO THE FLOOR. The shrunk tier used to be hang + one release +
        # breathing, and on a gym day — where the block's release block has
        # already taken the hip items — that left two real exercises. Reaching
        # for MORE RELEASE keeps the tier's contract intact: nothing here is
        # adaptation-seeking, so a longer session is still not a training
        # stressor. Region-ordered rather than arbitrary, and it stops the
        # moment the floor is cleared rather than emptying the pool.
        for candidate in _SHRUNK_FILL:
            if work_seconds(items) >= SHRUNK_MIN_WORK_SECONDS:
                break
            items.extend(_free((candidate,)))
        short_by = SHRUNK_MIN_WORK_SECONDS - work_seconds(items)
        if short_by > 0:
            reasons.append(
                f"today's own session already uses most of the release list, so this "
                f"comes in {short_by // 60} min under the {SHRUNK_MIN_WORK_SECONDS // 60}-minute "
                f"floor — the honest outcome, since the alternative is repeating work "
                f"already done today or reaching into adaptation-seeking work this tier "
                f"exists to exclude"
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
    # A shrunk session is a hang and release work drawn from every region's
    # list until it clears its floor — so it contains no region-specific
    # PROGRAMME, and a heading of "Shoulders & Posture" would promise work the
    # session does not centre on. The region is still CHOSEN and still recorded
    # (it decides what the fill reaches for first), it is simply not claimed on
    # screen.
    if choice.tier == TIER_SHRUNK:
        objective = "Accessory — Release Only"
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
    *_RELEASE_A,
    *_RELEASE_A_PRE_BASELINE,
    *(ex for group in _RELEASE_B.values() for ex in group),
    *(ex for group in _ACTIVATE.values() for ex in group),
)


def accessory_names() -> tuple[str, ...]:
    """Sorted, deduplicated names of everything emittable."""
    return tuple(sorted({ex["name"] for ex in ACCESSORY_LIBRARY}))
