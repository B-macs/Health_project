"""The banner has to NAME the reading that stopped training.

traffic_light takes the WORST of four metrics rather than averaging them, so a
red light is always attributable to one specific reading. Until 2026-08-23 that
attribution never left the function: volume_recommendation printed one fixed
sentence ("Biometrics indicate systemic fatigue or distress") for all four
causes, and sessions.coach_message renders that string as the day's headline —
so the training screen was the one place the athlete could not find out why he
was being told not to train. It also discarded the specific temperature
sentence traffic_light already builds for a possible-illness reading.

The athlete's question that prompted this (2026-08-23): readiness read 66 and
the screen said no loaded training, with no way to tell which metric fired.
Readiness is a weighted average of nine components and the light is a worst-of
four — they are SUPPOSED to be able to disagree — but that only helps if the
light says what it saw.
"""
import pytest

from services import engine


def _rows(n: int = 28, **today):
    """n days of unremarkable readings, with `today` overlaid on the last."""
    rows = [
        {
            "date": f"2026-08-{i + 1:02d}",
            "hrv_ms": 55.0,
            "resting_heart_rate": 50.0,
            "sleep_duration_hours": 7.0,
            "oura_temperature_deviation": 0.0,
        }
        for i in range(n)
    ]
    rows[-1].update(today)
    return rows


def _directive(rows):
    tl = engine.traffic_light(rows)
    return tl, engine.volume_recommendation(
        tl, {"hard_locked": False, "acwr": 1.0, "ceiling": 1.3}, 2, 0, 0.3
    )


# ── Each of the four metrics names itself ────────────────────────────────────

@pytest.mark.parametrize("today,key,must_contain", [
    ({"hrv_ms": 38.0},                     "hrv_ms",                     "HRV"),
    ({"resting_heart_rate": 64.0},         "resting_heart_rate",         "resting heart rate"),
    ({"sleep_duration_hours": 4.9},        "sleep_duration_hours",       "Sleep"),
    ({"oura_temperature_deviation": 0.68}, "oura_temperature_deviation", "Body temperature"),
])
def test_each_red_metric_is_named_in_the_action(today, key, must_contain):
    tl, rec = _directive(_rows(**today))
    assert tl["overall"] == "red"
    assert tl["drivers"] == [key]
    # Case-insensitive: the clause is sentence-cased when it leads the action.
    assert must_contain.lower() in rec["action"].lower()
    # The generic sentence is gone, not merely appended to.
    assert "systemic fatigue" not in rec["action"]
    # The recommendation survives — this changes the WHY, never the what.
    assert "Rest is the better call" in rec["action"]


def test_the_reading_and_its_baseline_are_both_quoted():
    """A percentage with no numbers behind it cannot be sanity-checked against
    the Insights table, which is the whole point of naming the driver."""
    _, rec = _directive(_rows(hrv_ms=38.0))
    assert "38 ms" in rec["action"]
    assert "28-day average" in rec["action"]


def test_direction_follows_the_metric_not_the_sign():
    """HRV falling and resting HR rising are both bad. The clause has to say
    which way the number actually moved, or it reads as nonsense."""
    _, low_hrv = _directive(_rows(hrv_ms=38.0))
    assert "below" in low_hrv["action"]
    _, high_rhr = _directive(_rows(resting_heart_rate=64.0))
    assert "above" in high_rhr["action"]


def test_temperature_quotes_no_baseline():
    """The reading IS a deviation from Oura's own personal norm, so there is no
    28-day ratio to quote — see the TEMP_DEVIATION_* block."""
    _, rec = _directive(_rows(oura_temperature_deviation=0.68))
    assert "0.68 °C above your normal" in rec["action"]
    assert "28-day average" not in rec["action"]


# ── Several at once ──────────────────────────────────────────────────────────

def test_every_metric_at_the_overall_signal_is_reported():
    """Reporting only the first would make the second disappear from the only
    place it is ever mentioned."""
    tl, rec = _directive(_rows(hrv_ms=38.0, resting_heart_rate=64.0))
    assert tl["drivers"] == ["hrv_ms", "resting_heart_rate"]
    assert "HRV" in rec["action"] and "resting heart rate" in rec["action"].lower()


def test_a_yellow_metric_is_not_reported_on_a_red_day():
    """Only metrics sitting AT the overall signal drive it. A yellow sleep
    reading did not stop training; a red HRV did."""
    tl, rec = _directive(_rows(hrv_ms=38.0, sleep_duration_hours=6.1))
    assert tl["metrics"]["sleep_duration_hours"]["signal"] == "yellow"
    assert tl["drivers"] == ["hrv_ms"]
    assert "Sleep" not in rec["action"]


# ── Silence where there is nothing to name ───────────────────────────────────

def test_green_names_nothing():
    tl, rec = _directive(_rows())
    assert tl["overall"] == "green"
    assert tl["drivers"] == [] and tl["driver_summary"] == ""


