"""Tests for services/clients/notion.py and services/clients/sheets.py —
the raw property (de)serializers, pagination/retry, and Sheets read, moved
verbatim from db.py / sync_sheets.py. Also services/clients/local_cache.py —
the generic JSON read/write underneath the Oura sync throttle."""

import ast

import gspread
import httpx
import pytest
from notion_client.errors import APIResponseError

from services.clients import local_cache
from services.clients import notion as notion_client_mod
from services.clients import sheets as sheets_client_mod


# ─── Property builders ─────────────────────────────────────────────────────

def test_title():
    assert notion_client_mod.title("Hello") == {"title": [{"text": {"content": "Hello"}}]}


def test_title_none_becomes_empty_string():
    assert notion_client_mod.title(None) == {"title": [{"text": {"content": ""}}]}


def test_title_truncates_to_2000_chars():
    long = "x" * 3000
    built = notion_client_mod.title(long)
    assert len(built["title"][0]["text"]["content"]) == 2000


def test_rich_text():
    assert notion_client_mod.rich_text("note") == {"rich_text": [{"text": {"content": "note"}}]}


def test_number():
    assert notion_client_mod.number(3) == {"number": 3.0}
    assert notion_client_mod.number(None) == {"number": None}


def test_select():
    assert notion_client_mod.select("Rehab") == {"select": {"name": "Rehab"}}
    assert notion_client_mod.select(None) == {"select": None}
    assert notion_client_mod.select("") == {"select": None}


def test_multi_select():
    assert notion_client_mod.multi_select(["a", "b"]) == {
        "multi_select": [{"name": "a"}, {"name": "b"}]
    }
    assert notion_client_mod.multi_select(None) == {"multi_select": []}


def test_date_prop():
    assert notion_client_mod.date_prop("2026-07-07") == {"date": {"start": "2026-07-07"}}
    assert notion_client_mod.date_prop(None) == {"date": None}


def test_checkbox():
    assert notion_client_mod.checkbox(True) == {"checkbox": True}
    assert notion_client_mod.checkbox(0) == {"checkbox": False}


# ─── Property extractor ────────────────────────────────────────────────────

def _page(prop_name: str, prop_value: dict) -> dict:
    return {"properties": {prop_name: prop_value}}


def test_get_property_title():
    page = _page("Name", {"title": [{"plain_text": "Bird-Dog"}]})
    assert notion_client_mod.get_property(page, "Name", "title") == "Bird-Dog"


def test_get_property_rich_text_concatenates_segments():
    page = _page("Notes", {"rich_text": [{"plain_text": "Hip "}, {"plain_text": "flexors."}]})
    assert notion_client_mod.get_property(page, "Notes", "rich_text") == "Hip flexors."


def test_get_property_number():
    page = _page("RPE", {"number": 6})
    assert notion_client_mod.get_property(page, "RPE", "number") == 6


def test_get_property_select_none():
    page = _page("Stage", {"select": None})
    assert notion_client_mod.get_property(page, "Stage", "select") is None


def test_get_property_multi_select():
    page = _page("Tags", {"multi_select": [{"name": "Tight"}, {"name": "Sharp"}]})
    assert notion_client_mod.get_property(page, "Tags", "multi_select") == ["Tight", "Sharp"]


def test_get_property_date():
    page = _page("Session Date", {"date": {"start": "2026-07-07"}})
    assert notion_client_mod.get_property(page, "Session Date", "date") == "2026-07-07"


def test_get_property_checkbox_defaults_false():
    page = _page("Flag", {"checkbox": False})
    assert notion_client_mod.get_property(page, "Flag", "checkbox") is False


def test_get_property_missing_property_returns_none():
    assert notion_client_mod.get_property({"properties": {}}, "Missing", "number") is None


# ─── query_database: pagination + rate-limit retry ─────────────────────────

class _FakeDatabases:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


class _FakeClient:
    def __init__(self, responses):
        self.databases = _FakeDatabases(responses)


def test_query_database_single_page():
    client = _FakeClient([{"results": [{"id": "1"}, {"id": "2"}], "has_more": False}])
    out = notion_client_mod.query_database(client, "db123")
    assert out == [{"id": "1"}, {"id": "2"}]
    assert client.databases.calls[0]["database_id"] == "db123"


