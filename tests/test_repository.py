"""
Tests for services/repository.py — the Notion property-name / Sheets
column-name mapping boundary. Fixtures below mirror real page/row shapes
already seen in db.py / sync_sheets.py (property types, field names), not
invented ones.
"""

import ast
import json

import pytest

from services import models
from services.repository import Repository
from services.config import Config


def _config() -> Config:
    return Config(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_biometrics="db-biometrics",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )


class _FakePages:
    def __init__(self):
        self.created = []
        self.updated = []
        self._retrieve_by_id = {}

    def create(self, parent, properties):
        page_id = f"page-{len(self.created) + 1}"
        self.created.append({"parent": parent, "properties": properties, "id": page_id})
        return {"id": page_id}

    def update(self, page_id, properties):
        self.updated.append({"page_id": page_id, "properties": properties})
        return {"id": page_id}

    def retrieve(self, page_id):
        return self._retrieve_by_id[page_id]


class _FakeDatabases:
    def __init__(self, pages_by_db: dict[str, list[dict]]):
        self._pages_by_db = pages_by_db
        self.queries = []
        self.update_calls = []
        self._properties_by_db: dict[str, dict] = {}

    def query(self, database_id, **kwargs):
        self.queries.append({"database_id": database_id, **kwargs})
        return {"results": self._pages_by_db.get(database_id, []), "has_more": False}

    def retrieve(self, database_id):
        return {"properties": self._properties_by_db.get(database_id, {})}

    def update(self, database_id, properties):
        self.update_calls.append({"database_id": database_id, "properties": properties})
        self._properties_by_db.setdefault(database_id, {}).update(properties)


class _FakeNotionClient:
    def __init__(self, pages_by_db: dict[str, list[dict]] | None = None):
        self.databases = _FakeDatabases(pages_by_db or {})
        self.pages = _FakePages()


def _title_prop(text):
    return {"title": [{"plain_text": text}]}


def _rich_text_prop(text):
    return {"rich_text": [{"plain_text": text}]}


def _number_prop(n):
    return {"number": n}


def _select_prop(name):
    return {"select": {"name": name} if name else None}


def _date_prop(d):
    return {"date": {"start": d} if d else None}


def _checkbox_prop(b):
    return {"checkbox": b}


def _repo(pages_by_db=None) -> Repository:
    repo = Repository(_config())
    repo._notion_client = _FakeNotionClient(pages_by_db)
    return repo


# ─── Phase round-trip ───────────────────────────────────────────────────────

def test_get_phases_empty_when_no_config_row():
    repo = _repo({"db-config": []})
    assert repo.get_phases() == []


def test_get_phases_parses_stored_json_into_dataclasses():
    stored = json.dumps([
        {"phase_number": 1, "name": "Stage 1 Rehab", "start_date": "2026-06-29",
         "length_days": 14, "status": "active"},
    ])
    page = {"id": "cfg-1", "properties": {
        "Key": _title_prop("phases"), "Value": _rich_text_prop(stored),
    }}
    repo = _repo({"db-config": [page]})
    phases = repo.get_phases()
    assert phases == [models.Phase(1, "Stage 1 Rehab", "2026-06-29", 14, "active")]


def test_get_phases_returns_empty_list_on_corrupt_json():
    page = {"id": "cfg-1", "properties": {
        "Key": _title_prop("phases"), "Value": _rich_text_prop("{not json"),
    }}
    repo = _repo({"db-config": [page]})
    assert repo.get_phases() == []


def test_set_phases_creates_new_config_row_when_absent():
    repo = _repo({"db-config": []})
    repo.set_phases([models.Phase(1, "Stage 1 Rehab", "2026-06-29", 14, "active")],
                     today=__import__("datetime").date(2026, 7, 7))
    assert len(repo._notion_client.pages.created) == 1
    props = repo._notion_client.pages.created[0]["properties"]
    stored = json.loads(props["Value"]["rich_text"][0]["text"]["content"])
    assert stored == [{"phase_number": 1, "name": "Stage 1 Rehab", "start_date": "2026-06-29",
                        "length_days": 14, "status": "active"}]


