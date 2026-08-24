"""Home and Training cannot describe different days.

2026-08-23, the athlete: "I saw 66 but then saw reduce load in training ... I
dont want to be suprised when I see the deload statement in training."

Neither screen was wrong. THEY SHARED NO NUMBER AT ALL. Home's card shows
readiness.compute_readiness_trend (an EMA over ~14 days); the training decision
buckets the RAW compute_readiness, which that day read 56.2 against the trend's
66; and views/training.py displays no readiness figure of any kind. So the fix
was not reconciling two numbers -- it was putting the DECISION on Home.

These tests hold that shut.
"""

import ast
import itertools
from pathlib import Path

import pytest

from services import engine, sessions, verdict as vd

ROOT = Path(__file__).resolve().parent.parent

GREEN = {"overall": "green", "status": "ok", "data_days": 30, "drivers": [], "metrics": {}}
YELLOW = {**GREEN, "overall": "yellow"}
RED = {**GREEN, "overall": "red"}
ACWR_OK = {"hard_locked": False, "acwr": 1.0, "ceiling": 1.3}


def _directive(traffic, injury=0.1, acwr=None, obs=0):
    return engine.volume_recommendation(traffic, acwr or ACWR_OK, 2, obs, injury)


#: Every distinct day the engine can produce.
_BRANCHES = [
    ("red", _directive(RED)),
    ("yellow", _directive(YELLOW)),
    ("injury cap", _directive(GREEN, injury=0.95)),
    ("clear", _directive(GREEN)),
    ("observation", _directive(GREEN, obs=3)),
]
_MODIFIERS = [
    {"volume_factor": 1.0},
    {"volume_factor": 1.12, "description": "three strong days"},
    {"volume_factor": 0.75, "description": "low readiness"},
    {},
]


# ─────────────────────────────────────────────────────────────────────────────
#  One sentence exists in the process
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,directive", _BRANCHES)
@pytest.mark.parametrize("modifier", _MODIFIERS)
def test_both_screens_print_the_same_string_object(name, directive, modifier):
    """IDENTITY, not equality. The verdict hands on load_policy's own string
    rather than re-authoring it, so the two screens cannot drift apart through
    someone editing one copy."""
    policy = sessions.load_policy(directive, modifier)
    v = vd.today_verdict(directive, modifier)
    assert v.banner_text is policy["banner_text"]
    assert v.banner_kind == policy["banner_kind"]


def test_neither_screen_re_authors_the_banner_text():
    """A source scan. If either view held the sentence as a literal, editing
    services/sessions.py would silently leave the other screen behind."""
    for view in ("app.py", "views/training.py"):
        src = (ROOT / view).read_text(encoding="utf-8")
        for literal in ("Rest is the better call today",
                        "Reduced load today",
                        "Your recovery metrics are green"):
            assert literal not in src, f"{view} re-authors {literal!r}"


# ─────────────────────────────────────────────────────────────────────────────
#  One cache entry, not two identical ones
# ─────────────────────────────────────────────────────────────────────────────

