"""The overall strain number must not move.

THIS FILE EXISTS TO BE BORING. It was written and committed against the
UNMODIFIED tree, before per-region strain existed, and every expected value in
it was PASTED from a read-only run of that tree — never recomputed from the
code under test. A test that calls the function to build its own expectation
pins nothing.

Localising strain is additive information: three regional readings beside the
headline. It is not a re-derivation of the headline. So the acceptance
criterion for the whole change is that every number and every key below is
bit-identical afterwards. If a regional feature moves one of these, the
regional feature is wrong.

The golden tables also pin the two persistence shapes that CLAUDE.md records as
traps: `_METRICS_HISTORY_HEADER` is positional and append-only (a tab created
before a column joined it discards that column forever — this already bit
`hrv_ms`), and `home_snapshot` keys a fixed set that the durable Home cache
round-trips.
"""

from datetime import date, timedelta

import pytest

from services import dashboard, engine, home_snapshot, readiness
from services import repository as repo_mod


# ─── the shared 0-21 curve ───────────────────────────────────────────────────

@pytest.mark.parametrize("load,expected", [
    (0, 0.0), (-5, 0.0), (1, 2.3), (10, 7.9), (100, 15.1),
    (300, 18.7), (600, 21.0), (601, 21.0), (5000, 21.0),
])
def test_load_to_strain_is_untouched(load, expected):
    assert engine.load_to_strain(load) == expected


@pytest.mark.parametrize("au,stage,expected", [
    (100.0, 1, 5.3), (100.0, 2, 12.2), (100.0, 3, 15.1),
    (360.0, 1, 9.0), (360.0, 2, 16.3), (360.0, 3, 19.3),
    (600.0, 1, 10.6), (600.0, 2, 18.0), (600.0, 3, 21.0),
])
def test_au_to_strain_is_untouched(au, stage, expected):
    assert engine.au_to_strain(au, stage) == expected


def test_the_strain_curve_saturates_where_it_always_did():
    assert engine.STRAIN_CURVE_ANCHOR == 601.0
    assert engine.STAGE_CLF == {1: 0.04, 2: 0.40, 3: 1.0}


# ─── the step modifier ───────────────────────────────────────────────────────

_STEP_BASELINE = [7000, 7100, 6900, 7050, 6950, 7000, 7100]


@pytest.mark.parametrize("yesterday,expected", [
    (14000, 1.5), (3000, -1.0), (7000, 0.0), (None, 0.0),
])
def test_step_strain_modifier_is_untouched(yesterday, expected):
    assert engine.step_strain_modifier(yesterday, _STEP_BASELINE) == expected


def test_step_modifier_needs_four_baseline_days():
    assert engine.step_strain_modifier(14000, [7000, 7100, 6900]) == 0.0


# ─── the rolling stand-in ────────────────────────────────────────────────────

def test_rolling_prior_strain_is_untouched():
    assert dashboard.rolling_prior_strain(
        [{"date": "2026-07-06", "total_au": 700.0}], 1, today=date(2026, 7, 7),
    ) == 5.3
    # Today's own AU is outside the prior-7-days window.
    assert dashboard.rolling_prior_strain(
        [{"date": "2026-07-07", "total_au": 500.0}], 1, today=date(2026, 7, 7),
    ) is None


# ─── the snapshot: keys, then values ─────────────────────────────────────────

_SNAPSHOT_KEYS = frozenset({
    "readiness_score", "sleep_pct", "sleep_score", "strain",
    "strain_is_rolling", "strain_source", "strain_source_label",
    "strain_rpe_only", "strain_hr_only", "hr_detail",
})

_D = date(2026, 7, 20)


def _step_bio(yesterday_steps: int) -> list[dict]:
    rows = [{"date": (_D - timedelta(days=1)).isoformat(), "steps": yesterday_steps}]
    rows += [
        {"date": (_D - timedelta(days=n)).isoformat(), "steps": s}
        for n, s in zip(range(2, 9), _STEP_BASELINE)
    ]
    return rows