def test_set_phases_updates_existing_config_row():
    existing = {"id": "cfg-existing", "properties": {
        "Key": _title_prop("phases"), "Value": _rich_text_prop("[]"),
    }}
    repo = _repo({"db-config": [existing]})
    repo.set_phases([models.Phase(2, "Stage 2", "2026-07-20", 28, "upcoming")])
    assert len(repo._notion_client.pages.updated) == 1
    assert repo._notion_client.pages.updated[0]["page_id"] == "cfg-existing"


# ─── SessionRecord grouping ─────────────────────────────────────────────────

def _exercise_page(session_date, movement, session_rpe=6, session_duration=42, session_au=252):
    return {"properties": {
        "Session Date":     _date_prop(session_date),
        "Session Duration": _number_prop(session_duration),
        "Session RPE":      _number_prop(session_rpe),
        "Session AU":       _number_prop(session_au),
        "Movement":         _title_prop(movement),
        "Type":             _select_prop("Core Stability"),
        "Planned Sets":     _number_prop(3),
        "Planned Reps":     _number_prop(10),
        "Exercise RPE":     _number_prop(session_rpe),
        "Sets":             _rich_text_prop(json.dumps([{"reps": 10, "weight": 0.0}] * 3)),
    }}


def test_get_recent_sessions_groups_multiple_exercises_under_one_date():
    pages = [
        _exercise_page("2026-07-07", "Bird-Dog"),
        _exercise_page("2026-07-07", "Glute Bridge"),
    ]
    repo = _repo({"db-training": pages})
    sessions = repo.get_recent_sessions(days=7, today=__import__("datetime").date(2026, 7, 7))
    assert len(sessions) == 1
    assert sessions[0].session_date == "2026-07-07"
    assert len(sessions[0].exercises) == 2
    names = {e.name for e in sessions[0].exercises}
    assert names == {"Bird-Dog", "Glute Bridge"}


def test_get_recent_sessions_computes_actual_sets_and_volume():
    page = {"properties": {
        "Session Date": _date_prop("2026-07-07"), "Session Duration": _number_prop(30),
        "Session RPE": _number_prop(5), "Session AU": _number_prop(150),
        "Movement": _title_prop("RDL"), "Type": _select_prop("Hip Hinge"),
        "Planned Sets": _number_prop(3), "Planned Reps": _number_prop(8),
        "Exercise RPE": _number_prop(5),
        "Sets": _rich_text_prop(json.dumps([
            {"reps": 8, "weight": 20.0}, {"reps": 8, "weight": 20.0},
        ])),
    }}
    repo = _repo({"db-training": [page]})
    sessions = repo.get_recent_sessions(today=__import__("datetime").date(2026, 7, 7))
    ex = sessions[0].exercises[0]
    assert ex.actual_sets == 2
    assert ex.total_volume_kg == 320.0  # 8*20 + 8*20


# ─── get_last_performance ───────────────────────────────────────────────────

def test_get_last_performance_returns_none_when_never_logged():
    repo = _repo({"db-training": []})
    assert repo.get_last_performance("Goblet Squat") is None


def test_get_last_performance_parses_last_set_of_most_recent_page():
    page = {"properties": {
        "Movement": _title_prop("Goblet Squat"),
        "Session Date": _date_prop("2026-07-14"),
        "Sets": _rich_text_prop(json.dumps([
            {"set_num": 1, "reps": 8, "weight": 10.0},
            {"set_num": 2, "reps": 8, "weight": 12.5},
        ])),
    }}
    repo = _repo({"db-training": [page]})
    result = repo.get_last_performance("Goblet Squat")
    assert result == {
        "session_date": "2026-07-14", "reps": 8, "weight_kg": 12.5,
        "band_tier": None, "sets_count": 2,
    }


def test_get_last_performance_picks_most_recent_date_among_multiple_sessions():
    older = {"properties": {
        "Movement": _title_prop("Goblet Squat"), "Session Date": _date_prop("2026-07-07"),
        "Sets": _rich_text_prop(json.dumps([{"reps": 8, "weight": 10.0}])),
    }}
    newer = {"properties": {
        "Movement": _title_prop("Goblet Squat"), "Session Date": _date_prop("2026-07-14"),
        "Sets": _rich_text_prop(json.dumps([{"reps": 8, "weight": 12.5}])),
    }}
    repo = _repo({"db-training": [older, newer]})
    assert repo.get_last_performance("Goblet Squat")["weight_kg"] == 12.5


