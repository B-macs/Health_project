"""services/hrv_trend.py — HRV trend, both devices on ONE millisecond axis.

⚠ DISPLAY ONLY. This module feeds NO guardrail — not engine.traffic_light,
not engine.acwr, not readiness, not volume_recommendation. Key rule 2b is the
reason: a figure that moves depending on which device was worn would swing a
safety ceiling on button behaviour rather than on physiology. Same stance
services/sleep_fusion.py takes, and the fence is structural rather than
intended — tests/test_hrv_trend_display_only.py AST-scans the import graph in
BOTH directions and fails if engine/rules/readiness ever reference this module,
or if this module ever references them.

Nothing here is persisted. Every figure recomputes from the two raw nightly
series on every call, so a changed constant self-heals rather than leaving a
stored number derived from a rule that no longer exists (CLAUDE.md's Stage 1
over-count).


THE AXIS, AND WHY IT IS NOT A PERCENTAGE
────────────────────────────────────────
The athlete asked for "a percentage difference or some other way" so that an
Oura reading and a Garmin reading sit on one graph despite Garmin running
higher. Percentage is the obvious reading of that and it is the wrong tool
here, for two reasons measured on his own data:

  1. The two devices' denominators differ. His Oura normal is ~20.5 ms and
     Garmin's ~33.0. On 2026-08-16 BOTH devices moved +14 ms — identical
     physiology — and percent-of-own-normal renders that as Oura +66.0%
     against Garmin +45.7%. The graph would show them disagreeing on a night
     they agreed exactly.
  2. Percent is not comparable to itself across time. His Oura normal has
     ranged 14 to 28 ms, so "−20%" means 2.8 ms in one month and 5.6 ms in
     another.

The offset between the devices is ADDITIVE, not multiplicative — measured over
the 18 paired nights to 2026-08-23: Garmin higher on 18 of 18, mean +9.44 ms,
population sd 1.77; additive RMSE 1.771 against multiplicative 3.136. Crucially
sd_garmin / sd_oura = 0.978, i.e. the two devices' night-to-night SPREADS agree
to within 2.2%.

That is what makes the honest axis simply:

    from_normal(device, night) = reading − that device's own trailing normal

Both lines are in real milliseconds, the +9.44 offset cancels exactly under the
subtraction (no fitted constant is stored anywhere), and a 1 ms step on one line
means the same as a 1 ms step on the other. It delivers what he asked for —
equal moves draw equal steps — without the distortion percent would add.

EACH DEVICE IS CENTRED ON ITS OWN HISTORY, never on nights they share. Centring
on shared nights is tidier and it fails catastrophically on this athlete's real
record: his longest ring-off stretch in the last two years is 274 nights
(2025-09-30 → 2026-06-30), 26 of them with the watch recording. A shared-night
design goes completely dark across it.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

# ── The chart's trailing centre ──────────────────────────────────────────────
# 28 nights because engine.traffic_light already scores HRV against a 28-day
# mean. Two screens must not disagree about what "recent" means.
BASELINE_NIGHTS = 28
# 14 == biometrics.MIN_HRV_PAIRED_NIGHTS == sleep_movement.MIN_CALIBRATION_NIGHTS.
# Same n=14 judgement, same situation: below it a centre is a guess wearing a
# number.
BASELINE_MIN_READINGS = 14

# MEDIAN, not mean. Measured on the watch's own window: recomputing it with and
# without the 2026-08-15 collapse moves the mean +1.16 ms and the spread 3.72 →
# 0.73 (5.1×), while the median moves 0.00. A single freak night must not
# redefine "normal".

# ── The downward flag ────────────────────────────────────────────────────────
NOISE_MULTIPLE = 2.0  # == services.battery's idiom: under ~2× the observed
                      # spread is not a result.
DEPTH_WINDOWS = (3, 4, 5)

#: ⚠ INVENTED-FROM-MEASUREMENT, and the athlete's own data is the source.
#: 2 × the standard deviation of drop_k measured over the FULL 380-night Oura
#: record with the reference window ending strictly before each run
#: (n = 244 / 221 / 200 windows). No s/√k assumption, no independence claim, no
#: Gaussian claim — the spread of the k-night mean is measured directly.
#:
#: Note the floors RISE as the window shortens: a 3-night warning needs a
#: BIGGER drop than a 5-night one, because averaging fewer nights is noisier.
#: Three days is the strict leg, not the fast one.
#:
#: REVERT CONDITION (HRV_GARMIN_HOLD idiom): re-fit when the Oura record grows
#: past ~500 nights, or on any device change. Held on evidence, not on a date.
DEPTH_FLOOR_MS = {3: 8.56, 4: 7.39, 5: 6.75}

#: Consecutive falling nights before the shape leg fires. Calibrated by shuffle
#: (600 reshuffles inside the 13 contiguous blocks of ≥8 nights, 289 nights):
#: ≥3 occurs on 16.26% of nights against 12.22% by chance (1.33×) — one night in
#: six is not a flag. ≥4 is 4.15% against 2.35% (1.77×). ≥5 has happened twice
#: ever. Four is the bar.
SHAPE_MIN_RUN = 4

#: Below this many of its OWN measured windows a device borrows the other's
#: floors, and says so. Justified by sd_garmin/sd_oura = 0.978.
DEVICE_OWN_FLOOR_MIN_WINDOWS = 60

#: ⚠ THIS SWITCHES A SENTENCE ON AND OFF. THERE IS NO SETTING OF IT THAT MAKES
#: THE RUN ACT.
#:
#: Deliberately NOT named *_ADVISORY_MODE, the way engine.ACWR_ADVISORY_MODE and
#: strain_regions' advisory_only are. Both of those describe a wire that EXISTS
#: and is currently held open, and both are expected to be flipped one day.
#: There is no such wire here: nothing in engine.py or services/sessions.py ever
#: receives this text, so False means the athlete stops being told — it can
#: never mean the run starts deciding.
#:
#: Added 2026-08-23 on the athlete's ask that the run APPEAR in the training
#: statement while changing no prescribed weight, rep, volume factor or ceiling.
#: Allowed out of a display-only module because ring_run_advisory reads the RING
#: ALONE — the same source engine.traffic_light already scores HRV against, since
#: biometrics.HRV_GARMIN_HOLD keeps hrv_ms Oura's or nothing — so it adds no new
#: dependence on which device was worn (key rule 2b). The 60/40 combined figure
#: does, and does not leave this file.
#:
#: REVERT CONDITION (HRV_GARMIN_HOLD idiom — evidence, not a date): re-measure
#: the fire rate over the first 90 days it is on screen and set this False if it
#: exceeds ~15% of days. The athlete's own bar is at SHAPE_MIN_RUN above — "one
#: night in six is not a flag" — and the calibrated rate is 4.15% of nights
#: against 2.35% by chance, so anything approaching 15% means DEPTH_FLOOR_MS has
#: drifted rather than that he is declining. Key rule 20's own lesson: a warning
#: on every session is ignored, at which point it is not a safety message.
HRV_RUN_ON_TRAINING_SCREEN = True

# ── Divergence ───────────────────────────────────────────────────────────────
#: Both devices report WHOLE milliseconds, so the gap series is quantised and a
#: rank-based spread collapses to exactly 0.00 on it (measured: MAD and Sn both
#: 0.00 on a gap series with a real range of 8 ms, which flagged 10 of 11 nights
#: as disagreeing). This floor is load-bearing, not tidying.
GAP_BAND_FLOOR_MS = 2.0
DIVERGENCE_MIN_PAIRED = 10

# ── The combined figure ──────────────────────────────────────────────────────
#: The athlete's rule, 2026-08-23: "if garmin moved one way and oura the other,
#: id put more emphasis on the oura but not much more."
#:
#: 0.60/0.40 priced in the unit on screen: on 2026-08-17 the ring read −3.0 and
#: the watch −1.0, giving −2.2 — 0.8 ms of movement from the ring, 1.2 from the
#: watch. The ring leads and the watch stays visibly in the number. A weighted
#: median, the pure rank answer, is degenerate at n=2: any weight over 0.5
#: returns Oura outright, which is "much more", not "not much more".
OURA_SHARE = 0.60
GARMIN_SHARE = 1.0 - OURA_SHARE

#: The metrics whose two devices are close enough in SPREAD to share one
#: millisecond axis. A BAND, not a minimum — Garmin's sleep score has a spread
#: 2.4× Oura's and would pass a one-sided test while being nonsense on a shared
#: axis. Measured: HRV 0.978 passes; resting HR 0.744 is blocked.
AMPLITUDE_RATIO_BAND = (0.85, 1.18)
SHARED_AXIS_METRICS = ("hrv_ms",)

#: A night is ABSENT from the mapping, never present as 0. A reading of 0 ms
#: would be a dead athlete; a missing night is a night the device was not worn.
Series = Mapping[date, float]

_OURA = "oura"
_GARMIN = "garmin"
#: Patient-facing device words. "ring" and "watch" are what he calls them.
DEVICE_WORDS = {_OURA: "ring", _GARMIN: "watch"}


# ─────────────────────────────────────────────────────────────────────────────
#  Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Normal:
    """One device's trailing centre, and how much it rests on."""
    device: str
    normal_ms: float | None
    readings_used: int
    readings_needed: int
    window_end: date
    provisional: bool          # fewer than BASELINE_NIGHTS readings available
    refusal: str | None = None


