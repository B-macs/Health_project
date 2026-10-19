"""The training session's checkpoint and restore rules and the "already
logged" lock, moved to services/sessions.py on 2026-10-19 (move TRN-2), and
two faults fixed with them:

- F17: the timers kept their state under a key that was the same every day,
  so a timer left running on an earlier day showed DONE at once.
- F19: a walk's Garmin-verified minutes and the heart-rate panel were not
  checkpointed, so after a dropped connection the walk logged its planned
  minutes.
"""

from __future__ import annotations

import ast
import json
from datetime import date, datetime
from pathlib import Path

from services import sessions as sess

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 19)


def _state(**over):
    state = {k: None for k in sess.CHECKPOINT_FIELDS}
    state.update(over)
    return state


def test_walk_minutes_and_the_heart_rate_panel_survive_a_drop():
    for field in ("tp_garmin_minutes", "tp_garmin_activity_detail", "tp_hr_au",
                  "tp_reported_rpe", "tp_reported_au"):
        assert field in sess.CHECKPOINT_FIELDS, field
    hr = {"hr_rpe": 6.2, "hr_au": 310.0, "window": (datetime(2026, 10, 19, 8, 0),
                                                    datetime(2026, 10, 19, 9, 0))}
    raw = sess.checkpoint_json(3, _state(tp_garmin_minutes={2: 31},
                                         tp_garmin_activity_detail={2: {"avg_hr": 128}},
                                         tp_hr_au=hr, tp_reported_rpe=6, tp_reported_au=300.0))
    back = sess.parse_checkpoint(raw, 3)
    assert back["tp_garmin_minutes"] == {2: 31}, "the walk logs its measured minutes"
    assert back["tp_garmin_activity_detail"] == {2: {"avg_hr": 128}}
    assert back["tp_hr_au"]["hr_au"] == 310.0
    assert back["tp_hr_au"]["window"][0].startswith("2026-10-19"), "date-times stored as text"
    assert back["tp_reported_rpe"] == 6


def test_a_checkpoint_of_another_day_or_an_unreadable_one_restores_nothing():
    raw = sess.checkpoint_json(3, _state(tp_ex_idx=4))
    assert sess.parse_checkpoint(raw, 3)["tp_ex_idx"] == 4
    assert sess.parse_checkpoint(raw, 4) is None
    assert sess.parse_checkpoint("not json", 3) is None
    assert sess.parse_checkpoint("[1, 2]", 3) is None
    assert sess.parse_checkpoint(None, 3) is None


def test_every_checkpoint_field_has_a_default():
    """The payload indexes session_state with every field; a field with no
    default in _init_state stops the whole checkpoint saving, silently."""
    tree = ast.parse((ROOT / "views" / "training.py").read_text(encoding="utf-8"))
    init = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_init_state")
    defaults = next(n.value for n in ast.walk(init)
                    if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "defaults")
    keys = {k.value for k in defaults.keys}
    assert set(sess.CHECKPOINT_FIELDS) <= keys, set(sess.CHECKPOINT_FIELDS) - keys
    assert set(sess.ACCESSORY_STALE_RESET) <= keys


def test_a_logged_plan_day_locks_and_a_failed_read_does_not():
    class _Repo:
        def __init__(self, answer):
            self.answer = answer

        def has_logged_session(self, day):
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer

    assert sess.logged_today(_Repo(True), DAY)
    assert not sess.logged_today(_Repo(False), DAY)
    assert not sess.logged_today(_Repo(RuntimeError("store unreachable")), DAY)


def test_a_timer_key_belongs_to_one_day_and_one_session():
    today = sess.timer_keys(DAY, 1, 2, 1, 1, "right")
    assert today != sess.timer_keys(date(2026, 10, 26), 8, 2, 1, 1, "right")
    assert today["duration"] != sess.timer_keys(DAY, -1, 2, 1, 1, "right")["duration"], (
        "the accessory session's timers are its own")
    assert len(set(today.values())) == 4


def test_the_activity_timer_drops_a_stale_state():
    src = (ROOT / "views" / "training.py").read_text(encoding="utf-8")
    assert "var _STALE_MS = (_dtotal + 3600) * 1000;" in src
    assert "if (Date.now() - s.savedAt > _STALE_MS) {{ _clear(); return; }}" in src
    assert 'f"tp_d_{_eidx}"' not in src, "the old same-every-day key is gone"
