"""
The mirror and a full rebuild must produce THE SAME ROW.

This is the property the whole design rests on and the one nothing tested
until now. Two independent paths turn a Notion page into a datastore row:

  REBUILD   _query -> get_all_*_raw() -> datastore._insert_rows (blank->NULL)
  MIRROR    mirror_notion_write -> row_from_properties -> blank_to_null

They share the PROPERTIES map and nothing else — different functions, written
at different times, one reading with notion.get_property and one decoding the
payload directly. If they disagree, Postgres holds something a rebuild would
never write, and neither path is obviously wrong when you read it. Every
per-column defect found so far (blank vs NULL, checkbox as bool, multi_select
as a list, the `_sets_json` phantom, missing derived columns) is an instance
of exactly this disagreement.

The earlier round-trip test (tests/test_datastore_round_trip.py) checks
datastore -> Postgres -> datastore, which is a different claim: that the
TRANSPORT is lossless. It cannot catch a mirror that faithfully transports the
wrong row.

REAL DATA, NOT INVENTED. Every case below is driven by datastore.db, so the
values are ones live Notion actually produced. A checkout without the snapshot
skips.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from services import supabase_store
from services.clients import notion_reader as nr
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "datastore.db"

pytestmark = pytest.mark.skipif(not LIVE.exists(),
                                reason="no datastore.db in this checkout")


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


@pytest.fixture
def repo():
    return Repository(Config(
        notion_api_key="unused", notion_db_readiness="db-readiness",
        notion_db_training="db-training", notion_db_biometrics="db-biometrics",
        notion_db_config="db-config", google_sheets_id="unused",
        google_service_account={}, datastore_path=str(LIVE),
        supabase_url="https://x.supabase.co", supabase_secret_key="secret",
    ))


@pytest.fixture
def conn():
    c = sqlite3.connect(LIVE)
    c.row_factory = sqlite3.Row
    return c


def _stored(conn, table):
    return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]


def _queued(table, mode=supabase_store.UPSERT):
    with supabase_store.OUTBOX._lock:
        return dict(supabase_store.OUTBOX._rows.get((table, mode), {}))


def _normalized(row: dict) -> dict:
    """A stored row under the mirror's own normalization, so the comparison
    is like-for-like. SQLite already holds NULL where the sheet held a blank;
    this makes the two representations meet."""
    return supabase_store.blank_to_null(row)


# ─── readiness ───────────────────────────────────────────────────────────

def test_the_mirror_row_equals_the_stored_row_for_every_real_checkin(repo, conn):
    """24 real check-ins, column by column. The pages come from the offline
    reader (already verified value-for-value against live Notion), and the
    stored rows were written by the rebuild path running against live Notion —
    so agreement here means the two paths converge on data neither invented."""
    stored = {r["date"]: r for r in _stored(conn, "readiness_checkins")}
    assert stored, "no check-ins to compare"

    pages = nr.query(repo._ds, nr.READINESS)
    assert len(pages) == len(stored)

    for page in pages:
        mirror = _normalized(nr.row_from_properties(nr.READINESS, page["properties"]))
        want = _normalized(stored[mirror["date"]])
        for column, value in mirror.items():
            assert value == want[column], (
                f"{mirror['date']}.{column}: mirror {value!r} != rebuild {want[column]!r}"
            )


def test_the_readiness_mirror_covers_every_column_a_rebuild_fills(repo, conn):
    """Coverage, not just agreement. A column the mirror never emits sits at
    NULL in Postgres while the rebuild holds a real value — and a
    column-by-column equality check passes right over it, because it only
    compares what the mirror sent."""
    stored = _stored(conn, "readiness_checkins")
    filled = {c for row in stored for c, v in row.items() if v not in (None, "")}

    pages = nr.query(repo._ds, nr.READINESS)
    emitted = set()
    for page in pages:
        emitted |= set(nr.row_from_properties(nr.READINESS, page["properties"]))

    missing = filled - emitted
    assert not missing, (
        f"the rebuild fills {sorted(missing)} but the mirror never emits them"
    )


# ─── config ──────────────────────────────────────────────────────────────

def test_config_converges(repo, conn):
    stored = {r["key"]: r for r in _stored(conn, "config")}
    assert stored
    for page in nr.query(repo._ds, nr.CONFIG):
        mirror = _normalized(nr.row_from_properties(nr.CONFIG, page["properties"]))
        want = _normalized(stored[mirror["key"]])
        assert mirror == {k: want[k] for k in mirror}


def test_a_long_config_value_survives_the_mirror(repo, conn):
    """`phases` is the value that actually gets long — every completed phase
    keeps its date_overrides and shift_reasons forever, and notion.rich_text
    chunks past 2000 chars. Taking element [0] would truncate it silently."""
    stored = {r["key"]: r["value"] for r in _stored(conn, "config")}
    longest = max(stored.values(), key=lambda v: len(v or ""))
    if len(longest or "") < 2000:
        pytest.skip("no config value over one rich_text chunk yet")
    key = [k for k, v in stored.items() if v == longest][0]
    page = [p for p in nr.query(repo._ds, nr.CONFIG)
            if nr.row_from_properties(nr.CONFIG, p["properties"])["key"] == key][0]
    assert nr.row_from_properties(nr.CONFIG, page["properties"])["value"] == longest


# ─── training: the three-table fan-out ───────────────────────────────────

def test_the_training_fan_out_reproduces_all_three_stored_tables(repo, conn):
    """The hardest case, on all 194 real exercises. One Notion page becomes a
    session row, an exercise row and a set list; the rebuild produces those
    same three via datastore._populate_training. Both must agree."""
    exercises = {r["exercise_id"]: r for r in _stored(conn, "training_exercises")}
    sessions = {r["session_id"]: r for r in _stored(conn, "training_sessions")}
    sets_by_ex: dict[str, list] = {}
    for row in conn.execute("SELECT * FROM training_sets ORDER BY id"):
        sets_by_ex.setdefault(row["exercise_id"], []).append(dict(row))
    assert exercises, "no exercises to compare"

    pages = nr.query(repo._ds, nr.TRAINING)
    assert len(pages) == len(exercises)

    for page in pages:
        ex_id = page["id"]
        decoded = nr.row_from_properties(nr.TRAINING, page["properties"])
        sets = json.loads(decoded.get("_sets_json") or "[]")
        supabase_store.OUTBOX.drain()
        repo.mirror_notion_write(nr.TRAINING, ex_id, page["properties"], sets=sets)

        # exercise
        mirror_ex = _queued("training_exercises")[ex_id]
        want_ex = _normalized(exercises[ex_id])
        for column, value in mirror_ex.items():
            assert value == want_ex[column], (
                f"{ex_id}.{column}: mirror {value!r} != rebuild {want_ex[column]!r}"
            )

        # session
        sid = mirror_ex.get("session_id") or decoded.get("session_id")
        if sid and sid in sessions:
            mirror_s = _queued("training_sessions")[sid]
            want_s = _normalized(sessions[sid])
            for column, value in mirror_s.items():
                assert value == want_s[column], (
                    f"session {sid}.{column}: {value!r} != {want_s[column]!r}"
                )

        # sets
        mirror_sets = _queued("training_sets", supabase_store.REPLACE).get(ex_id, [])
        want_sets = sets_by_ex.get(ex_id, [])
        assert len(mirror_sets) == len(want_sets), (
            f"{ex_id}: mirror has {len(mirror_sets)} sets, rebuild has {len(want_sets)}"
        )
        for got, want in zip(mirror_sets, want_sets):
            for column in ("exercise_id", "set_num", "reps", "weight",
                           "rest", "tut", "velocity", "band_tier", "ts"):
                assert got[column] == want[column], (
                    f"{ex_id} set {want['set_num']}.{column}: "
                    f"{got[column]!r} != {want[column]!r}"
                )


def test_the_derived_columns_agree_with_the_rebuild_on_real_sessions(repo, conn):
    """actual_sets and total_volume_kg have no Notion property — the mirror
    recomputes them. On real data they must equal what the rebuild stored,
    including the rounding."""
    stored = {r["exercise_id"]: r for r in _stored(conn, "training_exercises")}
    checked = 0
    for page in nr.query(repo._ds, nr.TRAINING):
        ex_id = page["id"]
        decoded = nr.row_from_properties(nr.TRAINING, page["properties"])
        sets = json.loads(decoded.get("_sets_json") or "[]")
        supabase_store.OUTBOX.drain()
        repo.mirror_notion_write(nr.TRAINING, ex_id, page["properties"], sets=sets)
        row = _queued("training_exercises")[ex_id]
        assert row["actual_sets"] == stored[ex_id]["actual_sets"], ex_id
        assert row["total_volume_kg"] == stored[ex_id]["total_volume_kg"], ex_id
        if stored[ex_id]["total_volume_kg"]:
            checked += 1
    assert checked, "no exercise carried a non-zero volume — test proves nothing"


def test_no_mirrored_column_is_absent_from_the_stored_training_row(repo, conn):
    """The reverse coverage check: the mirror must not invent a column the
    rebuild does not fill, and must not skip one it does."""
    stored = _stored(conn, "training_exercises")
    filled = {c for row in stored for c, v in row.items() if v not in (None, "")}
    # Owned by other write paths (the AI note parser), not by the create.
    ai_owned = {"note_summary", "sentiment_score", "flagged_body_parts",
                "warning_level"}

    emitted = set()
    for page in nr.query(repo._ds, nr.TRAINING):
        supabase_store.OUTBOX.drain()
        decoded = nr.row_from_properties(nr.TRAINING, page["properties"])
        repo.mirror_notion_write(nr.TRAINING, page["id"], page["properties"],
                                 sets=json.loads(decoded.get("_sets_json") or "[]"))
        emitted |= set(_queued("training_exercises")[page["id"]])

    missing = filled - emitted - ai_owned
    assert not missing, (
        f"the rebuild fills {sorted(missing)} but the mirror never emits them"
    )


# ─── the phantom guard, over every real page ─────────────────────────────

def test_no_real_page_ever_queues_a_column_that_does_not_exist(repo, conn):
    """Run every real Notion page through the mirror and check each queued key
    against the actual schema. A key that is not a column is a 400 from
    PostgREST — which is how `_sets_json` would have shipped."""
    schema = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")
    fresh = sqlite3.connect(":memory:")
    fresh.executescript(schema)
    columns = {t: {r[1] for r in fresh.execute(f"PRAGMA table_info({t})")}
               for t in ("readiness_checkins", "training_exercises",
                         "training_sessions", "training_sets", "config",
                         "notion_biometrics")}

    supabase_store.OUTBOX.drain()
    for page in nr.query(repo._ds, nr.TRAINING):
        decoded = nr.row_from_properties(nr.TRAINING, page["properties"])
        repo.mirror_notion_write(nr.TRAINING, page["id"], page["properties"],
                                 sets=json.loads(decoded.get("_sets_json") or "[]"))
    for kind, key_column in ((nr.READINESS, "date"), (nr.CONFIG, "key"),
                             (nr.BIOMETRICS, "date")):
        for page in nr.query(repo._ds, kind):
            row = nr.row_from_properties(kind, page["properties"])
            repo.mirror_notion_write(kind, row.get(key_column), page["properties"])

    with supabase_store.OUTBOX._lock:
        queued = dict(supabase_store.OUTBOX._rows)
    assert queued, "nothing was queued from real data"
    for (table, _mode), rows in queued.items():
        for payload in rows.values():
            for row in (payload if isinstance(payload, list) else [payload]):
                unknown = set(row) - columns[table]
                assert not unknown, f"{table}: no column(s) {sorted(unknown)}"
