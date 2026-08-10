"""services/strain_regions.py — the split, and the things it must refuse.

Read services/strain_regions.py's docstring before changing anything here. The
two tests most likely to look like bugs are deliberate:

  * test_regional_strains_do_not_sum_to_the_overall asserts NON-additivity as
    a POSITIVE property. It is the log curve, not a defect. If it ever fails
    because someone made them sum, revert THAT, not this.
  * test_a_fully_unmapped_session_has_no_regions_rather_than_zeros pins
    None-not-zero, the flexibility ladder's rule that an unmeasured muscle has
    no number.
"""

from datetime import date

import pytest

import training_constants as tc
from services import content_weighting, engine, strain_regions as sr
from services import strength as strength_svc
from services import tonnage as tonnage_svc

REGIONS = sr.REGIONS


def _mass(items):
    return sr.session_region_mass([{"name": n, "seconds": s} for n, s in items])


# ─── the vocabulary is shared, not re-invented ───────────────────────────────

def test_regions_tuple_matches_tonnage_and_strength():
    assert sr.REGIONS == tonnage_svc.REGIONS == strength_svc.REGIONS


# ─── the split is exact ──────────────────────────────────────────────────────

def test_region_au_sums_exactly_to_the_session_au():
    for au in (100.0, 204.6, 300.0, 333.3, 1.0, 0.1):
        mass = _mass([("Goblet Squat", 600), ("Lat Pulldown", 400), ("Dead Bug", 300)])
        parts = sr.split_session_au(au, mass)
        assert sum(parts.values()) == pytest.approx(round(au, 1), abs=1e-9), au


def test_the_split_survives_a_pathological_three_way_share():
    """0.333/0.333/0.334-style shares are exactly where naive rounding breaks
    an identity — the case services.strength.split_parts exists for."""
    mass = _mass([("Child's Pose", 600)])
    parts = sr.split_session_au(100.0, mass)
    assert sum(parts.values()) == pytest.approx(100.0, abs=1e-9)


def test_daily_region_au_totals_match_the_weighted_au():
    sessions = [
        {"date": "2026-07-20", "au": 200.0,
         "exercise_seconds": [{"name": "Goblet Squat", "seconds": 600}]},
        {"date": "2026-07-20", "au": 100.0,
         "exercise_seconds": [{"name": "Lat Pulldown", "seconds": 600}]},
    ]
    out = sr.daily_region_au(sessions)
    row = out["rows"][0]
    parts = sum(row[k] for k in list(REGIONS) + [sr.UNATTRIBUTED])
    assert parts == pytest.approx(row["total_au"], abs=1e-9)
    assert row["total_au"] == pytest.approx(300.0, abs=0.05)


def test_two_sessions_on_one_date_are_split_independently():
    """A gym session and a same-day yoga session must not let one's exercise
    mix redistribute the other's load."""
    merged = sr.daily_region_au([
        {"date": "2026-07-20", "au": 100.0,
         "exercise_seconds": [{"name": "Lat Pulldown", "seconds": 600}]},
        {"date": "2026-07-20", "au": 100.0,
         "exercise_seconds": [{"name": "Half Pigeon", "seconds": 600}]},
    ])["rows"][0]
    # The yoga half is unattributed; the gym half is not diluted by it.
    assert merged[sr.UNATTRIBUTED] == pytest.approx(100.0, abs=0.05)
    assert merged["upper_body"] == pytest.approx(90.0, abs=0.05)


# ─── weighting is by movement weight, not bare time ──────────────────────────

def test_the_split_is_weighted_by_movement_weight_not_just_time():
    """THE key design pin. Equal MINUTES of a 1.3 squat and a 0.25 scapular
    drill must not produce an equal split — the quantity being divided was
    itself produced by those weights."""
    mass = _mass([("Goblet Squat", 1200), ("Scapular Wall Slide", 1200)])
    assert mass["shares"]["lower_body"] > 2 * mass["shares"]["upper_body"]


def test_total_mass_equals_content_weightings_weighted_seconds():
    """The identity that makes this a decomposition of the AU rather than a
    second opinion about it."""
    items = [{"name": "Goblet Squat", "seconds": 600},
             {"name": "Dead Bug", "seconds": 300},
             {"name": "Lat Pulldown", "seconds": 450}]
    mass = sr.session_region_mass(items)
    assert mass["total_mass"] == pytest.approx(
        content_weighting.day_content_multiplier(items)["weighted_seconds"], abs=0.05,
    )


# ─── the athlete's founding requirement ──────────────────────────────────────

def test_a_hike_puts_most_of_its_au_in_lower_body():
    """The real importer shape: one synthetic exercise, one duration set."""
    mass = _mass([("Outdoor Hike", 7200)])
    parts = sr.split_session_au(300.0, mass)
    assert parts["lower_body"] / 300.0 >= 0.75
    assert parts["lower_body"] > parts["core"] + parts["upper_body"]
    assert parts[sr.UNATTRIBUTED] == 0.0