def test_the_cached_reader_is_one_function_object():
    """⚠ Two identically-coded @st.cache_data functions are TWO INDEPENDENT
    CACHE ENTRIES. Home fills at 09:00, Training at 09:31 after a sync lands,
    and the screens disagree with byte-identical source. That is why
    _engine_directive was MOVED to today.py rather than copied into app.py."""
    src = (ROOT / "today.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    defs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    for name in ("today_directive", "today_readiness_modifier", "today_readiness_raw"):
        assert defs.count(name) == 1, name

    training = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "def _engine_directive" not in training
    assert "def _bio_for_readiness" not in training


def test_training_reads_the_shared_verdict_rather_than_building_its_own():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "today.today_verdict()" in src
    assert "sess.load_policy(" not in src, (
        "the view must not call load_policy directly -- that is a second "
        "decision the other screen never sees")


# ─────────────────────────────────────────────────────────────────────────────
#  A hold-back day cannot reach Home silently — THE REPORTED BUG
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,directive", _BRANCHES)
@pytest.mark.parametrize("modifier", _MODIFIERS)
def test_a_reduced_day_always_carries_a_badge_and_a_line(name, directive, modifier):
    v = vd.today_verdict(directive, modifier)
    if v.reduced:
        assert v.badge, f"{name} clamps the session and Home shows no badge"
        assert v.banner_text, f"{name} clamps the session and Home shows no line"
        assert v.has_something_to_say


def test_a_clear_day_says_nothing_rather_than_reassuring():
    v = vd.today_verdict(_directive(GREEN), {"volume_factor": 1.0})
    assert v.reduced is False
    assert v.badge == "" and v.banner_text == ""
    assert v.has_something_to_say is False


def test_home_never_borrows_the_bright_signal_palette():
    """#FF4B4B on a 460px hero card is an alarm. The requirement was "not
    surprised", not "alarmed"."""
    assert set(vd.HOME_TONES.values()).isdisjoint(set(engine.SIGNAL_COLORS.values()))
    assert set(vd.HOME_TONES.values()) <= {"#6BAF8B", "#BFA06A", "#C47878"}
    assert "SIGNAL_COLORS" not in (ROOT / "app.py").read_text(encoding="utf-8")


def test_the_line_renders_after_the_button_not_between_it_and_the_card():
    """⚠ _NAV_BUTTON_CSS pulls the invisible hit target up 464px over the
    IMMEDIATELY PRECEDING element. Anything emitted between the card markdown
    and its button drags the button onto the wrong element and the card
    silently stops being tappable."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    button = src.index('st.button(f"Open {_cview} detail"')
    line = src.index('if _cview == "readiness" and _verdict_html:')
    assert line > button, "the verdict line must come AFTER the button"


# ─────────────────────────────────────────────────────────────────────────────
#  WARN-ONLY — the centrepiece
# ─────────────────────────────────────────────────────────────────────────────

_NOISE = ("", "Your HRV has come down 4 nights running on the ring.", "x" * 5000)
_DISPLAYS = (None, 0.0, 66.0, 100.0)
_RAWS = (None, 0.0, 56.2, 99.0)

_DECISION_FIELDS = ("reduced", "banner_kind", "banner_text", "driver",
                    "standing_cap", "volume_factor", "reasons", "badge", "tone")


@pytest.mark.parametrize("name,directive", _BRANCHES)
def test_nothing_carried_can_move_the_decision(name, directive):
    """⚠ THE WHOLE POINT. The athlete asked for the 4-night HRV run to APPEAR
    without changing a prescribed weight, rep, volume factor or ceiling.

    Stronger than an import fence, because it tests BEHAVIOUR and survives
    someone later importing hrv_trend into services/verdict.py."""
    modifier = {"volume_factor": 1.0}
    base = vd.today_verdict(directive, modifier)
    for note, disp, raw in itertools.product(_NOISE, _DISPLAYS, _RAWS):
        other = vd.today_verdict(directive, modifier, readiness_display=disp,
                                 readiness_raw=raw, readiness_band="Optimal",
                                 hrv_note=note)
        for f in _DECISION_FIELDS:
            assert getattr(other, f) == getattr(base, f), (
                f"{f} moved on carried display data ({note[:20]!r}, {disp}, {raw})")


@pytest.mark.parametrize("name,directive", _BRANCHES)
@pytest.mark.parametrize("modifier", _MODIFIERS)
def test_the_verdict_changes_no_prescription(name, directive, modifier):
    """A widening for display may not alter what load_policy decided."""
    policy = sessions.load_policy(directive, modifier)
    v = vd.today_verdict(directive, modifier, hrv_note="HRV is falling.")
    assert v.volume_factor == policy["volume_factor"]
    assert v.reduced == policy["reduced"]
    assert v.reasons == tuple(policy["reasons"])


def test_the_hrv_note_never_appears_in_the_reasons_that_clamp():
    """services/sessions.py builds `reasons`, and `reduced = bool(reasons)`.
    ONE appended reason would turn a clear day into a clamped day and cap the
    volume factor at 1.0. That is a two-line future edit which reads as
    obviously helpful."""
    v = vd.today_verdict(_directive(GREEN), {"volume_factor": 1.12},
                         hrv_note="Your HRV has come down 4 nights running.")
    assert v.reduced is False
    assert v.volume_factor == 1.12          # the +12% survives untouched
    assert not any("hrv" in r.lower() for r in v.reasons)


def test_the_verdict_module_cannot_reach_the_trend_module():
    """The note arrives as an opaque string from today.py, which sits OUTSIDE
    services/ precisely so no guardrail module gains a name through which the
    device-dependent 60/40 combined figure could be reached."""
    tree = ast.parse((ROOT / "services" / "verdict.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.update(a.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            names.update((node.module or "").split("."))
            names.update(a.name for a in node.names)
    assert "hrv_trend" not in names


# ─────────────────────────────────────────────────────────────────────────────
#  The two readiness scales are recorded, not accidental
# ─────────────────────────────────────────────────────────────────────────────

def test_the_two_scales_grade_different_numbers_and_that_is_deliberate():
    """dashboard.readiness_meta bands the TREND at 85/70/50; the engine's
    buckets band the RAW score at 80/60/40. Equalising them would make them
    look aligned while still meaning different things -- worse than a visible
    difference. Recorded here so a future edit has to mean it."""
    from services import dashboard as dash

    assert [dash.readiness_meta(s)[2] for s in (90, 80, 60, 30)] == \
        ["Optimal", "Good", "Pay Attention", "Rest"]
    assert [engine._bucket_readiness(s) for s in (85, 70, 50, 30)] == \
        ["high", "normal", "below", "low"]


def test_the_verdict_keeps_the_two_scores_apart():
    v = vd.today_verdict(_directive(GREEN), {"volume_factor": 1.0},
                         readiness_display=66.0, readiness_raw=56.2,
                         readiness_band="Pay Attention")
    assert v.readiness_display == 66.0     # the card's number
    assert v.readiness_raw == 56.2         # what the engine bucketed
    assert v.readiness_band == "Pay Attention"


def test_the_drill_down_caption_explains_the_gap_only_when_there_is_one():
    assert "last night alone" in vd.readiness_scale_caption(66.1, 56.2)
    assert vd.readiness_scale_caption(56.2, 56.2) == ""
    assert vd.readiness_scale_caption(None, 56.2) == ""


# ─────────────────────────────────────────────────────────────────────────────
#  Degradation
# ─────────────────────────────────────────────────────────────────────────────

def test_a_failed_engine_read_silences_both_screens_together():
    """Grey means "no opinion" -- no banner on either screen. They go quiet
    TOGETHER, so they still cannot disagree."""
    v = vd.today_verdict({"signal_color": "grey", "label": "", "action": "",
                          "multiplier": 1.0}, {})
    assert v.reduced is False
    assert v.badge == "" and v.banner_text == ""


def test_none_inputs_do_not_raise():
    v = vd.today_verdict(None, None)
    assert v.reduced is False and v.banner_kind == ""


# ─────────────────────────────────────────────────────────────────────────────
#  The reported case
# ─────────────────────────────────────────────────────────────────────────────

def test_the_2026_08_23_report():
    """The athlete: "I saw 66 but then saw reduce load in training."

    A trend of 66 reads "Pay Attention" on the card. Under the old code that
    was the whole story Home told. Now the same render carries the badge and
    the sentence Training is about to show."""
    from services import dashboard as dash

    assert dash.readiness_meta(66.0)[2] == "Pay Attention"
    directive = _directive(GREEN, injury=0.95)          # standing injury cap
    v = vd.today_verdict(directive, {"volume_factor": 1.0},
                         readiness_display=66.0, readiness_raw=56.2,
                         readiness_band="Pay Attention",
                         hrv_note="Your HRV has come down 4 nights running on the ring.")
    assert v.reduced is True
    assert v.badge == "VOLUME HELD"
    assert v.has_something_to_say
    assert v.banner_text == sessions.load_policy(
        directive, {"volume_factor": 1.0})["banner_text"]
    # A green-metrics day must not tell him he is under-recovered.
    assert "under-recovered" not in v.banner_text.lower()
    assert v.hrv_note                        # ...and the run is still said


# ─────────────────────────────────────────────────────────────────────────────
#  Two numbers, both shown, and the one with consequences leads
# ─────────────────────────────────────────────────────────────────────────────
#  Athlete, 2026-08-23: "I dont like the way I have two different numbers for
#  readiness, I either want them put together or show them both."

def test_the_card_shows_both_numbers_side_by_side_with_titles():
    """Athlete, 2026-08-23: "show them both ... with daily and trend as the
    titles of each". DAILY leads because it is the number with consequences —
    engine.readiness_training_modifier buckets the raw score and the trend
    drives nothing."""
    import app as home

    r = home._card_html("READINESS", "", "<svg/>", "57", "Pay Attention",
                        "#BFA06A", "h", "d",
                        score_pair=(("DAILY", "57"), ("TREND", "66")))
    assert "DAILY" in r and "TREND" in r
    assert r.index(">57<") < r.index(">66<"), "daily must come first"
    assert "font-size:58px" not in r, "the single-number block must not also render"

    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "_arc_svg(_r_card, 100, r_col)" in src, "the gauge must track the card's number"
    assert "score_pair=_r_pair" in src


def test_the_other_two_cards_are_untouched_by_the_pair():
    """score_pair defaults to None, so strain and sleep render byte-identical
    markup to what they rendered before readiness gained a second figure."""
    import app as home

    a = home._card_html("STRAIN", "", "<svg/>", "12", "Hard", "#BFA06A", "h", "d")
    b = home._card_html("STRAIN", "", "<svg/>", "12", "Hard", "#BFA06A", "h", "d",
                        score_pair=None)
    assert a == b
    assert "font-size:58px" in a, "the single-number card keeps its 58px figure"
    assert "DAILY" not in a


def test_no_pair_is_shown_on_a_day_the_two_numbers_agree():
    """Two identical figures side by side would invent a distinction. The app
    only pairs them when they genuinely differ."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "round(_readiness_today) != round(_readiness_score)" in src


def test_the_trend_is_still_what_gets_persisted():
    """⚠ compute_daily_metrics_snapshot's readiness_score is written into
    Metrics History and plotted by the 30-day sparkline. Changing WHICH number
    the card leads with must not change WHICH number is stored, or ~57 rows
    become incomparable with every row after them."""
    import inspect

    from services import dashboard as dash

    body = inspect.getsource(dash.compute_daily_metrics_snapshot)
    assert "compute_readiness_trend" in body
    assert "readiness_score = _readiness.compute_readiness_trend" in body


def test_the_two_numbers_are_never_averaged_into_a_third():
    """Averaging them would produce a figure that is neither today's score nor
    the fortnight's, and would break the r=0.992 agreement with Oura that
    MODEL_VERSION 2 was validated against."""
    v = vd.today_verdict(_directive(GREEN), {"volume_factor": 1.0},
                         readiness_display=66.0, readiness_raw=56.2)
    assert v.readiness_display == 66.0
    assert v.readiness_raw == 56.2
    assert not hasattr(v, "readiness_combined")
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    for forbidden in ("_readiness_score + _readiness_today",
                      "(_readiness_score + _readiness_today)"):
        assert forbidden not in src


def test_the_daily_number_is_computed_for_the_selected_date():
    """⚠ Home renders a PAST day whenever the `d` query param is set.
    today.today_readiness_raw() always answers for date.today(), so using it
    for the card would pair a past day's trend with today's daily score under
    one pair of titles — two different dates, no way to tell."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "for_date=selected_date, bio_rows=_bio_rows" in src


def test_todays_displayed_daily_is_the_number_the_engine_bucketed():
    """⚠ compute_readiness reads a WINDOW, and the score moves with how wide
    it is: measured 2026-08-23, 56.7 over the engine's 14 days against 56.2
    over the card's 60. Invisible today (both "56", both "below"); near a
    bucket edge the card would show one number while the session was decided
    on another."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "_readiness_today = today.today_readiness_raw()" in src, (
        "today's daily must come from the engine's own reader")
    assert "if is_today:" in src


def test_the_verdict_only_renders_on_today():
    """The verdict describes TODAY's session. Under a card the athlete has
    navigated back to, it would attach a live training decision to a day that
    is already over."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    i = src.index("_verdict = None\nif is_today:")
    assert i > 0, "the verdict must be gated on is_today"
    assert src.index("today.today_verdict(") > i
