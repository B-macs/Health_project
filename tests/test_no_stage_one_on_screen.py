"""
STAGE 1 IS OVER AND MUST NOT BE ON SCREEN (athlete, 2026-09-18: "Stage 1
information should never be displayed to the user, we have moved on from it").

He was reading the Autoregulation screen, which on a green day prints the
engine directive's own sentence — and it still said "Apply standard progressive
overload: +2.5 kg (Stage 2+) or +1 rep per set (Stage 1)". The check-in screen
captioned every single day "— Stage 1: Rehab" from a hard-coded string, two
blocks after Stage 1 ended in July.

WHAT THIS SCANS: string LITERALS in the screen layer and in the plain-language
copy it prints. Comments and docstrings are not scanned — the history of a
decision belongs in the file (Key Rule 20's split between what is authored and
what is rendered), and this repo's own record of the Stage 1 over-count lives
in those comments.

WHAT IT DELIBERATELY DOES NOT SCAN: entries KEYED by stage or phase number
(engine.STAGE_LABELS, sessions.PHASE_META). Those render only for the stage
they belong to, so they are correct whenever they appear; a catalogue is not
copy. What is banned is a stage written into a sentence every day, which is
wrong the day the stage changes and was wrong for two months here. The
directive sentence is covered by the two behaviour tests below instead.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: The screen layer, plus the two service modules that author what it prints.
_FILES = sorted((ROOT / "views").glob("*.py")) + [
    ROOT / "app.py",
    ROOT / "today.py",
    ROOT / "services" / "insights.py",
]

_STAGE_ONE = re.compile(r"stage\s*1|stage[- ]one", re.IGNORECASE)


def _green_directive() -> dict:
    from services import engine

    return engine.volume_recommendation(
        {"overall": "green", "status": "ok", "volume_multiplier_from_traffic": 1.0},
        {"status": "insufficient_data", "acwr": None},
        stage=2, injury_weight_val=0.0,
    )


def _string_literals(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value not in docstrings:
                yield node.lineno, node.value


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_no_stage_one_in_any_string_the_screen_can_print(path):
    offenders = [(line, text[:80]) for line, text in _string_literals(path)
                 if _STAGE_ONE.search(text)]
    assert not offenders, f"{path.name} still writes Stage 1 into copy: {offenders}"


def test_the_green_day_sentence_says_what_the_app_actually_does():
    """The one the athlete quoted. It promised a +2.5 kg step for a good day,
    which no longer happens: a step is earned by two sessions at the rep target
    (Key Rule 23)."""
    action = _green_directive()["action"]
    assert "+2.5 kg" not in action
    assert "two sessions in a row" in action


def test_the_green_day_sentence_is_what_the_autoregulation_screen_prints():
    """services.insights.directive_copy passes a green day's action through
    verbatim — which is how the stale sentence reached him."""
    from services import insights

    rec = _green_directive()
    _label, detail = insights.directive_copy(rec)
    assert detail == rec["action"]
