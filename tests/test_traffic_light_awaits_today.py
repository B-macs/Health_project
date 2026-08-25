"""The light may not grade a day it has no reading for.

Athlete, 2026-08-25, on Home showing "Awaiting Data" and REDUCED LOAD in the
same card: "reduced load must only come up after the decision is made from the
data. not before."

Both halves of that screen were computed correctly and from different rules
about what "today" means. readiness.compute_readiness refuses to score a date
that carries no measurement of its own; engine.traffic_light took
`biometric_rows[-1]` and graded it whatever morning it belonged to. Between
midnight and the ring uploading, the second one was still grading Sunday.

The fix is engine.traffic_light's `for_date`. These tests pin four things:

  * the OLD behaviour survives when for_date is omitted, because
    services/dashboard.py's fusion shadow report compares two row SETS and is
    not judging a calendar day at all;
  * a stale newest row, or one carrying no scored reading, yields grey;
  * grey never becomes a load decision — no badge, no clamp;
  * the two callers that carry a load decision actually pass for_date.

⚠ NO CLAMP, BUT NOT SILENCE EITHER — and that second half was settled a few
hours after the first. The athlete's call on the NUMBERS stands: a day with no
reading gets no badge and no ceiling, the same as every day below MIN_DAYS, and
test_no_reading_does_not_assert_all_clear pins that grey never becomes a green
light. What changed is that the absence is now SAID, in one sentence both
screens print — see section 5. Silence turned out to be the wrong shape,
because Home's card renders its own "Awaiting Data" state and the training
screen had no equivalent, so the same absence read as a normal session there.
"""

from datetime import date, timedelta

import pytest

from services import engine, sessions, verdict


# ─────────────────────────────────────────────────────────────────────────────
#  Fixtures — a healthy baseline, so anything the light says is about the
#  newest row rather than about a thin history.
# ─────────────────────────────────────────────────────────────────────────────

TODAY = date(2026, 8, 25)


def _rows(n: int = 28, last_day: date = TODAY, **last_row):
    """n days of unremarkable readings ending on `last_day`.

    `last_row` overrides fields on the final row only — that is the row the
    light scores.
    """
    out = []
    for i in range(n - 1, -1, -1):
        d = last_day - timedelta(days=i)
        out.append({
            "date": d.isoformat(),
            "hrv_ms": 50.0,
            "resting_heart_rate": 55.0,
            "sleep_duration_hours": 7.5,
            "oura_temperature_deviation": 0.0,
        })
    out[-1].update(last_row)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  1. The default is unchanged.
# ─────────────────────────────────────────────────────────────────────────────

def test_omitting_for_date_keeps_the_old_last_row_is_today_reading():
    """Every pre-existing caller must see byte-identical behaviour.

    services/dashboard.py hands this two DIFFERENT row sets to compare against
    each other; a date gate there would answer a question nobody asked.
    """
    stale = _rows(last_day=TODAY - timedelta(days=2), hrv_ms=20.0)
    tl = engine.traffic_light(stale)
    assert tl["status"] == engine.STATUS_OK
    assert tl["overall"] == "red"
    assert "hrv_ms" in tl["drivers"]


def test_healthy_day_is_judged_normally_when_for_date_matches():
    rows = _rows(last_day=TODAY)
    tl = engine.traffic_light(rows, for_date=TODAY)
    assert tl["status"] == engine.STATUS_OK
    assert tl["overall"] == "green"


def test_for_date_does_not_change_a_day_that_has_its_own_reading():
    """The gate must be invisible on every day the app actually has data for —
    otherwise it is not a gate, it is a behaviour change."""
    rows = _rows(last_day=TODAY, hrv_ms=20.0)
    assert (engine.traffic_light(rows, for_date=TODAY)
            == engine.traffic_light(rows))


# ─────────────────────────────────────────────────────────────────────────────
#  2. The two ways a day can have nothing to judge.
# ─────────────────────────────────────────────────────────────────────────────

def test_stale_newest_row_is_not_graded_as_today():
    """THE REPORTED BUG. Sunday's reading is not a verdict on Tuesday."""
    stale = _rows(last_day=TODAY - timedelta(days=2), hrv_ms=20.0)
    tl = engine.traffic_light(stale, for_date=TODAY)
    assert tl["status"] == engine.STATUS_AWAITING_DATA
    assert tl["overall"] == "grey"
    assert tl["volume_multiplier_from_traffic"] == 1.0
    # A missing reading is not a cause and must never be narrated as one.
    assert tl["drivers"] == []
    assert tl["driver_summary"] == ""
    assert tl["metrics"] == {}
    # The date of what it DOES have, so callers never re-derive it.
    assert tl["latest_reading_date"] == (TODAY - timedelta(days=2)).isoformat()


def test_a_row_for_today_carrying_no_scored_reading_is_not_enough():
    """A morning check-in creates a row for today with no night in it. Before
    the gate, all four metrics greyed, _worst_signal resolved that in green's
    favour and the directive came out "All systems nominal.\""""
    rows = _rows(last_day=TODAY, hrv_ms=None, resting_heart_rate=None,
                 sleep_duration_hours=None, oura_temperature_deviation=None)
    rows[-1]["alcohol_units"] = 0          # the check-in's own field
    tl = engine.traffic_light(rows, for_date=TODAY)
    assert tl["status"] == engine.STATUS_AWAITING_DATA


