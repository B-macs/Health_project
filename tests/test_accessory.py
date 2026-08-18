"""The accessory session — services/accessory.py.

Three things these tests are actually protecting, in descending order of how
badly they would fail silently:

  1. THE ACCOUNTING. An exercise name missing from the three
     `training_constants` maps is counted at `UNMAPPED_EXERCISE_WEIGHT` 1.0,
     i.e. as fully-loaded barbell work. That is the Stage 1 over-count — 34 of
     63 names, mobility days reading as barbell days for weeks — arriving by a
     new door. Nothing about it looks like an error at the time.

  2. THE SUPPLEMENTARY MECHANISM. One string in one frozenset is what stops an
     accessory session marking a plan day done. If that membership is lost, the
     app quietly decides the day's real training is finished.

  3. THE SAFETY VOCABULARY. `check_movement` returning `unknown` is not a
     block, so an unruled hang would read exactly like a cleared one.
"""

from datetime import date

import pytest

import training_constants as tc
import training_plan as tp
from services import accessory as acc
from services import flexibility as fx
from services import rules
from services import strain_regions as sr
from services.content_weighting import UNMAPPED_EXERCISE_WEIGHT
from services.repository import Repository


TODAY = date(2026, 8, 17)


def _rows(**au):
    """One region row for yesterday, with whatever regions are named loaded."""
    row = {"date": "2026-08-16", "upper_body": 0.0, "core": 0.0, "lower_body": 0.0,
           "unattributed": 0.0, "regions_known": True}
    row.update(au)
    row["total_au"] = sum(row[r] for r in sr.REGIONS) + row["unattributed"]
    return [row]


def _plan_day(day_type="stretch", rpe=4, exercises=()):
    return {"objective": "test", "phase": "test", "session_rpe_target": rpe,
            "day_type": day_type, "exercises": list(exercises)}


# ─────────────────────────────────────────────────────────────────────────────
#  Determinism — the session is chosen, so the choice has to be reproducible
# ─────────────────────────────────────────────────────────────────────────────

def test_same_inputs_give_the_same_session_every_time():
    kwargs = dict(plan_day=_plan_day(), region_rows=_rows(upper_body=90.0),
                  today=TODAY)
    first = acc.choose(**kwargs)
    for _ in range(5):
        again = acc.choose(**kwargs)
        assert again.tier == first.tier
        assert again.region == first.region
        assert again.names == first.names
        assert again.reasons == first.reasons


def test_a_session_is_always_produced_even_with_nothing_to_go_on():
    choice = acc.choose(plan_day=None, today=TODAY)
    assert choice.exercises
    assert choice.region in sr.REGIONS
    assert choice.tier in (acc.TIER_FULL, acc.TIER_SHRUNK)


def test_every_reason_is_recorded_not_just_the_outcome():
    choice = acc.choose(plan_day=_plan_day(), region_rows=_rows(upper_body=90.0),
                        today=TODAY)
    assert choice.reasons, "a chosen session with no recorded reasoning is a guess"
    assert all(isinstance(r, str) and r.strip() for r in choice.reasons)


# ─────────────────────────────────────────────────────────────────────────────
#  Region selection
# ─────────────────────────────────────────────────────────────────────────────

def test_the_region_loaded_yesterday_is_not_the_region_worked_today():
    choice = acc.choose(plan_day=_plan_day(), region_rows=_rows(upper_body=200.0),
                        today=TODAY)
    assert choice.region != "upper_body"


def test_the_least_loaded_of_three_loaded_regions_wins():
    rows = _rows(upper_body=200.0, core=40.0, lower_body=120.0)
    assert acc.choose(plan_day=_plan_day(), region_rows=rows, today=TODAY).region == "core"


def test_no_row_for_yesterday_is_a_rest_day_and_reads_as_fresh():
    """Absent is not zero in general — but a day with no session carried no
    load, which is the one place the two coincide. The reason string has to say
    which of the two happened."""
    choice = acc.choose(plan_day=_plan_day(), region_rows=[], today=TODAY)
    assert any("rest day" in r for r in choice.reasons)


