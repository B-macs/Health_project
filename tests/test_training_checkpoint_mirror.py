"""
Tests for the LOCAL MIRROR of the in-progress training checkpoint —
Repository.save_training_checkpoint_local / get_training_checkpoint_local /
clear_training_checkpoint_local, plus the two views/training.py contracts
built on them (_save_checkpoint's durable flag and _rerun_flow's fallback).

WHY THE MIRROR EXISTS. The durable checkpoint lives in Notion under
set_config("training_progress"), and ONE set_config is a find-then-write PAIR
— a database query to locate the page, then a page update (see
services/repository.py's set_config/_config_page). The guided flow called it
on every weight/reps/band stepper tap, i.e. two network round trips each time,
on a screen the athlete taps five times to move 20 kg to 32.5 kg. On a phone
that is the whole perceived lag.

WHY THE TAP-PATH WRITE WAS NOT SIMPLY DELETED. The stepper value is not
cosmetic. views/training.py's _record_completed_set reads
st.session_state.tp_actuals LIVE at the moment a set is completed, and
_auto_log_session persists exactly that blob. So a reconnect that restored a
STALE load would not merely inconvenience the athlete — it would LOG every
subsequent set at the wrong weight, understating weekly tonnage and lowering
the next session's clamp ceiling (which _seed_actuals_if_needed derives from
get_last_session_all_sets). The mirror keeps every tap lossless while taking
the network off the tap path.

THE ONE DANGEROUS STATE is a mirror that is OLDER than Notion, because
_load_checkpoint prefers the mirror by fixed precedence rather than comparing
timestamps. That precedence is only sound while the mirror is written on every
checkpoint and Notion on a subset — so a mirror write that FAILS must delete
the key rather than leave the previous payload behind. Left stale, it would
win over a newer Notion copy and could resurrect a session the athlete had
explicitly discarded (the _reset_session write is the one whose loss moves
state the wrong way). That is what test_a_failed_mirror_write_* pins.

tests/conftest.py points local_cache._DEFAULT_PATH at a tmp_path for every
test, so none of this touches the real .sync_state.json.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from services.clients import local_cache
from services.config import Config
from services.repository import Repository

TRAINING_VIEW = Path(__file__).resolve().parent.parent / "views" / "training.py"


def _config(**overrides) -> Config:
    base = dict(
        notion_api_key="ntn_test",
        notion_db_readiness="db-readiness",
        notion_db_training="db-training",
        notion_db_biometrics="db-biometrics",
        notion_db_config="db-config",
        google_sheets_id="sheet-id",
        google_service_account={"type": "service_account"},
    )
    base.update(overrides)
    return Config(**base)


def _repo() -> Repository:
    return Repository(_config())


# ─── the mirror round-trips ──────────────────────────────────────────────────

def test_mirror_round_trips_the_exact_payload_string():
    """Stored and returned VERBATIM. The caller hands over an already-encoded
    JSON string precisely so nothing re-serialises it — see the note on
    thread-safety in test_payload_is_encoded_before_storage below."""
    r = _repo()
    payload = json.dumps({"day_num": 3, "tp_ex_idx": 2, "tp_actuals": {"0": {"reps": 10}}})
    assert r.save_training_checkpoint_local(payload) is True
    assert r.get_training_checkpoint_local() == payload


def test_absent_mirror_reads_as_none_not_an_error():
    """None means "ask Notion", which is what a fresh process must do — on
    Streamlit Community Cloud the local file is gone after a container
    restart, and that is a normal state, not a failure."""
    assert _repo().get_training_checkpoint_local() is None


def test_mirror_overwrites_rather_than_accumulating():
    r = _repo()
    r.save_training_checkpoint_local(json.dumps({"tp_ex_idx": 1}))
    r.save_training_checkpoint_local(json.dumps({"tp_ex_idx": 2}))
    assert json.loads(r.get_training_checkpoint_local())["tp_ex_idx"] == 2


def test_clearing_the_mirror_leaves_none():
    r = _repo()
    r.save_training_checkpoint_local(json.dumps({"tp_ex_idx": 1}))
    r.clear_training_checkpoint_local()
    assert r.get_training_checkpoint_local() is None


def test_mirror_does_not_disturb_the_sync_throttle_markers():
    """The mirror shares .sync_state.json with the sync markers (the same way
    the Home snapshot and the flexibility assessments already do). Writing one
    must not drop the others."""
    r = _repo()
    local_cache.update({"oura_last_synced": "2026-08-10T09:00:00"})
    r.save_training_checkpoint_local(json.dumps({"tp_ex_idx": 1}))
    assert local_cache.read().get("oura_last_synced") == "2026-08-10T09:00:00"
    r.clear_training_checkpoint_local()
    assert local_cache.read().get("oura_last_synced") == "2026-08-10T09:00:00"


# ─── the failure rule: absent beats stale ────────────────────────────────────

def test_a_failed_mirror_write_reports_false(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(local_cache, "update", boom)
    assert _repo().save_training_checkpoint_local(json.dumps({"tp_ex_idx": 9})) is False


def test_a_failed_mirror_write_removes_the_previous_payload(monkeypatch):
    """THE load-bearing test. _load_checkpoint prefers the mirror over Notion
    by fixed precedence, so a mirror left holding an OLDER payload after a
    failed write would beat a newer durable copy — the concrete harm being a
    discarded session coming back to life. Absent is safe; stale is not."""
    r = _repo()
    r.save_training_checkpoint_local(json.dumps({"tp_ex_idx": 1}))
    assert r.get_training_checkpoint_local() is not None

    calls = {"n": 0}
    real_update = local_cache.update

    def fail_first_then_delete(changes, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real_update(changes, *a, **k)

    monkeypatch.setattr(local_cache, "update", fail_first_then_delete)
    assert r.save_training_checkpoint_local(json.dumps({"tp_ex_idx": 2})) is False
    assert r.get_training_checkpoint_local() is None


def test_a_read_failure_degrades_to_none_rather_than_raising(monkeypatch):
    """A checkpoint read must never be the thing that breaks the screen — the
    fallback to Notion is right there."""
    monkeypatch.setattr(local_cache, "read", lambda *a, **k: (_ for _ in ()).throw(OSError("gone")))
    assert _repo().get_training_checkpoint_local() is None


def test_a_non_string_mirror_value_is_ignored(monkeypatch):
    """Defensive against a hand-edited or half-migrated .sync_state.json: the
    contract is a JSON *string*, and anything else is treated as absent rather
    than handed to json.loads."""
    local_cache.update({"training_checkpoint": {"not": "a string"}})
    assert _repo().get_training_checkpoint_local() is None


# ─── the views/training.py contracts, pinned against the source ──────────────
#  views/ has no runtime coverage in this suite, so these read the module as
#  source text the way tests/test_manual_sync_serialised.py does.

def _view_source() -> str:
    return TRAINING_VIEW.read_text(encoding="utf-8")


def _fn(name: str) -> ast.FunctionDef:
    tree = ast.parse(_view_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in views/training.py")


def test_save_checkpoint_takes_a_durable_flag_defaulting_to_true():
    """Defaulting to True matters: every call site that is NOT explicitly on
    the hot path keeps its durable write without being touched."""
    fn = _fn("_save_checkpoint")
    assert any(a.arg == "durable" for a in fn.args.args)
    assert fn.args.defaults and fn.args.defaults[-1].value is True


def test_every_stepper_tap_is_local_only():
    """The six weight/reps/band steppers are the hot path — the whole point of
    the mirror. Each must pass durable=False, or the Notion pair is back."""
    src = _view_source()
    steppers = [
        'sess.step_reps(_actual["reps"], -1)',
        'sess.step_reps(_actual["reps"], +1)',
        'sess.step_band_tier(_actual["band_tier"], -1)',
        'sess.step_band_tier(_actual["band_tier"], +1)',
        'sess.step_weight_kg(_actual["weight_kg"], -1, increment=_incr)',
        'sess.step_weight_kg(_actual["weight_kg"], +1, increment=_incr)',
    ]
    for call in steppers:
        assert call in src, f"stepper moved or was renamed: {call}"
        after = src.split(call, 1)[1][:160]
        assert "_save_checkpoint(day_num, durable=False)" in after, (
            f"stepper {call} no longer checkpoints locally — a Notion "
            f"find-then-write pair is back on the tap path"
        )


def _called_methods(fn: ast.FunctionDef) -> list[str]:
    """Attribute-call names in source order. Walks the AST rather than the
    source text so a name merely MENTIONED in the docstring (both of these
    functions explain themselves in prose) cannot be mistaken for a call."""
    out: list[tuple[int, int, str]] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            out.append((node.lineno, node.col_offset, node.func.attr))
    return [name for _l, _c, name in sorted(out)]


def test_the_mirror_is_written_before_the_durable_copy():
    """Ordering IS the safety property behind _load_checkpoint's fixed
    precedence: mirror first means a Notion failure still leaves the fresher
    copy on disk, so the mirror can never be the older of the two."""
    calls = _called_methods(_fn("_save_checkpoint"))
    assert "save_training_checkpoint_local" in calls
    assert "set_config" in calls
    assert calls.index("save_training_checkpoint_local") < calls.index("set_config"), (
        "the local mirror must be written before the Notion write"
    )


def test_load_checkpoint_prefers_the_mirror_and_falls_back_to_notion():
    calls = _called_methods(_fn("_load_checkpoint"))
    assert "get_training_checkpoint_local" in calls, "the mirror must be consulted"
    assert "get_config_value" in calls, "the Notion fallback must remain"
    assert calls.index("get_training_checkpoint_local") < calls.index("get_config_value"), (
        "the mirror must be consulted before Notion"
    )
