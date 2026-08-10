"""Per-region ACWR — advisory, floored, and structurally unable to cap volume.

Two things are being pinned here, and the second is the important one.

BEHAVIOUR. engine.acwr's ratio is scale-free and ACWR_MIN_IN_STAGE_DAYS counts
CALENDAR days in the stage rather than days THIS REGION was loaded. Measured
directly, with stage_start = today-20, a region whose entire in-stage load is a
single session reads ACWR 3.00 with baseline_established=True — and reads the
identical 3.00 whether that session was 300 AU or a 1.5 AU wall slide. If all
of a region's in-stage load lands in the acute window the ratio is exactly N/7
for an N-day in-stage window, independent of AU. So a regional ratio needs a
floor the global one does not have.

STRUCTURE. The regional numbers rest on invented weights. They must not be able
to gate anything, ever, and the guard for that is the import graph rather than
a promise: services/engine.py and services/rules.py may not mention this
module, and this module may not mention the volume path.
"""

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from services import dashboard, engine, rules, strain_regions as sr

TODAY = date(2026, 7, 31)
REGIONS = sr.REGIONS


def _row(d: date, upper=0.0, core=0.0, lower=0.0) -> dict:
    return {"date": d.isoformat(), "upper_body": upper, "core": core,
            "lower_body": lower}


def _even_rows(n: int = 28, per_day: float = 40.0) -> list[dict]:
    return [_row(TODAY - timedelta(days=k), per_day, per_day, per_day)
            for k in range(n)]


# ─── delegation ──────────────────────────────────────────────────────────────

def test_region_acwr_delegates_to_engine_acwr(monkeypatch):
    """One implementation of the stage-scoped chronic window, the ceiling
    table and hard_locked. A parallel copy would be a second place to get the
    prior-stage-exclusion decision wrong — and that one was already measured
    moving ACWR the WRONG way when down-weighted."""
    calls = []
    real = engine.acwr

    def spy(rows, stage=1, today=None, stage_start=None):
        calls.append((stage, today, stage_start))
        return real(rows, stage, today=today, stage_start=stage_start)

    monkeypatch.setattr(engine, "acwr", spy)
    start = TODAY - timedelta(days=27)
    sr.region_acwr(_even_rows(), 2, today=TODAY, stage_start=start)
    assert len(calls) == 3
    assert all(c == (2, TODAY, start) for c in calls)


def test_the_ceiling_is_the_stage_ceiling_not_a_regional_one():
    """No regional ceiling table exists — three more invented safety constants
    nobody could validate."""
    out = sr.region_acwr(_even_rows(), 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=27))
    expected = rules.STAGE_CONSTRAINTS[2]["acwr_ceiling"]
    for region in REGIONS:
        assert out[region]["ceiling"] == expected


# ─── never caps volume ───────────────────────────────────────────────────────

def test_region_acwr_never_hard_locks_in_advisory_mode():
    out = sr.region_acwr(
        _even_rows(7, 60.0) + [_row(TODAY - timedelta(days=k), 3.0, 3.0, 3.0)
                               for k in range(7, 28)],
        2, today=TODAY, stage_start=TODAY - timedelta(days=27),
    )
    for region in REGIONS:
        assert out[region]["hard_locked"] is False
        assert out[region]["advisory_only"] is True


def test_region_acwr_never_hard_locks_even_with_advisory_mode_off(monkeypatch):
    """THE one that matters. engine.ACWR_ADVISORY_MODE is a dated hold that is
    expected to be flipped one day; a regional ratio built on invented weights
    is not the thing that should start capping volume on that day. The raw
    fact is still carried, exactly as the global one carries it."""
    monkeypatch.setattr(engine, "ACWR_ADVISORY_MODE", False)
    rows = ([_row(TODAY - timedelta(days=k), 50.0, 50.0, 50.0) for k in range(7)]
            + [_row(TODAY - timedelta(days=k), 5.0, 5.0, 5.0) for k in range(7, 28)])
    out = sr.region_acwr(rows, 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=27))
    for region in REGIONS:
        assert out[region]["acwr"] is not None, region
        assert out[region]["exceeds_ceiling"] is True, region
        assert out[region]["hard_locked"] is False, region


def _referenced_names(path: str) -> set[str]:
    """Every identifier the MODULE ACTUALLY EXECUTES — attributes, bare names
    and imported module names. Parsed rather than grepped so the docstring can
    name the forbidden things (it has to, to explain the rule) without
    tripping the rule."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.update(alias.name.split("."))
                if alias.asname:
                    names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            names.update((node.module or "").split("."))
            for alias in node.names:
                names.add(alias.name)
                if alias.asname:
                    names.add(alias.asname)
    return names


def test_regional_strain_cannot_reach_the_volume_path():
    """Structural, not behavioural: a future edit cannot quietly wire a
    regional number into a decision without failing this."""
    used = _referenced_names("services/strain_regions.py")
    for forbidden in ("volume_recommendation", "STAGE_CONSTRAINTS", "rules"):
        assert forbidden not in used, forbidden
    for consumer in ("services/engine.py", "services/rules.py"):
        assert "strain_regions" not in _referenced_names(consumer), consumer


# ─── the floors ──────────────────────────────────────────────────────────────

def test_a_single_session_region_reports_no_ratio():
    """Without the floor this reads ACWR 3.00, overreach_risk,
    baseline_established=True — off one session."""
    out = sr.region_acwr([_row(TODAY, upper=300.0)], 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=20))
    assert out["upper_body"]["acwr"] is None
    assert out["upper_body"]["status"] == sr.STATUS_INSUFFICIENT_REGIONAL_LOAD
    assert out["upper_body"]["exceeds_ceiling"] is False


def test_the_withheld_ratio_is_the_same_for_a_wall_slide_and_a_heavy_session():
    """The scale-free failure, stated as a test: before the floor these two
    were indistinguishable at 3.00. Now they are indistinguishable at 'not
    enough', which is the honest answer."""
    big = sr.region_acwr([_row(TODAY, upper=300.0)], 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=20))
    tiny = sr.region_acwr([_row(TODAY, upper=1.5)], 2, today=TODAY,
                          stage_start=TODAY - timedelta(days=20))
    assert big["upper_body"]["acwr"] is tiny["upper_body"]["acwr"] is None
    assert big["upper_body"]["status"] == tiny["upper_body"]["status"]


