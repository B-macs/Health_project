"""
services/body_composition.py — weight, and what can honestly be said about its split.

Pure functions only. No I/O, no Streamlit, no hidden clock reads — every
date-dependent function takes an explicit `today`, same convention as
services/engine.py and services/strength.py.

WHAT THE TWO DEVICES ACTUALLY MEASURE
-------------------------------------
Measured 2026-08-04/05 against the real exports, not assumed:

*Foryond foot-only scale* (`Input_files/Fitdays-Brian.csv`, 142 scans,
2024-06-07 -> 2026-08-03). Fourteen columns, ONE of which a sensor produced:
weight. Its body fat percent is itself predicted by weight and age at
R^2 0.9966 with a residual scatter of 0.051 pp against the 0.1 pp step it
prints — and it read 78.8 kg on three occasions across 111 days and printed
16.0% every time. Everything else is algebra on that:

    BMI                = weight / height^2
    fat-free mass      = weight * (1 - body_fat_pct/100)
    fat mass           = weight - fat-free mass
    bone mass          = 0.04994 * fat-free mass
    muscle mass        = fat-free mass - bone mass
    BMR                = 370 + 21.6 * fat-free mass        (Katch-McArdle)
    body water %       = 0.72201 * fat-free %
    protein %          = 0.22797 * fat-free %
    skeletal muscle %  = 77.80 - BMI
    subcutaneous fat % = body_fat_pct - 2.25
    visceral level     = -2.8932 + 0.5927 * body_fat_pct
    "body age"         = -20.73 + 1.226*body_fat_pct + 0.900*chronological age

None of those is stored by this module. They are listed so that a future reader
who finds them on the device's screen knows they are restatements of one number
and not corroboration of it. `DERIVED_COLUMNS` carries the same list in a form
tests can assert against.

*InBody 770 at the gym* (five scans, 2025-01-13 -> 2025-06-27). Genuinely
measures segmental impedance, and reports two quantities nothing else here can:
PHASE_ANGLE and the ECW/TBW ratio. Both are quotients of directly measured
values, so neither depends on the height typed at the console — which is the
only reason they survived what follows.

THE HEIGHT DEFECT, AND WHY `at_height` EXISTS
---------------------------------------------
InBody estimates total body water from height^2 / resistance, then defines
fat-free mass as TBW / TBW_FFM_FRACTION and fat as the remainder. Height is
therefore squared inside the FIRST step and contaminates every kilogram
downstream, at a measured -0.89 pp of body fat per centimetre.

The gym typed a different height on four of the five scans: 185.5, 175.1,
174.9, 181.6, 181.8 cm against a true 182.0. Two scans EIGHT MINUTES APART on
2025-05-21 differ by 6.0 pp of body fat and 2.9 kg of skeletal muscle at an
identical 79.5 kg, because the height was corrected between them. Phase angle
read 6.1 on both; ECW/TBW read 0.377 on both.

`at_height` re-runs a scan through the device's own chain at the true height.
It is a correction, NOT a dismissal: recomputed at 182 cm the eight-minute pair
agrees to 0.31 pp, and the five-scan spread falls from 8.2 pp to 4.64 pp —
leaving 4.6 pp of real change that no height exponent between 0 and 6 removes.

WHAT THIS MODULE REFUSES TO DO
------------------------------
No fused "true body fat percent" blending the two devices. The scale
contributes no composition information, so fusing adds a term with no signal
and would make the result look more certain than the InBody alone. No body
composition expressed as an age in years — the scale already ships one and it
is age predicting age. Both refusals are the lesson of the Stage-Adjusted
Recovery Score (see services/bioage.py) and readiness MODEL_VERSION 1: a
plausible formula over inputs too weak to carry it.
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

# ── measured constants ───────────────────────────────────────────────────────

#: True standing height, confirmed 2026-08-05. The Foryond was set to 183.0 and
#: corrected on that date; the gym's entries ranged 174.9-185.5.
TRUE_HEIGHT_M: float = 1.820

#: InBody defines fat-free mass as total body water divided by this. The sheet
#: prints the ratio rounded to 73.4%, but recovering it from each scan's printed
#: water and fat-free mass gives 0.73427, 0.73516, 0.73428, 0.73392, 0.73487 —
#: mean 0.73450, sd 0.00045. The rounded 0.734 overstates fat-free mass by ~0.05
#: kg and pushes the derived BMR 1.8 kcal past what the device prints, so the
#: measured mean is used instead.
TBW_FFM_FRACTION: float = 0.73450

#: Body fat percentage moved per centimetre of entered height, measured from the
#: 2025-05-21 pair (6.8 cm apart, 6.0 pp apart).
BODY_FAT_PP_PER_CM: float = -0.89

#: Repeat error from the 100 consecutive Foryond scans <= 2 days apart. This is
#: an UPPER bound on instrument error: it contains one to two days of real
#: fluctuation as well.
WEIGHT_REPEAT_SD_KG: float = 0.441

#: Longest gap that may be drawn as a continuous line, per device. The scale is
#: near-daily so three weeks of silence is a real absence; the InBody runs every
#: month or two, so the same rule would leave five scans as five isolated dots.
SCALE_GAP_BREAK_DAYS: int = 21
INBODY_GAP_BREAK_DAYS: int = 120

#: Every Foryond column that is arithmetic on weight (plus, for body fat percent,
#: the calendar). Name -> one-line statement of what it really is.
DERIVED_COLUMNS: dict[str, str] = {
    "bmi": "weight / height^2",
    "body_fat_pct": "-23.68 + 0.4570*weight + 0.1202*age, R^2 0.9966",
    "fat_mass_kg": "weight * body_fat_pct",
    "fat_free_mass_kg": "weight - fat mass",
    "bone_mass_kg": "0.04994 * fat-free mass",
    "muscle_mass_kg": "fat-free mass - bone mass",
    "bmr_kcal": "370 + 21.6 * fat-free mass (Katch-McArdle)",
    "body_water_pct": "0.72201 * fat-free percent",
    "protein_pct": "0.22797 * fat-free percent",
    "skeletal_muscle_pct": "77.80 - BMI",
    "subcutaneous_fat_pct": "body_fat_pct - 2.25",
    "visceral_level": "-2.8932 + 0.5927 * body_fat_pct",
    "body_age_years": "-20.73 + 1.226*body_fat_pct + 0.900*chronological age",
}

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_FITDAYS_DATE = re.compile(r"(\d{2}):(\d{2})\s+([A-Za-z]{3})\.(\d{2})\s+(\d{4})")


# ── models ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScaleReading:
    """One Foryond weigh-in. Only `weight_kg` is a measurement.

    `body_fat_pct` is kept as the device PRINTED it — not because it is
    independent evidence, but because a firmware change could alter the vendor's
    fit and the record of what it actually said is worth having.
    """

    taken_at: datetime
    weight_kg: float
    bmi: float | None = None
    body_fat_pct: float | None = None

    @property
    def day(self) -> date:
        return self.taken_at.date()

    @property
    def fat_mass_kg(self) -> float | None:
        if self.body_fat_pct is None:
            return None
        return self.weight_kg * self.body_fat_pct / 100.0

    @property
    def fat_free_mass_kg(self) -> float | None:
        fat = self.fat_mass_kg
        return None if fat is None else self.weight_kg - fat

    @property
    def implied_height_m(self) -> float | None:
        """The height the device divided by, recovered from weight and BMI.

        This is how the Foryond's 183.0 cm setting and the gym's five different
        entries were found; a change in it is a settings change, never a body.
        """
        if not self.bmi:
            return None
        return math.sqrt(self.weight_kg / self.bmi)


@dataclass(frozen=True)
class InBodyScan:
    """One InBody 770 scan.

    `phase_angle_deg` and `ecw_tbw` are the height-immune pair — quotients of
    directly measured quantities. Everything else on this record inherits
    whatever height was typed at the console; call `at_height` before trusting
    any of it.
    """

    taken_at: datetime
    weight_kg: float
    bmi: float
    total_body_water_l: float
    skeletal_muscle_kg: float
    ecw_tbw: float
    phase_angle_deg: float | None = None
    note: str = ""

    @property
    def day(self) -> date:
        return self.taken_at.date()

    @property
    def entered_height_m(self) -> float:
        return math.sqrt(self.weight_kg / self.bmi)

    @property
    def fat_free_mass_kg(self) -> float:
        return self.total_body_water_l / TBW_FFM_FRACTION

    @property
    def fat_mass_kg(self) -> float:
        return self.weight_kg - self.fat_free_mass_kg

    @property
    def body_fat_pct(self) -> float:
        return self.fat_mass_kg / self.weight_kg * 100.0

    @property
    def bmr_kcal(self) -> float:
        """Katch-McArdle, which is what the device prints — verified to the
        kilocalorie on all five scans."""
        return 370.0 + 21.6 * self.fat_free_mass_kg

    def height_error_cm(self, true_height_m: float = TRUE_HEIGHT_M) -> float:
        return (self.entered_height_m - true_height_m) * 100.0

    def at_height(self, true_height_m: float = TRUE_HEIGHT_M) -> "InBodyScan":
        """Re-run this scan through the device's own chain at the true height.

        Total body water scales as height^2 at fixed impedance, so the whole
        correction is one factor. Weight is untouched — it was measured. The
        eight-minute pair of 2025-05-21 goes from 6.0 pp apart to 0.31 pp under
        this transform, which is the evidence that the transform is right.
        """
        scale = (true_height_m / self.entered_height_m) ** 2
        return replace(
            self,
            bmi=self.weight_kg / (true_height_m ** 2),
            total_body_water_l=self.total_body_water_l * scale,
            skeletal_muscle_kg=self.skeletal_muscle_kg * scale,
        )


@dataclass(frozen=True)
class Window:
    """A calendar-aligned period. `start` and `end` are both inclusive."""

    kind: str
    offset: int
    start: date
    end: date
    label: str
    sub: str

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


# ── parsing ──────────────────────────────────────────────────────────────────

def _number(raw: str | None) -> float | None:
    """Pull the leading number out of '82.2kg', '17.6%', '1833kcal'. '--' is
    the export's empty cell and becomes None, as does a blank."""
    if raw is None:
        return None
    text = raw.strip()
    if text in ("", "--"):
        return None
    match = re.match(r"^(-?[\d.]+)", text)
    return float(match.group(1)) if match else None


