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
    # See tests/test_sessions.py's copy of this assertion: the banner was
    # reworded 2026-08-23, so this pins the banner's IDENTITY and its advice
    # rather than a phrase that is no longer in it.
    assert policy["banner_text"] == sess._REST_BANNER
    assert policy["banner_text"].startswith("Rest is the better call")


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

def _reachable_banner_kinds() -> set:
    kinds = set()
    for traffic, injury in [(RED, 0.1), (YELLOW, 0.1), (GREEN, 0.95), (GREEN, 0.1)]:
        kinds.add(sess.load_policy(_directive(traffic, injury),
                                   {"volume_factor": 1.0})["banner_kind"])
    return kinds - {""}


def test_the_training_view_renders_every_banner_kind():
    """A banner_kind the view does not branch on renders as SILENCE — the
    athlete would get a clamped session with no explanation at all, which is
    worse than the contradiction being fixed.

    Reads `verdict.banner_kind` — the view renders from the shared verdict
    rather than from its own policy dict, so that Home cannot print a different
    sentence. Matched without the leading underscore since 2026-08-25, when the
    block moved out of render()'s local `_verdict` and into
    _render_verdict_banner's parameter. The property this test protects is
    unchanged."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "views" / "training.py").read_text(encoding="utf-8")
    for kind in _reachable_banner_kinds():
        assert f'verdict.banner_kind == "{kind}"' in src, (
            f"load_policy can return banner_kind {kind!r} and the view never "
            f"renders it — the session would be clamped with no message")


# ─── and it renders it on the screen he is actually looking at ────────────

def test_the_day_overview_screen_renders_the_verdict_banner():
    """⚠ THE REPORTED BUG. Athlete, 2026-08-25, holding both screens at 08:03:
    Home read REDUCED LOAD, the training screen read "All systems nominal.
    Apply standard progressive overload: +2.5 kg."

    The banner block sat inline in render(), 77 lines BELOW the `st.stop()`
    that ends the day-overview screen — so the pre-session screen, the one
    actually read before training, never showed it. Rendering it only once you
    are already inside the session is rendering it after the decision it
    describes has been acted on.

    services/verdict.py exists so the two screens cannot describe different
    days. It cannot do that on a screen that does not render it.
    """
    import ast
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "views" / "training.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    def _calls(node, name):
        return [n for n in ast.walk(node)
                if isinstance(n, ast.Call)
                and getattr(n.func, "id", None) == name]

    defs = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_render_verdict_banner"]
    assert len(defs) == 1, "one banner renderer, or the two screens can drift again"

    overview = [n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_render_overview"]
    assert overview, "_render_overview vanished — re-point this test"
    assert _calls(overview[0], "_render_verdict_banner"), (
        "the day-overview screen must render the verdict banner; it st.stop()s "
        "before the in-session one is ever reached")

    # Two call sites total: the overview screen and the in-session flow.
    assert len(_calls(tree, "_render_verdict_banner")) >= 2, (
        "the in-session flow needs it too — it is a different screen")


def test_the_overview_headline_is_resolved_against_the_policy():
    """The banner alone is not enough. The headline is the DIRECTIVE's own
    sentence, and the directive is only one of load_policy's three inputs — so
    without the policy in hand it can still print "apply progressive overload"
    directly above a reduced-load banner."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "views" / "training.py").read_text(encoding="utf-8")
    assert "sess.coach_message(directive, today_plan, policy)" in src


def test_the_headline_never_asks_for_more_load_on_a_reduced_day():
    """The contradiction itself, at the function that produces the words.

    A green traffic light with a readiness modifier below 1.0 is a REDUCED day
    whose directive is still the overload sentence — the exact combination on
    screen on 2026-08-25."""
    plan = {"objective": "Posterior Chain Strength", "phase": "Stage 2B — Week 2"}
    directive = _directive(GREEN, injury=0.10)
    assert directive["multiplier"] > 1.0, "fixture must be the overload branch"

    policy = sess.load_policy(directive, {"volume_factor": 0.85})
    assert policy["reduced"] is True, "fixture must produce a reduced day"

    headline, _ = sess.coach_message(directive, plan, policy)
    assert headline == plan["objective"]
    for banned in ("progressive overload", "+2.5 kg", "nominal"):
        assert banned not in headline.lower()


def test_a_directive_that_reduced_the_day_itself_keeps_its_own_words():
    """Only the "add load" sentence is the contradiction. A yellow-biometrics
    or ACWR directive already says the right thing and NAMES THE READING —
    replacing it with the generic objective would throw away the one place the
    reason appears."""
    plan = {"objective": "Posterior Chain Strength", "phase": "Stage 2B — Week 2"}
    directive = _directive(YELLOW, injury=0.10)
    policy = sess.load_policy(directive, {"volume_factor": 1.0})
    assert policy["reduced"] is True

    headline, _ = sess.coach_message(directive, plan, policy)
    assert headline == directive["action"]


def test_omitting_the_policy_keeps_the_old_headline():
    """Any caller with no load decision in hand must be unaffected."""
    plan = {"objective": "Posterior Chain Strength", "phase": "Stage 2B — Week 2"}
    directive = _directive(GREEN, injury=0.10)
    assert (sess.coach_message(directive, plan)
            == sess.coach_message(directive, plan, None)
            == (directive["action"], plan["phase"]))


def test_home_renders_every_banner_kind_load_policy_can_emit():
    """⚠ A kind neither screen knows about renders as SILENCE, which is how
    both of this week's reports happened. Held wider than the reachable-kinds
    helper above, because that helper only walks traffic-light fixtures and
    "neutral" is reached through the DRIVER instead.

    Not every kind needs a badge — "neutral" deliberately has none, since the
    card's own status label already says it — but every kind needs a TONE, or
    _verdict_line renders the sentence with no left border and no colour.
    """
    from services import verdict as vd

    for kind in ("", "info", "warning", "error", "neutral"):
        assert kind in vd.HOME_TONES, f"Home has no tone for {kind!r}"
        assert kind in vd.BADGE_WORDS, f"Home has no badge entry for {kind!r}"

    # Every kind that CLAMPS must announce itself on the card.
    for kind in ("info", "warning", "error"):
        assert vd.BADGE_WORDS[kind], f"a clamping kind needs a badge: {kind!r}"


def test_home_carries_a_badge_for_every_banner_kind():
    """⚠ THE REPORTED BUG, GENERALISED. 2026-08-23: "I saw 66 but then saw
    reduce load in training." A kind Home has no badge word for renders as a
    reassuring number with nothing beside it, which is exactly how that
    happened. Home is now held to the same bar the training view is."""
    from services import verdict as vd

    for kind in _reachable_banner_kinds():
        assert vd.BADGE_WORDS.get(kind), f"Home has no badge for {kind!r}"
        assert vd.HOME_TONES.get(kind), f"Home has no tone for {kind!r}"
