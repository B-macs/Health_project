"""
services/sleep_fusion.py — merge Oura and Garmin sleep stages into one
master hypnogram.

The two devices fail in opposite directions, and that is the whole basis for
fusing them:

  - Oura reads stage well (pulse-wave amplitude distinguishes deep/REM/light
    reliably) but over-reports "Awake" — a finger-worn sensor registers
    micro-movement and autonomic spikes that are repositioning, not waking.
  - Garmin needs larger rotational wrist motion before it will call Awake, so
    its Awake label is a strict, reliable filter. It pays for that by
    frequently mislabelling REM as Light.

So: take stage from Oura, take permission-to-call-Awake from Garmin.

VERSION 2 — MOVEMENT
Until RULES_VERSION 2 the central rule ("Oura awake + Garmin asleep ->
repositioning") was an ASSERTION ABOUT MOVEMENT that never measured movement.
services/sleep_movement.py now supplies a fused motion series, and rules 5-7
answer the same question from it, splitting one verdict into three physically
different ones: still body -> asleep (rule 5), sustained gross motion ->
awakening kept (rule 6), and deep sleep with whole-body motion -> implausible
(rule 7).

What that evidence actually showed, measured across the 26 fused nights, is
worth stating plainly because it is not the hoped-for result: of the 1,804
minutes version 1 converted from Awake to sleep on the premise below,
movement CONFIRMS 23 and CONTRADICTS 39. It is silent on the other 1,742.
The premise is therefore still carrying almost all of the phantom-wake
removal; movement has narrowed it at the edges, not validated it. Net effect
on those nights is -1.5 minutes of sleep per night.

Movement also cannot help with stage DEPTH, and no future rule should try:
REM atonia makes REM as motionless as deep sleep, so stillness cannot
distinguish them. See services/sleep_movement.py's docstring.

WHY THE OUTPUT IS NOT WIRED INTO THE ENGINE
Every rule below either converts Awake -> sleep or swaps one sleep stage for
another. None converts a minute Oura called sleep into Awake, so per night,
fused total sleep remains monotonically >= Oura alone
(test_fusion_never_converts_a_sleep_minute...). Rule 6 is not an exception: it
keeps Awake where Oura already said Awake, so it lowers fused sleep relative
to RULES_VERSION 1 but never relative to Oura.

The first rule that WOULD break that invariant is quiet-wakefulness detection
— a long motionless run that both devices call sleep but where heart rate is
elevated against the night's own sleeping baseline. That is the actigraphy
blind spot proper (Marino et al. 2013 measure wake specificity at 0.34).

IT WAS BUILT AS FAR AS MEASUREMENT AND THEN ABANDONED. Do not re-attempt it
without reading this first — the data does not support it, and the reasons
are not the obvious ones.

Measured over the 26 fused nights, on still minutes only, using Garmin's
120-second overnight HR:

    HR minus the night's own low-quartile baseline
      Deep  med +3.0    Light med +1.0    REM med +3.0    AWAKE med +3.0
    HR minus a LOCAL (+/-30 min) rolling median   <- removes the
      Deep  med  0.0    Light med  0.0    REM med +1.0    AWAKE med +1.0
                                                     time-of-night trend

    Best precision at any threshold: ~12% (base rate 1.9%). So ~88% of the
    minutes such a rule converted to Awake would be wrong.

Three reasons, in increasing order of how fatal they are:

  1. Sampling is too coarse. Garmin overnight HR is 120s, Oura's is 300s.
     Probing get_heart_rates, get_respiration_data and get_all_day_stress
     (2026-07-31) found NOTHING finer: get_heart_rates is also 120s and
     covers less of the sleep window, respiration returns empty arrays, and
     all_day_stress is 180s. get_hrv_data returns {} outright. There is no
     better data available from this account, so this is not a "wait for a
     bigger sample" problem.
  2. The positive class is tiny — 123 still-awake minutes across 26 nights.
     Any threshold fitted on that is fitting noise.
  3. THE DECISIVE ONE: there is no ground truth. Validation here uses the
     hypnogram's own Awake labels, but the minutes such a rule exists to FIND
     are by definition the ones the hypnogram did NOT label Awake. Even a
     clean signal could not be validated without PSG. This does not improve
     with more nights or better sensors.

And the physiology says the same thing independently: REM is elevated-and-
motionless, which is exactly the signature quiet wakefulness would present.
The local-baseline rows above show REM and Awake are indistinguishable.

What would change the answer: a ground-truth source (a few nights against an
EEG headband or PSG), which would address (3), together with beat-to-beat
intervals rather than 120-second averages, which would address (1).

It is tempting to conclude that wiring this in would simply loosen every
safety constraint. It would not, and the real shadow report (2026-07-31, 26
fused nights inside a 60-day window) showed the opposite: the traffic light
moved green -> YELLOW and 7-day sleep debt ROSE from 8.04h to 8.47h.

The reason is that both engine.traffic_light and readiness.sleep_debt_hours
score a day against a rolling baseline computed from the same rows. Raising
sleep on the nights that HAVE Garmin data also raises the mean those nights
are compared against, so a night without Garmin data now looks worse by
comparison. With partial coverage the window is a mixture of two different
measurements and the net effect is not directional at all — it is noise with
a plausible-looking sign.

That is precisely the argument CLAUDE.md rule 2b already makes for keeping
ACWR on Foster AU rather than mixing Edwards'-TRIMP days into the same
window. Same failure mode, same answer: fused values are persisted and shown;
the engine keeps reading the Oura/Garmin blend in services/biometrics.py.
Wiring it in would require recomputing the ENTIRE history in one pass, which
is impossible while Garmin only has stage data from May 2026 onward.

CLINICAL PREMISE, STATED PLAINLY
The "Oura Awake + Garmin asleep -> repositioning" rule rests on the athlete
having confirmed generalised hypermobility (patient_profile.py, Beighton 6/9)
and a personally low HRV baseline. The hypermobility is documented; the
specific claim that it produces frequent NON-waking position shifts overnight
is an observation, not a documented clinical finding. It is encoded here as a
deliberate, reviewable assumption — which is a further reason the output stays
out of the safety path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services import hr_matching

# ─── Stage coding — deliberately the same digits Oura itself uses, so a
#     master hypnogram and an Oura hypnogram are directly comparable strings
#     and neither needs translating to read the other. ────────────────────────
DEEP, LIGHT, REM, AWAKE = 1, 2, 3, 4
UNCOVERED = 0

STAGE_LABELS: dict[int, str] = {
    DEEP: "Deep Sleep", LIGHT: "Light Sleep", REM: "REM Sleep",
    AWAKE: "Awake", UNCOVERED: "No data",
}
SLEEP_STAGES: frozenset[int] = frozenset({DEEP, LIGHT, REM})

# Verified against real payloads: summing each level's segment durations
# reproduces dailySleepDTO's own deepSleepSeconds/lightSleepSeconds/
# remSleepSeconds/awakeSleepSeconds. Repository.
# _garmin_sleep_stages_row re-checks this on EVERY night (totals_match) rather
# than trusting the one night it was first confirmed on.
GARMIN_LEVEL_TO_STAGE: dict[float, int] = {0.0: DEEP, 1.0: LIGHT, 2.0: REM, 3.0: AWAKE}

# Tie-break when one grid minute spans two stages. AWAKE first is the whole
# point: resampling must never MANUFACTURE sleep. Every awake->sleep
# conversion is then attributable to a named rule with its own reason code,
# which is what makes the phantom-wake total auditable rather than an
# unexplained residue of three separate mechanisms.
RESAMPLE_PRIORITY: tuple[int, ...] = (AWAKE, DEEP, REM, LIGHT)

# Rule 2's "brief window". Garmin's median stage segment is ~10 min, so +/-3
# sits inside a typical segment while still catching a short awake segment
# adjacent to the minute in question.
WAKE_CONFIRM_RADIUS_MINUTES = 3

# Rule 3's "unnaturally extended". A contiguous Oura-Deep run longer than this
# that STARTS in the second half defers only its excess minutes to Garmin —
# the first 45 stay Deep. Excess-only avoids a cliff where a 46-minute run
# loses all 46 minutes of deep sleep.
DEEP_RUN_PLAUSIBLE_MINUTES = 45

# Below this share of the shorter window, two nights are not the same night.
MIN_WINDOW_OVERLAP_FRACTION = 0.50

# ─── Movement thresholds (rules 5-7) ────────────────────────────────────────
#  Until version 2 the "Oura awake + Garmin asleep -> repositioning" rule was
#  an ASSERTION ABOUT MOVEMENT that never measured movement. These let the
#  same question be answered from the fused motion series instead, splitting
#  one verdict into three physically different ones. All are reasoned
#  defaults, recalibratable against logged nights.

# How far either side of a minute to look for corroborating motion. Matches
# WAKE_CONFIRM_RADIUS_MINUTES so the movement and stage evidence for the same
# minute are drawn from the same span of the night.
MOTION_RADIUS_MINUTES = 3

# Minutes of motion at or above MOTION_AWAKE_FROM, inside that window, before
# Oura's Awake is taken at face value. One minute is a postural shift; several
# is someone who is up. This is the threshold separating rule 6 from rule 5.
MOTION_AWAKE_SUSTAINED_MINUTES = 3

# The class that counts as evidence of being awake — TOSSING, i.e. whole-body
# movement, NOT merely RESTLESS.
#
# Measured, and the reason this is not RESTLESS: at RESTLESS the rule fired on
# 1,451 of 12,347 minutes across the 26 fused nights and cut phantom-wake
# removal from 1,811 minutes to 360, moving 24 hours of sleep across 26
# nights. That is not a refinement, it is a different measurement — and it is
# wrong, because "restless" is a normal state DURING sleep in Oura's own
# published alphabet (1 no motion, 2 restless, 3 tossing and turning, 4
# active), not a marker of wakefulness. Body movement during sleep is normal
# and frequent (Wilde-Frenz & Schulz 1983); only sustained GROSS movement
# distinguishes wake.
MOTION_AWAKE_FROM = 3

# Stillness this far either side, with Garmin calling sleep, is the
# highest-confidence "asleep" evidence available — and the specific case put
# forward when this ruleset was commissioned: Oura awake, Garmin light, no
# movement on either device, therefore asleep.
STILL_RADIUS_MINUTES = 2

# Movement classes this module's rules test against. Mirrors
# services/sleep_movement.py's published 1-4 alphabet, declared here rather
# than imported to keep the dependency one-directional (sleep_movement imports
# THIS module for the shared grid helpers and source vocabulary, so importing
# it back would be circular). test_movement_class_constants_match_sleep_movement
# pins them together so the duplication cannot drift.
MOTION_STILL = 1
MOTION_RESTLESS = 2
MOTION_ACTIVE = 4

# Bump on ANY change to the constants or rules above. Persisted per row so a
# stored hypnogram always says which ruleset produced it.
#
#   1 — stage labels only.
#   2 — movement-aware (rules 5-7). Degrades exactly to version 1 behaviour on
#       a night with no movement data, so the bump is safe to apply to the
#       whole history: nights without movement re-derive bit-identically.
RULES_VERSION = 2

SOURCE_FUSED = "fused"
SOURCE_OURA_ONLY = "oura_only"
SOURCE_GARMIN_ONLY = "garmin_only"
SOURCE_NONE = "none"
SOURCE_LABELS: dict[str, str] = {
    SOURCE_FUSED: "Oura + Garmin fused",
    SOURCE_OURA_ONLY: "Oura only (no Garmin match)",
    SOURCE_GARMIN_ONLY: "Garmin only",
    SOURCE_NONE: "No sleep data",
}

# One character per minute, same length as the master — so every single minute
# of the output can be attributed to the rule that produced it.
REASON_AGREE = "="
REASON_OURA_WINS = "o"
REASON_DEEP_EXCESS = "x"
REASON_REPOSITION = "r"
REASON_WAKE_CONFIRMED = "w"
REASON_GARMIN_WAKE = "g"
REASON_SMOOTHED = "s"
REASON_OURA_PASSTHROUGH = "-"
REASON_NO_DATA = "?"
# Version 2, movement-aware.
REASON_STILL_ASLEEP = "z"
REASON_MOTION_AWAKE = "m"
REASON_DEEP_MOTION = "d"
REASON_LABELS: dict[str, str] = {
    REASON_AGREE: "Both devices agree",
    REASON_OURA_WINS: "Both asleep, disagree — Oura's stage kept",
    REASON_DEEP_EXCESS: "Over-long deep run in second half — deferred to Garmin",
    REASON_REPOSITION: "Oura awake, Garmin asleep — read as repositioning",
    REASON_WAKE_CONFIRMED: "Oura awake, Garmin corroborates — real awakening",
    REASON_GARMIN_WAKE: "Garmin awake, Oura asleep — isolated limb movement",
    REASON_SMOOTHED: "Isolated one-minute awake, smoothed",
    REASON_OURA_PASSTHROUGH: "No Garmin coverage — Oura unchanged",
    REASON_NO_DATA: "Neither device covered this minute",
    REASON_STILL_ASLEEP: "Oura awake, Garmin asleep, body still — asleep",
    REASON_MOTION_AWAKE: "Oura awake, sustained motion — awakening kept",
    REASON_DEEP_MOTION: "Deep sleep with whole-body motion — deferred to Garmin",
}


# ─── Timezone normalisation ─────────────────────────────────────────────────
# Two NAMED converters rather than one lenient one that guesses. Garmin's
# sleepLevels timestamps are naive strings that ARE UTC; Garmin ALSO exposes
# naive local strings elsewhere (startTimeLocal). A single guessing parser
# applied to the wrong one would be silently wrong by exactly the UTC offset —
# an error that produces a plausible hypnogram and breaks nothing visibly.

def utc_from_gmt_string(value) -> datetime | None:
    """Garmin sleepLevels startGMT/endGMT: "2026-07-27T19:38:00.0", naive but
    denoting UTC. Returns an AWARE UTC datetime."""
    parsed = hr_matching._to_dt(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_from_iso_offset(value) -> datetime | None:
    """Oura bedtime_start: ISO carrying a real UTC offset. Returns an AWARE
    UTC datetime. A naive value is treated as already-UTC rather than guessed
    at, so the failure mode is visible rather than silently shifted."""
    parsed = hr_matching._to_dt(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_offset_minutes(start_gmt_ms, start_local_ms) -> int | None:
    """The night's UTC offset, from Garmin's GMT/local epoch-millisecond pair.

    Used for the night's local-date LABEL and for display only — never for
    alignment, which works entirely in absolute UTC instants. Keeping it off
    the correctness path means a wrong offset degrades a label, not a
    hypnogram."""
    try:
        return int(round((float(start_local_ms) - float(start_gmt_ms)) / 60000.0))
    except (TypeError, ValueError):
        return None


# ─── Minute arrays ──────────────────────────────────────────────────────────

def oura_minutes(phase_30_sec: str | None) -> list[int]:
    """Oura's 30-second hypnogram -> one stage per minute.

    Uses the 30-SECOND string, never sleep_phase_5_min: 5-minute blocks would
    upsample to five identical minutes and destroy exactly the single-minute
    granularity the isolated-awake smoothing rule exists to act on."""
    text = str(phase_30_sec or "").strip()
    if not text:
        return []
    out: list[int] = []
    for i in range(0, len(text), 2):
        pair = text[i:i + 2]
        stages = [int(c) for c in pair if c.isdigit() and int(c) in STAGE_LABELS]
        if not stages:
            out.append(UNCOVERED)
        elif len(stages) == 1:
            out.append(stages[0])
        else:
            out.append(dominant_stage({s: 30.0 for s in stages}))
    return out


def dominant_stage(weighted: dict[int, float]) -> int:
    """The stage holding the most seconds in one minute; ties broken by
    RESAMPLE_PRIORITY (awake first — never manufacture sleep)."""
    real = {s: sec for s, sec in weighted.items() if s != UNCOVERED and sec > 0}
    if not real:
        return UNCOVERED
    best = max(real.values())
    tied = [s for s, sec in real.items() if sec == best]
    if len(tied) == 1:
        return tied[0]
    for stage in RESAMPLE_PRIORITY:
        if stage in tied:
            return stage
    return tied[0]


def garmin_minutes(segments: list[dict], window_start: datetime,
                   minute_count: int) -> tuple[list[int], dict]:
    """Resample Garmin's variable-length stage segments onto the fixed
    one-minute grid anchored at window_start.

    Returns (minutes, diagnostics). Minutes no segment covers are UNCOVERED —
    NEVER Awake. Garmin does not always emit an explicit awake segment (it
    sometimes carries that in sleepMovement instead), so treating a gap as
    wakefulness would inject phantom wake from the very device being used to
    remove it.

    Only the minutes each segment actually spans are visited, so the cost is
    O(total covered minutes), not O(minutes x segments) — a full-history
    rebuild walks ~400 nights.
    """
    minutes = [UNCOVERED] * minute_count
    diagnostics = {
        "covered_minutes": 0, "gap_minutes": 0, "outside_window_minutes": 0,
        "segment_count": len(segments or []),
    }
    if not segments or minute_count <= 0 or window_start is None:
        diagnostics["gap_minutes"] = max(0, minute_count)
        return minutes, diagnostics

    weights: dict[int, dict[int, float]] = {}
    for seg in segments:
        stage = GARMIN_LEVEL_TO_STAGE.get(_as_float(seg.get("activityLevel")))
        start = utc_from_gmt_string(seg.get("startGMT"))
        end = utc_from_gmt_string(seg.get("endGMT"))
        if stage is None or start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        first = int((start - window_start).total_seconds() // 60)
        last = int(-(-(end - window_start).total_seconds() // 60))  # ceil
        if last <= 0 or first >= minute_count:
            diagnostics["outside_window_minutes"] += max(0, last - first)
            continue
        if first < 0:
            diagnostics["outside_window_minutes"] += -first
        if last > minute_count:
            diagnostics["outside_window_minutes"] += last - minute_count
        for k in range(max(0, first), min(minute_count, last)):
            m0 = window_start + timedelta(minutes=k)
            overlap = hr_matching.overlap_seconds(m0, m0 + timedelta(minutes=1), start, end)
            if overlap > 0:
                weights.setdefault(k, {})[stage] = weights.setdefault(k, {}).get(stage, 0.0) + overlap

    for k, w in weights.items():
        minutes[k] = dominant_stage(w)
    diagnostics["covered_minutes"] = sum(1 for m in minutes if m != UNCOVERED)
    diagnostics["gap_minutes"] = minute_count - diagnostics["covered_minutes"]
    return minutes, diagnostics


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ─── The rules ──────────────────────────────────────────────────────────────

def _garmin_wake_near(garmin: list[int], i: int, radius: int) -> bool:
    """Does Garmin flag Awake within +/-radius minutes of i? Garmin's Awake is
    the strict filter, so this is what separates a real awakening from a
    position shift."""
    lo, hi = max(0, i - radius), min(len(garmin), i + radius + 1)
    return any(garmin[j] == AWAKE for j in range(lo, hi))


def _deep_runs(oura: list[int]) -> dict[int, tuple[int, int]]:
    """index -> (run_start, run_length) for every minute inside a contiguous
    Oura-Deep run. Precomputed once so the rule-3 check is O(1) per minute."""
    runs: dict[int, tuple[int, int]] = {}
    i, n = 0, len(oura)
    while i < n:
        if oura[i] != DEEP:
            i += 1
            continue
        start = i
        while i < n and oura[i] == DEEP:
            i += 1
        for k in range(start, i):
            runs[k] = (start, i - start)
    return runs


def _is_deep_excess(i: int, runs: dict[int, tuple[int, int]], minute_count: int) -> bool:
    """Rule 3's second-half override: the run is longer than plausible, it
    STARTS in the second half of the night, and minute i is beyond the run's
    first DEEP_RUN_PLAUSIBLE_MINUTES. Slow-wave sleep is expected to be long
    early, so an equally long run in the first half is left alone."""
    run = runs.get(i)
    if run is None:
        return False
    start, length = run
    if length <= DEEP_RUN_PLAUSIBLE_MINUTES:
        return False
    if start < minute_count // 2:
        return False
    return (i - start) >= DEEP_RUN_PLAUSIBLE_MINUTES


def _motion_minutes_near(movement: list[int], i: int, radius: int, threshold: int) -> int:
    """How many minutes within +/-radius of i reach `threshold` motion."""
    lo, hi = max(0, i - radius), min(len(movement), i + radius + 1)
    return sum(1 for j in range(lo, hi) if movement[j] >= threshold)


def _still_around(movement: list[int], i: int, radius: int) -> bool:
    """Is the body still throughout +/-radius of i?

    Requires the window to be MEASURED, not merely free of reported motion —
    an uncovered slot is not evidence of stillness, and treating it as such
    would let a gap in the movement series manufacture the highest-confidence
    "asleep" verdict available.
    """
    lo, hi = max(0, i - radius), min(len(movement), i + radius + 1)
    window = movement[lo:hi]
    return bool(window) and all(m == MOTION_STILL for m in window)


def merge_minute(oura: list[int], garmin: list[int], i: int,
                 runs: dict[int, tuple[int, int]] | None = None,
                 movement: list[int] | None = None) -> tuple[int, str]:
    """One aligned minute through the rule hierarchy. Returns (stage, reason).

    `movement` is the FUSED per-minute motion series (services/
    sleep_movement.py, reduced from its 30-second grid by max). None means no
    movement evidence for this night, and every rule below falls back to its
    version-1 behaviour — which is what lets RULES_VERSION 2 be applied to the
    whole history without changing a single night that predates the watch.
    """
    o = oura[i] if i < len(oura) else UNCOVERED
    g = garmin[i] if i < len(garmin) else UNCOVERED
    m = movement[i] if movement and i < len(movement) else UNCOVERED

    if o == UNCOVERED and g == UNCOVERED:
        return UNCOVERED, REASON_NO_DATA
    if g == UNCOVERED:
        # No Garmin opinion — Oura passes through untouched. This is what makes
        # a Garmin-less night bit-identical to Oura alone.
        return o, REASON_OURA_PASSTHROUGH
    if o == UNCOVERED:
        return g, REASON_OURA_PASSTHROUGH

    if o == g:                                          # rule 1
        return o, REASON_AGREE

    if o == AWAKE:                                      # rule 2, Oura's wake
        if _garmin_wake_near(garmin, i, WAKE_CONFIRM_RADIUS_MINUTES):
            return AWAKE, REASON_WAKE_CONFIRMED
        if m != UNCOVERED:
            # Rules 5 and 6. Version 1 had ONE verdict here — "repositioning" —
            # for three physically different situations, because stage labels
            # alone cannot tell them apart. Motion can.
            if _motion_minutes_near(movement, i, MOTION_RADIUS_MINUTES,
                                    MOTION_AWAKE_FROM) >= MOTION_AWAKE_SUSTAINED_MINUTES:
                # Rule 6: not a shift, someone who is up. Version 1 would have
                # converted this to sleep; keeping it is the first time
                # movement PREVENTS an awake minute being erased.
                return AWAKE, REASON_MOTION_AWAKE
            if _still_around(movement, i, STILL_RADIUS_MINUTES):
                # Rule 5: Garmin says asleep and the body did not move. The
                # same verdict version 1 reached, now on evidence rather than
                # on the hypermobility premise alone.
                return LIGHT, REASON_STILL_ASLEEP
        return LIGHT, REASON_REPOSITION

    if g == AWAKE:                                      # rule 2, Garmin's wake
        return LIGHT, REASON_GARMIN_WAKE

    # rule 3 — both asleep, disagree. Oura wins, with two exceptions.
    if o == DEEP:
        if m >= MOTION_ACTIVE:
            # Rule 7. Slow-wave sleep is the most motionless state there is,
            # and sustained SWS essentially does not contain whole-body
            # postural shifts. A physiological test, where DEEP_RUN_PLAUSIBLE
            # below is only a rule of thumb about run length.
            return g, REASON_DEEP_MOTION
        if _is_deep_excess(i, runs or {}, len(oura)):
            return g, REASON_DEEP_EXCESS
    return o, REASON_OURA_WINS


def smooth_isolated_awake(master: list[int], reasons: list[str],
                          oura: list[int], garmin: list[int]) -> tuple[list[int], list[str]]:
    """Rule 4. A single master-Awake minute whose neighbours are asleep on
    BOTH raw devices is a fragmentary arousal, not an awakening — reclassify
    as Light.

    Reads the RAW device arrays, per the rule's own wording ("on both
    devices"), and runs after rules 1-3 because there is no master-Awake
    minute to smooth before then. Decisions are taken against a frozen
    snapshot and written into copies, so a smoothed minute can never cascade
    into its neighbour and the result cannot depend on scan direction.

    A minute rule 2 already marked WAKE_CONFIRMED is exempt. Rule 2 looks
    +/-WAKE_CONFIRM_RADIUS_MINUTES for corroboration while this rule looks
    only at immediate neighbours, so without the exemption a wake Garmin
    corroborated three minutes away would still be smoothed off — which would
    make rule 2's corroboration branch nearly dead code for exactly the
    one-minute awakenings it exists to protect, and would have fusion erasing
    real awakenings rather than phantom ones.

    MOTION_AWAKE is exempt for the identical reason: rule 6 established that
    wake from sustained motion across +/-MOTION_RADIUS_MINUTES, and smoothing
    it away here would silently undo the one rule whose entire purpose is to
    stop a real awakening being converted to sleep.
    """
    protected = (REASON_WAKE_CONFIRMED, REASON_MOTION_AWAKE)
    out, out_reasons = list(master), list(reasons)
    for i in range(1, len(master) - 1):
        if master[i] != AWAKE or master[i - 1] == AWAKE or master[i + 1] == AWAKE:
            continue
        if reasons[i] in protected:
            continue
        neighbours = (oura[i - 1], oura[i + 1], garmin[i - 1], garmin[i + 1])
        if all(stage in SLEEP_STAGES for stage in neighbours):
            out[i] = LIGHT
            out_reasons[i] = REASON_SMOOTHED
    return out, out_reasons


def fuse(oura: list[int], garmin: list[int] | None,
         movement: list[int] | None = None) -> tuple[list[int], list[str], str]:
    """The whole hierarchy. Returns (master, reason_codes, source).

    Contract mirrored from hr_load.blend_strain: when one source is absent the
    output collapses to the other, bit-identically. A night with no Garmin
    data behaves exactly as it did before this module existed.

    `movement` is the fused per-minute motion series and is optional; omitting
    it reproduces RULES_VERSION 1 exactly. Note movement alone never changes a
    verdict — every rule that reads it sits inside a branch that already
    required Garmin's stage opinion, so a night with movement but no Garmin
    stages still passes Oura straight through.
    """
    if not oura:
        return [], [], SOURCE_NONE
    if not garmin or all(g == UNCOVERED for g in garmin):
        return list(oura), [REASON_OURA_PASSTHROUGH] * len(oura), SOURCE_OURA_ONLY

    padded = list(garmin[:len(oura)]) + [UNCOVERED] * max(0, len(oura) - len(garmin))
    runs = _deep_runs(oura)
    master: list[int] = []
    reasons: list[str] = []
    for i in range(len(oura)):
        stage, reason = merge_minute(oura, padded, i, runs, movement)
        master.append(stage)
        reasons.append(reason)
    master, reasons = smooth_isolated_awake(master, reasons, oura, padded)
    return master, reasons, SOURCE_FUSED


# ─── Encoding + derived measures ────────────────────────────────────────────

def encode(minutes: list[int]) -> str:
    """Digit string, one char per minute — the same shape as Oura's own
    hypnogram columns. Stored as TEXT: see _SLEEP_FUSION_NUMERICISE_IGNORE in
    services/repository.py for why a digit string must never be numericised."""
    return "".join(str(m) for m in minutes)


def decode(text: str | None) -> list[int]:
    return [int(c) for c in str(text or "").strip() if c.isdigit()]


def stage_totals(minutes: list[int]) -> dict[int, int]:
    """Minutes per stage. Every stage key is present, including zeros, so
    callers never have to guard a missing key."""
    totals = {stage: 0 for stage in (DEEP, LIGHT, REM, AWAKE, UNCOVERED)}
    for m in minutes:
        if m in totals:
            totals[m] += 1
    return totals


def sleep_minutes(minutes: list[int]) -> int:
    return sum(1 for m in minutes if m in SLEEP_STAGES)


def phantom_wake_minutes(oura: list[int], master: list[int]) -> int:
    """Minutes Oura called Awake that the master calls sleep.

    Deliberately in the same unit as the manual wake-time correction
    (services/sleep_score.py's wake_time_adjustments — "minutes to subtract
    from recorded awake time"), which is what lets effective_wake_adjustments
    treat the two as interchangeable per night."""
    n = min(len(oura), len(master))
    return sum(1 for i in range(n) if oura[i] == AWAKE and master[i] in SLEEP_STAGES)


def agreement(oura: list[int], garmin: list[int]) -> tuple[float | None, float | None]:
    """(percent agreement, Cohen's kappa) over minutes BOTH devices covered.

    Kappa corrects for the agreement two devices would reach by chance alone,
    which matters here because both spend most of the night in Light — raw
    percent agreement flatters them. Display-only: no decision reads this.
    """
    pairs = [(o, g) for o, g in zip(oura, garmin)
             if o != UNCOVERED and g != UNCOVERED]
    if not pairs:
        return None, None
    n = len(pairs)
    observed = sum(1 for o, g in pairs if o == g) / n
    stages = (DEEP, LIGHT, REM, AWAKE)
    expected = sum(
        (sum(1 for o, _ in pairs if o == s) / n) * (sum(1 for _, g in pairs if g == s) / n)
        for s in stages
    )
    pct = round(observed * 100, 1)
    if expected >= 1.0:
        return pct, None
    return pct, round((observed - expected) / (1 - expected), 3)


def window_overlap_fraction(a_start, a_end, b_start, b_end) -> float:
    """Shared span as a fraction of the SHORTER window. Guards the night
    pairing: Oura keys a night by wake date and Garmin by its own date, and a
    silent one-day misalignment would produce an entirely plausible but wrong
    hypnogram — the worst failure mode in this module."""
    overlap = hr_matching.overlap_seconds(a_start, a_end, b_start, b_end)
    if not overlap:
        return 0.0
    spans = [
        abs((a_end - a_start).total_seconds()),
        abs((b_end - b_start).total_seconds()),
    ]
    shortest = min(s for s in spans if s > 0) if any(s > 0 for s in spans) else 0.0
    return round(overlap / shortest, 4) if shortest else 0.0


def night_summary(day: str, window_start: datetime | None, oura: list[int],
                  garmin: list[int] | None, offset_minutes: int | None = None,
                  oura_periods_on_day: int = 1, garmin_diagnostics: dict | None = None,
                  overlap_fraction: float | None = None,
                  movement: list[int] | None = None) -> dict:
    """The stage half of the persisted row, same role as
    hr_load.session_hr_summary. Its keys are a subset of _SLEEP_FUSION_HEADER;
    the movement columns are filled by services/sleep_movement.py's
    movement_summary, and a test asserts the two together cover the header."""
    master, reasons, source = fuse(oura, garmin, movement)
    padded = list((garmin or [])[:len(oura)]) + [UNCOVERED] * max(0, len(oura) - len(garmin or []))
    totals = stage_totals(master)
    diag = garmin_diagnostics or {}
    pct, kappa = agreement(oura, padded)
    return {
        "date": day,
        "source": source,
        "rules_version": RULES_VERSION,
        "window_start_utc": window_start.isoformat() if window_start else "",
        "utc_offset_minutes": offset_minutes,
        "minutes": len(master),
        "master_hypnogram": encode(master),
        "oura_hypnogram": encode(oura),
        "garmin_hypnogram": encode(padded),
        "reason_codes": "".join(reasons),
        "master_deep_minutes": totals[DEEP],
        "master_light_minutes": totals[LIGHT],
        "master_rem_minutes": totals[REM],
        "master_awake_minutes": totals[AWAKE],
        "master_sleep_hours": round(sleep_minutes(master) / 60.0, 2),
        "oura_sleep_hours": round(sleep_minutes(oura) / 60.0, 2),
        "garmin_sleep_hours": round(sleep_minutes(padded) / 60.0, 2),
        "phantom_wake_minutes": phantom_wake_minutes(oura, master),
        "window_overlap_pct": round((overlap_fraction or 0.0) * 100, 1),
        "agreement_pct": pct,
        "cohen_kappa": kappa,
        "garmin_covered_minutes": diag.get("covered_minutes"),
        "garmin_gap_minutes": diag.get("gap_minutes"),
        "garmin_outside_window_minutes": diag.get("outside_window_minutes"),
        "oura_periods_on_day": oura_periods_on_day,
    }


# ─── Collision with the manual wake-time correction ─────────────────────────

WAKE_SOURCE_FUSION = "fusion"
WAKE_SOURCE_MANUAL = "manual"


def effective_wake_adjustments(manual: dict[str, float] | None,
                               fused: dict[str, float] | None,
                               ) -> tuple[dict[str, float], dict[str, str]]:
    """Resolve the two mechanisms that both remove phantom Oura wake.

    services/sleep_score.py's wake_time_adjustments is a manual per-night
    correction for Oura's known wake-overestimation. Fusion computes the same
    quantity from Garmin. Applying both would subtract the same phantom
    minutes twice.

    Strict per-night precedence: a night with a fused figure uses it; a night
    without one keeps its manual value, behaving exactly as before. The two
    can never both apply, so double-counting is impossible by construction
    rather than by arithmetic.

    Returns (adjustments, sources) so the UI can say which one won — and so
    the pair (what you would have entered, what fusion computed) accumulates
    as the calibration data needed to eventually retire the manual knob.
    """
    out: dict[str, float] = {}
    sources: dict[str, str] = {}
    for day, minutes in (manual or {}).items():
        if minutes:
            out[day] = float(minutes)
            sources[day] = WAKE_SOURCE_MANUAL
    for day, minutes in (fused or {}).items():
        if minutes:
            out[day] = float(minutes)
            sources[day] = WAKE_SOURCE_FUSION
    return out, sources