def test_get_last_performance_parses_band_tier():
    page = {"properties": {
        "Movement": _title_prop("Lateral Band Walk"), "Session Date": _date_prop("2026-07-14"),
        "Sets": _rich_text_prop(json.dumps([{"reps": 10, "weight": 0.0, "band_tier": "Blue"}])),
    }}
    repo = _repo({"db-training": [page]})
    result = repo.get_last_performance("Lateral Band Walk")
    assert result["band_tier"] == "Blue"
    assert result["weight_kg"] == 0.0


def test_get_last_performance_empty_sets_json_returns_none():
    page = {"properties": {
        "Movement": _title_prop("Goblet Squat"), "Session Date": _date_prop("2026-07-14"),
        "Sets": _rich_text_prop("[]"),
    }}
    repo = _repo({"db-training": [page]})
    assert repo.get_last_performance("Goblet Squat") is None


def test_get_last_performance_corrupt_json_returns_none():
    page = {"properties": {
        "Movement": _title_prop("Goblet Squat"), "Session Date": _date_prop("2026-07-14"),
        "Sets": _rich_text_prop("{not json"),
    }}
    repo = _repo({"db-training": [page]})
    assert repo.get_last_performance("Goblet Squat") is None


def test_get_recent_sessions_multiple_dates_sorted_descending():
    pages = [_exercise_page("2026-07-05", "A"), _exercise_page("2026-07-07", "B")]
    repo = _repo({"db-training": pages})
    sessions = repo.get_recent_sessions(today=__import__("datetime").date(2026, 7, 7))
    assert [s.session_date for s in sessions] == ["2026-07-07", "2026-07-05"]


# ─── get_daily_session_au_weighted ──────────────────────────────────────────

def _weighted_exercise_page(session_date, session_id, movement, sets, session_au=264.0):
    return {"properties": {
        "Session Date": _date_prop(session_date),
        "Session ID":   _rich_text_prop(session_id),
        "Session AU":   _number_prop(session_au),
        "Movement":     _title_prop(movement),
        "Sets":         _rich_text_prop(json.dumps(sets)),
    }}


def test_get_daily_session_au_weighted_applies_content_multiplier():
    import datetime
    # One session, one exercise: 100s of Goblet Squat (weight 1.3) -> the
    # whole session's multiplier is 1.3, so 100 AU becomes 130.
    pages = [_weighted_exercise_page(
        "2026-07-20", "sid-1", "Goblet Squat",
        [{"reps": 8, "weight": 10.0, "rest": 20, "tut": 0, "velocity": "controlled"}] * 5,
        session_au=100.0,
    )]
    repo = _repo({"db-training": pages})
    rows = repo.get_daily_session_au_weighted(days=7, today=datetime.date(2026, 7, 20))
    assert rows == [{"date": "2026-07-20", "total_au": 130.0}]


def test_get_daily_session_au_weighted_dedupes_by_session_id_like_the_raw_version():
    import datetime
    pages = [_weighted_exercise_page(
        "2026-07-20", "sid-1", "Goblet Squat",
        [{"reps": 8, "weight": 10.0, "rest": 20, "tut": 0, "velocity": "controlled"}],
        session_au=100.0,
    )] * 3
    repo = _repo({"db-training": pages})
    rows = repo.get_daily_session_au_weighted(days=7, today=datetime.date(2026, 7, 20))
    assert len(rows) == 1  # not double/triple counted


def test_get_daily_session_au_weighted_two_sessions_same_day_weighted_independently():
    import datetime
    pages = [
        _weighted_exercise_page(
            "2026-07-20", "sid-a", "Goblet Squat",
            [{"reps": 8, "weight": 10.0, "rest": 20, "tut": 0, "velocity": "controlled"}],
            session_au=100.0,
        ),
        _weighted_exercise_page(
            "2026-07-20", "sid-b", "Bird-Dog",
            [{"reps": 8, "weight": 0.0, "rest": 20, "tut": 8, "velocity": "isometric"}],
            session_au=100.0,
        ),
    ]
    repo = _repo({"db-training": pages})
    rows = repo.get_daily_session_au_weighted(days=7, today=datetime.date(2026, 7, 20))
    # sid-a: pure squat (1.3x) -> 130; sid-b: pure mobility_core (0.25x) -> 25; total 155
    assert rows == [{"date": "2026-07-20", "total_au": 155.0}]


