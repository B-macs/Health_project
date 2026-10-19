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

from datetime import date, timedelta

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


# ─── Saving (move INS-7, 2026-10-19) ─────────────────────────────────────────

#: A check-in can be saved for today and the BACKFILL_DAYS days before, for a
#: missed morning. The form opens on today whatever is already filled in.
BACKFILL_DAYS = 3

#: The ranges every control draws from and the engine API enforces.
WHOLE_RANGES = _WHOLE
DECIMAL_RANGES = _DECIMAL
SWITCHES = _SWITCHES
#: The decimal controls' steps.
DECIMAL_STEPS: dict[str, float] = {"alcohol_units": 0.5, "meditation_minutes": 5.0}
_LISTS = ("anatomical_locations", "sensation_tags")


class CheckInError(ValueError):
    """A check-in that cannot be stored; `errors` names every reason."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def date_options(today: date) -> list[date]:
    """The days a check-in can be saved for: today first, then back."""
    return [today - timedelta(days=i) for i in range(BACKFILL_DAYS + 1)]


def meditation_done(minutes: float | None) -> bool:
    """There is no "practice done" control: any minutes logged count."""
    return bool(minutes) and minutes > 0


def _number(value, whole: bool) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, int) if whole else isinstance(value, (int, float))


def problems(day: date, today: date, values: dict, locations=(), tags=()) -> list[str]:
    """Every reason the form's values cannot be stored, or [].

    EVERY field is required. "Not set" is never read from a value equal to
    its default (fault F3: a second check-in the same day could not set pain
    back to 0), so a value the athlete did not touch is sent as what the form
    shows. `locations` and `tags` are the multi-select options; when given,
    a choice outside them is refused."""
    errors: list[str] = []
    if day not in date_options(today):
        errors.append(f"the date {day.isoformat()} is not today or one of the "
                      f"{BACKFILL_DAYS} days before")
    for field in FORM_DEFAULTS:
        if field not in values or values[field] is None:
            errors.append(f"{field} is not set")
            continue
        value = values[field]
        if field in _WHOLE:
            low, high = _WHOLE[field]
            if not _number(value, whole=True) or not low <= value <= high:
                errors.append(f"{field} must be a whole number from {low} to {high}")
        elif field in _DECIMAL:
            low, high = _DECIMAL[field]
            if not _number(value, whole=False) or not low <= value <= high:
                errors.append(f"{field} must be a number from {low:g} to {high:g}")
        elif field == "current_condition":
            if value not in CONDITIONS:
                errors.append(f"{field} must be one of {', '.join(CONDITIONS)}")
        elif field in _LISTS:
            allowed = set(locations if field == "anatomical_locations" else tags)
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                errors.append(f"{field} must be a list of names")
            elif allowed and any(x not in allowed for x in value):
                errors.append(f"{field} has a choice that is not an option: "
                              f"{', '.join(x for x in value if x not in allowed)}")
        elif field in _SWITCHES:
            if not isinstance(value, bool):
                errors.append(f"{field} must be true or false")
        elif not isinstance(value, str):
            errors.append(f"{field} must be text")
    unknown = sorted(set(values) - set(FORM_DEFAULTS))
    if unknown:
        errors.append(f"unknown fields: {', '.join(unknown)}")
    return errors


def record_from_form(day: date, today: date, values: dict, locations=(), tags=()) -> CheckInRecord:
    """The record to store, with meditation_done inferred from the minutes,
    or CheckInError naming every problem."""
    errors = problems(day, today, values, locations, tags)
    if errors:
        raise CheckInError(errors)
    return CheckInRecord(date=day.isoformat(),
                         **{field: values[field] for field in FORM_DEFAULTS},
                         meditation_done=meditation_done(values["meditation_minutes"]))


def save(repo, record: CheckInRecord, opened_entry: bool) -> None:
    """Store a check-in. `opened_entry`: the form opened the day's stored
    entry, so what it shows replaces it (fault F3). A form that could not
    read the entry opened at its defaults, and the save merges field by
    field, which never overwrites a real earlier reading with a default."""
    repo.save_check_in(record, replace=opened_entry)


# ─── The form, served (GET and PUT /api/checkin, rebuild Phase 2) ────────────

def options_lists() -> tuple[list[str], list[str]]:
    """The multi-select options: the anatomical locations and the sensation
    tags (training_constants)."""
    from training_constants import ANATOMICAL_LOCATIONS, SENSATION_TAGS
    return list(ANATOMICAL_LOCATIONS), list(SENSATION_TAGS)


def form_state(repo, day: date | None, today: date) -> dict:
    """What the check-in form shows for `day` (the caller's today without
    one): the days it can be saved for, whether the day already has an entry
    (and whether that read failed: a failed read opens at the defaults and
    the save then merges), the starting values, and every control's options
    and limits, so the phone draws the form from these and never holds a
    range of its own. CheckInError for a day outside the backfill window."""
    options = date_options(today)
    day = day or today
    if day not in options:
        raise CheckInError([f"the date {day.isoformat()} is not today or one of the "
                            f"{BACKFILL_DAYS} days before"])
    locations, tags = options_lists()
    read_failed = False
    try:
        existing = repo.get_check_in(day.isoformat())
    except Exception:
        existing, read_failed = None, True
    return {
        "date": day,
        "options": options,
        "is_today": day == today,
        "existing": existing is not None,
        "read_failed": read_failed,
        "values": initial_values(existing, locations, tags),
        "conditions": list(CONDITIONS),
        "whole": [{"field": f, "min": low, "max": high} for f, (low, high) in _WHOLE.items()],
        "decimal": [{"field": f, "min": low, "max": high, "step": DECIMAL_STEPS[f]}
                    for f, (low, high) in _DECIMAL.items()],
        "switches": list(_SWITCHES),
        "locations": locations,
        "tags": tags,
    }


def submit(repo, day: date, today: date, values: dict, opened_entry: bool) -> dict:
    """Validate and store a check-in (every field required, each in its
    control's limits), then return the form as the store now holds it.
    `opened_entry`: the form opened the day's stored entry, so what it sends
    replaces it (fault F3); otherwise the save merges field by field. One
    row per date, so the same request sent twice stores one entry.
    CheckInError names every problem; nothing is stored then."""
    from services import processing_queue
    locations, tags = options_lists()
    record = record_from_form(day, today, values, locations, tags)
    save(repo, record, opened_entry)
    processing_queue.parse_after_save(repo)     # the sensation note: parse on save (I63)
    return form_state(repo, day, today)
