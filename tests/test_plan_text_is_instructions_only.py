"""What reaches the training screen is an instruction, not a record.

KEY RULE 20: the why is not shown. `biomechanical_focus`, `progression` and
`regression` are still authored on every exercise and still required — they are
the programme's reasoning and the authored conditions for changing load — but
no panel renders them. That rule has a second half which had NOT held:

    "do not migrate their content into `mechanics`; mechanics says what to do
     and nothing else."

Found by audit 2026-08-24, on the athlete's question. The live Stage 2B block's
Anterior Hip Pressure Release opened with THREE SENTENCES of repo bookkeeping
before the first instruction -- a changelog stamp ("UNGATED 2026-08-17
(athlete)"), an app-defect note ("the app lost all but the last"), third person
about him ("he has captured it"), and "the null is the finding", which is
filing vocabulary. He reads that face down on the floor with a ball under his
hip. Stage 1 and Stage 2A carried a milder form -- "(finding #4)",
"(session note, 2026-07-08)" -- references he cannot resolve mid-session.

KEY RULE 19 is the other half of it: the words these files use for their own
bookkeeping belong in the files.

⚠ SCOPE. This checks ONLY the fields a view actually renders. Citations and
dates in `biomechanical_focus` are correct and stay -- that field is the
reasoning, it is never shown, and stripping it would destroy the provenance
this test exists to keep OFF the screen rather than delete.
"""

import re

import pytest

import training_plan as tp

#: The fields views/training.py puts in front of the athlete mid-session.
#: `mechanics` at views/training.py:3725, `warning` at :3748.
RENDERED_FIELDS = ("mechanics", "warning")

#: Repo bookkeeping. Each of these was ACTUALLY FOUND on screen on 2026-08-24
#: except where marked, so this is a list of real leaks, not hypotheticals.
_BOOKKEEPING = (
    r"UNGATED",                     # changelog stamp
    r"TOMBSTONE",
    r"REVERT CONDITION",
    r"finding #\d",                 # unresolvable mid-session
    r"the null is the finding",
    r"\(athlete\)",                 # who said it, not what to do
    r"\(session note[^)]*\)",
    r"\bkey rule \d",
    r"CLAUDE\.md",
    r"advisory mode",
    r"the gate\b",
    r"\bper the [\d-]{10} finding\b",
    r"the app (?:lost|dropped|failed)",   # an app defect is not an instruction
    r"\b(?:20\d\d-\d\d-\d\d)\b",          # a bare date is provenance
)
_BOOK_RE = re.compile("|".join(_BOOKKEEPING), re.I)

#: Third person about the athlete. These files are written ABOUT him for the
#: author's benefit and TO him on screen; the two must not be confused.
_THIRD_PERSON = re.compile(
    r"\bhe (?:has|had|is|was|reports|reported|captured|said|felt|found)\b", re.I)


def _plans():
    return [(n, getattr(tp, n)) for n in dir(tp)
            if n.startswith("PLAN") and isinstance(getattr(tp, n), dict)]


def _rendered_strings():
    """(plan, day, exercise, field, text) for everything a view shows."""
    for plan_name, plan in _plans():
        for day, content in plan.items():
            for ex in (content.get("exercises") or []):
                for field in RENDERED_FIELDS:
                    text = ex.get(field)
                    if text:
                        yield plan_name, day, ex.get("name", "?"), field, text


def test_there_is_something_to_check():
    """A guard that silently checks nothing is worse than no guard."""
    rows = list(_rendered_strings())
    assert len(rows) > 400, f"only {len(rows)} rendered strings found"
    assert {r[0] for r in rows} >= {"PLAN", "PLAN_STAGE2", "PLAN_STAGE2B"}


def test_no_repo_bookkeeping_reaches_the_screen():
    bad = []
    for plan, day, name, field, text in _rendered_strings():
        for m in _BOOK_RE.finditer(text):
            bad.append(f"{plan} day {day} · {name} [{field}]: {m.group(0)!r}")
    assert not bad, (
        "Repo bookkeeping is on the training screen. It belongs in a comment or "
        "in biomechanical_focus, which is never rendered:\n  " + "\n  ".join(bad))


def test_the_athlete_is_not_written_about_in_the_third_person():
    bad = []
    for plan, day, name, field, text in _rendered_strings():
        for m in _THIRD_PERSON.finditer(text):
            bad.append(f"{plan} day {day} · {name} [{field}]: {m.group(0)!r}")
    assert not bad, (
        "The training screen speaks TO him, not about him:\n  " + "\n  ".join(bad))


# DELETED 2026-08-24: test_an_instruction_starts_with_the_instruction.
# It tried to assert that `mechanics` opens on something actionable, by looking
# for a verb from a list. It flagged ten real instructions on its first run --
# "Cable at upper-chest height.", "Rear foot elevated on a bench, bodyweight.",
# "Rate your pain (0-10) in each of these 5 positions." -- because the list did
# not happen to contain those words. A check that needs a forever-growing
# allowlist produces false failures and teaches the next person to weaken it.
# The bookkeeping and third-person tests above catch the actual leak (the Stage
# 2B release opened on provenance, which they flag on the provenance, not on
# the grammar).

def test_the_reasoning_fields_keep_their_provenance():
    """⚠ THE OTHER DIRECTION. This test must not become a reason to strip
    citations from the fields that SHOULD carry them. biomechanical_focus is
    the programme's reasoning, is never rendered, and is exactly where a
    finding reference belongs."""
    cited = 0
    for _, plan in _plans():
        for _, content in plan.items():
            for ex in (content.get("exercises") or []):
                if _BOOK_RE.search(ex.get("biomechanical_focus") or ""):
                    cited += 1
    assert cited > 0, (
        "no biomechanical_focus cites a finding any more — provenance was "
        "stripped from the field that is supposed to hold it")


@pytest.mark.parametrize("field", RENDERED_FIELDS)
def test_every_guarded_field_is_one_the_view_really_shows(field):
    """If a view starts rendering a fourth field, this list has to grow with
    it or the guard quietly stops covering the screen."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent
           / "views" / "training.py").read_text(encoding="utf-8")
    assert f"'{field}'" in src or f'"{field}"' in src


def test_the_why_fields_are_still_not_rendered():
    """Key rule 20's first half, kept honest alongside the second."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent
           / "views" / "training.py").read_text(encoding="utf-8")
    # Field ACCESS, not the word. "progression" appears in prose ("Stage 1 -> 2
    # progression criteria") and in comments about the double-progression
    # clamp; neither renders an authored why.
    for why in ("biomechanical_focus", "progression", "regression"):
        access = re.findall(rf"""(?:ex|nex|exercise)(?:\[|\.get\()\s*["']{why}["']""", src)
        assert not access, f"{why} is being read from an exercise again: {access[:2]}"
