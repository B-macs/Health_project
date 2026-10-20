"""The engine API's contract, checked whole (rebuild Phase 2, milestone 6).

- Every KEEP or MOVE row of the screen inventory maps to an endpoint of the
  contract with a test that exists, or to the phone with a reason: the
  gate's inventory_unmapped counter, held in the main suite too, so a row
  cannot come loose between two gate runs.
- Every operation in shared/openapi.json is called by at least one test in
  tests/api: an endpoint nobody calls is an endpoint nobody checked.
- Every route that answers about a day takes the caller's day
  (X-Local-Date), and the contract says so.

Static: it reads the contract and the test sources, never runs a server.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = json.loads((ROOT / "shared" / "openapi.json").read_text(encoding="utf-8"))
METHODS = ("get", "post", "put", "patch", "delete")
#: Operations that do not depend on the caller's day, with the reason.
NO_DAY = {
    "GET /api/health": "the engine's own diagnostics",
    "GET /api/training/yoga": "the catalogue, the same every day",
    "POST /api/training/completion": "arithmetic on the phone's own clock readings",
    "DELETE /api/insights/flexibility/capture": "drops the draft, whatever its day",
    "POST /api/insights/queue/process": "parses what is pending, whatever its day",
    "GET /api/settings": "the stored settings",
    "GET /api/data/check": "the store against its newest backup; ages are in hours, not days",
}


def _operations():
    for path, ops in OPENAPI["paths"].items():
        for method, op in ops.items():
            if method in METHODS:
                yield f"{method.upper()} {path}", path, op


def test_every_inventory_row_is_served_or_the_phones():
    sys.path.insert(0, str(ROOT / "scripts"))
    import rebuild_gate as g
    rows = g.inventory_rows(g.SCREEN_INVENTORY.read_text(encoding="utf-8"))
    mapping = json.loads(g.INVENTORY_ENDPOINTS.read_text(encoding="utf-8"))["rows"]
    assert g.unmapped_rows(rows, mapping, g.openapi_operations(OPENAPI)) == []


def test_every_operation_is_called_by_a_test():
    sources = "\n".join(p.read_text(encoding="utf-8")
                        for p in (ROOT / "tests" / "api").glob("test_*.py"))
    uncalled = []
    for name, path, _op in _operations():
        pattern = re.escape(path)
        pattern = re.sub(r"\\\{[a-z_]+\\\}", r"[A-Za-z0-9_.-]+", pattern)
        if not re.search(r'["\']' + pattern + r'(\?|["\'])', sources) \
                and not re.search(r'f["\']' + pattern + r'(\?|["\'])', sources):
            uncalled.append(name)
    assert uncalled == []


def test_every_route_about_a_day_takes_the_callers_day():
    missing = []
    for name, _path, op in _operations():
        headers = {p["name"].lower() for p in op.get("parameters", []) if p.get("in") == "header"}
        if "x-local-date" not in headers and name not in NO_DAY:
            missing.append(name)
    assert missing == [], "a route that reads a day takes X-Local-Date (rebuild rule 3)"
