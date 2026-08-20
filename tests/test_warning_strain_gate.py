"""The per-exercise safety warning is gated on regional strain.

Athlete's instruction, 2026-08-20: a warning shown on every set of every
session is ignored, so it stops being a safety message. It now shows only when
the body area the exercise actually loads is above 16 on the 0-21 scale.

These pin the RULE, not the rendering. The three failure directions are the
point: an unmapped exercise and a failed read both warn, while a genuinely
unloaded area does not.
"""
import training_constants as tc
from services import strain_regions as sr


def _mapped_name(*wanted):
    """A real exercise name whose share in `wanted` clears the minimum."""
    for name, shares in tc.EXERCISE_REGION_SHARES.items():
        got, _ = sr.region_shares_for(name)
        if not got:
            continue
        regions = {r for r, s in got.items() if s >= sr.WARNING_MIN_REGION_SHARE}
        if regions == set(wanted):
            return name
    raise AssertionError("no exercise maps cleanly to %s" % (wanted,))


def _strains(**kw):
    return {r: kw.get(r) for r in sr.REGIONS}


# ── the threshold itself ─────────────────────────────────────────────────────

def test_the_threshold_is_the_athletes_number_and_is_strict():
    assert sr.WARNING_STRAIN_THRESHOLD == 16.0
    name = _mapped_name("lower_body")
    at = sr.warning_is_due(name, _strains(lower_body=16.0), None)
    over = sr.warning_is_due(name, _strains(lower_body=16.1), None)
    assert at["due"] is False, "16.0 is not OVER 16"
    assert over["due"] is True


def test_a_quiet_area_does_not_warn():
    name = _mapped_name("lower_body")
    out = sr.warning_is_due(name, _strains(lower_body=4.0),
                            _strains(lower_body=9.9))
    assert out["due"] is False
    assert out["peak"] == 9.9


# ── today OR yesterday, whichever is higher ──────────────────────────────────

def test_yesterday_alone_is_enough_to_warn():
    """The athlete's choice: today-so-far OR yesterday. This is the case that
    matters most in practice, because sets are not written until the session is
    saved, so today is empty for the whole session being performed."""
    name = _mapped_name("lower_body")
    out = sr.warning_is_due(name, _strains(lower_body=0.0),
                            _strains(lower_body=18.0))
    assert out["due"] is True
    assert out["peak"] == 18.0


def test_today_alone_is_enough_to_warn():
    name = _mapped_name("lower_body")
    out = sr.warning_is_due(name, _strains(lower_body=17.5),
                            _strains(lower_body=1.0))
    assert out["due"] is True


# ── it is the exercise's OWN area that decides ───────────────────────────────

def test_a_hot_region_the_exercise_does_not_load_does_not_warn():
    """The whole point of 'that body part area'. A blazing lower body must not
    fire the warning on an upper-body exercise."""
    name = _mapped_name("upper_body")
    out = sr.warning_is_due(name, _strains(lower_body=21.0, upper_body=2.0),
                            None)
    assert out["due"] is False


def test_a_minor_share_cannot_trigger_a_warning():
    """Without the minimum share, a lift with an incidental few-percent core
    component would fire on core strain, which is not what the rule means."""
    shares = {"upper_body": 0.95, "core": 0.05, "lower_body": 0.0}
    hot = {r for r, s in shares.items() if s >= sr.WARNING_MIN_REGION_SHARE}
    assert hot == {"upper_body"}, "0.05 must not clear the bar"


# ── the three failure directions, which differ on purpose ────────────────────

def test_an_unmapped_exercise_warns():
    out = sr.warning_is_due("Not A Real Exercise At All",
                            _strains(upper_body=0.0), _strains(upper_body=0.0))
    assert out["due"] is True
    assert out["basis"] == sr.BASIS_UNMAPPED


def test_a_failed_read_warns():
    """Both dicts None means the READ failed. Unknown is not evidence of
    safety — the same rule the battery applies with `indeterminate`."""
    out = sr.warning_is_due(_mapped_name("lower_body"), None, None)
    assert out["due"] is True
    assert "could not be read" in out["reason"]


def test_no_session_on_either_day_does_not_warn():
    """`region_strain` returns all-None for a day with no session. That is a
    real reading meaning the area is unloaded, NOT a missing one, and it is
    exactly when the athlete does not want the warning."""
    name = _mapped_name("lower_body")
    empty = {r: None for r in sr.REGIONS}
    out = sr.warning_is_due(name, empty, empty)
    assert out["due"] is False
    assert "unloaded" in out["reason"]


def test_it_never_raises_on_junk():
    for args in (("", None, None), ("x", {}, {}), ("x", {"nope": 1}, None)):
        assert isinstance(sr.warning_is_due(*args), dict)


# ── nothing was deleted from the plan ────────────────────────────────────────

def test_every_authored_warning_still_exists():
    """Gating is a DISPLAY change. If this drops, warnings were deleted from
    training_plan.py rather than gated, which is a different and worse thing."""
    import training_plan as tp
    warned = {e["name"] for plan in (tp.PLAN, tp.PLAN_STAGE2, tp.PLAN_STAGE2B)
              for day in plan.values() for e in day["exercises"]
              if e.get("warning")}
    assert len(warned) >= 13, warned


def test_every_warned_exercise_is_region_mapped():
    """An unmapped warned exercise warns unconditionally — correct as a
    fallback, useless as a steady state. All 13 map today; keep it that way."""
    import training_plan as tp
    unmapped = sorted(
        e["name"] for plan in (tp.PLAN, tp.PLAN_STAGE2, tp.PLAN_STAGE2B)
        for day in plan.values() for e in day["exercises"]
        if e.get("warning") and sr.region_shares_for(e["name"])[0] is None)
    assert unmapped == [], unmapped
