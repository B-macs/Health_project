"""A replacement the athlete creates in a session when a machine is not free
(WP-46).

The athlete, 2026-11-03: "if the machine with the current settings isnt
available I should be able to do another machine or free weight by creating it
easy in the app., this doesnt change the muscles worked on the exercise
replacement"; and, to "saved and offered again next time, or that day only":
"a it is now offered every time".

WHAT A REPLACEMENT IS. The same exercise on other equipment: the lift it
replaces gives it everything but its name, its equipment and its weight — the
sets, the rep range, the rest, the side, the section and the muscles. So it
keeps the lift's workflow record (Key Rule 25: the goal and the area do not
change); it is not a new exercise of the block. It has its own name and so its
own history: a weight on another machine is a different number, and the
rep-range rule must read only that machine's sessions. Its first weight is set
by hand in the session; the rule takes over from the second. A lift with a
ramp set gets a ramp of the replacement in front of it, as the V squat swap
(WP-28) has.

THE MUSCLES. The body-area maps (training_constants: EXERCISE_BODY_REGION,
EXERCISE_REGION_SHARES, EXERCISE_MOVEMENT_WEIGHT) are read by name, so each
replacement is entered there under the lift's entries (register): its sets
then count in the same body areas, strain and weekly work as the lift's.
A name a map already holds is never overwritten.

Stored in one config row (Repository.get_replacements): {lift: [{"name",
"item_id", "created"}, ...]}. Pure logic apart from register(), which fills
the maps of this process.
"""
from __future__ import annotations

from datetime import date

import training_constants as tc
from services import equipment
from services import sessions

#: The longest name a replacement may have.
MAX_NAME = 40


class ReplacementRefused(ValueError):
    """A replacement the engine will not store; the message says why."""


def _ramp_name(name: str) -> str:
    return f"{sessions.base_name(name)} {sessions.RAMP_SUFFIX}"


def validated(stored: dict, lift: str, name: str, item_id: str, *, lift_names: set[str],
              known_names: set[str], settings: equipment.Settings, today: date) -> tuple[dict, dict]:
    """`stored` with the new replacement, and the replacement. The same name
    sent again for the same lift returns it unchanged (a save sent twice stores
    one). Refused: a lift that is not a block lift with a weight stepper, an
    empty or long name, a name another exercise or replacement already has, an
    item not on the equipment list."""
    name = " ".join(str(name or "").split())
    if lift not in lift_names:
        raise ReplacementRefused(f"{lift!r} is not a lift with a weight")
    if not name or len(name) > MAX_NAME:
        raise ReplacementRefused(f"the name is 1 to {MAX_NAME} characters")
    if settings.item(item_id) is None:
        raise ReplacementRefused("that equipment is not on the list")
    for entry in stored.get(lift, []):
        if entry["name"].casefold() == name.casefold():
            return stored, entry
    taken = {n.casefold() for n in known_names}
    taken |= {e["name"].casefold() for entries in stored.values() for e in entries}
    if name.casefold() in taken or _ramp_name(name).casefold() in taken:
        raise ReplacementRefused(f"an exercise is already called {name!r}")
    entry = {"name": name, "item_id": item_id, "created": today.isoformat()}
    return {**stored, lift: [*stored.get(lift, []), entry]}, entry


def exercises_for(lift: dict, entry: dict, settings: equipment.Settings,
                  ramp_of_lift: dict | None) -> list[dict]:
    """The entries that run in the lift's place: the replacement's ramp (when
    the lift has one), then the replacement."""
    import goal_block as gb  # the block's ramp builder
    item = settings.item(entry.get("item_id")) or settings.item(equipment.default_item_id(lift))
    pair = equipment.factor(lift) > 1 and item is not None and item.kind == "dumbbell"
    repl = {
        **lift,
        "name": entry["name"],
        "equipment_type": item.kind if item else lift.get("equipment_type"),
        "weight_kg": 0.0,
        "increment_size": round((item.step if item else 2.5) * (2 if pair else 1), 2),
        "increment_unit": item.unit if item else "kg",
        "mechanics": (f"The same movement and muscles as the {lift['name']}, on the "
                      f"{entry['name']}: the same sets, reps and rest. Set the weight in the "
                      "first session; the rep-range rule takes over from the second."),
        "warning": None,
        "replacement_for": lift["name"],
    }
    if ramp_of_lift is None:
        return [repl]
    return [gb._ramp(_ramp_name(entry["name"]), repl), repl]


def register(stored: dict) -> None:
    """Enter every replacement in the body-area maps under the lift it
    replaces (its ramp under the lift's ramp, or the lift), so its sets count
    in the same areas. Never overwrites a name a map already holds."""
    for lift, entries in (stored or {}).items():
        for entry in entries:
            for new, old in ((entry["name"], lift), (_ramp_name(entry["name"]), _ramp_name(lift))):
                for table in (tc.EXERCISE_BODY_REGION, tc.EXERCISE_REGION_SHARES,
                              tc.EXERCISE_MOVEMENT_WEIGHT):
                    source = table.get(old, table.get(lift))
                    if source is not None and new not in table:
                        table[new] = source


def traits(stored: dict, plan_traits: dict[str, dict],
           settings: equipment.Settings) -> dict[str, dict]:
    """sessions.exercise_traits for the replacements: each the lift's sides and
    one-arm flag, in its item's unit."""
    out = {}
    for lift, entries in (stored or {}).items():
        base = plan_traits.get(lift)
        if base is None:
            continue
        for entry in entries:
            item = settings.item(entry.get("item_id"))
            out[entry["name"]] = {**base, "unit": item.unit if item else base.get("unit", "kg")}
    return out
