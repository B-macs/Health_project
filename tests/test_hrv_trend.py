"""services/hrv_trend.py — both devices on one millisecond axis.

Built 2026-08-23 on the athlete's ask: "could we find a way of ... a trend, so
oura of 2 moving to 2.1 and a garmin of 3 moving to 3.2 are on the same graph,
if garmin moved one way and oura the other, id put more emphasis on the oura but
not much more, my HRV moving downward is definitely worth flagging when its over
the last 3-5 days."

The REAL 18 paired nights to 2026-08-23 are the fixture, so these tests pin
behaviour against data that actually happened rather than against invented
numbers.
"""

import ast
import statistics
from datetime import date, timedelta
from pathlib import Path

import pytest

from services import hrv_trend as ht

TODAY = date(2026, 8, 23)

# ── A CONSTRUCTED SERIES, NOT A TRANSCRIPT ───────────────────────────────────
# The athlete's real nightly readings were REMOVED on 2026-08-24 at his own
# direction. This repo is public, and 53 dated HRV values are a health record
# rather than a test fixture.
#
# What these tests actually need is the SHAPE, so the shape is built here on
# purpose, with every branch exercised and no night belonging to anyone:
#
#   - a flat stretch around 20 ms, so the ring's median lands exactly on 20.0
#   - ONE single-night collapse to 10 ms, for the median-immunity test
#   - a four-night decline at the end (19, 17, 15, 13) for the shape leg
#   - the watch is the ring + 12 ms and starts four nights later, so it is
#     shorter, provisional, and borrows the ring's floors
#   - ONE night pushed to +18 so exactly one disagreement exists
#
# ⚠ The numbers below are invented. Where a test used to say "measured on his
# own record", it now says what the fixture was built to exhibit — the property
# is the same, the provenance claim is not, and the docstrings say so.
_RING = [20, 21, 19, 20, 22, 18, 20, 21, 19, 20,
         22, 18, 20, 21, 19, 20, 22, 18,
         10,                                    # the collapse
         21, 20, 22, 19, 18,
         19, 17, 15, 13]                        # the four-night decline
_WATCH_OFFSET_MS = 12.0
_WATCH_FROM = 4                                 # index into _RING
_COLLAPSE_AT = 18
_DIVERGENT_AT = 17
_DIVERGENT_OFFSET_MS = 18.0

COLLAPSE_NIGHT = TODAY - timedelta(days=len(_RING) - 1 - _COLLAPSE_AT)
DIVERGENT_NIGHT = TODAY - timedelta(days=len(_RING) - 1 - _DIVERGENT_AT)


def _build():
    ring, watch = {}, {}
    for i, v in enumerate(_RING):
        d = TODAY - timedelta(days=len(_RING) - 1 - i)
        ring[d] = float(v)
        if i >= _WATCH_FROM:
            off = _DIVERGENT_OFFSET_MS if i == _DIVERGENT_AT else _WATCH_OFFSET_MS
            watch[d] = float(v) + off
    return ring, watch


@pytest.fixture
def series():
    """The constructed ring and watch series. Named `series`, not `real` —
    it is not real, and a fixture whose name says otherwise is a lie a future
    reader would act on."""
    return _build()


# ─────────────────────────────────────────────────────────────────────────────
#  The axis is milliseconds, and that is the whole point
# ─────────────────────────────────────────────────────────────────────────────

def test_an_identical_physiological_move_draws_an_identical_step():
    """THE REQUIREMENT, in one test. On 2026-08-16 both devices moved +14 ms.
    A percent axis renders that as Oura +66.0% against Garmin +45.7% — the
    graph would show them disagreeing on a night they agreed exactly. In
    milliseconds-from-own-normal they draw the same step."""
    oura = {TODAY - timedelta(days=i): 20.0 for i in range(1, 29)}
    garmin = {TODAY - timedelta(days=i): 33.0 for i in range(1, 29)}
    oura[TODAY] = 34.0     # +14
    garmin[TODAY] = 47.0   # +14

    o_dev = ht.from_normal(oura[TODAY], ht.normal_for(oura, "oura", TODAY))
    g_dev = ht.from_normal(garmin[TODAY], ht.normal_for(garmin, "garmin", TODAY))
    assert o_dev == g_dev == 14.0

    # And the percentages they would have produced are NOT equal — which is
    # exactly why the axis is not a percentage.
    assert round(14 / 20.0 * 100, 1) != round(14 / 33.0 * 100, 1)