@dataclass(frozen=True)
class NightPoint:
    """One night on the common graph."""
    day: date
    oura_ms: float | None
    garmin_ms: float | None
    oura_from_normal: float | None
    garmin_from_normal: float | None
    combined_from_normal: float | None   # None unless BOTH devices reported
    gap_ms: float | None
    diverged: bool | None                # None when only one device reported
    sources: str                         # both | oura_only | garmin_only | none


@dataclass(frozen=True)
class DownwardFlag:
    device: str
    firing: bool
    legs: tuple[str, ...]
    readings_ms: tuple[float, ...]
    normal_ms: float | None
    run_length: int
    depth: dict = field(default_factory=dict)   # k -> {drop_ms, floor_ms, ratio, fired}
    floor_source: str = "own"
    provisional: bool = False
    sentence: str = ""
    refusal: str | None = None


@dataclass(frozen=True)
class DivergenceInfo:
    centre_ms: float | None
    spread_ms: float | None
    band_ms: float | None
    paired_nights: int
    diverging_days: tuple[date, ...]
    refusal: str | None = None


@dataclass(frozen=True)
class HrvTrendPanel:
    oura_normal: Normal
    garmin_normal: Normal
    nights: tuple[NightPoint, ...]
    divergence: DivergenceInfo
    oura_flag: DownwardFlag
    garmin_flag: DownwardFlag
    headline: str
    #: Documentation. The enforcement is the import-graph test, not this field.
    display_only: bool = True


