"""
Mirroring the NOTION writes — the half the Sheets pattern does not cover.

A sheet row is one row of one table, so the Sheets mirror is a zip of a header
onto values. A Notion page is not: ONE training page carries a flat,
denormalised session and its whole set list, and services/datastore.py
normalises that into training_sessions -> training_exercises -> training_sets.
The mirror has to perform the same split, or it posts session columns and a
`_sets_json` key that is not a column at all.

Four structural facts drive everything here, each established by reading the
code rather than assumed:

  * The page id IS training_exercises.exercise_id, so save_session_notes and
    update_session_note_ai already hold their primary key.
  * readiness_checkins is keyed by DATE while update_readiness_ai is handed a
    page id, and no page-id-to-date index exists — the caller has to pass it.
  * actual_sets and total_volume_kg have NO Notion property; they are derived
    on read and must be recomputed on write.
  * training_sets' primary key is a surrogate the writer never supplies, so
    upsert cannot express it and delete-then-insert is the faithful operation.

Pure tests — the store is a fake, nothing touches the network.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services import supabase_store
from services.clients import notion
from services.clients import notion_reader as nr
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


def _repo(store=None) -> Repository:
    repo = Repository(Config(
        notion_api_key="k", notion_db_readiness="a", notion_db_training="b", notion_db_config="d", google_sheets_id="e",
        google_service_account={},
        supabase_url="https://x.supabase.co", supabase_secret_key="secret",
    ))
    if store is not None:
        repo._supabase_store_obj = store
    return repo


def _rows(table, mode=supabase_store.UPSERT):
    with supabase_store.OUTBOX._lock:
        return dict(supabase_store.OUTBOX._rows.get((table, mode), {}))


def _training_properties():
    return {
        "Movement": notion.title("Goblet Squat"),
        "Session Date": notion.date_prop("2026-08-10"),
        "Session ID": notion.rich_text("2026-08-10-abc"),
        "Type": notion.select("Squat"),
        "Planned Sets": notion.number(3),
        "Planned Reps": notion.number(10),
        "Exercise RPE": notion.number(6),
        "Sets": notion.rich_text("[]"),
        "Notes": notion.rich_text(""),
        "Session Duration": notion.number(61),
        "Session RPE": notion.number(5),
        "Session AU": notion.number(305),
    }


SETS = [
    {"set_num": 1, "reps": 10, "weight": 20.0, "rest": 90, "tut": 0,
     "velocity": "controlled", "ts": "2026-08-10T09:00:00"},
    {"set_num": 2, "reps": 9, "weight": 20.0, "rest": 90, "tut": 0,
     "velocity": "controlled", "ts": "2026-08-10T09:03:00"},
]


class RecordingStore:
    def __init__(self):
        self.upserts, self.patches, self.deletes, self.inserts = [], [], [], []

    def upsert(self, table, rows):
        self.upserts.append((table, rows))
        return len(rows)

    def patch(self, table, pk_column, pk_value, row):
        self.patches.append((table, pk_column, str(pk_value), row))
        return 1

    def delete_where(self, table, column, value):
        self.deletes.append((table, column, str(value)))

    def insert(self, table, rows):
        self.inserts.append((table, rows))
        return len(rows)


# ─── the fan-out ─────────────────────────────────────────────────────────

def test_one_training_page_fans_out_to_three_tables():
    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    assert set(_rows("training_sessions")) == {"2026-08-10-abc"}
    assert set(_rows("training_exercises")) == {"ex-1"}
    assert set(_rows("training_sets", supabase_store.REPLACE)) == {"ex-1"}


def test_session_columns_do_not_reach_the_exercises_table():
    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    exercise = _rows("training_exercises")["ex-1"]
    for column in ("session_duration_minutes", "session_rpe", "session_au"):
        assert column not in exercise, f"{column} belongs to training_sessions"
    session = _rows("training_sessions")["2026-08-10-abc"]
    assert session["session_au"] == 305.0
    assert session["session_date"] == "2026-08-10"


def test_the_sets_json_phantom_never_reaches_a_table():
    """PROPERTIES maps "Sets" to `_sets_json`, which is not a column of any
    table — it is the marker for normalisation into training_sets. Posting it
    is a 400 from PostgREST."""
    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    assert "_sets_json" not in _rows("training_exercises")["ex-1"]


def test_derived_columns_are_recomputed():
    """actual_sets and total_volume_kg have no Notion property — they are
    derived on read. Omitting them leaves NULL where a rebuild holds real
    numbers."""
    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    exercise = _rows("training_exercises")["ex-1"]
    assert exercise["actual_sets"] == 2
    assert exercise["total_volume_kg"] == 380.0          # 10*20 + 9*20


def test_the_derived_volume_matches_the_getter_it_mirrors():
    """Same expression as get_all_training_exercises_raw, so the mirror and a
    rebuild cannot disagree."""
    expected = round(
        sum((s.get("reps") or 0) * (s.get("weight") or 0.0) for s in SETS), 1)
    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    assert _rows("training_exercises")["ex-1"]["total_volume_kg"] == expected


# ─── training_sets is replaced, never upserted ───────────────────────────

def test_sets_are_deleted_then_inserted():
    """Its key is a surrogate the writer never supplies, so merge-duplicates
    has nothing to conflict on and an insert-only mirror would duplicate every
    set on every re-log. A Notion write always carries the COMPLETE set list,
    which is what makes replacement faithful rather than a workaround."""
    store = RecordingStore()
    repo = _repo(store=store)
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    repo.flush_supabase_mirror()

    assert ("training_sets", "exercise_id", "ex-1") in store.deletes
    inserted = [rows for table, rows in store.inserts if table == "training_sets"]
    assert len(inserted) == 1 and len(inserted[0]) == 2
    assert all(table != "training_sets" for table, _ in store.upserts)


def test_an_exercise_with_no_sets_still_deletes_the_old_ones():
    """An empty list is meaningful — this exercise now has no sets. Skipping
    the delete would leave the previous log's sets attached forever."""
    store = RecordingStore()
    repo = _repo(store=store)
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=[])
    repo.flush_supabase_mirror()

    assert ("training_sets", "exercise_id", "ex-1") in store.deletes
    assert [r for t, r in store.inserts if t == "training_sets"] == []


