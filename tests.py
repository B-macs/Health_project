"""
tests.py — Deterministic regression tests.
Tests every calculation in engine.py, stats.py, and rules.py with known inputs.
Run with: py tests.py
"""

import sys
import math
from datetime import date, timedelta

import engine
import stats
import rules

# ── Test runner ───────────────────────────────────────────────────────────────

_passed = 0
_failed = 0
_section = ""


def section(name: str) -> None:
    global _section
    _section = name
    print(f"\n{name}")
    print("-" * len(name))


def check(description: str, actual, expected, tol: float = None) -> None:
    global _passed, _failed
    if tol is not None:
        ok = abs(float(actual) - float(expected)) <= tol
    else:
        ok = actual == expected
    if ok:
        print(f"  PASS  {description}")
        _passed += 1
    else:
        print(f"  FAIL  {description}")
        print(f"       expected : {expected!r}")
        print(f"       actual   : {actual!r}")
        _failed += 1


# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — Constants and simple helpers
# ─────────────────────────────────────────────────────────────────────────────

section("engine — constants and helpers")

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

# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — injury_weight decay
# ─────────────────────────────────────────────────────────────────────────────

section("engine -- injury_weight (e^-lambda*t, lambda=0.05)")

# e^(-0.05 * t)
check("day 0  -> 1.0000", engine.injury_weight(0.05, 0),   1.0,    tol=1e-4)
check("day 14 -> ~0.4966", engine.injury_weight(0.05, 14), math.exp(-0.7), tol=1e-4)
check("day 28 -> ~0.2466", engine.injury_weight(0.05, 28), math.exp(-1.4), tol=1e-4)
check("day 60 -> ~0.0498", engine.injury_weight(0.05, 60), math.exp(-3.0), tol=1e-4)
check("negative days clamped to 0", engine.injury_weight(0.05, -5), 1.0, tol=1e-4)
check("lambda=0 gives 1.0 always",       engine.injury_weight(0.0, 100), 1.0, tol=1e-4)

# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — traffic_light
# ─────────────────────────────────────────────────────────────────────────────

section("engine — traffic_light")

def _bio_rows(n, hrv, rhr, sleep):
    return [{"hrv_ms": hrv, "resting_heart_rate": rhr, "sleep_duration_hours": sleep}] * n

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

# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — acwr
# ─────────────────────────────────────────────────────────────────────────────

section("engine — acwr")

# No data
ac_empty = engine.acwr([], stage=1)
check("no data -> acwr is None",         ac_empty["acwr"], None)
check("no data -> Stage 1 ceiling 1.2",  ac_empty["ceiling"], 1.2)
check("Stage 2 ceiling is 1.3",         engine.acwr([], stage=2)["ceiling"], 1.3)
check("Stage 3 ceiling is 1.5",         engine.acwr([], stage=3)["ceiling"], 1.5)

# Build 28 days of uniform 200 AU -> ACWR = 1.0 (optimal)
today = date.today()
uniform_rows = [{"date": (today - timedelta(days=27-i)).isoformat(), "total_au": 200.0} for i in range(28)]
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
chronic_rows = [{"date": (today - timedelta(days=27-i)).isoformat(), "total_au": 200.0} for i in range(21)]
spike_rows   = [{"date": (today - timedelta(days=6-i)).isoformat(),  "total_au": 400.0} for i in range(7)]
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

# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — volume_recommendation
# ─────────────────────────────────────────────────────────────────────────────

section("engine — volume_recommendation")

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

# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — apply_volume_recommendation
# ─────────────────────────────────────────────────────────────────────────────

section("engine — apply_volume_recommendation")

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

# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — stage_status
# ─────────────────────────────────────────────────────────────────────────────

section("engine — stage_status")

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

# ─────────────────────────────────────────────────────────────────────────────
#  engine.py — check_auto_stage_advance
# ─────────────────────────────────────────────────────────────────────────────

section("engine — check_auto_stage_advance")

adv = engine.check_auto_stage_advance(1, 14, 3.0)
check("criteria met -> should_advance True",   adv["should_advance"], True)
check("criteria met -> next_stage = 2",        adv["next_stage"], 2)

no_adv = engine.check_auto_stage_advance(1, 13, 2.0)
check("criteria NOT met -> should_advance False", no_adv["should_advance"], False)

s3_adv = engine.check_auto_stage_advance(3, 200, 0.0)
check("Stage 3 -> never advances",             s3_adv["should_advance"], False)
check("Stage 3 -> next_stage is None",         s3_adv["next_stage"], None)