def test_get_daily_session_au_weighted_unmapped_exercise_name_stays_at_full_weight():
    import datetime
    pages = [_weighted_exercise_page(
        "2026-07-20", "sid-1", "Some Unknown Pose",
        [{"reps": 8, "weight": 0.0, "rest": 20, "tut": 8, "velocity": "isometric"}],
        session_au=100.0,
    )]
    repo = _repo({"db-training": pages})
    rows = repo.get_daily_session_au_weighted(days=7, today=datetime.date(2026, 7, 20))
    assert rows == [{"date": "2026-07-20", "total_au": 100.0}]


# ─── has_logged_session / get_logged_session_dates ─────────────────────────

def test_has_logged_session_true_when_page_exists():
    import datetime
    repo = _repo({"db-training": [_exercise_page("2026-07-07", "Bird-Dog")]})
    assert repo.has_logged_session(datetime.date(2026, 7, 7)) is True


def test_has_logged_session_false_when_no_pages():
    import datetime
    repo = _repo({"db-training": []})
    assert repo.has_logged_session(datetime.date(2026, 7, 7)) is False


def test_get_logged_session_dates_returns_set_of_dates():
    import datetime
    pages = [_exercise_page("2026-07-05", "A"), _exercise_page("2026-07-07", "B")]
    repo = _repo({"db-training": pages})
    dates = repo.get_logged_session_dates(datetime.date(2026, 7, 1), datetime.date(2026, 7, 10))
    assert dates == {"2026-07-05", "2026-07-07"}


# ─── CheckInRecord write ────────────────────────────────────────────────────

def test_save_check_in_maps_all_fields():
    repo = _repo({"db-readiness": []})
    record = models.CheckInRecord(
        date="2026-07-07", current_condition="Good", tightness_score=3, pain_score=0,
        anatomical_locations=["Glute — Right"], sensation_tags=["Tight"],
        subjective_tightness="mild", alcohol_units=0, travel_flag=False, psych_stress_score=2,
    )
    repo.save_check_in(record)
    props = repo._notion_client.pages.created[0]["properties"]
    assert props["Condition"] == {"select": {"name": "Good"}}
    assert props["Tightness"] == {"number": 3.0}
    assert props["Body Areas"] == {"multi_select": [{"name": "Glute — Right"}]}
    assert props["Travel"] == {"checkbox": False}


def test_save_check_in_maps_hsd_gut_hydration_meditation_fields():
    repo = _repo({"db-readiness": []})
    record = models.CheckInRecord(
        date="2026-07-07", current_condition="Good", tightness_score=3, pain_score=0,
        instability_events=2, bristol_type=4, unusual_stool_colour=True,
        hunger_deviation=-1, thirst_intensity=3,
        electrolytes_taken=True, meditation_done=True,
        meditation_minutes=10, relaxation_depth=4,
    )
    repo.save_check_in(record)
    props = repo._notion_client.pages.created[0]["properties"]
    assert props["Instability Events"] == {"number": 2.0}
    assert props["Bristol Type"] == {"number": 4.0}
    assert props["Unusual Stool Colour"] == {"checkbox": True}
    assert props["Hunger Deviation"] == {"number": -1.0}
    assert props["Thirst Intensity"] == {"number": 3.0}
    assert props["Electrolytes Taken"] == {"checkbox": True}
    assert props["Meditation Done"] == {"checkbox": True}
    assert props["Meditation Minutes"] == {"number": 10.0}
    assert props["Relaxation Depth"] == {"number": 4.0}


def test_get_recent_readiness_maps_fields_and_json_encodes_lists():
    page = {"properties": {
        "Date": _date_prop("2026-07-07"), "Condition": _select_prop("Good"),
        "Tightness": _number_prop(3), "Pain": _number_prop(0),
        "Body Areas": {"multi_select": [{"name": "Glute — Right"}]},
        "Sensations": {"multi_select": [{"name": "Tight"}]},
        "Note": _rich_text_prop("mild"), "Alcohol Units": _number_prop(0),
        "Travel": _checkbox_prop(False), "Stress Level": _number_prop(2),
    }}
    repo = _repo({"db-readiness": [page]})
    import datetime
    rows = repo.get_recent_readiness(today=datetime.date(2026, 7, 7))
    assert rows[0]["anatomical_locations"] == json.dumps(["Glute — Right"])
    assert rows[0]["travel_flag"] == 0


