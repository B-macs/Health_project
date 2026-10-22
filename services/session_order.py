"""Which exercises of today's session may change places (WP-27, 2026-10-22).

The owner's note: "Ability to switch the order of the exercises if the machine
isn't available". When a machine is busy he does another exercise first, and
the busy one comes straight after it. Until then the session ran in one fixed
order, and he did the other exercise anyway and tapped its sets later: on
2026-10-19 the shoulder press's three sets were stored 10 s apart, so their
times and rests were wrong, and the heart rate per exercise reads those times.

The phone runs a session with no network, so the engine sends with each
exercise its MOVE GROUP and the phone moves whole groups of the steps the
engine already walked (guided_flow.walk). It decides no order itself.

THE GROUPS come from the order rule's own sections (services/placement.order
over goal_week's cards):
- the warm-up ("warmup") never moves: it opens the session;
- a ramp set moves with the lift after it (sessions.ramp_lift_index): one
  station, one weight change (Key Rule 21);
- the shoulder release and the Y raise ("block") never move, and a press may
  run only after them (`after`): they run straight before the first press;
- the abs and hip work at the end ("last") never move: the abs are trained to
  failure at the end of the session;
- a timed test never moves: a measurement keeps its place;
- every other lift ("main") moves.
An exercise no card names (the accessory session, an older block) does not
move, so the phone offers nothing there.

A SWAP (WP-28, his note: "hack squat change to V squat"): a lift may have
entries that run in the place of its group when its equipment is in use
(goal_block.ALTERNATIVES). The engine sends them dosed, seeded from their own
history and walked; the phone puts them in the group's place only when the
athlete swaps, and the swapped-out lift is not saved.
"""

from __future__ import annotations

from services import sessions

MOVABLE = "main"


def block_sections() -> dict[str, tuple[str, bool]]:
    """{exercise name: (section, is a press)} from the 12-week block's cards."""
    import goal_week as gw  # the cards hold each exercise's section (placement.order)
    cards = list(gw.WARMUP) + list(gw.CARDS) + list(gw.BONUS_ORDER)
    return {c.name: (c.section, bool(c.is_press)) for c in cards}


def alternatives_for(name: str) -> list[dict]:
    """The entries that run in a lift's place when its equipment is in use
    (goal_block.ALTERNATIVES: its ramp, then itself), or [] (WP-28)."""
    import goal_block as gb
    return list(gb.ALTERNATIVES.get(name, []))


def move_groups(exercises: list[dict],
                sections: dict[str, tuple[str, bool]] | None = None) -> list[dict]:
    """One entry per exercise, in order: {"group": int, "movable": bool,
    "after": [group, ...]}. The exercises of one group are next to each other;
    a group may run only once every group in its `after` has run. `sections`
    is block_sections() unless a caller (the phone's made-up session) names
    its own."""
    sections = block_sections() if sections is None else sections
    out: list[dict] = []
    group = -1
    block_groups: list[int] = []
    for i, ex in enumerate(exercises):
        name = ex.get("name") or ""
        follows_ramp = i > 0 and sessions.ramp_lift_index(exercises, i - 1) == i
        if not follows_ramp:
            group += 1
        lift = sessions.ramp_lift_index(exercises, i)
        own = exercises[lift]["name"] if lift is not None else name
        section, is_press = sections.get(own, ("", False))
        movable = section == MOVABLE and not sessions.is_measurement(name)
        if section == "block" and group not in block_groups:
            block_groups.append(group)
        after = list(block_groups) if is_press else []
        if follows_ramp:
            # A ramp and its lift are one group: the lift's own reading decides it.
            out[-1] = {**out[-1], "movable": movable, "after": after}
        out.append({"group": group, "movable": movable, "after": after})
    return out
