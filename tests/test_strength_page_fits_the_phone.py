"""The Strength and Metabolism pages fit a phone screen.

Athlete, 2026-10: "Strength page is not aligned to the page it goes off the page
to the right." Measured at 390 x 844: the hero card and the muscle-balance card
were 740 px wide and the page 756, because a box with an aspect ratio, a minimum
height and no width of its own is widened to keep the ratio (220 px tall at
1194/356 is 738 px). Width 100% fixes the width and lets the min-height win the
height: 358 x 220, page 390.

Source checks, because the screen cannot be rendered in a test: every inline
style on these screens that sets an aspect ratio must also set its width.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSIGHTS = ROOT / "views" / "insights.py"


def _card_css() -> str:
    tree = ast.parse(INSIGHTS.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "_CARD_DIMENSIONS_CSS" for t in node.targets)):
            return ast.literal_eval(node.value)
    raise AssertionError("_CARD_DIMENSIONS_CSS is gone from views/insights.py")


def test_the_shared_card_box_sets_its_width_before_its_ratio():
    css = _card_css().replace(" ", "")
    assert "width:100%" in css
    assert "box-sizing:border-box" in css
    assert css.index("width:100%") < css.index("aspect-ratio")
    assert "min-height:220px" in css, "the card keeps its height on a phone"


def test_no_box_pairs_a_ratio_and_a_minimum_height_without_a_width():
    """The overflow needs both: an aspect ratio AND a minimum height, with the
    width left to the ratio. A new card copied without the shared string would
    bring it back on one screen and nowhere else. (The region faceplates set a
    ratio with no minimum height; their grid track sets the width, so they
    cannot widen — measured inside 374 px.)"""
    tree = ast.parse(INSIGHTS.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value.replace(" ", "")
            if "aspect-ratio:" in text and "min-height:" in text and "width:100%" not in text:
                bad.append((node.lineno, node.value[:80]))
    assert not bad, bad
