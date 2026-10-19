"""The Metabolism screen's rules (move INS-2, rebuild Phase 2, 2026-10-19), so
the phone's Metabolism screen and the Streamlit page read one composition.

Two inventory faults are fixed here:

- F15: the readings come from the store (Repository.get_scale_readings and
  get_inbody_scans), never from a local CSV or a Python tuple, so the screen
  is not empty on a server.
- F11: a change is coloured by what is better for THAT measure: down for fat,
  up for fat-free mass and phase angle, down for ECW/TBW, and no judgement on
  weight, which is not a goal. Before, every rise was amber and every fall
  green. No card carries a "Normal" pill any more: it was printed on every
  derived value with no check behind it.

What each figure IS stays services/body_composition.py's subject: the scale
measures weight only, and every other scale figure is arithmetic on it
(body_composition.DERIVED_COLUMNS).
"""

from __future__ import annotations

from datetime import date

from services import body_composition as bc

#: label -> series key, unit, decimals, minimum axis span, source, and the
#: direction that is better: "down", "up", or None for no judgement.
METRICS: dict[str, dict] = {
    "Weight":           {"key": "weight", "unit": "kg", "dp": 1, "span": 2.0,
                         "src": "scale", "better": None},
    "Fat mass":         {"key": "fat", "unit": "kg", "dp": 1, "span": 1.5,
                         "src": "scale", "better": "down"},
    "Fat-free mass":    {"key": "ffm", "unit": "kg", "dp": 1, "span": 1.5,
                         "src": "scale", "better": "up"},
    "Body fat percent": {"key": "bf", "unit": "%", "dp": 1, "span": 1.5,
                         "src": "scale", "better": "down"},
    "Phase angle":      {"key": "phase", "unit": "°", "dp": 1, "span": 0.5,
                         "src": "inbody", "better": "up"},
    "ECW / TBW ratio":  {"key": "ecw", "unit": "", "dp": 3, "span": 0.008,
                         "src": "inbody", "better": "down"},
}

#: The progress chart's calendar periods, as (label, kind).
RANGES: tuple[tuple[str, str], ...] = (
    ("Week", "week"), ("Month", "month"), ("Year", "year"), ("All", "all"),
)


def read_data(repo, today: date) -> dict:
    """{"readings", "scans", "today", "load_error"}: every weigh-in oldest
    first, and the gym scans of the latest machine, each corrected to the true
    height (four of the five were run against a height 3-7 cm out, and height
    is squared inside InBody's first step).

    A failed read is carried as load_error and never shown as "no weigh-in on
    record": the two look the same once the list is empty, and only one of
    them is a real reading."""
    errors: list[str] = []
    try:
        readings = repo.get_scale_readings()
    except Exception as exc:
        readings = []
        errors.append(f"scale readings: {type(exc).__name__}: {exc}")
    try:
        scans = [s.at_height() for s in bc.latest_device_scans(repo.get_inbody_scans())]
    except Exception as exc:
        scans = []
        errors.append(f"gym scans: {type(exc).__name__}: {exc}")
    return {"readings": readings, "scans": scans, "today": today,
            "load_error": "; ".join(errors) or None}


def value(record, key: str) -> float | None:
    """One accessor for both record types, so a series does not need to know
    which device it came from."""
    if key == "weight":
        return getattr(record, "weight_kg", None)
    if key == "fat":
        return record.fat_mass_kg
    if key == "ffm":
        return record.fat_free_mass_kg
    if key == "bf":
        return record.body_fat_pct
    if key == "phase":
        return getattr(record, "phase_angle_deg", None)
    if key == "ecw":
        return getattr(record, "ecw_tbw", None)
    return None


def change_tone(change: float | None, better: str | None, dp: int) -> str | None:
    """How a change is coloured (fault F11): None without a change, "flat"
    under half the last printed decimal, "neutral" for a measure with no
    better direction, else "good" or "bad" by that measure's own direction."""
    if change is None:
        return None
    if abs(change) < 10 ** -dp / 2:
        return "flat"
    if better is None:
        return "neutral"
    return "good" if (change < 0) == (better == "down") else "bad"


