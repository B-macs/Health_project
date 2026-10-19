"""scripts/rebuild_secrets.py: the engine's keys go to Google, and nothing else.

The engine (rebuild Phase 0) reads its secrets from ONE Secret Manager secret.
With Supabase as the only store the engine never calls Notion or Google Sheets,
so their token and service-account key - and the Voice Training app's keys -
must not be uploaded with it. These tests pin that the trimmed file keeps
exactly the engine's keys, that every value reads back identically whatever
characters a password holds, that the engine's own config loads from it, and
that the upload prints names only, never a value. No network: the gcloud call
is replaced.
"""

from __future__ import annotations

import tomllib

import pytest

from scripts import rebuild_secrets as rs
from services.config import load_config

FAKE = {
    "NOTION_API_KEY": "fake-notion-token",
    "NOTION_DB_TRAINING": "fake-db",
    "GOOGLE_SHEETS_ID": "fake-sheet",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SECRET_KEY": "fake-supabase-secret",
    "SUPABASE_PUBLISHABLE_KEY": "fake-publishable",
    "GARMIN_EMAIL": "someone@example.com",
    "GARMIN_PASSWORD": 'p"a\\ss\nwörd \U0001F642\x7fend',
    "OURA_TOKEN": "fake-pat",
    "CLIENT_ID": "fake-client-id",
    "CLIENT_SECRET": "fake-client-secret",
    "google_service_account": {"type": "service_account", "private_key": "fake-key"},
    "voxplot_supabase": {"url": "https://voice.example", "secret_key": "fake-voice"},
}
ENGINE_KEYS = {"SUPABASE_URL", "SUPABASE_SECRET_KEY", "GARMIN_EMAIL", "GARMIN_PASSWORD",
               "CLIENT_ID", "CLIENT_SECRET"}


def test_only_the_engines_keys_are_kept_and_they_read_back_identically():
    text, left_out = rs.engine_secrets_toml(FAKE)
    back = tomllib.loads(text)
    assert set(back) == ENGINE_KEYS
    assert all(back[k] == FAKE[k] for k in ENGINE_KEYS)       # the tricky password too
    assert {"NOTION_API_KEY", "GOOGLE_SHEETS_ID", "google_service_account",
            "voxplot_supabase", "SUPABASE_PUBLISHABLE_KEY", "OURA_TOKEN"} <= set(left_out)


def test_blank_or_missing_keys_are_simply_left_out():
    text, _ = rs.engine_secrets_toml({"SUPABASE_URL": "u", "SUPABASE_SECRET_KEY": "",
                                      "GARMIN_EMAIL": None})
    assert tomllib.loads(text) == {"SUPABASE_URL": "u"}


def test_the_engine_config_loads_from_the_trimmed_file(monkeypatch):
    for key in ("NOTION_API_KEY", "GOOGLE_SHEETS_ID", "GOOGLE_SERVICE_ACCOUNT_JSON",
                "HEALTH_DATASTORE_PATH", "HEALTH_DATASTORE_MODE", "HEALTH_SYSTEM_OF_RECORD",
                "NOTION_DB_READINESS", "NOTION_DB_TRAINING", "NOTION_DB_CONFIG"):
        monkeypatch.delenv(key, raising=False)
    text, _ = rs.engine_secrets_toml(FAKE)
    config = load_config(tomllib.loads(text))
    assert config.system_of_record == "supabase"
    assert config.datastore_mode == "cache"
    assert config.garmin_password == FAKE["GARMIN_PASSWORD"]
    assert config.oura_client_id == FAKE["CLIENT_ID"]
    assert config.notion_api_key == "" and config.google_service_account == {}


def test_the_upload_prints_names_only(tmp_path, monkeypatch, capsys):
    path = tmp_path / "secrets.toml"
    path.write_text("".join(f"{k} = {rs._toml_string(v)}\n"
                            for k, v in FAKE.items() if isinstance(v, str)), encoding="utf-8")
    sent = {}
    monkeypatch.setattr(rs, "SECRETS_TOML", path)
    monkeypatch.setattr(rs, "_gcloud", lambda: "gcloud")
    monkeypatch.setattr(rs, "_run", lambda cmd, data=None, **kw: sent.update(cmd=cmd, data=data))
    rs.engine_secrets()
    out = capsys.readouterr().out
    assert sent["cmd"][:4] == ["gcloud", "secrets", "create", "health-engine-secrets"]
    assert tomllib.loads(sent["data"].decode("utf-8"))["GARMIN_PASSWORD"] == FAKE["GARMIN_PASSWORD"]
    for value in (v for v in FAKE.values() if isinstance(v, str)):
        assert value not in out
    assert "GARMIN_PASSWORD" in out and "NOTION_API_KEY" in out      # names, for the record


def test_the_upload_refuses_without_supabase(tmp_path, monkeypatch):
    path = tmp_path / "secrets.toml"
    path.write_text('GARMIN_EMAIL = "x"\n', encoding="utf-8")
    monkeypatch.setattr(rs, "SECRETS_TOML", path)
    monkeypatch.setattr(rs, "_run", lambda *a, **k: pytest.fail("must not upload"))
    with pytest.raises(SystemExit):
        rs.engine_secrets()
