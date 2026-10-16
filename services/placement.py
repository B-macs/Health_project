"""Placement — put every exercise of the week on a day and in its place.

The athlete, 2026-10-16: "Can you bring understand each the exercise and create
a deterministic test to put them automatically in their correct position?", and
then "Make a session C and D and balance it out". The rules are step 6 of
docs/training/goal_system.md; this module is their code. Nothing is placed by
hand: the same cards always give the same week.

THE WEEK. Four full-body sessions, A to D, one per strength day. Each card says
how many days it runs (its areas' weekly minimums decide that) and every
appearance is 3 working sets.

THE RULES, in the order they run:

  P1  Fixed placements first: a card with ``fixed_days`` goes on those days
      (the press block — release, Y raise, both presses — on two days not in a
      row; the warm-up every day; the neck on its three days).
  P2  A rotating group (the abs) takes one card a day, in card order.
  P3  A pattern with as many appearances as there are days (the knee lifts,
      the hip lifts) takes one appearance a day.
  P4  A card never falls on two days in a row when the week leaves a choice
      that avoids it.
  P5  The other cards, high demand first and then in card order, each go on
      the allowed days that give their area the most NEW days, then the least
      modelled time so far; a tie goes to the earlier days.
  P6  Balance: move one card to another allowed set of days while that lowers
      the longest session without leaving an area on too few days; stop when
      no move helps. Cards are tried in card
      order and day sets in day order.
  P8  The bonus session (``fill_bonus``): one more appearance of each exercise
      in the drop order while it stays within the target, never a heavy lift
      from the day before.
  P7  Inside a day: warm-up; then the lifts — compound before isolation, high
      demand first, priority 1 first, the same station together, then the
      name; the press block straight before the first press; trunk work and
      holds last. A ramp set goes straight before its own lift.

THE CHECKS (``violations``): every area at or above its weekly minimum and on
2 or more days; no area over SESSION_AREA_CAP hard sets in one session; no
session over SESSION_MINUTES_LIMIT modelled minutes (services/sessions'
measured time model). ``over_target`` lists the sessions over
SESSION_MINUTES_TARGET: the aim, not a limit. Counting: 1 set for a card's area, 0.5 for its second
area; warm-up items and ramp sets count nothing.

No I/O and no Streamlit, like the rest of services/.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace

from services import sessions

#: Approved 2026-10-15/16: about 6-8 hard sets per muscle in a session, and the
#: 70-minute limit that replaced Key Rule 21's six-exercise cap for full-body days.
#: The athlete, 2026-10-16: "70min is the Max, 60min is the target Not 70 the
#: target" — over 70 breaks the week; over 60 is reported, not refused.
SESSION_AREA_CAP = 8
SESSION_MINUTES_LIMIT = 70
SESSION_MINUTES_TARGET = 60
WORKING_SETS = 3


@dataclass(frozen=True)
class Card:
    """One exercise as the placement sees it."""
    name: str
    area: str | None = None            # counts 1 a set; None for warm-up items
    second: str | None = None          # counts 0.5 a set
    sets: int = WORKING_SETS
    type: str = "reps"                 # reps | hold | hold_reps
    reps: int | None = 10
    hold_seconds: int | None = None
    reps_in_set: int | None = None
    rest_seconds: int = 90
    equipment_type: str | None = None  # machine | cable | dumbbell | None (floor)
    laterality: str = "bilateral"
    kind: str = "isolation"            # compound | isolation
    demand: int = 1                    # 3 high .. 1 low
    priority: int = 2                  # 1 for goal A's priority areas
    section: str = "main"              # warmup | block | main | last
    days: int = 2                      # how many days a week it runs
    fixed_days: tuple[str, ...] = ()
    pattern: str = ""                  # P3: one appearance a day for a full pattern
    rotation: str = ""                 # P2: one card of the group a day
    ramp: bool = False
    is_press: bool = False


@dataclass(frozen=True)
class WeekSpec:
    days: tuple[str, ...]                          # the strength days, in order
    in_a_row: frozenset = field(default_factory=frozenset)   # pairs of days in a row
    minimums: dict = field(default_factory=dict)   # area -> weekly hard sets
    min_days: dict = field(default_factory=dict)   # area -> days it must be trained (default 2)


def exercise_dict(card: Card) -> dict:
    """The shape services/sessions.session_seconds reads."""
    return {"name": card.name, "type": card.type, "sets": card.sets, "reps": card.reps,
            "hold_seconds": card.hold_seconds, "reps_in_set": card.reps_in_set,
            "rest_seconds": card.rest_seconds, "equipment_type": card.equipment_type,
            "laterality": card.laterality}


def _ramp_for(card: Card) -> Card:
    return replace(card, name=f"{sessions.base_name(card.name)} {sessions.RAMP_SUFFIX}", sets=1, reps=6,
                   rest_seconds=60, area=None, second=None, ramp=False)


def order(items: list[Card]) -> list[Card]:
    """P7. The order of one session, ramp sets included."""
    warmup = [c for c in items if c.section == "warmup"]
    block = [c for c in items if c.section == "block"]
    last = [c for c in items if c.section == "last"]
    main = sorted((c for c in items if c.section == "main" or (c.section == "block" and c.is_press)),
                  key=lambda c: (0 if c.kind == "compound" else 1, -c.demand, c.priority,
                                 c.equipment_type or "floor", c.name))
    pre_press = [c for c in block if not c.is_press]
    if pre_press:
        first = next((i for i, c in enumerate(main) if c.is_press), len(main))
        main = main[:first] + pre_press + main[first:]
    out: list[Card] = []
    for c in warmup + main + last:
        if c.ramp:
            out.append(_ramp_for(c))
        out.append(c)
    return out


def minutes(items: list[Card]) -> float:
    return sessions.session_seconds([exercise_dict(c) for c in order(items)]) / 60


def _has_a_row(combo: tuple[str, ...], spec: WeekSpec) -> bool:
    return any(pair in spec.in_a_row for pair in itertools.combinations(combo, 2))


def _row_free_exists(n: int, spec: WeekSpec) -> bool:
    """Whether n days can be chosen with no two in a row. With Mon, Tue, Thu,
    Fri, two can and three cannot; with Mon, Tue, Thu, two can."""
    return any(not _has_a_row(c, spec) for c in itertools.combinations(spec.days, n))


def _allowed(card: Card, combo: tuple[str, ...], week: dict, spec: WeekSpec) -> bool:
    # P4 binds whenever the week leaves a choice with no two days in a row.
    if _has_a_row(combo, spec) and _row_free_exists(len(combo), spec):
        return False
    if card.pattern and any(any(c.pattern == card.pattern for c in week[d]) for d in combo):
        return False
    return not any(card in week[d] for d in combo)


def _area_days(week: dict) -> dict[str, set]:
    out: dict[str, set] = {}
    for d, items in week.items():
        for area in hard_sets(items):
            out.setdefault(area, set()).add(d)
    return out


def _short_areas(week: dict, spec: WeekSpec) -> set:
    """Areas of the minimums trained on fewer days than they need."""
    days = _area_days(week)
    return {a for a in spec.minimums if len(days.get(a, ())) < spec.min_days.get(a, 2)}


def _new_days(card: Card, combo: tuple[str, ...], week: dict) -> int:
    """How many of `combo` would be a new day for the card's own area."""
    if not card.area:
        return 0
    have = _area_days(week).get(card.area, set())
    return sum(1 for d in combo if d not in have)