def test_an_unattributable_session_falls_back_to_the_week_not_to_zero():
    """A yoga day has real AU and an unknown distribution. Reading it as zero
    would call a shoulder-heavy flow a rest for the shoulders."""
    rows = [
        {"date": "2026-08-10", "upper_body": 150.0, "core": 30.0, "lower_body": 20.0,
         "unattributed": 0.0, "total_au": 200.0, "regions_known": True},
        {"date": "2026-08-16", "upper_body": 0.0, "core": 0.0, "lower_body": 0.0,
         "unattributed": 180.0, "total_au": 180.0, "regions_known": False},
    ]
    choice = acc.choose(plan_day=_plan_day(), region_rows=rows, today=TODAY)
    assert any("7-day mean" in r for r in choice.reasons)


def test_today_counts_as_if_the_planned_session_happens():
    """The athlete's own requirement: assume the day's real training will be
    done, whether or not it is logged yet."""
    run_day = tp.PLAN_STAGE2B[5]
    projected = acc.projected_region_au(run_day)
    assert projected["lower_body"] > projected["upper_body"], (
        "a running day has to project as lower-body load"
    )
    choice = acc.choose(plan_day=run_day, region_rows=[], today=TODAY)
    assert choice.region != "lower_body"


def test_an_empty_plan_day_projects_nothing_rather_than_guessing():
    assert acc.projected_region_au(None) == {r: 0.0 for r in sr.REGIONS}
    assert acc.projected_region_au({}) == {r: 0.0 for r in sr.REGIONS}


def test_ties_break_in_a_fixed_declared_order():
    choice = acc.choose(plan_day=_plan_day(), region_rows=_rows(), today=TODAY)
    assert choice.region == acc._REGION_PREFERENCE[0]


# ─────────────────────────────────────────────────────────────────────────────
#  Regional ACWR may swap a region and may NEVER refuse a session
# ─────────────────────────────────────────────────────────────────────────────

def test_a_region_over_its_acwr_ceiling_is_swapped_away_from():
    rows = _rows(upper_body=200.0, core=10.0, lower_body=50.0)
    racwr = {"core": {"acwr": 1.9, "ceiling": 1.3},
             "upper_body": {"acwr": 1.0, "ceiling": 1.3},
             "lower_body": {"acwr": 0.9, "ceiling": 1.3}}
    choice = acc.choose(plan_day=_plan_day(), region_rows=rows,
                        region_acwr=racwr, today=TODAY)
    assert choice.region == "lower_body"
    assert any("over its" in r for r in choice.reasons)


def test_every_region_over_ceiling_still_returns_a_session():
    """`region_acwr` is advisory_only and hard_locked=False unconditionally.
    Building a refusal on it would be a per-region volume cap by another door —
    and the release half of this session is most useful exactly on the days the
    numbers look worst."""
    racwr = {r: {"acwr": 3.0, "ceiling": 1.3} for r in sr.REGIONS}
    choice = acc.choose(plan_day=_plan_day(), region_rows=_rows(),
                        region_acwr=racwr, today=TODAY)
    assert choice.exercises
    assert choice.region in sr.REGIONS


def test_withheld_regional_acwr_is_simply_not_consulted():
    """`insufficient_regional_load` carries acwr=None, which is the state for
    the whole first week of a block and through the travel fortnight."""
    racwr = {r: {"acwr": None, "ceiling": 1.3,
                 "status": sr.STATUS_INSUFFICIENT_REGIONAL_LOAD} for r in sr.REGIONS}
    with_it = acc.choose(plan_day=_plan_day(), region_rows=_rows(core=99.0),
                         region_acwr=racwr, today=TODAY)
    without = acc.choose(plan_day=_plan_day(), region_rows=_rows(core=99.0),
                         today=TODAY)
    assert with_it.region == without.region
    assert not any("ceiling" in r for r in with_it.reasons)


# ─────────────────────────────────────────────────────────────────────────────
#  Tier
# ─────────────────────────────────────────────────────────────────────────────

