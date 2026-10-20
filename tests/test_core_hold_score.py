"""The core hold score (WP-15 step 6, decided 2026-10-13, built 2026-10-16).

docs/core_hold_index_design_2026-10-13.md: core has no 2025 kilogram, so it is
scored on hold time — each Bunkie line held until the line breaks, the worse
side against the 2025 log's nearest hold, × 100; core's index is the mean of
the lateral and medial lines. It is shown on core's card from the first test,
marked provisional, and stays out of the headline. The seconds are typed in
for each side: `tut` holds the right, `tut_left` the left.
"""
import re
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

import goal_block as gb
import strength_baselines as sb
from services import sessions as sess
from services import strength

ROOT = Path(__file__).resolve().parent.parent
LATERAL = "Bunkie — Lateral Stabilizing Line (Timed)"
MEDIAL = "Bunkie — Medial Stabilizing Line (Timed)"


def _row(name, day, right, left=None):
    s = {"set_num": 1, "reps": 1, "weight": 0.0, "tut": right, "velocity": "isometric"}
    if left is not None and left != right:
        s["tut_left"] = left
    return {"movement_name": name, "session_date": day, "sets": [s]}


# ─── The capture ────────────────────────────────────────────────────────────

def test_the_plank_test_lines_are_timed_tests_and_ordinary_holds_are_not():
    for e in gb.PLANK_TEST:
        assert sess.is_timed_test(e), e["name"]
    assert not sess.is_timed_test({"name": "Full Side Bridge", "type": "hold"})
    assert not sess.is_timed_test({"name": "Hack Squat", "type": "reps"})


def test_the_seconds_go_to_the_right_side_and_the_left_side():
    entry = sess.timed_hold_entry(None, "left", 52)
    entry = sess.timed_hold_entry(entry, "right", 61)
    assert entry == {"tut": 61, "tut_left": 52}


def test_a_timed_test_set_records_the_seconds_held_not_the_reference():
    ex = gb.PLANK_TEST[3]
    rec = sess.build_set_record(ex, 1, {"tut": 61, "tut_left": 52}, "ts")
    assert (rec["tut"], rec["tut_left"]) == (61, 52)
    same = sess.build_set_record(ex, 1, {"tut": 45, "tut_left": 45}, "ts")
    assert same["tut"] == 45 and "tut_left" not in same


def test_an_ordinary_hold_still_logs_its_prescribed_time():
    ex = {"name": "Full Side Bridge", "type": "hold", "hold_seconds": 30, "rest_seconds": 45}
    rec = sess.build_set_record(ex, 1, None, "ts")
    assert rec["tut"] == 30 and "tut_left" not in rec


# ─── The storage: every projection carries the new field ────────────────────

def test_every_projection_of_a_set_row_carries_tut_left():
    import inspect

    from services import datastore, reconcile, repository
    from services.clients import notion_reader

    for label, src in (
        ("Supabase write", inspect.getsource(repository.Repository._mirror_training_write)),
        ("datastore populate", inspect.getsource(datastore._populate_training)),
        ("offline restore", inspect.getsource(notion_reader._restore_set)),
    ):
        assert '"tut_left"' in src, f"tut_left missing from the {label} projection"
    assert "tut_left" in reconcile._SET_FIELDS
    assert "tut_left" in notion_reader._INTEGRAL_SET_FIELDS


def test_the_migration_adds_the_column_the_schema_has():
    from services import datastore_postgres as dp

    migration = ROOT / "scripts" / "migrate_2026-10-16_training_sets_tut_left.sql"
    text = migration.read_text(encoding="utf-8")
    added = set(re.findall(r"ADD COLUMN IF NOT EXISTS (\w+)", text))
    assert added == {"tut_left"}
    assert "DROP" not in text.replace("DROP TABLE ... CASCADE", "")
    block = re.search(r"CREATE TABLE training_sets \((.*?)\n\);", dp.to_postgres(), re.S).group(1)
    assert re.search(r"^\s{4}tut_left\s+DOUBLE PRECISION", block, re.M)
    sqlite = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")
    assert re.search(r"^\s{4}tut_left\s+REAL", sqlite, re.M)


