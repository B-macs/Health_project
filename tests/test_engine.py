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
from unittest import mock

import pytest

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
    check("7-day spike -> ACWR exceeds 1.2 ceiling", ac_spike["exceeds_ceiling"], True)
    check("breach -> status overreach_risk",         ac_spike["status"], "overreach_risk")
    # The CEILING is untouched — only enforcement is held (ACWR_ADVISORY_MODE).
    # Pin both directions so the switch cannot silently stop working either way.
    check("advisory mode -> breach does not lock",   ac_spike["hard_locked"], False)
    with mock.patch.object(engine, "ACWR_ADVISORY_MODE", False):
        ac_enforced = engine.acwr(chronic_rows + spike_rows, stage=1)
    check("advisory OFF -> same breach hard locks",  ac_enforced["hard_locked"], True)
    check("advisory OFF -> ceiling still 1.2",       ac_enforced["ceiling"], 1.2)

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

    # Hard lock — enforcement is held by default, so re-enable it to test it.
    with mock.patch.object(engine, "ACWR_ADVISORY_MODE", False):
        ac_locked = engine.acwr(chronic_rows + spike_rows, stage=1)
    rec_lock = engine.volume_recommendation(tl_ok, ac_locked, 1, 0, injury_weight_val=0.3)
    check("hard lock -> VOLUME HARD-LOCKED",     "HARD-LOCKED" in rec_lock["label"], True)
    check("hard lock -> multiplier 0.75",        rec_lock["multiplier"], 0.75)
    check("hard lock -> no duplicate advisory",  rec_lock["acwr_advisory"], None)

    # Same ACWR under advisory mode: the directive is NOT overridden, but the
    # breach is still reported alongside it.
    ac_adv  = engine.acwr(chronic_rows + spike_rows, stage=1)
    rec_adv = engine.volume_recommendation(tl_ok, ac_adv, 1, 0, injury_weight_val=0.3)
    check("advisory -> directive not overridden", "HARD-LOCKED" in rec_adv["label"], False)
    check("advisory -> breach still surfaced",
          "Advisory" in (rec_adv["acwr_advisory"] or ""), True)

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

    # High readiness adds NOTHING since 2026-09-16 (it was +12/+8/+4%): no trial
    # raises resistance load or volume because readiness is high —
    # docs/training/load_progression_evidence_review_2026-09-16.md.
    check("3-day high -> 1.00", _mfb(["high", "high", "high"])["volume_factor"],  1.00)
    check("2-day high -> 1.00", _mfb(["high", "high", "normal"])["volume_factor"], 1.00)
    check("1-day high -> 1.00", _mfb(["high", "normal", "normal"])["volume_factor"], 1.00)
    check("high still reads as high", _mfb(["high", "high", "high"])["streak_label"], "high")
    check("high carries no description", _mfb(["high", "high", "high"])["description"], "")
    check("normal -> 1.00",     _mfb(["normal", "normal", "normal"])["volume_factor"], 1.00)
    check("1-day below -> 0.90",_mfb(["below", "normal", "normal"])["volume_factor"], 0.90)
    check("2-day below -> 0.82",_mfb(["below", "below", "normal"])["volume_factor"],  0.82)
    check("3-day below -> 0.75",_mfb(["below", "below", "below"])["volume_factor"],   0.75)
    check("1-day low -> 0.75",  _mfb(["low", "normal", "normal"])["volume_factor"],   0.75)
    check("2-day low -> 0.60",  _mfb(["low", "low", "normal"])["volume_factor"],      0.60)
    check("3-day low -> 0.50",  _mfb(["low", "low", "low"])["volume_factor"],         0.50)

    # Mixed: high today, low prior -- counts as 1-day high streak (no prior confirmation)
    check("high today, low prior -> 1.00", _mfb(["high", "low", "low"])["volume_factor"], 1.00)
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


# ─── suggested_weight_kg ─────────────────────────────────────────────────────
#
# Readiness may LOWER a weight and never raises one (2026-09-16). "high" added
# an increment until then, and that is the step that started a goblet squat at
# 25 kg after 22.5 kg x 8, the bottom of its range —
# docs/training/load_progression_evidence_review_2026-09-16.md.

def test_suggested_weight_kg_high_streak_never_raises():
    assert engine.suggested_weight_kg(10.0, "high") == 10.0
    assert engine.suggested_weight_kg(22.5, "high") == 22.5


