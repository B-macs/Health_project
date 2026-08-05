"""
Tests for services/flexibility.py — the Range x Control score, its two-sided
band, and the refusals that keep it honest.

Expected values below are hand-computed from flexibility_baselines.py, not
copied out of the implementation.
"""

import ast
from datetime import date

import pytest

import flexibility_baselines as fb
from services import flexibility as fx

TODAY = date(2026, 8, 5)          # same day as the depth ratings
SCAN_AGE_DAYS = 565               # 2025-01-17 -> 2026-08-05


# ── the two-sided band, which is the whole design ────────────────────────────

def test_band_scores_100_anywhere_inside_and_penalises_both_sides():
    lo, hi = fx.CONTROL_BAND
    for v in (lo, (lo + hi) / 2, hi):
        score, direction = fx.band_score(v, lo, hi, 2.0, 3.0)
        assert score == 100.0
        assert direction == fx.DIRECTION_IDEAL

    below, d_below = fx.band_score(lo - 10, lo, hi, 2.0, 3.0)
    above, d_above = fx.band_score(hi + 10, lo, hi, 2.0, 3.0)
    assert below < 100.0 and d_below == fx.DIRECTION_RESTRICTED
    assert above < 100.0 and d_above == fx.DIRECTION_UNSTABLE


def test_depth_rating_100_is_not_a_score_of_100():
    """The single most important property in this module. On the athlete's own
    depth scale 100 means 'at the physical limit, no sensation left'. On the
    control score 100 means IDEAL. Conflating them would make the six poses he
    rated 80-88 his best results, when the profile names them as the hazard."""
    score, direction = fx.control_score(100)
    assert score < 50.0
    assert direction == fx.DIRECTION_UNSTABLE


@pytest.mark.parametrize("rating,expected,direction", [
    (25, 25.0,  fx.DIRECTION_RESTRICTED),   # (25/50)^2  — the straddle fold
    (40, 64.0,  fx.DIRECTION_RESTRICTED),
    (46, 84.64, fx.DIRECTION_RESTRICTED),
    (50, 100.0, fx.DIRECTION_IDEAL),        # floor of the band
    (64, 100.0, fx.DIRECTION_IDEAL),
    (70, 100.0, fx.DIRECTION_IDEAL),        # ceiling of the band
    (76, 82.0,  fx.DIRECTION_UNSTABLE),     # 100 - 3*6
    (85, 55.0,  fx.DIRECTION_UNSTABLE),
    (88, 46.0,  fx.DIRECTION_UNSTABLE),     # the lying twists
])
def test_control_score_reference_values(rating, expected, direction):
    score, got_direction = fx.control_score(rating)
    assert score == pytest.approx(expected, abs=0.01)
    assert got_direction == direction


def test_band_score_is_clamped_and_rejects_a_nonsense_band():
    score, _ = fx.band_score(500, 50, 70, 2.0, 3.0)
    assert score == 0.0                      # linear falloff cannot go negative
    with pytest.raises(ValueError):
        fx.band_score(10, 70, 50, 2.0, 3.0)  # hi < lo
    with pytest.raises(ValueError):
        fx.band_score(10, 0, 50, 2.0, 3.0)   # lo == 0 would divide by zero


# ── score-then-average, the error this module is built to avoid ──────────────

def test_scores_each_pose_before_averaging_not_after():
    """Hamstrings sees straddle 25, Walk the Dog 76, Down Dog 64 at weights
    0.5/0.6/0.3. Averaging the RATINGS gives ~55, which lands inside the ideal
    band and would score 100, erasing the 25 — the most informative reading in
    the assessment. Scoring first gives ~65.5."""
    axis = fx.control_axis("hamstrings", fb.POSE_DEPTH_RATING_2026_08_05,
                           fb.DEPTH_RATING_DATE, TODAY)
    expected = (0.6 * 82.0 + 0.3 * 100.0 + 0.5 * 25.0) / 1.4
    assert axis.score == pytest.approx(expected, abs=0.01)
    assert axis.score == pytest.approx(65.5, abs=0.1)
    assert axis.score < 100.0