def test_a_missing_reading_is_never_narrated_as_a_cause():
    """Grey means NOT MEASURED. It cannot turn the light red (grey outranks
    yellow in _SIGNAL_PRIORITY) and it must not appear as a reason."""
    tl = engine.traffic_light(_rows(hrv_ms=None))
    assert tl["overall"] == "grey"
    assert tl["drivers"] == [] and tl["driver_summary"] == ""


def test_metric_reason_is_empty_for_green_grey_and_missing():
    assert engine.metric_reason("hrv_ms", {"signal": "green", "value": 55}) == ""
    assert engine.metric_reason("hrv_ms", {"signal": "grey", "value": None}) == ""
    assert engine.metric_reason("hrv_ms", {"signal": "red", "value": None}) == ""


# ── Yellow gets the same treatment ───────────────────────────────────────────

def test_yellow_names_its_driver_too():
    tl, rec = _directive(_rows(hrv_ms=48.0))
    assert tl["overall"] == "yellow"
    assert "HRV" in rec["action"]
    assert "Scale total volume down" in rec["action"]


# ── Drift is a statement about the baseline, not about a reading ─────────────

def test_drift_downgrade_attributes_to_drift_not_to_a_metric():
    """A drift downgrade fires only when every reading is green, so there is no
    metric to name — the drift message is the honest attribution."""
    prior = [
        {"date": f"2026-05-{i + 1:02d}", "hrv_ms": 80.0,
         "resting_heart_rate": 46.0, "sleep_duration_hours": 8.0,
         "oura_temperature_deviation": 0.0}
        for i in range(40)
    ]
    tl = engine.traffic_light(_rows(), drift_rows=prior + _rows())
    if not tl["drift_applied"]:
        pytest.skip("drift guard did not fire on this fixture")
    assert tl["overall"] == "yellow"
    assert tl["drivers"] == []
    assert tl["driver_summary"] == tl["drift"]["message"]


# ── The instruction is unchanged by any of this ──────────────────────────────

def test_naming_the_driver_changes_no_number():
    """This commit changes a sentence. The multiplier, the signal colour and
    the label are exactly what they were."""
    _, rec = _directive(_rows(hrv_ms=38.0))
    assert rec["multiplier"] == 0.0
    assert rec["signal_color"] == "red"
    assert rec["label"] == "REST / DELOAD"
    assert rec["driver"] == engine.DRIVER_BIOMETRICS


# ── The message must not claim more than the app actually does ───────────────
#  Athlete, 2026-08-23: "soften the message, don't change the loaded work."
#
#  A red day clamps every weight, rep and band tier to the last completed
#  session and caps volume at 100%. It does NOT remove an exercise, gate the
#  Start button or zero anything -- load_policy reads the engine's 0.0
#  multiplier as a reason string, never as a factor. The old wording ("No
#  loaded training" / "No loaded exercises") described a behaviour that has
#  never existed, on the one screen where the athlete would act on it.

from services import sessions  # noqa: E402


def test_the_red_directive_does_not_assert_what_the_screen_will_do():
    _, rec = _directive(_rows(hrv_ms=38.0))
    assert "No loaded training" not in rec["action"]
    assert "Rest is the better call" in rec["action"]


def test_the_rest_banner_does_not_promise_an_unloaded_session():
    """The session below is fully loaded, merely held. Saying otherwise is the
    contradiction this replaced."""
    assert "No loaded exercises" not in sessions._REST_BANNER
    assert "held at your last session" in sessions._REST_BANNER


def test_the_rest_banner_still_recommends_rest():
    """Softening the CLAIM must not soften the ADVICE -- the metrics said rest
    and the banner still has to say so first."""
    assert sessions._REST_BANNER.startswith("Rest is the better call today")
    assert "mobility and walking" in sessions._REST_BANNER


def test_a_red_day_still_clamps_and_still_reads_as_an_error():
    """The whole point: the wording moved, the behaviour did not."""
    _, rec = _directive(_rows(hrv_ms=38.0))
    policy = sessions.load_policy(rec, {"volume_factor": 1.12, "description": "streak"})
    assert policy["reduced"] is True
    assert policy["volume_factor"] == 1.0      # the +12% proposal is refused
    assert policy["banner_kind"] == "error"
    assert policy["banner_text"] == sessions._REST_BANNER


def test_clamping_is_unchanged_by_the_new_wording():
    """clamp_to_ceiling is what actually holds the numbers, and it runs off
    policy["reduced"] — which a red day still sets. Exercised directly rather
    than through resolve_prescription so this pins the clamp itself, not the
    seeding fixture around it."""
    _, rec = _directive(_rows(hrv_ms=38.0))
    policy = sessions.load_policy(rec, {"volume_factor": 1.0})
    assert policy["reduced"] is True

    proposed = {"weight_kg": 15.0, "reps": 11}
    ceiling  = {"weight_kg": 12.5, "reps": 10}
    held = sessions.clamp_to_ceiling(proposed, ceiling)
    assert held["weight_kg"] == 12.5 and held["reps"] == 10
    assert set(held["clamped"]) == {"weight_kg", "reps"}
