"""
Serving Notion reads from the datastore.

services/clients/notion_reader.py is the Notion half of offline mode — the
sibling of clients/datastore_reader.py, which has done this for Google Sheets
since 2026-08-01. Both are duck-typed rather than abstracted: that one wears
enough of a gspread Worksheet to be read through unchanged, this one wears
enough of notion.query_database.

THE ROUND TRIP IS THE REAL TEST, and it is at the bottom of this file: take
the live datastore.db, read it back through the whole Repository stack
offline, and require the result to equal the rows the datastore itself holds.
Those rows were produced by the same getter running against live Notion, so
an exact match means the reconstruction is faithful on real data — which the
unit tests below, working from rows this file invented, cannot establish.

The mapping tests exist because PROPERTIES is a hand-written inverse of the
Repository getters that populate the datastore. Nothing stops the two from
drifting except a test that walks both.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from services.clients import notion_reader as nr
from services.clients.notion import get_property

ROOT = Path(__file__).resolve().parent.parent
LIVE_DATASTORE = ROOT / "datastore.db"


# ─── a small datastore to read through ───────────────────────────────────

@pytest.fixture
def conn():
    """Three check-ins and two exercises, built straight from the real
    schema so a column rename breaks these tests rather than sliding past."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    schema = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")
    c.executescript(schema)
    c.executemany(
        "INSERT INTO readiness_checkins (date, current_condition, tightness_score, "
        "pain_score, anatomical_locations, sensation_tags, subjective_tightness, "
        "travel_flag, parsed, warning_level) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("2026-08-01", "Good", 3.0, 0.0, '["lumbar"]', '["tight"]', "ok", 1, 1, "monitor"),
            ("2026-08-02", "Poor", 6.0, 2.0, '["lumbar","hip"]', "[]", "", 0, 0, None),
            ("2026-08-03", None, 4.0, 1.0, "[]", "[]", "sore left", 0, 0, "flag"),
        ],
    )
    c.execute(
        "INSERT INTO training_sessions (session_id, session_date, "
        "session_duration_minutes, session_rpe, session_au) VALUES (?,?,?,?,?)",
        ("2026-08-02-aaa", "2026-08-02", 61.0, 5.0, 305.0),
    )
    c.executemany(
        "INSERT INTO training_exercises (exercise_id, session_id, session_date, "
        "movement_name, movement_type, exercise_rpe, notes, warning_level) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [
            ("ex-1", "2026-08-02-aaa", "2026-08-02", "Goblet Squat", "Squat", 6.0, "felt good", None),
            ("ex-2", "2026-08-02-aaa", "2026-08-02", "Face Pull", "Pull", 5.0, "", "flag"),
        ],
    )
    c.executemany(
        "INSERT INTO training_sets (exercise_id, set_num, reps, weight, rest, tut, "
        "velocity, band_tier, ts) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("ex-1", 1, 10.0, 20.0, 90.0, 0.0, "controlled", None, "2026-08-02T09:00:00"),
            ("ex-1", 2, 9.0, 20.0, 90.0, 0.0, "controlled", None, "2026-08-02T09:03:00"),
            ("ex-2", 1, 12.0, 0.0, 60.0, 0.0, "controlled", "orange", None),
        ],
    )
    c.execute("INSERT INTO config (key, value, updated) VALUES (?,?,?)",
              ("current_stage", "2", "2026-07-20"))
    c.commit()
    return c


# ─── every property kind survives the trip ───────────────────────────────

def test_each_property_kind_reads_back_through_get_property(conn):
    """The whole design rests on this: the SAME notion.get_property decodes
    live and offline pages, so a page that get_property cannot read is
    worthless however well-formed it looks."""
    page = nr.query(conn, nr.READINESS, filter_={"property": "Date", "date": {"equals": "2026-08-01"}})[0]
    assert get_property(page, "Date", "date") == "2026-08-01"
    assert get_property(page, "Condition", "select") == "Good"
    assert get_property(page, "Tightness", "number") == 3.0
    assert get_property(page, "Body Areas", "multi_select") == ["lumbar"]
    assert get_property(page, "Note", "rich_text") == "ok"
    assert get_property(page, "Travel", "checkbox") is True
    assert get_property(page, "Entry", "title") == "2026-08-01 Morning Check-In"


