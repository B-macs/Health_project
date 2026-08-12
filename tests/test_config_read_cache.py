"""
The Config database is read ONCE per burst, not once per key.

THE N+1 THIS REMOVES. Repository._config_page ran a filtered Notion database
query per key, and six methods use it — get_config_value, get_current_stage,
get_phases, get_diagnostic_profile, latest_movement_risk, and the training
checkpoint. Six keys out of one tiny table meant six HTTP round trips, on
every page's critical path.

Measured 2026-08-10 against the live backend: get_phases 0.57s,
get_current_stage 0.40s, get_config_value 0.36s — 1.33s of a 4.62s page open,
with Notion accounting for 92% of that wall time. An unfiltered fetch of the
same table costs about the same as one filtered fetch, because the table holds
a handful of rows, so this trades six round trips for one.

WHAT KEEPS IT HONEST. A Repository is process-wide (repo.get_repository is an
@st.cache_resource), shared across sessions and reruns, so an unbounded memo
would hide a config change until the process restarted. Two things bound it:
set_config invalidates, so this app's own writes are always visible
immediately; and a 30s TTL bounds the one writer the cache cannot see — a
human editing the Config database in Notion's UI.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from services.config import Config
from services.repository import Repository


def _config() -> Config:
    return Config(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )


def _row(key: str, value: str) -> dict:
    return {
        "id": f"page-{key}",
        "properties": {
            "Key": {"type": "title", "title": [{"plain_text": key}]},
            "Value": {"type": "rich_text", "rich_text": [{"plain_text": value}]},
        },
    }


ROWS = [
    _row("plan_start_date", "2026-06-29"),
    _row("current_stage", "2"),
    _row("phases", json.dumps([{"phase_number": 1, "name": "Stage 1",
                                "start_date": "2026-06-29", "length_days": 28,
                                "status": "active", "date_overrides": {},
                                "shift_reasons": {}}])),
    _row("training_progress", json.dumps({"day_num": 3})),
]


class _Counter:
    """Stands in for Repository._query and counts the round trips."""

    def __init__(self, rows=ROWS):
        self.rows = rows
        self.calls = 0
        self.filters = []

    def __call__(self, db_id, filter_=None, sorts=None):
        self.calls += 1
        self.filters.append(filter_)
        return list(self.rows)


@pytest.fixture
def repo_and_query(monkeypatch):
    repo = Repository(_config())
    q = _Counter()
    monkeypatch.setattr(repo, "_query", q)
    return repo, q


# ─── the win ─────────────────────────────────────────────────────────────────

def test_six_different_config_reads_cost_one_query(repo_and_query):
    """THE regression test for the N+1. Before this, each of these was its own
    filtered database query."""
    repo, q = repo_and_query
    repo.get_config_value("plan_start_date")
    repo.get_current_stage()
    repo.get_phases()
    repo.get_config_value("training_progress")
    repo.get_config_value("plan_start_date")
    repo.get_config_value("does_not_exist")
    assert q.calls == 1, (
        f"{q.calls} Notion round trips for six config reads — the N+1 is back"
    )


def test_the_one_query_is_unfiltered(repo_and_query):
    """Fetching the whole table is the point; a per-key filter would put us
    straight back to one query per key."""
    repo, q = repo_and_query
    repo.get_config_value("current_stage")
    assert q.filters == [None]


def test_the_values_are_still_correct(repo_and_query):
    repo, _q = repo_and_query
    assert repo.get_config_value("plan_start_date") == "2026-06-29"
    assert repo.get_current_stage() == 2
    assert len(repo.get_phases()) == 1
    assert repo.get_config_value("absent") is None


def test_a_missing_key_does_not_trigger_a_refetch(repo_and_query):
    """A miss must be cached as a miss. Otherwise every read of an unset key —
    and several are optional — re-queries the whole table."""
    repo, q = repo_and_query
    for _ in range(5):
        assert repo.get_config_value("never_set") is None
    assert q.calls == 1


# ─── what stops it going stale ───────────────────────────────────────────────

def test_a_write_is_visible_to_the_very_next_read(monkeypatch):
    """set_config must invalidate, or the app cannot read back what it just
    wrote — which is how the training checkpoint would resurrect old state."""
    repo = Repository(_config())
    rows = list(ROWS)
    q = _Counter(rows)
    monkeypatch.setattr(repo, "_query", q)
    monkeypatch.setattr(repo, "_notion_client", object())
    monkeypatch.setattr("services.repository.notion.update_page",
                        lambda *a, **k: None)
    monkeypatch.setattr("services.repository.notion.create_page",
                        lambda *a, **k: None)

    assert repo.get_config_value("current_stage") == "2"
    q.rows = [_row("current_stage", "3")]
    repo.set_config("current_stage", "3", today=date(2026, 8, 10))
    assert repo.get_config_value("current_stage") == "3"


def test_a_failed_write_also_invalidates(monkeypatch):
    """The cached page may be exactly what is wrong — deleted upstream, or the
    wrong side of a duplicate — and serving it again repeats the failure."""
    repo = Repository(_config())
    q = _Counter()
    monkeypatch.setattr(repo, "_query", q)
    monkeypatch.setattr(repo, "_notion_client", object())

    def boom(*a, **k):
        raise RuntimeError("notion down")

    monkeypatch.setattr("services.repository.notion.update_page", boom)
    repo.get_config_value("current_stage")
    with pytest.raises(RuntimeError):
        repo.set_config("current_stage", "3", today=date(2026, 8, 10))
    assert repo._config_cache is None


def test_the_cache_expires(monkeypatch, repo_and_query):
    """Bounds the one writer this cache cannot see: a human editing the Config
    DB in Notion's UI. A process-wide Repository would otherwise hide that
    edit until restart."""
    repo, q = repo_and_query
    clock = {"t": 1000.0}
    monkeypatch.setattr("services.repository.time.monotonic", lambda: clock["t"])

    repo.get_config_value("current_stage")
    assert q.calls == 1
    clock["t"] += repo._CONFIG_CACHE_TTL_SECONDS - 1
    repo.get_config_value("current_stage")
    assert q.calls == 1, "still inside the TTL"
    clock["t"] += 2
    repo.get_config_value("current_stage")
    assert q.calls == 2, "past the TTL, it must refetch"


def test_duplicate_keys_resolve_first_wins(monkeypatch):
    """Matches what the per-key filtered query already did (`pages[0]`).
    Notion guarantees no order either way, so a duplicated key was already
    nondeterministic — this must not make it worse by picking at random."""
    repo = Repository(_config())
    dupes = [_row("current_stage", "2"), _row("current_stage", "9")]
    monkeypatch.setattr(repo, "_query", _Counter(dupes))
    assert repo.get_config_value("current_stage") == "2"
    assert repo.get_config_value("current_stage") == "2"


def test_rows_without_a_key_are_skipped(monkeypatch):
    repo = Repository(_config())
    blank = {"id": "p", "properties": {
        "Key": {"type": "title", "title": []},
        "Value": {"type": "rich_text", "rich_text": [{"plain_text": "orphan"}]},
    }}
    monkeypatch.setattr(repo, "_query", _Counter([blank, _row("current_stage", "2")]))
    assert repo.get_config_value("current_stage") == "2"