def test_query_database_follows_pagination_cursor():
    client = _FakeClient([
        {"results": [{"id": "1"}], "has_more": True, "next_cursor": "cursor-abc"},
        {"results": [{"id": "2"}], "has_more": False},
    ])
    out = notion_client_mod.query_database(client, "db123")
    assert out == [{"id": "1"}, {"id": "2"}]
    assert client.databases.calls[1]["start_cursor"] == "cursor-abc"


def test_query_database_passes_filter_and_sorts():
    client = _FakeClient([{"results": [], "has_more": False}])
    notion_client_mod.query_database(
        client, "db123", filter_={"property": "X", "number": {"equals": 1}},
        sorts=[{"property": "X", "direction": "ascending"}],
    )
    call = client.databases.calls[0]
    assert call["filter"] == {"property": "X", "number": {"equals": 1}}
    assert call["sorts"] == [{"property": "X", "direction": "ascending"}]


def test_query_database_retries_once_on_429():
    req = httpx.Request("POST", "https://api.notion.com/v1/databases/db123/query")
    resp = httpx.Response(429, request=req)
    rate_limited = APIResponseError(resp, "rate limited", "rate_limited")
    client = _FakeClient([rate_limited, {"results": [{"id": "1"}], "has_more": False}])
    out = notion_client_mod.query_database(client, "db123")
    assert out == [{"id": "1"}]
    assert len(client.databases.calls) == 2


def test_query_database_reraises_non_429_errors():
    req = httpx.Request("POST", "https://api.notion.com/v1/databases/db123/query")
    resp = httpx.Response(404, request=req)
    not_found = APIResponseError(resp, "not found", "object_not_found")
    client = _FakeClient([not_found])
    with pytest.raises(APIResponseError):
        notion_client_mod.query_database(client, "db123")


def test_create_page_and_update_page():
    class _Pages:
        def __init__(self):
            self.created = None
            self.updated = None

        def create(self, parent, properties):
            self.created = (parent, properties)
            return {"id": "new-page"}

        def update(self, page_id, properties):
            self.updated = (page_id, properties)
            return {"id": page_id}

    class _C:
        def __init__(self):
            self.pages = _Pages()

    c = _C()
    created = notion_client_mod.create_page(c, "db123", {"Key": "value"})
    assert created == {"id": "new-page"}
    assert c.pages.created == ({"database_id": "db123"}, {"Key": "value"})

    updated = notion_client_mod.update_page(c, "page-1", {"Key": "value2"})
    assert updated == {"id": "page-1"}
    assert c.pages.updated == ("page-1", {"Key": "value2"})


# ─── Sheets client ──────────────────────────────────────────────────────────

def test_get_all_records():
    class _Worksheet:
        def get_all_records(self):
            return [{"Date/Time": "2026-07-01 08:00", "Heart Rate Variability (ms)": "45.2"}]

    class _Sheet:
        def worksheet(self, name):
            assert name == "Sheet1"
            return _Worksheet()

    class _Client:
        def open_by_key(self, sheet_id):
            assert sheet_id == "sheet-xyz"
            return _Sheet()

    out = sheets_client_mod.get_all_records(_Client(), "sheet-xyz")
    assert out == [{"Date/Time": "2026-07-01 08:00", "Heart Rate Variability (ms)": "45.2"}]


# ─── Weekly Rollup worksheet primitives ─────────────────────────────────────

class _FakeCell:
    def __init__(self, row):
        self.row = row


class _FakeWeeklyRollupWorksheet:
    def __init__(self, rows=None):
        self.rows = rows or []  # list of row_values lists, in sheet order
        self.updates = []
        self.appended = []
        self.header_written = None

    def get_all_records(self):
        return [dict(zip(self.header_written or [], r)) for r in self.rows]

    def find(self, query, in_column=None):
        idx = in_column - 1
        for i, row in enumerate(self.rows):
            if idx < len(row) and row[idx] == query:
                return _FakeCell(row=i + 2)  # +1 for header row, +1 for 1-indexing
        return None

    def update(self, values, range_name):
        self.updates.append((range_name, values))
        # Reflect the update back into self.rows so a second call in the
        # same test sees the new state, like a real sheet would.
        row_idx = int("".join(c for c in range_name.split(":")[0] if c.isdigit())) - 2
        if 0 <= row_idx < len(self.rows):
            self.rows[row_idx] = list(values[0])

    def append_row(self, values):
        self.appended.append(values)
        self.rows.append(list(values))


