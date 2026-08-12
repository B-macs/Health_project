"""Tests for services/config.py — env-var and overrides-dict resolution."""

import pytest

from services.config import load_config

_OVERRIDES = {
    "NOTION_API_KEY": "ntn_test",
    "NOTION_DB_READINESS": "db-readiness",
    "NOTION_DB_TRAINING": "db-training",
    "NOTION_DB_CONFIG": "db-config",
    "GOOGLE_SHEETS_ID": "sheet-id",
    "google_service_account": {"type": "service_account", "project_id": "p"},
}


def test_load_config_from_overrides():
    cfg = load_config(_OVERRIDES)
    assert cfg.notion_api_key == "ntn_test"
    assert cfg.notion_db_readiness == "db-readiness"
    assert cfg.notion_db_training == "db-training"
    assert cfg.notion_db_config == "db-config"
    assert cfg.google_sheets_id == "sheet-id"
    assert cfg.google_service_account == {"type": "service_account", "project_id": "p"}


def test_load_config_from_env_vars(monkeypatch):
    for k, v in _OVERRIDES.items():
        if k != "google_service_account":
            monkeypatch.setenv(k, v)
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", '{"type": "service_account", "project_id": "p"}')
    cfg = load_config()
    assert cfg.notion_api_key == "ntn_test"
    assert cfg.google_service_account == {"type": "service_account", "project_id": "p"}


def test_overrides_win_over_env(monkeypatch):
    monkeypatch.setenv("NOTION_API_KEY", "from_env")
    cfg = load_config({**_OVERRIDES, "NOTION_API_KEY": "from_overrides"})
    assert cfg.notion_api_key == "from_overrides"


def test_missing_key_raises():
    with pytest.raises(EnvironmentError):
        load_config({})


def test_missing_service_account_raises(monkeypatch):
    incomplete = {k: v for k, v in _OVERRIDES.items() if k != "google_service_account"}
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
    with pytest.raises(EnvironmentError):
        load_config(incomplete)


def test_config_never_imports_streamlit():
    import ast
    import services.config as config_mod
    src = open(config_mod.__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "streamlit" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] != "streamlit"


def test_secrets_override_environment_variables_not_the_other_way_round():
    """The docstring claimed env-first for a long time and the code has always
    been overrides-first. It decides where a setting can live: anything in
    secrets.toml cannot be varied per environment by an env var, which is why
    HEALTH_DATASTORE_PATH/MODE belong in the environment and credentials
    belong in secrets."""
    import os
    from services import config as config_mod

    os.environ["HEALTH_DATASTORE_MODE"] = "from-env"
    try:
        assert config_mod._resolve_optional_str(
            "HEALTH_DATASTORE_MODE", {"HEALTH_DATASTORE_MODE": "from-secrets"}
        ) == "from-secrets"
        assert config_mod._resolve_optional_str("HEALTH_DATASTORE_MODE", {}) == "from-env"
    finally:
        del os.environ["HEALTH_DATASTORE_MODE"]


def test_cache_mode_needs_a_datastore_path_to_mean_anything():
    """Setting the mode alone does nothing — datastore_mode is only read when
    datastore_path is set. Worth pinning, because setting one and not the
    other looks like it should work and silently leaves the app on live."""
    from services.repository import Repository
    from services.config import Config

    cfg = Config(notion_api_key="k", notion_db_readiness="a", notion_db_training="b",
                 notion_db_config="d", google_sheets_id="e", google_service_account={},
                 datastore_mode="cache")
    repo = Repository(cfg)
    assert repo.cached is False and repo.local_datastore is False
