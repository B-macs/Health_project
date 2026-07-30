"""Tests for services/hr_load.py — Edwards' TRIMP and HR-derived strain."""

import math

import pytest

from services import engine, hr_load


HR_MAX = 190.0


# ─── zones ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hr,expected", [
    (60, None),    # below Z1's 50% floor -> no load
    (94, None),    # 49.5%
    (95, 1),       # exactly 50% -> Z1 (boundaries belong to the HIGHER zone)
    (113, 1),      # 59.5%
    (114, 2),      # exactly 60%
    (132, 2),      # 69.5%
    (133, 3),      # exactly 70%
    (151, 3),      # 79.5%
    (152, 4),      # exactly 80%
    (170, 4),      # 89.5%
    (171, 5),      # exactly 90%
    (190, 5),      # at HRmax
])
def test_zone_for_hr_boundaries(hr, expected):
    assert hr_load.zone_for_hr(hr, HR_MAX) == expected


def test_zone_for_hr_rejects_implausible_readings():
    # Strap dropouts emit 0; contact glitches emit spikes.
    assert hr_load.zone_for_hr(0, HR_MAX) is None
    assert hr_load.zone_for_hr(250, HR_MAX) is None


def test_zone_for_hr_handles_zero_hr_max():
    assert hr_load.zone_for_hr(150, 0) is None


# ─── seconds in zone from a sample series ───────────────────────────────────

def test_seconds_in_zone_buckets_by_time_to_next_sample():
    # 1s apart: 3 samples in Z3, then 2 in Z5.
    samples = [(0, 140), (1, 140), (2, 140), (3, 180), (4, 180)]
    z = hr_load.seconds_in_zone_from_samples(samples, HR_MAX)
    assert z[3] == pytest.approx(3.0)   # 2 gaps + the median-interval tail...
    assert z[5] == pytest.approx(2.0)


def test_seconds_in_zone_clamps_recording_dropouts():
    # A 4-minute gap must not credit 4 minutes at the pre-dropout intensity.
    samples = [(0, 180), (240, 180)]
    z = hr_load.seconds_in_zone_from_samples(samples, HR_MAX)
    assert z[5] <= 2 * hr_load.MAX_SAMPLE_GAP_SECONDS


def test_seconds_in_zone_ignores_sub_threshold_time():
    samples = [(0, 60), (1, 60), (2, 60)]
    assert hr_load.seconds_in_zone_from_samples(samples, HR_MAX) == {}


def test_seconds_in_zone_sorts_unordered_input():
    ordered = hr_load.seconds_in_zone_from_samples([(0, 140), (1, 140), (2, 140)], HR_MAX)
    shuffled = hr_load.seconds_in_zone_from_samples([(2, 140), (0, 140), (1, 140)], HR_MAX)
    assert ordered == shuffled


def test_seconds_in_zone_empty_inputs():
    assert hr_load.seconds_in_zone_from_samples([], HR_MAX) == {}
    assert hr_load.seconds_in_zone_from_samples([(0, 150)], 0) == {}


# ─── Garmin's own pre-bucketed zones ────────────────────────────────────────

def test_seconds_in_zone_from_garmin_zones_sums_rows():
    rows = [{"zoneNumber": 1, "secsInZone": 300.0}, {"zoneNumber": 3, "secsInZone": 600.0}]
    assert hr_load.seconds_in_zone_from_garmin_zones(rows) == {1: 300.0, 3: 600.0}


def test_seconds_in_zone_from_garmin_zones_tolerates_garmin_key_typo():
    # Garmin's payload has shipped "zoneNumer" in the wild.
    rows = [{"zoneNumer": 2, "secsInZones": 120.0}]
    assert hr_load.seconds_in_zone_from_garmin_zones(rows) == {2: 120.0}


def test_seconds_in_zone_from_garmin_zones_skips_junk():
    rows = [{"zoneNumber": 9, "secsInZone": 60}, {"zoneNumber": 2, "secsInZone": "x"},
            {"zoneNumber": 1, "secsInZone": 0}, None or {}]
    assert hr_load.seconds_in_zone_from_garmin_zones(rows) == {}


# ─── Edwards' load ──────────────────────────────────────────────────────────

def test_edwards_load_is_weighted_minutes():
    # 10 min in Z1 (x1) + 10 min in Z5 (x5) = 10 + 50
    assert hr_load.edwards_load({1: 600.0, 5: 600.0}) == 60.0


