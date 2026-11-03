"""The muscle balance: which side of each pair is stronger, and by how much (WP-44).

The athlete, 2026-11-03: "Present the muscle imbalance with gym data mixed with
information provided and present it in a bar graph so that it shows where the
imbalance is going pecs stronger than back, hamstrings stronger than quads etc";
"if I can do 100kg row and 20kg press, it is clear there is an imbalance, Bar
Chart should show which side is stronger and which is weaker"; "both the data
from training and the seca profile should add to this metric". His answers the
same day: method "A", and "start with 5" pairs.

TWO KINDS OF PAIR.
- Two muscle groups on two different machines (chest and back, front and rear
  shoulder, quads and hamstrings). Kilograms on two machines do not compare, so
  each lift's estimated one-rep max is read against the published standard for
  that lift at his body weight (strength_standards.py: 100 = the Intermediate
  standard). The side further above its standard is the stronger side.
- The left and the right arm, the left and the right leg. Both sides do the same
  lift, so the training part is the left arm's one-rep max against the right
  arm's on every one-arm lift; the SECA part is the scan's muscle in each arm or
  leg (its "Segmentale Skelettmuskelmasse"). Both parts count equally ("both ...
  should add to this metric"), and a part with no data is left out, never zero.

A pair reads "about even" when its two sides are less than EVEN_PCT apart.

A LIFT UNDER THE BEGINNER STANDARD IS LEFT OUT and says why: for a man who
trains it is almost always a weight logged another way (one side of a
plate-loaded machine, plates without the sled, a stack number), and drawn it
would make the pair's difference several hundred percent. The machine
shoulder press was logged at 5-10 kg in October 2026, against a beginner
standard of 32 kg.

Pure logic: no I/O, no clock. The caller reads the log, the scans and the body
weight (insights_screens.strength).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from services import strength
from services import strength_standards as standards

#: Under this difference a pair reads "about even". 10% is the usual line for a
#: left-right difference in sport (a limb symmetry index of 90%).
EVEN_PCT = 10.0
#: A lift's newest session counts while it is this recent.
RECENT_DAYS = 56


@dataclass(frozen=True)
class MusclePair:
    key: str
    left: str
    right: str
    left_lifts: tuple[str, ...]
    right_lifts: tuple[str, ...]


@dataclass(frozen=True)
class SidePair:
    key: str
    left: str
    right: str
    region: str
    seca_left: str
    seca_right: str


#: The five pairs (his answer, 2026-11-03: "Ok start with 5"), in screen order.
MUSCLE_PAIRS: tuple[MusclePair, ...] = (
    MusclePair("chest_back", "Chest", "Back", ("Machine Chest Press",), ("Single-Arm DB Row",)),
    MusclePair("front_rear_shoulder", "Front shoulder", "Rear shoulder",
               ("Machine Shoulder Press",), ("Reverse Cable Crossover",)),
    MusclePair("quads_hamstrings", "Quads", "Hamstrings", ("Hack Squat",), ("Seated Leg Curl",)),
)
SIDE_PAIRS: tuple[SidePair, ...] = (
    SidePair("arms", "Left arm", "Right arm", "upper_body", "left_arm", "right_arm"),
    SidePair("legs", "Left leg", "Right leg", "lower_body", "left_leg", "right_leg"),
)


def standard_kg(name: str, body_weight_kg: float, level: str = standards.REFERENCE_LEVEL) -> float | None:
    """The lift's standard at this body weight, interpolated between the table's
    rows; the nearest row outside them. None for a lift with no standard."""
    entry = standards.STANDARDS.get(name)
    if entry is None or body_weight_kg is None:
        return None
    table = entry[1]
    column = standards.LEVELS.index(level)
    weights = sorted(table)
    if body_weight_kg <= weights[0]:
        return float(table[weights[0]][column])
    if body_weight_kg >= weights[-1]:
        return float(table[weights[-1]][column])
    for lo, hi in zip(weights, weights[1:]):
        if lo <= body_weight_kg <= hi:
            share = (body_weight_kg - lo) / (hi - lo)
            return table[lo][column] + share * (table[hi][column] - table[lo][column])
    return None


def _recent(rows: list[dict], today: date) -> list[dict]:
    out = []
    for row in rows:
        try:
            day = date.fromisoformat(str(row.get("session_date"))[:10])
        except ValueError:
            continue
        if 0 <= (today - day).days <= RECENT_DAYS:
            out.append(row)
    return out


def _left_set(s: dict) -> dict:
    """A set as the left side did it: stored only where it differs."""
    reps, weight = s.get("reps_left"), s.get("weight_left")
    return {**s, "reps": s.get("reps") if reps is None else reps,
            "weight": s.get("weight") if weight is None else weight}


def _difference(a: float, b: float) -> tuple[str | None, float]:
    """Which side is stronger ("left", "right", or None when about even) and
    by how many percent of the weaker side."""
    low, high = min(a, b), max(a, b)
    pct = (high / low - 1.0) * 100.0 if low > 0 else 0.0
    if pct < EVEN_PCT:
        return None, round(pct, 1)
    return ("left" if a > b else "right"), round(pct, 1)


def _row(key: str, left: str, right: str, a: float | None, b: float | None,
         parts: list[str]) -> dict:
    if a is None or b is None or a <= 0 or b <= 0:
        a = None if a is None else round(a, 1)
        b = None if b is None else round(b, 1)
        return {"key": key, "left": left, "right": right, "left_value": a, "right_value": b,
                "left_share": None, "stronger": None, "difference_pct": None,
                "words": f"Not enough data yet for {left.lower()} and {right.lower()}.",
                "parts": parts}
    stronger, pct = _difference(a, b)
    if stronger is None:
        words = f"About even: {pct:g}% apart."
    else:
        strong, weak = (left, right) if stronger == "left" else (right, left)
        words = f"{strong} is {pct:g}% stronger than {weak.lower()}."
    return {"key": key, "left": left, "right": right,
            "left_value": round(a, 1), "right_value": round(b, 1),
            "left_share": round(a / (a + b), 3), "stronger": stronger,
            "difference_pct": pct, "words": words, "parts": parts}


def muscle_pair(pair: MusclePair, observations: dict, body_weight_kg: float | None) -> dict:
    """One muscle pair from each lift's newest one-rep max (strength.best_observations),
    as a % of its standard at this body weight."""
    def side(lifts: tuple[str, ...]) -> tuple[float | None, list[str]]:
        scores, parts = [], []
        for name in lifts:
            obs = observations.get(name)
            std = standard_kg(name, body_weight_kg) if body_weight_kg else None
            if obs is None or not std:
                continue
            floor = standard_kg(name, body_weight_kg, standards.LEVELS[0])
            if floor and obs.e1rm < floor:
                parts.append(f"{name}: one-rep max about {obs.e1rm:.0f} kg, under the beginner "
                             f"standard ({floor:.0f} kg), so left out: check how this "
                             "machine's weight is logged")
                continue
            score = obs.e1rm / std * 100.0
            scores.append(score)
            parts.append(f"{name}: one-rep max about {obs.e1rm:.0f} kg, {score:.0f}% of the standard")
        return (sum(scores) / len(scores) if scores else None), parts

    a, left_parts = side(pair.left_lifts)
    b, right_parts = side(pair.right_lifts)
    return _row(pair.key, pair.left, pair.right, a, b, left_parts + right_parts)


def training_side_ratio(rows: list[dict], one_arm: set[str], region_of: dict[str, str],
                        region: str, pr_rir: float = 1.0) -> tuple[float | None, list[str]]:
    """The left side against the right on the one-sided lifts of a body area:
    each lift's newest session, the best one-rep max of each side, and the mean
    of the left/right ratios over the lifts. None without a loaded one-sided
    lift."""
    newest: dict[str, dict] = {}
    for row in rows:
        name = row.get("movement_name")
        if name not in one_arm or region_of.get(name) != region:
            continue
        if name not in newest or str(row.get("session_date")) > str(newest[name].get("session_date")):
            newest[name] = row
    ratios, parts = [], []
    rpe = 10.0 - pr_rir
    for name in sorted(newest):
        work = [s for s in newest[name].get("sets") or []
                if not s.get("is_warmup") and (s.get("reps") or 0)]

        def best(sets: list[dict]) -> float:
            values = [strength.estimated_1rm(float(s.get("weight") or 0), float(s.get("reps") or 0), rpe)[0]
                      for s in sets if (s.get("weight") or 0) and (s.get("reps") or 0)]
            return max(values) if values else 0.0

        right, left = best(work), best([_left_set(s) for s in work])
        if right <= 0 or left <= 0:
            continue
        ratios.append(left / right)
        parts.append(f"{name}: left {left / right * 100:.0f}% of right")
    return (sum(ratios) / len(ratios) if ratios else None), parts


def side_pair(pair: SidePair, rows: list[dict], one_arm: set[str], region_of: dict[str, str],
              seca_segments: dict[str, float] | None, pr_rir: float = 1.0) -> dict:
    """One left-right pair: the training ratio and the SECA ratio, each counted
    equally, as a left and a right value around 100."""
    ratios, parts = [], []
    trained, trained_parts = training_side_ratio(rows, one_arm, region_of, pair.region, pr_rir)
    if trained is not None:
        ratios.append(trained)
        parts.extend(trained_parts)
    seg = seca_segments or {}
    left_kg, right_kg = seg.get(pair.seca_left), seg.get(pair.seca_right)
    if left_kg and right_kg:
        ratios.append(left_kg / right_kg)
        parts.append(f"SECA scan: muscle left {left_kg:g} kg, right {right_kg:g} kg")
    if not ratios:
        return _row(pair.key, pair.left, pair.right, None, None, parts)
    ratio = sum(ratios) / len(ratios)
    return _row(pair.key, pair.left, pair.right, 100.0 * ratio, 100.0, parts)


def balance(rows: list[dict], *, today: date, body_weight_kg: float | None,
            seca_segments: dict[str, float] | None, one_arm: set[str],
            region_of: dict[str, str], pr_rir: float = 1.0) -> dict:
    """The five pairs, in screen order, and how they were read.

    `rows` is the training log in kilograms (strength_screen.kilogram_rows),
    `one_arm` the names of the one-arm lifts (sessions.exercise_traits), and
    `region_of` training_constants.EXERCISE_BODY_REGION."""
    recent = _recent(rows, today)
    observations = strength.best_observations(recent, today=today, pr_rir=pr_rir)
    pairs = [muscle_pair(p, observations, body_weight_kg) for p in MUSCLE_PAIRS]
    pairs += [side_pair(p, recent, one_arm, region_of, seca_segments, pr_rir) for p in SIDE_PAIRS]
    return {
        "pairs": pairs,
        "body_weight_kg": None if body_weight_kg is None else round(body_weight_kg, 1),
        "method": ("Two muscle groups: each lift's one-rep max against the published standard "
                   f"for that lift at your body weight ({standards.SOURCE}; 100 = "
                   f"{standards.REFERENCE_LEVEL.lower()}). Machines differ from gym to gym. "
                   "Left and right: your one-arm lifts and the SECA scan's muscle, counted "
                   f"equally. Under {EVEN_PCT:g}% apart reads as about even."),
    }