def place(cards: list[Card], spec: WeekSpec) -> dict[str, list[Card]]:
    """P1-P6. Day -> the cards on it (unordered; ``order`` sorts a day)."""
    week: dict[str, list[Card]] = {d: [] for d in spec.days}
    for c in cards:                                            # P1
        for d in c.fixed_days:
            week[d].append(c)
    groups: dict[str, list[Card]] = {}
    for c in cards:                                            # P2
        if c.rotation and not c.fixed_days:
            groups.setdefault(c.rotation, []).append(c)
    for members in groups.values():
        for d, c in zip(spec.days, members):
            week[d].append(c)
    free = [c for c in cards if not c.fixed_days and not c.rotation]
    for c in sorted(free, key=lambda c: -c.demand):            # P3-P5 (sort is stable)
        options = [combo for combo in itertools.combinations(spec.days, min(c.days, len(spec.days)))
                   if _allowed(c, combo, week, spec)]
        if not options:
            raise ValueError(f"{c.name}: no allowed days left")
        best = min(options, key=lambda o: (-_new_days(c, o, week),
                                           sum(minutes(week[d]) for d in o),
                                           [spec.days.index(d) for d in o]))
        for d in best:
            week[d].append(c)
    return _balance(week, free, spec)


def _longest(week: dict) -> float:
    return max(minutes(items) for items in week.values())