@pytest.mark.parametrize("field", [
    "hrv_ms", "resting_heart_rate", "sleep_duration_hours",
    "oura_temperature_deviation",
])
def test_any_single_scored_reading_is_enough_to_judge(field):
    """Partial data still greys the individual metrics it is missing — that is
    pre-existing and correct. What it must NOT do is withhold the whole light,
    which would silence the engine on any night the ring recorded less than
    everything."""
    blanks = {k: None for k in engine._LIGHT_READING_FIELDS}
    blanks[field] = _rows()[-1][field]
    rows = _rows(last_day=TODAY, **blanks)
    assert engine.traffic_light(rows, for_date=TODAY)["status"] == engine.STATUS_OK


def test_too_little_history_still_wins_over_the_date_gate():
    """Below MIN_DAYS the engine is not activated at all, which is the more
    fundamental statement of the two and keeps its own message."""
    tl = engine.traffic_light(_rows(3, last_day=TODAY - timedelta(days=2)),
                              for_date=TODAY)
    assert tl["status"] == engine.STATUS_INSUFFICIENT_DATA


# ─────────────────────────────────────────────────────────────────────────────
#  3. End to end — grey reaches the screen as silence.
# ─────────────────────────────────────────────────────────────────────────────

def _verdict_for(rows, for_date):
    tl = engine.traffic_light(rows, for_date=for_date)
    acwr = engine.acwr([], stage=2)
    rec = engine.volume_recommendation(
        tl, acwr, stage=2,
        observation_days_remaining=engine.observation_days_remaining(tl["data_days"]),
        injury_weight_val=0.5,
    )
    return rec, verdict.today_verdict(rec, {"volume_factor": 1.0})


def test_no_reading_produces_no_load_decision():
    """The screenshot, made impossible. Home printed REDUCED LOAD under a card
    reading "Awaiting Data"; the badge is derived from banner_kind alone, and
    no kind that carries a badge is reachable without a reading.

    ⚠ This asserted `banner_kind == ""` until later the same day, when the
    athlete asked for the absence to be stated rather than merely not
    contradicted. The kind is "neutral" now and section 5 pins what it says.
    The property THIS test protects — a day with nothing to judge produces no
    load decision — is unchanged, and is the one that matters here."""
    stale = _rows(last_day=TODAY - timedelta(days=2), hrv_ms=20.0)
    rec, v = _verdict_for(stale, TODAY)

    assert rec["signal_color"] == "grey"
    assert rec["driver"] == engine.DRIVER_NO_DATA
    assert rec["multiplier"] == 1.0
    assert rec["label"] == "AWAITING TODAY'S READING"

    assert v.reduced is False
    assert v.badge == ""
    assert v.reasons == ()
    assert v.volume_factor == 1.0


def test_the_same_reading_arriving_today_does_produce_the_badge():
    """The other half of the requirement — the verdict is delayed, not
    deleted. The identical HRV reading, dated today, still says reduce."""
    fresh = _rows(last_day=TODAY, hrv_ms=20.0)
    rec, v = _verdict_for(fresh, TODAY)
    assert rec["signal_color"] == "red"
    assert v.reduced is True
    assert v.badge == verdict.BADGE_WORDS["error"]


def test_no_reading_does_not_assert_all_clear():
    """Silence, not reassurance. Going quiet is only safe while the app is not
    also telling him everything is fine — "All systems nominal. Apply standard
    progressive overload" off no data is the same error wearing green."""
    stale = _rows(last_day=TODAY - timedelta(days=2))
    rec, _ = _verdict_for(stale, TODAY)
    assert rec["label"] != "PROGRESSIVE OVERLOAD"
    assert rec["multiplier"] <= 1.0
    assert "nominal" not in rec["action"].lower()


def test_load_policy_holds_nothing_back_on_an_awaiting_day():
    """Pinned at the policy rather than through the verdict, because
    load_policy is what clamp_to_ceiling reads. The banner it now carries is a
    statement about the DATA; nothing here may become a statement about the
    numbers."""
    tl = engine.traffic_light(_rows(last_day=TODAY - timedelta(days=2),
                                    hrv_ms=20.0), for_date=TODAY)
    rec = engine.volume_recommendation(tl, engine.acwr([], stage=2), stage=2)
    policy = sessions.load_policy(rec, {"volume_factor": 1.0})
    assert policy["reduced"] is False
    assert policy["volume_factor"] == 1.0
    assert policy["reasons"] == []
    assert policy["banner_kind"] == "neutral"


# ─────────────────────────────────────────────────────────────────────────────
#  4. The callers cannot silently drop the argument again.
# ─────────────────────────────────────────────────────────────────────────────

#: Call sites deliberately NOT date-gated, with the reason. dashboard's pair
#: compares two row SETS against each other for the sleep-fusion shadow report
#: — neither is a claim about a calendar day, and gating them would answer a
#: question nobody asked.
_UNGATED_ALLOWED = {"services/dashboard.py": 2}