def test_the_delete_is_scoped_to_one_exercise_not_the_table():
    """A wrong filter here removes one exercise's sets; truncate would remove
    the training history."""
    store = RecordingStore()
    repo = _repo(store=store)
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    repo.flush_supabase_mirror()
    assert store.deletes == [("training_sets", "exercise_id", "ex-1")]


# ─── partial writes ──────────────────────────────────────────────────────

def test_a_partial_training_update_touches_only_the_exercises_table():
    """save_session_notes writes ONE property. It must not create a session
    row, invent derived columns, or wipe the sets."""
    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1",
                             {"Notes": notion.rich_text("felt good")},
                             mode=supabase_store.PATCH)
    assert _rows("training_sessions") == {}
    assert _rows("training_sets", supabase_store.REPLACE) == {}
    assert _rows("training_exercises", supabase_store.PATCH)["ex-1"] == {
        "notes": "felt good"}


def test_the_ai_note_update_patches_four_columns():
    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1", {
        "Note Summary": notion.rich_text("ok"),
        "Sentiment": notion.number(0.5),
        "Flagged Areas": notion.rich_text('["lumbar"]'),
        "Warning": notion.select("monitor"),
    }, mode=supabase_store.PATCH)
    patched = _rows("training_exercises", supabase_store.PATCH)["ex-1"]
    assert set(patched) == {"note_summary", "sentiment_score",
                            "flagged_body_parts", "warning_level"}


def test_readiness_ai_needs_its_date_and_is_skipped_without_one():
    """readiness_checkins is keyed by DATE, not page id. Rather than guess,
    the mirror is skipped — the Notion write still happens and the full push
    repairs Postgres."""
    repo = _repo(store=RecordingStore())
    import inspect
    sig = inspect.signature(repo.update_readiness_ai)
    assert "entry_date" in sig.parameters
    assert sig.parameters["entry_date"].default is None, (
        "entry_date must be optional so no existing caller breaks"
    )


def test_the_caller_passes_the_date_through():
    """views/insights.py has it for free: get_unparsed_readiness returns it as
    `timestamp`, read by the same get_property call that populates `date`."""
    src = (ROOT / "views" / "insights.py").read_text(encoding="utf-8")
    call = src.split("update_readiness_ai(")[1].split("\n                    except")[0]
    assert "entry_date" in call, "the date is not threaded through to the mirror"
    assert 'entry.get("timestamp")' in call


# ─── nothing is posted that is not a column ──────────────────────────────

