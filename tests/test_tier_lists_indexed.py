"""Every exercise tier-list file is indexed and complete, so none sits unread.

The athlete, 2026-10-15: "I dont want to have seperate md files that are just
ignored when creating the plan." docs/training/tier_lists/ holds ONE file per
body area, each with the area's ranked list (or the line "No ranked list yet")
and the unranked advice from videos that rank nothing. Step 5 of the slot
procedure reads the file of every area from the index in README.md, so a file
missing from the index would never be read — which is what these tests stop.
"""
import re
from pathlib import Path

_DIR = Path(__file__).resolve().parents[1] / "docs" / "training" / "tier_lists"
_LINK = re.compile(r"\]\(([\w-]+\.md)\)")


def _area_files() -> set[str]:
    return {p.name for p in _DIR.glob("*.md") if p.name != "README.md"}


def _indexed() -> set[str]:
    return set(_LINK.findall((_DIR / "README.md").read_text(encoding="utf-8")))


def test_there_are_area_files_to_check():
    assert _area_files(), "the tier-list folder is empty — the tests would pass vacuously"


def test_every_area_file_is_in_the_index():
    missing = sorted(_area_files() - _indexed())
    assert missing == [], f"not in tier_lists/README.md, so step 5 never reads them: {missing}"


def test_the_index_names_only_files_that_exist():
    ghosts = sorted(_indexed() - _area_files())
    assert ghosts == [], f"the index names files that do not exist: {ghosts}"


def test_every_area_file_has_both_parts():
    for name in sorted(_area_files()):
        text = (_DIR / name).read_text(encoding="utf-8")
        assert "## Unranked source advice" in text, f"{name} has no unranked-advice part"
        assert "## The full list" in text or "No ranked list yet" in text, (
            f"{name} neither holds a ranked list nor says it has none")
