"""The engine image copies exactly the root modules the engine imports.

The image (Dockerfile) and the upload to Cloud Build (.gcloudignore, and
.dockerignore for a local build) are ALLOW-LISTS: only named files leave the
PC, because this folder also holds clinical documents and live credentials
(CLAUDE.md, rebuild rule 7). An allow-list goes stale silently: on 2026-10-16
services/ had started importing goal_block (the 12-week block), the image did
not copy it, and twelve services/ modules - repository and sessions among
them - would have failed to import in a container built that day. Nothing
local showed it, because the checkout has every file.

So the list is checked against the code, both ways:
- every root module that services/ or api/ imports, directly or through
  another root module, is copied by the Dockerfile and admitted by both
  ignore files;
- every root module the Dockerfile copies is one of those, so an unused file
  (a clinical profile, say) is never uploaded by accident.

Static (ast), so it needs neither FastAPI nor any of the modules it reads.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOT_MODULES = {p.stem for p in ROOT.glob("*.py")}
NEVER_UPLOADED = {"patient_profile", "training_history"}   # clinical record


def _imported_root_modules(path: Path) -> set[str]:
    """Root modules a file imports, at the top or inside a function."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".")[0]]
        else:
            continue
        found.update(n for n in names if n in ROOT_MODULES)
    return found


def needed_root_modules() -> set[str]:
    sources = [*ROOT.joinpath("services").rglob("*.py"), *ROOT.joinpath("api").rglob("*.py")]
    needed: set[str] = set()
    for path in sources:
        needed |= _imported_root_modules(path)
    todo = list(needed)
    while todo:                                   # what those modules import in turn
        for name in _imported_root_modules(ROOT / f"{todo.pop()}.py") - needed:
            needed.add(name)
            todo.append(name)
    return needed


def dockerfile_copies() -> set[str]:
    text = ROOT.joinpath("Dockerfile").read_text(encoding="utf-8").replace("\\\n", " ")
    copied: set[str] = set()
    for line in text.splitlines():
        if line.strip().startswith("COPY "):
            copied |= {Path(t).stem for t in line.split()[1:] if t.endswith(".py") and "/" not in t}
    return copied


def admitted(ignore_file: str, prefix: str) -> set[str]:
    text = ROOT.joinpath(ignore_file).read_text(encoding="utf-8")
    return set(re.findall(rf"^!{re.escape(prefix)}([A-Za-z0-9_]+)\.py$", text, re.MULTILINE))


def test_the_engine_imports_some_root_modules():
    # Guards the walk itself: an empty set would make every check below vacuous.
    assert {"training_plan", "training_constants", "goal_block"} <= needed_root_modules()


def test_the_dockerfile_copies_every_root_module_the_engine_imports():
    missing = needed_root_modules() - dockerfile_copies()
    assert not missing, f"add to the Dockerfile's COPY: {sorted(missing)}"


def test_both_ignore_files_admit_every_root_module_the_engine_imports():
    needed = needed_root_modules()
    assert not needed - admitted(".gcloudignore", "/"), \
        f"admit in .gcloudignore: {sorted(needed - admitted('.gcloudignore', '/'))}"
    assert not needed - admitted(".dockerignore", ""), \
        f"admit in .dockerignore: {sorted(needed - admitted('.dockerignore', ''))}"


def test_nothing_unused_is_copied_or_uploaded():
    needed = needed_root_modules()
    for name, listed in (("Dockerfile", dockerfile_copies()),
                         (".gcloudignore", admitted(".gcloudignore", "/")),
                         (".dockerignore", admitted(".dockerignore", ""))):
        assert not listed - needed, f"{name} lists modules the engine never imports: " \
                                    f"{sorted(listed - needed)}"


def test_the_clinical_record_is_never_in_the_image():
    for listed in (dockerfile_copies(), admitted(".gcloudignore", "/"),
                   admitted(".dockerignore", "")):
        assert not listed & NEVER_UPLOADED
