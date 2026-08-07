"""
Tests for services/scheduling.py — readiness-based auto-shift (Feature 6).

Covers should_evaluate_shift (the idempotency guard), should_shift_session
(each of the three trigger conditions in isolation, plus the no-trigger
case), and swap_pairs_for_shift (the pairwise-adjacent-day swap, reproducing
the user's own Mon/Wed/Fri -> Tue/Thu/Sat example exactly).

sleep_debt_hours itself now lives in tests/test_readiness.py, alongside
services.readiness.sleep_debt_hours (moved there 2026-07-30 so
compute_readiness could use it too — see that module's docstring).

Note: the idempotency GUARD (never re-evaluate a date that already has a
shift_reasons entry) lives in views/training.py, not here — these tests only
verify swap_pairs_for_shift's own output is well-defined, deterministic, and
side-effect-free when called more than once.
"""

from dataclasses import replace
from datetime import date, timedelta

import training_plan as tp
from services import plan
from services import scheduling
from services.models import Phase


# ─── should_evaluate_shift (idempotency guard) ──────────────────────────────
# Extracted from views/training.py so this guard -- which gates a live
# Notion write -- has direct test coverage instead of living untested
# inline in a Streamlit view.

def test_should_evaluate_shift_false_on_a_non_gym_day():
    assert scheduling.should_evaluate_shift(False, "2026-07-06", {}) is False


def test_should_evaluate_shift_false_once_already_recorded_for_today():
    assert scheduling.should_evaluate_shift(
        True, "2026-07-06", {"2026-07-06": "Sleep debt of 10.2h over the last 7 nights"},
    ) is False


def test_should_evaluate_shift_true_on_a_gym_day_not_yet_recorded():
    assert scheduling.should_evaluate_shift(
        True, "2026-07-06", {"2026-07-08": "some other date's reason"},
    ) is True


def test_should_evaluate_shift_true_with_no_shift_reasons_at_all():
    assert scheduling.should_evaluate_shift(True, "2026-07-06", {}) is True


# ─── should_shift_session ───────────────────────────────────────────────────

def test_should_shift_session_triggers_on_sleep_debt():
    # for_date's own night is comfortable (11h, not short) -- isolates the
    # debt trigger from the single-night-short-sleep trigger.
    bio_rows = [
        {"date": "2026-07-01", "sleep_duration_hours": 4.0},
        {"date": "2026-07-02", "sleep_duration_hours": 4.0},
        {"date": "2026-07-03", "sleep_duration_hours": 4.0},
        {"date": "2026-07-04", "sleep_duration_hours": 4.0},
        {"date": "2026-07-05", "sleep_duration_hours": 11.0},
        {"date": "2026-07-06", "sleep_duration_hours": 11.0},
        {"date": "2026-07-07", "sleep_duration_hours": 11.0},  # today, comfortable
    ]
    shift, reason = scheduling.should_shift_session(bio_rows, [], date(2026, 7, 7))
    assert shift is True
    assert reason == "Sleep debt of 12.0h over the last 7 nights"


def test_should_shift_session_triggers_on_single_night_short_sleep():
    # Only one row (today) -- insufficient history for any sleep-debt
    # baseline (sleep_debt_hours returns 0.0), isolating the short-sleep
    # trigger.
    bio_rows = [{"date": "2026-07-07", "sleep_duration_hours": 4.2}]
    shift, reason = scheduling.should_shift_session(bio_rows, [], date(2026, 7, 7))
    assert shift is True
    assert reason == "Only 4.2h slept last night"


def test_should_shift_session_triggers_on_consecutive_day_alcohol():
    bio_rows = [{"date": "2026-07-07", "sleep_duration_hours": 8.0}]
    checkin_rows = [
        {"date": "2026-07-06", "alcohol_units": 2.0},  # yesterday
        {"date": "2026-07-05", "alcohol_units": 1.0},  # day before
    ]
    shift, reason = scheduling.should_shift_session(bio_rows, checkin_rows, date(2026, 7, 7))
    assert shift is True
    assert reason == "Alcohol logged 2 days in a row"


def test_should_shift_session_does_not_trigger_on_single_alcohol_day():
    # Only yesterday has alcohol logged, not the day before -- one day short
    # of CONSECUTIVE_ALCOHOL_DAYS (2), so it must not trigger.
    bio_rows = [{"date": "2026-07-07", "sleep_duration_hours": 8.0}]
    checkin_rows = [{"date": "2026-07-06", "alcohol_units": 2.0}]
    shift, reason = scheduling.should_shift_session(bio_rows, checkin_rows, date(2026, 7, 7))
    assert (shift, reason) == (False, None)


def test_should_shift_session_does_not_trigger_on_nonconsecutive_alcohol():
    # Alcohol on the day before yesterday but NOT yesterday breaks the
    # consecutive-day streak counted backward from yesterday.
    bio_rows = [{"date": "2026-07-07", "sleep_duration_hours": 8.0}]
    checkin_rows = [{"date": "2026-07-05", "alcohol_units": 3.0}]
    shift, reason = scheduling.should_shift_session(bio_rows, checkin_rows, date(2026, 7, 7))
    assert (shift, reason) == (False, None)