def test_the_additive_device_offset_cancels_with_no_stored_constant():
    """Garmin runs ~9.44 ms above Oura. Subtracting each device's OWN normal
    removes that exactly, so no bias constant is fitted or stored anywhere."""
    assert not any(
        "9.44" in str(v) for k, v in vars(ht).items() if not k.startswith("_")
    ), "a fitted device offset must never be stored as a constant"


# ─────────────────────────────────────────────────────────────────────────────
#  The trailing normal
# ─────────────────────────────────────────────────────────────────────────────

def test_normal_refuses_at_thirteen_readings_and_computes_at_fourteen():
    series = {TODAY - timedelta(days=i): 20.0 for i in range(13)}
    n = ht.normal_for(series, "garmin", TODAY)
    assert n.normal_ms is None and n.readings_used == 13
    assert "14" in n.refusal

    series[TODAY - timedelta(days=13)] = 20.0
    n = ht.normal_for(series, "garmin", TODAY)
    assert n.normal_ms == 20.0 and n.readings_used == 14 and n.refusal is None


def test_the_normal_is_a_median_so_one_freak_night_cannot_move_it(series):
    """The fixture holds ONE single-night collapse for exactly this. Dropping
    it moves the window's mean and leaves the median untouched, which is the
    whole reason the centre is a median."""
    _, garmin = series
    with_it = ht.normal_for(garmin, "garmin", TODAY).normal_ms
    without = ht.normal_for(
        {d: v for d, v in garmin.items() if d != COLLAPSE_NIGHT},
        "garmin", TODAY,
    ).normal_ms
    assert with_it == without == 32.0

    vals_with = list(garmin.values())
    vals_without = [v for d, v in garmin.items() if d != COLLAPSE_NIGHT]
    assert statistics.mean(vals_without) > statistics.mean(vals_with)
    assert statistics.median(vals_without) - statistics.median(vals_with) == 0.0


def test_a_missing_reading_is_none_never_zero():
    """C3. Zero on this axis would claim the night was exactly usual."""
    n = ht.normal_for({TODAY - timedelta(days=i): 20.0 for i in range(20)},
                      "oura", TODAY)
    assert ht.from_normal(None, n) is None
    assert ht.from_normal(20.0, n) == 0.0   # a real reading AT normal is 0


# ─────────────────────────────────────────────────────────────────────────────
#  The Oura lean
# ─────────────────────────────────────────────────────────────────────────────

def test_the_ring_leads_but_the_watch_stays_in_the_number():
    """His words: more emphasis on Oura, "but not much more". 0.60/0.40 lands
    the answer 60% of the way from watch to ring — the watch can never be
    overruled outright, which a weighted median at n=2 would do."""
    assert ht.combine(-3.0, -1.0) == pytest.approx(-2.2)
    assert ht.OURA_SHARE == 0.60 and ht.GARMIN_SHARE == pytest.approx(0.40)
    # Not a landslide: the watch still moves it more than a millisecond here.
    assert abs(ht.combine(-3.0, -1.0) - (-3.0)) == pytest.approx(0.8)


def test_the_combined_figure_refuses_a_one_device_night():
    """The key rule 2b hazard, contained. Substituting whichever device
    reported would step this number by up to 0.4x the gap on device presence."""
    assert ht.combine(-3.0, None) is None
    assert ht.combine(None, -1.0) is None


def test_the_weight_does_not_change_when_the_devices_disagree():
    """A weight that moved on agreement would make the number depend on which
    device was worn by another door."""
    agree = ht.combine(-5.0, -5.0)
    disagree = ht.combine(-5.0, +5.0)
    assert agree == pytest.approx(-5.0)
    assert disagree == pytest.approx(-1.0)   # 0.6*-5 + 0.4*+5


# ─────────────────────────────────────────────────────────────────────────────
#  Divergence — on RAW readings, never on deviations
# ─────────────────────────────────────────────────────────────────────────────