def test_a_rest_day_gets_the_release_only_version():
    choice = acc.choose(plan_day=_plan_day(day_type="rest", rpe=2), today=TODAY)
    assert choice.tier == acc.TIER_SHRUNK


def test_an_assessment_day_gets_the_release_only_version():
    """Day 28 is where the block's exit criteria are judged — final working
    loads and the functional screen. Extra work beside them is a confound."""
    choice = acc.choose(plan_day=_plan_day(day_type="test", rpe=4), today=TODAY)
    assert choice.tier == acc.TIER_SHRUNK
    assert any("assessment day" in r for r in choice.reasons)
    assert acc.choose(plan_day=tp.PLAN_STAGE2B[28], today=TODAY).tier == acc.TIER_SHRUNK


def test_a_heavy_day_gets_the_release_only_version():
    choice = acc.choose(plan_day=_plan_day(rpe=acc.HEAVY_DAY_RPE_TARGET), today=TODAY)
    assert choice.tier == acc.TIER_SHRUNK


def test_a_reduced_volume_day_gets_the_release_only_version():
    choice = acc.choose(plan_day=_plan_day(),
                        volume_rec={"multiplier": acc.LOW_VOLUME_MULTIPLIER},
                        today=TODAY)
    assert choice.tier == acc.TIER_SHRUNK
    assert any("normal volume" in r for r in choice.reasons)


def test_a_moderate_day_gets_the_full_version():
    choice = acc.choose(plan_day=_plan_day(rpe=4),
                        volume_rec={"multiplier": 1.0}, today=TODAY)
    assert choice.tier == acc.TIER_FULL


def test_the_shrunk_version_has_no_adaptation_seeking_work():
    """Release and decompress. Nothing that asks for an adaptation, which is
    what lets it sit beside a heavy gym day without becoming a sixth session.

    REFINED 2026-08-18, when the shrunk tier gained a 10-minute floor and
    started filling from the release lists. A plain intersection with
    _ACTIVATE gives a FALSE POSITIVE: Thoracic Extension (Rolled Towel) is in
    both — it is mobility, and lying back over a towel breathing into the
    position asks for no adaptation. What must never appear is something only
    an activation list offers, so that is what this asserts. Narrower on
    purpose, and the exercise it now allows is one the release lists already
    contained."""
    shrunk = acc.choose(plan_day=_plan_day(day_type="rest", rpe=2), today=TODAY)
    activation = {ex["name"] for group in acc._ACTIVATE.values() for ex in group}
    release = ({ex["name"] for ex in acc._SHRUNK_FILL}
               | {ex["name"] for ex in tp.ACCESSORY_HANG_LADDER})
    activation_only = activation - release
    assert not (set(shrunk.names) & activation_only), sorted(
        set(shrunk.names) & activation_only)


def test_both_tiers_land_inside_the_ten_to_twenty_minute_ask():
    for day, expected in ((_plan_day(day_type="rest", rpe=2), acc.TIER_SHRUNK),
                          (_plan_day(rpe=4), acc.TIER_FULL)):
        choice = acc.choose(plan_day=day, today=TODAY)
        assert choice.tier == expected
        assert 10 <= choice.estimated_minutes <= 20, choice.names


def test_both_tiers_rate_low_enough_to_still_be_an_accessory_session():
    assert max(acc.TIER_RPE.values()) <= 4


# ─────────────────────────────────────────────────────────────────────────────
#  Collisions with the day's own session
# ─────────────────────────────────────────────────────────────────────────────

def test_an_exercise_already_in_todays_session_is_not_repeated():
    day = _plan_day(exercises=[tp.ANTERIOR_HIP_RELEASE])
    choice = acc.choose(plan_day=day, battery_baseline_captured=True, today=TODAY)
    assert tp.ANTERIOR_HIP_RELEASE["name"] not in choice.names


def test_a_collision_substitutes_rather_than_leaving_the_slot_empty():
    """The block's own release block runs two of these in 28 of 28 days. A rule
    that merely DROPPED a collision would empty the release slot every single
    day — deleting the half of this session that justifies it."""
    for day_num, plan_day in tp.PLAN_STAGE2B.items():
        choice = acc.choose(plan_day=plan_day, battery_baseline_captured=True,
                            today=TODAY)
        release_names = {ex["name"] for ex in
                         (*acc._RELEASE_A, *acc._RELEASE_A_PRE_BASELINE)}
        assert set(choice.names) & release_names, (
            f"day {day_num} produced an accessory session with no release item"
        )


