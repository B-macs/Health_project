"""The check-in form's rules, moved out of views/checkin.py on 2026-10-19
(move INS-7): the backfill window, the field limits the engine API enforces,
meditation_done from the minutes, and every field sent explicitly, so a value
equal to its default is stored as itself (fault F3).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from services import checkin_form as cf

TODAY = date(2026, 10, 19)


def _form(**over):
    values = dict(cf.FORM_DEFAULTS)
    values.update(over)
    return values


def test_today_and_the_three_days_before_can_be_saved():
    assert cf.date_options(TODAY) == [TODAY - timedelta(days=i) for i in range(4)]
    assert cf.date_options(TODAY)[0] == TODAY, "the form opens on today"
    assert cf.problems(TODAY - timedelta(days=3), TODAY, _form()) == []
    assert cf.problems(TODAY - timedelta(days=4), TODAY, _form())
    assert cf.problems(TODAY + timedelta(days=1), TODAY, _form())


def test_minutes_logged_mean_the_practice_was_done():
    assert cf.meditation_done(10.0) and not cf.meditation_done(0.0)
    assert not cf.meditation_done(None)
    assert cf.record_from_form(TODAY, TODAY, _form(meditation_minutes=15.0)).meditation_done
    assert not cf.record_from_form(TODAY, TODAY, _form()).meditation_done


def test_a_default_value_is_stored_as_itself_and_a_missing_field_is_refused():
    # F3: pain back to 0 is a real reading, never "not filled in".
    record = cf.record_from_form(TODAY, TODAY, _form(pain_score=0))
    assert record.pain_score == 0 and record.date == TODAY.isoformat()
    values = _form()
    del values["pain_score"]
    with pytest.raises(cf.CheckInError) as exc:
        cf.record_from_form(TODAY, TODAY, values)
    assert "pain_score is not set" in exc.value.errors
    assert "pain_score is not set" in cf.problems(TODAY, TODAY, _form(pain_score=None))


@pytest.mark.parametrize("field,value", [
    ("pain_score", 11), ("pain_score", -1), ("pain_score", 4.5), ("pain_score", True),
    ("tightness_score", "3"), ("psych_stress_score", 0), ("bristol_type", 8),
    ("hunger_deviation", 3), ("alcohol_units", 20.5), ("meditation_minutes", -5.0),
    ("current_condition", "Fine"), ("travel_flag", 1), ("subjective_tightness", 3),
    ("anatomical_locations", "Lower Back"),
])
def test_a_value_outside_its_control_is_refused(field, value):
    assert cf.problems(TODAY, TODAY, _form(**{field: value})), (field, value)


def test_the_limits_are_the_controls_own():
    assert cf.WHOLE_RANGES["pain_score"] == (0, 10)
    assert cf.WHOLE_RANGES["bristol_type"] == (0, 7)
    assert cf.DECIMAL_RANGES["alcohol_units"] == (0.0, 20.0)
    assert set(cf.DECIMAL_STEPS) == set(cf.DECIMAL_RANGES)
    assert cf.problems(TODAY, TODAY, _form(alcohol_units=3)) == [], "a whole number of units"


def test_a_choice_outside_the_options_and_an_unknown_field_are_refused():
    assert cf.problems(TODAY, TODAY, _form(anatomical_locations=["Hip"]),
                       locations=["Lower Back"]), "not an option"
    assert cf.problems(TODAY, TODAY, _form(anatomical_locations=["Lower Back"]),
                       locations=["Lower Back"]) == []
    assert any("unknown fields" in e for e in cf.problems(TODAY, TODAY, _form(mood=3)))


def test_the_save_replaces_only_an_entry_the_form_opened():
    calls = []

    class _Repo:
        def save_check_in(self, record, replace=False):
            calls.append(replace)

    record = cf.record_from_form(TODAY, TODAY, _form())
    cf.save(_Repo(), record, opened_entry=True)
    cf.save(_Repo(), record, opened_entry=False)
    assert calls == [True, False]
