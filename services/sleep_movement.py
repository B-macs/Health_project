"""
services/sleep_movement.py — fuse Oura and Garmin overnight MOVEMENT into one
per-30-second motion series.

Companion to services/sleep_fusion.py, which fuses STAGES. Deliberately a
separate module: that one's argument is about stage labels, this one's is about
an incompatible-units problem and a personal calibration. Keeping them apart
means movement work cannot destabilise the staging rules, and RULES_VERSION
there stays a statement about stages.

WHAT MOVEMENT CAN AND CANNOT DECIDE
-----------------------------------
Accelerometry separates ONE axis of sleep and not the other:

                    movement            autonomic (PPG: HR/HRV)
  wake vs sleep     primary             secondary
  light vs deep     weak                primary
  deep vs REM       NONE                primary

The "NONE" is not a sensor limitation, it is physiology. During REM the
brainstem (sublaterodorsal nucleus -> ventromedial medulla) actively paralyses
skeletal muscle via glycinergic/GABAergic inhibition of spinal motor neurons —
REM atonia. Everything but the diaphragm, the extraocular muscles and some
upper-airway muscles is switched off, so gross movement in REM is LOWER than
in light sleep and comparable to deep sleep. What survives atonia is phasic
twitching: brief distal jerks of fingers and toes, which a finger-worn ring may
register and a wrist strap will not.

EXPLICIT NON-GOAL: never use movement to identify REM. "Stillness -> REM" is
simply wrong, because deep sleep is equally still. "Movement -> not REM" only
excludes REM where wake or light already excluded it. Depth stays the PPG's
job. Any future rule that infers REM from motion is a bug, not an enhancement.

What movement IS good for is the wake/sleep axis, and specifically for the
known blind spot there: wrist actigraphy validated against polysomnography has
sensitivity to sleep around 0.97 but specificity to wake around 0.34 (Marino et
al. 2013, Sleep 36(11); the same asymmetry across seven consumer devices in
Chinoy et al. 2021, Sleep 44(5)). Motion finds sleep brilliantly and wake
terribly, because quiet wakefulness looks exactly like sleep to an
accelerometer. That is the gap the fused series exists to narrow.

THE UNITS PROBLEM, WHICH IS THE WHOLE DESIGN
--------------------------------------------
The two devices do not report the same quantity:

  Oura   movement_30_sec  ordinal CLASS 1-4, one char per 30s, published
                          alphabet (1 no motion, 2 restless, 3 tossing and
                          turning, 4 active).
  Garmin sleepMovement    continuous FLOAT per minute on an undocumented
                          scale. Observed range 0.0-8.13 over 53 nights.

Averaging an ordinal class with an undocumented float is meaningless. Before
any weighting can mean anything the two must be on one scale, and the only
defensible direction is Garmin -> Oura: Oura's alphabet is published and
semantic, Garmin's float is neither. quantile_cutpoints() therefore picks
Garmin's three cut points so its four-class marginal distribution matches
Oura's, over the athlete's OWN paired nights — standard quantile mapping, and
the same personal-baseline philosophy as readiness.sleep_baseline and
hr_load's preference for observed HRmax over account-configured zones.
"""

from __future__ import annotations

import math
from datetime import timedelta

from services import sleep_fusion

# ─── Classes — deliberately Oura's own alphabet, so a fused series and an Oura
#     series are directly comparable without either being translated. Mirrors
#     the same choice sleep_fusion.py makes for stage digits. ─────────────────
STILL, RESTLESS, TOSSING, ACTIVE = 1, 2, 3, 4
UNCOVERED = sleep_fusion.UNCOVERED

CLASS_LABELS: dict[int, str] = {
    STILL: "No motion",
    RESTLESS: "Restless",
    TOSSING: "Tossing and turning",
    ACTIVE: "Active",
    UNCOVERED: "No data",
}
CLASSES: tuple[int, ...] = (STILL, RESTLESS, TOSSING, ACTIVE)

# The boundary between "the ring is the better witness" and "the watch is".
# A class of TOSSING or above is a whole-body postural event; below it is
# micro-motion.
HIGH_AMPLITUDE_FROM = TOSSING