def test_no_exercise_appears_twice_in_one_accessory_session():
    for plan_day in tp.PLAN_STAGE2B.values():
        for baseline in (False, True):
            names = acc.choose(plan_day=plan_day,
                               battery_baseline_captured=baseline,
                               today=TODAY).names
            assert len(names) == len(set(names))


def test_every_authored_day_of_the_block_produces_a_usable_session():
    for day_num, plan_day in tp.PLAN_STAGE2B.items():
        choice = acc.choose(plan_day=plan_day, today=TODAY)
        assert len(choice.exercises) >= 3, f"day {day_num}: {choice.names}"
        assert choice.estimated_minutes <= 20, f"day {day_num}: {choice.names}"


# ─────────────────────────────────────────────────────────────────────────────
#  The battery gate
# ─────────────────────────────────────────────────────────────────────────────

def test_the_front_of_hip_protocol_is_held_until_the_battery_has_a_baseline():
    """Not a preference. The seated tilt is the battery's central measurement
    and starting this intervention before the three cold baseline mornings is
    the pre-declared failure mode."""
    choice = acc.choose(plan_day=_plan_day(), battery_baseline_captured=False,
                        today=TODAY)
    assert tp.ANTERIOR_HIP_RELEASE["name"] not in choice.names
    assert any("cold baseline" in r for r in choice.reasons)


def test_a_hip_flexor_release_is_still_offered_before_the_baseline_exists():
    """The athlete asked for a hip-flexor/psoas release by name. The gate covers
    the sustained-pressure protocol, not the standing stretch, so the ask is
    still answered meanwhile."""
    choice = acc.choose(plan_day=_plan_day(), battery_baseline_captured=False,
                        today=TODAY)
    assert tp.ACC_STANDING_HIP_FLEXOR["name"] in choice.names


def test_the_front_of_hip_protocol_leads_once_the_baseline_exists():
    choice = acc.choose(plan_day=_plan_day(), battery_baseline_captured=True,
                        today=TODAY)
    assert tp.ANTERIOR_HIP_RELEASE["name"] in choice.names


# ─────────────────────────────────────────────────────────────────────────────
#  The flexibility retest
# ─────────────────────────────────────────────────────────────────────────────

def test_lower_body_activation_is_suppressed_the_day_before_a_retest():
    """A leg day the day before reads as extra tightness in exactly the tissue
    under test — the same contamination class as a warm-up, one day earlier."""
    rows = _rows(upper_body=250.0, core=200.0, lower_body=1.0)
    plain = acc.choose(plan_day=_plan_day(), region_rows=rows, today=TODAY)
    assert plain.region == "lower_body"
    guarded = acc.choose(plan_day=_plan_day(), region_rows=rows,
                         legs_must_stay_clean=True, today=TODAY)
    assert guarded.region != "lower_body"
    assert any("retest" in r for r in guarded.reasons)


def test_nothing_the_session_can_emit_dirties_a_retest_unclassified():
    """`flexibility.RELEASE_EXERCISES` is an ALLOW-list: anything lower-body and
    not named there counts as loaded. An unclassified name would silently mark
    every accessory day a leg day and leave no clean retest morning anywhere."""
    for name in acc.accessory_names():
        if tc.EXERCISE_BODY_REGION.get(name) != "lower_body":
            continue
        assert name in fx.RELEASE_EXERCISES or name in fx.MOBILITY_TIER_LOADS_LEGS, name


# ─────────────────────────────────────────────────────────────────────────────
#  The hang ladder
# ─────────────────────────────────────────────────────────────────────────────