# ─────────────────────────────────────────────────────────────────────────────
#  stats.py — neural / urgent symptom detection
# ─────────────────────────────────────────────────────────────────────────────

section("stats — symptom detection")

check("'shooting' -> neural",              stats.detect_neural_symptoms("shooting pain down my leg"), True)
check("'tingling' -> neural",             stats.detect_neural_symptoms("tingling in my left foot"), True)
check("'numb' -> neural",                 stats.detect_neural_symptoms("my foot went numb"), True)
check("'tight lower back' -> not neural", stats.detect_neural_symptoms("tight lower back"), False)
check("empty string -> not neural",       stats.detect_neural_symptoms(""), False)

check("'bowel' -> urgent",                stats.detect_urgent_symptoms("bowel issues today"), True)
check("'cauda equina' -> urgent",         stats.detect_urgent_symptoms("cauda equina symptoms"), True)
check("'shooting' -> not urgent",         stats.detect_urgent_symptoms("shooting pain"), False)

check("neural text -> auto_warning_level flag",   stats.auto_warning_level("shooting down my leg"), "flag")
check("urgent text -> auto_warning_level flag",   stats.auto_warning_level("bladder control issues"), "flag")
check("normal text -> auto_warning_level None",   stats.auto_warning_level("slightly tight today"), None)
check("empty -> auto_warning_level None",         stats.auto_warning_level(""), None)

# ─────────────────────────────────────────────────────────────────────────────
#  stats.py — trend_slope
# ─────────────────────────────────────────────────────────────────────────────

section("stats — trend_slope")

# Perfectly flat series -> slope ≈ 0
check("flat series -> slope ~0", stats.trend_slope([5.0, 5.0, 5.0, 5.0, 5.0]), 0.0, tol=1e-4)

# Perfectly linear increasing -> slope = 1.0
check("linear +1/day -> slope ~1.0", stats.trend_slope([0, 1, 2, 3, 4, 5, 6]), 1.0, tol=1e-3)

# Decreasing
check("linear -1/day -> slope ~-1.0", stats.trend_slope([6, 5, 4, 3, 2, 1, 0]), -1.0, tol=1e-3)

# Too few values
check("< 3 values -> None", stats.trend_slope([5.0, 6.0]), None)
check("empty -> None",      stats.trend_slope([]), None)

# None values are filtered
check("Nones filtered -> still computes", stats.trend_slope([None, 1, 2, 3, None, 5]), None if False else stats.trend_slope([1, 2, 3, 5]), tol=0.5)

# ─────────────────────────────────────────────────────────────────────────────
#  stats.py — recovery_direction
# ─────────────────────────────────────────────────────────────────────────────

section("stats — recovery_direction")

# Improving: pain and tightness both decreasing (negative slopes)
improving = stats.recovery_direction([5, 4, 3, 2, 1, 0], [5, 4, 3, 2, 1, 0])
check("decreasing pain+tightness -> improving", improving, "improving")

# Degrading: both increasing
degrading = stats.recovery_direction([0, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5])
check("increasing pain+tightness -> degrading", degrading, "degrading")

# Stable: flat
stable = stats.recovery_direction([3, 3, 3, 3, 3, 3], [2, 2, 2, 2, 2, 2])
check("flat -> stable", stable, "stable")

# Insufficient
insuff = stats.recovery_direction([3], [])
check("< 3 values -> insufficient_data", insuff, "insufficient_data")

# ─────────────────────────────────────────────────────────────────────────────
#  stats.py — session_tonnage
# ─────────────────────────────────────────────────────────────────────────────

section("stats — session_tonnage")

check("3×10@20kg = 200 (one set)", stats.session_tonnage([{"reps_completed": 10, "weight_kg": 20.0}]), 200.0)
check("multiple sets sum",
      stats.session_tonnage([
          {"reps_completed": 10, "weight_kg": 20.0},
          {"reps_completed": 8,  "weight_kg": 25.0},
          {"reps_completed": 6,  "weight_kg": 30.0},
      ]),
      10*20 + 8*25 + 6*30)  # 200 + 200 + 180 = 580
check("empty -> 0.0", stats.session_tonnage([]), 0.0)
check("None weight treated as 0", stats.session_tonnage([{"reps_completed": 10, "weight_kg": None}]), 0.0)
check("None reps treated as 0",   stats.session_tonnage([{"reps_completed": None, "weight_kg": 20.0}]), 0.0)