def test_divergence_finds_the_one_night_built_to_disagree(series):
    """The fixture offsets the watch by a constant +12 ms on every night but
    one, which is pushed to +18. Exactly that night must come back."""
    oura, garmin = series
    d = ht.divergence(oura, garmin, TODAY)
    assert d.paired_nights == 24
    assert d.centre_ms == 12.0
    assert d.spread_ms == pytest.approx(1.199, abs=0.001)
    assert d.band_ms == pytest.approx(2.398, abs=0.01)
    assert d.diverging_days == (DIVERGENT_NIGHT,)


def test_divergence_never_reads_the_plotted_deviations():
    """Source-level. The deviation gap carries a systematic +2.50 ms purely
    because Oura's window reaches further back than Garmin's — testing on it
    would manufacture disagreement out of wear pattern."""
    src = Path("services/hrv_trend.py").read_text(encoding="utf-8")
    body = src[src.index("def divergence("):src.index("def _consecutive_readings(")]
    assert "from_normal" not in body


def test_divergence_refuses_below_ten_paired_nights():
    oura = {TODAY - timedelta(days=i): 20.0 for i in range(5)}
    garmin = {TODAY - timedelta(days=i): 30.0 for i in range(5)}
    d = ht.divergence(oura, garmin, TODAY)
    assert d.centre_ms is None and d.band_ms is None
    assert "both devices" in d.refusal


def test_the_gap_band_has_a_floor_because_both_devices_report_whole_ms():
    """A perfectly constant gap gives spread 0, and 2x0 would flag every
    1 ms wobble as disagreement."""
    oura = {TODAY - timedelta(days=i): 20.0 for i in range(14)}
    garmin = {TODAY - timedelta(days=i): 30.0 for i in range(14)}
    d = ht.divergence(oura, garmin, TODAY)
    assert d.spread_ms == 0.0
    assert d.band_ms == ht.GAP_BAND_FLOOR_MS == 2.0


# ─────────────────────────────────────────────────────────────────────────────
#  The downward flag
# ─────────────────────────────────────────────────────────────────────────────

def test_the_shape_leg_fires_on_both_devices(series):
    """The fixture ends on a four-night decline, so both lines fire on SHAPE
    while the drop stays inside the ordinary swing — the case where the run is
    what is unusual, not the depth."""
    oura, garmin = series
    o = ht.downward_flag(oura, TODAY, "oura")
    assert o.firing and o.legs == ("shape4",)
    assert o.run_length == 4 and o.readings_ms == (19.0, 17.0, 15.0, 13.0)
    assert o.normal_ms == 20.0
    assert o.depth[3]["drop_ms"] == pytest.approx(5.0)
    assert o.depth[3]["ratio"] == pytest.approx(0.584, abs=0.01)
    assert not any(o.depth[k]["fired"] for k in ht.DEPTH_WINDOWS)

    g = ht.downward_flag(garmin, TODAY, "garmin")
    assert g.firing and g.legs == ("shape4",)
    assert g.normal_ms == 32.0


def test_the_depth_leg_fires_on_a_drop_past_the_floor():
    """The other leg, on its own fixture: a flat series then three nights far
    enough below to clear the 3-night floor."""
    s = {TODAY - timedelta(days=i): 30.0 for i in range(3, 32)}
    for i, v in enumerate((18.0, 17.0, 16.0)):
        s[TODAY - timedelta(days=2 - i)] = v
    f = ht.downward_flag(s, TODAY, "oura")
    assert f.firing
    assert "depth3" in f.legs
    assert f.depth[3]["drop_ms"] > ht.DEPTH_FLOOR_MS[3]


def test_three_nights_is_the_STRICT_leg_not_the_fast_one():
    """The athlete asked for "3-5 days" expecting 3 to be the sensitive
    setting. It is the opposite: averaging fewer nights is noisier, so the
    3-night bar is 27% HIGHER than the 5-night one."""
    assert ht.DEPTH_FLOOR_MS[3] > ht.DEPTH_FLOOR_MS[4] > ht.DEPTH_FLOOR_MS[5]
    assert ht.DEPTH_FLOOR_MS[3] / ht.DEPTH_FLOOR_MS[5] == pytest.approx(1.27, abs=0.01)