# ─── Amplitude-dependent weights ────────────────────────────────────────────
#  The two devices are NOT differently-reliable measurements of the same
#  thing — they are reliable at DIFFERENT AMPLITUDES, so a single fixed ratio
#  would average away exactly what makes each one useful.
#
#    Low amplitude  — a finger sits on a small, light segment and resolves
#      micro-motion that falls below a wrist strap's noise floor. Trust Oura.
#    High amplitude — a real postural shift rotates the whole arm and is
#      unambiguous at the wrist, whereas a finger can reach the top class from
#      a hand twitch that moved no part of the body. Trust Garmin.
#
#  services/biometrics.py already establishes directional per-metric weights
#  in this codebase (Oura 70/30 for HRV and RHR, Garmin 80/20 for steps);
#  this is that idea made amplitude-conditional. Reasoned defaults, not
#  published constants — same status as sleep_score._WEIGHTS, and recalibrate
#  against real nights rather than treating them as settled.
LOW_AMPLITUDE_WEIGHTS: dict[str, float] = {"oura": 0.75, "garmin": 0.25}
HIGH_AMPLITUDE_WEIGHTS: dict[str, float] = {"oura": 0.30, "garmin": 0.70}

# Below this many paired nights the quantile mapping is fitted to too little
# data to mean anything, and quantile_cutpoints returns None so the caller
# falls back to stage-only fusion. Same discipline as
# readiness.sleep_baseline refusing to produce a number under 7 nights: a
# missing calibration must read as missing, never as a fabricated default.
MIN_CALIBRATION_NIGHTS = 14

# Oura reports movement every 30s; Garmin every 60s. Fusion runs on the FINER
# grid — downsampling Oura to match Garmin would destroy real resolution to
# accommodate the coarser device, which is the same argument
# sleep_fusion.oura_minutes makes for using the 30-second hypnogram.
SLOT_SECONDS = 30

# Segment length Garmin actually emits. Verified across 53 archived nights:
# every single sleepMovement segment is exactly 60.0s, no exceptions.
GARMIN_INTERVAL_SECONDS = 60


# ─── Oura ───────────────────────────────────────────────────────────────────

def oura_movement(text: str | None) -> list[int]:
    """Oura's movement_30_sec digit string -> one class per 30-second slot.

    Verified over 414 archived nights: present on 100% of them, at most 1,800
    chars, alphabet strictly 1-4. Anything outside 1-4 becomes UNCOVERED
    rather than raising — a single bad char must not cost the whole night.

    NOTE the string is NOT always the same length as sleep_phase_30_sec. Both
    are anchored at bedtime_start, but on 216 of 414 nights the hypnogram is
    one 30-second block SHORTER (movement matches time_in_bed exactly; the
    hypnogram is occasionally truncated). Callers align at index 0 and
    truncate to the shorter — never assume equal lengths.
    """
    out: list[int] = []
    for ch in str(text or "").strip():
        if not ch.isdigit():
            continue
        value = int(ch)
        out.append(value if value in CLASS_LABELS and value != UNCOVERED else UNCOVERED)
    return out


# ─── Garmin ─────────────────────────────────────────────────────────────────

def parse_garmin_movement(segments: list[dict] | None) -> dict:
    """Garmin's sleepMovement segments -> a GAP-FILLED regular grid.

    Returns {start_utc, interval_seconds, levels, contiguous, segment_count,
    gap_slots}, where `levels` holds one float per interval and None for any
    interval no segment covered.

    Gap-filling rather than gap-flagging is the point. Raw sleepMovement is
    ~78-84k chars a night, over Sheets' 50,000-char cell limit, so it cannot
    be stored losslessly the way sleep_levels_json is. The compact form is
    start + interval + levels[], which is only equivalent to the raw segments
    IF the grid is unbroken — and it is not always: 2 of 53 archived nights
    carry real time gaps (4 minutes on 2026-05-27, 1 minute on 2026-06-02).
    Storing those nights' levels packed end-to-end would shift every value
    after the gap by the gap's width and produce a plausible, silently wrong
    series — the worst failure mode available here.

    So missing intervals get an explicit None and every later value keeps its
    true position. `contiguous` then downgrades from a correctness gate to
    what it should be: a diagnostic saying whether this night needed filling.
    Same spirit as _garmin_sleep_stages_row's totals_match — turn an
    assumption into a stored, checkable fact.
    """
    empty = {"start_utc": None, "interval_seconds": GARMIN_INTERVAL_SECONDS,
             "levels": [], "contiguous": True, "segment_count": 0, "gap_slots": 0}
    if not segments:
        return empty

    parsed = []
    for seg in segments:
        start = sleep_fusion.utc_from_gmt_string(seg.get("startGMT"))
        end = sleep_fusion.utc_from_gmt_string(seg.get("endGMT"))
        level = sleep_fusion._as_float(seg.get("activityLevel"))
        if start is None or end is None or level is None:
            continue
        if end < start:
            start, end = end, start
        parsed.append((start, end, level))
    if not parsed:
        return empty

    parsed.sort(key=lambda t: t[0])
    start_utc = parsed[0][0]
    interval = GARMIN_INTERVAL_SECONDS
    total = int(round((parsed[-1][1] - start_utc).total_seconds() / interval))
    levels: list[float | None] = [None] * max(0, total)

    for seg_start, _seg_end, level in parsed:
        idx = int(round((seg_start - start_utc).total_seconds() / interval))
        if 0 <= idx < len(levels):
            levels[idx] = level

    gaps = sum(1 for v in levels if v is None)
    return {
        "start_utc": start_utc,
        "interval_seconds": interval,
        "levels": levels,
        "contiguous": gaps == 0,
        "segment_count": len(parsed),
        "gap_slots": gaps,
    }