def test_get_recent_readiness_maps_hsd_gut_hydration_meditation_fields():
    page = {"properties": {
        "Date": _date_prop("2026-07-07"), "Condition": _select_prop("Good"),
        "Tightness": _number_prop(3), "Pain": _number_prop(0),
        "Body Areas": {"multi_select": []}, "Sensations": {"multi_select": []},
        "Note": _rich_text_prop(""), "Alcohol Units": _number_prop(0),
        "Travel": _checkbox_prop(False), "Stress Level": _number_prop(2),
        "Instability Events": _number_prop(1), "Bristol Type": _number_prop(5),
        "Unusual Stool Colour": _checkbox_prop(True),
        "Hunger Deviation": _number_prop(2),
        "Thirst Intensity": _number_prop(4), "Electrolytes Taken": _checkbox_prop(True),
        "Meditation Done": _checkbox_prop(True),
        "Meditation Minutes": _number_prop(15), "Relaxation Depth": _number_prop(5),
    }}
    repo = _repo({"db-readiness": [page]})
    import datetime
    row = repo.get_recent_readiness(today=datetime.date(2026, 7, 7))[0]
    assert row["instability_events"] == 1
    assert row["bristol_type"] == 5
    assert row["unusual_stool_colour"] == 1
    assert row["hunger_deviation"] == 2
    assert row["thirst_intensity"] == 4
    assert row["electrolytes_taken"] == 1
    assert row["meditation_done"] == 1
    assert row["meditation_minutes"] == 15
    assert row["relaxation_depth"] == 5


# ─── Check-In schema migration ───────────────────────────────────────────────

def test_ensure_checkin_extension_columns_creates_all_nine_properties():
    repo = _repo({"db-readiness": []})
    created = repo.ensure_checkin_extension_columns()
    assert set(created) == {
        "Instability Events", "Bristol Type", "Unusual Stool Colour",
        "Hunger Deviation", "Thirst Intensity",
        "Electrolytes Taken", "Meditation Done",
        "Meditation Minutes", "Relaxation Depth",
    }
    update_call = repo._notion_client.databases.update_calls[0]
    assert update_call["database_id"] == "db-readiness"


def test_ensure_checkin_extension_columns_is_idempotent():
    repo = _repo({"db-readiness": []})
    first = repo.ensure_checkin_extension_columns()
    second = repo.ensure_checkin_extension_columns()
    assert len(first) == 9
    assert second == []


# ─── BiometricRecord / Sheets mapping ───────────────────────────────────────

class _FakeWorksheet:
    def __init__(self, rows):
        self._rows = rows

    def get_all_records(self):
        return self._rows


class _FakeSheet:
    def __init__(self, rows):
        self._rows = rows

    def worksheet(self, name):
        assert name == "Sheet1"
        return _FakeWorksheet(self._rows)


class _FakeSheetsClient:
    def __init__(self, rows):
        self._rows = rows

    def open_by_key(self, sheet_id):
        return _FakeSheet(self._rows)


_SHEET_ROWS = [
    {
        "Date/Time": "2026-07-07 08:00:00",
        "Heart Rate Variability (ms)": "45.2",
        "Resting Heart Rate (count/min)": "58",
        "Sleep Analysis [Total] (hr)": "7.5",
        "Sleep Analysis [Deep] (hr)": "1.2",
        "Active Energy (kJ)": "1500",
        "Weight (kg)": "78.4",
        "Step Count (count)": "8500",
    },
    {
        "Date/Time": "2026-05-01 08:00:00",  # outside a 28-day window from 2026-07-07
        "Heart Rate Variability (ms)": "40.0",
        "Resting Heart Rate (count/min)": "60",
        "Sleep Analysis [Total] (hr)": "6.0",
        "Sleep Analysis [Deep] (hr)": "1.0",
        "Active Energy (kJ)": "1000",
        "Weight (kg)": "78.0",
        "Step Count (count)": "5000",
    },
]