# (label, au_rows, stage, hr_rows, bio_rows,
#  strain, source, is_rolling, rpe_only, hr_only)
_MATRIX = [
    ("rpe_stage2",   [{"date": "2026-07-20", "total_au": 360.0}], 2, None, [],
     16.3, "rpe", False, 16.3, None),
    ("rpe_stage1",   [{"date": "2026-07-20", "total_au": 360.0}], 1, None, [],
     9.0, "rpe", False, 9.0, None),
    ("rpe_stage3",   [{"date": "2026-07-20", "total_au": 360.0}], 3, None, [],
     19.3, "rpe", False, 19.3, None),
    ("hr_blend",     [{"date": "2026-07-20", "total_au": 360.0}], 2,
     [{"date": "2026-07-20", "hr_strain": 19.0}], [],
     18.2, "blended", False, 16.3, 19.0),
    ("hr_only",      [], 2, [{"date": "2026-07-20", "hr_strain": 19.0}], [],
     19.0, "hr", False, None, 19.0),
    ("hr_other_day", [{"date": "2026-07-20", "total_au": 360.0}], 2,
     [{"date": "2026-07-19", "hr_strain": 19.0}], [],
     16.3, "rpe", False, 16.3, None),
    ("rolling",      [{"date": "2026-07-13", "total_au": 700.0}], 1, None, [],
     5.3, "none", True, None, None),
    ("nodata",       [], 2, None, [],
     None, "none", False, None, None),
    ("steps_high",   [{"date": "2026-07-20", "total_au": 360.0}], 2, None,
     _step_bio(14000), 17.8, "rpe", False, 16.3, None),
    ("steps_low",    [{"date": "2026-07-20", "total_au": 360.0}], 2, None,
     _step_bio(3000), 15.3, "rpe", False, 16.3, None),
]


@pytest.mark.parametrize("case", _MATRIX, ids=[c[0] for c in _MATRIX])
def test_compute_daily_metrics_snapshot_is_bit_identical(case):
    (_label, au_rows, stage, hr_rows, bio_rows,
     strain, source, is_rolling, rpe_only, hr_only) = case
    snap = dashboard.compute_daily_metrics_snapshot(
        _D, bio_rows, au_rows, stage, hr_rows=hr_rows,
    )
    assert snap["strain"] == strain
    assert snap["strain_source"] == source
    assert snap["strain_is_rolling"] is is_rolling
    assert snap["strain_rpe_only"] == rpe_only
    assert snap["strain_hr_only"] == hr_only


def test_compute_daily_metrics_snapshot_returns_exactly_these_keys():
    """Deliberately duplicates tests/test_dashboard.py's own key assertion.
    THIS file's name is what tells a future reader why the set must not grow:
    three consumers read it positionally or by literal key set —
    Repository._metrics_history_row (bracket access, so a rename KeyErrors),
    home_snapshot.build, and the Home page itself. A regional metric belongs in
    a SIBLING function, not in here."""
    snap = dashboard.compute_daily_metrics_snapshot(
        _D, [], [{"date": "2026-07-20", "total_au": 360.0}], 2,
    )
    assert set(snap) == _SNAPSHOT_KEYS


# ─── persistence shapes ──────────────────────────────────────────────────────

def test_metrics_history_header_is_unchanged():
    """Positional and append-only. Widening it without a one-time
    Repository.rebuild_metrics_history() makes every read silently discard the
    new column — the failure that already bit hrv_ms on the Garmin Daily tab."""
    assert repo_mod._METRICS_HISTORY_HEADER == [
        "date", "readiness_score", "sleep_pct", "sleep_score", "strain",
        "readiness_model_version",
    ]


def test_metrics_history_row_still_uses_bracket_access_for_strain():
    """Pins the documented trap rather than papering over it: the existing keys
    are read with [...], so a snapshot missing one raises instead of writing a
    blank. Any NEW key added later must use .get()."""
    repo = repo_mod.Repository.__new__(repo_mod.Repository)
    with pytest.raises(KeyError):
        repo._metrics_history_row({
            "date": "2026-07-20", "readiness_score": 50.0,
            "sleep_pct": 90, "sleep_score": 80.0,
        })


def test_metrics_history_row_maps_a_populated_snapshot_unchanged():
    repo = repo_mod.Repository.__new__(repo_mod.Repository)
    row = repo._metrics_history_row({
        "date": "2026-07-20", "readiness_score": 50.0, "sleep_pct": 90,
        "sleep_score": 80.0, "strain": 16.3,
    })
    assert row == {
        "date": "2026-07-20", "readiness_score": 50.0, "sleep_pct": 90,
        "sleep_score": 80.0, "strain": 16.3,
        "readiness_model_version": readiness.MODEL_VERSION,
    }


def test_home_snapshot_entry_shape_is_unchanged():
    snap = dashboard.compute_daily_metrics_snapshot(
        _D, [], [{"date": "2026-07-20", "total_au": 360.0}], 2,
    )
    entry = home_snapshot.build(snap, 8.0, 56)
    assert set(entry) == {
        "schema", "computed_at", "readiness_score", "sleep_score",
        "strain", "strain_is_rolling", "sleep_need_hours",
        "sleep_baseline_window",
    }
    assert home_snapshot.SCHEMA_VERSION == 1
