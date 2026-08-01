"""Tests for the two 2026-08-01 traffic-light additions:

  1. body-temperature deviation as a fourth metric, scored against ABSOLUTE
     cut points rather than a rolling baseline
  2. the baseline-drift guard, which catches "green" quietly coming to mean
     "consistently as bad as recently"

Both are one-way-stricter by construction, and the tests below pin that
property specifically — it is the whole reason they were safe to add to a
safety-relevant path (CLAUDE.md: never weaken a guardrail).
"""

from services import engine


def _rows(n, hrv=60.0, rhr=55.0, sleep=7.5, temp=None):
    row = {"hrv_ms": hrv, "resting_heart_rate": rhr, "sleep_duration_hours": sleep}
    if temp is not None:
        row["oura_temperature_deviation"] = temp
    return [dict(row) for _ in range(n)]


# ─── Temperature deviation as a fourth metric ───────────────────────────────

def test_temperature_metric_is_present_even_when_the_reading_is_absent():
    tl = engine.traffic_light(_rows(7))
    m = tl["metrics"]["oura_temperature_deviation"]
    assert m["signal"] == "grey"
    assert m["value"] is None
    assert m["unit"] == "°C"


def test_missing_temperature_does_not_grey_the_overall_light():
    """Temperature is Oura-exclusive; the Garmin 645 reports no skin temp on
    53/53 archived nights. A device gap must not degrade the light the way a
    physiological signal does."""
    tl = engine.traffic_light(_rows(7))
    assert tl["overall"] == "green"
    assert tl["volume_multiplier_from_traffic"] == 1.0


def test_temperature_below_the_yellow_cut_point_stays_green():
    rows = _rows(7, temp=0.0)
    rows[-1]["oura_temperature_deviation"] = engine.TEMP_DEVIATION_YELLOW_C - 0.01
    tl = engine.traffic_light(rows)
    assert tl["metrics"]["oura_temperature_deviation"]["signal"] == "green"
    assert tl["overall"] == "green"


def test_temperature_at_the_yellow_cut_point_is_yellow():
    rows = _rows(7, temp=0.0)
    rows[-1]["oura_temperature_deviation"] = engine.TEMP_DEVIATION_YELLOW_C
    tl = engine.traffic_light(rows)
    assert tl["metrics"]["oura_temperature_deviation"]["signal"] == "yellow"
    assert tl["overall"] == "yellow"
    assert tl["volume_multiplier_from_traffic"] == 0.75


def test_temperature_at_the_red_cut_point_is_red_and_forces_rest():
    rows = _rows(7, temp=0.0)
    rows[-1]["oura_temperature_deviation"] = engine.TEMP_DEVIATION_RED_C
    tl = engine.traffic_light(rows)
    assert tl["metrics"]["oura_temperature_deviation"]["signal"] == "red"
    assert tl["overall"] == "red"
    assert tl["volume_multiplier_from_traffic"] == 0.0

    rec = engine.volume_recommendation(tl, {"hard_locked": False, "acwr": 0.9},
                                        stage=1, observation_days_remaining=0,
                                        injury_weight_val=0.1)
    assert rec["label"] == "REST / DELOAD"
    assert rec["multiplier"] == 0.0


def test_a_cool_deviation_is_never_penalised():
    """One-sided on purpose: below-norm temperature is not a training risk,
    so this metric can only ever make the light stricter."""
    rows = _rows(7, temp=0.0)
    rows[-1]["oura_temperature_deviation"] = -1.2
    tl = engine.traffic_light(rows)
    assert tl["metrics"]["oura_temperature_deviation"]["signal"] == "green"
    assert tl["overall"] == "green"


def test_temperature_is_not_scored_against_a_rolling_baseline():
    """A week of fever must not become the new normal. Every day sits at the
    red cut point, so a ratio-to-baseline metric would read today as
    perfectly average; the absolute cut point still fires."""
    rows = _rows(10, temp=engine.TEMP_DEVIATION_RED_C)
    tl = engine.traffic_light(rows)
    assert tl["metrics"]["oura_temperature_deviation"]["baseline_28d"] is None
    assert tl["overall"] == "red"


def test_red_temperature_message_names_the_reading():
    rows = _rows(7, temp=0.0)
    rows[-1]["oura_temperature_deviation"] = 0.65
    tl = engine.traffic_light(rows)
    assert "0.65" in tl["message"]


# ─── Baseline-drift guard ───────────────────────────────────────────────────

def test_drift_reports_insufficient_data_on_a_short_history():
    d = engine.baseline_drift(_rows(28))
    assert d["status"] == "insufficient_data"
    assert d["drifted"] is False