def test_suggested_weight_kg_low_streak_nudges_down():
    assert engine.suggested_weight_kg(10.0, "low") == 7.5
    assert engine.suggested_weight_kg(10.0, "below") == 7.5


def test_suggested_weight_kg_normal_or_unknown_leaves_value_exactly_unchanged():
    assert engine.suggested_weight_kg(10.0, "normal") == 10.0
    assert engine.suggested_weight_kg(10.0, "unknown") == 10.0
    # Off-grid weights (e.g. a 1kg accessory dumbbell) must NOT be snapped
    # to the 2.5kg increment grid on a "no change" suggestion.
    assert engine.suggested_weight_kg(1.0, "normal") == 1.0
    assert engine.suggested_weight_kg(1.0, "high") == 1.0


def test_suggested_weight_kg_has_no_upward_switch_left():
    # allow_increase went with the upward move. A parameter that switches off
    # something that cannot happen would read as though it could.
    import inspect
    assert "allow_increase" not in inspect.signature(engine.suggested_weight_kg).parameters


def test_a_run_of_high_readiness_days_never_climbs():
    weight = 20.0
    for _ in range(10):
        weight = engine.suggested_weight_kg(weight, "high")
    assert weight == 20.0


def test_suggested_weight_kg_floors_at_zero():
    assert engine.suggested_weight_kg(2.5, "low") == 0.0
    assert engine.suggested_weight_kg(0.0, "low") == 0.0


def test_suggested_weight_kg_none_input_returns_none():
    assert engine.suggested_weight_kg(None, "high") is None


def test_suggested_weight_kg_snaps_to_increment_multiple_on_an_actual_move():
    # Simulates float drift from a non-aligned seed -- only when actually
    # moving (delta != 0) does the result snap to the 2.5kg grid.
    assert engine.suggested_weight_kg(11.3, "low") == 10.0


# ─── suggested_band_tier ─────────────────────────────────────────────────────

def test_suggested_band_tier_high_streak_never_moves_up():
    assert engine.suggested_band_tier("Green", "high") == "Green"
    assert engine.suggested_band_tier("Yellow", "high") == "Yellow"


def test_suggested_band_tier_low_streak_moves_down_one_tier():
    assert engine.suggested_band_tier("Blue", "low") == "Green"
    assert engine.suggested_band_tier("Red", "below") == "Yellow"


def test_suggested_band_tier_normal_unchanged():
    assert engine.suggested_band_tier("Yellow", "normal") == "Yellow"


def test_suggested_band_tier_clamped_at_black():
    assert engine.suggested_band_tier("Black", "high") == "Black"


def test_suggested_band_tier_clamped_at_green():
    assert engine.suggested_band_tier("Green", "low") == "Green"


def test_suggested_band_tier_has_no_upward_switch_left():
    import inspect
    assert "allow_increase" not in inspect.signature(engine.suggested_band_tier).parameters


def test_suggested_band_tier_unrecognised_tier_returns_none():
    assert engine.suggested_band_tier("Purple", "high") is None
    assert engine.suggested_band_tier(None, "high") is None


# ─── range_progression ───────────────────────────────────────────────────────
#
# 2026-10-16, docs/training/load_progression_evidence_review_2026-09-16.md §10,
# approved by the athlete: one weight, a rep range and today's aim. The aim
# climbs one rep; the weight goes up when the last set reached the top in every
# session within 7 days, and back when the last set was under the range twice
# in a row. The reps after a step are what the step costs (Nuzzo 2024's tables).

def _session(day, reps, weight=40.0):
    return (day, [{"reps": r, "weight": weight} for r in reps])


def _rp(sessions, weight=40.0, reps=10, rep_min=8, rep_max=12, **kw):
    kw.setdefault("prescribed_sets", 3)
    return engine.range_progression(rep_min, rep_max, sessions, weight, reps, **kw)


def test_his_lat_pulldown_holds_at_50_and_aims_one_rep_higher():
    """The case he brought (2026-10-10: 45 x 10, 50 x 11, 50 x 8) on the approved
    8-12 range: the last set made 8, inside the range, so 50 kg with an aim of 9."""
    s = [("2026-10-10", [{"reps": 10, "weight": 45.0}, {"reps": 11, "weight": 50.0},
                         {"reps": 8, "weight": 50.0}])]
    out = _rp(s, weight=45.0, reps=11)
    assert (out["weight"], out["aim"], out["action"], out["top"]) == (50.0, 9, "hold", 12)