# ─────────────────────────────────────────────────────────────────────────────
#  Primitives
# ─────────────────────────────────────────────────────────────────────────────

def _window_readings(series: Series, window_end: date,
                     nights: int = BASELINE_NIGHTS) -> list[float]:
    """The readings present in the `nights` calendar days ending at window_end
    (inclusive). Absent nights contribute nothing — they are not zeros."""
    out = []
    for i in range(nights):
        v = series.get(window_end - timedelta(days=i))
        if v is not None:
            out.append(float(v))
    return out


def normal_for(series: Series, device: str, window_end: date,
               nights: int = BASELINE_NIGHTS,
               min_readings: int = BASELINE_MIN_READINGS) -> Normal:
    """That device's own trailing normal — the MEDIAN of its readings over the
    `nights` days ending at window_end.

    Refuses below `min_readings` rather than returning a centre fitted on a
    handful of nights. On 2026-08-19 the watch had exactly 14 and began
    plotting; before that it had no line at all, which is the honest state.
    """
    vals = _window_readings(series, window_end, nights)
    if len(vals) < min_readings:
        word = DEVICE_WORDS.get(device, device)
        return Normal(
            device=device, normal_ms=None, readings_used=len(vals),
            readings_needed=min_readings, window_end=window_end,
            provisional=True,
            refusal=(f"The {word} has {len(vals)} night"
                     f"{'' if len(vals) == 1 else 's'} of HRV in the last "
                     f"{nights} days. It needs {min_readings} before there is "
                     f"a usual level to compare against."),
        )
    return Normal(
        device=device, normal_ms=statistics.median(vals),
        readings_used=len(vals), readings_needed=min_readings,
        window_end=window_end, provisional=len(vals) < nights,
    )


