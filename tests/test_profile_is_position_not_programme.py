"""
THE PROFILE IS HIS POSITION, NOT HIS PROGRAMME (athlete, 2026-09-18).

Asked whether the pre-session release protocol and the retired stage exit
criteria belonged in his clinical profile: "Both come out they're not my
profile. Move it to somewhere more relevant like previous training history."

They moved verbatim to training_history.py. This pins the split in both
directions — the profile cannot grow a prescription back, and the record
cannot quietly lose what was moved into it.

Why it matters beyond tidiness: patient_profile.py is imported by the app
(services/bioage.py reads the imbalances for the screen), so anything in it is
one render away from being shown as though it were current. The block that
runs today is training_plan.py, and it authors its own release block — the
profile's copy was a second statement of a live thing, free to drift from it.
"""
from __future__ import annotations

import re

import patient_profile
import training_history

#: Moved out on 2026-09-18. Keys, not prose, so this fails loudly on a revival.
MOVED = ("pre_session_release", "stage_1_exit_criteria",
         "stage_2_exit_criteria", "stage_2b_exit_criteria")

#: What a prescription looks like at the top level of the profile: a named
#: protocol, a gate, or a list of exercises to perform.
_PROGRAMME_KEY = re.compile(r"protocol|exit_criteria|prescription|release|"
                            r"exercises|session_plan|programme|program",
                            re.IGNORECASE)


def test_the_moved_sections_are_in_the_history():
    for key in MOVED:
        assert key in training_history.HISTORY, key


def test_the_profile_no_longer_holds_them():
    for key in MOVED:
        assert key not in patient_profile.PROFILE, key


def test_the_profile_grows_no_new_prescription_at_its_top_level():
    offenders = [k for k in patient_profile.PROFILE if _PROGRAMME_KEY.search(k)]
    assert not offenders, (
        f"{offenders} reads as a programme, not a position — author it in "
        f"training_plan.py, or record it in training_history.py")


def test_the_profile_still_holds_his_position():
    """The other direction: this must not become a way to empty the profile."""
    for key in ("mri", "hypermobility", "biomechanical_findings", "imbalances",
                "symptom_log", "stage_transitions", "current_stage"):
        assert key in patient_profile.PROFILE, key


def test_the_history_is_read_by_nothing():
    """A rule that still binds belongs in services/rules.py or in the block that
    runs it. If something starts importing this, it is live again and the
    profile split has quietly reversed."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    live = [p for folder in ("services", "views", "scripts") for p in (root / folder).rglob("*.py")]
    live += [root / "app.py", root / "today.py", root / "repo.py", root / "training_plan.py",
             root / "patient_profile.py"]
    importers = []
    for path in live:
        if not path.exists():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import) and any(a.name == "training_history" for a in node.names):
                importers.append(path.name)
            if isinstance(node, ast.ImportFrom) and node.module == "training_history":
                importers.append(path.name)
    assert not importers, importers
