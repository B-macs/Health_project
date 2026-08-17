"""
tests/test_directive_no_contradiction.py — the banner may not contradict the
metrics it is shown beside.

Athlete, 2026-08-17, on being told "Reduced load today" with every biometric
green and strain at 2.3:

    "I want to ensure that the colours match — if my strain is at 2.3 then it
     shouldn't say reduced load in training, that is a contradiction."

WHAT WAS ACTUALLY HAPPENING. engine.volume_recommendation caps volume at 0.85
whenever injury weight is above 0.7, deliberately, even on a green day — tissue
is still healing and that is a standing clinical constraint, not a claim about
this morning. But it returned signal_color "yellow", which is in
sessions.REDUCED_LOAD_SIGNALS, so the training view rendered the amber
_REDUCED_BANNER: "keep the session controlled, don't push to failure". On a day
the engine itself scored every metric green, that sentence is false.

THE CLAMP IS NOT THE BUG AND IS NOT CHANGED BY ANY OF THIS. A capped day stays
capped; these tests assert the numbers still come down. What changes is that
the athlete is no longer told he is under-recovered when the engine believes he
is not.

Two failure directions, and only one of them is safe:
  * saying "recovered" on a genuinely bad day  -> dangerous, must be impossible
  * saying "capped" on a good day              -> merely honest
so an unknown driver falls through to the warning wording.
"""

from __future__ import annotations

import pytest

from services import engine, sessions as sess


GREEN = {"overall": "green", "status": "ok", "data_days": 30}
YELLOW = {"overall": "yellow", "status": "ok", "data_days": 30}
RED = {"overall": "red", "status": "ok", "data_days": 30}
NO_ACWR = {"acwr": None, "status": "unknown", "exceeds_ceiling": False,
           "hard_locked": False}


def _directive(traffic, injury=1.0, acwr=None, obs=0, stage=2):
    return engine.volume_recommendation(traffic, acwr or NO_ACWR, stage, obs, injury)


# ─── every branch says what drove it ──────────────────────────────────────

@pytest.mark.parametrize("traffic,injury,acwr,obs,expected", [
    (GREEN,  1.00, None, 0, engine.DRIVER_INJURY_WEIGHT),
    (GREEN,  0.10, None, 0, engine.DRIVER_NONE),
    (YELLOW, 0.10, None, 0, engine.DRIVER_BIOMETRICS),
    (RED,    0.10, None, 0, engine.DRIVER_BIOMETRICS),
    (GREEN,  0.10, {"acwr": 1.9, "hard_locked": True, "ceiling": 1.3,
                    "status": "overreach", "exceeds_ceiling": True}, 0, engine.DRIVER_ACWR),
    (GREEN,  0.10, None, 5, engine.DRIVER_OBSERVATION),
])
def test_every_directive_names_its_driver(traffic, injury, acwr, obs, expected):
    assert _directive(traffic, injury, acwr, obs)["driver"] == expected


def test_no_directive_branch_can_omit_a_driver():
    """A directive that cannot say what drove it gets the conservative
    wording, so an omission is safe — but it is still a bug, and silence here
    would hide it."""
    cases = [
        _directive(GREEN, 1.0), _directive(GREEN, 0.1), _directive(YELLOW, 0.1),
        _directive(RED, 0.1), _directive(GREEN, 0.1, obs=3),
        _directive({"overall": "grey", "status": "insufficient_data", "data_days": 2}, 0.1),
        _directive(GREEN, 0.1, acwr={"acwr": 1.9, "hard_locked": True, "ceiling": 1.3,
                                     "status": "overreach", "exceeds_ceiling": True}),
    ]
    for rec in cases:
        assert rec.get("driver"), f"no driver on {rec['label']!r}"


# ─── THE CONTRADICTION ────────────────────────────────────────────────────

def test_a_green_day_never_says_you_are_under_recovered():
    """The reported bug, stated as an invariant."""
    policy = sess.load_policy(_directive(GREEN, injury=0.95), {"volume_factor": 1.0})
    assert policy["reduced"] is True, "the cap still applies"
    assert policy["banner_kind"] != "warning", (
        "amber fatigue banner on a day every metric is green — the contradiction")
    assert "don't push to failure" not in policy["banner_text"]
    assert "green" in policy["banner_text"].lower()


def test_the_capped_banner_says_why_and_says_it_is_not_todays_readings():
    policy = sess.load_policy(_directive(GREEN, injury=0.95), {"volume_factor": 1.0})
    text = policy["banner_text"].lower()
    assert "injury" in text, "must name the driver"
    assert "not today" in text or "not because" in text, (
        "must separate the standing cap from today's readings")


def test_a_yellow_day_still_gets_the_fatigue_warning():
    """The safe direction must be preserved: a genuinely below-baseline day
    still says so, in amber."""
    policy = sess.load_policy(_directive(YELLOW, injury=0.1), {"volume_factor": 1.0})
    assert policy["banner_kind"] == "warning"
    assert "don't push to failure" in policy["banner_text"]