def test_a_hike_reproduces_the_documented_worked_example():
    """The table in services/strain_regions.py's docstring is a claim about
    behaviour; this is the claim under test."""
    parts = sr.split_session_au(300.0, _mass([("Outdoor Hike", 7200)]))
    assert (parts["upper_body"], parts["core"], parts["lower_body"]) == (15.0, 45.0, 240.0)
    strains = sr.region_strain({**parts, "regions_known": True}, 2)
    assert strains == {"upper_body": 6.4, "core": 9.7, "lower_body": 15.0}


# ─── non-additivity, asserted positively ─────────────────────────────────────

def test_regional_strains_do_not_sum_to_the_overall_strain():
    """THIS IS THE LOG CURVE, NOT A BUG.

    engine.load_to_strain is 21*ln(x+1)/ln(601), so ln(a)+ln(b) != ln(a+b) and
    the three regional readings total far more than the headline. If this test
    fails because someone made them add up, the change that did it is wrong —
    not this test."""
    parts = sr.split_session_au(300.0, _mass([("Outdoor Hike", 7200)]))
    strains = sr.region_strain({**parts, "regions_known": True}, 2)
    overall = engine.au_to_strain(300.0, 2)
    assert sum(strains.values()) > overall + 1.0


def test_every_region_is_bounded_above_by_the_overall():
    """The property that stops the screen looking broken: a part can never
    read larger than the whole, because regional AU <= total AU and the curve
    is monotonic."""
    parts = sr.split_session_au(300.0, _mass([("Outdoor Hike", 7200)]))
    strains = sr.region_strain({**parts, "regions_known": True}, 2)
    overall = engine.au_to_strain(300.0, 2)
    for region, value in strains.items():
        assert value <= overall, region


def test_additivity_gap_reports_the_difference_rather_than_hiding_it():
    parts = sr.split_session_au(300.0, _mass([("Outdoor Hike", 7200)]))
    strains = sr.region_strain({**parts, "regions_known": True}, 2)
    overall = engine.au_to_strain(300.0, 2)
    assert sr.additivity_gap(strains, overall) == pytest.approx(
        round(sum(strains.values()) - overall, 1), abs=1e-9,
    )
    assert sr.additivity_gap({r: None for r in REGIONS}, overall) is None
    assert sr.additivity_gap(strains, None) is None


def test_no_public_name_suggests_a_regional_total():
    """additivity_gap is the ONLY place the three are added, and its name says
    it measures a gap. A `total_region_strain` would be a lie with a signature."""
    for banned in ("total_region_strain", "combined_strain", "regions_strain_sum",
                   "sum_region_strain", "overall_from_regions"):
        assert not hasattr(sr, banned), banned


def test_the_non_additive_note_states_the_mechanism():
    note = sr.NON_ADDITIVE_NOTE.lower()
    assert "logarithm" in note or "log" in note
    assert "never sum" in note or "do not add" in note


# ─── unmapped names ──────────────────────────────────────────────────────────

def test_an_unmapped_name_is_reported_not_dropped():
    mass = _mass([("Goblet Squat", 600), ("Made Up Drill", 600)])
    assert mass["unmapped_names"] == ["Made Up Drill"]
    parts = sr.split_session_au(200.0, mass)
    assert sum(parts.values()) == pytest.approx(200.0, abs=1e-9)
    assert parts[sr.UNATTRIBUTED] > 0.0


def test_an_unmapped_name_is_never_spread_across_the_regions():
    """Spreading it would assert the drill loaded upper body, which for a yoga
    pose or a self-assessment is a fabrication."""
    mass = _mass([("Made Up Drill", 600)])
    assert mass["mass"] == {r: 0.0 for r in REGIONS}
    assert mass["unattributed_mass"] > 0.0


def test_a_fully_unmapped_session_has_no_regions_rather_than_zeros():
    """A 45-minute yoga session loaded something. Three zeros would be a lie;
    None with a stated reason is not. Same rule as the flexibility ladder's
    'an unmeasured muscle has no number'."""
    mass = _mass([("Half Pigeon", 1200), ("Low Lunge", 900)])
    assert mass["regions_known"] is False
    parts = sr.split_session_au(150.0, mass)
    strains = sr.region_strain({**parts, "regions_known": mass["regions_known"]}, 2)
    assert strains == {r: None for r in REGIONS}


def test_the_self_assessment_lands_in_the_unattributed_bucket():
    mass = _mass([("Week 1 Self-Assessment", 300)])
    assert mass["regions_known"] is False
    assert mass["unmapped_names"] == ["Week 1 Self-Assessment"]


def test_a_region_with_no_work_reads_zero_on_a_training_day():
    """0.0 beside a 14.2 means 'you did no upper-body work', which is true.
    A dash there would read as missing data, which is false."""
    parts = sr.split_session_au(200.0, _mass([("Hip Thrust (Loaded)", 900)]))
    strains = sr.region_strain({**parts, "regions_known": True}, 2)
    assert strains["upper_body"] == 0.0
    assert strains["lower_body"] > 0.0


# ─── degenerate inputs ───────────────────────────────────────────────────────