def series(data: dict, label: str, kind: str, offset: int) -> dict:
    """One measure over one calendar window: the window and whether it can
    step back or on, the visible points, the runs that the chart draws as
    lines (a gap longer than the device's break is never bridged), the first
    and last visible points, the change between them (the change the chart
    draws, body_composition.window_change) and its tone."""
    metric = METRICS[label]
    readings, scans, today = data["readings"], data["scans"], data["today"]
    earliest = readings[0].day if readings else None
    window = bc.period_window(kind, offset, today, earliest)
    source = scans if metric["src"] == "inbody" else readings
    gap = bc.INBODY_GAP_BREAK_DAYS if metric["src"] == "inbody" else bc.SCALE_GAP_BREAK_DAYS
    visible = bc.readings_in(source, window)
    points = [(r.day, v) for r in visible if (v := value(r, metric["key"])) is not None]
    runs = [[(r.day, v) for r in run if (v := value(r, metric["key"])) is not None]
            for run in bc.split_runs(visible, gap)]
    change = bc.window_change([v for _d, v in points])
    return {
        "label": label, "metric": metric, "window": window,
        "can_back": bc.can_step(kind, offset, -1, today, earliest),
        "can_forward": bc.can_step(kind, offset, 1, today, earliest),
        "points": points, "runs": runs,
        "first": points[0] if points else None,
        "last": points[-1] if points else None,
        "change": change, "tone": change_tone(change, metric["better"], metric["dp"]),
    }


def split(reading) -> dict | None:
    """Fat against fat-free, which total the weight by construction (one
    number restated, never corroboration of it); None without a body fat."""
    if reading is None:
        return None
    fat, lean = reading.fat_mass_kg, reading.fat_free_mass_kg
    if fat is None or lean is None or fat + lean <= 0:
        return None
    total = fat + lean
    return {"fat": fat, "lean": lean, "total": total, "fat_pct": fat / total * 100}


def cellular(scans: list, today: date) -> dict | None:
    """The latest scan's height-immune pair (phase angle, ECW/TBW), its
    machine and its age in days; None without a scan."""
    if not scans:
        return None
    scan = scans[-1]
    return {"scan": scan, "device": scan.device, "days_old": (today - scan.day).days}


def _card(name: str, figure: float | None, dp: int, unit: str, source: str) -> dict:
    return {"name": name, "value": None if figure is None else round(figure, dp),
            "dp": dp, "unit": unit, "source": source}


def analysis(reading) -> list[dict]:
    """The body-analysis cards of one weigh-in, in groups. Each card says
    what it is: "measured" (weight), "derived" (arithmetic on the weight, see
    body_composition.DERIVED_COLUMNS) or "absent". No card carries a status:
    the "Normal" every derived card printed was no check (fault F11)."""
    if reading is None:
        return []
    weight, pct = reading.weight_kg, reading.body_fat_pct
    fat, lean = reading.fat_mass_kg, reading.fat_free_mass_kg
    mass = [_card("Weight", weight, 1, "kg", "measured"),
            _card("Body mass index", weight / bc.TRUE_HEIGHT_M ** 2, 1, "kg/m²", "derived")]
    groups = [{"group": "MASS", "blurb": "what the body is made of, in kilograms",
               "cards": mass}]
    if pct is None or fat is None or lean is None:
        return groups
    mass += [_card("Body fat", fat, 1, "kg", "derived"),
             _card("Body fat", pct, 1, "%", "derived"),
             _card("Fat-free mass", lean, 1, "kg", "derived"),
             _card("Bone mass", lean * 0.04994, 1, "kg", "derived")]
    groups += [
        {"group": "ENERGY", "blurb": "what it costs to run",
         "cards": [_card("Basal metabolic rate", 370 + 21.6 * lean, 0, "kcal", "derived")]},
        {"group": "WATER", "blurb": "how that mass is hydrated",
         "cards": [_card("Body water", 0.72201 * (100 - pct), 1, "%", "derived"),
                   _card("Protein", 0.22797 * (100 - pct), 1, "%", "derived")]},
        {"group": "RISK", "blurb": "what it implies",
         "cards": [_card("Visceral fat level", -2.8932 + 0.5927 * pct, 1, "", "derived"),
                   _card("Subcutaneous fat", pct - 2.25, 1, "%", "derived"),
                   _card("Waist circumference", None, 1, "cm", "absent"),
                   _card("Hip circumference", None, 1, "cm", "absent")]},
    ]
    return groups