def test_direction_is_attributed_from_lost_points_not_from_the_mean_rating():
    """Same region, and the reason the direction cannot come from a rating mean:
    the weighted mean rating is ~55, inside the ideal band, so a rating-mean
    would label a 65-scoring region 'ideal'."""
    ratings = fb.POSE_DEPTH_RATING_2026_08_05
    mean_rating = (0.6 * 76 + 0.3 * 64 + 0.5 * 25) / 1.4
    lo, hi = fx.CONTROL_BAND
    assert lo <= mean_rating <= hi, "precondition: the rating mean looks ideal"

    axis = fx.control_axis("hamstrings", ratings, fb.DEPTH_RATING_DATE, TODAY)
    assert axis.direction == fx.DIRECTION_RESTRICTED


def test_back_reads_unstable_because_its_deficit_is_end_range_twists():
    axis = fx.control_axis("back", fb.POSE_DEPTH_RATING_2026_08_05,
                           fb.DEPTH_RATING_DATE, TODAY)
    assert axis.direction == fx.DIRECTION_UNSTABLE


# ── the geometric mean ───────────────────────────────────────────────────────

def test_region_uses_geometric_mean_so_one_axis_cannot_carry_the_other():
    region = fx.score_region("hamstrings", fb.POSE_DEPTH_RATING_2026_08_05,
                             fb.DEPTH_RATING_DATE, TODAY)
    r, c = region.range_axis.score, region.control_axis.score
    assert region.score == pytest.approx((r * c) ** 0.5, abs=0.01)
    # The arithmetic mean would be materially kinder — that difference is the
    # design, not rounding.
    assert region.score < (r + c) / 2 - 1.0


def test_a_zero_on_either_axis_annihilates_the_region():
    ratings = dict.fromkeys(fb.POSE_DEPTH_RATING_2026_08_05, 1)
    region = fx.score_region("hamstrings", ratings, fb.DEPTH_RATING_DATE, TODAY)
    assert region.control_axis.score < 1.0
    assert region.score < 10.0


# ── staleness ────────────────────────────────────────────────────────────────

def test_staleness_halves_confidence_every_halflife():
    assert fx.staleness_confidence(TODAY, TODAY) == 1.0
    half = date.fromordinal(TODAY.toordinal() - int(fx.CONFIDENCE_HALFLIFE_DAYS))
    assert fx.staleness_confidence(half, TODAY) == pytest.approx(0.5, abs=0.01)


def test_a_future_measurement_cannot_manufacture_extra_confidence():
    future = date.fromordinal(TODAY.toordinal() + 400)
    assert fx.staleness_confidence(future, TODAY) == 1.0


def test_staleness_moves_confidence_and_never_the_score():
    """Decaying a stale VALUE would invent a decline that was never measured —
    the error services/strength.py's asymmetry rule exists to prevent."""
    fresh = fx.score_region("hamstrings", fb.POSE_DEPTH_RATING_2026_08_05,
                            fb.DEPTH_RATING_DATE, TODAY)
    later = date.fromordinal(TODAY.toordinal() + 3 * 365)
    stale = fx.score_region("hamstrings", fb.POSE_DEPTH_RATING_2026_08_05,
                            fb.DEPTH_RATING_DATE, later)
    assert stale.range_axis.score == fresh.range_axis.score
    assert stale.confidence < fresh.confidence