def test_a_red_day_still_gets_the_rest_banner():
    policy = sess.load_policy(_directive(RED, injury=0.1), {"volume_factor": 1.0})
    assert policy["banner_kind"] == "error"
    assert "Rest day" in policy["banner_text"]


def test_an_acwr_lock_is_a_recovery_driver_and_keeps_the_warning():
    """ACWR is a statement about accumulated load, i.e. about how he is —
    unlike the injury cap, which is about the tissue's timeline. So it keeps
    the amber warning rather than the reassuring blue.

    ⚠ It used to return signal_color "red", which routed it to the REST
    banner — "mobility and walking only, no loaded exercises" — on a branch
    whose own action text says "maintain current loads" and whose multiplier
    is 0.75, not 0.0. Same contradiction class as the reported one, found
    while fixing that, and dormant only because ACWR_ADVISORY_MODE forces
    hard_locked False. Corrected before enforcement is evaluated, not after.
    """
    acwr = {"acwr": 1.9, "hard_locked": True, "ceiling": 1.3,
            "status": "overreach", "exceeds_ceiling": True}
    rec = _directive(GREEN, 0.1, acwr=acwr)
    assert rec["multiplier"] == 0.75, "the lock caps, it does not prescribe rest"
    policy = sess.load_policy(rec, {"volume_factor": 1.0})
    assert policy["banner_kind"] == "warning"
    assert "No loaded" not in policy["banner_text"], (
        "a 0.75 multiplier must not render the rest banner")


def test_only_a_zero_multiplier_renders_the_rest_banner():
    """The general form of the bug above: the banner that forbids loaded
    exercises may only appear when the engine actually prescribed none."""
    for traffic, injury, acwr in [
        (RED, 0.1, None),
        (YELLOW, 0.1, None),
        (GREEN, 0.95, None),
        (GREEN, 0.1, {"acwr": 1.9, "hard_locked": True, "ceiling": 1.3,
                      "status": "overreach", "exceeds_ceiling": True}),
    ]:
        rec = _directive(traffic, injury, acwr)
        policy = sess.load_policy(rec, {"volume_factor": 1.0})
        if policy["banner_kind"] == "error":
            assert rec["multiplier"] == 0.0, (
                f"{rec['label']!r} shows the rest banner at multiplier "
                f"{rec['multiplier']}")


@pytest.mark.parametrize("driver", [None, "", "something_new"])
def test_an_unknown_driver_falls_back_to_the_warning(driver):
    """Under-warning about fatigue is the worse error. A directive that cannot
    say what drove it has not earned the reassurance."""
    policy = sess.load_policy(
        {"signal_color": "yellow", "multiplier": 0.85, "label": "X", "driver": driver},
        {"volume_factor": 1.0})
    assert policy["banner_kind"] == "warning"


# ─── the clamp is untouched ───────────────────────────────────────────────

def test_the_capped_day_still_clamps_the_numbers():
    """THE SAFETY PROPERTY. Everything above changes wording and colour; none
    of it may relax the ceiling."""
    policy = sess.load_policy(_directive(GREEN, injury=0.95), {"volume_factor": 1.2})
    assert policy["reduced"] is True
    assert policy["volume_factor"] == 1.0, (
        "a readiness streak must not inflate reps on a capped day")


def test_the_capped_day_and_the_warning_day_clamp_identically():
    capped = sess.load_policy(_directive(GREEN, injury=0.95), {"volume_factor": 1.2})
    warned = sess.load_policy(_directive(YELLOW, injury=0.10), {"volume_factor": 1.2})
    assert capped["reduced"] == warned["reduced"] is True
    assert capped["volume_factor"] == warned["volume_factor"] == 1.0


def test_the_multiplier_on_the_injury_branch_is_unchanged():
    """0.85 is a clinical constant, not presentation. Pinning it so a future
    wording change cannot quietly move the ceiling."""
    assert _directive(GREEN, injury=0.95)["multiplier"] == 0.85
    assert _directive(GREEN, injury=0.10)["multiplier"] == 1.05


def test_a_clear_day_shows_no_banner_at_all():
    policy = sess.load_policy(_directive(GREEN, injury=0.10), {"volume_factor": 1.0})
    assert policy["reduced"] is False
    assert policy["banner_kind"] == "" and policy["banner_text"] == ""


# ─── the view renders the third kind ──────────────────────────────────────

def test_the_training_view_renders_every_banner_kind():
    """A banner_kind the view does not branch on renders as SILENCE — the
    athlete would get a clamped session with no explanation at all, which is
    worse than the contradiction being fixed."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "views" / "training.py").read_text(encoding="utf-8")
    kinds = set()
    for traffic, injury in [(RED, 0.1), (YELLOW, 0.1), (GREEN, 0.95), (GREEN, 0.1)]:
        kinds.add(sess.load_policy(_directive(traffic, injury),
                                   {"volume_factor": 1.0})["banner_kind"])
    for kind in kinds - {""}:
        assert f'_policy["banner_kind"] == "{kind}"' in src, (
            f"load_policy can return banner_kind {kind!r} and the view never "
            f"renders it — the session would be clamped with no message")