def test_his_lat_pulldown_steps_when_the_last_set_makes_twelve():
    out = _rp([_session("2026-10-17", [12, 12, 12], 50.0)], weight=45.0, reps=11)
    assert (out["weight"], out["aim"], out["action"]) == (52.5, 10, "step_up")


def test_one_session_at_the_top_steps_the_weight():
    # Replaces the two-sessions-in-a-row rule of 2026-09-16 (his choice).
    out = _rp([_session("2026-10-10", [12, 12, 12])])
    assert (out["weight"], out["aim"], out["action"]) == (42.5, 10, "step_up")


def test_only_the_last_set_decides():
    assert _rp([_session("2026-10-10", [12, 11, 12])])["action"] == "step_up"
    out = _rp([_session("2026-10-10", [12, 12, 11])])
    assert (out["action"], out["aim"]) == ("hold", 12)


def test_every_session_within_seven_days_must_reach_the_top():
    # Twice a week: Thursday at the top, Monday not -> hold.
    s = [_session("2026-10-15", [12, 12, 12]), _session("2026-10-12", [10, 10, 10])]
    assert _rp(s)["action"] == "hold"
    # Seven days apart is outside the window: once a week, the newest decides.
    s = [_session("2026-10-17", [12, 12, 12]), _session("2026-10-10", [10, 10, 10])]
    assert _rp(s)["action"] == "step_up"


def test_the_sessions_in_the_window_must_be_at_the_same_weight():
    s = [_session("2026-10-15", [12, 12, 12]), _session("2026-10-12", [12, 12, 12], 37.5)]
    assert _rp(s)["action"] == "hold"


def test_a_session_stopped_short_never_steps():
    # Stopped after 1 of 3 sets: the last set was never reached.
    assert _rp([_session("2026-10-10", [12])])["action"] == "hold"
    assert _rp([_session("2026-10-10", [12, 12, 12, 12])])["action"] == "step_up"


def test_the_aim_climbs_one_rep_up_to_the_top():
    assert _rp([_session("2026-10-10", [10, 10, 9])])["aim"] == 10
    assert _rp([_session("2026-10-10", [12, 12, 11])])["aim"] == 12


def test_a_light_dumbbell_aims_past_the_range_before_it_steps():
    # 22.5 kg: the top is 13 (rule 5), so 12 is not yet a step.
    out = _rp([_session("2026-10-10", [12, 12, 12], 22.5)], weight=22.5)
    assert (out["action"], out["aim"], out["top"]) == ("hold", 13, 13)
    out = _rp([_session("2026-10-10", [13, 13, 13], 22.5)], weight=22.5)
    assert (out["weight"], out["aim"], out["action"]) == (25.0, 9, "step_up")


def test_the_last_set_under_the_range_twice_steps_back():
    s = [_session("2026-10-17", [9, 8, 7]), _session("2026-10-10", [9, 8, 6])]
    out = _rp(s)
    # 2.5 kg off 40 gives back about 2.5 reps: 7 becomes 9.
    assert (out["weight"], out["aim"], out["action"]) == (37.5, 9, "step_back")


def test_once_under_the_range_is_not_a_step_back():
    s = [_session("2026-10-17", [9, 8, 7]), _session("2026-10-10", [10, 10, 9])]
    assert (_rp(s)["weight"], _rp(s)["action"], _rp(s)["aim"]) == (40.0, "hold", 8)


def test_a_blocked_step_holds_the_weight():
    out = _rp([_session("2026-10-10", [12, 12, 12])], allow_step=False)
    assert (out["weight"], out["aim"], out["action"]) == (40.0, 12, "hold")


def test_a_failed_week_holds_the_weight_and_the_reps():
    out = _rp([_session("2026-10-10", [12, 12, 12])], hold=True)
    assert (out["weight"], out["aim"], out["action"]) == (40.0, 12, "held")


def test_no_history_starts_at_the_plan_inside_the_range():
    out = _rp([], weight=45.0, reps=11)
    assert (out["weight"], out["aim"], out["action"], out["date"]) == (45.0, 11, "start", None)
    assert _rp(None, reps=15)["aim"] == 12


def test_the_working_weight_is_the_logged_one_not_the_plan():
    # The plan's weight can be stale; progress from what was lifted.
    assert _rp([_session("2026-10-10", [12, 12, 12], 42.5)], weight=10.0)["weight"] == 45.0


