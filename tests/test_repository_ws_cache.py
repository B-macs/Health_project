"""
Tests for Repository._ws's worksheet-handle memoization.

Distinct from the short-lived READ cache further down that file (_read_records,
covered by its own behaviour elsewhere). That one caches the rows; this one
caches the handle, and the difference matters because the handle is resolved
BEFORE _read_records is even entered:

    self._read_records(self._garmin_daily_ws())

Python evaluates the getter first, so every read-cache HIT still paid a
sheets.get_or_create_worksheet() — an open_by_key() plus a
fetch_sheet_metadata() round-trip. One Home render resolves the same handful
of tabs a dozen-plus times over.

Caching a handle is safe in a way caching rows is not: it carries no data, so
every read through it still goes to the API. That is why this needs no
invalidation and _read_records needs write_generation().
"""

from __future__ import annotations

from services.clients import sheets
from services.config import Config
from services.repository import Repository


def _config(**overrides) -> Config:
    base = dict(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )
    base.update(overrides)
    return Config(**base)


class _CountingWorksheet:
    def __init__(self, title):
        self.title = title

    def get_all_records(self, numericise_ignore=None, expected_headers=None):
        return []


class _CountingSpreadsheet:
    """Counts worksheet() lookups — the API round-trip being saved."""

    def __init__(self, counter):
        self.counter = counter

    def worksheet(self, title):
        self.counter[title] = self.counter.get(title, 0) + 1
        return _CountingWorksheet(title)


class _CountingClient:
    def __init__(self, counter):
        self.opens = 0
        self._ss = _CountingSpreadsheet(counter)

    def open_by_key(self, sheet_id):
        self.opens += 1
        return self._ss


def _repo():
    counter: dict = {}
    repo = Repository(_config())
    client = _CountingClient(counter)
    repo._sheets_client = client
    return repo, client, counter


def test_handle_resolved_once_per_tab():
    repo, client, counter = _repo()
    for _ in range(6):
        repo._garmin_daily_ws()
    assert counter[sheets.GARMIN_DAILY_WORKSHEET] == 1
    assert client.opens == 1


def test_same_handle_object_is_returned():
    repo, _client, _counter = _repo()
    assert repo._garmin_daily_ws() is repo._garmin_daily_ws()


def test_each_tab_cached_independently():
    repo, _client, counter = _repo()
    repo._garmin_daily_ws()
    repo._metrics_history_ws()
    repo._oura_daily_ws()
    repo._garmin_daily_ws()
    repo._metrics_history_ws()
    assert counter[sheets.GARMIN_DAILY_WORKSHEET] == 1
    assert counter[sheets.METRICS_HISTORY_WORKSHEET] == 1
    assert counter[sheets.OURA_DAILY_WORKSHEET] == 1


def test_reads_through_the_cached_handle_do_not_re_resolve_it():
    """The real shape: several getters reading the same tab across one
    render. Previously each _read_records(self._x_ws()) re-resolved."""
    repo, _client, counter = _repo()
    for _ in range(4):
        repo._read_records(repo._oura_daily_ws())
    assert counter[sheets.OURA_DAILY_WORKSHEET] == 1


def test_separate_repository_instances_do_not_share_handles():
    """Per instance, so a new process (or a st.cache_resource miss) starts
    cold rather than inheriting a stale handle."""
    counter: dict = {}
    for _ in range(2):
        repo = Repository(_config())
        repo._sheets_client = _CountingClient(counter)
        repo._garmin_daily_ws()
    assert counter[sheets.GARMIN_DAILY_WORKSHEET] == 2
