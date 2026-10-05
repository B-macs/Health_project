"""A yoga or outdoor session is written ONCE, however many times its save runs.

2026-10-05: one Complete press on the 22-pose hip and spine flow wrote 51
sessions and 407 rows between 06:50 and 06:51 UTC, while the hosted app was
updating after a push. `_log_yoga_completion` minted a fresh session id on
every run, and runs that stopped partway left partial copies (1 to 19 poses).
The day read about 2,300 AU against a real 45. The data repair was
scripts/archive_duplicate_sessions.py (385 pages archived, one copy kept).

The fix reads the day back from Notion before writing, under one process-wide
lock: an earlier write of the same flow is continued under its own id with its
written poses skipped, a flow already fully logged writes nothing, and an
outdoor activity whose Garmin id is already in a note writes nothing. The
decisions are pure functions in services/sessions.py and are tested directly;
views/training.py is Streamlit and cannot be imported here, so its use of them
is pinned at the source, the way tests/test_session_save_resumes.py pins the
gym session's save.
"""

from __future__ import annotations

import ast
import pathlib

from services import sessions as sess
from services import yoga as yg

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_VIEW = (_ROOT / "views" / "training.py").read_text(encoding="utf-8")
_REPO = (_ROOT / "services" / "repository.py").read_text(encoding="utf-8")

FLOW = ["Down Dog", "Happy Baby", "Lying Twist (Left)", "Lying Twist (Right)"]


def _function_source(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f"{name} not found")


# ── the yoga decision ───────────────────────────────────────────────────────

def test_nothing_logged_yet_mints_a_new_session():
    assert sess.yoga_save_plan({}, FLOW) == (None, set())


def test_a_partial_write_of_this_flow_is_continued_under_its_own_id():
    existing = {"2026-10-05-aaaa": {"movements": ["Down Dog", "Happy Baby"], "notes": ["", ""]}}
    assert sess.yoga_save_plan(existing, FLOW) == ("2026-10-05-aaaa", {"Down Dog", "Happy Baby"})


def test_a_fully_logged_flow_comes_back_complete_so_nothing_is_written():
    existing = {"s1": {"movements": list(FLOW), "notes": [""] * 4}}
    sid, done = sess.yoga_save_plan(existing, FLOW)
    assert sid == "s1" and done == set(FLOW)


def test_a_different_flow_is_never_continued():
    existing = {"s1": {"movements": ["Down Dog", "Thread the Needle"], "notes": ["", ""]}}
    assert sess.yoga_save_plan(existing, FLOW) == (None, set())


def test_the_most_complete_copy_wins_the_2026_10_05_shape():
    """Many partial copies and several complete ones: continue a complete one,
    which means write nothing."""
    existing = {
        "p1": {"movements": ["Happy Baby"], "notes": [""]},
        "p2": {"movements": ["Down Dog", "Happy Baby", "Lying Twist (Left)"], "notes": [""] * 3},
        "c1": {"movements": list(FLOW), "notes": [""] * 4},
        "c2": {"movements": list(FLOW), "notes": [""] * 4},
    }
    sid, done = sess.yoga_save_plan(existing, FLOW)
    assert sid in {"c1", "c2"} and done == set(FLOW)


def test_every_yoga_flow_names_each_pose_once():
    """The saver keys on pose NAMES, so a flow that repeated a pose would log
    it once. Author a repeat under its own name (e.g. a "(2)" suffix)."""
    for flow in yg.YOGA_LIBRARY:
        names = [p.name for p in flow.poses]
        assert len(names) == len(set(names)), flow.slug


# ── the outdoor decision ────────────────────────────────────────────────────

def test_an_outdoor_activity_already_in_a_note_is_logged():
    existing = {"s": {"movements": ["Hiking"],
                      "notes": ["Garmin import: Walk [walking], started 08:00, activity 1234"]}}
    assert sess.outdoor_activity_logged(existing, 1234)
    assert sess.outdoor_activity_logged(existing, "1234")


def test_an_activity_id_is_matched_whole_never_inside_a_longer_one():
    existing = {"s": {"movements": ["Hiking"], "notes": ["... activity 1234"]}}
    assert not sess.outdoor_activity_logged(existing, 123)
    assert not sess.outdoor_activity_logged(existing, 12345)


def test_a_missing_activity_id_is_never_treated_as_logged():
    existing = {"s": {"movements": ["Hiking"], "notes": ["activity None"]}}
    assert not sess.outdoor_activity_logged(existing, None)
    assert not sess.outdoor_activity_logged(existing, "")


# ── the savers use them, under the lock, before writing ─────────────────────

def test_the_yoga_saver_reads_the_day_back_under_the_lock_before_writing():
    body = _function_source(_VIEW, "_log_yoga_completion")
    lock = body.index("with _SUPPLEMENTARY_SAVE_LOCK:")
    read = body.index('r.get_supplementary_sessions_live(date.today(), "Yoga")')
    plan = body.index("sess.yoga_save_plan(")
    write = body.index("_save_yoga_pose(")
    assert lock < plan < write and lock < read < write
    assert 'session_info["session_id"] = existing_id' in body
    assert "if pose.name in written:" in body and "continue" in body
    assert "return False" in body


def test_the_outdoor_saver_checks_the_activity_under_the_lock_before_writing():
    body = _function_source(_VIEW, "_log_outdoor_activity")
    lock = body.index("with _SUPPLEMENTARY_SAVE_LOCK:")
    check = body.index("sess.outdoor_activity_logged(")
    write = body.index("_write_outdoor_activity(")
    assert lock < check < write
    assert "return False" in body


def test_the_lock_is_one_process_wide_lock():
    assert "_SUPPLEMENTARY_SAVE_LOCK = threading.Lock()" in _VIEW


def test_no_yoga_or_outdoor_write_bypasses_the_savers():
    """The only Yoga/Outdoor save_training_exercise calls are the two row
    writers, each called only from its guarded saver."""
    for writer, saver in (("_save_yoga_pose", "_log_yoga_completion"),
                          ("_write_outdoor_activity", "_log_outdoor_activity")):
        callers = [node.name for node in ast.walk(ast.parse(_VIEW))
                   if isinstance(node, ast.FunctionDef)
                   and f"{writer}(" in (ast.get_source_segment(_VIEW, node) or "")
                   and node.name != writer]
        assert callers == [saver], (writer, callers)
    for movement_type in ('movement_type="Yoga"', 'movement_type="Outdoor"'):
        holders = [node.name for node in ast.walk(ast.parse(_VIEW))
                   if isinstance(node, ast.FunctionDef)
                   and movement_type in (ast.get_source_segment(_VIEW, node) or "")]
        assert holders and set(holders) <= {"_save_yoga_pose", "_write_outdoor_activity"}, holders


def test_the_day_is_read_from_notion_itself_not_the_local_copy():
    body = _function_source(_REPO, "get_supplementary_sessions_live")
    assert "notion.query_database(" in body
    assert body.index("if self.offline:") < body.index("notion.query_database(")