def test_every_decision_carrying_caller_passes_for_date():
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in list(root.glob("*.py")) + list((root / "views").glob("*.py")) \
            + list((root / "services").glob("*.py")):
        rel = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                     # pragma: no cover
            continue
        ungated = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name != "traffic_light":
                continue
            if not any(kw.arg == "for_date" for kw in node.keywords):
                ungated += 1
        if ungated and ungated != _UNGATED_ALLOWED.get(rel):
            offenders.append(f"{rel}: {ungated} ungated traffic_light call(s)")

    assert not offenders, (
        "engine.traffic_light without for_date grades the newest row it can "
        "find as if it were today. Pass for_date, or add the file to "
        "_UNGATED_ALLOWED with the reason: " + "; ".join(offenders)
    )


# ─────────────────────────────────────────────────────────────────────────────
#  5. "Nothing to judge" is said on BOTH screens, in one sentence.
# ─────────────────────────────────────────────────────────────────────────────
#  Athlete, 2026-08-25: "when there is no data in the home page, then no data
#  is message is presented in the training page."
#
#  Silence was the wrong shape. Home's readiness card renders its own "Awaiting
#  Data" state, so Home looked handled; the training screen had no equivalent
#  and fell through to whatever the directive's action string happened to be,
#  which on a grey day is not a load statement at all and read as a normal
#  session. Two screens inferring the same absence separately is how they came
#  to disagree about it.

def test_a_no_reading_day_produces_one_banner_for_both_screens():
    stale = _rows(last_day=TODAY - timedelta(days=2))
    rec, v = _verdict_for(stale, TODAY)

    assert v.banner_kind == "neutral"
    assert v.banner_text                      # ...and it is not empty
    # Home renders the line, which is the half the training banner mirrors.
    assert v.has_something_to_say is True
    # THE SAME STRING OBJECT, not a copy and not a re-authoring.
    assert v.banner_text is v.policy["banner_text"]


def test_the_no_reading_banner_names_both_dates():
    """The day with nothing, and the day of the last real reading. Those are
    the two facts that make it actionable rather than merely apologetic."""
    stale = _rows(last_day=TODAY - timedelta(days=2))
    _, v = _verdict_for(stale, TODAY)
    assert TODAY.isoformat() in v.banner_text
    assert (TODAY - timedelta(days=2)).isoformat() in v.banner_text


def test_an_empty_row_for_today_is_not_named_as_the_most_recent_reading():
    """A row can exist for today carrying nothing — a morning check-in makes
    one. Naming that date as "the most recent reading" in the same sentence
    that says there is no reading is a contradiction of its own."""
    blanks = {k: None for k in engine._LIGHT_READING_FIELDS}
    rows = _rows(last_day=TODAY, **blanks)
    tl = engine.traffic_light(rows, for_date=TODAY)
    assert tl["latest_reading_date"] == (TODAY - timedelta(days=1)).isoformat()
    assert tl["message"].count(TODAY.isoformat()) == 1, \
        "today must appear only as the day with nothing"


def test_the_no_reading_day_carries_no_badge_and_no_clamp():
    """⚠ IT IS NOT A LOAD DECISION. The athlete's choice was silence on the
    numbers; what changed is that the SILENCE is now explained rather than
    inferred. No badge — the card's own status label already reads "No
    Readings" directly above where the pill would sit."""
    stale = _rows(last_day=TODAY - timedelta(days=2))
    _, v = _verdict_for(stale, TODAY)
    assert v.reduced is False
    assert v.badge == ""
    assert v.volume_factor == 1.0


def test_a_real_reduction_still_wins_over_the_no_reading_notice():
    """The branch is reached only when nothing else had an opinion, so it can
    never mask one. If readiness computed and asked for less, that is a
    reduction off real data even where the light has none."""
    stale = _rows(last_day=TODAY - timedelta(days=2))
    tl = engine.traffic_light(stale, for_date=TODAY)
    rec = engine.volume_recommendation(tl, engine.acwr([], stage=2), stage=2)
    v = verdict.today_verdict(rec, {"volume_factor": 0.85,
                                    "description": "two low readiness days"})
    assert v.banner_kind == "warning"
    assert v.badge == verdict.BADGE_WORDS["warning"]


def test_the_training_view_renders_the_no_reading_kind():
    """A kind the view does not branch on renders as silence — which is the
    state this whole change exists to end."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[1]
           / "views" / "training.py").read_text(encoding="utf-8")
    assert 'verdict.banner_kind == "neutral"' in src


def test_the_headline_does_not_repeat_the_no_reading_banner():
    """The banner text IS the directive's action on this branch, so letting the
    headline print it too would say the same thing twice, once at 26px."""
    from services import sessions as sess

    stale = _rows(last_day=TODAY - timedelta(days=2))
    rec, v = _verdict_for(stale, TODAY)
    plan = {"objective": "Posterior Chain Strength", "phase": "Stage 2B"}
    headline, _ = sess.coach_message(rec, plan, v.policy)
    assert headline == plan["objective"]
    assert headline != v.banner_text