def _repo_with_sheets(rows) -> Repository:
    repo = Repository(_config())
    repo._sheets_client = _FakeSheetsClient(rows)
    return repo


def test_get_sheet1_biometric_rolling_maps_and_converts_units():
    import datetime
    repo = _repo_with_sheets(_SHEET_ROWS)
    rows = repo.get_sheet1_biometric_rolling(days=28, today=datetime.date(2026, 7, 7))
    assert len(rows) == 1  # the May row is outside the 28-day window
    r = rows[0]
    assert r.date == "2026-07-07"
    assert r.hrv_ms == 45.2
    assert r.resting_heart_rate == 58
    assert r.sleep_duration_hours == 7.5
    assert r.active_kcal == round(1500 / 4.184)  # kJ -> kcal
    assert r.weight_kg == 78.4
    assert r.steps == 8500


def test_get_sheet1_biometric_rolling_sorted_ascending():
    import datetime
    repo = _repo_with_sheets(_SHEET_ROWS)
    rows = repo.get_sheet1_biometric_rolling(days=120, today=datetime.date(2026, 7, 7))
    assert [r.date for r in rows] == ["2026-05-01", "2026-07-07"]


def test_get_raw_sheet_rows_returns_completely_unmapped_rows():
    repo = _repo_with_sheets(_SHEET_ROWS)
    raw = repo.get_raw_sheet_rows()
    assert raw == _SHEET_ROWS  # untouched, original column names


def test_get_sheet1_biometric_rolling_empty_sheet_range():
    repo = _repo_with_sheets([])
    import datetime
    assert repo.get_sheet1_biometric_rolling(today=datetime.date(2026, 7, 7)) == []


def test_get_all_sheet1_biometric_records_unwindowed():
    repo = _repo_with_sheets(_SHEET_ROWS)
    records = repo.get_all_sheet1_biometric_records()
    assert [r.date for r in records] == ["2026-07-07", "2026-05-01"]  # Sheet1 row order, unsorted/unwindowed


# ─── Weekly Rollup — WeekScore <-> row mapping ──────────────────────────────

class _FakeCell:
    def __init__(self, row):
        self.row = row


class _FakeWeeklyRollupWorksheet:
    def __init__(self, rows=None, header=None):
        self.header = header or [
            "week_start", "week_end", "phase", "scheduled", "completed", "ratio", "status", "computed_at",
        ]
        self.rows = rows or []
        self.updates = []
        self.appended = []

    def get_all_records(self):
        return [dict(zip(self.header, r)) for r in self.rows]

    def find(self, query, in_column=None):
        idx = in_column - 1
        for i, row in enumerate(self.rows):
            if idx < len(row) and row[idx] == query:
                return _FakeCell(row=i + 2)
        return None

    def update(self, values, range_name):
        self.updates.append((range_name, values))

    def append_row(self, values):
        self.appended.append(values)
        self.rows.append(list(values))


class _FakeWeeklyRollupSpreadsheet:
    def __init__(self, ws: _FakeWeeklyRollupWorksheet):
        self._ws = ws

    def worksheet(self, name):
        return self._ws


class _FakeWeeklyRollupSheetsClient:
    def __init__(self, ws: _FakeWeeklyRollupWorksheet):
        self._ws = ws

    def open_by_key(self, sheet_id):
        return _FakeWeeklyRollupSpreadsheet(self._ws)


def _repo_with_weekly_rollup(ws: _FakeWeeklyRollupWorksheet) -> Repository:
    repo = Repository(_config())
    repo._sheets_client = _FakeWeeklyRollupSheetsClient(ws)
    return repo


def test_upsert_weekly_rollup_writes_expected_row_shape():
    ws = _FakeWeeklyRollupWorksheet()
    repo = _repo_with_weekly_rollup(ws)
    score = models.WeekScore(
        week_start="2026-07-06", week_end="2026-07-12", phase_number=1,
        scheduled=5, completed=4, status="perfect", computed_at="2026-07-13T09:00:00",
    )
    written = repo.upsert_weekly_rollup([score])
    assert written == ["2026-07-06"]
    assert ws.appended == [[
        "2026-07-06", "2026-07-12", "1", "5", "4", "4/5", "perfect", "2026-07-13T09:00:00",
    ]]


