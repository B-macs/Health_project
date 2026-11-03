"""The equipment list: each piece of equipment's weight step, and which one each
lift is done on (WP-46).

The athlete, 2026-11-03: "I should have settings to change the weight
increments and also add additional exercises with these weight increments";
his answer "A": a list of equipment, each with its step, and each exercise
linked to one item. The step is what the + and - buttons move and what the
rep-range rule adds (engine.range_progression).

THE DEFAULTS ARE THE BLOCK'S OWN STEPS (goal_block.py): dumbbells 2.5 kg, a
pair logged as the total 5 kg; machines 2.5 kg; the back extension a 2.5 kg
plate; cables half a unit; the new cable machine 2 kg (WP-45). With nothing
stored, every lift steps exactly as goal_block wrote it, and a test keeps it so.

A LIFT LOGGED AS A PAIR (a dumbbell in each hand, logged as the total) steps
twice its item's step: the factor is the plan's step over its default item's.

Stored in one config row (Repository.get_equipment_steps), as it is saved:
{"items": [{"id", "name", "step", "unit", "kind"}, ...], "links": {exercise:
item id}}. A stored item replaces the default of its id; a link to an item no
longer on the list falls back to the default. Pure logic: no I/O.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

#: What an item is, so a replacement on it gets the right kind of stepper.
KINDS = ("dumbbell", "machine", "cable")
UNITS = ("kg", "unit")
#: The largest step an item may take, and the longest name.
MAX_STEP = 25.0
MAX_NAME = 40


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    step: float
    unit: str
    kind: str


DEFAULT_ITEMS: tuple[Item, ...] = (
    Item("dumbbells", "Dumbbells", 2.5, "kg", "dumbbell"),
    Item("machines", "Machines", 2.5, "kg", "machine"),
    Item("plates", "Plates", 2.5, "kg", "machine"),
    Item("cables", "Cables", 0.5, "unit", "cable"),
    Item("new_cable_machine", "New cable machine", 2.0, "kg", "cable"),
)
DEFAULT_IDS = frozenset(i.id for i in DEFAULT_ITEMS)
#: The item a lift is on when its kind alone does not say (goal_block's steps).
DEFAULT_LINKS: dict[str, str] = {
    "45° Back Extension": "plates",
    "Single-Arm Cable Y Raise": "new_cable_machine",
    "Cable Lateral Raise": "new_cable_machine",
    "Reverse Cable Crossover": "new_cable_machine",
}
_BY_KIND = {"dumbbell": "dumbbells", "machine": "machines", "cable": "cables"}


class InvalidSettings(ValueError):
    """A saved list the engine refuses; the message says why."""


@dataclass(frozen=True)
class Settings:
    items: tuple[Item, ...]
    links: dict[str, str]

    def item(self, item_id: str | None) -> Item | None:
        return next((i for i in self.items if i.id == item_id), None)


def defaults() -> Settings:
    return Settings(DEFAULT_ITEMS, {})


def _base(name: str) -> str:
    from services import sessions
    return sessions.base_name(name)


def default_item_id(ex: dict) -> str | None:
    """The item a plan lift is on with nothing stored; None for a lift with no
    weight stepper (a band, body weight). A ramp set is on its lift's item: a
    ramp and its lift share one station name (sessions.base_name)."""
    name = ex.get("name") or ""
    by_base = {_base(k): v for k, v in DEFAULT_LINKS.items()}
    return (DEFAULT_LINKS.get(name) or by_base.get(_base(name))
            or _BY_KIND.get(ex.get("equipment_type") or ""))


def factor(ex: dict) -> float:
    """How many of the item's steps one step of this lift is: 2 for a pair of
    dumbbells logged as the total, else 1 (the plan's step over its default
    item's)."""
    item = next((i for i in DEFAULT_ITEMS if i.id == default_item_id(ex)), None)
    plan_step = ex.get("increment_size")
    if item is None or not plan_step or not item.step:
        return 1.0
    return max(1.0, round(float(plan_step) / item.step))


def from_stored(stored: dict | None) -> Settings:
    """The settings as stored, over the defaults. Unreadable parts are left out
    rather than raised: a damaged row must never stop a session."""
    if not stored:
        return defaults()
    by_id = {i.id: i for i in DEFAULT_ITEMS}
    for raw in stored.get("items") or []:
        try:
            item = _item(raw)
        except InvalidSettings:
            continue
        by_id[item.id] = item
    order = [i.id for i in DEFAULT_ITEMS] + [k for k in by_id if k not in DEFAULT_IDS]
    items = tuple(by_id[k] for k in order)
    known = {i.id for i in items}
    links = {str(k): str(v) for k, v in (stored.get("links") or {}).items() if v in known}
    return Settings(items, links)


def _item(raw: dict) -> Item:
    try:
        item_id = str(raw["id"]).strip()
        name = str(raw["name"]).strip()
        step = float(raw["step"])
        unit = str(raw["unit"])
        kind = str(raw["kind"])
    except (KeyError, TypeError, ValueError):
        raise InvalidSettings("an item needs an id, a name, a step, a unit and a kind") from None
    if not item_id or not name or len(name) > MAX_NAME:
        raise InvalidSettings(f"an item's name is 1 to {MAX_NAME} characters")
    if not 0 < step <= MAX_STEP:
        raise InvalidSettings(f"a step is more than 0 and at most {MAX_STEP:g}")
    if unit not in UNITS:
        raise InvalidSettings(f"a unit is one of {', '.join(UNITS)}")
    if kind not in KINDS:
        raise InvalidSettings(f"a kind is one of {', '.join(KINDS)}")
    return Item(item_id, name, round(step, 2), unit, kind)


def validated(body: dict, exercise_names: set[str]) -> dict:
    """A list sent by the phone, checked, as it is stored. Every default item
    stays on the list (its step and name may change); a link names a lift the
    block has and an item on the list."""
    raw_items = body.get("items")
    if not isinstance(raw_items, list):
        raise InvalidSettings("the list of items is missing")
    items = [_item(r) for r in raw_items]
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise InvalidSettings("two items have the same id")
    if not DEFAULT_IDS <= set(ids):
        raise InvalidSettings("the default items cannot be removed")
    links = body.get("links") or {}
    if not isinstance(links, dict):
        raise InvalidSettings("the links are not a list of exercise and item")
    for name, item_id in links.items():
        if name not in exercise_names:
            raise InvalidSettings(f"no exercise is called {name!r}")
        if item_id not in ids:
            raise InvalidSettings(f"no item has the id {item_id!r}")
    return {"items": [asdict(i) for i in items], "links": {str(k): str(v) for k, v in links.items()}}


def item_for(ex: dict, settings: Settings) -> Item | None:
    """The item this lift is on: its stored link (a ramp set reads its lift's),
    else its default."""
    name = ex.get("name") or ""
    link = settings.links.get(name) or next(
        (v for k, v in settings.links.items() if _base(k) == _base(name)), None)
    return settings.item(link) or settings.item(default_item_id(ex))


def apply(ex: dict, settings: Settings) -> dict:
    """The lift with the step of its item (times its factor) and the item's
    unit; unchanged when it has no item (a band, body weight)."""
    if ex.get("equipment_type") in (None, "band"):
        return ex
    item = item_for(ex, settings)
    if item is None:
        return ex
    step = round(item.step * factor(ex), 2)
    if step == ex.get("increment_size") and item.unit == ex.get("increment_unit"):
        return ex
    return {**ex, "increment_size": step, "increment_unit": item.unit}


def lifts(plan_exercises: list[dict]) -> list[dict]:
    """The block's lifts with a weight stepper, once each, in the order first
    met, ramp sets left out (they follow their lift)."""
    seen, out = set(), []
    for ex in plan_exercises:
        name = ex.get("name") or ""
        if (ex.get("warmup") or ex.get("equipment_type") in (None, "band") or name in seen
                or default_item_id(ex) is None):
            continue
        seen.add(name)
        out.append(ex)
    return out


def with_units(traits: dict[str, dict], plan_exercises: list[dict],
               settings: Settings) -> dict[str, dict]:
    """sessions.exercise_traits with each lift's unit as its item gives it, so a
    lift moved to a kilogram item counts its sets in kilograms."""
    out = dict(traits)
    for ex in lifts(plan_exercises):
        name = ex["name"]
        unit = apply(ex, settings).get("increment_unit")
        if name in out and unit and out[name].get("unit") != unit:
            out[name] = {**out[name], "unit": unit}
    return out


def answer(settings: Settings, plan_exercises: list[dict]) -> dict:
    """The Settings screen's list: the items, and each lift with its item and
    the step it takes."""
    return {
        "items": [{**asdict(i), "default": i.id in DEFAULT_IDS} for i in settings.items],
        "exercises": [{"name": ex["name"], "item_id": item_for(ex, settings).id,
                       "default_item_id": default_item_id(ex),
                       "pair": factor(ex) > 1,
                       "step": apply(ex, settings).get("increment_size"),
                       "unit": apply(ex, settings).get("increment_unit")}
                      for ex in lifts(plan_exercises)],
    }