def test_should_shift_session_returns_false_none_when_nothing_triggers():
    bio_rows = [
        {"date": "2026-07-01", "sleep_duration_hours": 8.0},
        {"date": "2026-07-02", "sleep_duration_hours": 8.0},
        {"date": "2026-07-03", "sleep_duration_hours": 8.0},
        {"date": "2026-07-04", "sleep_duration_hours": 8.0},
        {"date": "2026-07-05", "sleep_duration_hours": 8.0},
        {"date": "2026-07-06", "sleep_duration_hours": 8.0},
        {"date": "2026-07-07", "sleep_duration_hours": 8.0},
    ]
    checkin_rows = [{"date": "2026-07-06", "alcohol_units": 0.0}]
    shift, reason = scheduling.should_shift_session(bio_rows, checkin_rows, date(2026, 7, 7))
    assert (shift, reason) == (False, None)


# ─── swap_pairs_for_shift ───────────────────────────────────────────────────

_PLAN_DICT = {
    1: {"is_gym_session": True},   # Mon
    2: {"is_gym_session": False},  # Tue
    3: {"is_gym_session": True},   # Wed
    4: {"is_gym_session": False},  # Thu
    5: {"is_gym_session": True},   # Fri
    6: {"is_gym_session": False},  # Sat
    7: {"is_gym_session": False},  # Sun
}


def _monday_on_or_before(d: date) -> date:
    return d - timedelta(days=d.weekday())


def test_swap_pairs_for_shift_reproduces_mon_wed_fri_becomes_tue_thu_sat():
    monday = _monday_on_or_before(date(2026, 7, 6))
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, monday, _PLAN_DICT)

    assert overrides == {
        monday.isoformat():                     2,  # Mon shows Tue's (day2) content
        (monday + timedelta(days=1)).isoformat(): 1,  # Tue shows Mon's (day1) content
        (monday + timedelta(days=2)).isoformat(): 4,  # Wed shows Thu's (day4) content
        (monday + timedelta(days=3)).isoformat(): 3,  # Thu shows Wed's (day3) content
        (monday + timedelta(days=4)).isoformat(): 6,  # Fri shows Sat's (day6) content
        (monday + timedelta(days=5)).isoformat(): 5,  # Sat shows Fri's (day5) content
    }
    # Sunday (day 7) is untouched -- odd day out, no drift introduced.
    assert (monday + timedelta(days=6)).isoformat() not in overrides


def test_swap_pairs_for_shift_leaves_every_other_date_mapped_identically():
    monday = _monday_on_or_before(date(2026, 7, 6))
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")
    overrides = scheduling.swap_pairs_for_shift(phase, monday, _PLAN_DICT)
    shifted_phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active",
                           date_overrides=overrides)

    for offset in range(28):
        d = monday + timedelta(days=offset)
        if d.isoformat() in overrides:
            continue
        assert (plan.day_number_in_phase(shifted_phase, d)
                == plan.day_number_in_phase(phase, d))

    # And start_date/length_days are never touched by the shift.
    assert shifted_phase.start_date == phase.start_date
    assert shifted_phase.length_days == phase.length_days


def test_swap_pairs_for_shift_only_touches_from_date_forward():
    # Triggered on Wednesday (a gym day) mid-week -- Monday/Tuesday, before
    # from_date, must be untouched even though Monday is also a gym day.
    monday = _monday_on_or_before(date(2026, 7, 6))
    wednesday = monday + timedelta(days=2)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, wednesday, _PLAN_DICT)

    assert monday.isoformat() not in overrides
    assert (monday + timedelta(days=1)).isoformat() not in overrides
    assert overrides == {
        wednesday.isoformat():                     4,
        (wednesday + timedelta(days=1)).isoformat(): 3,  # Thu
        (wednesday + timedelta(days=2)).isoformat(): 6,  # Fri
        (wednesday + timedelta(days=3)).isoformat(): 5,  # Sat
    }


def test_swap_pairs_for_shift_is_deterministic_across_repeated_calls():
    # The idempotency GUARD lives in views/training.py, not here -- this only
    # verifies the pure function itself is side-effect-free and returns an
    # identical, well-defined result no matter how many times it's called
    # for the same inputs.
    monday = _monday_on_or_before(date(2026, 7, 6))
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    first = scheduling.swap_pairs_for_shift(phase, monday, _PLAN_DICT)
    second = scheduling.swap_pairs_for_shift(phase, monday, _PLAN_DICT)

    assert first == second
    # Inputs themselves must be untouched (frozen Phase, dict left as-is).
    assert phase.date_overrides == {}
    assert _PLAN_DICT[1] == {"is_gym_session": True}


def test_swap_pairs_for_shift_trailing_gym_day_with_no_partner_self_maps():
    # A gym day on Sunday itself has no same-week neighbor to pair with --
    # its day-number content must be left unchanged, but it still needs an
    # entry (a no-op self-mapping) so the caller's idempotency guard has
    # something to key off for from_date. Omitting it entirely caused an
    # unbounded re-trigger-and-rewrite loop against Notion (see
    # swap_pairs_for_shift's docstring) -- regression guard for that.
    plan_dict = dict(_PLAN_DICT)
    plan_dict[7] = {"is_gym_session": True}  # Sunday is now a gym day too
    monday = _monday_on_or_before(date(2026, 7, 6))
    sunday = monday + timedelta(days=6)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, sunday, plan_dict)

    assert overrides == {sunday.isoformat(): 7}  # self-mapped, day-number unchanged


