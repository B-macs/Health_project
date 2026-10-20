"""The retired old app (rebuild Phase 9, switch step 8).

Once the engine is the background writer, the Streamlit app refuses every write
with the banner's words (Repository._refuse_if_retired) and says so on every
page (app.py). Keyed on the stored setting, so the switch and its undo need no
push; the engine and scripts are never refused. Made-up rows, a fake store.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from services import background_writer as bw
from services import repository as repository_module
from services.models import CheckInRecord
from services.repository import Repository
from tests._record_store import FakeStore, new_local_copy, record_config

ROOT = Path(__file__).resolve().parents[1]


def _maker(tmp_path):
    """Repositories over one store and one local copy, each naming its process."""
    path = new_local_copy(tmp_path)
    store = FakeStore()

    def make(process: str | None) -> Repository:
        config = record_config(path)
        if process:
            config = dataclasses.replace(config, background_process=process)
        repo = Repository(config)
        repo._supabase_store_obj = store
        return repo
    return make, store


def _checkin(day: str) -> CheckInRecord:
    return CheckInRecord(date=day, current_condition=None, tightness_score=2.0, pain_score=0.0)


def _stored_days(store) -> list[str]:
    return sorted(str(r["date"]) for r in store.tables.get("readiness_checkins", []))


def test_the_old_app_refuses_every_write_once_the_engine_writes(tmp_path):
    make, store = _maker(tmp_path)
    make(None).set_config(bw.CONFIG_KEY, bw.ENGINE)
    old = make(bw.STREAMLIT)
    with pytest.raises(bw.AppRetiredError, match="This app is retired"):
        old.save_check_in(_checkin("2026-10-20"))
    assert _stored_days(store) == [], "nothing reached the store"


def test_the_old_app_writes_while_it_is_the_writer(tmp_path):
    make, store = _maker(tmp_path)
    make(bw.STREAMLIT).save_check_in(_checkin("2026-10-20"))
    assert _stored_days(store) == ["2026-10-20"]


def test_the_engine_and_scripts_are_never_refused(tmp_path):
    make, store = _maker(tmp_path)
    make(None).set_config(bw.CONFIG_KEY, bw.ENGINE)
    make(bw.ENGINE).save_check_in(_checkin("2026-10-19"))
    make(None).save_check_in(_checkin("2026-10-20"))
    assert _stored_days(store) == ["2026-10-19", "2026-10-20"]


def test_the_setting_is_read_again_after_a_minute(tmp_path, monkeypatch):
    """The setting is read live at most once a minute: a switch reaches a running old app
    within that minute, and the undo the same way."""
    make, store = _maker(tmp_path)
    old = make(bw.STREAMLIT)
    clock = [1000.0]
    monkeypatch.setattr(repository_module.time, "monotonic", lambda: clock[0])
    old.save_check_in(_checkin("2026-10-18"))
    make(None).set_config(bw.CONFIG_KEY, bw.ENGINE)
    old.save_check_in(_checkin("2026-10-19"))            # the minute has not passed
    clock[0] += old.RETIRED_CHECK_SECONDS
    with pytest.raises(bw.AppRetiredError):
        old.save_check_in(_checkin("2026-10-20"))
    make(None).set_config(bw.CONFIG_KEY, bw.STREAMLIT)   # the undo
    clock[0] += old.RETIRED_CHECK_SECONDS
    old.save_check_in(_checkin("2026-10-20"))
    assert _stored_days(store) == ["2026-10-18", "2026-10-19", "2026-10-20"]


def test_every_page_of_the_old_app_shows_the_retired_banner():
    """Drawn before the router, beside the offline banner, from the same words."""
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    banner = source.index("st.error(background_writer.RETIRED_TEXT")
    assert banner < source.index("_page = navigation.resolve_page(")
    assert "def _app_retired()" in source and "background_writer.ENGINE" in source