def test_exactly_one_hang_runs_and_it_is_a_reachable_step():
    ladder = {ex["name"] for ex in tp.ACCESSORY_HANG_LADDER}
    reachable = {ex["name"] for ex in tp.ACCESSORY_HANG_LADDER[:acc.HANG_MAX_STEP]}
    for plan_day in tp.PLAN_STAGE2B.values():
        names = set(acc.choose(plan_day=plan_day, today=TODAY).names)
        assert len(names & ladder) == 1
        assert names & ladder <= reachable


def test_the_passive_hang_is_held_out_of_every_session():
    """The only genuinely passive end-range loading on a shoulder with three
    anterior dislocations, a failed capsular wrap and a Latarjet on a shallow
    glenoid. Authored, held, with the condition that lifts it written down."""
    assert acc.HANG_MAX_STEP < len(tp.ACCESSORY_HANG_LADDER)
    held = tp.ACCESSORY_HANG_LADDER[-1]["name"]
    assert held == "Passive Dead Hang"
    for plan_day in tp.PLAN_STAGE2B.values():
        for baseline in (False, True):
            assert held not in acc.choose(plan_day=plan_day,
                                          battery_baseline_captured=baseline,
                                          today=TODAY).names


def test_the_shrunk_tier_always_uses_the_easiest_hang():
    choice = acc.choose(plan_day=_plan_day(day_type="rest", rpe=2), today=TODAY)
    assert choice.hang_step == 1
    assert tp.ACCESSORY_HANG_LADDER[0]["name"] in choice.names


def test_every_hang_is_two_handed_and_says_so():
    """A single-arm hang on this shoulder is the one thing that must never be
    read into these instructions."""
    for ex in tp.ACCESSORY_HANG_LADDER:
        text = f"{ex['mechanics']} {ex.get('warning') or ''}".lower()
        assert "both hands" in text or "both arms" in text, ex["name"]
        assert "one arm" in text or "one hand" in text, (
            f"{ex['name']} never says not to hang single-armed"
        )


def test_every_hang_carries_the_right_shoulder_stop_rule():
    for ex in tp.ACCESSORY_HANG_LADDER:
        warning = (ex.get("warning") or "").lower()
        assert "end-feel" in warning, ex["name"]
        assert "apprehension" in warning or "instability" in warning, ex["name"]


# ─────────────────────────────────────────────────────────────────────────────
#  Safety vocabulary — `unknown` is not a block
# ─────────────────────────────────────────────────────────────────────────────

def test_every_emittable_movement_resolves_to_a_real_verdict():
    for name in acc.accessory_names():
        severity = rules.check_movement(name, 2)["severity"]
        assert severity != "unknown", (
            f"{name!r} has no rule — and `unknown` reads exactly like `cleared`"
        )


def test_nothing_emittable_is_contraindicated_at_the_live_stage():
    for name in acc.accessory_names():
        assert rules.check_movement(name, 2)["severity"] != "contraindicated", name


def test_hanging_is_ruled_as_caution_rather_than_cleared():
    for ex in tp.ACCESSORY_HANG_LADDER:
        assert rules.check_movement(ex["name"], 2)["severity"] == "caution", ex["name"]


def test_the_hang_rule_catches_nothing_it_was_not_written_for():
    """A permissive substring rule that fired on an unrelated movement would put
    a shoulder caution on it — the false-positive twin of the vocabulary bug."""
    planned = {ex["name"] for plan in (tp.PLAN, tp.PLAN_STAGE2, tp.PLAN_STAGE2B)
               for day in plan.values() for ex in day["exercises"]}
    ladder = {ex["name"] for ex in tp.ACCESSORY_HANG_LADDER}
    for name in planned - ladder:
        assert "hang" not in rules.normalise_movement(name), name


# ─────────────────────────────────────────────────────────────────────────────
#  The accounting — the failure that looks like nothing at all
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", acc.accessory_names())
def test_every_emittable_name_is_in_all_three_maps(name):
    assert name in tc.EXERCISE_BODY_REGION, "would leave every sector total"
    assert name in tc.EXERCISE_REGION_SHARES, "would land in `unattributed`"
    assert name in tc.EXERCISE_MOVEMENT_WEIGHT, (
        "would be counted at UNMAPPED_EXERCISE_WEIGHT, i.e. as barbell work"
    )