def test_trailing_gym_day_still_produces_a_shift_reason_for_from_date():
    # End-to-end regression guard: swap_pairs_for_shift's self-mapping for a
    # trailing gym day must survive through shift_reason_entries too, so
    # views/training.py's idempotency guard (checks shift_reasons, not
    # date_overrides) actually sees from_date recorded.
    plan_dict = dict(_PLAN_DICT)
    plan_dict[7] = {"is_gym_session": True}
    monday = _monday_on_or_before(date(2026, 7, 6))
    sunday = monday + timedelta(days=6)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, sunday, plan_dict)
    reasons = scheduling.shift_reason_entries(overrides, "Only 4.2h slept last night")

    assert sunday.isoformat() in reasons


# ─── shift_reason_entries ───────────────────────────────────────────────────

def test_shift_reason_entries_applies_same_reason_to_every_touched_date():
    overrides = {"2026-07-06": 2, "2026-07-07": 1}
    reasons = scheduling.shift_reason_entries(overrides, "Only 4.2h slept last night")
    assert reasons == {
        "2026-07-06": "Only 4.2h slept last night",
        "2026-07-07": "Only 4.2h slept last night",
    }


# ─── SESSION_PRIORITY / day_type / can_overwrite ────────────────────────────

def test_session_priority_orders_test_above_main_above_stretch_above_rest():
    p = scheduling.SESSION_PRIORITY
    assert p["test"] > p["main"] > p["stretch"] > p["rest"]
    assert set(p) == {"test", "main", "stretch", "rest"}


def test_day_type_returns_none_for_absent_unknown_or_none_content():
    assert scheduling.day_type(None) is None
    assert scheduling.day_type({}) is None
    assert scheduling.day_type({"is_gym_session": True}) is None   # every Stage 1 day
    assert scheduling.day_type({"day_type": "cardio"}) is None     # not in the table
    assert scheduling.day_type({"day_type": "main"}) == "main"


def test_can_overwrite_is_strict_and_false_on_any_unknown_type():
    assert scheduling.can_overwrite("main", "rest") is True
    assert scheduling.can_overwrite("test", "main") is True
    assert scheduling.can_overwrite("main", "main") is False    # equal never overwrites
    assert scheduling.can_overwrite("stretch", "main") is False  # lower never overwrites
    assert scheduling.can_overwrite(None, "rest") is False       # unknown mover
    assert scheduling.can_overwrite("main", None) is False       # unknown target


# ─── missed_reschedules ─────────────────────────────────────────────────────
# Fixtures are Monday-start phases so date offset o resolves to day o+1 and
# the weekday names in the comments are literal.

def _phase(monday: date, length_days: int = 28, **kwargs) -> Phase:
    return Phase(2, "Stage 2", monday.isoformat(), length_days, "active", **kwargs)


_MONDAY = _monday_on_or_before(date(2026, 7, 6))

# The realistic Stage-2A-shaped week: mains Mon/Wed/Fri, plus the two types
# the live plan doesn't place mid-week yet.
_TYPED_PLAN = {
    1: {"is_gym_session": True, "day_type": "main"},    # Mon
    2: {"is_gym_session": False, "day_type": "rest"},   # Tue
    3: {"is_gym_session": True, "day_type": "main"},    # Wed
    4: {"is_gym_session": False, "day_type": "rest"},   # Thu
    5: {"is_gym_session": True, "day_type": "main"},    # Fri
    6: {"day_type": "stretch"},                          # Sat
    7: {"day_type": "test"},                             # Sun
}


def _rest_days(*day_nums: int) -> dict:
    return {n: {"day_type": "rest"} for n in day_nums}


def test_missed_main_moves_to_earliest_later_rest_day_in_its_week():
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    monday, tuesday = _MONDAY, _MONDAY + timedelta(days=1)

    overrides, reasons = scheduling.missed_reschedules(
        _phase(monday), plan_dict, set(), today=tuesday)

    assert overrides == {monday.isoformat(): 2, tuesday.isoformat(): 1}
    assert reasons == {
        monday.isoformat(): f"Missed → moved to {tuesday.isoformat()}",
        tuesday.isoformat(): f"Moved from {monday.isoformat()} (missed)",
    }


def test_nothing_overwrites_an_equal_or_higher_priority_session():
    # A missed stretch day skips an equal (stretch) and a higher (main) day
    # and lands on the first strictly-lower (rest) one.
    plan_dict = {1: {"day_type": "stretch"}, 2: {"day_type": "stretch"},
                 3: {"day_type": "main"}, **_rest_days(4, 5, 6, 7)}
    monday, thursday = _MONDAY, _MONDAY + timedelta(days=3)

    overrides, _ = scheduling.missed_reschedules(
        _phase(monday), plan_dict, set(), today=monday + timedelta(days=1))

    assert overrides == {monday.isoformat(): 4, thursday.isoformat(): 1}