def test_a_false_checkbox_reads_as_False_not_None(conn):
    """The gap that would hide for months: a MISSING property returns None
    from get_property, while a live page with an unticked box returns False.
    `if not x` treats them alike; `x is False` and `x is None` do not, and
    neither does anything that counts them."""
    page = nr.query(conn, nr.READINESS, filter_={"property": "Date", "date": {"equals": "2026-08-02"}})[0]
    assert get_property(page, "Travel", "checkbox") is False
    assert get_property(page, "Electrolytes Taken", "checkbox") is False


def test_an_absent_select_is_None_and_an_absent_number_is_None(conn):
    page = nr.query(conn, nr.READINESS, filter_={"property": "Date", "date": {"equals": "2026-08-03"}})[0]
    assert get_property(page, "Condition", "select") is None
    assert get_property(page, "Alcohol Units", "number") is None


def test_every_mapped_property_is_present_on_every_page(conn):
    """A page must carry the full property set, not just the columns that
    happened to be non-NULL — see the checkbox test above for the cost."""
    for kind in (nr.READINESS, nr.TRAINING, nr.CONFIG):
        for page in nr.query(conn, kind):
            assert set(page["properties"]) == set(nr.PROPERTIES[kind])


# ─── the Sets JSON, reassembled ──────────────────────────────────────────

def test_sets_json_is_rebuilt_from_the_normalized_table(conn):
    page = [p for p in nr.query(conn, nr.TRAINING)
            if get_property(p, "Movement", "title") == "Goblet Squat"][0]
    sets = json.loads(get_property(page, "Sets", "rich_text"))
    assert [s["set_num"] for s in sets] == [1, 2]
    assert [s["reps"] for s in sets] == [10, 9]
    assert sets[0]["ts"] == "2026-08-02T09:00:00"


def test_counts_come_back_as_ints_not_floats(conn):
    """SQLite has no int/float distinction to preserve, so reps returns 10.0
    unless it is restored. A stepper seeded from last session would read
    "10.0"."""
    page = [p for p in nr.query(conn, nr.TRAINING)
            if get_property(p, "Movement", "title") == "Goblet Squat"][0]
    s = json.loads(get_property(page, "Sets", "rich_text"))[0]
    for field in ("set_num", "reps", "rest", "tut"):
        assert isinstance(s[field], int), f"{field} came back {type(s[field])}"


def test_weight_stays_a_float(conn):
    """Deliberately NOT restored to int: services.sessions.make_sets_data
    emits `ex.get("weight_kg") or 0.0`, so a float is the faithful value
    rather than a round-trip artefact."""
    page = [p for p in nr.query(conn, nr.TRAINING)
            if get_property(p, "Movement", "title") == "Goblet Squat"][0]
    s = json.loads(get_property(page, "Sets", "rich_text"))[0]
    assert isinstance(s["weight"], float)


def test_absent_optional_set_keys_are_omitted_not_nulled(conn):
    """Both writers omit band_tier/ts entirely when absent. Emitting them as
    null would round-trip a different JSON document than the one stored."""
    squat = [p for p in nr.query(conn, nr.TRAINING)
             if get_property(p, "Movement", "title") == "Goblet Squat"][0]
    assert "band_tier" not in json.loads(get_property(squat, "Sets", "rich_text"))[0]
    pull = [p for p in nr.query(conn, nr.TRAINING)
            if get_property(p, "Movement", "title") == "Face Pull"][0]
    pull_set = json.loads(get_property(pull, "Sets", "rich_text"))[0]
    assert pull_set["band_tier"] == "orange"
    assert "ts" not in pull_set


def test_session_fields_are_joined_onto_every_exercise(conn):
    """Notion denormalises the session onto each exercise row; the datastore
    normalises it out. Callers still read it per page."""
    for page in nr.query(conn, nr.TRAINING):
        assert get_property(page, "Session AU", "number") == 305.0
        assert get_property(page, "Session Duration", "number") == 61.0


def test_the_training_page_id_is_the_real_notion_id(conn):
    """It is training_exercises' primary key, and get_all_training_exercises_raw
    returns it as exercise_id."""
    assert {p["id"] for p in nr.query(conn, nr.TRAINING)} == {"ex-1", "ex-2"}


