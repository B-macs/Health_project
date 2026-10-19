"""The background_writer setting (rebuild rule 2; Phase 2 milestone 4,
2026-10-19): only the process the store names runs the background writes.
The gate's background_writer_leaks counter runs this file. Fakes only; no
network.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from services import background_writer as bw
from services import oura_auth
from services.background_sync import BackgroundSyncRunner
from services.config import Config, load_config
from services.repository import Repository

ROOT = Path(__file__).resolve().parents[1]


class _Store:
    """A config row as the store holds it; `fail` makes the read fail."""

    def __init__(self, value=None, fail=False):
        self.value, self.fail = value, fail

    def get_config_value_live(self, key):
        assert key == bw.CONFIG_KEY
        if self.fail:
            raise RuntimeError("store unreachable")
        return self.value


@pytest.mark.parametrize("stored,writer", [
    (None, bw.STREAMLIT), ("", bw.STREAMLIT), ("streamlit", bw.STREAMLIT),
    ("engine", bw.ENGINE), (" Engine ", bw.ENGINE), ("both", None),
])
def test_the_store_names_the_writer(stored, writer):
    assert bw.current(_Store(stored)) == writer


def test_a_failed_read_names_nobody():
    assert bw.current(_Store(fail=True)) is None
    assert not bw.may_write(_Store(fail=True), bw.STREAMLIT)
    assert not bw.may_write(_Store(fail=True), bw.ENGINE)


def test_exactly_one_process_may_write():
    for stored in (None, "engine", "streamlit"):
        store = _Store(stored)
        assert [bw.may_write(store, p) for p in bw.WRITERS].count(True) == 1
    with pytest.raises(bw.NotTheWriterError):
        bw.require(_Store("engine"), bw.STREAMLIT)
    bw.require(_Store("engine"), bw.ENGINE)


# ─── the sync runner ──────────────────────────────────────────────────────────

class _Repo(_Store):
    def __init__(self, config, value):
        super().__init__(value)
        self.synced = False

    def run_home_syncs(self, today=None):
        self.synced = True
        return {"oura": (True, None)}


def _run(process: str, stored):
    made = []

    def factory(config):
        made.append(_Repo(config, stored))
        return made[-1]

    runner = BackgroundSyncRunner(Config(**{**_CONFIG, "background_process": process}),
                                  repository_factory=factory)
    runner.run_now(date(2026, 10, 19))
    return runner, made[0]


_CONFIG = dict(notion_api_key="", notion_db_readiness="a", notion_db_training="b",
               notion_db_config="c", google_sheets_id="", google_service_account={})


def test_the_streamlit_app_syncs_until_the_engine_takes_over():
    runner, repo = _run(bw.STREAMLIT, None)
    assert repo.synced and runner.skipped_for() is None
    runner, repo = _run(bw.STREAMLIT, "engine")
    assert not repo.synced and runner.skipped_for() == bw.ENGINE


def test_the_engine_syncs_only_once_it_is_named():
    runner, repo = _run(bw.ENGINE, None)
    assert not repo.synced and runner.skipped_for() == bw.STREAMLIT
    runner, repo = _run(bw.ENGINE, "engine")
    assert repo.synced


def test_a_process_that_names_nothing_is_not_checked():
    runner, repo = _run("", "engine")
    assert repo.synced


# ─── the Oura refresh token ───────────────────────────────────────────────────

class _OuraRepo(_Store):
    """The real _refresh_oura_token over a fake store and a fake Oura."""

    def __init__(self, process, stored):
        super().__init__(stored)
        self.config = Config(**{**_CONFIG, "background_process": process,
                                "oura_client_id": "id", "oura_client_secret": "secret"})
        self.stored_tokens = []

    def _store_oura_token(self, token):
        self.stored_tokens.append(token)

    _refresh_oura_token = Repository._refresh_oura_token


def _token():
    return oura_auth.OAuthToken(access_token="a", refresh_token="r")


def test_the_engine_never_spends_the_oura_refresh_token_while_streamlit_writes(monkeypatch):
    calls = []
    monkeypatch.setattr("services.clients.oura.refresh_access_token",
                        lambda *a, **k: calls.append(a) or {})
    with pytest.raises(bw.NotTheWriterError):
        _OuraRepo(bw.ENGINE, "streamlit")._refresh_oura_token(_token())
    with pytest.raises(bw.NotTheWriterError):
        _OuraRepo(bw.STREAMLIT, "engine")._refresh_oura_token(_token())
    assert calls == [], "Oura was never asked: the refresh token is intact"


def test_the_writer_refreshes(monkeypatch):
    calls = []
    monkeypatch.setattr("services.clients.oura.refresh_access_token",
                        lambda *a, **k: calls.append(a) or {
                            "access_token": "a2", "refresh_token": "r2", "expires_in": 3600})
    repo = _OuraRepo(bw.ENGINE, "engine")
    repo._refresh_oura_token(_token())
    assert len(calls) == 1 and repo.stored_tokens


# ─── each process names itself ────────────────────────────────────────────────

def test_each_process_names_itself(tmp_path):
    import sys
    if str(ROOT / "api") not in sys.path:      # the engine's package
        sys.path.insert(0, str(ROOT / "api"))
    from healthapi import settings
    assert '"HEALTH_PROCESS": "streamlit"' in (ROOT / "repo.py").read_text(encoding="utf-8")
    secrets = tmp_path / "secrets.toml"         # a made-up project, never reached
    secrets.write_text('SUPABASE_URL = "https://example.supabase.co"\n'
                       'SUPABASE_SECRET_KEY = "not-a-key"\n', encoding="utf-8")
    assert settings.build_config(secrets).background_process == bw.ENGINE
    assert load_config({"HEALTH_PROCESS": " Streamlit ", "SUPABASE_URL": "https://example.supabase.co",
                        "SUPABASE_SECRET_KEY": "not-a-key"}).background_process == bw.STREAMLIT


def test_the_engines_sync_job_refuses_while_streamlit_writes():
    """POST /api/sync's job (services/engine_sync.py): while the store names
    the Streamlit app, nothing reaches a device and nothing is stored."""
    from services import engine_sync

    class Runner:
        asked = False

        def run_now(self, today=None):
            Runner.asked = True
            return {}

    class Store(_Store):
        stored = {}

        def get_config_value(self, key):
            return None

        def set_config(self, key, value, today=None):
            Store.stored[key] = value

    for stored in (None, "streamlit", "both"):
        with pytest.raises(bw.NotTheWriterError):
            engine_sync.run(Store(stored), Runner(), date(2026, 10, 19),
                            datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc), force=True)
    assert not Runner.asked and Store.stored == {}


def test_the_training_page_writes_unasked_only_as_the_writer():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "if phases and not _in_session and _streamlit_writes():" in src
    assert src.count("_streamlit_writes()") >= 4, "the rule, two unasked records, the helper"
