"""
Walks the entire services/ package and asserts no module imports streamlit
or references `st.` anywhere. This is the acceptance-criteria enforcement
test — services/ must stay framework-agnostic so a future FastAPI deployment
can reuse it unmodified.
"""

import ast
import pathlib

SERVICES_ROOT = pathlib.Path(__file__).resolve().parent.parent / "services"


def _all_service_modules() -> list[pathlib.Path]:
    return sorted(SERVICES_ROOT.rglob("*.py"))


def test_services_package_exists_and_has_modules():
    modules = _all_service_modules()
    assert len(modules) > 5, "services/ should contain many modules by now"


def _imports_streamlit(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == "streamlit" for a in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.split(".")[0] == "streamlit":
                return True
    return False


def _references_st_attr(tree: ast.AST) -> bool:
    """Catches `st.something` even if streamlit were imported under an alias
    (e.g. `import streamlit as st`) — belt-and-suspenders alongside the
    import check above."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "st":
                return True
    return False


def test_no_module_in_services_imports_streamlit():
    offenders = []
    for path in _all_service_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _imports_streamlit(tree):
            offenders.append(str(path))
    assert offenders == [], f"streamlit imported in: {offenders}"


def test_no_module_in_services_references_st_dot_attribute():
    offenders = []
    for path in _all_service_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _references_st_attr(tree):
            offenders.append(str(path))
    assert offenders == [], f"st.<attr> referenced in: {offenders}"


def test_services_modules_all_import_cleanly():
    """Belt-and-suspenders: every module actually imports without error,
    independent of any Streamlit runtime being present."""
    import importlib
    for path in _all_service_modules():
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(SERVICES_ROOT.parent).with_suffix("")
        module_name = ".".join(rel.parts)
        importlib.import_module(module_name)  # raises on failure