def encode_levels(levels: list[float | None]) -> str:
    """Comma-joined, 2 decimal places, EMPTY for a gap-filled hole.

    ~5 chars per minute, so a 12-hour night is ~3.5k chars against the 50,000
    limit — two orders of magnitude of headroom versus the 84k raw form.
    2dp is well inside the resolution the quantile mapping consumes (the
    observed value range is 0.0-8.13 across ~32,000 samples).
    """
    return ",".join("" if v is None else f"{float(v):.2f}" for v in levels)


def decode_levels(text: str | None) -> list[float | None]:
    raw = str(text or "").strip()
    if not raw:
        return []
    out: list[float | None] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            out.append(None)
            continue
        out.append(sleep_fusion._as_float(part))
    return out


# ─── Calibration: Garmin's float -> Oura's published alphabet ───────────────

def _quantile(sorted_values: list[float], fraction: float) -> float:
    """Empirical quantile by nearest rank. No interpolation: the result is
    used as a class boundary, and a boundary that lands on a value the device
    actually reported is easier to reason about than one between two."""
    if not sorted_values:
        raise ValueError("empty sample")
    idx = int(round(fraction * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(len(sorted_values) - 1, idx))]


def quantile_cutpoints(garmin_values: list[float],
                       oura_classes: list[int],
                       nights: int = 0) -> tuple[float, float, float] | None:
    """Three Garmin cut points that reproduce Oura's own class distribution.

    Both samples must come from the SAME set of nights — this matches
    marginal distributions, so mismatched populations would silently bias the
    mapping. Returns None (never a guessed default) when there is too little
    to fit: fewer than MIN_CALIBRATION_NIGHTS paired nights, or an Oura sample
    so degenerate it implies no boundaries.

    Reference distribution measured over 414 archived nights, for orientation
    when reviewing a fitted result: class 1 76.8%, class 2 18.7%, class 3
    4.35%, class 4 0.17%. Class 4 is genuinely rare, so its boundary sits far
    into the tail and is the least stable of the three — which is the honest
    reason ACTIVE is treated as corroboration in the staging rules rather than
    as proof on its own.
    """
    if nights and nights < MIN_CALIBRATION_NIGHTS:
        return None
    values = sorted(v for v in garmin_values if v is not None)
    classes = [c for c in oura_classes if c in CLASSES]
    if len(values) < 2 or not classes:
        return None

    total = len(classes)
    cumulative = 0.0
    cuts: list[float] = []
    for cls in (STILL, RESTLESS, TOSSING):
        cumulative += sum(1 for c in classes if c == cls) / total
        cuts.append(_quantile(values, cumulative))

    # Strictly increasing, or a class becomes unreachable and the mapping
    # silently loses a level. Happens when Oura's own sample has ~no examples
    # of a class, which is exactly when a fitted boundary is meaningless.
    if not (cuts[0] < cuts[1] < cuts[2]):
        return None
    return (cuts[0], cuts[1], cuts[2])


def garmin_class(value: float | None, cutpoints: tuple[float, float, float] | None) -> int:
    """One Garmin float -> Oura's 1-4 alphabet. UNCOVERED when the value is a
    gap or the mapping has not been calibrated yet."""
    if value is None or cutpoints is None:
        return UNCOVERED
    c1, c2, c3 = cutpoints
    if value < c1:
        return STILL
    if value < c2:
        return RESTLESS
    if value < c3:
        return TOSSING
    return ACTIVE