def _balance(week: dict, movable: list[Card], spec: WeekSpec) -> dict:
    """P6."""
    improved = True
    while improved:
        improved = False
        current = _longest(week)
        short = _short_areas(week, spec)
        for card in movable:
            if card.days >= len(spec.days):
                continue
            stripped = {d: [c for c in items if c is not card] for d, items in week.items()}
            now = tuple(d for d in spec.days if card in week[d])
            for combo in itertools.combinations(spec.days, card.days):
                if combo == now or not _allowed(card, combo, stripped, spec):
                    continue
                trial = {d: list(items) for d, items in stripped.items()}
                for d in combo:
                    trial[d].append(card)
                if _longest(trial) < current - 1e-9 and _short_areas(trial, spec) <= short:
                    week, improved = trial, True
                    break
            if improved:
                break
    return week


def fill_bonus(day_before: list[Card], warmup: list[Card], candidates: list[Card],
               press_block: list[Card], target: float = SESSION_MINUTES_TARGET) -> list[Card]:
    """P8, the bonus session (approved 2026-10-16: "a 3 day week meets the
    required goal and a 4th day is a bonus"). One more appearance of each
    candidate, in the drop order given, while the session stays at or under the
    target. Never a high-demand lift that is on the day before. A press brings
    the press block (the release and the Y raise) in straight before it."""
    bonus = list(warmup)
    before = {c.name for c in day_before}
    for card in candidates:
        if any(c.name == card.name for c in bonus):
            continue
        if card.demand >= 3 and card.name in before:
            continue
        trial = bonus + [card]
        if card.is_press and not any(c.name == b.name for b in press_block for c in bonus):
            trial += [b for b in press_block]
        if minutes(trial) <= target + 0.5:
            bonus = trial
    return bonus


def hard_sets(items: list[Card]) -> dict[str, float]:
    tally: dict[str, float] = {}
    for c in items:
        if c.area:
            tally[c.area] = tally.get(c.area, 0) + c.sets
        if c.second:
            tally[c.second] = tally.get(c.second, 0) + 0.5 * c.sets
    return tally


def weekly_sets(week: dict, extra: dict | None = None) -> dict[str, float]:
    """All days' hard sets, plus sets done outside the strength days."""
    total = dict(extra or {})
    for items in week.values():
        for area, n in hard_sets(items).items():
            total[area] = total.get(area, 0) + n
    return total


def over_target(week: dict) -> list[tuple[str, float]]:
    """Sessions over SESSION_MINUTES_TARGET (60), with their modelled minutes.
    Reported, never refused: 70 is the limit."""
    return [(d, round(minutes(items), 1)) for d, items in week.items()
            if minutes(items) > SESSION_MINUTES_TARGET + 0.5]


def violations(week: dict, spec: WeekSpec, extra_sets: dict | None = None,
               extra_days: dict | None = None) -> list[str]:
    """Every broken rule, in plain words. Empty when the week passes.
    extra_sets / extra_days: what non-strength days add (e.g. the adductor
    ladder on Wednesday and Sunday)."""
    out: list[str] = []
    total = weekly_sets(week, extra_sets)
    for area, minimum in sorted(spec.minimums.items()):
        if total.get(area, 0) < minimum:
            out.append(f"{area}: {total.get(area, 0):g} hard sets a week, under its {minimum}")
        days = sum(1 for items in week.values() if hard_sets(items).get(area))
        days += (extra_days or {}).get(area, 0)
        need = spec.min_days.get(area, 2)
        if days < need:
            out.append(f"{area}: trained on {days} day(s), under {need}")
    for d, items in week.items():
        for area, n in hard_sets(items).items():
            if n > SESSION_AREA_CAP:
                out.append(f"{d}: {area} gets {n:g} hard sets, over {SESSION_AREA_CAP}")
        m = minutes(items)
        if m > SESSION_MINUTES_LIMIT + 0.5:
            out.append(f"{d}: {m:.0f} modelled minutes, over {SESSION_MINUTES_LIMIT}")
    return out
