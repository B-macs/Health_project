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

from datetime import date, timedelta

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