def test_zero_logged_seconds_does_not_divide_by_zero():
    mass = _mass([("Goblet Squat", 0)])
    assert mass["total_mass"] == 0.0
    parts = sr.split_session_au(100.0, mass)
    assert sum(parts.values()) == pytest.approx(100.0, abs=1e-9)
    assert parts[sr.UNATTRIBUTED] == 100.0


def test_no_session_means_no_regions():
    assert sr.region_strain(None, 2) == {r: None for r in REGIONS}
    assert sr.region_strain({"regions_known": False}, 2) == {r: None for r in REGIONS}


def test_a_row_without_regional_keys_is_not_read_as_zeros():
    """Existing callers hand-build [{'date', 'total_au'}]. Absent is not the
    same claim as zero."""
    rows = [{"date": "2026-07-20", "total_au": 300.0}]
    assert sr.region_au_for_date(rows, date(2026, 7, 20)) is None


def test_renormalisation_is_reported_rather_than_silent(monkeypatch):
    broken = dict(tc.EXERCISE_REGION_SHARES)
    broken["Goblet Squat"] = {"upper_body": 0.10, "core": 0.50, "lower_body": 0.80}
    monkeypatch.setattr(tc, "EXERCISE_REGION_SHARES", broken)
    shares, basis = sr.region_shares_for("Goblet Squat")
    assert basis == sr.BASIS_RENORMALISED
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-9)
    mass = _mass([("Goblet Squat", 600)])
    assert mass["renormalised_names"] == ["Goblet Squat"]


# ─── the rolling stand-in ────────────────────────────────────────────────────

def test_rolling_prior_region_strain_mirrors_the_overall_fallback():
    rows = [{"date": "2026-07-13", "upper_body": 70.0, "core": 0.0, "lower_body": 630.0}]
    out = sr.rolling_prior_region_strain(rows, 1, today=date(2026, 7, 20))
    assert out["lower_body"] > out["upper_body"] > 0
    assert out["core"] == 0.0


def test_rolling_is_all_none_when_the_window_is_empty():
    """So a screen never shows 0.0/0.0/0.0 under a headline reading
    'No Readings'."""
    out = sr.rolling_prior_region_strain([], 1, today=date(2026, 7, 20))
    assert out == {r: None for r in REGIONS}


# ─── the heart-rate term ─────────────────────────────────────────────────────

def test_hr_load_is_divided_by_the_au_shares_and_says_so():
    row = {"upper_body": 15.0, "core": 45.0, "lower_body": 240.0,
           "regions_known": True}
    loads, basis = sr.region_hr_load({"edwards_load": 200.0}, row)
    assert basis == sr.HR_BASIS_AU_SHARES
    assert sum(loads.values()) == pytest.approx(200.0, abs=1e-9)
    assert loads["lower_body"] > loads["core"] > loads["upper_body"]


def test_hr_load_is_none_basis_without_a_row_or_a_split():
    assert sr.region_hr_load(None, None)[1] == sr.HR_BASIS_NONE
    assert sr.region_hr_load({"edwards_load": 200.0},
                             {"regions_known": False})[1] == sr.HR_BASIS_NONE


def test_per_region_blend_uses_the_shared_blend_weight():
    from services import hr_load

    row = {"upper_body": 15.0, "core": 45.0, "lower_body": 240.0,
           "regions_known": True}
    loads, basis = sr.region_hr_load({"edwards_load": 200.0}, row)
    rpe = sr.region_strain(row, 2)
    blended = sr.blend_region_strain(loads, rpe, basis)
    for region, (value, source) in blended.items():
        assert source == hr_load.SOURCE_BLENDED, region
        expected, _ = hr_load.blend_strain(hr_load.hr_strain(loads[region]), rpe[region])
        assert value == expected


def test_without_hr_the_blend_is_the_rpe_value_unchanged():
    from services import hr_load

    row = {"upper_body": 15.0, "core": 45.0, "lower_body": 240.0,
           "regions_known": True}
    rpe = sr.region_strain(row, 2)
    blended = sr.blend_region_strain({r: 0.0 for r in REGIONS}, rpe, sr.HR_BASIS_NONE)
    for region, (value, source) in blended.items():
        assert source == hr_load.SOURCE_RPE, region
        assert value == rpe[region]


# ─── the step modifier stays off the regions ─────────────────────────────────

def test_the_step_modifier_is_not_applied_to_any_region():
    """It is added on the LOG scale, so the same +1.5 is worth 2.7 AU at strain
    2 and 140 AU at strain 15 — a factor of 52. Its own docstring names a
    lumbar (core) rationale for a walking (lower) mechanism, so every placement
    is arbitrary; leaving it on the day total is arbitrary in a way that
    fabricates no regional load."""
    source = (__import__("pathlib").Path("services/strain_regions.py")
              .read_text(encoding="utf-8"))
    assert "step_strain_modifier" not in source
    assert "apply_step_modifier" not in source


def test_the_attributed_fraction_is_reported():
    out = sr.daily_region_au([{
        "date": "2026-07-20", "au": 200.0, "elapsed_seconds": 3600.0,
        "exercise_seconds": [{"name": "Goblet Squat", "seconds": 1800}],
    }])
    assert out["attributed_fraction"] == pytest.approx(0.5, abs=1e-9)