def test_nothing_emittable_falls_through_to_the_unmapped_weight():
    for name in acc.accessory_names():
        _, weight = tc.EXERCISE_MOVEMENT_WEIGHT[name]
        assert weight != UNMAPPED_EXERCISE_WEIGHT or name in tc.EXERCISE_MOVEMENT_WEIGHT


def test_region_shares_sum_to_one_for_every_emittable_name():
    for name in acc.accessory_names():
        shares = tc.EXERCISE_REGION_SHARES[name]
        assert set(shares) == set(sr.REGIONS)
        assert round(sum(shares.values()), 6) == 1.0, name
        for value in shares.values():
            assert round(value * 20, 6) == round(round(value * 20), 6), name


def test_the_sector_and_the_share_map_agree_on_which_region_dominates():
    """The same argmax invariant the rest of the repo is bound by, so the two
    maps cannot drift apart for these names either."""
    for name in acc.accessory_names():
        shares = tc.EXERCISE_REGION_SHARES[name]
        assert max(shares, key=lambda r: shares[r]) == tc.EXERCISE_BODY_REGION[name], name


# ─────────────────────────────────────────────────────────────────────────────
#  The supplementary mechanism
# ─────────────────────────────────────────────────────────────────────────────

def test_the_accessory_type_is_supplementary():
    """One string in one frozenset is what stops this session marking a plan day
    done. Lose it and the app decides the day's real training is finished."""
    assert acc.ACCESSORY_TYPE in Repository.SUPPLEMENTARY_SESSION_TYPES


def test_the_session_is_stamped_with_the_day_it_was_chosen_for():
    """The checkpoint slot is keyed by ACCESSORY_DAY_KEY, which unlike a plan
    day number is the SAME every day — so without a date nothing could tell a
    session abandoned yesterday from one in progress now, and the app would
    reopen a dead session every morning."""
    choice = acc.choose(plan_day=_plan_day(), today=TODAY)
    assert choice.on_date == TODAY.isoformat()
    assert acc.build_day(choice)["accessory_date"] == TODAY.isoformat()


def test_the_checkpoint_key_can_never_collide_with_a_plan_day():
    assert acc.ACCESSORY_DAY_KEY < 1
    assert acc.ACCESSORY_DAY_KEY not in tp.PLAN_STAGE2B
    assert acc.ACCESSORY_DAY_KEY not in tp.PLAN
    assert acc.ACCESSORY_DAY_KEY not in tp.PLAN_STAGE2


def test_the_day_dict_is_the_shape_the_renderer_reads():
    """`build_day` returning exactly a plan day's shape is what lets this run
    through the SAME guided flow instead of a second screen that would drift."""
    day = acc.build_day(acc.choose(plan_day=_plan_day(), today=TODAY))
    for key in ("objective", "phase", "session_rpe_target", "day_type", "exercises"):
        assert key in day
    assert day["day_type"] in {"main", "rest", "stretch", "test"}
    assert day["exercises"]


def test_the_shrunk_heading_does_not_promise_work_the_session_lacks():
    """A shrunk session is a hang, a release and two minutes of breathing. A
    heading of "Shoulders & Posture" over it would name work that is not there.
    Caught on screen, not by reasoning about it."""
    shrunk = acc.choose(plan_day=_plan_day(day_type="rest", rpe=2),
                        region_rows=_rows(core=200.0, lower_body=200.0), today=TODAY)
    assert shrunk.tier == acc.TIER_SHRUNK and shrunk.region == "upper_body"
    assert acc.build_day(shrunk)["objective"] == "Accessory — Release Only"

    full = acc.choose(plan_day=_plan_day(rpe=4),
                      region_rows=_rows(core=200.0, lower_body=200.0), today=TODAY)
    assert full.tier == acc.TIER_FULL
    assert acc.build_day(full)["objective"] == "Accessory — Shoulders & Posture"