def test_missed_rest_day_is_never_evaluated_and_writes_nothing():
    # A missed rest day can never claim anything (nothing ranks below rest),
    # so evaluating it would only generate a pointless Notion write and a
    # banner per skipped recovery day.
    plan_dict = _rest_days(1, 2, 3, 4, 5, 6, 7)
    result = scheduling.missed_reschedules(
        _phase(_MONDAY), plan_dict, set(), today=_MONDAY + timedelta(days=3))
    assert result == ({}, {})


def test_two_misses_are_ordered_priority_desc_then_date_asc_and_both_carry_when_slots_exist():
    # Monday's main and Tuesday's test are both missed. The test resolves
    # FIRST despite its later date and claims Wednesday (the earliest slot);
    # the main then takes Thursday. A main landing the day AFTER a test is
    # allowed — only the day BEFORE contaminates.
    plan_dict = {1: {"day_type": "main"}, 2: {"day_type": "test"},
                 **_rest_days(3, 4, 5, 6, 7)}
    monday = _MONDAY
    tuesday, wednesday, thursday = (monday + timedelta(days=o) for o in (1, 2, 3))

    overrides, reasons = scheduling.missed_reschedules(
        _phase(monday), plan_dict, set(), today=wednesday)

    assert overrides == {
        tuesday.isoformat(): 3, wednesday.isoformat(): 2,   # test -> Wednesday
        monday.isoformat(): 4, thursday.isoformat(): 1,     # main -> Thursday
    }
    assert reasons[wednesday.isoformat()] == f"Moved from {tuesday.isoformat()} (missed)"
    assert reasons[thursday.isoformat()] == f"Moved from {monday.isoformat()} (missed)"


def test_a_target_claimed_by_an_earlier_miss_is_not_reused_in_the_same_pass():
    # Two missed mains. The first claims Thursday (Wednesday is blocked by
    # Tuesday's still-unresolved main next door); the second must then skip
    # Wednesday (its neighbour Thursday now holds a pending main) and Friday
    # (same neighbour), landing on Saturday. No shared target, and the two
    # rescheduled mains are not adjacent.
    plan_dict = {1: {"day_type": "main"}, 2: {"day_type": "main"},
                 **_rest_days(3, 4, 5, 6, 7)}
    monday = _MONDAY
    tuesday, wednesday, thursday, saturday = (
        monday + timedelta(days=o) for o in (1, 2, 3, 5))

    overrides, _ = scheduling.missed_reschedules(
        _phase(monday), plan_dict, set(), today=wednesday)

    assert overrides == {
        monday.isoformat(): 4, thursday.isoformat(): 1,
        tuesday.isoformat(): 6, saturday.isoformat(): 2,
    }


def test_miss_with_no_eligible_target_self_maps_with_a_dropped_reason():
    # The realistic dense week: a Wednesday main missed with Friday's main
    # still ahead has nowhere legal to go — Thursday and Saturday sit next
    # to Friday's main, Friday is equal priority, Sunday is the test. It
    # drops, visibly, with the reason on the missed date.
    monday, wednesday = _MONDAY, _MONDAY + timedelta(days=2)

    overrides, reasons = scheduling.missed_reschedules(
        _phase(monday), _TYPED_PLAN, {monday.isoformat()}, today=monday + timedelta(days=3))

    assert overrides == {wednesday.isoformat(): 3}
    assert reasons == {
        wednesday.isoformat():
            scheduling.DROPPED_REASON_PREFIX + "no free lower-priority day this week",
    }


def test_every_evaluated_miss_always_leaves_a_shift_reasons_entry():
    # Both Monday's and Wednesday's mains are missed and neither can be
    # placed (each candidate neighbours Friday's main or the Sunday test).
    # Every evaluated miss must leave a ledger entry — and merging the
    # result back into the phase must make the next call a no-op, which is
    # the property that terminates the caller's evaluate->write->rerun
    # cycle.
    monday, wednesday = _MONDAY, _MONDAY + timedelta(days=2)
    phase = _phase(monday)
    today = monday + timedelta(days=3)

    overrides, reasons = scheduling.missed_reschedules(phase, _TYPED_PLAN, set(), today)

    assert set(reasons) == {monday.isoformat(), wednesday.isoformat()}
    assert all(r.startswith(scheduling.DROPPED_REASON_PREFIX) for r in reasons.values())

    settled = replace(phase,
                      date_overrides={**phase.date_overrides, **overrides},
                      shift_reasons={**phase.shift_reasons, **reasons})
    assert scheduling.missed_reschedules(settled, _TYPED_PLAN, set(), today) == ({}, {})


def test_a_miss_already_in_shift_reasons_stays_missed_even_if_readiness_wrote_it():
    # The two mechanisms share one ledger. A date the readiness auto-shift
    # touched reads as already handled, so a miss on it is NOT rescued —
    # the accepted fail-safe limitation, pinned here so it stays deliberate.
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    phase = _phase(_MONDAY, shift_reasons={_MONDAY.isoformat(): "Only 4.2h slept last night"})

    result = scheduling.missed_reschedules(
        phase, plan_dict, set(), today=_MONDAY + timedelta(days=1))

    assert result == ({}, {})


