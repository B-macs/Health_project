"""The Training page's routing and small rules, moved out of the view on
2026-10-19 (moves TRN-11, TRN-12, TRN-15, TRN-19) so the phone's API routes
the same way.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace

from services import flexibility as fx
from services import plan as ph
from services import scheduling
from services import sessions as sess
from services.models import Phase

MON = date(2026, 10, 19)
BLOCK = Phase(5, "12-week block", MON.isoformat(), 84, "active")
WED = MON + timedelta(days=2)            # a planned rest day of the 12-week block
TUE = MON + timedelta(days=1)


def test_a_planned_rest_day_is_rest_never_missed():
    assert sess.is_planned_rest(sess.calendar_plan(BLOCK).get(3))
    assert sess.day_route(WED, MON + timedelta(days=7), BLOCK, is_logged=False) == "rest"
    assert sess.day_route(TUE, MON + timedelta(days=7), BLOCK, is_logged=False) == "past_missed"
    assert sess.day_route(TUE, MON + timedelta(days=7), BLOCK, is_logged=True) == "past_completed"
    assert sess.day_route(TUE, MON, BLOCK, is_logged=False) == "future"
    assert sess.day_route(TUE, TUE, BLOCK, is_logged=False) == "today"
    assert sess.day_route(TUE, TUE, None, is_logged=False) == "no_phase"


def test_today_is_rest_on_a_forced_rest_or_a_planned_rest_day():
    assert sess.today_is_rest(BLOCK, WED)
    assert not sess.today_is_rest(BLOCK, TUE)
    assert sess.today_is_rest(replace(BLOCK, date_overrides={TUE.isoformat(): 0}), TUE)


def test_todays_flow_opens_on_the_overview_until_start():
    assert sess.today_screen(2, 84, done_today=False, started=False) == "overview"
    assert sess.today_screen(2, 84, done_today=False, started=True) == "session"
    assert sess.today_screen(2, 84, done_today=True, started=False) == "session"
    assert sess.today_screen(0, 84, done_today=False, started=False) == "not_started"
    assert sess.today_screen(85, 84, done_today=False, started=False) == "complete"


def test_the_gap_screen_names_the_next_block_and_any_stranded_days():
    nxt = Phase(6, "Next block", (MON + timedelta(days=90)).isoformat(), 28, "upcoming")
    gap = sess.phase_gap([BLOCK, nxt], MON + timedelta(days=86))
    assert gap["next"] == {"name": "Next block", "start_date": nxt.start_date, "days_away": 4}
    assert gap["stranded"] is None
    last = ph.phase_end_date(BLOCK)
    lapsed = replace(BLOCK, date_overrides={(last + timedelta(days=1)).isoformat(): 84})
    gap = sess.phase_gap([lapsed], last + timedelta(days=2))
    assert gap["next"] is None
    assert gap["stranded"]["name"] == "12-week block"
    assert gap["stranded"]["days"][0][0] == 84 and gap["stranded"]["last_date"] == last


def test_the_small_rules():
    assert sess.is_loaded_session([{"weight_kg": 0}, {"weight_kg": 22.5}])
    assert not sess.is_loaded_session([{"reps": 10}, {"weight_kg": None}])
    assert sess.days_back_to(MON, MON + timedelta(days=10)) == 13
    assert sess.HOLD_TIMER_TYPES == ("hold", "hold_reps")
    assert not scheduling.shift_note_moved(scheduling.HELD_REASON_PREFIX + "trailing day")
    assert scheduling.shift_note_moved("Missed → moved to 2026-10-21")


def test_the_retest_banner_speaks_only_when_a_retest_is_near():
    assert fx.retest_notice([], [], MON) is None
    import cluster_a_prescription as cap
    last = SimpleNamespace(taken_on=MON - timedelta(days=cap.RETEST_INTERVAL_DAYS))
    notice = fx.retest_notice([last], [], MON)
    assert notice is not None and notice[0] in ("warning", "info")
    assert notice[1] in fx.RETEST_NOTICE_KIND
    recent = SimpleNamespace(taken_on=MON - timedelta(days=3))
    assert fx.retest_notice([recent], [], MON) is None