class _FakeSpreadsheet:
    def __init__(self, worksheets=None):
        self._worksheets = worksheets or {}
        self.added = []

    def worksheet(self, name):
        if name not in self._worksheets:
            raise gspread.WorksheetNotFound(name)
        return self._worksheets[name]

    def add_worksheet(self, title, rows, cols):
        ws = _FakeWeeklyRollupWorksheet()
        self._worksheets[title] = ws
        self.added.append({"title": title, "rows": rows, "cols": cols})
        return ws


class _FakeSpreadsheetClient:
    def __init__(self, spreadsheet):
        self._spreadsheet = spreadsheet

    def open_by_key(self, sheet_id):
        return self._spreadsheet


_HEADER = ["week_start", "week_end", "phase", "scheduled", "completed", "ratio", "status", "computed_at"]


def test_get_or_create_weekly_rollup_worksheet_creates_when_absent():
    spreadsheet = _FakeSpreadsheet()
    client = _FakeSpreadsheetClient(spreadsheet)
    ws = sheets_client_mod.get_or_create_weekly_rollup_worksheet(client, "sheet-1", _HEADER)
    assert spreadsheet.added == [{"title": "Weekly Rollup", "rows": 200, "cols": 10}]
    assert ws.updates == [("A1", [_HEADER])]


def test_get_or_create_weekly_rollup_worksheet_reuses_existing():
    existing = _FakeWeeklyRollupWorksheet()
    spreadsheet = _FakeSpreadsheet({"Weekly Rollup": existing})
    client = _FakeSpreadsheetClient(spreadsheet)
    ws = sheets_client_mod.get_or_create_weekly_rollup_worksheet(client, "sheet-1", _HEADER)
    assert ws is existing
    assert spreadsheet.added == []


def test_upsert_weekly_rollup_row_appends_when_key_not_found():
    ws = _FakeWeeklyRollupWorksheet()
    sheets_client_mod.upsert_weekly_rollup_row(ws, key_col=1, key_value="2026-07-06", row_values=["2026-07-06", "x"])
    assert ws.appended == [["2026-07-06", "x"]]
    assert ws.updates == []


def test_upsert_weekly_rollup_row_updates_in_place_when_key_found():
    ws = _FakeWeeklyRollupWorksheet(rows=[["2026-07-06", "old"]])
    sheets_client_mod.upsert_weekly_rollup_row(ws, key_col=1, key_value="2026-07-06", row_values=["2026-07-06", "new"])
    assert ws.appended == []
    assert ws.updates == [("A2:B2", [["2026-07-06", "new"]])]


def test_upsert_weekly_rollup_row_never_appends_a_duplicate():
    ws = _FakeWeeklyRollupWorksheet(rows=[["2026-07-06", "old"]])
    sheets_client_mod.upsert_weekly_rollup_row(ws, key_col=1, key_value="2026-07-06", row_values=["2026-07-06", "new"])
    assert len(ws.rows) == 1


# ─── local_cache ─────────────────────────────────────────────────────────────

def test_local_cache_read_missing_file_returns_empty_dict(tmp_path):
    assert local_cache.read(path=tmp_path / "nope.json") == {}


def test_local_cache_read_corrupted_json_returns_empty_dict(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json")
    assert local_cache.read(path=p) == {}


def test_local_cache_write_then_read_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    local_cache.write({"oura_last_synced": "2026-07-14T09:00:00"}, path=p)
    assert local_cache.read(path=p) == {"oura_last_synced": "2026-07-14T09:00:00"}


def test_local_cache_write_overwrites_existing_file(tmp_path):
    p = tmp_path / "state.json"
    local_cache.write({"a": 1}, path=p)
    local_cache.write({"a": 2}, path=p)
    assert local_cache.read(path=p) == {"a": 2}


# ─── No Streamlit imports ───────────────────────────────────────────────────

@pytest.mark.parametrize("mod", [notion_client_mod, sheets_client_mod, local_cache])
def test_no_streamlit_import(mod):
    tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"