def test_sunday_miss_is_never_evaluated_because_its_week_has_ended():
    # A Sunday date only becomes "past" the following Monday, when the scan
    # window has already moved to the new week — so a Sunday miss (both live
    # test days fall on Sundays this phase) is structurally unrecoverable.
    plan_dict = {7: {"day_type": "main"}, **_rest_days(1, 2, 3, 4, 5, 6, 8, 9)}
    tuesday_week2 = _MONDAY + timedelta(days=8)

    result = scheduling.missed_reschedules(
        _phase(_MONDAY), plan_dict, set(), today=tuesday_week2)

    assert result == ({}, {})


def test_monday_scan_window_is_empty_and_returns_no_deltas():
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    result = scheduling.missed_reschedules(_phase(_MONDAY), plan_dict, set(), today=_MONDAY)
    assert result == ({}, {})


def test_forced_rest_zero_override_is_neither_a_miss_nor_a_target():
    # Tuesday carries a forced-rest 0 override (not a miss: day-number 0 is
    # out of range); Thursday carries one too (not a target: dates already
    # in date_overrides are protected). The miss skips both and lands Friday.
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    monday, friday = _MONDAY, _MONDAY + timedelta(days=4)
    tuesday, thursday = _MONDAY + timedelta(days=1), _MONDAY + timedelta(days=3)
    phase = _phase(monday, date_overrides={tuesday.isoformat(): 0, thursday.isoformat(): 0})

    overrides, reasons = scheduling.missed_reschedules(
        phase, plan_dict, set(), today=thursday)

    assert overrides == {monday.isoformat(): 5, friday.isoformat(): 1}
    assert tuesday.isoformat() not in reasons
    assert thursday.isoformat() not in reasons


def test_miss_resolved_through_an_earlier_manual_override_carries_the_overridden_content():
    # Monday was manually remapped to day 3 (a main) before being missed —
    # the carry moves the RESOLVED content, day 3, not the formula's day 1.
    # (Wednesday still resolves to day 3 as well — a manual override is a
    # single-date edit, so day-numbers can duplicate across dates — which is
    # exactly why Tuesday/Thursday are spacing-blocked here.)
    plan_dict = {1: {"day_type": "rest"}, 2: {"day_type": "rest"},
                 3: {"day_type": "main"}, **_rest_days(4, 5, 6, 7)}
    monday, friday = _MONDAY, _MONDAY + timedelta(days=4)
    phase = _phase(monday, date_overrides={monday.isoformat(): 3})

    overrides, _ = scheduling.missed_reschedules(
        phase, plan_dict, set(), today=monday + timedelta(days=1))

    assert overrides == {monday.isoformat(): 5, friday.isoformat(): 3}


def test_no_two_main_days_land_adjacent_after_a_reschedule():
    # Wednesday's main is untouched and upcoming, so the carried Monday main
    # may not land on Tuesday (day before it) or Thursday (day after it).
    plan_dict = {1: {"day_type": "main"}, 2: {"day_type": "rest"},
                 3: {"day_type": "main"}, **_rest_days(4, 5, 6, 7)}
    monday, friday = _MONDAY, _MONDAY + timedelta(days=4)

    overrides, _ = scheduling.missed_reschedules(
        _phase(monday), plan_dict, set(), today=monday + timedelta(days=1))

    assert overrides == {monday.isoformat(): 5, friday.isoformat(): 1}


def test_a_main_never_lands_the_day_before_a_test_and_a_test_never_lands_the_day_after_a_main():
    # (a) Carried main: Tuesday is blocked because Wednesday is the test.
    plan_a = {1: {"day_type": "main"}, 2: {"day_type": "rest"},
              3: {"day_type": "test"}, **_rest_days(4, 5, 6, 7)}
    monday, thursday = _MONDAY, _MONDAY + timedelta(days=3)
    overrides, _ = scheduling.missed_reschedules(
        _phase(monday), plan_a, set(), today=monday + timedelta(days=1))
    assert overrides == {monday.isoformat(): 4, thursday.isoformat(): 1}

    # (b) Carried test: Tuesday holds a main it MAY overwrite on priority,
    # but the post-swap mapping puts a main on its previous day, and
    # Wednesday sits the day after Tuesday's real main — both blocked, so
    # the test lands Thursday.
    plan_b = {1: {"day_type": "test"}, 2: {"day_type": "main"},
              **_rest_days(3, 4, 5, 6, 7)}
    overrides, _ = scheduling.missed_reschedules(
        _phase(monday), plan_b, set(), today=monday + timedelta(days=1))
    assert overrides == {monday.isoformat(): 4, thursday.isoformat(): 1}