def test_the_provisional_protocol_penalty_applies_and_is_self_removing():
    axis = fx.range_axis(fb.REGION_BASELINES["hamstrings"], TODAY)
    expected = 0.5 ** (SCAN_AGE_DAYS / fx.CONFIDENCE_HALFLIFE_DAYS) * fx.PROVISIONAL_PROTOCOL_PENALTY
    assert axis.provisional is True
    assert axis.confidence == pytest.approx(expected, abs=0.001)

    # Setting the protocol removes the penalty with no other edit — which is
    # what should happen the day the gym supplies the movement list.
    from dataclasses import replace
    confirmed = replace(fb.REGION_BASELINES["hamstrings"],
                        protocol="passive straight-leg raise", provisional=False)
    assert fx.range_axis(confirmed, TODAY).confidence == pytest.approx(
        expected / fx.PROVISIONAL_PROTOCOL_PENALTY, abs=0.001)


# ── uncovered and unscoreable regions are reported, never imputed ────────────

def test_lat_flex_range_is_unscoreable_and_stays_that_way():
    """The vendor calls 20-21 deg 'Normal', which contradicts the obvious
    reading of the label. A band guessed out of a contradiction is worse than
    no band, so the Range axis is absent and the region scores on Control."""
    assert fb.REGION_BASELINES["lat_flex"].reference_band is None
    region = fx.score_region("lat_flex", fb.POSE_DEPTH_RATING_2026_08_05,
                             fb.DEPTH_RATING_DATE, TODAY)
    assert region.range_axis is None
    assert region.control_axis is not None
    assert region.score == pytest.approx(region.control_axis.score, abs=0.01)


def test_squat_depth_is_uncovered_on_both_axes_and_excluded_not_imputed():
    region = fx.score_region("squat_depth", fb.POSE_DEPTH_RATING_2026_08_05,
                             fb.DEPTH_RATING_DATE, TODAY)
    assert region.score is None
    assert region.confidence == 0.0
    assert region.unscoreable_reason

    result = fx.overall_score(today=TODAY)
    assert "squat_depth" in result.uncovered_regions


def test_neck_control_is_withheld_below_the_evidence_floor():
    """Only one pose touches the neck, at weight 0.1. A score built on that
    would look like evidence and not be one."""
    total = sum(w.get("neck", 0.0) for w in fb.POSE_REGION_WEIGHT.values())
    assert total < fx.MIN_CONTROL_EVIDENCE
    assert fx.control_axis("neck", fb.POSE_DEPTH_RATING_2026_08_05,
                           fb.DEPTH_RATING_DATE, TODAY) is None


def test_unmapped_poses_are_surfaced_rather_than_silently_dropped():
    """Same failure mode as training_constants.EXERCISE_BODY_REGION: a pose
    missing from the map is excluded from every region total."""
    ratings = dict(fb.POSE_DEPTH_RATING_2026_08_05)
    ratings["Some Brand New Pose"] = 55
    result = fx.overall_score(ratings=ratings, ratings_date=fb.DEPTH_RATING_DATE, today=TODAY)
    assert "Some Brand New Pose" in result.unmapped_poses
    # Savasana is deliberately unmapped and must NOT be reported as an oversight.
    assert "Deep Relaxation (Savasana)" not in result.unmapped_poses


# ── the overall ──────────────────────────────────────────────────────────────

def test_overall_on_the_real_data():
    result = fx.overall_score(today=TODAY)
    assert result.overall == pytest.approx(80.5, abs=0.5)
    assert result.coverage == pytest.approx(0.44, abs=0.02)


def test_adding_either_instrument_moves_the_overall():
    """The athlete's stated requirement. A Control-only region gaining a Range
    reading changes the score (single axis -> geometric mean) AND the confidence
    (0.5 -> higher), so numerator and denominator move together."""
    from dataclasses import replace
    before = fx.overall_score(today=TODAY).overall

    original = fb.REGION_BASELINES["back"]
    try:
        fb.REGION_BASELINES["back"] = replace(
            original, left_deg=40.0, right_deg=40.0,
            reference_band=(50.0, 60.0), assumed_protocol="lumbar flexion",
        )
        after = fx.overall_score(today=TODAY).overall
    finally:
        fb.REGION_BASELINES["back"] = original

    assert after != pytest.approx(before, abs=0.01)