def parse_fitdays_csv(text: str) -> list[ScaleReading]:
    """Parse a Fitdays export into readings, oldest first.

    Only the three columns worth keeping are read. Rows whose timestamp does not
    parse are skipped rather than raising: a partial export is more useful than
    an exception, and a malformed row is not a reason to lose 141 good ones.
    """
    out: list[ScaleReading] = []
    for row in csv.DictReader(io.StringIO(text)):
        match = _FITDAYS_DATE.match((row.get("Date") or "").strip())
        if not match:
            continue
        hour, minute, mon, day, year = match.groups()
        if mon not in _MONTHS:
            continue
        weight = _number(row.get("Weight"))
        if weight is None:
            continue
        out.append(ScaleReading(
            taken_at=datetime(int(year), _MONTHS[mon], int(day), int(hour), int(minute)),
            weight_kg=weight,
            bmi=_number(row.get("BMI")),
            body_fat_pct=_number(row.get("Body Fat")),
        ))
    out.sort(key=lambda r: r.taken_at)
    return dedupe_readings(out)


def dedupe_readings(readings: list[ScaleReading]) -> list[ScaleReading]:
    """Collapse readings that share a timestamp to the last one seen.

    The export really does contain same-minute duplicates — 2024-06-19 09:00
    appears twice, as do 2024-07-18 08:51 and 2025-05-17 08:15. Summing or
    averaging over them would double-count a single weigh-in, the same trap
    `biometrics.dedupe_sleep_periods` exists for on the Oura side.
    """
    by_stamp: dict[datetime, ScaleReading] = {}
    for reading in readings:
        by_stamp[reading.taken_at] = reading
    return [by_stamp[k] for k in sorted(by_stamp)]


