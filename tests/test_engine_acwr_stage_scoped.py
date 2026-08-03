"""Tests for engine.acwr()'s stage-scoped chronic baseline and advisory mode.

Both exist because of one measured failure. Over the Stage 1 -> Stage 2A
transition, a flat 28-day chronic window put ACWR above the 1.3 ceiling on 20
of the block's first 30 days (67%), peaking at 1.78 — and the breach was
largely INDEPENDENT of training: 2026-07-25..27 were three consecutive
zero-AU days pinned at 1.73. The window was dividing a training-load acute
term by a rehab-load chronic term.

The fix scopes chronic to the current stage. The decisive test in this file is
test_rest_day_does_not_read_as_overreach: a day with no training at all must
not report overreach.

Prior-stage days are EXCLUDED, never down-weighted — they are the denominator,
so shrinking them raises the ratio (measured 2026-08-03: x0.5 moved ACWR
1.32 -> 1.50). test_downweighting_would_have_moved_the_wrong_way pins that
arithmetic so the idea is not revisited by accident.
"""

from datetime import date, timedelta
from unittest import mock

import pytest

from services import engine
from services import plan as plan_svc
from services.models import Phase


TODAY = date(2026, 8, 3)
STAGE_START = date(2026, 7, 20)          # Stage 2A day 1

# Real logged Foster AU, Stage 1 rehab era through Stage 2A day 15.
_REAL_AU = {
    "2026-07-07": 24.0,  "2026-07-08": 177.0, "2026-07-10": 10.0,
    "2026-07-13": 48.0,  "2026-07-14": 46.0,  "2026-07-15": 56.0,
    "2026-07-16": 224.0, "2026-07-17": 25.0,
    "2026-07-20": 264.0, "2026-07-21": 135.0, "2026-07-22": 315.0,
    "2026-07-23": 106.0, "2026-07-24": 290.0, "2026-07-28": 295.0,
    "2026-07-30": 402.0, "2026-07-31": 72.0,  "2026-08-03": 80.0,
}


def _rows(au_by_date: dict[str, float]) -> list[dict]:
    return [{"date": d, "total_au": au} for d, au in sorted(au_by_date.items())]


def _uniform(n: int, au: float, end: date = TODAY) -> dict[str, float]:
    return {(end - timedelta(days=n - 1 - i)).isoformat(): au for i in range(n)}


# ── Backwards compatibility ──────────────────────────────────────────────────

def test_stage_start_omitted_keeps_the_flat_calendar_window():
    """Every pre-existing caller must be bit-identical."""
    r = engine.acwr(_rows(_REAL_AU), stage=2, today=TODAY)
    assert r["chronic_basis"] == "calendar"
    assert r["in_stage_days"] == 28
    assert r["baseline_established"] is True
    # 2569 AU over 28 days
    assert r["chronic_avg"] == pytest.approx(91.8, abs=0.1)


def test_calendar_window_reproduces_the_measured_breach():
    """The bug being fixed, pinned so the comparison stays honest."""
    r = engine.acwr(_rows(_REAL_AU), stage=2, today=TODAY)
    assert r["acwr"] == pytest.approx(1.32, abs=0.01)
    assert r["exceeds_ceiling"] is True


# ── Stage scoping ────────────────────────────────────────────────────────────

def test_stage_scoped_chronic_excludes_prior_stage_days():
    r = engine.acwr(_rows(_REAL_AU), stage=2, today=TODAY, stage_start=STAGE_START)
    assert r["chronic_basis"] == "stage"
    assert r["in_stage_days"] == 15           # Jul 20 .. Aug 3 inclusive
    # 1959 AU over the 15 in-stage days, vs 91.8 over the flat calendar
    assert r["chronic_avg"] == pytest.approx(130.6, abs=0.1)
    assert r["acwr"] == pytest.approx(0.93, abs=0.01)
    assert r["exceeds_ceiling"] is False
    assert r["status"] == "optimal"


def test_acute_window_is_never_stage_scoped():
    """Acute stays a plain 7-day window — it measures recent load, not baseline."""
    flat  = engine.acwr(_rows(_REAL_AU), stage=2, today=TODAY)
    scoped = engine.acwr(_rows(_REAL_AU), stage=2, today=TODAY, stage_start=STAGE_START)
    assert flat["acute_avg"] == scoped["acute_avg"] == pytest.approx(121.3, abs=0.1)


def test_rest_day_does_not_read_as_overreach():
    """The headline defect: 2026-07-25..27 logged ZERO AU and still reported
    1.73 overreach under a calendar window, because the chronic term was
    Stage 1 rehab load."""
    rest_day = date(2026, 7, 26)
    au = {d: v for d, v in _REAL_AU.items() if d <= rest_day.isoformat()}

    flat = engine.acwr(_rows(au), stage=2, today=rest_day)
    assert flat["exceeds_ceiling"] is True            # the old behaviour

    scoped = engine.acwr(_rows(au), stage=2, today=rest_day, stage_start=STAGE_START)
    # Only 7 in-stage days exist by Jul 26 — below the floor, so the ratio is
    # explicitly not treated as diagnostic rather than asserted as a breach.
    assert scoped["baseline_established"] is False
    assert scoped["status"] == "baseline_establishing"
    assert scoped["hard_locked"] is False


# ── The minimum-in-stage-days floor ──────────────────────────────────────────

def test_below_floor_is_flagged_not_diagnostic_and_falls_back_to_calendar():
    start = TODAY - timedelta(days=engine.ACWR_MIN_IN_STAGE_DAYS - 2)
    r = engine.acwr(_rows(_uniform(28, 200.0)), stage=2, today=TODAY, stage_start=start)
    assert r["in_stage_days"] == engine.ACWR_MIN_IN_STAGE_DAYS - 1
    assert r["baseline_established"] is False
    assert r["chronic_basis"] == "calendar"
    assert r["status"] == "baseline_establishing"


