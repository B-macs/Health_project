"""The tier decider — a deterministic stand-in for a source's tier list.

The athlete, 2026-10-16: "I want you to take the deterministic decider for
tiers and use the same script to create a tier list for back and chest, I can
copy in later videos to see if you're correct but go for that for now."

WHAT IT IS. The recorded tier lists (docs/training/tier_lists/) all rank on the
same few things, named outright in four of them: tension where the muscle is
longest, a way to add load, the target muscle doing the work, and a joint that
does not complain. Each exercise gets five ratings of 0, 1 or 2, written from
its mechanics (exercise_features.py holds them, with the rule for each value):

    stretch  tension where the target muscle is longest
    target   the target muscle, not something else, ends the set
    stable   support or bracing, so a set can go close to failure
    load     load added in small steps over a wide range
    comfort  a smooth resistance curve and a quick, joint-friendly set-up

and one flag, ``not_growth``: a combination move, a jump or swing, an unstable
surface, or cardio.

    score = 3 x stretch + target + stable + load + comfort - 4 x not_growth

so the score runs from -4 to 14. Stretch carries three times the weight of the
others because it is the first criterion of every list that states criteria.

The tier is the score against five cut points (``CUTS``). The cut points are
CALIBRATED, not chosen: every possible set is tried against the source tiers
of the recorded lists, and the set that reproduces the most of them wins (ties:
the smallest total distance in tiers, then the lowest cut points). The search
is deterministic, and tests/test_tier_decider.py pins its answer.

WHAT IT IS NOT. A trial result, or a source. Its agreement with the recorded
lists is IN-SAMPLE — the ratings were written by someone who had read those
lists — so the honest estimate of its accuracy on a list it has never seen is
the leave-one-list-out figure (calibrate on four lists, test on the fifth). The
real test is the next video the athlete pastes for an area the decider ranked.

No I/O here: the callers read the markdown and pass its text in.
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

#: Worst to best. A tier's index is its rank.
TIERS: tuple[str, ...] = ("F", "D", "C", "B", "A", "S")

WEIGHTS: dict[str, int] = {"stretch": 3, "target": 1, "stable": 1, "load": 1, "comfort": 1}
NOT_GROWTH_PENALTY = 4
SCORE_MIN = -NOT_GROWTH_PENALTY
SCORE_MAX = 2 * sum(WEIGHTS.values())

#: The lowest score that reaches D, C, B, A and S. Found by ``calibrate`` over
#: the five recorded lists on 2026-10-16; a test re-runs the search and fails if
#: the answer moves, so a change to a rating cannot shift the tiers unseen.
CUTS: tuple[int, int, int, int, int] = (3, 4, 6, 8, 13)


@dataclass(frozen=True)
class Features:
    """What the decider knows about one exercise. Every rating is 0, 1 or 2."""
    name: str
    stretch: int
    target: int
    stable: int
    load: int
    comfort: int
    not_growth: bool = False
    why: str = ""

    def __post_init__(self):
        for field in WEIGHTS:
            value = getattr(self, field)
            if value not in (0, 1, 2):
                raise ValueError(f"{self.name}: {field} must be 0, 1 or 2, got {value!r}")


def score(f: Features) -> int:
    total = sum(weight * getattr(f, field) for field, weight in WEIGHTS.items())
    return total - (NOT_GROWTH_PENALTY if f.not_growth else 0)


def tier_for(value: int, cuts: tuple[int, ...] = CUTS) -> str:
    """The tier a score reaches: F below cuts[0], S at or above cuts[4]."""
    reached = sum(1 for cut in cuts if value >= cut)
    return TIERS[reached]


def decide(f: Features, cuts: tuple[int, ...] = CUTS) -> str:
    return tier_for(score(f), cuts)


def ranked(features: list[Features], cuts: tuple[int, ...] = CUTS
           ) -> list[tuple[Features, int, str]]:
    """Best first: by score, then by name, so a tie always breaks the same way."""
    rows = [(f, score(f), decide(f, cuts)) for f in features]
    return sorted(rows, key=lambda r: (-r[1], r[0].name.lower()))


# ── reading a source's list ──────────────────────────────────────────────────

_TIER_TOKEN = re.compile(r"(?<![A-Za-z])([SABCDF])(?:\+)?(?![A-Za-z])")


def normalise_tier(text: str) -> str | None:
    """'**S+**' -> 'S', 'high A' -> 'A', 'A; **S** sideways' -> 'A' (the
    first tier named, the exercise done the usual way). None when no tier
    letter stands alone — an unreadable tier is not a tier."""
    match = _TIER_TOKEN.search((text or "").replace("*", ""))
    return match.group(1) if match else None


def parse_tier_table(markdown: str) -> list[tuple[int, str, str | None]]:
    """(row number, exercise, tier) for each row of the first table under
    '## The full list'. Columns are found by their header, because the files
    add different columns (Area, Head, Region emphasis)."""
    _, _, section = markdown.partition("## The full list")
    lines = [line for line in section.splitlines() if line.startswith("|")]
    if len(lines) < 3:
        return []
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    ex_col, tier_col = header.index("Exercise"), header.index("Tier")
    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or not cells[0].isdigit():
            break
        rows.append((int(cells[0]), cells[ex_col], normalise_tier(cells[tier_col])))
    return rows


# ── calibration and agreement ────────────────────────────────────────────────

def _distance(a: str, b: str) -> int:
    return abs(TIERS.index(a) - TIERS.index(b))


def agreement(pairs: list[tuple[int, str]], cuts: tuple[int, ...] = CUTS) -> dict:
    """pairs: (score, source tier). Exact and within-one-tier counts."""
    n = len(pairs)
    exact = sum(1 for s, t in pairs if tier_for(s, cuts) == t)
    near = sum(1 for s, t in pairs if _distance(tier_for(s, cuts), t) <= 1)
    return {"n": n, "exact": exact, "within_one": near,
            "exact_share": exact / n if n else 0.0,
            "within_one_share": near / n if n else 0.0}


def calibrate(pairs: list[tuple[int, str]]) -> tuple[int, int, int, int, int]:
    """Every increasing set of five cut points in the score range; the one
    with the most exact matches, then the smallest total distance, then the
    lowest points. Deterministic."""
    best_key, best_cuts = None, None
    for cuts in itertools.combinations(range(SCORE_MIN, SCORE_MAX + 2), 5):
        exact = distance = 0
        for s, t in pairs:
            got = tier_for(s, cuts)
            if got == t:
                exact += 1
            distance += _distance(got, t)
        key = (-exact, distance, cuts)
        if best_key is None or key < best_key:
            best_key, best_cuts = key, cuts
    return best_cuts


def leave_one_list_out(lists: dict[str, list[tuple[int, str]]]) -> dict:
    """Calibrate on every list but one, score the one left out. The honest
    estimate of how the decider does on a list it has not seen."""
    out, exact, near, n = {}, 0, 0, 0
    for held_out, pairs in sorted(lists.items()):
        rest = [p for name, ps in lists.items() if name != held_out for p in ps]
        result = agreement(pairs, calibrate(rest))
        out[held_out] = result
        exact, near, n = exact + result["exact"], near + result["within_one"], n + result["n"]
    out["all"] = {"n": n, "exact": exact, "within_one": near,
                  "exact_share": exact / n if n else 0.0,
                  "within_one_share": near / n if n else 0.0}
    return out


def most_common_tier_baseline(pairs: list[tuple[int, str]]) -> dict:
    """What guessing the most common tier for every exercise would score —
    the bar the decider has to clear to mean anything."""
    counts = {t: sum(1 for _, s in pairs if s == t) for t in TIERS}
    guess = max(TIERS, key=lambda t: (counts[t], TIERS.index(t)))
    n = len(pairs)
    exact = counts[guess]
    near = sum(1 for _, t in pairs if _distance(guess, t) <= 1)
    return {"guess": guess, "n": n, "exact": exact, "within_one": near,
            "exact_share": exact / n if n else 0.0,
            "within_one_share": near / n if n else 0.0}