def test_the_session_note_records_why_and_flags_the_confound():
    """The interscapular exit criterion says in terms that the intervention
    under test is the DESK HEIGHT, not the training. Scapular work here
    confounds it, so it is recorded rather than discovered afterwards."""
    rows = _rows(core=200.0, lower_body=200.0)
    choice = acc.choose(plan_day=_plan_day(rpe=4), region_rows=rows, today=TODAY)
    assert choice.region == "upper_body" and choice.tier == acc.TIER_FULL
    note = acc.session_note(choice)
    assert "interscapular" in note
    assert acc.build_day(choice)["accessory_note"] == note


# ─────────────────────────────────────────────────────────────────────────────
#  Layer boundary — this module chooses, it does not author
# ─────────────────────────────────────────────────────────────────────────────

def test_the_selector_defines_no_exercise_of_its_own():
    """WHAT lives in training_plan.py, WHICH lives here, HOW lives in the view.
    The same guard the flexibility cluster runs between its own three layers."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(acc))
    called = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "_ex" not in called, "an exercise was authored in the selector"
    authored = {id(ex) for plan in (tp.PLAN, tp.PLAN_STAGE2, tp.PLAN_STAGE2B)
                for day in plan.values() for ex in day["exercises"]}
    authored |= {id(ex) for ex in tp.ACCESSORY_HANG_LADDER}
    authored |= {id(getattr(tp, n)) for n in dir(tp)
                 if isinstance(getattr(tp, n), dict) and "biomechanical_focus" in getattr(tp, n)}
    for ex in acc.ACCESSORY_LIBRARY:
        assert id(ex) in authored, f"{ex['name']} is not a training_plan object"


def test_every_emittable_exercise_carries_its_patient_facing_text():
    for ex in acc.ACCESSORY_LIBRARY:
        for field in ("mechanics", "biomechanical_focus", "progression", "regression"):
            assert (ex.get(field) or "").strip(), f"{ex['name']} has no {field}"


# ─────────────────────────────────────────────────────────────────────────────
#  The view wiring, checked against the source
# ─────────────────────────────────────────────────────────────────────────────
#
# Same idiom as tests/test_manual_sync_serialised.py and
# tests/test_no_replay_unsafe_cached_elements.py: the behaviour lives inside a
# Streamlit render path that cannot be called from a test, so the source is the
# thing asserted against. These three were verified by hand in the running app
# on 2026-08-16; the tests are what stop them regressing unnoticed.

def _training_source() -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / "views" / "training.py").read_text(
        encoding="utf-8")


def test_the_accessory_session_logs_under_the_supplementary_type():
    """Without the override every row would log its own movement category, the
    session would not be supplementary, and it WOULD mark the plan day done —
    the app deciding the day's real training was finished."""
    source = _training_source()
    assert "movement_type_override=acc.ACCESSORY_TYPE" in source
    assert "movement_type_override or sess.movement_category(ex)" in source


def test_starting_an_accessory_session_refuses_while_one_is_in_flight():
    """There is one checkpoint slot. Entering mid-session would overwrite the
    plan session's saved progress, and the reset would clear the live state it
    was mirroring."""
    import ast
    tree = ast.parse(_training_source())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_start_accessory_session")
    body = [n for n in fn.body if not (isinstance(n, ast.Expr)
                                       and isinstance(n.value, ast.Constant))]
    guard = ast.unparse(body[0])
    assert isinstance(body[0], ast.If), "the refusal must be the FIRST thing it does"
    assert "tp_started" in guard and "tp_session_logged" in guard
    assert "tp_accessory_blocked" in ast.unparse(fn)


def test_exiting_overwrites_the_persisted_checkpoint_before_clearing_state():
    """`_init_state` restores an accessory checkpoint by a CONSTANT key, so
    clearing only session_state means the next render reads the live session
    straight back off disk and Discard appears to do nothing. Found exactly
    that way in the running app."""
    import ast
    tree = ast.parse(_training_source())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_exit_accessory_session")
    body = ast.unparse(fn)
    assert "_save_checkpoint(acc.ACCESSORY_DAY_KEY)" in body
    assert body.index("_save_checkpoint") < body.rindex("_clear_training_state")


def test_a_stale_accessory_session_is_dropped_on_restore():
    assert "accessory_date" in _training_source()
