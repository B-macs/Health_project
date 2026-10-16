"""tier_decider.py — check the tier decider against the source lists, and print
its lists for the areas no source has ranked.

    python scripts/tier_decider.py validate      # agreement with the five lists
    python scripts/tier_decider.py calibrate     # re-run the cut-point search
    python scripts/tier_decider.py list back     # the decider's back list
    python scripts/tier_decider.py list chest    # the decider's chest list
    python scripts/tier_decider.py compare FILE  # a source list for a decided
                                                 # area against the decider

The method is in services/tier_decider.py and the ratings in
exercise_features.py. Reads only the markdown in docs/training/tier_lists/.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import exercise_features as ef  # noqa: E402
from services import tier_decider as td  # noqa: E402

LISTS_DIR = ROOT / "docs" / "training" / "tier_lists"


def recorded_pairs() -> dict[str, list[tuple[int, str]]]:
    """(score, source tier) for every row of each recorded list that has a
    readable tier."""
    out: dict[str, list[tuple[int, str]]] = {}
    for filename, ratings in ef.RECORDED.items():
        rows = td.parse_tier_table((LISTS_DIR / filename).read_text(encoding="utf-8"))
        pairs = []
        for number, _name, tier in rows:
            if tier is not None:
                pairs.append((td.score(ratings[number]), tier))
        out[filename] = pairs
    return out


def misses() -> list[tuple[str, int, str, str, str, int]]:
    out = []
    for filename, ratings in ef.RECORDED.items():
        rows = td.parse_tier_table((LISTS_DIR / filename).read_text(encoding="utf-8"))
        for number, name, tier in rows:
            if tier is None:
                continue
            got = td.decide(ratings[number])
            if got != tier:
                out.append((filename, number, name, tier, got, td.score(ratings[number])))
    return out


def _share(result: dict) -> str:
    return (f"{result['exact']}/{result['n']} exact ({result['exact_share']:.0%}), "
            f"{result['within_one']}/{result['n']} within one tier ({result['within_one_share']:.0%})")


def validate() -> None:
    lists = recorded_pairs()
    every = [p for pairs in lists.values() for p in pairs]
    print(f"Cut points (lowest score for D, C, B, A, S): {td.CUTS}")
    print("\nIn-sample (the ratings' author had read these lists):")
    for filename, pairs in sorted(lists.items()):
        print(f"  {filename:15s} {_share(td.agreement(pairs))}")
    print(f"  {'all':15s} {_share(td.agreement(every))}")
    base = td.most_common_tier_baseline(every)
    print(f"\nGuessing '{base['guess']}' for everything: {_share(base)}")
    lolo = td.leave_one_list_out(lists)
    print("\nLeave one list out (calibrated on the other four):")
    for name in sorted(k for k in lolo if k != "all"):
        print(f"  {name:15s} {_share(lolo[name])}")
    print(f"  {'all':15s} {_share(lolo['all'])}")
    print("\nMisses (source tier -> decider tier, score):")
    for filename, number, name, tier, got, value in misses():
        print(f"  {filename} #{number} {name}: {tier} -> {got} ({value})")


def list_area(area: str) -> None:
    print(f"| # | Exercise | Tier | Score | Why |")
    print(f"|---|---|---|---|---|")
    for i, (f, value, tier) in enumerate(td.ranked(ef.DECIDED[area]), start=1):
        print(f"| {i} | {f.name} | {tier} | {value} | {f.why} |")


def compare(path: str) -> None:
    """A source list pasted later for an area the decider ranked: match rows by
    name and print the agreement. Rows whose names do not match exactly are
    listed so they can be paired by hand."""
    rows = td.parse_tier_table(Path(path).read_text(encoding="utf-8"))
    decided = {f.name.lower(): f for area in ef.DECIDED.values() for f in area}
    pairs, unmatched = [], []
    for _number, name, tier in rows:
        f = decided.get(name.lower())
        if f is None or tier is None:
            unmatched.append(name)
            continue
        pairs.append((td.score(f), tier))
    print(_share(td.agreement(pairs)) if pairs else "No row matched a decided exercise by name.")
    for name in unmatched:
        print(f"  not matched: {name}")


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "validate":
        validate()
    elif argv[0] == "calibrate":
        every = [p for pairs in recorded_pairs().values() for p in pairs]
        print(td.calibrate(every))
    elif argv[0] == "list" and len(argv) == 2 and argv[1] in ef.DECIDED:
        list_area(argv[1])
    elif argv[0] == "compare" and len(argv) == 2:
        compare(argv[1])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