# ─────────────────────────────────────────────────────────────────────────────
#  stats.py — lag_correlation
# ─────────────────────────────────────────────────────────────────────────────

section("stats — lag_correlation")

# Perfect negative correlation at lag 1: when au spikes, hrv drops next day
import random; random.seed(42)
base = [60.0] * 20
au_spike = [0.0] * 20
# On days 5,10,15: AU=300 -> HRV drops next day
hrv_series = list(base)
au_series  = list([0.0] * 20)
for i in [5, 10, 15]:
    au_series[i] = 300.0
    hrv_series[i+1] = 40.0

corr = stats.lag_correlation(hrv_series, au_series, [1])
check("lag-1 correlation exists (not None)", corr[1] is not None, True)
check("spike AU -> drop HRV next day -> negative correlation", corr[1] < 0, True)

# Perfect positive correlation at lag 0
same = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
corr_same = stats.lag_correlation(same, same, [0])
check("lag-0 self-correlation = 1.0", corr_same[0], 1.0, tol=1e-6)

# Too few values -> None
corr_short = stats.lag_correlation([1, 2], [1, 2], [1])
check("< 5 paired values -> None", corr_short[1], None)

# ─────────────────────────────────────────────────────────────────────────────
#  rules.py — movement safety
# ─────────────────────────────────────────────────────────────────────────────

section("rules — check_movement")

# Always contraindicated
heavy_dl = rules.check_movement("heavy deadlift", current_stage=1)
check("heavy deadlift Stage 1 -> contraindicated",   heavy_dl["severity"], "contraindicated")

barbell_dl = rules.check_movement("barbell deadlift", current_stage=3)
check("barbell deadlift Stage 3 -> still contraindicated (stage_cap=1)", barbell_dl["severity"], "contraindicated")

# Cleared
bird_dog = rules.check_movement("bird-dog", current_stage=1)
check("bird-dog Stage 1 -> cleared",               bird_dog["severity"], "cleared")

cat_cow = rules.check_movement("cat-cow", current_stage=1)
check("cat-cow Stage 1 -> cleared",                cat_cow["severity"], "cleared")

walking = rules.check_movement("walking", current_stage=1)
check("walking Stage 1 -> cleared",                walking["severity"], "cleared")

# Caution — not available in Stage 1 but clears from Stage 2
rdl_s1 = rules.check_movement("romanian deadlift", current_stage=1)
check("RDL Stage 1 -> contraindicated (stage_cap=2)", rdl_s1["severity"], "contraindicated")

rdl_s2 = rules.check_movement("romanian deadlift", current_stage=2)
check("RDL Stage 2 -> caution",                    rdl_s2["severity"], "caution")

# Unknown movement
unknown = rules.check_movement("underwater basket weaving", current_stage=1)
check("unknown movement -> severity unknown",       unknown["severity"], "unknown")

# Stage constraints
s1_constraints = rules.get_stage_constraints(1)
check("Stage 1 ACWR ceiling = 1.2",                s1_constraints["acwr_ceiling"], 1.2)
check("Stage 2 ACWR ceiling = 1.3",                rules.get_stage_constraints(2)["acwr_ceiling"], 1.3)
check("Stage 3 ACWR ceiling = 1.5",                rules.get_stage_constraints(3)["acwr_ceiling"], 1.5)
check("Stage 1 RPE ceiling = 7",                   s1_constraints["rpe_ceiling"], 7)

# Cleared list for Stage 1 contains known safe movements
cleared_s1 = rules.get_cleared_for_stage(1)
check("bird-dog in Stage 1 cleared list",          "bird-dog" in cleared_s1, True)
check("walking in Stage 1 cleared list",           "walking" in cleared_s1, True)

# Contraindicated list
always_contra = rules.get_contraindicated_always()
check("heavy deadlift always contraindicated",     "heavy deadlift" in always_contra, True)
check("jumping always contraindicated",            "jumping" in always_contra, True)

# ─────────────────────────────────────────────────────────────────────────────
#  Summary
# ─────────────────────────────────────────────────────────────────────────────

total = _passed + _failed
print(f"\n{'=' * 50}")
print(f"  RESULTS: {_passed}/{total} passed", end="")
if _failed:
    print(f"  ({_failed} FAILED)", end="")
print()
print(f"{'=' * 50}")

if _failed:
    sys.exit(1)