# ── windows ──────────────────────────────────────────────────────────────────

def _fmt_day(day: date) -> str:
    return f"{day.day} {_MONTH_LABELS[day.month - 1]} {day.year}"


def period_window(kind: str, offset: int, today: date,
                  earliest: date | None = None) -> Window:
    """A calendar-aligned window: 'week' (Mon-Sun), 'month', 'year' or 'all'.

    `offset` 0 is the period containing `today`; -1 is the one before it.
    Calendar alignment rather than a rolling look-back is deliberate — "July
    2026" is a period you can name and return to, "the last 30 days" is not.
    """
    if kind == "all":
        start = earliest or today
        return Window("all", 0, start, today,
                      f"{_MONTH_LABELS[start.month - 1]} {start.year} – "
                      f"{_MONTH_LABELS[today.month - 1]} {today.year}",
                      "every reading")

    if kind == "year":
        year = today.year + offset
        return Window("year", offset, date(year, 1, 1), date(year, 12, 31),
                      str(year), "calendar year")

    if kind == "month":
        index = today.year * 12 + (today.month - 1) + offset
        year, month = divmod(index, 12)
        start = date(year, month + 1, 1)
        end = date(year + (month == 11), (month + 1) % 12 + 1, 1) - timedelta(days=1)
        return Window("month", offset, start, end,
                      f"{_MONTH_LABELS[month]} {year}", "calendar month")

    if kind == "week":
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        end = start + timedelta(days=6)
        return Window("week", offset, start, end,
                      f"{_fmt_day(start)} – {_fmt_day(end)}", "Mon–Sun")

    raise ValueError(f"unknown period kind: {kind!r}")


def can_step(kind: str, offset: int, direction: int, today: date,
             earliest: date | None = None) -> bool:
    """Whether the period selector may move by `direction` (-1 back, +1 on).

    Forward stops at the period containing today; backward stops once the window
    no longer reaches any data, so the arrows cannot walk off into empty years.
    """
    if kind == "all" or direction == 0:
        return False
    if direction > 0:
        return offset + direction <= 0
    if earliest is None:
        return True
    return period_window(kind, offset + direction, today, earliest).end >= earliest


def readings_in(readings: list, window: Window) -> list:
    """Every reading whose calendar day falls inside the window, order kept."""
    return [r for r in readings if window.contains(r.day)]


def window_change(values: list[float]) -> float | None:
    """Last minus first across what is visible. None if fewer than two.

    The change on screen must be the change the chart draws, or the number and
    the picture disagree — which is how a reader learns to trust neither.
    """
    if len(values) < 2:
        return None
    return values[-1] - values[0]


def split_runs(readings: list, gap_days: int) -> list[list]:
    """Split into runs so a gap longer than `gap_days` is never interpolated.

    The 97-day hole between 2025-10-21 and 2026-01-27 is what this exists for:
    it is the index back injury, and a line drawn across it invents 4.4 kg of
    change that was never observed.
    """
    runs: list[list] = []
    current: list = []
    for i, reading in enumerate(readings):
        if i and (reading.day - readings[i - 1].day).days > gap_days:
            runs.append(current)
            current = []
        current.append(reading)
    if current:
        runs.append(current)
    return runs
