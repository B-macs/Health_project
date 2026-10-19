"""The morning check-in form's starting values (rebuild Phase 2, fault F3).

A day without a check-in opens the form at FORM_DEFAULTS. A day that already
has one opens it at that entry's values, each brought into what its control can
show, and the save then stores exactly what the form shows
(Repository.save_check_in with replace=True). Before 2026-10-19 the form always
opened at its defaults and a second save the same day merged field by field,
reading a value equal to its default as "not filled in": a pain of 4 could not
be corrected back to 0, and the pain gate kept reading 4.

FORM_DEFAULTS are the same values as Repository._CHECKIN_FIELD_MAP's, which
still decide the field-by-field merge when the form could not read the day's
entry; tests/test_checkin_form.py keeps the two equal. The phone app's form
(rebuild Phase 5) takes its starting values from here too.
"""

from __future__ import annotations

from services.models import CheckInRecord

CONDITIONS: tuple[str, ...] = ("Excellent", "Good", "Average", "Below Average", "Poor")

FORM_DEFAULTS: dict[str, object] = {
    "current_condition": "Excellent",
    "tightness_score": 0,
    "pain_score": 0,
    "anatomical_locations": [],
    "sensation_tags": [],
    "subjective_tightness": "",
    "alcohol_units": 0.0,
    "travel_flag": False,
    "psych_stress_score": 1,
    "instability_events": 0,
    "bristol_type": 4,
    "unusual_stool_colour": False,
    "hunger_deviation": 0,
    "thirst_intensity": 1,
    "electrolytes_taken": False,
    "meditation_minutes": 0.0,
    "relaxation_depth": 1,
}

#: Whole-number controls and the range each can show.
_WHOLE: dict[str, tuple[int, int]] = {
    "tightness_score": (0, 10), "pain_score": (0, 10), "psych_stress_score": (1, 5),
    "instability_events": (0, 20), "bristol_type": (0, 7), "hunger_deviation": (-2, 2),
    "thirst_intensity": (1, 5), "relaxation_depth": (1, 5),
}
#: Decimal controls and their range.
_DECIMAL: dict[str, tuple[float, float]] = {
    "alcohol_units": (0.0, 20.0), "meditation_minutes": (0.0, 120.0),
}
_SWITCHES = ("travel_flag", "unusual_stool_colour", "electrolytes_taken")


def initial_values(record: CheckInRecord | None, locations=(), tags=()) -> dict[str, object]:
    """The form's starting value for every field: the defaults for a day with
    no entry, else the entry's own values. A stored value a control cannot show
    (outside its range, an unknown option) is brought to the nearest value it
    can, or to the default, so the form never fails to open on old data.
    `locations` and `tags` are the multi-select options; a stored choice that is
    no longer an option is left out rather than breaking the control."""
    values = dict(FORM_DEFAULTS)
    if record is None:
        return values
    for field, default in FORM_DEFAULTS.items():
        got = getattr(record, field, None)
        if got is None:
            continue
        if field in _WHOLE:
            low, high = _WHOLE[field]
            try:
                values[field] = min(high, max(low, int(round(float(got)))))
            except (TypeError, ValueError):
                values[field] = default
        elif field in _DECIMAL:
            low, high = _DECIMAL[field]
            try:
                values[field] = min(high, max(low, float(got)))
            except (TypeError, ValueError):
                values[field] = default
        elif field == "current_condition":
            values[field] = got if got in CONDITIONS else default
        elif field in ("anatomical_locations", "sensation_tags"):
            allowed = set(locations if field == "anatomical_locations" else tags)
            values[field] = [x for x in got if not allowed or x in allowed]
        elif field in _SWITCHES:
            values[field] = bool(got)
        else:
            values[field] = str(got)
    return values