def test_the_facts_behind_a_withheld_ratio_are_still_reported():
    """Report the fact, withhold the number — the shape baseline_establishing
    already uses."""
    out = sr.region_acwr([_row(TODAY, upper=300.0)], 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=20))["upper_body"]
    assert out["loaded_days"] == 1
    assert out["min_loaded_days"] == sr.REGION_ACWR_MIN_LOADED_DAYS
    assert out["acute_avg"] > 0
    assert "chronic_share" in out


def test_a_thin_chronic_share_reports_no_ratio():
    """Loaded often enough, but a rounding error against the other two."""
    rows = [_row(TODAY - timedelta(days=k), upper=0.5, lower=200.0)
            for k in range(28)]
    out = sr.region_acwr(rows, 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=27))
    assert out["upper_body"]["chronic_share"] < sr.REGION_ACWR_MIN_CHRONIC_SHARE
    assert out["upper_body"]["acwr"] is None
    assert out["lower_body"]["acwr"] is not None


def test_a_well_loaded_region_still_reports_its_ratio():
    """The floor must not swallow the signal it was added to protect. Over the
    28 days to 2026-07-31 the athlete's regions were loaded on 19, 18 and 13
    days, so this is his real pattern, not a contrived one."""
    rows = ([_row(TODAY - timedelta(days=k), 50.0, 50.0, 50.0) for k in range(7)]
            + [_row(TODAY - timedelta(days=k), 20.0, 20.0, 20.0) for k in range(7, 28)])
    out = sr.region_acwr(rows, 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=27))
    for region in REGIONS:
        assert out[region]["acwr"] is not None, region
        assert out[region]["loaded_days"] == 28, region


def test_below_the_stage_baseline_the_status_is_baseline_establishing():
    rows = _even_rows()
    out = sr.region_acwr(rows, 2, today=TODAY, stage_start=TODAY - timedelta(days=5))
    for region in REGIONS:
        assert out[region]["status"] == "baseline_establishing"
        assert out[region]["hard_locked"] is False


def test_a_region_with_no_load_at_all_does_not_divide_by_zero():
    out = sr.region_acwr([_row(TODAY, lower=100.0)], 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=27))
    assert out["upper_body"]["acwr"] is None
    assert out["upper_body"]["loaded_days"] == 0


def test_the_floor_constants_are_flagged_as_invented():
    src = Path("services/strain_regions.py").read_text(encoding="utf-8")
    assert "INVENTED" in src
    assert "REVERT CONDITION" in src
    assert sr.REGION_ACWR_MIN_LOADED_DAYS > 0
    assert 0.0 < sr.REGION_ACWR_MIN_CHRONIC_SHARE < 1.0


# ─── how it reads on screen ──────────────────────────────────────────────────

def test_an_establishing_baseline_is_grey_and_says_why():
    """It must not be distinguishable from a good score only by a shade of
    grey on a phone in daylight."""
    out = sr.region_acwr(_even_rows(), 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=5))
    shown = dashboard.strain_region_acwr_display(out["upper_body"])
    assert shown["diagnostic"] is False
    assert shown["colour"] == "#4A5568"
    assert "not diagnostic" in shown["reason"]


def test_a_withheld_regional_ratio_reads_as_a_dash_never_a_zero():
    out = sr.region_acwr([_row(TODAY, upper=300.0)], 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=20))
    shown = dashboard.strain_region_acwr_display(out["upper_body"])
    assert shown["value"] == "ACWR —"
    assert "0.00" not in shown["value"]
    assert shown["diagnostic"] is False


def test_a_missing_result_reads_as_no_load_rather_than_an_error():
    shown = dashboard.strain_region_acwr_display(None)
    assert shown["value"] == "ACWR —"
    assert shown["reason"] == "no load in window"


def test_a_real_breach_is_coloured_and_names_the_ceiling(monkeypatch):
    rows = ([_row(TODAY - timedelta(days=k), 50.0, 50.0, 50.0) for k in range(7)]
            + [_row(TODAY - timedelta(days=k), 5.0, 5.0, 5.0) for k in range(7, 28)])
    out = sr.region_acwr(rows, 2, today=TODAY,
                         stage_start=TODAY - timedelta(days=27))
    shown = dashboard.strain_region_acwr_display(out["upper_body"])
    assert shown["diagnostic"] is True
    assert shown["colour"] == "#C47878"
    assert "ceiling" in shown["reason"]


@pytest.mark.parametrize("status,expected", [
    ("optimal", True), ("undertraining", True), ("overreach_risk", True),
    ("baseline_establishing", False), ("insufficient_regional_load", False),
    ("insufficient_chronic_data", False),
])
def test_only_a_verdict_status_is_marked_diagnostic(status, expected):
    result = {"status": status, "acwr": None if not expected else 1.0,
              "ceiling": 1.3, "in_stage_days": 5, "loaded_days": 2,
              "min_loaded_days": 8}
    assert dashboard.strain_region_acwr_display(result)["diagnostic"] is expected