def test_a_set_without_a_weight_reads_as_the_plan_weight():
    s = [("2026-10-10", [{"reps": 12}] * 3)]
    assert (_rp(s)["weight"], _rp(s)["action"]) == (42.5, "step_up")


def test_ramp_sets_and_empty_sessions_are_not_the_lift():
    ramp = [{"reps": 5, "weight": 20.0, "is_warmup": True}]
    s = [("2026-10-17", []), ("2026-10-10", ramp + [{"reps": 12, "weight": 40.0}] * 3)]
    out = _rp(s)
    assert (out["action"], out["date"]) == ("step_up", "2026-10-10")


def test_an_unreadable_date_never_counts_toward_a_step():
    s = [_session("2026-10-15", [12, 12, 12]), _session("bad", [10, 10, 10])]
    assert _rp(s)["action"] == "step_up"            # outside the window, never inside
    assert _rp([_session("bad", [12, 12, 12])])["action"] == "step_up"   # the newest counts


def test_a_custom_increment_steps_by_its_own_unit():
    # A cable stack in its own units: 20 -> 21 is +5%, which costs about 2 reps.
    out = _rp([_session("2026-10-10", [12, 12, 12], 20.0)], weight=20.0, increment=1)
    assert (out["weight"], out["aim"]) == (21.0, 10)


@pytest.mark.parametrize("weight", [15.0, 22.5, 40.0, 50.0])
@pytest.mark.parametrize("rep_min,rep_max", [(8, 12), (10, 15)])
def test_the_weight_moves_at_most_one_step_and_the_aim_is_never_zero(weight, rep_min, rep_max):
    for newest in range(4, 18):
        for older in range(4, 18):
            s = [_session("2026-10-17", [newest] * 3, weight),
                 _session("2026-10-10", [older] * 3, weight)]
            out = _rp(s, weight=weight, rep_min=rep_min, rep_max=rep_max)
            assert abs(out["weight"] - weight) <= 2.5 + 1e-9
            assert out["aim"] >= 1
            if out["action"] in ("step_up", "step_back"):
                assert rep_min <= out["aim"] <= rep_max


# ─── the reps after a step, and the reps before one ──────────────────────────

def test_the_reps_drop_by_what_the_step_costs():
    # From the review's worked cases, starting at 12 reps:
    assert engine.reps_after_load_step(12, 40.0) == 10   # +6.3%, DB RDL
    assert engine.reps_after_load_step(12, 25.0) == 8    # +10%, goblet squat / hip thrust
    assert engine.reps_after_load_step(12, 45.0) == 10   # +5.6%


def test_the_reps_never_rise_after_a_step():
    assert engine.reps_after_load_step(8, 1000.0) == 8


def test_the_reps_fall_back_to_the_bottom_of_the_range_with_no_weight_to_scale():
    assert engine.reps_after_load_step(12, 0.0, rep_min=8) == 8
    assert engine.reps_after_load_step(12, None, rep_min=8) == 8


def test_a_heavy_lift_steps_at_the_top_of_its_range():
    assert engine.progression_rep_target(8, 12, 40.0) == 12
    assert engine.progression_rep_target(8, 12, 25.0) == 12


def test_a_light_dumbbell_climbs_past_the_range_before_it_steps():
    # 2.5 kg on 22.5 kg is +11%, past ACSM's 2-10%: 12 reps would drop to 8 at
    # the edge, so the target is 13 and the drop lands at 9.
    assert engine.progression_rep_target(8, 12, 22.5) == 13
    assert engine.reps_after_load_step(13, 22.5) == 9
    # 2.5 kg on 15 kg is +17%.
    assert engine.progression_rep_target(8, 12, 15.0) == 15
    assert engine.reps_after_load_step(15, 15.0) == 9


@pytest.mark.parametrize("weight", [10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 30.0, 40.0, 60.0])
@pytest.mark.parametrize("rep_min,rep_max", [(8, 12), (10, 12), (6, 10), (12, 15)])
def test_after_a_step_the_reps_land_inside_the_range(weight, rep_min, rep_max):
    """The target is built so the drop can never leave the range — the one
    property that makes reps-first and effort-matching a single rule."""
    target = engine.progression_rep_target(rep_min, rep_max, weight)
    assert target >= rep_max
    assert rep_min <= engine.reps_after_load_step(target, weight) <= target
