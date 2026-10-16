"""The placement rules put every exercise in its place, the same way each time.

The athlete, 2026-10-16: "create a deterministic test to put them automatically
in their correct position"; then "a 3 day week meets the required goal and a
4th day is a bonus". services/placement.py holds the rules (step 6 of
docs/training/goal_system.md); goal_week.py holds the cards. These tests run the
rules on the cards and check the week they produce — and that the checker
catches a broken week.
"""
from dataclasses import replace

import goal_week as gw
from services import placement as pl
from services import rules
from services import sessions

WEEK = gw.week()
CORE = {d: WEEK[d] for d in gw.CORE_DAYS}
ORDERED = {d: pl.order(WEEK[d]) for d in gw.DAYS}
ALL_CARDS = {c.name: c for c in gw.CARDS + gw.BONUS_ORDER}


def _names(day):
    return [c.name for c in ORDERED[day]]


# ── the core: three sessions meet the required dose ─────────────────────────

def test_the_three_core_sessions_break_no_rule():
    assert pl.violations(CORE, gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS) == []


def test_the_core_reaches_every_required_number():
    total = pl.weekly_sets(CORE, gw.EXTRA_SETS)
    for area, minimum in gw.REQUIRED.items():
        assert total.get(area, 0) >= minimum, area


def test_the_required_dose_is_the_approved_one():
    """Approved 2026-10-16 (docs/training/weekly_volume_minimum_2026-10-16.md)."""
    for area in ("glute max", "abs", "deep back", "hamstrings"):
        assert gw.REQUIRED[area] == 6, area
    for area in ("quads", "chest", "back", "press muscles", "shoulder-blade muscles",
                 "side delts", "rear delts"):
        assert gw.REQUIRED[area] == 4, area


def test_the_same_cards_give_the_same_week():
    again = gw.week()
    assert {d: [c.name for c in pl.order(again[d])] for d in gw.DAYS} == \
        {d: _names(d) for d in gw.DAYS}


def test_no_session_breaks_the_seventy_minute_limit():
    for d in gw.DAYS:
        assert pl.minutes(WEEK[d]) <= pl.SESSION_MINUTES_LIMIT + 0.5, d


def test_sixty_is_the_target_and_seventy_the_limit():
    """The athlete, 2026-10-16: "70min is the Max, 60min is the target"."""
    assert (pl.SESSION_MINUTES_TARGET, pl.SESSION_MINUTES_LIMIT) == (60, 70)


def test_over_target_lists_exactly_the_sessions_over_sixty():
    reported = {d for d, _ in pl.over_target(WEEK)}
    for d in gw.DAYS:
        assert (d in reported) == (pl.minutes(WEEK[d]) > pl.SESSION_MINUTES_TARGET + 0.5), d


def test_every_training_exercise_has_three_sets():
    for c in ALL_CARDS.values():
        if c.area:
            assert c.sets == pl.WORKING_SETS, c.name


def test_every_core_session_is_full_body():
    lower = {"quads", "glute max", "hamstrings"}
    upper = {"chest", "back", "press muscles", "side delts", "rear delts", "shoulder-blade muscles"}
    for d in gw.CORE_DAYS:
        areas = set(pl.hard_sets(WEEK[d]))
        assert areas & lower and areas & upper, d


def test_a_two_day_exercise_is_never_on_two_core_days_in_a_row():
    for c in gw.CARDS:
        on = tuple(d for d in gw.CORE_DAYS if any(x.name == c.name for x in WEEK[d]))
        if len(on) == 2:
            assert on not in gw.IN_A_ROW, (c.name, on)


def test_the_hack_squat_and_the_lunge_are_on_different_days():
    for d in gw.CORE_DAYS:
        assert sum(1 for c in WEEK[d] if c.pattern == "knee") <= 1, d


# ── order inside a day ───────────────────────────────────────────────────────

def test_the_warm_up_comes_first_and_the_holds_last():
    for d in gw.DAYS:
        sections = [c.section for c in ORDERED[d]]
        first_other = next(i for i, s in enumerate(sections) if s != "warmup")
        assert all(s == "warmup" for s in sections[:first_other])
        assert "warmup" not in sections[first_other:], d
        if "last" in sections:
            first_last = sections.index("last")
            assert all(s == "last" for s in sections[first_last:]), d