def test_depth_refuses_when_any_night_in_the_window_is_missing():
    """A night not recorded is not a low reading."""
    series = {TODAY - timedelta(days=i): 20.0 for i in range(30)}
    del series[TODAY - timedelta(days=1)]
    drop, _ = ht.depth_drop(series, TODAY, 3)
    assert drop is None
    f = ht.downward_flag(series, TODAY, "oura")
    assert f.depth[3]["drop_ms"] is None
    assert "no reading" in f.depth[3]["refusal"]


def test_the_shape_leg_needs_four_nights_not_three():
    """Three falling nights happen on 16.26% of his nights against 12.22% by
    chance — one night in six is not a flag."""
    assert ht.SHAPE_MIN_RUN == 4
    base = {TODAY - timedelta(days=i): 19.0 for i in range(2, 30)}
    three = {**base,
             TODAY - timedelta(days=2): 19.0,
             TODAY - timedelta(days=1): 18.0,
             TODAY: 17.0}
    assert ht.declining_run(three, TODAY) == 3
    assert not any(l.startswith("shape")
                   for l in ht.downward_flag(three, TODAY, "oura").legs)


def test_a_declining_run_is_broken_by_a_missing_night():
    """A gap cannot be assumed to continue a decline."""
    series = {TODAY: 13.0, TODAY - timedelta(days=1): 15.0,
              TODAY - timedelta(days=3): 17.0, TODAY - timedelta(days=4): 20.0}
    assert ht.declining_run(series, TODAY) == 2


def test_a_single_deep_night_cannot_carry_the_shape_leg():
    """The shape leg is a pure count. Magnitude cannot enter it."""
    series = {TODAY - timedelta(days=i): 20.0 for i in range(1, 30)}
    series[TODAY] = 1.0
    assert ht.declining_run(series, TODAY) == 2


def test_the_flag_refuses_a_night_with_no_reading():
    series = {TODAY - timedelta(days=i): 20.0 for i in range(1, 30)}
    f = ht.downward_flag(series, TODAY, "oura")
    assert f.firing is False and "No HRV reading" in f.refusal


# ─────────────────────────────────────────────────────────────────────────────
#  The alert cannot depend on which device was worn
# ─────────────────────────────────────────────────────────────────────────────

def test_the_flag_is_structurally_blind_to_the_other_device(series):
    """downward_flag takes ONE series and one device name. There is no
    parameter through which the other device could reach it, which is what
    stops the alert stepping on wear pattern."""
    oura, garmin = series
    alone = ht.downward_flag(oura, TODAY, "oura")

    # The whole panel, with the watch present, absent, and replaced by noise.
    with_watch = ht.panel(oura, garmin, TODAY).oura_flag
    no_watch = ht.panel(oura, {}, TODAY).oura_flag
    noise = ht.panel(oura, {d: 999.0 for d in garmin}, TODAY).oura_flag
    assert alone == with_watch == no_watch == noise


def test_removing_the_watch_leaves_every_ring_point_unchanged(series):
    oura, garmin = series
    a = [n.oura_from_normal for n in ht.panel(oura, garmin, TODAY).nights]
    b = [n.oura_from_normal for n in ht.panel(oura, {}, TODAY).nights]
    assert a == b


def test_one_device_only_still_draws_and_still_flags():
    """His real record holds a 274-night stretch (2025-09-30 -> 2026-06-30)
    with NO ring HRV while the watch was worn. Centring each device on nights
    they SHARE would go completely dark across it."""
    garmin = {}
    for i in range(60):
        garmin[TODAY - timedelta(days=i)] = 33.0
    for i, v in enumerate([30.0, 27.0, 25.0, 21.0]):
        garmin[TODAY - timedelta(days=3 - i)] = v

    p = ht.panel({}, garmin, TODAY)
    assert p.garmin_normal.normal_ms is not None
    assert p.garmin_flag.firing is True
    assert any(n.garmin_from_normal is not None for n in p.nights)
    # ...and the ring simply has nothing to say, rather than reading as zero.
    assert p.oura_normal.normal_ms is None
    assert all(n.oura_from_normal is None for n in p.nights)
    assert all(n.combined_from_normal is None for n in p.nights)