def test_drift_is_a_noop_for_callers_that_pass_only_a_28_day_window():
    """Existing callers hand traffic_light ~28 rows and pass no drift_rows.
    They must see exactly the behaviour they saw before the guard existed."""
    tl = engine.traffic_light(_rows(28))
    assert tl["drift"]["status"] == "insufficient_data"
    assert tl["drift_applied"] is False
    assert tl["overall"] == "green"


def test_drift_detects_a_declining_baseline_and_downgrades_green_to_yellow():
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=60.0, sleep=8.0)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=48.0, sleep=6.8)   # -20%, -15%
    tl = engine.traffic_light(recent, drift_rows=prior + recent)

    # Today matches its own 28-day baseline exactly, so all three ratio
    # metrics are green — the decline is invisible to them by construction.
    assert tl["metrics"]["hrv_ms"]["signal"] == "green"
    assert tl["drift"]["drifted"] is True
    assert tl["drift"]["severity"] == "severe"
    assert tl["drift_applied"] is True
    assert tl["overall"] == "yellow"
    assert tl["volume_multiplier_from_traffic"] == 0.75


def test_drift_leaves_a_stable_baseline_alone():
    prior  = _rows(engine.DRIFT_PRIOR_DAYS)
    recent = _rows(engine.DRIFT_RECENT_DAYS)
    tl = engine.traffic_light(recent, drift_rows=prior + recent)
    assert tl["drift"]["drifted"] is False
    assert tl["drift"]["severity"] == "none"
    assert tl["overall"] == "green"


def test_drift_adverse_pct_is_signed_so_positive_always_means_worse():
    """RHR rising and HRV falling are both bad but move in opposite raw
    directions; adverse_pct normalises that."""
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=60.0, rhr=50.0)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=54.0, rhr=55.0)
    d = engine.baseline_drift(prior + recent)
    assert d["metrics"]["hrv_ms"]["delta_pct"] < 0
    assert d["metrics"]["hrv_ms"]["adverse_pct"] > 0
    assert d["metrics"]["resting_heart_rate"]["delta_pct"] > 0
    assert d["metrics"]["resting_heart_rate"]["adverse_pct"] > 0


def test_an_improving_baseline_is_not_drift():
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=48.0, sleep=6.5)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=60.0, sleep=8.0)
    d = engine.baseline_drift(prior + recent)
    assert d["drifted"] is False
    assert all(not m["adverse"] for m in d["metrics"].values())


def test_one_moderate_metric_alone_does_not_downgrade():
    """DRIFT_MODERATE_PCT on a single metric is noted but not acted on; it
    takes one severe metric or two moderate ones."""
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=60.0)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=60.0 * (1 - 0.07))   # -7%
    d = engine.baseline_drift(prior + recent)
    assert d["severity"] == "moderate"
    assert d["drifted"] is False


def test_two_moderate_metrics_do_downgrade():
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=60.0, sleep=8.0)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=60.0 * (1 - 0.07),
                    sleep=8.0 * (1 - 0.07))
    d = engine.baseline_drift(prior + recent)
    assert d["drifted"] is True


def test_drift_never_downgrades_a_yellow_light_to_red():
    """Drift is chronic context, not an acute reading: it justifies holding
    volume, never prescribing rest."""
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=60.0, sleep=8.0)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=48.0, sleep=6.8)
    recent[-1]["hrv_ms"] = 48.0 * 0.85          # today also -15% vs its own baseline
    tl = engine.traffic_light(recent, drift_rows=prior + recent)
    assert tl["metrics"]["hrv_ms"]["signal"] == "yellow"
    assert tl["overall"] == "yellow"
    assert tl["drift_applied"] is False          # already yellow; nothing to apply


def test_drift_never_upgrades_a_red_light():
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=60.0, sleep=8.0)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=48.0, sleep=6.8)
    recent[-1]["hrv_ms"] = 48.0 * 0.60
    tl = engine.traffic_light(recent, drift_rows=prior + recent)
    assert tl["overall"] == "red"
    assert tl["drift_applied"] is False


def test_drift_rows_does_not_leak_into_the_baseline_used_for_today():
    """drift_rows is for the guard only. The 28-day baseline the three ratio
    metrics score against must still come from biometric_rows."""
    prior  = _rows(engine.DRIFT_PRIOR_DAYS, hrv=200.0)
    recent = _rows(engine.DRIFT_RECENT_DAYS, hrv=60.0)
    with_drift    = engine.traffic_light(recent, drift_rows=prior + recent)
    without_drift = engine.traffic_light(recent)
    assert (with_drift["metrics"]["hrv_ms"]["baseline_28d"]
            == without_drift["metrics"]["hrv_ms"]["baseline_28d"] == 60.0)
