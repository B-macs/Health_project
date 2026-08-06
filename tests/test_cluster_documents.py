"""
The Cluster A source documents, checked against the movement safety rules.

`Input_files/` is GITIGNORED — these documents are clinical material about one
person, the same status as the MRI. So this test is conditional: it runs when
the documents are present and skips when they are not, which means it protects
the athlete's own checkout without breaking a clean clone or CI.

WHY IT EXISTS. On 2026-08-06, before either was fixed, 78 movement names from
these documents were run through services.rules.check_movement: 8 matched any
rule, 70 returned `unknown` — which is not a block — and zero of the 14
movements contraindicated on mechanism were caught by the rule written for
them. One instruction came back affirmatively `cleared`.

Both the matcher and the documents have been fixed. This is what stops a later
edit to either quietly undoing it.
"""

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from services import rules  # noqa: E402

check_cluster_documents = pytest.importorskip("check_cluster_documents")

_DOCS = [os.path.join(_ROOT, d) for d in check_cluster_documents.DOCS]
_present = [d for d in _DOCS if os.path.exists(d)]

pytestmark = pytest.mark.skipif(
    len(_present) != len(_DOCS),
    reason="Input_files/ is gitignored; the cluster documents are not in this checkout",
)


def _named_movements():
    import io
    out = []
    for path in _DOCS:
        text = io.open(path, encoding="utf-8").read()
        for name in check_cluster_documents.movement_names(text):
            out.append((os.path.basename(path), name))
    return out


def test_the_documents_name_movements_at_all():
    """A parser that silently stops finding anything would make every test
    below vacuously pass — which is the failure mode of a check like this."""
    found = _named_movements()
    assert len(found) > 50, f"only found {len(found)} movements; the parser has drifted"


def test_no_named_movement_is_unrecognised_by_the_rule_set():
    """`unknown` reads as 'no rule applies' and is not a block —
    services/yoga.py discards it outright. A movement the rules have never
    heard of is indistinguishable from one they have cleared."""
    unknown = [(doc, name) for doc, name in _named_movements()
               if rules.check_movement(name, check_cluster_documents.STAGE)["severity"] == "unknown"]
    assert unknown == [], unknown


def test_no_named_movement_is_contraindicated_at_the_live_stage():
    """The documents are ADAPTED — the substitutions are baked in rather than
    filtered at runtime. So nothing contraindicated should survive in them, and
    if one does, the adaptation missed it rather than the gate catching it."""
    stage = check_cluster_documents.STAGE
    banned = [(doc, name) for doc, name in _named_movements()
              if rules.check_movement(name, stage)["severity"] == "contraindicated"]
    assert banned == [], banned


def test_the_script_itself_agrees():
    """The test and the script must not be able to disagree about the answer —
    the script is what gets run by hand, and a test that duplicated its logic
    could pass while the script failed."""
    cwd = os.getcwd()
    try:
        os.chdir(_ROOT)
        assert check_cluster_documents.main() == 0
    finally:
        os.chdir(cwd)
