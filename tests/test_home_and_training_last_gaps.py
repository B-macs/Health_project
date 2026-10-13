"""Home and Training say the same thing, in the same colour, for the same reason.

The athlete, August: "These keep gapping and we need to add in rules that they
can't gap." One shared verdict has driven both screens since 2026-08-23
(tests/test_home_and_training_agree.py). Four gaps were left, found 2026-10-13
and closed here:

  1. On an injury-cap day the banner was blue but the in-session SESSION
     ADAPTED badge and the "Adapt session" box were amber.
  2. Home showed that same kind ("info", VOLUME HELD) in amber.
  3. The baseline-drift rule can reduce load on a day every tile is green, and
     Home never said why; only Training's headline named the reason.
  4. Insights > Engine Data printed the raw engine label in the bright signal
     yellow, and services.insights.directive_copy had no caller.
"""
from __future__ import annotations

import pathlib

from services import engine
from services import insights
from services import sessions
from services import verdict as vd

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _rows(n: int = 28, **today):
    rows = [{"date": f"2026-08-{i + 1:02d}", "hrv_ms": 55.0, "resting_heart_rate": 50.0,
             "sleep_duration_hours": 7.0, "oura_temperature_deviation": 0.0}
            for i in range(n)]
    rows[-1].update(today)
    return rows


def _directive(rows):
    tl = engine.traffic_light(rows)
    return engine.volume_recommendation(
        tl, {"hard_locked": False, "acwr": 1.0, "ceiling": 1.3}, 2, 0, 0.3)


# ── 3. the reason reaches Home ───────────────────────────────────────────────

def test_a_reduced_day_carries_the_reading_the_engine_named():
    rec = _directive(_rows(hrv_ms=38.0))
    assert rec["cause"] and "38 ms" in rec["cause"]
    assert rec["action"].startswith(rec["cause"]), "the headline and the cause are one sentence"
    v = vd.today_verdict(rec, {"volume_factor": 1.0})
    assert v.cause == rec["cause"] and v.reduced


def test_a_drift_day_names_the_drift_on_home():
    """The drift directive has no metric behind it by construction — every
    tile is green — so its message is the cause."""
    rec = {"label": "REDUCED VOLUME  (−25%)", "driver": engine.DRIVER_BIOMETRICS,
           "cause": "Your baseline has drifted down over four weeks.", "multiplier": 0.75,
           "action": "Your baseline has drifted down over four weeks. Scale total volume "
                     "down 20–30%.", "signal_color": "orange"}
    v = vd.today_verdict(rec, {"volume_factor": 1.0})
    assert v.banner_kind == "warning"
    assert v.cause.startswith("Your baseline has drifted")


def test_a_clear_day_or_an_injury_cap_day_carries_no_cause():
    green = _directive(_rows())
    assert vd.today_verdict(green, {"volume_factor": 1.0}).cause == ""
    capped = {"label": "CONSERVATIVE LOAD  (injury weight 95%)",
              "driver": engine.DRIVER_INJURY_WEIGHT, "multiplier": 0.85,
              "action": "Biometrics nominal...", "signal_color": "yellow"}
    assert vd.today_verdict(capped, {"volume_factor": 1.0}).cause == ""


def test_home_prints_the_cause_above_the_banner_text():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "if v.cause:" in src
    assert src.index("if v.cause:") < src.index("if v.banner_text:")


# ── 1 and 2. one colour per kind on both screens ────────────────────────────

def test_the_held_kind_is_blue_on_home_and_never_the_warning_amber():
    assert vd.HOME_TONES["info"] != vd.HOME_TONES["warning"]
    assert vd.HOME_TONES["info"] == "#7FA3C4"


def test_the_training_badge_and_the_adapt_box_follow_the_kind():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert '{"info": "#4FC3F7", "error": "#FF4B4B"}.get(' in src
    assert '_policy["banner_kind"],' in src
    assert '_held = policy.get("banner_kind") == "info"' in src
    assert "(st.info if _held else st.warning)(" in src


# ── 4. the Engine Data panel, and the dead copy function ────────────────────

def test_the_engine_data_panel_speaks_in_homes_words():
    src = (ROOT / "views" / "insights.py").read_text(encoding="utf-8")
    assert 'sessions_svc.load_policy(rec, {})["banner_kind"]' in src
    assert "verdict_svc.HOME_TONES.get(_kind" in src
    assert "verdict_svc.BADGE_WORDS.get(_kind)" in src
    # The directive line itself; the per-metric table below it rightly keeps
    # each metric's own signal colour (sig_k).
    assert 'engine.SIGNAL_COLORS.get(sig, engine.SIGNAL_COLORS["grey"])' not in src


def test_the_dead_copy_function_is_gone():
    assert not hasattr(insights, "directive_copy")
    assert not hasattr(insights, "_DIRECTIVE_LABELS")


def test_load_policy_reads_a_directive_with_a_cause_unchanged():
    """`cause` is a new key on the directive; the decision must not move."""
    rec = _directive(_rows(hrv_ms=38.0))
    without = {k: v for k, v in rec.items() if k != "cause"}
    a, b = sessions.load_policy(rec, {}), sessions.load_policy(without, {})
    assert {k: a[k] for k in ("reduced", "banner_kind", "volume_factor", "driver")} == \
           {k: b[k] for k in ("reduced", "banner_kind", "volume_factor", "driver")}
