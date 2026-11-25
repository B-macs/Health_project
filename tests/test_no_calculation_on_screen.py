"""No screen text shows a calculation (the owner, 2026-11-25: *"Calculations are never
show to the user"*, of the Strain screen's "How the carried strain adds up" list).

A screen shows the figure and what it means, never the sum, the formula or the
shares that make it. Until 2026-11-25 four strings did: the carried strain's
rows ("16.0 × 1/512 = 0.0"), the outdoor import's "48 min × effort 4 = load 192",
the one-rep max formula on the Strength page, and the Engine Data screen's
"reps × weight" and "session RPE × duration".

A set written as "3 × 10" or "40 kg × 12" is a prescription or a set, not a
calculation, so a "×" between two numbers stays allowed, and so does a named figure
such as a correlation's "r = 0.41". A "×" before a word or a bracket, an "=" after a
value, and "÷" are calculations."""

from __future__ import annotations

import re

from scripts.rebuild_gate import STRINGS_TS, ts_string_literals

#: What a calculation looks like in screen text, once each ${...} is a number.
_CALCULATION = re.compile(r"[0-9)] = |÷|×\s*[A-Za-z(]")


def _as_shown(literal: str) -> str:
    """A template literal with each ${...} read as a number, as the screen fills it."""
    previous = None
    while previous != literal:
        previous, literal = literal, re.sub(r"\$\{[^{}]*\}", "0", literal)
    return literal


def calculation_hits(literals: list[str]) -> list[str]:
    return [f"a calculation in {text[:60]!r}" for text in literals
            if _CALCULATION.search(_as_shown(text))]


def test_no_screen_string_shows_a_calculation():
    literals = ts_string_literals(STRINGS_TS.read_text(encoding="utf-8"))
    assert literals, "the strings file was read"
    assert calculation_hits(literals) == []


def test_the_check_finds_the_strings_it_was_written_for():
    found = calculation_hits([
        "${strain} ${share} = ${carried}",
        "${minutes} min × effort ${rpe} = load ${au}",
        "weight × (1 + (reps + 1) ÷ 30)",
        "Total kg moved (reps × weight) per week",
    ])
    assert len(found) == 4


def test_a_set_or_a_prescription_is_not_a_calculation():
    assert calculation_hits(["${sets} × ${reps}", "${sets} × ${seconds} s",
                             "${kg} kg × ${reps} on ${date}", "lag ${lag} d · r = ${r}"]) == []