def test_a_ramp_set_sits_straight_before_its_lift():
    for d in gw.DAYS:
        names = _names(d)
        for i, n in enumerate(names):
            if n.endswith("(Ramp Set)"):
                # The ramp is named for the lift without its equipment tag
                # ("Romanian Deadlift (Ramp Set)" before "Romanian Deadlift
                # (DB)"), so the app's base name reads them as one station.
                lift = names[i + 1]
                assert not lift.endswith("(Ramp Set)"), (d, n)
                assert sessions.base_name(lift) == sessions.base_name(n), (d, n, lift)


def test_the_release_and_the_y_raise_come_straight_before_the_first_press():
    for d in gw.DAYS:
        names = _names(d)
        presses = [i for i, c in enumerate(ORDERED[d]) if c.is_press]
        has_release = "Pec & Scar Release (Right)" in names
        assert has_release == bool(presses), d          # only on a press day
        if presses:
            i = names.index("Pec & Scar Release (Right)")
            assert names[i + 1] == "Single-Arm Cable Y Raise", d
            assert i + 2 == presses[0], d


# ── the bonus ────────────────────────────────────────────────────────────────

def test_the_bonus_stays_within_the_target():
    assert pl.minutes(WEEK[gw.BONUS_DAY]) <= pl.SESSION_MINUTES_TARGET + 0.5


def test_the_bonus_never_repeats_a_heavy_lift_from_the_day_before():
    before = {c.name for c in WEEK["Thu"]}
    for c in WEEK[gw.BONUS_DAY]:
        if c.demand >= 3:
            assert c.name not in before, c.name


def test_the_bonus_follows_the_drop_order():
    order = [c.name for c in gw.BONUS_ORDER]
    picked = [c.name for c in WEEK[gw.BONUS_DAY] if c.name in order and c.section != "block"]
    assert picked == sorted(picked, key=order.index)


def test_the_minimums_hold_without_the_bonus():
    """The 4th day is a bonus: nothing required depends on it — except the
    hip flexors' second day, the one named exception (gw.MIN_DAYS, approved
    2026-10-16)."""
    total = pl.weekly_sets(CORE, gw.EXTRA_SETS)
    assert all(total.get(a, 0) >= m for a, m in gw.REQUIRED.items())
    assert set(gw.MIN_DAYS) == {"hip flexors"}


def test_the_90_90_hip_lift_is_not_in_the_new_week():
    """Out on 2026-10-16 (athlete: "It doesnt warm up anything and the evidence
    it fixes the issue is weak"). It had been carried over from Block B's
    warm-up without being checked."""
    assert all("90/90 Hip Lift" not in _names(d) for d in gw.DAYS)
    assert [c.name for c in gw.WARMUP] == ["Standing Psoas March"]


def test_the_neck_stretch_is_done_at_home_not_in_the_gym():
    """Approved 2026-10-16: at home on the core days, so it takes no gym time."""
    name = "Neck Working Stretch (Right)"
    assert all(name not in _names(d) for d in gw.DAYS)
    assert gw.HOME[name]["days"] == gw.CORE_DAYS
    assert rules.check_movement(name, 2)["severity"] == "caution"


# ── safety ───────────────────────────────────────────────────────────────────

def test_every_card_lands_on_a_safety_rule():
    for c in ALL_CARDS.values():
        severity = rules.check_movement(c.name, 2)["severity"]
        assert severity in ("cleared", "caution"), (c.name, severity)


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
                       for i, c in enumerate([gw.CRUNCH, gw.REVERSE_CRUNCH, gw.WOODCHOP])]
    found = pl.violations(pl.place(many, gw.SPEC), gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS)
    assert any("abs gets" in v for v in found), found


def test_the_checker_catches_an_area_on_one_day():
    one = [replace(c, days=1) if c.name == "Romanian Deadlift (DB)" else c for c in gw.CARDS]
    found = pl.violations(pl.place(one, gw.SPEC), gw.SPEC, gw.EXTRA_SETS, gw.EXTRA_DAYS)
    assert any(v.startswith("hamstrings") for v in found), found


def test_a_two_day_card_avoids_days_in_a_row_on_a_three_day_week():
    """Regression, 2026-10-16: the not-in-a-row rule once switched on only for
    cards on at most half the days, so on Mon, Tue, Thu a two-day card could
    land on Mon and Tue. It binds whenever a choice without a row exists."""
    spec = pl.WeekSpec(days=("Mon", "Tue", "Thu"), in_a_row=frozenset({("Mon", "Tue")}))
    cards = [pl.Card(f"Lift {i}", area="x", days=2) for i in range(4)]
    week = pl.place(cards, spec)
    for c in cards:
        on = tuple(d for d in spec.days if c in week[d])
        assert on != ("Mon", "Tue"), (c.name, on)