def test_synthesized_ids_are_not_valid_notion_ids(conn):
    """A readiness row is keyed by date, so there is no page id to return.
    The sentinel must be something Notion rejects, so a write that reached it
    fails loudly rather than updating an arbitrary page."""
    for page in nr.query(conn, nr.READINESS):
        assert page["id"].startswith(nr.ID_PREFIX)


# ─── filtering ───────────────────────────────────────────────────────────

def test_date_equals(conn):
    got = nr.query(conn, nr.READINESS, filter_={"property": "Date", "date": {"equals": "2026-08-02"}})
    assert [get_property(p, "Date", "date") for p in got] == ["2026-08-02"]


def test_date_on_or_after_is_inclusive(conn):
    got = nr.query(conn, nr.READINESS, filter_={"property": "Date", "date": {"on_or_after": "2026-08-02"}})
    assert sorted(get_property(p, "Date", "date") for p in got) == ["2026-08-02", "2026-08-03"]


def test_date_on_or_before_is_inclusive(conn):
    got = nr.query(conn, nr.READINESS, filter_={"property": "Date", "date": {"on_or_before": "2026-08-02"}})
    assert sorted(get_property(p, "Date", "date") for p in got) == ["2026-08-01", "2026-08-02"]


def test_checkbox_equals_false_matches_the_unticked_rows(conn):
    got = nr.query(conn, nr.READINESS, filter_={"property": "Parsed", "checkbox": {"equals": False}})
    assert sorted(get_property(p, "Date", "date") for p in got) == ["2026-08-02", "2026-08-03"]


def test_rich_text_is_not_empty_and_is_empty_are_complementary(conn):
    full = nr.query(conn, nr.READINESS, filter_={"property": "Note", "rich_text": {"is_not_empty": True}})
    empty = nr.query(conn, nr.READINESS, filter_={"property": "Note", "rich_text": {"is_empty": True}})
    assert sorted(get_property(p, "Date", "date") for p in full) == ["2026-08-01", "2026-08-03"]
    assert [get_property(p, "Date", "date") for p in empty] == ["2026-08-02"]


def test_title_equals_selects_one_movement(conn):
    got = nr.query(conn, nr.TRAINING, filter_={"property": "Movement", "title": {"equals": "Face Pull"}})
    assert [p["id"] for p in got] == ["ex-2"]


def test_and_narrows_while_or_widens(conn):
    both = nr.query(conn, nr.READINESS, filter_={"and": [
        {"property": "Date", "date": {"on_or_after": "2026-08-02"}},
        {"property": "Warning", "select": {"equals": "flag"}},
    ]})
    assert [get_property(p, "Date", "date") for p in both] == ["2026-08-03"]
    either = nr.query(conn, nr.READINESS, filter_={"or": [
        {"property": "Warning", "select": {"equals": "flag"}},
        {"property": "Warning", "select": {"equals": "monitor"}},
    ]})
    assert sorted(get_property(p, "Date", "date") for p in either) == ["2026-08-01", "2026-08-03"]


def test_a_row_with_no_date_never_satisfies_a_range_filter(conn):
    """Notion excludes an empty date from a range rather than sorting it to
    one end. Returning it would silently widen every windowed getter."""
    conn.execute("INSERT INTO readiness_checkins (date, tightness_score) VALUES ('', 9)")
    got = nr.query(conn, nr.READINESS, filter_={"property": "Date", "date": {"on_or_after": "1900-01-01"}})
    assert all(get_property(p, "Date", "date") for p in got)


# ─── refusals ────────────────────────────────────────────────────────────

def test_an_unimplemented_operator_raises_rather_than_matching_everything(conn):
    """The whole point of the refusal: a silently-ignored filter returns
    every row, which reads as a successful query over a wider window and is
    indistinguishable from correct output until a decision is made on it."""
    with pytest.raises(nr.NotionQueryUnsupportedError, match="contains"):
        nr.query(conn, nr.READINESS,
                 filter_={"property": "Note", "rich_text": {"contains": "sore"}})


def test_filtering_on_an_unmapped_property_raises(conn):
    with pytest.raises(nr.NotionQueryUnsupportedError):
        nr.query(conn, nr.READINESS, filter_={"property": "Nonexistent", "number": {"equals": 1}})


def test_filtering_a_property_by_the_wrong_kind_raises(conn):
    """`{"property": "Tightness", "date": ...}` is a caller bug; matching
    nothing would look like a legitimately empty result."""
    with pytest.raises(nr.NotionQueryUnsupportedError):
        nr.query(conn, nr.READINESS, filter_={"property": "Tightness", "date": {"equals": "x"}})