def test_exactly_at_the_floor_switches_to_stage_scoping():
    start = TODAY - timedelta(days=engine.ACWR_MIN_IN_STAGE_DAYS - 1)
    r = engine.acwr(_rows(_uniform(28, 200.0)), stage=2, today=TODAY, stage_start=start)
    assert r["in_stage_days"] == engine.ACWR_MIN_IN_STAGE_DAYS
    assert r["baseline_established"] is True
    assert r["chronic_basis"] == "stage"


def test_floor_is_longer_than_the_acute_window():
    """A chronic window no longer than the 7-day acute one collapses toward
    1.0 by construction and would read 'fine' for any ramp whatsoever."""
    assert engine.ACWR_MIN_IN_STAGE_DAYS > 7


def test_young_baseline_never_hard_locks_even_with_enforcement_on():
    """Two independent reasons a breach may not lock. This pins the second one
    (young baseline) in isolation, with advisory mode switched off."""
    start = TODAY - timedelta(days=3)
    au = _uniform(21, 50.0, end=TODAY - timedelta(days=7)) | _uniform(7, 400.0)
    with mock.patch.object(engine, "ACWR_ADVISORY_MODE", False):
        r = engine.acwr(_rows(au), stage=2, today=TODAY, stage_start=start)
    assert r["exceeds_ceiling"] is True
    assert r["baseline_established"] is False
    assert r["hard_locked"] is False


# ── Direction-of-effect guard ────────────────────────────────────────────────

def test_downweighting_would_have_moved_the_wrong_way():
    """Prior-stage days live in the DENOMINATOR. Down-weighting them raises
    ACWR. Kept as an executable note so 'just weight the rehab days lower'
    is not tried again."""
    window = [(TODAY - timedelta(days=27 - i)) for i in range(28)]
    au = [_REAL_AU.get(d.isoformat(), 0.0) for d in window]
    acute = sum(au[-7:]) / 7
    pre  = [v for d, v in zip(window, au) if d < STAGE_START]
    cur  = [v for d, v in zip(window, au) if d >= STAGE_START]

    flat        = acute / (sum(pre) + sum(cur)) * 28
    downweighted = acute / (sum(pre) * 0.5 + sum(cur)) * 28
    excluded    = acute / (sum(cur) / len(cur))

    assert flat == pytest.approx(1.32, abs=0.01)
    assert downweighted == pytest.approx(1.50, abs=0.01)   # WORSE
    assert excluded == pytest.approx(0.93, abs=0.01)       # what we ship
    assert downweighted > flat > excluded


# ── Advisory mode ────────────────────────────────────────────────────────────

def test_advisory_mode_reports_the_breach_without_capping_volume():
    au = _uniform(21, 200.0, end=TODAY - timedelta(days=7)) | _uniform(7, 400.0)
    r = engine.acwr(_rows(au), stage=2, today=TODAY)
    assert r["exceeds_ceiling"] is True
    assert r["hard_locked"] is False
    assert r["advisory_mode"] is True

    note = engine.acwr_advisory_note(r, stage=2)
    assert note is not None and "Advisory" in note and "not enforced" in note.lower()


def test_ceiling_still_comes_from_rules_untouched():
    from services import rules
    for stage in (1, 2, 3):
        assert (engine.acwr([], stage=stage)["ceiling"]
                == rules.STAGE_CONSTRAINTS[stage]["acwr_ceiling"])


def test_advisory_note_is_silent_when_nothing_to_say():
    r = engine.acwr(_rows(_uniform(28, 200.0)), stage=2, today=TODAY)
    assert r["status"] == "optimal"
    assert engine.acwr_advisory_note(r, stage=2) is None


def test_advisory_note_explains_a_young_baseline():
    start = TODAY - timedelta(days=2)
    r = engine.acwr(_rows(_uniform(28, 200.0)), stage=2, today=TODAY, stage_start=start)
    note = engine.acwr_advisory_note(r, stage=2)
    assert note is not None and "still establishing" in note


def test_volume_recommendation_carries_the_advisory_on_every_branch():
    """The note rides along regardless of which directive branch wins."""
    au = _uniform(21, 200.0, end=TODAY - timedelta(days=7)) | _uniform(7, 400.0)
    ac = engine.acwr(_rows(au), stage=2, today=TODAY)
    tl_grey = engine.traffic_light([])          # insufficient_data branch
    rec = engine.volume_recommendation(tl_grey, ac, 2, 0, injury_weight_val=0.3)
    assert rec["acwr_advisory"] is not None
    assert rec["multiplier"] == 1.0             # directive itself unchanged


# ── plan.current_stage_start ─────────────────────────────────────────────────

def _phase(num: int, start: str, length: int, status: str = "active") -> Phase:
    return Phase(phase_number=num, name=f"Phase {num}", start_date=start,
                 length_days=length, status=status, date_overrides={})


def test_current_stage_start_returns_the_active_phase_start():
    phases = [_phase(1, "2026-06-29", 21, "completed"),
              _phase(2, "2026-07-20", 28)]
    assert plan_svc.current_stage_start(phases, TODAY) == STAGE_START


def test_current_stage_start_is_none_in_a_reassessment_gap():
    """None is a safe answer — acwr() falls back to the calendar window."""
    phases = [_phase(1, "2026-06-29", 21, "completed")]
    assert plan_svc.current_stage_start(phases, TODAY) is None
    assert plan_svc.current_stage_start([], TODAY) is None
