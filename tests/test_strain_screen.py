"""The strain drill-down's own layer: the snapshot the panel renders from, and
the skin plumbing that keeps the OTHER two drill-downs untouched.

services/strain_regions.py is covered by test_strain_regions.py. What this adds
is the screen contract — that a rest day, a yoga day and a failed read each
produce a stated absence rather than three zeros, and that adopting the
Strength palette on this one view could not have moved Readiness or Sleep.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from services import dashboard, strain_regions as sr

REGIONS = sr.REGIONS
D = date(2026, 7, 30)


def _rows(**kw):
    row = {"date": D.isoformat(), "upper_body": 50.1, "core": 47.2,
           "lower_body": 107.3, "unattributed": 0.0, "total_au": 204.6,
           "regions_known": True}
    row.update(kw)
    return [row]


def _snap(rows=None, overall=14.5, rolling=False, provenance=None, acwr=None):
    return dashboard.compute_region_strain_snapshot(
        D, rows if rows is not None else _rows(), 2,
        overall_snapshot={"strain": overall, "strain_is_rolling": rolling},
        provenance=provenance or {}, acwr_results=acwr,
    )


# ─── the populated case ──────────────────────────────────────────────────────

def test_a_training_day_reports_every_region_in_display_order():
    data = _snap()
    assert data["has_split"] is True
    assert [r["id"] for r in data["regions"]] == list(REGIONS)
    for region in data["regions"]:
        assert region["strain"] is not None
        assert region["au_pct"] is not None


def test_the_shares_add_to_one_hundred():
    data = _snap()
    total = sum(r["au_pct"] for r in data["regions"]) + (data["unattributed_pct"] or 0.0)
    assert total == pytest.approx(100.0, abs=0.05)


def test_no_region_ever_reads_above_the_overall():
    """The property that stops the panel looking broken. Necessarily true —
    regional AU <= total AU and the curve is monotonic — so this is a
    regression guard, not a hope."""
    data = _snap(overall=14.5)
    for region in data["regions"]:
        assert region["strain"] <= 14.5, region["id"]


def test_the_additivity_gap_is_reported():
    data = _snap(overall=14.5)
    assert data["additivity_gap"] > 0
    assert "logarithmic" in data["non_additive_note"]


def test_the_provisional_basis_reaches_the_screen():
    """The weights are authored, not measured. The screen has to say so."""
    data = _snap()
    assert data["shares_basis"] == "provisional"
    assert data["shares_version"] >= 1


def test_a_thin_attributed_fraction_is_flagged():
    data = _snap(provenance={"attributed_fraction": 0.49})
    assert data["attributed_is_low"] is True
    assert _snap(provenance={"attributed_fraction": 0.95})["attributed_is_low"] is False


def test_unmapped_names_reach_the_screen():
    data = _snap(provenance={"unmapped_names": ["Half Pigeon"]})
    assert data["unmapped_names"] == ["Half Pigeon"]


# ─── the states that must not read as zeros ──────────────────────────────────

def test_a_rest_day_has_no_split_at_all():
    """The headline is a 7-day trailing average. There is no single day to
    divide, so the panel states that rather than dividing the average."""
    data = _snap(rolling=True)
    assert data["has_split"] is False
    for region in data["regions"]:
        assert region["strain"] is None
        assert region["au"] is None


def test_a_yoga_day_claims_nothing_rather_than_claiming_zero():
    """Every pose is outside both region maps. Three zeros beside a real
    strain number would say "your body did nothing", which is false."""
    rows = [{"date": D.isoformat(), "upper_body": 0.0, "core": 0.0,
             "lower_body": 0.0, "unattributed": 150.0, "total_au": 150.0,
             "regions_known": False}]
    data = _snap(rows=rows, overall=11.2)
    assert data["has_split"] is False
    assert all(r["strain"] is None for r in data["regions"])


def test_a_day_with_no_row_at_all_has_no_split():
    assert _snap(rows=[])["has_split"] is False


def test_a_row_without_regional_keys_is_not_read_as_zeros():
    """Existing callers hand-build [{'date', 'total_au'}]."""
    assert _snap(rows=[{"date": D.isoformat(), "total_au": 204.6}])["has_split"] is False


def test_every_region_still_carries_an_acwr_verdict_when_there_is_no_split():
    """The rows are kept so the panel does not restructure between a rest day
    and a training day — but they must read as absent, not as passing."""
    data = _snap(rolling=True)
    for region in data["regions"]:
        assert region["acwr"]["diagnostic"] is False
        assert region["acwr"]["value"] == "ACWR —"


# ─── the other two drill-downs are untouched ─────────────────────────────────

def _app_source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_the_home_skin_reproduces_the_original_panel_colours():
    """Readiness and Sleep keep _SKIN_HOME, and its values are the exact
    strings those screens already emitted — "#555" rather than "#555555", and
    border:none rather than a transparent 1px border that would have shifted
    every panel by 2px."""
    tree = ast.parse(_app_source())
    skins = {}
    for node in tree.body:
        # The skins are annotated assignments (dict[str, str]), so AnnAssign —
        # matching only ast.Assign would silently find nothing and pass.
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        else:
            continue
        if name in ("_SKIN_HOME", "_SKIN_BOARD"):
            skins[name] = ast.literal_eval(node.value)
    assert skins["_SKIN_HOME"] == {
        "panel": "#131929", "ink": "#D4DCEE", "ink2": "#6B7A9B",
        "ink3": "#555", "border": "none", "radius": "12px",
    }
    assert skins["_SKIN_BOARD"]["panel"] == "#0E1018"


def test_only_the_strain_view_takes_the_board_skin():
    src = _app_source()
    assert '_SKIN_BOARD if view == "strain" else _SKIN_HOME' in src


def test_panel_defaults_to_the_home_skin():
    """Every pre-existing _panel call site passes no skin, so it must default
    to the look it has always had."""
    tree = ast.parse(_app_source())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_panel")
    skin_arg = fn.args.args[-1]
    assert skin_arg.arg == "skin"
    assert isinstance(fn.args.defaults[-1], ast.Constant)
    assert fn.args.defaults[-1].value is None


def test_the_region_reads_happen_only_on_the_strain_branch():
    """A read added to the Home card stream would cost every open a Notion
    query on a page whose whole latency story is about not doing that. Both
    new fetchers must be CALLED exactly once, and from inside _metric_detail.

    Counted off the AST rather than the text, so the `def` line is not
    mistaken for a call site."""
    tree = ast.parse(_app_source())
    detail = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_metric_detail")
    wanted = {"_region_au_history", "_stage_start_cached"}

    def _calls(node):
        return [c.func.id for c in ast.walk(node)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                and c.func.id in wanted]

    assert sorted(set(_calls(detail))) == sorted(wanted)
    module_level = [c for c in _calls(tree) if c in wanted]
    assert len(module_level) == len(_calls(detail)), (
        "a regional fetcher is called outside _metric_detail — the Home card "
        "stream would pay for it on every open"
    )


def test_the_home_card_stream_still_uses_the_unwidened_au_window():
    """_au_history was deliberately NOT widened — the regional series has its
    own fetch so the three-card stream pays nothing for it."""
    src = _app_source()
    assert "def _au_history(days: int = 28)" in src