def test_a_set_with_its_left_seconds_round_trips_through_sqlite():
    import sqlite3

    from services.clients import notion_reader

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE training_sets (set_num INTEGER, reps REAL, weight REAL, "
                 "rest REAL, tut REAL, velocity TEXT, band_tier TEXT, ts TEXT, "
                 "is_warmup INTEGER DEFAULT 0, rest_taken_seconds REAL, "
                 "reps_left REAL, weight_left REAL, tut_left REAL)")
    conn.execute("INSERT INTO training_sets VALUES (1, 1.0, 0.0, 60.0, 61.0, 'isometric', "
                 "NULL, 'ts', 0, NULL, NULL, NULL, 52.0)")
    out = notion_reader._restore_set(conn.execute("SELECT * FROM training_sets").fetchone())
    assert out["tut"] == 61 and out["tut_left"] == 52 and isinstance(out["tut_left"], int)


# ─── The score ──────────────────────────────────────────────────────────────

def test_the_2025_references_are_the_design_s():
    assert sb.HOLD_BASELINES_2025[LATERAL][0] == 15.0
    assert sb.HOLD_BASELINES_2025[MEDIAL][0] == 30.0
    assert sb.HOLD_COMPARABILITY == 0.6
    assert set(sb.HOLD_BASELINES_2025) <= {e["name"] for e in gb.PLANK_TEST}


def test_no_test_no_score():
    assert strength.core_hold_index([], sb.HOLD_BASELINES_2025) is None
    other = [_row("Bunkie — Posterior Power Line (Timed)", "2026-10-19", 50)]
    assert strength.core_hold_index(other, sb.HOLD_BASELINES_2025) is None


def test_the_worse_side_counts_and_core_is_the_mean_of_its_lines():
    rows = [_row(LATERAL, "2026-10-19", 33, 27), _row(MEDIAL, "2026-10-19", 45)]
    out = strength.core_hold_index(rows, sb.HOLD_BASELINES_2025, today=date(2026, 10, 20))
    by = {l["name"]: l for l in out["lines"]}
    assert by[LATERAL]["worse"] == 27 and by[LATERAL]["index"] == 180.0
    assert by[MEDIAL]["worse"] == 45 and by[MEDIAL]["index"] == 150.0
    assert out["index"] == 165.0 and out["date"] == date(2026, 10, 19)


def test_the_latest_test_of_each_line_is_the_one_read():
    rows = [_row(LATERAL, "2026-10-19", 20), _row(LATERAL, "2027-01-04", 30),
            _row(MEDIAL, "2026-10-19", 30)]
    out = strength.core_hold_index(rows, sb.HOLD_BASELINES_2025, today=date(2027, 1, 5))
    assert {l["name"]: l["index"] for l in out["lines"]}[LATERAL] == 200.0
    early = strength.core_hold_index(rows, sb.HOLD_BASELINES_2025, today=date(2026, 12, 1))
    assert {l["name"]: l["index"] for l in early["lines"]}[LATERAL] == 133.3


def test_the_score_stays_out_of_the_headline():
    rows = [_row(LATERAL, "2026-10-19", 33, 27), _row(MEDIAL, "2026-10-19", 45)]
    kwargs = dict(rows=rows, peaks=sb.PEAKS_2025, region_map={}, movement_weights={},
                  prior=sb.REGION_PRIOR, pr_rir=sb.PR_RIR, today=date(2026, 10, 20))
    without = strength.screen(**kwargs)
    with_holds = strength.screen(**kwargs, hold_baselines=sb.HOLD_BASELINES_2025)
    assert without["core_hold"] is None and with_holds["core_hold"]["index"] == 165.0
    assert with_holds["overall"] == without["overall"]
    assert [r.contribution_points for r in with_holds["regions"]] == \
        [r.contribution_points for r in without["regions"]]


def test_core_s_card_shows_the_hold_time_marked_provisional():
    from views import insights as V

    rows = [_row(LATERAL, "2026-10-19", 33, 27), _row(MEDIAL, "2026-10-19", 45)]
    snap = strength.screen(rows, sb.PEAKS_2025, {}, {}, sb.REGION_PRIOR, sb.PR_RIR,
                           today=date(2026, 10, 20), hold_baselines=sb.HOLD_BASELINES_2025)
    html = V._strength_region_strip_html(snap["regions"], snap["core_hold"])
    assert "Hold time <em>165.0</em>" in html
    assert "provisional · hold time" in html
    plain = V._strength_region_strip_html(snap["regions"])
    assert "Hold time" not in plain and "Index <em>—</em>" in plain