def test_reschedule_never_crosses_the_missed_sessions_sunday_or_the_phase_end():
    # (a) Saturday's main missed, Sunday is the test: next week's Monday is
    # free but out of reach — the carry never crosses Sunday, so it drops.
    plan_a = {**_rest_days(1, 2, 3, 4, 5, 8, 9), 6: {"day_type": "main"},
              7: {"day_type": "test"}}
    saturday, sunday = _MONDAY + timedelta(days=5), _MONDAY + timedelta(days=6)
    overrides, reasons = scheduling.missed_reschedules(
        _phase(_MONDAY), plan_a, set(), today=sunday)
    assert overrides == {saturday.isoformat(): 6}
    assert reasons[saturday.isoformat()].startswith(scheduling.DROPPED_REASON_PREFIX)

    # (b) A 5-day phase ending Friday: Friday's main missed, and although
    # Saturday/Sunday are free calendar days they sit beyond the phase end —
    # an override there would ADD a scheduled day to a later week's rollup.
    plan_b = {**_rest_days(1, 2, 3, 4), 5: {"day_type": "main"}}
    friday = _MONDAY + timedelta(days=4)
    overrides, reasons = scheduling.missed_reschedules(
        _phase(_MONDAY, length_days=5), plan_b, set(), today=_MONDAY + timedelta(days=5))
    assert overrides == {friday.isoformat(): 5}
    assert reasons[friday.isoformat()].startswith(scheduling.DROPPED_REASON_PREFIX)


def test_missed_reschedules_is_pure_deterministic_and_leaves_inputs_untouched():
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    phase = _phase(_MONDAY)
    logged: set[str] = set()
    today = _MONDAY + timedelta(days=1)

    first = scheduling.missed_reschedules(phase, plan_dict, logged, today)
    second = scheduling.missed_reschedules(phase, plan_dict, logged, today)

    assert first == second
    assert phase.date_overrides == {} and phase.shift_reasons == {}
    assert plan_dict[1] == {"day_type": "main"}
    assert logged == set()


def test_a_logged_date_is_not_a_miss_regardless_of_session_type():
    # logged_dates is the day strip's own yoga-INCLUSIVE source, so a
    # yoga-only day reads as done here exactly as it does on screen — the
    # engine's "missed" and the strip's "missed" are one definition.
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    result = scheduling.missed_reschedules(
        _phase(_MONDAY), plan_dict, {_MONDAY.isoformat()}, today=_MONDAY + timedelta(days=2))
    assert result == ({}, {})


def test_reschedule_onto_today_suppresses_the_readiness_shift_via_the_shared_guard():
    # A carried session that claims TODAY writes today's shift_reasons
    # entry, and should_evaluate_shift keys on exactly that — one scheduling
    # rewrite per date, deliberately.
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    phase = _phase(_MONDAY)
    tuesday = _MONDAY + timedelta(days=1)

    overrides, reasons = scheduling.missed_reschedules(phase, plan_dict, set(), today=tuesday)

    assert tuesday.isoformat() in overrides
    merged = {**phase.shift_reasons, **reasons}
    assert scheduling.should_evaluate_shift(True, tuesday.isoformat(), merged) is False


def test_stage1_plan_without_day_type_is_inert_for_rescheduling():
    # Stage 1 authors no day_type, so nothing is carried and nothing is a
    # target — the feature is inert for phase 1 by construction.
    phase = Phase(1, "Stage 1 Rehab", _MONDAY.isoformat(), 21, "active")
    result = scheduling.missed_reschedules(
        phase, tp.PLAN, set(), today=_MONDAY + timedelta(days=3))
    assert result == ({}, {})


# ─── swap_pairs_for_shift × SESSION_PRIORITY (the hardened partner check) ───

def test_swap_pairs_for_shift_still_swaps_when_partner_has_no_day_type():
    # A typed mover with an UNTYPED neighbour swaps exactly as before — an
    # unknown partner permits the swap, otherwise adding day_type to gym
    # days before recovery days (or any partial adoption) would silently
    # kill the whole auto-shift.
    plan_dict = {1: {"is_gym_session": True, "day_type": "main"},
                 2: {"is_gym_session": False}}
    monday = _monday_on_or_before(date(2026, 7, 6))
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, monday, plan_dict)

    assert overrides[monday.isoformat()] == 2
    assert overrides[(monday + timedelta(days=1)).isoformat()] == 1


def test_swap_pairs_for_shift_never_swaps_a_gym_day_onto_a_known_test_day():
    # Monday's gym day may not displace Tuesday's test day — it self-maps
    # instead — and the walk still continues: Thursday's gym day swaps with
    # its rest-typed neighbour as normal.
    plan_dict = {
        1: {"is_gym_session": True, "day_type": "main"},
        2: {"day_type": "test"},
        3: {"day_type": "rest"},
        4: {"is_gym_session": True, "day_type": "main"},
        5: {"day_type": "rest"},
        6: {"day_type": "rest"},
        7: {"day_type": "rest"},
    }
    monday = _monday_on_or_before(date(2026, 7, 6))
    thursday = monday + timedelta(days=3)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, monday, plan_dict)

    assert overrides == {
        monday.isoformat(): 1,                          # refused -> self-map
        thursday.isoformat(): 5,                        # later gym day still shifts
        (thursday + timedelta(days=1)).isoformat(): 4,
    }


