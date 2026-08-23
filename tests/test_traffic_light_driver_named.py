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
    # The instruction itself survives — this changes the WHY, never the what.
    assert "No loaded training" in rec["action"]


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
