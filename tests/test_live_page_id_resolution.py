"""
A NOTION WRITE NEEDS A LIVE PAGE ID, and in cache mode the read did not give
it one.

Cache mode — the HOSTED runtime — reads locally and writes live. Every Notion
read goes through Repository._query, which off the datastore returns rows
wearing SYNTHESIZED page ids ("offline:config:phases"): notion_reader invents
them because a SQLite row has no Notion UUID. They are deliberately not UUIDs
so that a write built on one is rejected by the API rather than landing on
some unrelated page.

That safety property fired for real. Starting the Stage 2B block on the hosted
app called set_phases -> set_config -> notion.pages.update("offline:config:
phases") and raised APIResponseError out of the one button that screen exists
to offer, with no way forward but editing Notion by hand. The id was doing
exactly its job; what was missing was the other half of the split.

Repository._live_page_id is that half — the Notion twin of _write_target,
which already resolves a live Sheets tab for writes while _ws serves reads
locally. Two handles, because there are two backends in play.

⚠ Only READINESS and CONFIG synthesize. A TRAINING page id IS its exercise_id,
the real UUID, which is why none of the training write paths were ever bitten
and why they must keep costing no extra round trip.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from pathlib import Path

import pytest

from services import supabase_store
from services.clients import notion_reader
from services.clients.datastore_reader import DatastoreReadOnlyError
from services.config import Config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = (ROOT / "services" / "datastore_schema.sql").read_text(encoding="utf-8")

REAL_ID = "3bec1e81-c8fe-8106-b48a-d7e98fa5d5eb"


@pytest.fixture(autouse=True)
def _empty_outbox():
    supabase_store.OUTBOX.drain()
    yield
    supabase_store.OUTBOX.drain()


class FakeNotion:
    """Records what the API was asked to do, and answers queries from `pages`.

    Deliberately does NOT validate the page id — the point of these tests is
    which id we send, and a fake that rejected a bad one would prove only that
    the fake rejects it.
    """

    def __init__(self, pages=None):
        self._pages = list(pages or [])
        self.calls: list[tuple] = []
        outer = self

        class _Pages:
            def update(self, page_id, properties=None, **kw):
                outer.calls.append(("update", page_id, properties))
                return {"id": page_id}

            def create(self, parent, properties=None, **kw):
                outer.calls.append(("create", parent["database_id"], properties))
                return {"id": REAL_ID}

            def retrieve(self, page_id):
                outer.calls.append(("retrieve", page_id, None))
                return {"id": page_id, "properties": {}}

        class _Databases:
            def query(self, **kw):
                outer.calls.append(("query", kw.get("database_id"), kw.get("filter")))
                return {"results": outer._pages, "has_more": False}

        self.pages = _Pages()
        self.databases = _Databases()

    @property
    def queries(self):
        return [c for c in self.calls if c[0] == "query"]

    @property
    def writes(self):
        return [c for c in self.calls if c[0] in ("update", "create")]


def _config(path, mode="cache"):
    return Config(
        notion_api_key="k", notion_db_readiness="db-readiness",
        notion_db_training="db-training", notion_db_config="db-config",
        google_sheets_id="e", google_service_account={},
        datastore_path=path, datastore_mode=mode)


@pytest.fixture
def cache_db(tmp_path):
    path = tmp_path / "cache.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO config (key, value, updated) VALUES (?,?,?)",
                 ("phases", "[]", "2026-08-16"))
    conn.execute("INSERT INTO readiness_checkins (date, tightness_score) VALUES (?,?)",
                 ("2026-08-17", 2.0))
    conn.commit()
    conn.close()
    return str(path)


def _repo(path, notion_pages=None, mode="cache"):
    repo = Repository(_config(path, mode))
    repo._notion_client = FakeNotion(notion_pages)
    return repo


def _live_config_page(key):
    return {"id": REAL_ID, "properties": {"Key": {"title": [{"plain_text": key}]}}}


# ─── the reported failure ────────────────────────────────────────────────

def test_the_datastore_really_does_hand_out_unwritable_config_ids(cache_db):
    """The premise, pinned so the rest of this file cannot go stale silently."""
    repo = _repo(cache_db)
    page = repo._config_page("phases")
    assert page is not None
    assert page["id"] == "offline:config:phases"
    assert notion_reader.is_synthesized_page_id(page["id"])


def test_set_config_updates_the_real_page_not_the_synthesized_one(cache_db):
    """The bug: beginning the next block crashed here on the hosted app."""
    repo = _repo(cache_db, notion_pages=[_live_config_page("phases")])
    repo.set_config("phases", json.dumps([{"phase_number": 3}]))

    writes = repo._notion_client.writes
    assert [w[0] for w in writes] == ["update"]
    assert writes[0][1] == REAL_ID, "wrote to a page id Notion cannot parse"


def test_set_config_creates_when_the_local_row_outlives_the_notion_page(cache_db):
    """A cache hydrated from Supabase can hold a row whose Notion page is
    gone. Updating nothing is not an option and neither is raising — create."""
    repo = _repo(cache_db, notion_pages=[])
    repo.set_config("phases", "[]")

    writes = repo._notion_client.writes
    assert [w[0] for w in writes] == ["create"]
    assert writes[0][1] == "db-config"


def test_a_brand_new_key_still_creates_without_a_lookup(cache_db):
    """No local row means nothing to resolve; the lookup must not happen."""
    repo = _repo(cache_db, notion_pages=[_live_config_page("nope")])
    repo.set_config("some_new_key", "1")
    assert [w[0] for w in repo._notion_client.writes] == ["create"]
    assert repo._notion_client.queries == [], "resolved an id that did not exist"


def test_the_lookup_filters_on_the_key_it_is_resolving(cache_db):
    repo = _repo(cache_db, notion_pages=[_live_config_page("phases")])
    repo.set_config("phases", "[]")
    (_, db_id, filter_), = repo._notion_client.queries
    assert db_id == "db-config"
    assert filter_ == {"property": "Key", "title": {"equals": "phases"}}


def test_beginning_a_block_persists_and_the_next_read_sees_it(cache_db):
    """The whole outcome, not just which id was sent: press the button, and
    the phase is active on the next render. Cache mode makes this the real
    acceptance criterion — the write has to reach Notion AND land in the local
    copy the very next read comes from."""
    from datetime import date

    from services import plan as ph, sessions as sess

    repo = _repo(cache_db, notion_pages=[_live_config_page("phases")])
    assert repo.get_phases() == [], "fixture seeds an empty phase list"

    new_phase = ph.default_phase(date(2026, 8, 17), length_days=28,
                                 phase_number=3, name="Stage 2B")
    repo.set_phases(sess.begin_new_phase(repo.get_phases(), new_phase))

    after = repo.get_phases()
    assert [(p.phase_number, p.start_date, p.status) for p in after] == \
        [(3, "2026-08-17", "active")]
    assert ph.active_phase(after, date(2026, 8, 17)) is not None


# ─── live mode is untouched, and pays nothing ────────────────────────────

def test_a_real_id_passes_straight_through(cache_db):
    """Every TRAINING write path relies on this: its ids are already real, so
    resolution must be a no-op costing no round trip."""
    repo = _repo(cache_db)
    assert repo._live_page_id(REAL_ID) == REAL_ID
    assert repo._live_page_id(None) is None
    assert repo._notion_client.queries == []


def test_live_mode_issues_no_resolution_query():
    """With no datastore, reads already return real pages. Adding a lookup
    would have doubled the writes on the one path that was never broken."""
    repo = Repository(Config(
        notion_api_key="k", notion_db_readiness="db-readiness",
        notion_db_training="db-training", notion_db_config="db-config",
        google_sheets_id="e", google_service_account={}))
    repo._notion_client = FakeNotion([_live_config_page("phases")])
    repo.set_config("phases", "[]")

    # One query only: _config_pages' own read. The write resolves nothing.
    assert len(repo._notion_client.queries) == 1
    writes = repo._notion_client.writes
    assert [w[0] for w in writes] == ["update"] and writes[0][1] == REAL_ID


# ─── the other two readiness write paths ─────────────────────────────────

def test_save_check_in_updates_the_real_page(cache_db):
    import services.models as models
    repo = _repo(cache_db, notion_pages=[{
        "id": REAL_ID,
        "properties": {"Date": {"date": {"start": "2026-08-17"}}},
    }])
    repo.save_check_in(models.CheckInRecord(
        date="2026-08-17", current_condition="Good",
        tightness_score=3, pain_score=0))

    writes = repo._notion_client.writes
    assert [w[0] for w in writes] == ["update"]
    assert writes[0][1] == REAL_ID


def test_update_readiness_ai_resolves_its_caller_supplied_id(cache_db):
    """get_unparsed_readiness hands back whatever _query produced."""
    repo = _repo(cache_db, notion_pages=[{
        "id": REAL_ID,
        "properties": {"Date": {"date": {"start": "2026-08-17"}}},
    }])
    repo.update_readiness_ai("offline:readiness:2026-08-17", 4.0, [], [], "none")
    writes = repo._notion_client.writes
    assert [w[0] for w in writes] == ["update"] and writes[0][1] == REAL_ID


def test_update_readiness_ai_skips_a_page_that_no_longer_exists(cache_db):
    """It only ever ANNOTATES someone else's check-in. A page holding five AI
    columns and no reading is worse than no page at all."""
    repo = _repo(cache_db, notion_pages=[])
    repo.update_readiness_ai("offline:readiness:2026-08-17", 4.0, [], [], "none")
    assert repo._notion_client.writes == []


# ─── the merge path refuses instead of guessing ──────────────────────────

def test_duplicate_detection_refuses_to_run_off_the_datastore(cache_db):
    """readiness_checkins is keyed BY date, so duplicates were collapsed on
    the way in. Returning {} would read as "checked, all clean"."""
    repo = _repo(cache_db)
    with pytest.raises(DatastoreReadOnlyError):
        repo.find_duplicate_check_in_dates()


def test_apply_check_in_merge_refuses_a_synthesized_id(cache_db):
    repo = _repo(cache_db)
    with pytest.raises(ValueError):
        repo.apply_check_in_merge("offline:readiness:2026-08-17", {}, [])
    with pytest.raises(ValueError):
        repo.apply_check_in_merge(REAL_ID, {}, ["offline:readiness:2026-08-17"])
    assert repo._notion_client.writes == []


# ─── the id helpers ──────────────────────────────────────────────────────

def test_synthesized_page_key_round_trips():
    assert notion_reader.synthesized_page_key("offline:config:phases") == \
        ("config", "phases")
    assert notion_reader.synthesized_page_key("offline:readiness:2026-08-17") == \
        ("readiness", "2026-08-17")


def test_a_real_uuid_is_not_mistaken_for_a_synthesized_id():
    assert notion_reader.is_synthesized_page_id(REAL_ID) is False
    assert notion_reader.is_synthesized_page_id(None) is False
    with pytest.raises(ValueError):
        notion_reader.synthesized_page_key(REAL_ID)


# ─── the guard: no new write may skip the resolution ─────────────────────

#: Functions whose page id is a real Notion UUID by construction, with the
#: reason. notion_reader._page_id returns row["exercise_id"] for TRAINING —
#: the id Notion itself issued at create_page — so these need no lookup and
#: must not pay for one.
_TRAINING_ID_WRITERS = {
    "save_session_notes":     "training_log_id IS exercise_id, the real page id",
    "update_session_note_ai": "note_id comes from a TRAINING page, id already real",
    "reassign_exercise_rpe_from_hr": "TRAINING pages carry their real ids",
    "apply_check_in_merge":   "refuses a synthesized id outright, see above",
}

_WRITE_CALLS = {"update_page", "archive_page"}


def _page_id_args():
    """(function name, the expression passed as the page id) for every Notion
    page write in repository.py."""
    tree = ast.parse((ROOT / "services" / "repository.py").read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr in _WRITE_CALLS and \
                    isinstance(f.value, ast.Name) and f.value.id == "notion":
                out.append((fn.name, node.args[1] if len(node.args) > 1 else None))
            elif isinstance(f, ast.Attribute) and f.attr == "retrieve" and \
                    isinstance(f.value, ast.Attribute) and f.value.attr == "pages":
                out.append((fn.name, node.args[0] if node.args else None))
    return out


def _resolved_names(fn_name):
    """Names assigned from self._live_page_id(...) inside `fn_name`."""
    tree = ast.parse((ROOT / "services" / "repository.py").read_text(encoding="utf-8"))
    names = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name != fn_name:
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                   and c.func.attr == "_live_page_id" for c in ast.walk(node.value)):
                names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def test_the_guard_actually_finds_the_write_sites():
    """A scan that matched nothing would pass the test below vacuously."""
    found = _page_id_args()
    assert len(found) >= 6, f"only found {len(found)} Notion page writes"
    assert "set_config" in {name for name, _ in found}


def test_every_notion_page_write_uses_a_resolved_id():
    """Adding a write that reuses a _query-derived id reintroduces the exact
    crash this file is named for — silently, and only on the hosted app."""
    bad = []
    for fn_name, arg in _page_id_args():
        if fn_name in _TRAINING_ID_WRITERS or arg is None:
            continue
        direct = (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
                  and arg.func.attr == "_live_page_id")
        via_name = isinstance(arg, ast.Name) and arg.id in _resolved_names(fn_name)
        if not (direct or via_name):
            bad.append(f"{fn_name}: {ast.unparse(arg)}")
    assert not bad, (
        "these Notion writes pass an unresolved page id — in cache mode that "
        "is a synthesized 'offline:...' string and the API rejects it:\n  "
        + "\n  ".join(bad)
    )
