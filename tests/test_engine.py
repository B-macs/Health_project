"""
Tests for services/engine.py's today-parameterization fix — the one required
logic change in this refactor (both functions previously called date.today()
directly instead of accepting it as a parameter). Full engine.py coverage
already exists in the ported tests.py suite; this file targets specifically
what changed.
"""

import ast
import math
from datetime import date, timedelta

from services import engine
from tests._legacy_check import check


def test_readiness_training_modifier_is_deterministic_given_explicit_today():
    bio_rows = [{"date": "2026-07-05", "hrv_ms": 45, "resting_heart_rate": 55,
                 "sleep_duration_hours": 7.5}]
    fixed_today = date(2026, 7, 7)
    r1 = engine.readiness_training_modifier(bio_rows, today=fixed_today)
    r2 = engine.readiness_training_modifier(bio_rows, today=fixed_today)
    assert r1 == r2


def test_readiness_training_modifier_defaults_to_real_today_when_omitted():
    # Doesn't raise, still returns a well-formed directive with no rows
    result = engine.readiness_training_modifier([])
    assert "volume_factor" in result


def test_acwr_is_deterministic_given_explicit_today():
    rows = [{"date": "2026-07-01", "total_au": 100.0}, {"date": "2026-07-05", "total_au": 150.0}]
    fixed_today = date(2026, 7, 7)
    r1 = engine.acwr(rows, stage=1, today=fixed_today)
    r2 = engine.acwr(rows, stage=1, today=fixed_today)
    assert r1 == r2
    assert len(r1["daily_au_28"]) == 28


def test_acwr_different_today_changes_the_calendar_window():
    rows = [{"date": "2026-07-01", "total_au": 100.0}]
    r1 = engine.acwr(rows, today=date(2026, 7, 7))
    r2 = engine.acwr(rows, today=date(2026, 8, 7))
    # A month later, that same logged day has fallen out of the 28-day window
    assert r1["daily_au_28"] != r2["daily_au_28"]


def test_acwr_defaults_to_real_today_when_omitted():
    result = engine.acwr([], stage=1)
    assert result["status"] == "insufficient_data"