def test_sorting_by_an_unmapped_property_raises(conn):
    with pytest.raises(nr.NotionQueryUnsupportedError):
        nr.query(conn, nr.TRAINING, sorts=[{"property": "Nonexistent", "direction": "ascending"}])


def test_an_unknown_database_raises(conn):
    with pytest.raises(nr.NotionQueryUnsupportedError):
        nr.query(conn, "sleep")


# ─── sorting ─────────────────────────────────────────────────────────────

def test_descending_and_ascending_sorts(conn):
    desc = nr.query(conn, nr.READINESS, sorts=[{"property": "Date", "direction": "descending"}])
    assert [get_property(p, "Date", "date") for p in desc] == ["2026-08-03", "2026-08-02", "2026-08-01"]
    asc = nr.query(conn, nr.READINESS, sorts=[{"property": "Date", "direction": "ascending"}])
    assert [get_property(p, "Date", "date") for p in asc] == ["2026-08-01", "2026-08-02", "2026-08-03"]


def test_a_missing_table_reads_as_no_rows(conn):
    """Same tolerance OfflineWorksheet has: a datastore built before a table
    existed reads as "nothing logged yet", which is what an empty Notion
    database returns."""
    conn.execute("DROP TABLE config")
    assert nr.query(conn, nr.CONFIG) == []


# ─── the mapping cannot drift from what Repository reads ─────────────────

def _properties_read_by_repository() -> set[tuple[str, str]]:
    """Every (property name, kind) pair repository.py decodes, scraped from
    its own source. Scraping beats a hand-listed set for the usual reason: a
    list goes stale silently, and the failure is a property that reads None
    forever."""
    import re
    src = (ROOT / "services" / "repository.py").read_text(encoding="utf-8")
    return set(re.findall(r'get_property\(\s*\w+,\s*"([^"]+)",\s*"(\w+)"\s*\)', src))


def test_every_property_repository_reads_is_mapped_to_a_column():
    """The drift guard. A getter that starts reading a new Notion property
    would return None for it offline — data that is simply absent, with no
    error anywhere."""
    mapped = {(name, kind)
              for props in nr.PROPERTIES.values()
              for name, (_col, kind) in props.items()}
    missing = _properties_read_by_repository() - mapped
    assert not missing, (
        f"repository.py reads these Notion properties but notion_reader has "
        f"no column for them, so they read as None offline: {sorted(missing)}"
    )


def test_every_mapped_column_exists_in_the_schema():
    """The other direction — a column renamed in datastore_schema.sql must
    break the map rather than quietly return None."""
    schema = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")
    c = sqlite3.connect(":memory:")
    c.executescript(schema)
    joined = {  # supplied by the join / rebuilt, not columns of the base table
        nr.TRAINING: {"session_duration_minutes", "session_rpe", "session_au", "_sets_json"},
    }
    for kind, props in nr.PROPERTIES.items():
        cols = {r[1] for r in c.execute(f"PRAGMA table_info({nr.TABLES[kind]})")}
        cols |= joined.get(kind, set())
        for name, (column, _k) in props.items():
            if column is not None:
                assert column in cols, f"{kind}.{name} -> {column!r} is not a column"


def test_a_property_with_no_column_has_a_synthesizer():
    for kind, props in nr.PROPERTIES.items():
        for name, (column, _k) in props.items():
            if column is None:
                nr._synthesize(kind, name, {"date": "2026-08-01"})  # must not raise


# ─── the round trip that actually proves it, on real data ────────────────

def _offline_repo():
    from services.config import Config
    from services.repository import Repository
    return Repository(Config(
        notion_api_key="unused", notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_config="db-config", google_sheets_id="unused",
        google_service_account={}, datastore_path=str(LIVE_DATASTORE),
    ))