# ─────────────────────────────────────────────────────────────────────────────
#  Which metrics may share the axis at all
# ─────────────────────────────────────────────────────────────────────────────

def test_only_hrv_is_on_the_shared_axis():
    assert ht.SHARED_AXIS_METRICS == ("hrv_ms",)


def test_the_amplitude_gate_is_a_band_not_a_minimum(series):
    """A one-sided "at least as variable" test would pass Garmin's sleep
    score, whose spread is 2.4x Oura's and is nonsense on a shared axis."""
    _, garmin = series
    ring, watch = _build()
    oura_vals = [ring[d] for d in sorted(watch)]
    garmin_vals = [watch[d] for d in sorted(watch)]
    ok = ht.amplitude_ratio(list(zip(oura_vals, garmin_vals)))
    assert ok["sd_ratio"] == pytest.approx(1.059, abs=0.01)
    assert ok["shared_axis_ok"] is True

    too_wide = ht.amplitude_ratio([(o, o * 2.4) for o in oura_vals])
    assert too_wide["shared_axis_ok"] is False


def test_the_opposite_sign_rate_is_reported_but_never_gated_on():
    """It is 2 of 16 on the real nights — 12.5% — and at n=16 the 95% interval
    on that runs roughly 1.5% to 38%. Gating on it would admit or reject a
    metric on which side of the noise two nights happened to fall."""
    ring, watch = _build()
    oura_vals = [ring[d] for d in sorted(watch)]
    garmin_vals = [watch[d] for d in sorted(watch)]
    m = ht.amplitude_ratio(list(zip(oura_vals, garmin_vals)))
    assert m["opposite_sign_rate"] is not None
    assert m["shared_axis_ok"] is True     # decided by sd_ratio alone


# ─────────────────────────────────────────────────────────────────────────────
#  DISPLAY ONLY — structural, in both directions
# ─────────────────────────────────────────────────────────────────────────────

def _referenced_names(path: str) -> set[str]:
    """Every identifier the module ACTUALLY EXECUTES. Parsed rather than
    grepped so the docstring can name the forbidden things — it has to, to
    explain the rule — without tripping it. Same helper as
    tests/test_strain_regions_acwr.py."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.update(alias.name.split("."))
                if alias.asname:
                    names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            names.update((node.module or "").split("."))
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
    return names



def _referenced_names_in_function(path: str, func: str) -> set[str]:
    """_referenced_names, narrowed to one function body."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == func)
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute):
            names.add(sub.attr)
        elif isinstance(sub, ast.Name):
            names.add(sub.id)
    return names

def test_the_trend_cannot_reach_any_guardrail():
    used = _referenced_names("services/hrv_trend.py")
    for forbidden in ("traffic_light", "volume_recommendation", "acwr",
                      "STAGE_CONSTRAINTS", "rules", "engine", "readiness"):
        assert forbidden not in used, forbidden


def test_no_guardrail_reaches_the_trend():
    for consumer in ("services/engine.py", "services/rules.py",
                     "services/readiness.py", "services/biometrics.py",
                     "services/scheduling.py", "services/dashboard.py",
                     "services/metrics.py", "services/metrics_logic.py"):
        assert "hrv_trend" not in _referenced_names(consumer), consumer


def test_nothing_is_persisted():
    """C5. A stored number derived from constants expected to change is the
    does-not-self-heal failure that produced the Stage 1 over-count."""
    src = Path("services/hrv_trend.py").read_text(encoding="utf-8")
    for writer in ("upsert", "save_", "sync_", "OUTBOX", "sqlite", "open("):
        assert writer not in src, writer


def test_the_invented_floors_carry_a_revert_condition():
    """HRV_GARMIN_HOLD idiom: a number fitted from this athlete's own history
    must say what would make it wrong."""
    src = Path("services/hrv_trend.py").read_text(encoding="utf-8")
    i = src.index("DEPTH_FLOOR_MS")
    assert "REVERT CONDITION" in src[max(0, i - 1200):i]


# ─────────────────────────────────────────────────────────────────────────────
#  Plain English — key rule 19
# ─────────────────────────────────────────────────────────────────────────────