def test_blocked_from_date_swap_still_self_maps_and_writes_a_reason():
    # The guaranteed-entry-for-from_date invariant under the new refusal
    # branch: without the self-map, shift_reason_entries would omit
    # from_date and the caller's guard would re-trigger the Notion write on
    # every render — the documented unbounded-loop failure, recreated.
    plan_dict = {1: {"is_gym_session": True, "day_type": "main"},
                 2: {"day_type": "test"}, **_rest_days(3, 4, 5, 6, 7)}
    monday = _monday_on_or_before(date(2026, 7, 6))
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, monday, plan_dict)
    reasons = scheduling.shift_reason_entries(overrides, "Only 4.2h slept last night")

    assert overrides == {monday.isoformat(): 1}
    assert monday.isoformat() in reasons


# ─── swap_pairs_for_shift × _spacing_ok (post-walk validation) ──────────────
# The live phase: Stage 2A started Monday 2026-07-20, so day 26 (main) falls
# on Friday 2026-08-14, day 27 (rest) on Saturday, and day 28 — the Day-28
# physio reassessment, day_type "test" — on Sunday 2026-08-16.

_LIVE_PHASE = Phase(2, "Stage 2A", "2026-07-20", 28, "active")


def test_auto_shift_never_lands_a_main_on_the_eve_of_a_test():
    # THE live hazard the adversarial review found: a readiness trigger on
    # Friday 2026-08-14 must NOT push Session C onto the Saturday before
    # the reassessment — leg work the morning before the test is the exact
    # contamination the athlete's own rule forbids. The swap is undone and
    # Friday holds in place.
    overrides = scheduling.swap_pairs_for_shift(
        _LIVE_PHASE, date(2026, 8, 14), tp.PLAN_STAGE2)
    assert overrides == {"2026-08-14": 26}


def test_week4_monday_trigger_holds_everything_rather_than_stack_mains():
    # With Friday pinned off the test's eve, EVERY partial shift of week 4
    # stacks two mains somewhere, so the whole cascade collapses to a hold:
    # the Monday session stays scheduled (the readiness volume modifier
    # still protects the athlete) and the banner says so.
    overrides = scheduling.swap_pairs_for_shift(
        _LIVE_PHASE, date(2026, 8, 10), tp.PLAN_STAGE2)
    assert overrides == {"2026-08-10": 22}


def test_typed_canonical_cascade_still_shifts_all_three_mains_when_sunday_is_rest():
    # Weeks 1-3 end on a plain rest day, so the approved Mon/Wed/Fri ->
    # Tue/Thu/Sat cascade must survive the spacing validation unchanged —
    # mid-walk adjacency is transient and must not be punished.
    overrides = scheduling.swap_pairs_for_shift(
        _LIVE_PHASE, date(2026, 7, 20), tp.PLAN_STAGE2)
    assert overrides == {
        "2026-07-20": 2, "2026-07-21": 1,
        "2026-07-22": 4, "2026-07-23": 3,
        "2026-07-24": 6, "2026-07-25": 5,
    }


def test_a_refused_swap_never_leaves_two_mains_adjacent():
    # Monday's swap is individually legal, but Wednesday's is refused by
    # Thursday's test — leaving Monday's moved main next to Wednesday's
    # unmoved one. The post-walk validation undoes Monday's swap too.
    plan_dict = {1: {"is_gym_session": True, "day_type": "main"},
                 2: {"day_type": "rest"},
                 3: {"is_gym_session": True, "day_type": "main"},
                 4: {"day_type": "test"}, **_rest_days(5, 6, 7)}
    monday = _monday_on_or_before(date(2026, 7, 6))
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, monday, plan_dict)

    assert overrides == {monday.isoformat(): 1}


def test_auto_shift_walk_never_crosses_the_phase_end():
    # A 5-day phase ending Friday with a gym day on its last day: Saturday
    # is a free calendar date but outside the phase, where a swapped
    # session would never render, count, or be rescued — same cap, same
    # reason as missed_reschedules' phase-end horizon.
    plan_dict = {**_rest_days(1, 2, 3, 4), 5: {"is_gym_session": True, "day_type": "main"}}
    monday = _monday_on_or_before(date(2026, 7, 6))
    friday = monday + timedelta(days=4)
    phase = Phase(2, "Stage 2", monday.isoformat(), 5, "active")

    overrides = scheduling.swap_pairs_for_shift(phase, friday, plan_dict)

    assert overrides == {friday.isoformat(): 5}


def test_a_forced_rest_partner_is_never_swapped_onto():
    # Tuesday carries the athlete's explicit forced-rest 0 override; the
    # auto-shift fired precisely because readiness demanded MORE recovery,
    # so clobbering the rest day would invert the trigger's own intent.
    plan_dict = {1: {"is_gym_session": True, "day_type": "main"}, 2: {"day_type": "rest"}}
    monday = _monday_on_or_before(date(2026, 7, 6))
    tuesday = monday + timedelta(days=1)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active",
                  date_overrides={tuesday.isoformat(): 0})

    overrides = scheduling.swap_pairs_for_shift(phase, monday, plan_dict)

    assert overrides == {monday.isoformat(): 1}