def test_edwards_load_ceiling_is_five_times_minutes():
    # 60 minutes entirely in zone 5 -> the practical single-session maximum.
    assert hr_load.edwards_load({5: 3600.0}) == 300.0


def test_edwards_load_weights_high_zones_proportionally_more():
    """The property the whole method was chosen for: the same total time
    shifted into higher zones must produce a higher load."""
    easy = hr_load.edwards_load({1: 1800.0, 2: 1800.0})
    hard = hr_load.edwards_load({4: 1800.0, 5: 1800.0})
    assert hard > easy
    assert hard / easy == pytest.approx(3.0)  # (4+5)/(1+2)


def test_edwards_load_empty_is_zero():
    assert hr_load.edwards_load({}) == 0.0
    assert hr_load.edwards_load(None) == 0.0


def test_edwards_load_ignores_unknown_zone_numbers():
    assert hr_load.edwards_load({0: 600.0, 6: 600.0, 3: 600.0}) == 30.0


# ─── Banister TRIMP (cross-check figure) ────────────────────────────────────

def test_banister_trimp_matches_published_formula():
    # HRR fraction = (150-50)/(190-50) = 0.7142857
    frac = (150 - 50) / (190 - 50)
    expected = round(60 * frac * 0.64 * math.exp(1.92 * frac), 1)
    assert hr_load.banister_trimp(150, 50, 190, 60) == expected


def test_banister_trimp_female_coefficients_differ():
    male = hr_load.banister_trimp(150, 50, 190, 60, male=True)
    female = hr_load.banister_trimp(150, 50, 190, 60, male=False)
    assert male != female


def test_banister_trimp_none_when_inputs_missing():
    assert hr_load.banister_trimp(None, 50, 190, 60) is None
    assert hr_load.banister_trimp(150, None, 190, 60) is None
    assert hr_load.banister_trimp(150, 50, None, 60) is None
    assert hr_load.banister_trimp(150, 50, 190, 0) is None


def test_banister_trimp_degenerate_reserve_is_none():
    assert hr_load.banister_trimp(150, 190, 190, 60) is None


def test_banister_trimp_at_or_below_rest_is_zero():
    assert hr_load.banister_trimp(45, 50, 190, 60) == 0.0


def test_banister_cannot_distinguish_distributions_that_edwards_can():
    """Documents WHY Edwards' is primary. Two 60-minute sessions with the
    SAME mean HR (145) score identically under Banister, which sees only the
    mean — but differently under Edwards', which sees the distribution.

        steady   : 60 min @145      -> all Z3          -> 60*3       = 180
        skewed   : 45 min @130 (Z2) + 15 min @190 (Z5) -> 45*2+15*5  = 165
                   mean = (45*130 + 15*190)/60 = 145
    """
    assert (45 * 130 + 15 * 190) / 60 == 145  # the two really do share a mean
    assert hr_load.banister_trimp(145, 50, 190, 60) == hr_load.banister_trimp(145, 50, 190, 60)

    steady = hr_load.edwards_load({3: 3600.0})
    skewed = hr_load.edwards_load({2: 45 * 60.0, 5: 15 * 60.0})
    assert steady != skewed


def test_edwards_linear_weights_coincide_on_symmetric_distributions():
    """The method's honest limit, asserted so it isn't mistaken for a bug:
    Edwards' weights are LINEAR in zone number, so time split symmetrically
    about a zone scores the same as that zone throughout. Z1+Z5 averages to
    Z3. Lucia's/Stagno's non-linear weights are what address this, and both
    need lab-derived thresholds this athlete doesn't have (see the module
    docstring)."""
    assert hr_load.edwards_load({1: 1800.0, 5: 1800.0}) == hr_load.edwards_load({3: 3600.0})


# ─── strain conversion + calibration against the RPE scale ──────────────────

def test_hr_strain_uses_the_shared_curve_without_stage_clf():
    load = 142.0
    assert hr_load.hr_strain(load) == engine.load_to_strain(load)
    # Emphatically NOT the CLF-scaled path used for Foster AU.
    assert hr_load.hr_strain(load) != engine.au_to_strain(load, stage=1)


def test_hr_strain_zero_and_negative():
    assert hr_load.hr_strain(0) == 0.0
    assert hr_load.hr_strain(-5) == 0.0