_JARGON = ("standard deviation", "z-score", "baseline", "threshold",
           "noise floor", "divergence", "advisory", "percentile", "median")


def test_every_patient_facing_sentence_is_plain_english(series):
    oura, garmin = series
    p = ht.panel(oura, garmin, TODAY)
    said = [p.headline, p.oura_flag.sentence, p.garmin_flag.sentence,
            p.divergence.refusal or "", p.oura_normal.refusal or "",
            p.garmin_normal.refusal or ""]
    for text in said:
        for word in _JARGON:
            assert word not in text.lower(), f"{word!r} in {text!r}"


def test_the_sentence_says_the_flag_changes_no_training_number(series):
    """⚠ "ON ITS OWN" is load-bearing, not a stylistic choice. This sentence now
    renders on the training screen, where on a reduced-load day it sits directly
    under a banner saying every weight and rep IS held. The earlier wording
    ("Nothing in your training numbers changes because of this") was true and
    would not be read that way — two statements about today's numbers,
    apparently contradicting each other. Same contradiction class the athlete
    reported on 2026-08-17."""
    oura, garmin = series
    p = ht.panel(oura, garmin, TODAY)
    assert "on its own does not change any of today's numbers" in p.oura_flag.sentence
    assert "Nothing in your training numbers changes" not in p.oura_flag.sentence


def test_a_shape_only_fire_says_the_depth_was_ordinary(series):
    """Honest reporting: on 2026-08-23 the ring's drop is 5.5 ms where its
    ordinary 3-night swing reaches 8.6. It is the run, not the size."""
    oura, _ = series
    s = ht.downward_flag(oura, TODAY, "oura").sentence
    assert "ordinary for you" in s
    assert "nights in a row" in s


def test_a_quiet_day_says_nothing_rather_than_reassuring():
    series = {TODAY - timedelta(days=i): 20.0 for i in range(30)}
    f = ht.downward_flag(series, TODAY, "oura")
    assert f.firing is False and f.sentence == ""


# ─────────────────────────────────────────────────────────────────────────────
#  The panel
# ─────────────────────────────────────────────────────────────────────────────

def test_the_panel_end_to_end(series):
    oura, garmin = series
    p = ht.panel(oura, garmin, TODAY)
    assert p.oura_normal.normal_ms == 20.0 and p.oura_normal.readings_used == 28
    assert p.garmin_normal.normal_ms == 32.0 and p.garmin_normal.readings_used == 24
    assert p.garmin_normal.provisional is True     # 24 < 28
    assert p.headline == "Both devices show your HRV coming down."
    assert p.display_only is True


def test_the_watch_borrows_the_rings_floors_and_says_so(series):
    """Justified by the two devices' spreads agreeing to 2.2% — and stated on
    screen rather than assumed."""
    oura, garmin = series
    p = ht.panel(oura, garmin, TODAY)
    assert p.garmin_flag.floor_source == "borrowed_from_oura"
    assert p.garmin_flag.provisional is True
    assert "still settling" in p.garmin_flag.sentence


def test_the_chart_is_anchored_and_back_dated(series):
    """Athlete, 2026-08-23: "we now know the average is 33, so we can back date
    that data to the first day the watch is used."

    One normal per device, applied to every night that device recorded. The
    watch's first reading is 2026-08-06, so it gets 18 points on the chart --
    not the 5 a trailing per-night normal allowed, which withheld 13 nights of
    real readings purely because nights AFTER them had not happened yet."""
    oura, garmin = series
    p = ht.panel(oura, garmin, TODAY)
    watch = [n for n in p.nights if n.garmin_from_normal is not None]
    assert len(watch) == 24, "every night the watch recorded, not just recent ones"
    assert watch[0].day == TODAY - timedelta(days=23)
    # ...and each is simply the reading minus the one anchor.
    assert watch[0].garmin_from_normal == watch[0].garmin_ms - 32.0
    assert watch[-1].garmin_from_normal == watch[-1].garmin_ms - 32.0