def from_normal(value_ms: float | None, normal: Normal) -> float | None:
    """Signed milliseconds away from that device's own normal.

    None on a missing reading and None on an unestablished normal — NEVER 0.
    Zero on this axis means "exactly your usual", which is a strong claim about
    a night that may not have been recorded at all.
    """
    if value_ms is None or normal.normal_ms is None:
        return None
    return float(value_ms) - normal.normal_ms


def combine(oura_dev: float | None, garmin_dev: float | None,
            oura_share: float = OURA_SHARE) -> float | None:
    """The one number that leans on the ring, for a night BOTH devices saw.

    None when either is missing, deliberately. Substituting whichever device
    happened to report would make this figure step by up to 0.4 × the gap on
    device presence — the artefact key rule 2b exists to stop. It is a caption
    figure, never a plotted line, so there is nothing to break by refusing.

    The weight is CONSTANT, including on a night the devices disagree. A weight
    that moved on agreement would make the number depend on which device was
    worn by another route.
    """
    if oura_dev is None or garmin_dev is None:
        return None
    return oura_share * oura_dev + (1.0 - oura_share) * garmin_dev


def divergence(oura: Series, garmin: Series, today: date,
               window_nights: int = BASELINE_NIGHTS,
               min_paired: int = DIVERGENCE_MIN_PAIRED) -> DivergenceInfo:
    """Do the two devices disagree about a night, beyond their usual offset?

    ⚠ RUNS ON THE RAW READINGS, never on the plotted deviations. The deviation
    gap carries a systematic +2.50 ms (max 6.00) purely because Oura's 28-night
    window reaches further back than Garmin's can — testing on deviations would
    manufacture disagreement out of wear pattern.

    Both terms recompute live and nothing is stored, so a device swap
    self-corrects rather than being compared against a frozen constant
    (CLAUDE.md's never-pool-two-devices rule).
    """
    gaps: list[tuple[date, float]] = []
    for i in range(window_nights):
        d = today - timedelta(days=i)
        o, g = oura.get(d), garmin.get(d)
        if o is not None and g is not None:
            gaps.append((d, float(g) - float(o)))

    if len(gaps) < min_paired:
        return DivergenceInfo(
            centre_ms=None, spread_ms=None, band_ms=None,
            paired_nights=len(gaps), diverging_days=(),
            refusal=(f"Only {len(gaps)} night"
                     f"{'' if len(gaps) == 1 else 's'} in the last "
                     f"{window_nights} days have a reading from both devices. "
                     f"It takes {min_paired} before they can be compared."),
        )

    values = [g for _, g in gaps]
    centre = statistics.median(values)
    spread = statistics.pstdev(values) if len(values) > 1 else 0.0
    band = max(NOISE_MULTIPLE * spread, GAP_BAND_FLOOR_MS)
    diverging = tuple(sorted(d for d, g in gaps if abs(g - centre) > band))
    return DivergenceInfo(
        centre_ms=centre, spread_ms=spread, band_ms=band,
        paired_nights=len(gaps), diverging_days=diverging,
    )