def test_every_mirrored_column_is_a_real_column_of_its_table():
    """THE structural guard: a key that is not a column is a 400, and it is
    exactly how `_sets_json` would have shipped."""
    schema = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")
    db = sqlite3.connect(":memory:")
    db.executescript(schema)

    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-1", _training_properties(), sets=SETS)
    repo.mirror_notion_write(nr.READINESS, "2026-08-10", {
        "Date": notion.date_prop("2026-08-10"),
        "Tightness": notion.number(3),
        "Body Areas": notion.multi_select(["lumbar"]),
        "Travel": notion.checkbox(True),
        "Entry": notion.title("2026-08-10 Morning Check-In"),
    })
    repo.mirror_notion_write(nr.CONFIG, "current_stage", {
        "Key": notion.title("current_stage"),
        "Value": notion.rich_text("2"),
        "Updated": notion.date_prop("2026-07-20"),
    })
    with supabase_store.OUTBOX._lock:
        queued = dict(supabase_store.OUTBOX._rows)
    assert queued, "nothing was queued"
    for (table, _mode), rows in queued.items():
        columns = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
        for payload in rows.values():
            for row in (payload if isinstance(payload, list) else [payload]):
                unknown = set(row) - columns
                assert not unknown, f"{table} has no column(s) {sorted(unknown)}"


def test_values_are_stored_the_way_a_rebuild_stores_them():
    """Mirroring the PROPERTIES rather than the record is what makes this
    true for free: a checkbox becomes 1/0 and a multi_select becomes a JSON
    array STRING, because row_from_properties applies the getters' own
    conventions. Mirroring the CheckInRecord would have sent Python bools
    into BIGINT columns and Python lists into TEXT ones."""
    repo = _repo()
    repo.mirror_notion_write(nr.READINESS, "2026-08-10", {
        "Date": notion.date_prop("2026-08-10"),
        "Travel": notion.checkbox(True),
        "Body Areas": notion.multi_select(["lumbar", "hip"]),
        "Tightness": notion.number(3),
    })
    row = _rows("readiness_checkins")["2026-08-10"]
    assert row["travel_flag"] == 1 and isinstance(row["travel_flag"], int)
    assert row["anatomical_locations"] == '["lumbar", "hip"]'
    assert row["tightness_score"] == 3.0


# ─── ordering at the write sites ─────────────────────────────────────────

def test_a_notion_write_is_mirrored_only_AFTER_the_notion_call():
    """A create_page that raised must not leave a row queued for Postgres
    that Notion does not hold. set_config is the sharp case: its write sits in
    a try/finally, and queueing in the finally would do exactly that."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def set_config")[1].split("\n    def ")[0]
    # rindex for the real `finally:` block — the explanatory comment above
    # it contains the word too, and indexing to the first hit tested prose.
    assert body.index("notion.create_page") < body.index("mirror_notion_write")
    assert body.index("mirror_notion_write") < body.rindex("\n        finally:")


def test_the_readiness_create_path_supplies_parsed_zero():
    """A brand-new page carries no "Parsed" property, and get_property reads
    an absent checkbox as None — which the datastore stores as 0. An INSERT
    omitting the column would leave NULL where a rebuild holds 0."""
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def save_check_in")[1].split("\n    # ─── One-off")[0]
    assert '"Parsed": notion.checkbox(False)' in body
    assert "supabase_store.PATCH" in body, (
        "the UPDATE branch must PATCH — it writes 19 of 24 columns and must "
        "not reset the AI-parser columns it does not own"
    )


def test_the_page_id_is_used_as_the_exercise_primary_key():
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    body = src.split("def save_training_exercise")[1].split("\n    def ")[0]
    assert 'mirror_notion_write(notion_reader.TRAINING, page["id"]' in body
    assert body.index("notion.create_page") < body.index("mirror_notion_write")


def test_the_volume_rounding_matches_the_getter_where_the_data_cannot_tell():
    """A discriminating case, because the real log cannot supply one.

    Every logged weight carries at most one decimal and every rep count is an
    integer, so on real data round(x, 1) and round(x, 2) are indistinguishable
    — a mutation of the rounding survives the convergence test for that reason
    alone. This pins the mirror to get_all_training_exercises_raw's exact
    expression using values that separate them.
    """
    awkward = [{"set_num": 1, "reps": 3, "weight": 0.33, "rest": 0, "tut": 0,
                "velocity": "controlled"}]
    getter_result = round(
        sum((s.get("reps") or 0) * (s.get("weight") or 0.0) for s in awkward), 1)
    assert getter_result == 1.0                     # 0.99 -> 1.0 at one decimal

    repo = _repo()
    repo.mirror_notion_write(nr.TRAINING, "ex-round", _training_properties(),
                             sets=awkward)
    assert _rows("training_exercises")["ex-round"]["total_volume_kg"] == getter_result