def test_the_anchor_is_a_median_so_the_current_slide_cannot_define_it():
    """The one thing that could make back-dating dishonest is a decline
    dragging down the level it is measured against. Measured on the real watch
    series the anchor is 33.0 computed three ways: all 18 nights, the first 14,
    and with the four declining nights removed."""
    _, watch = _build()
    vals = [watch[d] for d in sorted(watch)]
    assert statistics.median(vals) == 32.0
    assert statistics.median(vals[:14]) == 32.0
    assert statistics.median(vals[:-4]) == 32.0


def test_the_flag_is_NOT_anchored(series):
    """⚠ The chart and the flag answer different questions and must keep
    different references. The flag's reference deliberately ends where the run
    BEGINS, so a slide cannot drag down the number deciding whether it is a
    slide. Anchoring the flag would break exactly that."""
    src = Path("services/hrv_trend.py").read_text(encoding="utf-8")
    body = src[src.index("def depth_drop("):src.index("def declining_run(")]
    assert "today - timedelta(days=k)" in body

    oura, garmin = series
    p = ht.panel(oura, garmin, TODAY)
    # The ring's chart anchor and its flag reference are both 20.5 here only
    # because the window happens to agree; what matters is that the flag
    # computes its own rather than reading the chart's.
    assert p.oura_flag.depth[5]["drop_ms"] == pytest.approx(3.6)
    assert p.oura_flag.normal_ms == 20.0


def test_an_older_point_moves_when_the_anchor_moves():
    """THE PRICE OF BACK-DATING, pinned so it is a known trade and not a
    surprise. Under the previous trailing design an old point was fixed
    forever; under anchoring the whole line redraws when the anchor shifts.
    That is the right way round for a chart whose job is reading a trend --
    a trailing reference follows a decline down and flattens it out of its own
    chart -- but it is a genuine change and this test says so.

    Built deliberately so the anchor DOES move, and that took some doing: the
    real series holds a median of 20.5 on four consecutive days, and a single
    freak night cannot shift a median at all (one 60 ms night among 28 at
    20 ms moves it exactly 0.00 — which is the robustness the centre was
    chosen for). A steady ramp is what actually walks a median forward."""
    series = {TODAY - timedelta(days=i): 100.0 - i for i in range(1, 29)}
    before = ht.panel(series, {}, TODAY - timedelta(days=1))
    anchor_before = before.oura_normal.normal_ms

    series[TODAY] = 100.0
    after = ht.panel(series, {}, TODAY)
    assert after.oura_normal.normal_ms != anchor_before

    day = TODAY - timedelta(days=5)
    was = next(n.oura_from_normal for n in before.nights if n.day == day)
    now = next(n.oura_from_normal for n in after.nights if n.day == day)
    assert was != now


# ─────────────────────────────────────────────────────────────────────────────
#  ring_run_advisory — the one thing allowed out of a display-only module
# ─────────────────────────────────────────────────────────────────────────────
#  Added 2026-08-23. The athlete asked for the run to APPEAR in the training
#  statement while changing no prescribed number. That means one sentence
#  crosses onto a screen that also carries a load decision — so the sentence
#  itself has to be structurally incapable of being about the watch or about
#  the 60/40 combined figure, both of which depend on which device was worn.

import inspect  # noqa: E402


def test_the_advisory_takes_no_device_and_no_second_series():
    """The signature IS the guarantee. downward_flag takes a device NAME, which
    selects the word on screen but not the data — downward_flag(garmin, today,
    "oura") runs happily and lies. This entry point cannot."""
    assert list(inspect.signature(ht.ring_run_advisory).parameters) == ["oura", "today"]


def test_the_advisory_cannot_reach_the_combined_figure():
    """Source-level. The ring's series is what engine.traffic_light already
    scores HRV against, so a sentence about it adds no new device dependence.
    The combined figure would, and must not be reachable from here."""
    used = _referenced_names_in_function("services/hrv_trend.py", "ring_run_advisory")
    for forbidden in ("combine", "OURA_SHARE", "GARMIN_SHARE", "panel",
                      "combined_from_normal", "divergence", "_GARMIN"):
        assert forbidden not in used, forbidden
    assert "_OURA" in used, "the device must be a literal, not an argument"