def _consecutive_readings(series: Series, today: date, k: int) -> list[float] | None:
    """The k readings on the k calendar days ending today, or None if ANY of
    them is missing. A night not recorded is not a low reading."""
    out = []
    for i in range(k - 1, -1, -1):
        v = series.get(today - timedelta(days=i))
        if v is None:
            return None
        out.append(float(v))
    return out


def depth_drop(series: Series, today: date, k: int) -> tuple[float | None, Normal]:
    """How far the last k nights sit below the normal that ENDED where they
    began.

    The reference window stops at today−k, so a slide can never drag down the
    number it is being judged against. Positive drop means downward.
    """
    ref = normal_for(series, _OURA, today - timedelta(days=k))
    vals = _consecutive_readings(series, today, k)
    if vals is None or ref.normal_ms is None:
        return None, ref
    return ref.normal_ms - (sum(vals) / len(vals)), ref


def declining_run(series: Series, today: date, max_look: int = 30) -> int:
    """How many consecutive calendar nights ending today are strictly falling.

    Counts READINGS in the run, so 20 → 17 → 15 → 13 is a run of 4. A gap in
    the calendar ends the run — a missing night cannot be assumed to continue
    a decline.
    """
    if series.get(today) is None:
        return 0
    run = 1
    for i in range(1, max_look):
        cur = series.get(today - timedelta(days=i - 1))
        prev = series.get(today - timedelta(days=i))
        if cur is None or prev is None or not prev > cur:
            break
        run += 1
    return run


def amplitude_ratio(paired: Sequence[tuple[float, float]]) -> dict:
    """Are these two devices' night-to-night SPREADS close enough to share one
    millisecond axis?

    A BAND, not a minimum. Garmin's sleep score has a spread 2.4× Oura's and
    would sail through a one-sided "at least as variable" test while being
    meaningless on a shared axis.
    """
    pairs = [(float(o), float(g)) for o, g in paired
             if o is not None and g is not None]
    n = len(pairs)
    if n < 3:
        return {"n": n, "sd_ratio": None, "opposite_sign_rate": None,
                "shared_axis_ok": False}
    sd_o = statistics.pstdev([o for o, _ in pairs])
    sd_g = statistics.pstdev([g for _, g in pairs])
    ratio = (sd_g / sd_o) if sd_o else None

    opposite = 0
    moves = 0
    for i in range(1, n):
        do = pairs[i][0] - pairs[i - 1][0]
        dg = pairs[i][1] - pairs[i - 1][1]
        if do == 0 and dg == 0:
            continue
        moves += 1
        if do * dg < 0:
            opposite += 1
    opp_rate = (opposite / moves) if moves else 0.0

    lo, hi = AMPLITUDE_RATIO_BAND
    # ⚠ THE GATE IS THE SPREAD RATIO ALONE. opposite_sign_rate is REPORTED,
    # never gated on: measured on the real paired HRV nights it is 2 of 16
    # (12.5%), and at n=16 the 95% interval on that runs roughly 1.5% to 38% —
    # far too wide to be a threshold. Gating on it would reject or accept a
    # metric on which side of the noise two nights happened to land. The spread
    # ratio is what actually separates the cases: HRV 0.978 passes, resting HR
    # 0.744 and Garmin's sleep score 2.439 do not.
    ok = ratio is not None and lo <= ratio <= hi
    return {"n": n, "sd_ratio": ratio, "opposite_sign_rate": opp_rate,
            "shared_axis_ok": ok}


# ─────────────────────────────────────────────────────────────────────────────
#  The downward flag
# ─────────────────────────────────────────────────────────────────────────────

