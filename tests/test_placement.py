"""The placement rules put every exercise in its place, the same way each time.

The athlete, 2026-10-16: "create a deterministic test to put them automatically
in their correct position", then "Make a session C and D and balance it out".
services/placement.py holds the rules (step 6 of docs/training/goal_system.md);
goal_week.py holds the draft cards. These tests run the rules on the cards and
check the week they produce — and that the checker catches a broken week.
"""
from dataclasses import replace

import goal_week as gw
from services import placement as pl
from services import rules

WEEK = pl.place(gw.CARDS, gw.SPEC)
ORDERED = {d: pl.order(WEEK[d]) for d in gw.DAYS}

#: Picks waiting for his approval (2026-10-16); they get rules when approved.
#: This set may only shrink.
_PICKS_WITHOUT_A_RULE_YET = {"Single-Arm DB Row", "Machine Chest Press"}


def _names(day):
    return [c.name for c in ORDERED[day]]


def test_the_draft_week_breaks_no_rule():
    assert pl.violations(WEEK, gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS) == []


def test_the_same_cards_give_the_same_week():
    again = pl.place(list(gw.CARDS), gw.SPEC)
    assert {d: [c.name for c in pl.order(again[d])] for d in gw.DAYS} == \
        {d: _names(d) for d in gw.DAYS}


def test_every_session_fits_the_time_limit():
    for d in gw.DAYS:
        assert pl.minutes(WEEK[d]) <= pl.SESSION_MINUTES_LIMIT + 0.5, d


def test_sixty_is_the_target_and_seventy_the_limit():
    """The athlete, 2026-10-16: "70min is the Max, 60min is the target"."""
    assert (pl.SESSION_MINUTES_TARGET, pl.SESSION_MINUTES_LIMIT) == (60, 70)


def test_over_target_lists_exactly_the_sessions_over_sixty():
    reported = {d for d, _ in pl.over_target(WEEK)}
    for d in gw.DAYS:
        assert (d in reported) == (pl.minutes(WEEK[d]) > pl.SESSION_MINUTES_TARGET + 0.5), d


def test_every_area_reaches_its_minimum():
    total = pl.weekly_sets(WEEK, gw.EXTRA_SETS)
    for area, minimum in gw.MINIMUMS.items():
        assert total.get(area, 0) >= minimum, area


def test_every_training_exercise_has_three_sets():
    for c in gw.CARDS:
        if c.area:
            assert c.sets == pl.WORKING_SETS, c.name


def test_every_session_is_full_body():
    lower = {"quads", "glute max", "hamstrings"}
    upper = {"chest", "back", "press muscles", "side delts", "rear delts", "shoulder-blade muscles"}
    for d in gw.DAYS:
        areas = set(pl.hard_sets(WEEK[d]))
        assert areas & lower and areas & upper and "abs" in areas, d


def test_the_warm_up_comes_first_and_the_holds_last():
    for d in gw.DAYS:
        sections = [c.section for c in ORDERED[d]]
        first_other = next(i for i, s in enumerate(sections) if s != "warmup")
        assert all(s == "warmup" for s in sections[:first_other])
        assert "warmup" not in sections[first_other:], d
        first_last = sections.index("last")
        assert all(s == "last" for s in sections[first_last:]), d


def test_a_ramp_set_sits_straight_before_its_lift():
    for d in gw.DAYS:
        names = _names(d)
        for i, n in enumerate(names):
            if n.endswith("(Ramp Set)"):
                assert names[i + 1] == n.replace(" (Ramp Set)", ""), (d, n)


def test_the_release_and_the_y_raise_come_straight_before_the_first_press():
    for d in gw.DAYS:
        names = _names(d)
        presses = [i for i, c in enumerate(ORDERED[d]) if c.is_press]
        has_release = "Pec & Scar Release (Right)" in names
        assert has_release == bool(presses), d          # only on a press day
        if presses:
            i = names.index("Pec & Scar Release (Right)")
            assert names[i + 1] == "Prone Y-Raise (Scapular)", d
            assert i + 2 == presses[0], d


def test_a_two_day_exercise_is_never_on_two_days_in_a_row():
    for c in gw.CARDS:
        on = tuple(d for d in gw.DAYS if any(x.name == c.name for x in WEEK[d]))
        if len(on) == 2:
            assert on not in gw.IN_A_ROW, (c.name, on)


def test_the_abs_rotate_one_a_day():
    abs_cards = [c.name for c in gw.CARDS if c.rotation == "abs"]
    seen = [[c.name for c in WEEK[d] if c.rotation == "abs"] for d in gw.DAYS]
    assert all(len(s) == 1 for s in seen)
    assert [s[0] for s in seen] == abs_cards


def test_the_knee_and_hip_lifts_take_one_slot_a_day():
    for d in gw.DAYS:
        for pattern in ("knee", "hip"):
            assert sum(1 for c in WEEK[d] if c.pattern == pattern) == 1, (d, pattern)


def test_every_card_lands_on_a_safety_rule_except_the_pending_picks():
    unknown = {c.name for c in gw.CARDS if rules.check_movement(c.name, 2)["severity"] == "unknown"}
    assert unknown <= _PICKS_WITHOUT_A_RULE_YET, unknown - _PICKS_WITHOUT_A_RULE_YET
    assert all(rules.check_movement(c.name, 2)["severity"] != "contraindicated" for c in gw.CARDS)


# ── the checker is not vacuous ───────────────────────────────────────────────

def test_the_checker_catches_a_missing_area():
    cards = [c for c in gw.CARDS if c.name != "45° Back Extension"]
    week = pl.place(cards, gw.SPEC)
    found = pl.violations(week, gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS)
    assert any(v.startswith("deep back") for v in found), found


def test_the_checker_catches_an_over_long_session():
    heavy = [replace(c, rest_seconds=c.rest_seconds * 3) if c.area else c for c in gw.CARDS]
    found = pl.violations(pl.place(heavy, gw.SPEC), gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS)
    assert any("modelled minutes" in v for v in found), found


def test_the_checker_catches_too_many_sets_for_one_area():
    many = gw.CARDS + [replace(c, name=c.name + f" #{i}", pattern="", fixed_days=("Mon",))
                       for i, c in enumerate(gw.CARDS) if c.area == "abs"]
    found = pl.violations(pl.place(many, gw.SPEC), gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS)
    assert any("abs gets" in v for v in found), found