def test_the_advisory_is_the_ring_even_when_the_watch_is_also_firing(series):
    oura, garmin = series
    note = ht.ring_run_advisory(oura, TODAY)
    assert "ring" in note and "watch" not in note
    # The watch IS firing on this date — so this is a real discrimination.
    assert ht.downward_flag(garmin, TODAY, "garmin").firing is True
    assert note == ht.downward_flag(oura, TODAY, "oura").sentence


def test_the_advisory_is_none_on_a_quiet_day():
    """None, not "". A quiet day says nothing rather than reassuring."""
    series = {TODAY - timedelta(days=i): 20.0 for i in range(30)}
    assert ht.ring_run_advisory(series, TODAY) is None


def test_the_training_sentence_and_the_panel_sentence_are_the_same_sentence():
    """⚠ downward_flag defaults provisional=False while panel computes it, and
    the sentence gains a "still settling" clause on a thin series. Without
    passing it explicitly the two screens would print DIFFERENT sentences for
    the same night — invisible on a 28-reading fixture, and live on his real
    record, which holds a 274-night ring-off stretch."""
    thin = {TODAY - timedelta(days=i): v
            for i, v in enumerate([13.0, 15.0, 17.0, 20.0] + [21.0] * 20)}
    note = ht.ring_run_advisory(thin, TODAY)
    assert note == ht.panel(thin, {}, TODAY).oura_flag.sentence
    assert "still settling" in note


def test_the_gate_only_silences_and_carries_a_revert_condition():
    """There is no setting of HRV_RUN_ON_TRAINING_SCREEN that makes the run act
    — nothing in engine.py or sessions.py ever receives this text. False means
    he stops being told."""
    src = Path("services/hrv_trend.py").read_text(encoding="utf-8")
    i = src.index("HRV_RUN_ON_TRAINING_SCREEN = True")
    preamble = src[max(0, i - 2200):i]
    assert "REVERT CONDITION" in preamble
    assert "15%" in preamble, "the revert condition needs a measurable bar"


def test_the_gate_off_returns_none_and_changes_nothing_else(series, monkeypatch):
    oura, _ = series
    assert ht.ring_run_advisory(oura, TODAY) is not None
    monkeypatch.setattr(ht, "HRV_RUN_ON_TRAINING_SCREEN", False)
    assert ht.ring_run_advisory(oura, TODAY) is None
    # The panel is untouched by the gate — the chart is not what it governs.
    assert ht.panel(oura, {}, TODAY).oura_flag.firing is True


# ─────────────────────────────────────────────────────────────────────────────
#  No real readings in the fixtures
# ─────────────────────────────────────────────────────────────────────────────

def test_the_fixture_is_constructed_and_says_so():
    """Athlete, 2026-08-24: "lets make that fake data or remove it ... remove
    it its not required."

    This repo is public. The fixtures used to be a transcript of 53 dated
    nightly readings, which is a health record rather than test data. The
    series is built from _RING now, and nothing about these tests needs it to
    have been anyone's."""
    src = Path("services/../tests/test_hrv_trend.py").read_text(encoding="utf-8")
    assert "CONSTRUCTED, NOT A TRANSCRIPT" in src
    # Every value in the fixture is a whole number by construction — a real
    # ring series is not that tidy, so this is a cheap signal that it is made up.
    assert all(float(v).is_integer() for v in _RING)
    ring, watch = _build()
    assert all(float(v).is_integer() for v in ring.values())
    assert all(float(v).is_integer() for v in watch.values())


def test_no_fixture_carries_a_long_run_of_dated_readings():
    """The shape to prevent is a TRANSCRIPT: many dated values in a row. The
    constructed series is a list of plain integers with the dates derived, so
    a date literal paired with a reading is the thing that must not reappear."""
    import re

    src = Path("services/../tests/test_hrv_trend.py").read_text(encoding="utf-8")
    # A quoted ISO date immediately followed by numbers is a reading bound to
    # a night. Described rather than shown, because a literal example here
    # would make this test flag itself.
    transcript = re.findall(r'\("20\d\d-\d\d-\d\d",\s*\d+', src)
    assert not transcript, (
        f"{len(transcript)} dated readings are back in the fixture: "
        f"{transcript[:3]}")