def downward_flag(series: Series, today: date, device: str,
                  floors: Mapping[int, float] = DEPTH_FLOOR_MS,
                  floor_source: str = "own",
                  provisional: bool = False) -> DownwardFlag:
    """Is this device's HRV coming down, over the last 3 to 5 nights?

    ⚠ TAKES ONE SERIES AND ONE DEVICE. It is structurally incapable of reading
    the other device or the combined figure, which is what stops the alert from
    depending on which device was worn. A test pins that handing it an absurd
    second series changes nothing, because there is no parameter to hand one to.

    Two legs, either sufficient:

      DEPTH — the last k nights (k = 3, 4, 5) average more than `floors[k]`
              below the normal that ended before the run began.
      SHAPE — SHAPE_MIN_RUN consecutive falling nights, and tonight below that
              normal. A pure count: no single deep night can carry it, because
              magnitude cannot enter a count.

    The two legs fail in different ways, which is why both exist: depth misses
    a slow steady slide, shape misses a single cliff.
    """
    word = DEVICE_WORDS.get(device, device)
    tonight = series.get(today)
    if tonight is None:
        return DownwardFlag(
            device=device, firing=False, legs=(), readings_ms=(),
            normal_ms=None, run_length=0, floor_source=floor_source,
            provisional=provisional,
            refusal=f"No HRV reading from the {word} for tonight.",
        )

    legs: list[str] = []
    depth: dict[int, dict] = {}
    for k in DEPTH_WINDOWS:
        drop, ref = depth_drop(series, today, k)
        floor = floors.get(k)
        if drop is None or floor is None:
            missing = _consecutive_readings(series, today, k) is None
            depth[k] = {
                "drop_ms": None, "floor_ms": floor, "ratio": None, "fired": False,
                "refusal": (f"one of the last {k} nights has no reading"
                            if missing else
                            f"not enough history to know the {word}'s usual level"),
            }
            continue
        fired = drop > floor
        depth[k] = {"drop_ms": drop, "floor_ms": floor,
                    "ratio": drop / floor if floor else None, "fired": fired,
                    "refusal": None}
        if fired:
            legs.append(f"depth{k}")

    run = declining_run(series, today)
    ref_for_shape = normal_for(series, device, today - timedelta(days=run))
    below = (ref_for_shape.normal_ms is not None
             and float(tonight) < ref_for_shape.normal_ms)
    if run >= SHAPE_MIN_RUN and below:
        legs.append(f"shape{run}")

    readings = tuple(
        v for v in (series.get(today - timedelta(days=i))
                    for i in range(run - 1, -1, -1)) if v is not None
    )
    normal_ms = ref_for_shape.normal_ms

    flag = DownwardFlag(
        device=device, firing=bool(legs), legs=tuple(legs),
        readings_ms=readings, normal_ms=normal_ms, run_length=run,
        depth=depth, floor_source=floor_source, provisional=provisional,
    )
    return DownwardFlag(**{**flag.__dict__, "sentence": _flag_sentence(flag)})


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{round(float(v), 1):g}"