def test_region_weights_sum_to_one_and_cover_every_baseline():
    assert sum(fb.REGION_WEIGHT.values()) == pytest.approx(1.0, abs=1e-9)
    assert set(fb.REGION_WEIGHT) == set(fb.REGION_BASELINES)


def test_pose_region_weights_sum_to_one_per_pose():
    for pose, weights in fb.POSE_REGION_WEIGHT.items():
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9), pose
        assert set(weights) <= set(fb.REGION_WEIGHT), pose


def test_every_yoga_pose_is_either_mapped_or_explicitly_excluded():
    from services import yoga
    for pose in yoga.YOGA_LIBRARY[0].poses:
        assert pose.name in fb.POSE_REGION_WEIGHT or pose.name in fb.UNMAPPED_POSES, pose.name
    # ...and the depth-rating table must cover the flow exactly.
    assert set(fb.POSE_DEPTH_RATING_2026_08_05) == {
        p.name for p in yoga.YOGA_LIBRARY[0].poses
    }


def test_region_direction_is_taken_from_the_worse_axis():
    region = fx.score_region("hamstrings", fb.POSE_DEPTH_RATING_2026_08_05,
                             fb.DEPTH_RATING_DATE, TODAY)
    assert region.range_axis.score > region.control_axis.score
    assert region.direction == region.control_axis.direction


# ── refusals ─────────────────────────────────────────────────────────────────

def test_no_flexibility_age_in_years_is_ever_produced():
    """Same refusal as services/body_composition.py's. The vendor ships one and
    it is contaminated: 28 was measured when the athlete was 30, and it is
    displayed against a live age of 31, so the gap widens every birthday
    without anybody moving."""
    source = open(fx.__file__, encoding="utf-8").read()
    tree = ast.parse(source)
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for banned in ("flexibility_age", "bio_age", "bioage", "age_years", "flexibility_bioage"):
        assert not any(banned in n.lower() for n in names), banned

    result = fx.overall_score(today=TODAY)
    assert not hasattr(result, "age_years")
    assert 0.0 <= result.overall <= 100.0

    # The vendor's own numbers are kept for provenance, and the defect with them.
    assert fb.AGE_AT_SCAN_YEARS == 30
    assert fb.VENDOR_BIOAGE_COMPARED_AGAINST_AGE == 31


def test_vendor_verdicts_are_kept_verbatim_but_never_scored():
    """Converting Low/Normal into a score would import the vendor's undisclosed
    norm table into ours and double-count it against our own band."""
    assert fb.REGION_BASELINES["hamstrings"].vendor_verdict == "Normal"
    assert fb.REGION_BASELINES["hip"].vendor_verdict == "Low"

    source = open(fx.__file__, encoding="utf-8").read()
    body = source.split('"""', 2)[-1]          # drop the module docstring
    assert "vendor_verdict" not in body, "the score must not read the vendor's verdict"


def test_symmetry_suspects_are_flagged_not_silently_averaged():
    """Neck 30/30 and Chest 106/106 are exactly equal while the other three
    differ by 1-3 deg. Post-Latarjet, exact bilateral equality at the chest is
    the least likely reading on the sheet."""
    assert fb.REGION_BASELINES["chest"].symmetry_suspect is True
    assert fb.REGION_BASELINES["neck"].symmetry_suspect is True
    assert fb.REGION_BASELINES["hip"].symmetry_suspect is False
    assert fb.REGION_BASELINES["chest"].asymmetry_deg == 0.0
    assert fb.REGION_BASELINES["hamstrings"].asymmetry_deg == 3.0


def test_every_provisional_region_names_the_protocol_it_assumed():
    for key, base in fb.REGION_BASELINES.items():
        if base.provisional and base.reference_band is not None:
            assert base.assumed_protocol, key
        assert base.protocol is None, (
            f"{key}: protocol is now recorded — confirm the reference band and "
            "clear `provisional`, then update this test"
        )


def test_no_streamlit_import():
    tree = ast.parse(open(fx.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
