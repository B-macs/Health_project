"""Every clinical finding must say how it is re-measured.

Written 2026-08-17, on the athlete's instruction, after the audit found what
had gone wrong and why it was structural rather than accidental.

THE FAILURE THIS PREVENTS. Finding #2 attributes the standing hinge crack to
two structures — a tight right posterior hip capsule and the proximal hamstring
at the ischial tuberosity — and named neither a test. The block treated the
first for seven weeks. When it was finally measured (prone hip internal
rotation, sixty seconds, one person) it came back past 45 degrees on BOTH sides
with no asymmetry: no capsular restriction, nothing to treat, and a directly
contradicting reading available at any point since 2026-06-28 for the cost of
one minute.

That was not bad luck. `patient_profile.py` records findings and
`training_plan.py` prescribes against them, and NOTHING sat between the two
asking whether the attribution was right. Every finding had a `mechanism` and a
`training_implication`; not one had a `test`. There was no way to be wrong, and
therefore no way to stop.

In the athlete's words: "that's ridiculous to prescribe other exercises on
nothing when we could have just done a test to figure it out. This needs to not
happen again."

WHAT IS PINNED HERE
  * every finding carries a `test`, with a protocol, a unit and a positive
    threshold;
  * every test is runnable BY ONE PERSON — his constraint, and the reason the
    lateral scapular slide test was rejected;
  * a finding a prescribed exercise names must have a test DEFINED;
  * findings whose test has never been RUN are listed explicitly below, so the
    set can shrink freely but can never grow silently.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from patient_profile import PROFILE

FINDINGS = PROFILE["biomechanical_findings"]
IDS = [f["id"] for f in FINDINGS]

#: Required on every finding's `test`. `single_person` is here because a test
#: needing a second pair of hands does not get run, which is indistinguishable
#: from a test that does not exist — the state findings #1-#6 were all in.
REQUIRED_KEYS = ("name", "protocol", "unit", "positive_if", "single_person",
                 "last_run", "last_result")


@pytest.mark.parametrize("finding", FINDINGS, ids=[str(i) for i in IDS])
def test_every_finding_has_a_test(finding):
    assert finding.get("test"), (
        f"finding #{finding['id']} ({finding['title']!r}) has no test. A finding "
        f"with no way to be re-measured cannot be shown to be resolved, and "
        f"cannot be shown to be wrong — which is how the posterior hip capsule "
        f"was treated for seven weeks on an attribution that a one-minute "
        f"measurement refuted."
    )


@pytest.mark.parametrize("finding", FINDINGS, ids=[str(i) for i in IDS])
def test_every_test_is_fully_specified(finding):
    t = finding["test"]
    missing = [k for k in REQUIRED_KEYS if k not in t]
    assert not missing, f"finding #{finding['id']} test is missing {missing}"
    for k in ("name", "protocol", "unit", "positive_if"):
        assert isinstance(t[k], str) and t[k].strip(), (
            f"finding #{finding['id']} test has an empty {k}"
        )


@pytest.mark.parametrize("finding", FINDINGS, ids=[str(i) for i in IDS])
def test_every_test_is_runnable_alone(finding):
    """The athlete's constraint, 2026-08-17: "all test should be easy to perform
    and by one person." A test needing a helper is a test that waits for a
    physio appointment, and those are months apart."""
    assert finding["test"]["single_person"] is True, (
        f"finding #{finding['id']} test needs a second person"
    )


@pytest.mark.parametrize("finding", FINDINGS, ids=[str(i) for i in IDS])
def test_a_test_that_has_run_carries_its_result(finding):
    """A `last_run` date with no `last_result` is the note-loss failure by
    another door: the measurement happened and the reading is gone."""
    t = finding["test"]
    if t["last_run"] is not None:
        assert t["last_result"], (
            f"finding #{finding['id']} was measured on {t['last_run']} and no "
            f"result was recorded"
        )


@pytest.mark.parametrize("finding", FINDINGS, ids=[str(i) for i in IDS])
def test_a_positive_threshold_is_not_a_vibe(finding):
    """The proposed tests this replaces were rejected by the athlete for being
    too vague to be tests — "is the right still tighter, and by how much?" has
    no unit and no threshold, so it collects an impression and files it as a
    measurement. A threshold must name a quantity."""
    positive = finding["test"]["positive_if"].lower()
    quantitative = re.search(r"\d", positive) or any(
        w in positive for w in ("any ", "more", "over", "gap", "grade")
    )
    assert quantitative, (
        f"finding #{finding['id']} positive_if states no measurable condition: "
        f"{finding['test']['positive_if']!r}"
    )


# ── the link from prescription back to evidence ─────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent


def _findings_cited_by_the_plan() -> set[int]:
    """Exercise `biomechanical_focus` text names the finding it treats, e.g.
    "the maintenance-dependent right shoulder (finding #6)". That citation is
    the only machine-readable link between a prescription and its evidence, so
    it is what this test walks."""
    src = (_ROOT / "training_plan.py").read_text(encoding="utf-8")
    return {int(m) for m in re.findall(r"finding #(\d)", src)}


def test_the_plan_never_cites_a_finding_that_does_not_exist():
    unknown = _findings_cited_by_the_plan() - set(IDS)
    assert not unknown, f"training_plan.py cites non-existent findings: {sorted(unknown)}"


def test_every_finding_the_plan_treats_has_a_test_defined():
    """THE CORE RULE. An exercise may not be prescribed against a finding that
    has no way of being checked."""
    without = sorted(
        fid for fid in _findings_cited_by_the_plan()
        if not next(f for f in FINDINGS if f["id"] == fid).get("test")
    )
    assert not without, (
        f"the plan prescribes against findings with no test: {without}"
    )


#: Findings whose test EXISTS but has never been run. This set may SHRINK
#: freely; it may only grow by a deliberate edit, which is the point — a new
#: untested finding cannot arrive quietly. Dated so the age is visible.
#:
#: EMPTY since the evening of 2026-08-17: the athlete ran #3 (0 releases),
#: #5 (0 cracks — the finding the audit called neither-treated-nor-retired is
#: now measured QUIET, and its two movements returned as content) and #6
#: (right 105 s to failure, left capped with reserve) on the block's new day-1
#: measurement day. All six findings now carry at least one reading.
UNRUN_AS_OF_2026_08_17 = set()


def test_the_unrun_set_has_not_grown():
    unrun = {f["id"] for f in FINDINGS if f["test"]["last_run"] is None}
    new = unrun - UNRUN_AS_OF_2026_08_17
    assert not new, (
        f"findings {sorted(new)} now have an unrun test. Either run it, or add "
        f"it to UNRUN_AS_OF_2026_08_17 with a reason — silently is the one way "
        f"it must not happen."
    )


def test_the_unrun_set_does_not_list_findings_that_have_since_been_run():
    """Keeps the list honest in the other direction, so it cannot rot into a
    permanent excuse."""
    unrun = {f["id"] for f in FINDINGS if f["test"]["last_run"] is None}
    stale = UNRUN_AS_OF_2026_08_17 - unrun
    assert not stale, (
        f"findings {sorted(stale)} have been run — remove them from "
        f"UNRUN_AS_OF_2026_08_17"
    )