def _flag_sentence(flag: DownwardFlag) -> str:
    """Plain English. Never "baseline", "threshold", "standard deviation" or
    "divergence" — key rule 19, and this string is rendered verbatim."""
    word = DEVICE_WORDS.get(flag.device, flag.device)
    if not flag.firing:
        return ""
    parts = []
    seq = ", ".join(_fmt(v) for v in flag.readings_ms)
    shape = any(l.startswith("shape") for l in flag.legs)
    depths = [l for l in flag.legs if l.startswith("depth")]

    if shape:
        parts.append(
            f"Your HRV has come down {flag.run_length} nights running on the "
            f"{word}: {seq} ms, against a usual level of "
            f"{_fmt(flag.normal_ms)} ms."
        )
    if depths:
        k = int(depths[0][-1])
        d = flag.depth.get(k, {})
        parts.append(
            f"The last {k} nights on the {word} average "
            f"{_fmt(d.get('drop_ms'))} ms below your usual level, which is "
            f"more than your ordinary {k}-night swing of "
            f"{_fmt(d.get('floor_ms'))} ms."
        )
    elif shape:
        quiet = next((flag.depth[k] for k in DEPTH_WINDOWS
                      if flag.depth.get(k, {}).get("drop_ms") is not None), None)
        if quiet:
            parts.append(
                f"The size of the drop is ordinary for you — "
                f"{_fmt(quiet['drop_ms'])} ms where your usual swing reaches "
                f"{_fmt(quiet['floor_ms'])} ms. It is the nights in a row that "
                f"is unusual, not the depth."
            )
    if flag.provisional or flag.floor_source != "own":
        parts.append(
            f"The {word} has only been recording HRV for a short time, so its "
            f"usual level is still settling."
        )
    # ⚠ "ON ITS OWN". This sentence now renders on the training screen, where
    # on a reduced-load day it sits directly under a banner saying every weight
    # and rep IS held. The earlier wording — "Nothing in your training numbers
    # changes because of this" — was true (the run is not what held them) and
    # would not be read that way: two statements about today's numbers,
    # apparently contradicting. That is the contradiction class the athlete has
    # already reported once, on 2026-08-17.
    parts.append("This on its own does not change any of today's numbers.")
    return " ".join(parts)


def ring_run_advisory(oura: Series, today: date) -> str | None:
    """The RING'S downward run, as one sentence, or None.

    ⚠ THE ONLY THING IN THIS MODULE ANYTHING OUTSIDE A VIEW MAY CALL, and the
    only thing that may be quoted on a screen that also carries a load decision.

    NO DEVICE PARAMETER AND NO SECOND SERIES. `_OURA` is a literal inside this
    function, so the sentence cannot be about the watch and cannot be about the
    60/40 combined figure, whatever a caller passes. That is why it exists as
    its own name rather than callers reaching for `downward_flag`, which takes a
    device NAME — and a name selects the word on screen, not the data:
    `downward_flag(garmin, today, "oura")` runs happily and lies.

    KEY RULE 2b, and why this is allowed out of a display-only module: the
    ring's series is the SAME source engine.traffic_light already scores HRV
    against, because biometrics.HRV_GARMIN_HOLD keeps hrv_ms Oura's or nothing.
    So a sentence about the ring adds NO new dependence on which device was
    worn. The combined figure does, and stays in here — `combine`, `OURA_SHARE`
    and `NightPoint.combined_from_normal` are not reachable from this function.

    ⚠ Callers must pass Repository.hrv_trend_series()["oura"] — the RAW ring
    series — never `hrv_ms` off get_biometric_rolling. Those are the same
    numbers today only because the hold is on; the day it lifts, `hrv_ms`
    becomes a 70/30 mixture and this function would start describing a blend
    while claiming to describe the ring.

    Passes `provisional` explicitly so this sentence and the one on the trend
    panel are the SAME sentence for the same night — `downward_flag` defaults it
    False while `panel` computes it, and the two would otherwise differ by the
    "still settling" clause on any stretch where the ring is thin.
    """
    if not HRV_RUN_ON_TRAINING_SCREEN:
        return None
    norm = normal_for(oura, _OURA, today)
    flag = downward_flag(oura, today, _OURA, provisional=norm.provisional)
    return flag.sentence or None


# ─────────────────────────────────────────────────────────────────────────────
#  The one entry point a view calls
# ─────────────────────────────────────────────────────────────────────────────