def test_hr_strain_is_monotonic_and_capped():
    values = [hr_load.hr_strain(x) for x in (10, 50, 100, 200, 300, 5000)]
    assert values == sorted(values)
    assert max(values) <= 21.0


@pytest.mark.parametrize("rpe,minutes,edwards", [
    (3, 30, 30),    # light rehab
    (5, 45, 95),    # moderate gym
    (6, 60, 142),   # hard gym
    (8, 75, 210),   # very hard
])
def test_hr_and_rpe_scales_stay_continuous(rpe, minutes, edwards):
    """The fallback requirement: when a session has no Garmin activity the
    displayed strain drops to the RPE value, and that must not read as a
    visible jump. Both scales agree within 1 point across the realistic
    Stage-2 range."""
    rpe_strain = engine.au_to_strain(rpe * minutes, stage=2)
    assert abs(hr_load.hr_strain(edwards) - rpe_strain) < 1.0


# ─── blending / fallback chain ──────────────────────────────────────────────

def test_blend_weights_hr_more_heavily():
    value, source = hr_load.blend_strain(18.0, 8.0)
    assert source == hr_load.SOURCE_BLENDED
    assert value == round(18.0 * 0.7 + 8.0 * 0.3, 1)
    assert value > 13.0  # pulled toward the HR signal, not the midpoint


def test_blend_hr_only():
    assert hr_load.blend_strain(15.0, None) == (15.0, hr_load.SOURCE_HR)


def test_blend_rpe_only_is_the_documented_fallback():
    assert hr_load.blend_strain(None, 12.4) == (12.4, hr_load.SOURCE_RPE)


def test_blend_neither():
    assert hr_load.blend_strain(None, None) == (None, hr_load.SOURCE_NONE)


def test_blend_rpe_fallback_is_bit_identical_to_pre_existing_strain():
    """The safety property: with no Garmin activity the number must be
    exactly what au_to_strain would have produced on its own."""
    legacy = engine.au_to_strain(6 * 60, stage=2)
    assert hr_load.blend_strain(None, legacy)[0] == legacy


def test_blend_weight_is_clamped():
    assert hr_load.blend_strain(20.0, 10.0, hr_weight=5.0)[0] == 20.0
    assert hr_load.blend_strain(20.0, 10.0, hr_weight=-1.0)[0] == 10.0


def test_every_source_has_a_display_label():
    for src in (hr_load.SOURCE_HR, hr_load.SOURCE_BLENDED,
                hr_load.SOURCE_RPE, hr_load.SOURCE_NONE):
        assert hr_load.SOURCE_LABELS[src]


# ─── HRmax estimation ───────────────────────────────────────────────────────

def test_estimate_hr_max_takes_highest_plausible():
    assert hr_load.estimate_hr_max([165, 182, 171, None]) == 182.0


def test_estimate_hr_max_rejects_implausible_values():
    # 0 from a dropped strap, 250 from a contact glitch, 90 too low to be a max.
    assert hr_load.estimate_hr_max([0, 250, 90, 178]) == 178.0


def test_estimate_hr_max_none_when_nothing_usable():
    assert hr_load.estimate_hr_max([]) is None
    assert hr_load.estimate_hr_max([None, 0, 300]) is None


# ─── the assembled per-session summary ──────────────────────────────────────

def test_session_hr_summary_shape_and_values():
    out = hr_load.session_hr_summary(
        {1: 600.0, 3: 900.0, 5: 300.0},
        avg_hr=142, max_hr=178, hr_rest=52, hr_max=HR_MAX, duration_minutes=30,
    )
    assert out["edwards_load"] == pytest.approx(10 * 1 + 15 * 3 + 5 * 5)
    assert out["hr_strain"] == hr_load.hr_strain(out["edwards_load"])
    assert out["banister_trimp"] is not None
    assert out["zone_minutes"] == {1: 10.0, 3: 15.0, 5: 5.0}
    assert out["total_minutes"] == 30.0
    assert out["hr_max_used"] == HR_MAX


def test_session_hr_summary_survives_empty_zones():
    out = hr_load.session_hr_summary({})
    assert out["edwards_load"] == 0.0
    assert out["hr_strain"] == 0.0
    assert out["banister_trimp"] is None
    assert out["zone_minutes"] == {}
