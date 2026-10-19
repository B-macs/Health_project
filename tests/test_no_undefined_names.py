"""No function reads a name that nothing defines.

On 2026-08-23 a commit moved the 14-day biometric read out of views/training.py
into today.py and deleted the line that assigned `_rm_bio`. The readiness
auto-shift still read `_rm_bio`, so every evaluation raised NameError, and an
`except Exception: pass` swallowed it: no shift was proposed or recorded for
two months (found 2026-10-19, rebuild Phase 2 inventory, fault F1). The tests
of the time only checked the source text, which still looked right.

This walks every function of the app's Python with the standard symtable: a
name a function reads, that is not local, not from an enclosing function, not
assigned or imported at module level and not a builtin, can only raise
NameError when that line runs. No network and no import of the checked files.
"""

from __future__ import annotations

import builtins
import symtable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKED = sorted(
    [ROOT / "app.py", ROOT / "today.py", ROOT / "repo.py", ROOT / "nav.py", ROOT / "styles.py"]
    + list((ROOT / "views").glob("*.py"))
    + list((ROOT / "services").rglob("*.py"))
    + list((ROOT / "api").rglob("*.py"))
)
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__", "__package__",
                                 "__builtins__", "__loader__", "__path__"}


def undefined_names(source: str, filename: str) -> list[tuple[str, str]]:
    """(function, name) for every global read that the module never defines."""
    module = symtable.symtable(source, filename, "exec")
    defined = {s.get_name() for s in module.get_symbols()
               if s.is_assigned() or s.is_imported() or s.is_namespace()}
    found: list[tuple[str, str]] = []

    def walk(table: symtable.SymbolTable) -> None:
        for child in table.get_children():
            if child.get_type() in ("function", "class") or child.get_type().name in (
                    "FUNCTION", "CLASS"):
                for sym in child.get_symbols():
                    name = sym.get_name()
                    if (sym.is_referenced() and sym.is_global() and not sym.is_assigned()
                            and name not in defined and name not in BUILTINS):
                        found.append((child.get_name(), name))
            walk(child)

    walk(module)
    return found


def test_the_check_finds_the_fault_that_hid_for_two_months():
    source = (
        "def render():\n"
        "    try:\n"
        "        shift = should_shift(_rm_bio)\n"
        "    except Exception:\n"
        "        pass\n"
        "def should_shift(rows):\n"
        "    return rows\n"
    )
    assert undefined_names(source, "x.py") == [("render", "_rm_bio")]


def test_names_from_imports_enclosing_functions_and_builtins_are_fine():
    source = (
        "import json\n"
        "from datetime import date\n"
        "LIMIT = 3\n"
        "def outer():\n"
        "    seen = []\n"
        "    def inner():\n"
        "        return len(seen) < LIMIT and json.dumps(date.today().isoformat())\n"
        "    return inner\n"
    )
    assert undefined_names(source, "x.py") == []


@pytest.mark.parametrize("path", CHECKED, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_function_reads_an_undefined_name(path):
    assert undefined_names(path.read_text(encoding="utf-8"), str(path)) == []