def test_upsert_weekly_rollup_updates_in_place_not_duplicate():
    ws = _FakeWeeklyRollupWorksheet(rows=[
        ["2026-07-06", "2026-07-12", "1", "3", "2", "2/3", "normal", "2026-07-13T09:00:00"],
    ])
    repo = _repo_with_weekly_rollup(ws)
    score = models.WeekScore(
        week_start="2026-07-06", week_end="2026-07-12", phase_number=1,
        scheduled=5, completed=5, status="ultimate", computed_at="2026-07-20T09:00:00",
    )
    repo.upsert_weekly_rollup([score])
    assert ws.appended == []
    assert len(ws.rows) == 1
    assert len(ws.updates) == 1


def test_upsert_weekly_rollup_phase_none_writes_empty_string():
    ws = _FakeWeeklyRollupWorksheet()
    repo = _repo_with_weekly_rollup(ws)
    score = models.WeekScore(
        week_start="2026-06-22", week_end="2026-06-28", phase_number=None,
        scheduled=0, completed=0, status="no_plan", computed_at="2026-07-01T09:00:00",
    )
    repo.upsert_weekly_rollup([score])
    assert ws.appended[0][2] == ""  # phase column


def test_get_weekly_rollup_history_parses_rows_back_to_weekscore():
    ws = _FakeWeeklyRollupWorksheet(rows=[
        ["2026-07-06", "2026-07-12", "1", "5", "4", "4/5", "perfect", "2026-07-13T09:00:00"],
    ])
    repo = _repo_with_weekly_rollup(ws)
    history = repo.get_weekly_rollup_history()
    assert history == [models.WeekScore(
        week_start="2026-07-06", week_end="2026-07-12", phase_number=1,
        scheduled=5, completed=4, status="perfect", computed_at="2026-07-13T09:00:00",
    )]


def test_get_weekly_rollup_history_empty_phase_column_becomes_none():
    ws = _FakeWeeklyRollupWorksheet(rows=[
        ["2026-06-22", "2026-06-28", "", "0", "0", "0/0", "no_plan", "2026-07-01T09:00:00"],
    ])
    repo = _repo_with_weekly_rollup(ws)
    history = repo.get_weekly_rollup_history()
    assert history[0].phase_number is None


def test_get_weekly_rollup_history_skips_malformed_rows():
    ws = _FakeWeeklyRollupWorksheet(rows=[
        ["2026-07-06", "2026-07-12", "1", "not-a-number", "4", "4/5", "perfect", "2026-07-13T09:00:00"],
    ])
    repo = _repo_with_weekly_rollup(ws)
    assert repo.get_weekly_rollup_history() == []


# ─── Long-tail dict-returning functions (spot checks) ──────────────────────

def test_get_pain_free_streak_counts_until_first_pain_day():
    pages = [
        {"properties": {"Pain": _number_prop(0)}},
        {"properties": {"Pain": _number_prop(0)}},
        {"properties": {"Pain": _number_prop(2)}},
        {"properties": {"Pain": _number_prop(0)}},
    ]
    repo = _repo({"db-readiness": pages})
    assert repo.get_pain_free_streak() == 2


def test_get_avg_tightness_rounds_to_one_decimal():
    import datetime
    pages = [
        {"properties": {"Tightness": _number_prop(3)}},
        {"properties": {"Tightness": _number_prop(4)}},
    ]
    repo = _repo({"db-readiness": pages})
    assert repo.get_avg_tightness(today=datetime.date(2026, 7, 7)) == 3.5


def test_get_avg_tightness_empty_returns_zero():
    import datetime
    repo = _repo({"db-readiness": []})
    assert repo.get_avg_tightness(today=datetime.date(2026, 7, 7)) == 0.0


def test_get_current_stage_defaults_to_1():
    repo = _repo({"db-config": []})
    assert repo.get_current_stage() == 1


# ─── No Streamlit import ────────────────────────────────────────────────────

def test_repository_and_models_never_import_streamlit():
    import services.repository as repo_mod
    import services.models as models_mod
    for mod in (repo_mod, models_mod):
        tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or node.module.split(".")[0] != "streamlit"
