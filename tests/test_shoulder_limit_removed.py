"""The right shoulder's 90-degree limit stays removed, wording and all.

The athlete, 2026-10-16: "remove it, I don't have any problems with this and
have been doing shoulder presses for years without issue" — then, "Delete the
wording from there too". The limit ("never load the arm turned out at 90
degrees to the side") came from a general precaution in the Cluster D
documents; no surgeon, physiotherapist or test of his shoulder ever set it
(docs/training/goal_system.md, goal B). Its wording had spread into the plan,
the safety rules and the yoga notes, and a limit that survives as text gets
re-derived as a rule — which is how it reached the 2026-10-15 exercise picks.

What these tests do NOT forbid: the word "apprehension" on its own. It is the
stop sign on the hang ladder (the feeling that the shoulder may slip), and that
feeling is also his condition for bringing the limit back.
"""
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]

#: The modules whose text reaches a plan, a safety verdict or a screen.
_SOURCES = (
    "training_plan.py",
    "services/rules.py",
    "services/yoga.py",
    "services/accessory.py",
    "patient_profile.py",
    "training_history.py",
)

#: The limit's own wording, lower-cased. Each phrase is specific to the
#: shoulder limit, so none can match a hip or a knee instruction.
_REMOVED_PHRASES = (
    "apprehension position",
    "apprehension-adjacent",
    "degrees of abduction",
    "° abduction",
    "° of abduction",
    "turned outward",
    "arm out at 90",
)


@pytest.mark.parametrize("source", _SOURCES)
def test_the_removed_limit_is_not_written_back(source):
    text = (_ROOT / source).read_text(encoding="utf-8").lower()
    found = [p for p in _REMOVED_PHRASES if p in text]
    assert found == [], f"{source} carries the removed shoulder limit again: {found}"


def test_the_phrases_would_catch_the_old_wording():
    """Guard against a vacuous scan: the old warning, word for word, must trip
    at least one phrase."""
    old = ("Never press from a position with the arm out at 90 degrees and "
           "turned outward — that is the position the right shoulder's repair "
           "exists to protect.").lower()
    assert any(p in old for p in _REMOVED_PHRASES)


def test_the_hang_ladder_keeps_its_stop_sign():
    """Removing the limit's wording must not take the feeling-based stop sign
    with it: the hang ladder still stops on apprehension or instability."""
    import training_plan as tp
    for ex in tp.ACCESSORY_HANG_LADDER:
        warning = (ex.get("warning") or "").lower()
        assert "apprehension" in warning or "instability" in warning, ex["name"]