def panel(oura: Series, garmin: Series, today: date,
          chart_nights: int = BASELINE_NIGHTS) -> HrvTrendPanel:
    """Everything the screen needs, computed and refused in one place."""
    o_norm = normal_for(oura, _OURA, today)
    g_norm = normal_for(garmin, _GARMIN, today)
    div = divergence(oura, garmin, today)

    # ── THE CHART IS ANCHORED, AND BACK-DATED ───────────────────────────────
    # One normal per device — today's — applied to EVERY night that device
    # recorded, however little history sat behind that night at the time.
    #
    # Athlete, 2026-08-23: "we now know the average is 33, so we can back date
    # that data to the first day the watch is used." He is right, though not
    # for the reason he gave: the watch was never calibrating. Every nightly
    # reading was a direct measurement from its first night. The 14-reading
    # minimum is OUR rule for when we will call something a usual level, not
    # the watch's — so refusing to plot 2026-08-06 because nights AFTER it had
    # not happened yet withholds a subtraction we can already do today.
    #
    # It was a trailing per-night normal before this. Two consequences of the
    # change, both real:
    #   + A sustained decline now SHOWS. Under a trailing normal the reference
    #     follows you down, so a slow slide flattens itself out of its own
    #     chart — the module's own known blind spot.
    #   − Every point redraws when the anchor moves. An older point is no
    #     longer fixed. That is the price, and it is the right way round for a
    #     chart whose job is reading a trend rather than replaying what was
    #     knowable on the night.
    #
    # Safe here because the anchor is a MEDIAN: measured on the real watch
    # series it is 33.0 computed from all 18 nights, from the first 14, or with
    # the four declining nights removed. The current slide cannot define the
    # line it is judged against.
    #
    # ⚠ THE FLAG IS NOT ANCHORED AND MUST NOT BE. Its reference deliberately
    # ends where the run BEGINS (see depth_drop) so a slide cannot drag down
    # the number deciding whether it is a slide. Chart and flag answer
    # different questions and keep different references on purpose.
    nights: list[NightPoint] = []
    for i in range(chart_nights - 1, -1, -1):
        d = today - timedelta(days=i)
        o, g = oura.get(d), garmin.get(d)
        od = from_normal(o, o_norm)
        gd = from_normal(g, g_norm)
        gap = (float(g) - float(o)) if (o is not None and g is not None) else None
        diverged = None
        if gap is not None and div.centre_ms is not None and div.band_ms is not None:
            diverged = abs(gap - div.centre_ms) > div.band_ms
        sources = ("both" if o is not None and g is not None else
                   "oura_only" if o is not None else
                   "garmin_only" if g is not None else "none")
        nights.append(NightPoint(
            day=d, oura_ms=o, garmin_ms=g,
            oura_from_normal=od, garmin_from_normal=gd,
            combined_from_normal=combine(od, gd),
            gap_ms=gap, diverged=diverged, sources=sources,
        ))

    # The watch borrows the ring's floors until it has enough of its own
    # windows. Justified by the two devices' spreads agreeing to 2.2%; said out
    # loud on screen rather than assumed.
    garmin_windows = len(garmin)
    g_borrowed = garmin_windows < DEVICE_OWN_FLOOR_MIN_WINDOWS
    o_flag = downward_flag(oura, today, _OURA, provisional=o_norm.provisional)
    g_flag = downward_flag(
        garmin, today, _GARMIN,
        floor_source="borrowed_from_oura" if g_borrowed else "own",
        provisional=g_norm.provisional or g_borrowed,
    )

    return HrvTrendPanel(
        oura_normal=o_norm, garmin_normal=g_norm, nights=tuple(nights),
        divergence=div, oura_flag=o_flag, garmin_flag=g_flag,
        headline=_headline(o_flag, g_flag, div, today),
    )


def _headline(o_flag: DownwardFlag, g_flag: DownwardFlag,
              div: DivergenceInfo, today: date) -> str:
    firing = [f for f in (o_flag, g_flag) if f.firing]
    if not firing:
        return "No downward run in your HRV over the last few nights."
    agree = today not in div.diverging_days and div.centre_ms is not None
    both = len(firing) == 2
    if both and agree:
        return "Both devices show your HRV coming down."
    if both:
        return "Both devices show your HRV coming down, though they disagree about last night."
    word = DEVICE_WORDS.get(firing[0].device, firing[0].device)
    return f"Your HRV is coming down on the {word}."