@pytest.mark.skipif(not LIVE_DATASTORE.exists(), reason="no datastore.db in this checkout")
def test_readiness_round_trips_the_real_snapshot_exactly():
    """get_all_readiness_checkins_raw is what WROTE readiness_checkins, from
    live Notion. Running it offline must return those same rows — value for
    value, not merely the right count. Anything less means the
    reconstruction is lossy on data this file did not invent."""
    repo = _offline_repo()
    got = {r["date"]: r for r in repo.get_all_readiness_checkins_raw()}
    conn = sqlite3.connect(LIVE_DATASTORE)
    conn.row_factory = sqlite3.Row
    stored = {r["date"]: dict(r) for r in conn.execute("SELECT * FROM readiness_checkins")}
    assert set(got) == set(stored)
    for d, row in stored.items():
        for column, want in row.items():
            have = got[d][column]
            if want is None and (have is None or have in ("", 0, "[]")):
                continue  # NULL was a blank/absent Notion property either way
            assert have == want, f"{d}.{column}: offline {have!r} != stored {want!r}"


@pytest.mark.skipif(not LIVE_DATASTORE.exists(), reason="no datastore.db in this checkout")
def test_training_round_trips_the_real_snapshot_including_every_set():
    """The hardest reconstruction: training_sets normalized back into the
    Sets JSON, and the session fields re-joined."""
    repo = _offline_repo()
    got = {r["exercise_id"]: r for r in repo.get_all_training_exercises_raw()}
    conn = sqlite3.connect(LIVE_DATASTORE)
    conn.row_factory = sqlite3.Row
    stored = {r["exercise_id"]: dict(r) for r in conn.execute(
        "SELECT e.*, s.session_duration_minutes, s.session_rpe, s.session_au "
        "FROM training_exercises e LEFT JOIN training_sessions s "
        "ON s.session_id = e.session_id")}
    assert set(got) == set(stored)
    for ex_id, row in stored.items():
        assert got[ex_id]["movement_name"] == row["movement_name"]
        assert got[ex_id]["session_date"] == row["session_date"]
        assert got[ex_id]["session_au"] == row["session_au"]
        # actual_sets/total_volume_kg are DERIVED from the reassembled JSON,
        # so matching them is a check on the sets themselves.
        assert got[ex_id]["actual_sets"] == row["actual_sets"]
        assert got[ex_id]["total_volume_kg"] == row["total_volume_kg"]


@pytest.mark.skipif(not LIVE_DATASTORE.exists(), reason="no datastore.db in this checkout")
def test_config_round_trips_and_the_stage_reads_back():
    repo = _offline_repo()
    conn = sqlite3.connect(LIVE_DATASTORE)
    stored = dict(conn.execute("SELECT key, value FROM config").fetchall())
    for key, value in stored.items():
        assert repo.get_config_value(key) == value
    if "current_stage" in stored:
        assert repo.get_current_stage() == int(stored["current_stage"])


@pytest.mark.skipif(not LIVE_DATASTORE.exists(), reason="no datastore.db in this checkout")
def test_windowed_getters_return_a_subset_of_the_unwindowed_one():
    """The filter runs over synthesized pages; this checks it against the
    real date distribution rather than three invented rows."""
    repo = _offline_repo()
    every = {r["date"] for r in repo.get_all_readiness_checkins_raw()}
    recent = {r["date"] for r in repo.get_recent_readiness(days=14, today=date(2026, 8, 10))}
    assert recent <= every
    assert all(d >= "2026-07-27" for d in recent)


# ─── offline is read-only for Notion too ─────────────────────────────────

def test_a_notion_write_raises_offline():
    """datastore_reader.py's docstring names the failure this closes:
    "Reading local while writing live would be worse still." Every read now
    goes through _query, so anything still reaching _nc is a write."""
    from services.clients.datastore_reader import DatastoreReadOnlyError
    repo = _offline_repo()
    with pytest.raises(DatastoreReadOnlyError, match="Notion write"):
        _ = repo._nc


def test_an_unconfigured_database_id_raises_rather_than_guessing():
    """Serving one database's rows for another's query would make every
    property read None — an empty screen, not an error."""
    repo = _offline_repo()
    assert repo._db_kind("db-training") == nr.TRAINING
    with pytest.raises(KeyError):
        repo._db_kind("some-other-database")


# ─── page -> row: the inverse, used by the Supabase mirror ───────────────

