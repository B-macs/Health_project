"""
services/tonnage.py — weekly training tonnage, split by primary body sector.

Pure functions. No I/O, no Streamlit, explicit `today`.

    exercise tonnage = load x reps x completed sets
                     = sum over completed sets of (load x reps)

The second form is what the per-set log actually supports, and it is identical
to the first whenever the sets are uniform (3 x 10 x 40 kg = 1,200 kg either
way). Summing per set means a top set at a different weight is not silently
rounded into the others.

    weekly tonnage[r] = sum of eligible loaded sets in sector r, Mon-Sun
    overall           = upper_body + core + lower_body

ELIGIBILITY, stated honestly. A set counts when it carries both reps and a real
external load. Warm-ups are NOT excluded, because the log has no way to mark
one — there is no per-set warm-up flag today, so "working sets only" is an
assumption, not something this module can enforce. Every unloaded rehab drill
falls out naturally, since its sets carry no weight.

UNLOADED WORK IS COUNTED IN ITS OWN UNITS AND NEVER CONVERTED. Dead bugs,
planks, bird-dogs, side bridges and glute bridges produce real training and zero
kilograms. There is no defined bodyweight-to-kg conversion here and inventing
one would put fictional weight into a real total, so they are carried alongside
instead — which is also what stops a week of genuine rehab work from displaying
as though nothing happened.

That takes TWO counters, not one. services/sessions.py encodes a hold or a
timed exercise as **reps=1 with the work in `tut`** (seconds), so a 60-second
plank and a single dead bug are both "1 rep". Summing reps alone therefore
misrepresents exactly the work it was added to represent: across
training_plan.PLAN, holds and durations are 54 of 113 exercises and 11,955
seconds of time-under-tension but only 113 of 1,603 reps — 7%. `unloaded_reps`
and `unloaded_seconds` are kept separate and are never added together, because
a rep and a second are not the same unit and no exchange rate between them is
defined here either.

ONE PRIMARY SECTOR PER EXERCISE, from training_constants.EXERCISE_BODY_REGION.
A compound lift's WHOLE tonnage goes to its primary sector — a Romanian
deadlift is not split between lower body and core. That is what makes
`upper + core + lower == overall` an identity rather than an approximation.
An exercise missing from the map contributes to nothing and is reported in
`unmapped` rather than being silently dropped.

NO DECAY, EVER. Unlike the Overall Strength Score (services/strength.py),
tonnage is a statement about one week and nothing else. A week with no eligible
loaded work is 0 kg, which is true rather than alarming, and it says nothing at
all about strength.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

REGIONS: tuple[str, ...] = ("upper_body", "core", "lower_body")


@dataclass(frozen=True)
class SectorWeek:
    kg: float = 0.0
    sets: int = 0
    sessions: int = 0
    unloaded_reps: float = 0.0
    # Held/timed work, in seconds. Separate from unloaded_reps on purpose —
    # see the module docstring. Never add the two.
    unloaded_seconds: float = 0.0


@dataclass(frozen=True)
class TonnageWeek:
    week_start: date
    training_days: int
    sectors: dict[str, SectorWeek] = field(default_factory=dict)

    @property
    def overall(self) -> SectorWeek:
        return SectorWeek(
            kg=sum(s.kg for s in self.sectors.values()),
            sets=sum(s.sets for s in self.sectors.values()),
            sessions=self.training_days,
            unloaded_reps=sum(s.unloaded_reps for s in self.sectors.values()),
            unloaded_seconds=sum(s.unloaded_seconds for s in self.sectors.values()),
        )

    def value(self, key: str) -> SectorWeek:
        """`key` is a sector name or "overall"."""
        if key == "overall":
            return self.overall
        return self.sectors.get(key, SectorWeek())


def week_start(day: date) -> date:
    """Monday of the week `day` falls in."""
    return day - timedelta(days=day.weekday())


def weekly_tonnage(
    rows: list[dict],
    region_map: dict[str, str],
    today: date | None = None,
    weeks: int = 8,
) -> tuple[list[TonnageWeek], set[str]]:
    """`weeks` consecutive calendar weeks ending with the one containing
    `today`, so a week with no training is present and reads zero rather than
    being absent from the series.

    `rows` is Repository.get_all_training_exercises_raw()'s shape. Returns
    (series, unmapped_exercise_names)."""
    today = today or date.today()
    last = week_start(today)
    span = [last - timedelta(weeks=n) for n in range(weeks - 1, -1, -1)]
    first = span[0]

    kg: dict[date, dict[str, float]] = {w: {r: 0.0 for r in REGIONS} for w in span}
    sets: dict[date, dict[str, int]] = {w: {r: 0 for r in REGIONS} for w in span}
    unloaded: dict[date, dict[str, float]] = {w: {r: 0.0 for r in REGIONS} for w in span}
    held: dict[date, dict[str, float]] = {w: {r: 0.0 for r in REGIONS} for w in span}
    sector_days: dict[date, dict[str, set[str]]] = {w: {r: set() for r in REGIONS} for w in span}
    all_days: dict[date, set[str]] = {w: set() for w in span}
    unmapped: set[str] = set()

    for row in rows:
        name = row.get("movement_name")
        raw_date = row.get("session_date")
        if not name or not raw_date:
            continue
        try:
            day = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            continue
        if day > today:
            continue
        wk = week_start(day)
        if wk < first or wk > last:
            continue

        region = region_map.get(name)
        if region not in REGIONS:
            # Not an error: the log contains non-exercise rows (a written
            # self-assessment, for one). Reported so a genuinely missing
            # mapping is visible rather than silently zeroing a sector.
            unmapped.add(name)
            continue

        all_days[wk].add(raw_date)
        loaded_kg, loaded_sets, reps_only, seconds_only = 0.0, 0, 0.0, 0.0
        for s in (row.get("sets") or []):
            reps = float(s.get("reps") or 0)
            weight = float(s.get("weight") or 0)
            tut = float(s.get("tut") or 0)
            if reps and weight:
                loaded_kg += reps * weight
                loaded_sets += 1
            elif tut:
                # A hold or a timed piece: sessions.py writes reps=1 and puts
                # the actual work in tut. Counting its "1 rep" would hide it.
                seconds_only += tut
            elif reps:
                reps_only += reps
        if loaded_kg:
            kg[wk][region] += loaded_kg
            sets[wk][region] += loaded_sets
            sector_days[wk][region].add(raw_date)
        if reps_only:
            unloaded[wk][region] += reps_only
        if seconds_only:
            held[wk][region] += seconds_only

    series = [
        TonnageWeek(
            week_start=w,
            training_days=len(all_days[w]),
            sectors={
                r: SectorWeek(
                    kg=round(kg[w][r], 1),
                    sets=sets[w][r],
                    sessions=len(sector_days[w][r]),
                    unloaded_reps=round(unloaded[w][r], 1),
                    unloaded_seconds=round(held[w][r], 1),
                )
                for r in REGIONS
            },
        )
        for w in span
    ]
    return series, unmapped


def change(current: float, previous: float) -> tuple[float, float | None]:
    """(absolute, percent) week over week. Percent is None when the previous
    week was zero — a rise from nothing is not a percentage, and printing one
    would be a division-by-zero dressed up as a number."""
    delta = current - previous
    if previous == 0:
        return delta, None
    return delta, delta / previous * 100.0


def nice_axis_max(peak: float, divisions: int = 4) -> float:
    """An axis top that is `divisions` clean steps above `peak`, so core's
    225 kg and lower body's 2,775 kg each get a readable axis of their own.

    That the two then look alike at a glance is precisely why kilograms are
    never compared across sectors anywhere else — the axis label is the only
    thing carrying the scale.

    The step is forced to a WHOLE number of kilograms. The candidate ladder
    contains 1.5, 2.5 and 7.5, which are fine at scale (750, 2,500) but at a
    small peak produce fractional gridlines that the integer kg formatter then
    prints wrong: a 25 kg core week gave a top of 30 with lines at
    30/22.5/15/7.5/0 and labels reading 30/22/15/8/0. Rounding the step up
    keeps the axis above the peak, so the fix cannot hide data."""
    if peak <= 0:
        return float(divisions * 25)
    target = peak / divisions
    exponent = 10 ** (len(str(int(target))) - 1) if target >= 1 else 1
    while exponent * 10 <= target:
        exponent *= 10
    for candidate in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 7.5, 10):
        step = candidate * exponent
        if step >= target - 1e-9:
            return math.ceil(step) * divisions
    return math.ceil(exponent * 10) * divisions
