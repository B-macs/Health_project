"""Per-exercise RPE comes from that exercise's own heart rate, not from the
session slider.

The defect this closes, found in a real session on 2026-08-14: every exercise
carried RPE 8 because the session did — a 90-second pressure release and a set
of Romanian deadlifts rated identically. It was not merely cosmetic.
services/strength.py takes `exercise_rpe` first and falls back to `session_rpe`
only when it is None, so the fallback was never reached and every 1RM estimate
was computed at the session figure.

The session slider is untouched. It is the athlete's own answer, it feeds
session_au and through it Strain and ACWR, and key rule 2b keeps anything
heart-rate-derived away from that.
"""

from __future__ import annotations

from datetime import date

import pytest

from services import hr_load, strength


def test_the_session_slider_is_no_longer_copied_onto_every_exercise():
    """Source check: the save call passes rpe=None, not rpe=session_rpe."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "views" / "training.py").read_text(encoding="utf-8")
    # Indented so it cannot match the legitimate `session_rpe=session_rpe,`
    # keyword on the same call.
    assert "\n            rpe=session_rpe," not in src, (
        "the session RPE is being copied onto every exercise again"
    )
    assert "\n            rpe=None," in src


def test_a_null_exercise_rpe_falls_back_to_the_session_figure():
    """Nulling must not change any number downstream — it removes a claim, not
    data. strength.py's fallback is what makes that true."""
    rows = [{"movement_name": "Goblet Squat", "session_date": "2026-08-14",
             "exercise_rpe": None, "session_rpe": 8,
             "sets": [{"reps": 10, "weight": 20.0}]}]
    out = list(strength.qualifying_rows(rows, date(2026, 8, 15)))
    assert len(out) == 1
    assert out[0][3] == 8


def test_an_assigned_exercise_rpe_wins_over_the_session_figure():
    rows = [{"movement_name": "Goblet Squat", "session_date": "2026-08-14",
             "exercise_rpe": 5.2, "session_rpe": 8,
             "sets": [{"reps": 10, "weight": 20.0}]}]
    assert list(strength.qualifying_rows(rows, date(2026, 8, 15)))[0][3] == 5.2


def test_heart_rate_separates_a_release_from_a_working_set():
    """The whole point. Real numbers from the 2026-08-10 session: the pressure
    release sat at 74.7 bpm mean and the Pallof hold at 105.5, and the flat
    session value erased the difference."""
    rest, hr_max = 52.0, 185.0
    release = hr_load.exercise_hr_rpe([72, 74, 76, 77], rest, hr_max)
    pallof = hr_load.exercise_hr_rpe([100, 105, 110, 137], rest, hr_max)
    assert release["rpe"] < 3.0
    assert pallof["rpe"] > release["rpe"] + 2.0


class _FakeNotion:
    def __init__(self, pages):
        self.pages, self.updates = pages, []


def _repo_with(pages, monkeypatch):
    """A Repository with just enough wired to exercise the write-back."""
    from services import repository as repo_mod

    r = object.__new__(repo_mod.Repository)
    # _nc is a lazily-built property with no setter — override it on the class.
    monkeypatch.setattr(repo_mod.Repository, "_nc", property(lambda self: object()))
    r.config = type("C", (), {"notion_db_training": "db"})()
    calls = []
    monkeypatch.setattr(r, "_query", lambda *a, **k: pages, raising=False)
    monkeypatch.setattr(repo_mod.notion, "update_page",
                        lambda c, pid, properties: calls.append((pid, properties)))
    monkeypatch.setattr(r, "mirror_notion_write", lambda *a, **k: None, raising=False)
    return r, calls


def _page(pid, name):
    return {"id": pid, "properties": {"Movement": {"title": [{"plain_text": name}]}}}


def test_each_exercise_gets_its_own_number(monkeypatch):
    pages = [_page("p1", "Upper Glute / TFL Self-Release"), _page("p2", "Pallof Press Hold (Doorframe)")]
    r, calls = _repo_with(pages, monkeypatch)
    n = r.reassign_exercise_rpe_from_hr(date(2026, 8, 10), {
        "Upper Glute / TFL Self-Release": {"hr_rpe": 1.4, "covered": True},
        "Pallof Press Hold (Doorframe)": {"hr_rpe": 5.2, "covered": True},
    })
    assert n == 2
    assert {pid: props["Exercise RPE"]["number"] for pid, props in calls} == {"p1": 1.4, "p2": 5.2}


def test_an_uncovered_exercise_keeps_its_null(monkeypatch):
    """A paused watch means no samples. Null is 'not measured'; overwriting it
    with a guess is the failure this whole change undoes."""
    r, calls = _repo_with([_page("p1", "Goblet Squat")], monkeypatch)
    assert r.reassign_exercise_rpe_from_hr(date(2026, 8, 10), {
        "Goblet Squat": {"hr_rpe": None, "covered": False}}) == 0
    assert calls == []


def test_nothing_usable_touches_nothing(monkeypatch):
    r, calls = _repo_with([_page("p1", "Goblet Squat")], monkeypatch)
    assert r.reassign_exercise_rpe_from_hr(date(2026, 8, 10), {}) == 0
    assert calls == []


def test_the_write_back_uses_patch_not_upsert():
    """A partial upsert would insert an orphan training_exercises row carrying
    an RPE and nothing else — no session_id, no movement, no sets."""
    import inspect
    from services import repository as repo_mod
    src = inspect.getsource(repo_mod.Repository.reassign_exercise_rpe_from_hr)
    assert "supabase_store.PATCH" in src
    assert "supabase_store.UPSERT" not in src


def test_a_needs_choice_result_is_not_saved_as_a_measurement():
    """It carries candidates, not a load summary, and has no 'date' —
    save_session_hr would raise KeyError building its row."""
    import inspect
    from services import repository as repo_mod
    src = inspect.getsource(repo_mod.Repository.sync_session_hr_for_date)
    assert 'summary.get("needs_choice")' in src
    assert src.index('needs_choice') < src.index("self.save_session_hr(summary)")