def garmin_values_on_grid(parsed: dict, window_start,
                          slot_count: int) -> tuple[list[float | None], dict]:
    """Resample Garmin's per-minute levels onto the 30-second fusion grid
    anchored at window_start, still as RAW floats.

    Garmin's movement window is far wider than Oura's sleep period — on real
    nights movement runs 18:39-06:26 (707 minutes) where the Oura period is
    ~427 minutes, roughly 2.7x. It covers settling-down and post-wake time,
    both far more active than sleep.

    That width is why this function exists separately from garmin_slots().
    Fitting the class boundaries on the RAW series while matching them to
    Oura's sleep-period-only class distribution compares two different spans
    of the night: the pre-sleep movement inflates Garmin's upper quantiles, the
    boundaries land too high, and almost every in-sleep minute collapses into
    STILL. Measured, before this was split out: one night mapped to 94.7% STILL
    and 0% at TOSSING or above, i.e. a night with no postural shifts at all,
    which is physiologically implausible. Calibration must see exactly the
    slots fusion will see.

    Uncovered slots stay None, never 0.0. Reporting absence of data as absence
    of motion would feed the staging rules a confident "the body was still"
    for minutes nothing was measured — the same fabrication
    sleep_fusion.garmin_minutes refuses to make for stages.

    Each Garmin minute covers two 30-second slots: held, not interpolated.
    """
    values: list[float | None] = [None] * max(0, slot_count)
    diagnostics = {"covered_slots": 0, "gap_slots": 0, "outside_window_slots": 0}
    levels = parsed.get("levels") or []
    start_utc = parsed.get("start_utc")
    if not levels or start_utc is None or window_start is None or slot_count <= 0:
        diagnostics["gap_slots"] = max(0, slot_count)
        return values, diagnostics

    interval = int(parsed.get("interval_seconds") or GARMIN_INTERVAL_SECONDS)
    per_slot = max(1, interval // SLOT_SECONDS)
    offset = (start_utc - window_start).total_seconds() / SLOT_SECONDS

    for i, value in enumerate(levels):
        first = int(math.floor(offset + i * per_slot))
        for k in range(first, first + per_slot):
            if k < 0 or k >= slot_count:
                diagnostics["outside_window_slots"] += 1
                continue
            values[k] = value

    diagnostics["covered_slots"] = sum(1 for v in values if v is not None)
    diagnostics["gap_slots"] = slot_count - diagnostics["covered_slots"]
    return values, diagnostics


def garmin_slots(parsed: dict, cutpoints: tuple[float, float, float] | None,
                 window_start, slot_count: int) -> tuple[list[int], dict]:
    """garmin_values_on_grid, mapped through the calibration into Oura's
    alphabet. One alignment path shared with the calibration, so the two can
    never drift apart."""
    values, diagnostics = garmin_values_on_grid(parsed, window_start, slot_count)
    diagnostics["calibrated"] = cutpoints is not None
    slots = [garmin_class(v, cutpoints) for v in values]
    if cutpoints is None:
        diagnostics["covered_slots"] = 0
        diagnostics["gap_slots"] = max(0, slot_count)
    return slots, diagnostics


# ─── Fusion ─────────────────────────────────────────────────────────────────

def weights_for(oura_class: int, garmin_class_: int) -> dict[str, float]:
    """Which weight pair applies to this slot.

    The regime is chosen on max(oura, garmin) — if EITHER device saw a
    whole-body event, this is a high-amplitude slot and the watch is the
    better witness. Deciding the regime on the ring alone would let a finger
    twitch pull the slot into the regime where the ring is then trusted least,
    and deciding it on the watch alone would miss events the watch under-reads.
    """
    return (HIGH_AMPLITUDE_WEIGHTS
            if max(oura_class, garmin_class_) >= HIGH_AMPLITUDE_FROM
            else LOW_AMPLITUDE_WEIGHTS)


def fuse_slot(oura_class: int, garmin_class_: int) -> int:
    """One aligned 30-second slot -> one fused class.

    Contract mirrored from sleep_fusion.fuse: when one source is absent the
    output IS the other, unchanged. A night with no Garmin movement therefore
    reproduces Oura's own series bit-identically.

    The weighted mean of two integers with weights summing to 1 always lands
    within [min, max], so the fused class can never claim motion neither
    device saw — the movement analogue of the "never manufacture sleep" rule.
    Half-up rounding, not Python's banker's rounding: no tie is reachable with
    the current constants, but a future weight change must not silently start
    rounding 2.5 down to 2 on an ordinal perceptual scale.
    """
    if oura_class == UNCOVERED and garmin_class_ == UNCOVERED:
        return UNCOVERED
    if garmin_class_ == UNCOVERED:
        return oura_class
    if oura_class == UNCOVERED:
        return garmin_class_

    w = weights_for(oura_class, garmin_class_)
    blended = w["oura"] * oura_class + w["garmin"] * garmin_class_
    fused = int(math.floor(blended + 0.5))
    return max(min(oura_class, garmin_class_), min(max(oura_class, garmin_class_), fused))


def fuse_movement(oura: list[int], garmin: list[int] | None) -> tuple[list[int], str]:
    """Whole-night movement fusion. Returns (fused_slots, source).

    Source strings are sleep_fusion's own, so a movement provenance label and
    a stage provenance label are the same vocabulary and the UI's approved
    naming rule ("Fused" when both contributed, otherwise the device that did)
    applies unchanged to both strips.
    """
    if not oura and not garmin:
        return [], sleep_fusion.SOURCE_NONE
    if not oura:
        return list(garmin or []), sleep_fusion.SOURCE_GARMIN_ONLY
    if not garmin or all(g == UNCOVERED for g in garmin):
        return list(oura), sleep_fusion.SOURCE_OURA_ONLY

    padded = list(garmin[:len(oura)]) + [UNCOVERED] * max(0, len(oura) - len(garmin))
    return [fuse_slot(o, g) for o, g in zip(oura, padded)], sleep_fusion.SOURCE_FUSED


def to_minutes(slots: list[int]) -> list[int]:
    """30-second slots -> one class per minute, reduced by MAX.

    Max, never mean. A minute containing one 30-second burst of thrashing and
    one of stillness is a minute in which the body moved; averaging it to
    "mildly restless" would dilute exactly the events the staging rules look
    for. The stage grid is per-minute (sleep_fusion works in minutes), so this
    is the bridge between the two modules.
    """
    return [max(slots[i:i + 2], default=UNCOVERED) for i in range(0, len(slots), 2)]


# ─── Derived measures — all display/diagnostic, nothing decides on these ────

def class_totals(slots: list[int]) -> dict[int, int]:
    """Slot counts per class, every key present including zeros."""
    totals = {c: 0 for c in (*CLASSES, UNCOVERED)}
    for s in slots:
        if s in totals:
            totals[s] += 1
    return totals


def _runs(slots: list[int], predicate) -> list[tuple[int, int]]:
    """(start_index, length) for every maximal run satisfying predicate."""
    out: list[tuple[int, int]] = []
    i, n = 0, len(slots)
    while i < n:
        if not predicate(slots[i]):
            i += 1
            continue
        start = i
        while i < n and predicate(slots[i]):
            i += 1
        out.append((start, i - start))
    return out


def position_shifts(slots: list[int]) -> list[tuple[int, int]]:
    """Runs at TOSSING or above — candidate whole-body postural events.

    Useful because major postural shifts cluster at stage TRANSITIONS,
    particularly at the end of a REM bout, rather than being spread evenly. A
    shift is therefore better read as "a stage just ended" than as "awake",
    which is what the staging rules act on.
    """
    return _runs(slots, lambda s: s >= HIGH_AMPLITUDE_FROM)


def still_runs(slots: list[int], min_slots: int = 1) -> list[tuple[int, int]]:
    """Runs of STILL at least min_slots long.

    The raw material for quiet-wakefulness detection: a long motionless run is
    the state actigraphy cannot tell from sleep on motion alone (Marino 2013's
    0.34 wake specificity), so it must be paired with an autonomic signal
    before anything is concluded from it.
    """
    return [(s, n) for s, n in _runs(slots, lambda x: x == STILL) if n >= min_slots]


def movement_summary(slots: list[int], source: str) -> dict:
    """Stable per-night shape, same role as sleep_fusion.night_summary."""
    totals = class_totals(slots)
    covered = sum(totals[c] for c in CLASSES)
    shifts = position_shifts(slots)
    return {
        "movement_source": source,
        "movement_slots": len(slots),
        "movement_covered_slots": covered,
        "movement_still_slots": totals[STILL],
        "movement_restless_slots": totals[RESTLESS],
        "movement_tossing_slots": totals[TOSSING],
        "movement_active_slots": totals[ACTIVE],
        "movement_position_shifts": len(shifts),
        "movement_mean_class": (
            round(sum(s for s in slots if s in CLASSES) / covered, 3) if covered else None
        ),
    }