def test_a_real_row_survives_row_to_page_to_row():
    """PROPERTIES is used in BOTH directions, so the strongest check is that
    they compose to the identity on data this file did not invent."""
    import sqlite3
    if not LIVE_DATASTORE.exists():
        pytest.skip("no datastore.db in this checkout")
    conn = sqlite3.connect(LIVE_DATASTORE)
    conn.row_factory = sqlite3.Row
    stored = [dict(r) for r in conn.execute("SELECT * FROM readiness_checkins")]
    assert stored, "no rows to check"
    for row in stored:
        page = nr.page_from_row(nr.READINESS, row)
        back = nr.row_from_properties(nr.READINESS, page["properties"])
        for column, want in row.items():
            if column not in back:
                continue
            have = back[column]
            # A blank decodes to "" and the datastore stores NULL; the mirror
            # normalizes with supabase_store.blank_to_null, so compare the way
            # the mirror will actually send it. Stepping around this instead
            # is what let the ''-vs-NULL defect through the first time.
            if have == "":
                have = None
            if want is None and have in (None, 0, "[]"):
                continue
            assert have == want, f"{row['date']}.{column}: {have!r} != {want!r}"


def test_the_BUILDER_shape_decodes_too_not_just_the_response_shape():
    """THE trap. services/clients/notion.py's builders emit
    {"text": {"content": ...}}; get_property reads {"plain_text": ...}. A
    decoder written against the wrong one returns "" for every title and note
    — silently, since "" is a legitimate value."""
    from services.clients import notion
    props = {
        "Movement": notion.title("Goblet Squat"),
        "Notes": notion.rich_text("felt good"),
        "Session Date": notion.date_prop("2026-08-10"),
        "Type": notion.select("Squat"),
        "Exercise RPE": notion.number(6),
    }
    row = nr.row_from_properties(nr.TRAINING, props)
    assert row["movement_name"] == "Goblet Squat", "builder title decoded empty"
    assert row["notes"] == "felt good", "builder rich_text decoded empty"
    assert row["session_date"] == "2026-08-10"
    assert row["movement_type"] == "Squat"
    assert row["exercise_rpe"] == 6.0


def test_a_chunked_rich_text_rejoins():
    """notion.rich_text splits a value over 2000 chars into up to 100
    elements. Taking element [0] would truncate the phases JSON blob and any
    long note to exactly 2000 characters."""
    from services.clients import notion
    long_value = "x" * 4500
    row = nr.row_from_properties(nr.CONFIG, {"Value": notion.rich_text(long_value)})
    assert row["value"] == long_value
    assert len(row["value"]) == 4500


def test_multi_select_is_stored_as_a_json_array_string():
    """Not as a list. get_all_readiness_checkins_raw does json.dumps, so a
    list here would compare unequal to every row the other path builds."""
    from services.clients import notion
    row = nr.row_from_properties(
        nr.READINESS, {"Body Areas": notion.multi_select(["lumbar", "hip"])})
    assert row["anatomical_locations"] == '["lumbar", "hip"]'


def test_a_checkbox_is_stored_as_one_or_zero_not_a_bool():
    from services.clients import notion
    assert nr.row_from_properties(
        nr.READINESS, {"Travel": notion.checkbox(True)})["travel_flag"] == 1
    assert nr.row_from_properties(
        nr.READINESS, {"Travel": notion.checkbox(False)})["travel_flag"] == 0


def test_an_update_decodes_to_ONLY_the_columns_it_wrote():
    """A Notion update_page sends only what it changes, and the mirror upserts
    only those columns. Inventing defaults for the rest would blank real data
    on every partial update."""
    from services.clients import notion
    row = nr.row_from_properties(nr.READINESS, {
        "Parsed Severity": notion.number(3),
        "Parsed": notion.checkbox(True),
    })
    assert set(row) == {"parsed_severity", "parsed"}


def test_an_unmapped_property_is_skipped_rather_than_raising():
    """A Notion database may carry columns this app does not mirror, and a
    write is not the place to discover that."""
    assert nr.row_from_properties(
        nr.READINESS, {"Some Manual Column": {"number": 1}}) == {}


def test_a_synthesized_title_has_nothing_to_store():
    from services.clients import notion
    assert nr.row_from_properties(
        nr.READINESS, {"Entry": notion.title("2026-08-10 Morning Check-In")}) == {}


def test_an_empty_select_and_date_decode_to_none():
    from services.clients import notion
    row = nr.row_from_properties(nr.READINESS, {
        "Condition": notion.select(""), "Date": notion.date_prop(None)})
    assert row["current_condition"] is None
    assert row["date"] is None