def test_no_streamlit_import():
    tree = ast.parse(open(engine.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


# ── Ported verbatim from the old flat tests.py — engine.py constants/helpers ──


def test_engine_constants_and_helpers():
    check("MIN_OBSERVATION_DAYS is 14", engine.MIN_OBSERVATION_DAYS, 14)
    check("compute_session_au(7, 45) = 315", engine.compute_session_au(7, 45), 315.0)
    check("compute_session_au(10, 60) = 600", engine.compute_session_au(10, 60), 600.0)
    check("compute_session_au(1, 1) = 1", engine.compute_session_au(1, 1), 1.0)

    # Boundary: strict > 0.50 for red, strict > 0.20 for yellow
    check("injury_weight_signal(0.8)  = red",    engine.injury_weight_signal(0.8),  "red")
    check("injury_weight_signal(0.51) = red",    engine.injury_weight_signal(0.51), "red")
    check("injury_weight_signal(0.50) = yellow", engine.injury_weight_signal(0.50), "yellow")  # NOT > 0.50
    check("injury_weight_signal(0.49) = yellow", engine.injury_weight_signal(0.49), "yellow")
    check("injury_weight_signal(0.21) = yellow", engine.injury_weight_signal(0.21), "yellow")
    check("injury_weight_signal(0.20) = green",  engine.injury_weight_signal(0.20), "green")   # NOT > 0.20
    check("injury_weight_signal(0.19) = green",  engine.injury_weight_signal(0.19), "green")
    check("injury_weight_signal(0.0)  = green",  engine.injury_weight_signal(0.0),  "green")

    check("observation_days_remaining(0) = 14",  engine.observation_days_remaining(0), 14)
    check("observation_days_remaining(7) = 7",   engine.observation_days_remaining(7), 7)
    check("observation_days_remaining(14) = 0",  engine.observation_days_remaining(14), 0)
    check("observation_days_remaining(30) = 0",  engine.observation_days_remaining(30), 0)


def test_engine_injury_weight_decay():
    # e^(-0.05 * t)
    check("day 0  -> 1.0000", engine.injury_weight(0.05, 0),   1.0,    tol=1e-4)
    check("day 14 -> ~0.4966", engine.injury_weight(0.05, 14), math.exp(-0.7), tol=1e-4)
    check("day 28 -> ~0.2466", engine.injury_weight(0.05, 28), math.exp(-1.4), tol=1e-4)
    check("day 60 -> ~0.0498", engine.injury_weight(0.05, 60), math.exp(-3.0), tol=1e-4)
    check("negative days clamped to 0", engine.injury_weight(0.05, -5), 1.0, tol=1e-4)
    check("lambda=0 gives 1.0 always",       engine.injury_weight(0.0, 100), 1.0, tol=1e-4)


def _bio_rows(n, hrv, rhr, sleep):
    return [{"hrv_ms": hrv, "resting_heart_rate": rhr, "sleep_duration_hours": sleep}] * n


def test_engine_traffic_light():
    # Insufficient data
    tl_empty = engine.traffic_light([])
    check("no data -> overall grey",            tl_empty["overall"],  "grey")
    check("no data -> status insufficient_data",tl_empty["status"],   "insufficient_data")
    check("no data -> volume_mult 1.0",         tl_empty["volume_multiplier_from_traffic"], 1.0)

    # 6 identical days (below MIN_DAYS=7)
    tl_6 = engine.traffic_light(_bio_rows(6, 60, 55, 7.5))
    check("6 days -> still grey (< 7 required)", tl_6["overall"], "grey")

    # 7 days identical -> baseline = today = green
    tl_green = engine.traffic_light(_bio_rows(7, 60, 55, 7.5))
    check("7 days identical -> green",          tl_green["overall"], "green")
    check("green -> volume_mult 1.0",           tl_green["volume_multiplier_from_traffic"], 1.0)

    # Today's HRV 12% below 28d avg -> yellow (10-25% threshold)
    baseline_7 = _bio_rows(6, 60.0, 55, 7.5)
    today_12pct_drop = [{"hrv_ms": 52.8, "resting_heart_rate": 55, "sleep_duration_hours": 7.5}]
    tl_yellow = engine.traffic_light(baseline_7 + today_12pct_drop)
    check("HRV -12% from baseline -> yellow",   tl_yellow["overall"], "yellow")
    check("yellow -> volume_mult 0.75",         tl_yellow["volume_multiplier_from_traffic"], 0.75)

    # Today's HRV 30% below baseline -> red (>25% threshold)
    baseline_7b = _bio_rows(6, 60.0, 55, 7.5)
    today_30pct_drop = [{"hrv_ms": 42.0, "resting_heart_rate": 55, "sleep_duration_hours": 7.5}]
    tl_red = engine.traffic_light(baseline_7b + today_30pct_drop)
    check("HRV -30% from baseline -> red",      tl_red["overall"], "red")
    check("red -> volume_mult 0.0",             tl_red["volume_multiplier_from_traffic"], 0.0)

    # RHR higher is worse: today +15% above baseline -> yellow
    baseline_rhr = _bio_rows(6, 60, 55, 7.5)
    today_rhr_up = [{"hrv_ms": 60, "resting_heart_rate": int(55 * 1.15), "sleep_duration_hours": 7.5}]
    tl_rhr_y = engine.traffic_light(baseline_rhr + today_rhr_up)
    check("RHR +15% above baseline -> yellow",  tl_rhr_y["metrics"]["resting_heart_rate"]["signal"], "yellow")


def test_engine_acwr():
    # No data
    ac_empty = engine.acwr([], stage=1)
    check("no data -> acwr is None",         ac_empty["acwr"], None)
    check("no data -> Stage 1 ceiling 1.2",  ac_empty["ceiling"], 1.2)
    check("Stage 2 ceiling is 1.3",         engine.acwr([], stage=2)["ceiling"], 1.3)
    check("Stage 3 ceiling is 1.5",         engine.acwr([], stage=3)["ceiling"], 1.5)

    # Build 28 days of uniform 200 AU -> ACWR = 1.0 (optimal)
    today = date.today()
    uniform_rows = [{"date": (today - timedelta(days=27 - i)).isoformat(), "total_au": 200.0} for i in range(28)]
    ac_uniform = engine.acwr(uniform_rows, stage=1)
    check("uniform 200 AU/day -> ACWR 1.000",  ac_uniform["acwr"],        1.0, tol=0.001)
    check("uniform -> acute_avg 200.0",        ac_uniform["acute_avg"],   200.0, tol=0.1)
    check("uniform -> chronic_avg 200.0",      ac_uniform["chronic_avg"], 200.0, tol=0.1)
    check("uniform -> status optimal",         ac_uniform["status"],      "optimal")
    check("uniform -> not hard_locked",        ac_uniform["hard_locked"], False)

    # Undertraining: only 3 sessions in 28 days
    sparse_rows = [{"date": (today - timedelta(days=25)).isoformat(), "total_au": 100.0},
                   {"date": (today - timedelta(days=14)).isoformat(), "total_au": 100.0},
                   {"date": (today - timedelta(days=7)).isoformat(),  "total_au": 100.0}]
    ac_sparse = engine.acwr(sparse_rows, stage=1)
    check("sparse training -> undertraining",   ac_sparse["status"], "undertraining")

    # Hard lock: spike last 7 days above Stage 1 ceiling (1.2)
    chronic_rows = [{"date": (today - timedelta(days=27 - i)).isoformat(), "total_au": 200.0} for i in range(21)]
    spike_rows   = [{"date": (today - timedelta(days=6 - i)).isoformat(),  "total_au": 400.0} for i in range(7)]
    ac_spike = engine.acwr(chronic_rows + spike_rows, stage=1)
    check("7-day spike -> ACWR > 1.2 -> hard_locked", ac_spike["hard_locked"], True)
    check("hard locked -> status overreach_risk",     ac_spike["status"], "overreach_risk")

    # Zero-fill check: 1 entry 27 days ago only -> chronic diluted to near 0
    one_entry = [{"date": (today - timedelta(days=27)).isoformat(), "total_au": 300.0}]
    ac_one = engine.acwr(one_entry, stage=1)
    # chronic = 300/28 ≈ 10.7; acute = 0/7 = 0 -> ACWR = 0 -> undertraining
    check("single old entry -> rest days zeroed -> undertraining", ac_one["status"], "undertraining")

    # daily_au_28 length is always 28
    check("daily_au_28 always 28 entries (no data)", len(engine.acwr([], stage=1)["daily_au_28"]), 28)
    check("daily_au_28 always 28 entries (uniform)", len(ac_uniform["daily_au_28"]), 28)


def test_engine_volume_recommendation():
    baseline_7 = _bio_rows(6, 60.0, 55, 7.5)
    today_12pct_drop = [{"hrv_ms": 52.8, "resting_heart_rate": 55, "sleep_duration_hours": 7.5}]
    baseline_7b = _bio_rows(6, 60.0, 55, 7.5)
    today_30pct_drop = [{"hrv_ms": 42.0, "resting_heart_rate": 55, "sleep_duration_hours": 7.5}]

    today = date.today()
    uniform_rows = [{"date": (today - timedelta(days=27 - i)).isoformat(), "total_au": 200.0} for i in range(28)]
    chronic_rows = [{"date": (today - timedelta(days=27 - i)).isoformat(), "total_au": 200.0} for i in range(21)]
    spike_rows   = [{"date": (today - timedelta(days=6 - i)).isoformat(),  "total_au": 400.0} for i in range(7)]

    tl_ok  = engine.traffic_light(_bio_rows(7, 60, 55, 7.5))   # green
    tl_yel = engine.traffic_light(baseline_7 + today_12pct_drop) # yellow
    tl_red_sig = engine.traffic_light(baseline_7b + today_30pct_drop) # red
    ac_ok  = engine.acwr(uniform_rows, stage=1)
    ac_emp = engine.acwr([], stage=1)

    # Observation mode
    rec_obs = engine.volume_recommendation(tl_ok, ac_emp, 1, observation_days_remaining=5, injury_weight_val=0.5)
    check("obs mode -> label OBSERVATION MODE",  "OBSERVATION MODE" in rec_obs["label"], True)
    check("obs mode -> multiplier 1.0",          rec_obs["multiplier"], 1.0)

    # Red traffic light
    rec_red = engine.volume_recommendation(tl_red_sig, ac_ok, 1, 0, injury_weight_val=0.3)
    check("red traffic -> REST / DELOAD",        "REST" in rec_red["label"], True)
    check("red traffic -> multiplier 0.0",       rec_red["multiplier"], 0.0)

    # Yellow traffic light
    rec_yel = engine.volume_recommendation(tl_yel, ac_ok, 1, 0, injury_weight_val=0.3)
    check("yellow traffic -> REDUCED VOLUME",    "REDUCED" in rec_yel["label"], True)
    check("yellow traffic -> multiplier 0.75",   rec_yel["multiplier"], 0.75)

    # Hard lock
    ac_locked = engine.acwr(chronic_rows + spike_rows, stage=1)
    rec_lock = engine.volume_recommendation(tl_ok, ac_locked, 1, 0, injury_weight_val=0.3)
    check("hard lock -> VOLUME HARD-LOCKED",     "HARD-LOCKED" in rec_lock["label"], True)
    check("hard lock -> multiplier 0.75",        rec_lock["multiplier"], 0.75)

    # Green + low injury weight -> progressive overload
    rec_green = engine.volume_recommendation(tl_ok, ac_ok, 1, 0, injury_weight_val=0.3)
    check("green + inj_wt 0.3 -> PROGRESSIVE OVERLOAD", "PROGRESSIVE" in rec_green["label"], True)
    check("green -> multiplier 1.05",            rec_green["multiplier"], 1.05)
    check("green -> injury_weight_active False", rec_green["injury_weight_active"], False)

    # Green + HIGH injury weight -> conservative
    rec_cons = engine.volume_recommendation(tl_ok, ac_ok, 1, 0, injury_weight_val=0.8)
    check("green + inj_wt 0.8 -> CONSERVATIVE", "CONSERVATIVE" in rec_cons["label"], True)
    check("conservative -> multiplier 0.85",     rec_cons["multiplier"], 0.85)
    check("conservative -> injury_weight_active True", rec_cons["injury_weight_active"], True)

    # Boundary: exactly 0.7 injury weight -> conservative (>0.7 check is strict)
    rec_07 = engine.volume_recommendation(tl_ok, ac_ok, 1, 0, injury_weight_val=0.70)
    check("inj_wt exactly 0.70 -> NOT conservative (> not >=)", "PROGRESSIVE" in rec_07["label"], True)
    rec_071 = engine.volume_recommendation(tl_ok, ac_ok, 1, 0, injury_weight_val=0.701)
    check("inj_wt 0.701 -> conservative",       "CONSERVATIVE" in rec_071["label"], True)


def test_engine_apply_volume_recommendation():
    rec_rest = {"multiplier": 0.0, "label": "REST"}
    rest_out = engine.apply_volume_recommendation(3, 12, 50.0, rec_rest, stage=1)
    check("rest -> 0 sets",        rest_out["sets"],      0)
    check("rest -> 0 reps",        rest_out["reps"],      0)
    check("rest -> 0 weight",      rest_out["weight_kg"], 0.0)

    rec_ol = {"multiplier": 1.05, "label": "OVERLOAD"}
    # Stage 1: +1 rep, same weight
    ol_s1 = engine.apply_volume_recommendation(3, 12, 50.0, rec_ol, stage=1)
    check("overload Stage 1 -> same sets",     ol_s1["sets"],      3)
    check("overload Stage 1 -> +1 rep (13)",   ol_s1["reps"],      13)
    check("overload Stage 1 -> same weight",   ol_s1["weight_kg"], 50.0)

    # Stage 2: +2.5kg, same reps
    ol_s2 = engine.apply_volume_recommendation(3, 12, 50.0, rec_ol, stage=2)
    check("overload Stage 2 -> same sets",     ol_s2["sets"],      3)
    check("overload Stage 2 -> same reps",     ol_s2["reps"],      12)
    check("overload Stage 2 -> +2.5kg",        ol_s2["weight_kg"], 52.5)

    # Volume reduction 0.75 -> 3 sets -> 2 sets (rounded)
    rec_red2 = {"multiplier": 0.75, "label": "REDUCED"}
    red_out = engine.apply_volume_recommendation(4, 10, 40.0, rec_red2, stage=1)
    check("0.75 × 4 sets -> 3 sets",          red_out["sets"],      3)
    check("reduced -> same reps",             red_out["reps"],      10)
    check("reduced -> same weight",           red_out["weight_kg"], 40.0)

    # Conservative 0.85 -> 3 sets -> 3 (3×0.85=2.55 rounds to 3)
    rec_cons2 = {"multiplier": 0.85, "label": "CONSERVATIVE"}
    cons_out = engine.apply_volume_recommendation(3, 10, 40.0, rec_cons2, stage=1)
    check("0.85 × 3 sets -> 3 sets (rounds up)", cons_out["sets"], 3)

    # Minimum sets floor: even 1 set * 0.75 stays at 1
    min_sets = engine.apply_volume_recommendation(1, 5, 10.0, rec_red2, stage=1)
    check("min sets floor at 1",              min_sets["sets"], 1)


def test_engine_stage_status():
    # Stage 1 -> 2: need 14 days pain-free AND avg tightness ≤ 3.0
    s1_not_ready = engine.stage_status(1, 13, 2.5)
    check("Stage 1: 13d / tight 2.5 -> not ready (days short)",  s1_not_ready["advance_ready"], False)

    s1_tight_fail = engine.stage_status(1, 14, 3.1)
    check("Stage 1: 14d / tight 3.1 -> not ready (tightness high)", s1_tight_fail["advance_ready"], False)

    s1_ready = engine.stage_status(1, 14, 3.0)
    check("Stage 1: 14d / tight 3.0 -> READY",                   s1_ready["advance_ready"], True)
    check("Stage 1 next stage = 2",                              s1_ready["next_stage"], 2)
    check("Stage 1 days_progress_pct = 1.0 at 14/14",           s1_ready["days_progress_pct"], 1.0)

    s1_excess_days = engine.stage_status(1, 30, 2.0)
    check("Stage 1: 30d pain-free -> capped pct at 1.0",         s1_excess_days["days_progress_pct"], 1.0)

    # Stage 2 -> 3: need 28 days AND tightness ≤ 2.0
    s2_ready = engine.stage_status(2, 28, 2.0)
    check("Stage 2: 28d / tight 2.0 -> READY",                   s2_ready["advance_ready"], True)
    check("Stage 2 next stage = 3",                              s2_ready["next_stage"], 3)

    s2_not_ready = engine.stage_status(2, 28, 2.1)
    check("Stage 2: 28d / tight 2.1 -> not ready",               s2_not_ready["advance_ready"], False)

    # Stage 3 -> no further advancement
    s3 = engine.stage_status(3, 100, 0.0)
    check("Stage 3 -> advance_ready always False",               s3["advance_ready"], False)
    check("Stage 3 -> next_stage is None",                       s3["next_stage"], None)


def test_engine_check_auto_stage_advance():
    adv = engine.check_auto_stage_advance(1, 14, 3.0)
    check("criteria met -> should_advance True",   adv["should_advance"], True)
    check("criteria met -> next_stage = 2",        adv["next_stage"], 2)

    no_adv = engine.check_auto_stage_advance(1, 13, 2.0)
    check("criteria NOT met -> should_advance False", no_adv["should_advance"], False)

    s3_adv = engine.check_auto_stage_advance(3, 200, 0.0)
    check("Stage 3 -> never advances",             s3_adv["should_advance"], False)
    check("Stage 3 -> next_stage is None",         s3_adv["next_stage"], None)


def test_engine_step_strain_modifier():
    # baseline [8,9,10,11,12]: mean=10, population std=sqrt(2)≈1.414
    # z-scores: 13→+2.12, 12→+1.41, 10→0, 8→-1.41, 7→-2.12
    _ssm_base = [8, 9, 10, 11, 12]

    check("z >= +1.5 -> +1.5",              engine.step_strain_modifier(13, _ssm_base), 1.5)
    check("+0.75 <= z < +1.5 -> +0.75",   engine.step_strain_modifier(12, _ssm_base), 0.75)
    check("|z| < 0.75 -> 0.0",            engine.step_strain_modifier(10, _ssm_base), 0.0)
    check("-1.5 < z <= -0.75 -> -0.5",    engine.step_strain_modifier(8,  _ssm_base), -0.5)
    check("z <= -1.5 -> -1.0",            engine.step_strain_modifier(7,  _ssm_base), -1.0)
    check("yesterday_steps None -> 0.0",  engine.step_strain_modifier(None, _ssm_base), 0.0)
    check("< 4 baseline values -> 0.0",   engine.step_strain_modifier(15, [9, 10, 11]), 0.0)
    check("exactly 4 baseline -> computes", engine.step_strain_modifier(13, [8, 9, 10, 11]), 1.5)
    check("std == 0 -> 0.0",              engine.step_strain_modifier(12000, [10000] * 5), 0.0)


def test_engine_readiness_training_modifier_buckets():
    # Pure bucket helper
    check("high bucket at 85",   engine._bucket_readiness(85),    "high")
    check("normal bucket at 70", engine._bucket_readiness(70),    "normal")
    check("normal bucket at 60", engine._bucket_readiness(60),    "normal")
    check("below bucket at 55",  engine._bucket_readiness(55),    "below")
    check("below bucket at 40",  engine._bucket_readiness(40),    "below")
    check("low bucket at 39",    engine._bucket_readiness(39),    "low")
    check("low bucket at 0",     engine._bucket_readiness(0),     "low")
    check("unknown for None",    engine._bucket_readiness(None),  "unknown")

    # Modifier table — via _readiness_modifier_from_buckets
    _mfb = engine._readiness_modifier_from_buckets

    check("3-day high -> 1.12", _mfb(["high", "high", "high"])["volume_factor"],  1.12)
    check("2-day high -> 1.08", _mfb(["high", "high", "normal"])["volume_factor"], 1.08)
    check("1-day high -> 1.04", _mfb(["high", "normal", "normal"])["volume_factor"], 1.04)
    check("normal -> 1.00",     _mfb(["normal", "normal", "normal"])["volume_factor"], 1.00)
    check("1-day below -> 0.90",_mfb(["below", "normal", "normal"])["volume_factor"], 0.90)
    check("2-day below -> 0.82",_mfb(["below", "below", "normal"])["volume_factor"],  0.82)
    check("3-day below -> 0.75",_mfb(["below", "below", "below"])["volume_factor"],   0.75)
    check("1-day low -> 0.75",  _mfb(["low", "normal", "normal"])["volume_factor"],   0.75)
    check("2-day low -> 0.60",  _mfb(["low", "low", "normal"])["volume_factor"],      0.60)
    check("3-day low -> 0.50",  _mfb(["low", "low", "low"])["volume_factor"],         0.50)

    # Mixed: high today, low prior -- counts as 1-day high streak (no prior confirmation)
    check("high today, low prior -> 1.04", _mfb(["high", "low", "low"])["volume_factor"], 1.04)
    check("high today, low prior streak=1", _mfb(["high", "low", "low"])["streak_days"],   1)

    # Mixed: low today, high prior -- counts as 1-day low streak
    check("low today, high prior -> 0.75", _mfb(["low", "high", "high"])["volume_factor"], 0.75)

    # Empty / single unknown bucket
    check("empty list -> 1.00",         _mfb([])["volume_factor"],           1.00)
    check("unknown today -> 1.00",      _mfb(["unknown"])["volume_factor"],  1.00)

    # Volume floor — 3-day low never goes below 0.50
    check("3-day low floor at 0.50",   _mfb(["low", "low", "low"])["volume_factor"] >= 0.50, True)


def test_engine_apply_exercise_volume_modifier():
    _avm = engine.apply_exercise_volume_modifier

    # Fast path: factor == 1.0 returns same object
    _ex_base = {"name": "Bird-Dog", "hold_seconds": 45, "reps": 10, "sets": 3}
    check("factor 1.0 -> same object", _avm(_ex_base, 1.0) is _ex_base, True)

    # hold_seconds scaled by 0.75: round(45 * 0.75) = round(33.75) = 34
    check("hold_seconds 0.75: 45 -> 34",
          _avm({"hold_seconds": 45}, 0.75)["hold_seconds"], 34)

    # reps scaled by 1.10: round(10 * 1.1) = round(11.0) = 11
    check("reps 1.10: 10 -> 11",
          _avm({"reps": 10}, 1.10)["reps"], 11)

    # reps_in_set scaled by 0.60: round(5 * 0.60) = round(3.0) = 3
    check("reps_in_set 0.60: 5 -> 3",
          _avm({"reps_in_set": 5}, 0.60)["reps_in_set"], 3)

    # duration_minutes scaled by 0.75: round(20 * 0.75) = round(15.0) = 15
    check("duration_minutes 0.75: 20 -> 15",
          _avm({"duration_minutes": 20}, 0.75)["duration_minutes"], 15)

    # duration_minutes floor: round(5 * 0.10) = round(0.5) = 0, but max(5, 0) = 5
    check("duration_minutes floor at 5",
          _avm({"duration_minutes": 5}, 0.10)["duration_minutes"], 5)

    # Regression: duration_minutes must always come back a true int, never a
    # float — _duration_timer's f"{minutes:02d}:00" formatting raises
    # ValueError on a float even when its value is a whole number (e.g. 10.0),
    # and 1.04 * 10 = 10.4 is exactly the kind of factor that used to produce
    # a non-integer float under the old *2/2 half-minute-rounding formula.
    check("duration_minutes 1.04: 10 -> int",
          isinstance(_avm({"duration_minutes": 10}, 1.04)["duration_minutes"], int), True)

    # hold_seconds floor: round(6 * 0.10) = 1, max(5, 1) = 5
    check("hold_seconds floor at 5",
          _avm({"hold_seconds": 6}, 0.10)["hold_seconds"], 5)

    # reps floor: round(1 * 0.10) = 0, max(1, 0) = 1
    check("reps floor at 1",
          _avm({"reps": 1}, 0.10)["reps"], 1)

    # sets are NOT changed by the modifier
    check("sets unchanged",
          _avm({"sets": 3, "reps": 10}, 0.75)["sets"], 3)

    # rest_seconds are NOT changed
    check("rest_seconds unchanged",
          _avm({"rest_seconds": 60, "reps": 10}, 0.75)["rest_seconds"], 60)

    # Missing fields are passed through untouched
    check("missing reps not added",
          "reps" not in _avm({"hold_seconds": 30}, 0.75), True)
