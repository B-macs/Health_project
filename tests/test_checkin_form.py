"""The morning check-in form's starting values (rebuild Phase 2, fault F3).

A day with a check-in opens the form at that entry's values, so a second save
the same day can set a field back to its default (pain 4 → 0) instead of the
merge reading the default as "not filled in". No Streamlit and no network.
"""

from __future__ import annotations

from services import checkin_form as cf
from services import repository
from services.models import CheckInRecord


def test_a_day_without_a_check_in_opens_at_the_defaults():
    assert cf.initial_values(None) == cf.FORM_DEFAULTS


def test_a_day_with_a_check_in_opens_at_its_values():
    stored = CheckInRecord(date="2026-10-19", current_condition="Good", tightness_score=3.0,
                           pain_score=4.0, anatomical_locations=["Lower Back"],
                           sensation_tags=["Tight"], subjective_tightness="stiff on rising",
                           alcohol_units=1.5, travel_flag=True, psych_stress_score=2.0,
                           bristol_type=3, meditation_minutes=10.0)
    form = cf.initial_values(stored, locations=["Lower Back", "Hip"], tags=["Tight"])
    assert form["pain_score"] == 4 and isinstance(form["pain_score"], int)
    assert form["tightness_score"] == 3 and form["current_condition"] == "Good"
    assert form["anatomical_locations"] == ["Lower Back"] and form["sensation_tags"] == ["Tight"]
    assert form["subjective_tightness"] == "stiff on rising" and form["travel_flag"] is True
    assert form["alcohol_units"] == 1.5 and form["meditation_minutes"] == 10.0
    assert form["bristol_type"] == 3 and form["psych_stress_score"] == 2


def test_a_value_the_control_cannot_show_never_stops_the_form_opening():
    odd = CheckInRecord(date="2026-10-19", current_condition="Fine", tightness_score=None,
                        pain_score=12.0, anatomical_locations=["Old region name"],
                        psych_stress_score="x", hunger_deviation=-5)
    form = cf.initial_values(odd, locations=["Lower Back"], tags=[])
    assert form["pain_score"] == 10                              # brought into 0-10
    assert form["current_condition"] == cf.FORM_DEFAULTS["current_condition"]
    assert form["tightness_score"] == cf.FORM_DEFAULTS["tightness_score"]
    assert form["anatomical_locations"] == []                    # no longer an option
    assert form["psych_stress_score"] == cf.FORM_DEFAULTS["psych_stress_score"]
    assert form["hunger_deviation"] == -2


def test_the_form_defaults_are_the_merges_defaults():
    # The merge still uses its defaults when the form could not read the day's
    # entry; a form default that differs would be stored over a real reading.
    merge = {field: default for field, (_p, _k, default) in repository._CHECKIN_FIELD_MAP.items()}
    assert merge == cf.FORM_DEFAULTS