def test_a_partner_already_in_the_ledger_is_never_reswapped():
    # Tuesday holds a session carried in by missed_reschedules (override +
    # ledger reason). A date is scheduled at most once: the auto-shift may
    # not displace it again nor overwrite its reason.
    plan_dict = {1: {"is_gym_session": True, "day_type": "main"},
                 2: {"day_type": "rest"}, **_rest_days(3, 4, 5, 6, 7)}
    monday = _monday_on_or_before(date(2026, 7, 6))
    tuesday = monday + timedelta(days=1)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active",
                  date_overrides={tuesday.isoformat(): 9},
                  shift_reasons={tuesday.isoformat(): "Moved from 2026-06-29 (missed)"})

    overrides = scheduling.swap_pairs_for_shift(phase, monday, plan_dict)

    assert tuesday.isoformat() not in overrides
    assert overrides == {monday.isoformat(): 1}


def test_a_gym_date_mid_walk_already_in_the_ledger_is_skipped():
    # Wednesday's main was itself carried in earlier (ledger entry), so the
    # walk skips it — and the validation then also undoes Monday's swap,
    # which would have stacked Monday's moved main against Wednesday's.
    plan_dict = {1: {"is_gym_session": True, "day_type": "main"},
                 2: {"day_type": "rest"},
                 3: {"is_gym_session": True, "day_type": "main"},
                 **_rest_days(4, 5, 6, 7)}
    monday = _monday_on_or_before(date(2026, 7, 6))
    wednesday = monday + timedelta(days=2)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active",
                  shift_reasons={wednesday.isoformat(): "Moved from 2026-06-29 (missed)"})

    overrides = scheduling.swap_pairs_for_shift(phase, monday, plan_dict)

    assert wednesday.isoformat() not in overrides
    assert overrides == {monday.isoformat(): 1}


def test_shift_reason_entries_marks_self_maps_held_and_real_moves_bare():
    # A held day must not read "Session moved" on screen; the ledger
    # semantics (entry exists -> never re-evaluated) are identical either
    # way, so the anti-loop guard survives the retag.
    monday = _monday_on_or_before(date(2026, 7, 6))
    tuesday = monday + timedelta(days=1)
    phase = Phase(2, "Stage 2", monday.isoformat(), 28, "active")
    overrides = {monday.isoformat(): 1, tuesday.isoformat(): 3}  # self-map + real move

    reasons = scheduling.shift_reason_entries(
        overrides, "Only 4.2h slept last night", phase=phase)

    assert reasons[monday.isoformat()] == (
        scheduling.HELD_REASON_PREFIX + "Only 4.2h slept last night")
    assert reasons[tuesday.isoformat()] == "Only 4.2h slept last night"
    assert scheduling.should_evaluate_shift(
        True, monday.isoformat(), reasons) is False


def test_a_logged_today_is_never_claimed_as_a_target():
    # Today already holds a completed session (the yoga-inclusive source
    # counts it): the carried main must skip it and land on the next free
    # day, never relabelling a done date.
    plan_dict = {1: {"day_type": "main"}, **_rest_days(2, 3, 4, 5, 6, 7)}
    monday = _MONDAY
    tuesday, wednesday = monday + timedelta(days=1), monday + timedelta(days=2)

    overrides, reasons = scheduling.missed_reschedules(
        _phase(monday), plan_dict, {tuesday.isoformat()}, today=tuesday)

    assert overrides == {monday.isoformat(): 3, wednesday.isoformat(): 1}
    assert reasons[wednesday.isoformat()] == f"Moved from {monday.isoformat()} (missed)"


def test_higher_priority_miss_drops_while_lower_still_places():
    # A missed test with no legal slot (Saturday sits after Friday's
    # performed main, Sunday is another test) drops — and the lower-priority
    # stretch missed the day after it must STILL be evaluated and placed.
    plan_dict = {**_rest_days(1, 2, 6), 3: {"day_type": "test"},
                 4: {"day_type": "stretch"}, 5: {"day_type": "main"},
                 7: {"day_type": "test"}}
    monday = _MONDAY
    wednesday, thursday = monday + timedelta(days=2), monday + timedelta(days=3)
    friday, saturday = monday + timedelta(days=4), monday + timedelta(days=5)

    overrides, reasons = scheduling.missed_reschedules(
        _phase(monday), plan_dict, {friday.isoformat()}, today=saturday)

    assert overrides == {wednesday.isoformat(): 3,       # test: dropped, self-map
                         thursday.isoformat(): 6,        # stretch -> Saturday
                         saturday.isoformat(): 4}
    assert reasons[wednesday.isoformat()].startswith(scheduling.DROPPED_REASON_PREFIX)


def test_both_view_writer_blocks_are_gated_off_during_a_guided_session():
    # Source-scan pin (the tests/test_manual_sync_serialised.py idiom): both
    # scheduling writer blocks in views/training.py remap today's
    # day-number, and the guided flow's tp_ex_idx/tp_actuals are keyed by
    # exercise index against the content the session STARTED with — a
    # mid-session remap would carry them onto a different session.
    import pathlib
    src = pathlib.Path(scheduling.__file__).parent.parent / "views" / "training.py"
    text = src.read_text(encoding="utf-8")
    assert "if active is not None and not _in_session:" in text
    assert "if active is not None and day_num is not None and not _in_session:" in text
