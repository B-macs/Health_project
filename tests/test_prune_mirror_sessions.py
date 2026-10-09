"""scripts/prune_mirror_sessions.py deletes Supabase rows, so its plan is pinned.

2026-10-09: Supabase held 50 sessions on 2026-10-05 where Notion holds two,
and the hosted app rebuilds its read cache from Supabase on every restart.
The script removes what Notion does not hold. The one safety property: an
empty Notion read names NOTHING for deletion, never everything.
"""
import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "prune_mirror_sessions.py"
_spec = importlib.util.spec_from_file_location("prune_mirror_sessions", _PATH)
prune = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prune)


def _ex(exercise_id, session_id):
    return {"exercise_id": exercise_id, "session_id": session_id,
            "session_date": "2026-10-05"}


def test_an_empty_notion_read_deletes_nothing():
    with pytest.raises(prune.PruneRefused):
        prune.prune_plan([], [_ex("a", "s1")], [{"session_id": "s1"}])


def test_names_only_what_notion_does_not_hold():
    notion = [_ex("a", "s1"), _ex("b", "s1")]
    supabase_ex = [_ex("a", "s1"), _ex("b", "s1"), _ex("c", "s2"), _ex("d", "s2")]
    supabase_sessions = [{"session_id": "s1"}, {"session_id": "s2"}]
    ex_ids, session_ids = prune.prune_plan(notion, supabase_ex, supabase_sessions)
    assert ex_ids == ["c", "d"]
    assert session_ids == ["s2"]


def test_a_session_a_kept_exercise_points_to_is_never_named():
    # Notion moved exercise "a" to session s2; Supabase still files it under s1.
    notion = [_ex("a", "s2")]
    supabase_ex = [_ex("a", "s1")]
    supabase_sessions = [{"session_id": "s1"}, {"session_id": "s2"}]
    ex_ids, session_ids = prune.prune_plan(notion, supabase_ex, supabase_sessions)
    assert ex_ids == []
    assert session_ids == []


def test_an_id_that_could_change_the_filter_is_refused():
    notion = [_ex("a", "s1")]
    with pytest.raises(prune.PruneRefused):
        prune.prune_plan(notion, [_ex("a", "s1"), _ex("x),id.neq.(", "s1")],
                         [{"session_id": "s1"}])


def test_the_backup_goes_where_git_never_looks():
    gitignore = (_PATH.parent.parent / ".gitignore").read_text(encoding="utf-8")
    assert "Input_files/" in gitignore.splitlines()
    assert prune._BACKUP_DIR.parts[-2] == "Input_files"
