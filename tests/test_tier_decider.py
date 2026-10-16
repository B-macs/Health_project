"""The tier decider is deterministic, calibrated, checked, and its lists match.

The athlete, 2026-10-16, asked for a deterministic decider for tiers and for it
to rank back and chest until he pastes their videos. These tests pin:
the method's arithmetic; that every row of the five source lists is rated, under
the row's own name; that the cut points are what the calibration finds; the
agreement it reached, as a floor, so a rating edit cannot make it worse unseen;
and that back.md and chest.md hold exactly the decider's lists.
"""
from pathlib import Path

import pytest

import exercise_features as ef
from services import tier_decider as td

_DIR = Path(__file__).resolve().parents[1] / "docs" / "training" / "tier_lists"


def _rows(filename):
    return td.parse_tier_table((_DIR / filename).read_text(encoding="utf-8"))


def _pairs():
    out = {}
    for filename, ratings in ef.RECORDED.items():
        out[filename] = [(td.score(ratings[n]), t) for n, _name, t in _rows(filename) if t]
    return out


# ── the arithmetic ───────────────────────────────────────────────────────────

def test_score_weights_stretch_three_times():
    f = td.Features("x", stretch=2, target=2, stable=2, load=2, comfort=2)
    assert td.score(f) == td.SCORE_MAX == 14
    assert td.score(td.Features("y", 0, 0, 0, 0, 0, not_growth=True)) == td.SCORE_MIN == -4
    assert td.score(td.Features("z", 1, 0, 0, 0, 0)) == 3


def test_a_rating_outside_0_to_2_is_refused():
    with pytest.raises(ValueError):
        td.Features("bad", stretch=3, target=0, stable=0, load=0, comfort=0)


def test_tiers_follow_the_cut_points():
    d, c, b, a, s = td.CUTS
    assert [td.tier_for(v) for v in (d - 1, d, c, b, a, s, td.SCORE_MAX)] == \
        ["F", "D", "C", "B", "A", "S", "S"]


@pytest.mark.parametrize("text,tier", [
    ("**S+**", "S"), ("high A", "A"), ("low D", "D"), ("**A+**", "A"), ("C", "C"),
    ("A; **S** sideways, one arm at a time", "A"),
    ('unreadable ("science based here") — from the reason, the bottom', None),
])
def test_source_tiers_are_read_the_same_way(text, tier):
    assert td.normalise_tier(text) == tier


# ── the ratings cover the source lists, under the rows' own names ────────────

@pytest.mark.parametrize("filename", sorted(ef.RECORDED))
def test_every_source_row_is_rated_under_its_own_name(filename):
    rows = _rows(filename)
    assert rows, f"{filename} has no ranked table"
    ratings = ef.RECORDED[filename]
    assert sorted(ratings) == [n for n, _, _ in rows], filename
    for number, name, _tier in rows:
        assert ratings[number].name == name, (filename, number)


# ── calibration and agreement ────────────────────────────────────────────────

def test_the_cut_points_are_what_the_calibration_finds():
    every = [p for pairs in _pairs().values() for p in pairs]
    assert td.calibrate(every) == td.CUTS


def test_the_calibration_is_deterministic():
    every = [p for pairs in _pairs().values() for p in pairs]
    assert td.calibrate(every) == td.calibrate(list(every))


def test_agreement_does_not_fall_below_the_measured_floor():
    """Measured 2026-10-16: 59/111 exact and 105/111 within one tier in
    sample; 46/111 and 107/111 leaving each list out. Guessing the most
    common tier scores 35/111 and 82/111. A rating edit may improve these;
    it may not lower them without this floor being moved on purpose."""
    pairs = _pairs()
    every = [p for ps in pairs.values() for p in ps]
    ins = td.agreement(every)
    lolo = td.leave_one_list_out(pairs)["all"]
    base = td.most_common_tier_baseline(every)
    assert ins["n"] == 111
    assert ins["exact"] >= 59 and ins["within_one"] >= 105
    assert lolo["exact"] >= 46 and lolo["within_one"] >= 107
    assert lolo["exact"] > base["exact"], "the decider must beat guessing one tier"


# ── the decided lists in the markdown are the decider's ──────────────────────

@pytest.mark.parametrize("area", sorted(ef.DECIDED))
def test_the_markdown_list_is_the_deciders(area):
    rows = _rows(f"{area}.md")
    expected = [(i, f.name, tier) for i, (f, _score, tier)
                in enumerate(td.ranked(ef.DECIDED[area]), start=1)]
    assert rows == expected, area


def test_the_decided_areas_are_not_also_source_lists():
    assert not set(f"{a}.md" for a in ef.DECIDED) & set(ef.RECORDED)
