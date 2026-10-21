"""scripts/rebuild_gate.py -- the phone-app rebuild's counter gate.

    python scripts/rebuild_gate.py p0 [--update-features] [--reuse-test-runs]

A phase is green only when every counter it registers reads 0. Each counter
returns a count of OPEN items, a one-line detail and evidence paths; a counter
that crashes is itself one open item, so a broken check can never read green.
The design is ../lauscher's `lauscher gate` (generator/lauscher/gate.py), kept
standalone here: no Typer, no Jinja2, nothing this repo does not already have.

Writes reports/rebuild/<phase>_gate.html and .json. reports/rebuild/ is
gitignored on purpose: evidence logs can carry personal readings, and this repo
is public (CLAUDE.md, rebuild rule 7). The console and the reports never print
a secret: the secret scan reports file and line, never the match.

Exit codes: 0 green, 1 open items, 2 no counters registered for the phase.
See docs/rebuild/ and the "Phone app rebuild" section of CLAUDE.md.
"""

from __future__ import annotations

import argparse
import ast
import html
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports" / "rebuild"
REBUILD_DOCS = REPO_ROOT / "docs" / "rebuild"
FEATURE_LIST = REBUILD_DOCS / "feature_list.json"
OWNER_CHECKS = REBUILD_DOCS / "owner_checks.json"
STREAMLIT_BOUND_TESTS = REBUILD_DOCS / "streamlit_bound_tests.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
REBUILD_SECTION_HEADING = "## Phone app rebuild (from 2026-10-07)"

GREEN, RED = "\U0001F7E2", "\U0001F534"


# ── the registry ─────────────────────────────────────────────────────────────

@dataclass
class CounterResult:
    count: int
    detail: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Counter:
    phase: str
    name: str
    description: str
    func: Callable[[], CounterResult]


@dataclass
class GateRow:
    name: str
    description: str
    count: int
    detail: str
    evidence: list[str]
    error: str | None = None


REGISTRY: dict[str, dict[str, Counter]] = {}
REVIEW_ITEMS: dict[str, list[str]] = {}

# Set by --reuse-test-runs: the test counters read the last junit file instead
# of running the suite again (minutes each). The gate run for a PROMPT 2 never
# sets it.
REUSE_TEST_RUNS = False


def counter(phase: str, name: str, description: str):
    """Register a gate counter for a phase."""
    def register(func: Callable[[], CounterResult]):
        REGISTRY.setdefault(phase.lower(), {})[name] = Counter(
            phase.lower(), name, description, func)
        return func
    return register


def review(phase: str, *items: str) -> None:
    """Manual checks listed on the report page; they are not counted."""
    REVIEW_ITEMS.setdefault(phase.lower(), []).extend(items)


def run_gate(phase: str) -> list[GateRow]:
    rows: list[GateRow] = []
    for item in REGISTRY.get(phase.lower(), {}).values():
        try:
            result = item.func()
        except Exception as exc:  # noqa: BLE001 - a crashing counter is an open item
            rows.append(GateRow(item.name, item.description, 1, "counter crashed",
                                [], f"{type(exc).__name__}: {exc}"))
            continue
        rows.append(GateRow(item.name, item.description, int(result.count),
                            result.detail, list(result.evidence)))
    return rows


# ── shared helpers (pure, so tests reach them without running anything) ─────

def gate_floor(claude_md_text: str) -> int | None:
    """The pass-count floor from CLAUDE.md's "Deterministic Gate" line."""
    match = re.search(r"Expected: \*\*(\d+)/\d+ passed\*\*", claude_md_text)
    return int(match.group(1)) if match else None


@dataclass
class JunitSummary:
    tests: int
    failures: int
    errors: int
    skipped: int

    @property
    def passed(self) -> int:
        return self.tests - self.failures - self.errors - self.skipped


def read_junit(path: Path) -> JunitSummary:
    """Sums every <testsuite> in a pytest junit file."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.get(key, 0))
    return JunitSummary(**totals)


def streamlit_bound_tests(md_path: Path = STREAMLIT_BOUND_TESTS) -> list[str]:
    """The tests that import Streamlit or the screen modules, as listed in
    docs/rebuild/streamlit_bound_tests.md: a whole file ("- `tests/x.py` ...")
    or one test in an otherwise engine-only file ("- `tests/x.py::test_y` ...")."""
    if not md_path.exists():
        return []
    return re.findall(r"^- `(tests/[^`:]+\.py(?:::[A-Za-z0-9_]+)?)`",
                      md_path.read_text(encoding="utf-8"), flags=re.MULTILINE)


def engine_run_exclusions(entries: list[str]) -> list[str]:
    """pytest arguments that leave the listed tests out of the engine run: a
    whole file is ignored, a single test is deselected."""
    return [f"--deselect={e}" if "::" in e else f"--ignore={e}" for e in entries]


def main_python(root: Path | None = None) -> Path:
    """The repo's own venv/, whatever Python started the gate: the system
    Python on this PC has none of the app's libraries, and a suite run there
    reads as 57 collection errors, not as the app's state."""
    root = root or REPO_ROOT
    windows = root / "venv" / "Scripts" / "python.exe"
    return windows if windows.exists() else root / "venv" / "bin" / "python"


def engine_python(root: Path = REPO_ROOT) -> Path:
    windows = root / ".venv-engine" / "Scripts" / "python.exe"
    return windows if windows.exists() else root / ".venv-engine" / "bin" / "python"


def parity_python(root: Path = REPO_ROOT) -> Path:
    """The interpreter the parity run computes the services' side with: the engine's
    (.venv-engine, the Python the engine runs), so the run measures the deployment and
    not the interpreter. Python 3.12 adds floats in sum() more exactly than 3.11 (the
    repo's venv/), and a 28-night average then lands on the other side of a rounding
    step: on 2026-10-20 that alone was 3 "differences" in the fused sleep debt."""
    engine = engine_python(root)
    return engine if engine.exists() else main_python(root)


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({"NO_COLOR": "1", "FORCE_COLOR": "0", "CI": "1",
                "PYTHONIOENCODING": "utf-8"})
    return env


def _run_pytest(python: Path | str, junit: Path, log: Path,
                extra: list[str] | None = None, target: str = "tests/") -> int:
    junit.parent.mkdir(parents=True, exist_ok=True)
    junit.unlink(missing_ok=True)      # a crashed run must not read the last run's file
    cmd = [str(python), "-m", "pytest", target, "-q", "-p", "no:cacheprovider",
           f"--junitxml={junit}", *(extra or [])]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=_child_env(), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    log.write_text(proc.stdout + proc.stderr, encoding="utf-8", newline="\n")
    return proc.returncode


# Secret patterns: credential SHAPES, never tied to a value in this repo. The
# scan reports file:line only; the matched text never leaves this process.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("Notion token", re.compile(r"\b(?:secret|ntn)_[A-Za-z0-9]{40,}\b")),
    ("Supabase secret key", re.compile(r"\bsb_secret_[A-Za-z0-9_\-]{20,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{15,}\.eyJ[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{15,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Cloudflare API token assignment",
     re.compile(r"CLOUDFLARE_API_TOKEN\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{30,}")),
]

# Files that hold a pattern on purpose (this scanner's own patterns and tests).
SECRET_SCAN_ALLOW = {"scripts/rebuild_gate.py", "tests/test_rebuild_gate.py"}


def scan_text_for_secrets(text: str) -> list[tuple[int, str]]:
    """(line number, pattern name) for every secret-shaped match."""
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                hits.append((lineno, name))
    return hits


# What may go to Cloud Build. Anything else in the upload list is unexpected;
# these patterns are the PERSONAL ones, counted as open items.
PERSONAL_UPLOAD_PATTERNS = [
    re.compile(r"^Input_files(/|$)"),
    re.compile(r"^\.streamlit(/|$)"),
    re.compile(r"(^|/)\.env(\.|$)"),
    re.compile(r"\.(db|db-shm|db-wal|sqlite|sqlite3)$"),
    re.compile(r"(^|/)\.sync_state\.json$"),
    re.compile(r"(^|/)patient_profile\.py$"),
    re.compile(r"(^|/)training_history\.py$"),
    re.compile(r"^voice_training(/|$)"),
    re.compile(r"^reports(/|$)"),
]


def personal_upload_files(paths: list[str]) -> list[str]:
    norm = [p.replace("\\", "/") for p in paths]
    norm = [p[2:] if p.startswith("./") else p for p in norm]
    return [p for p in norm if any(rx.search(p) for rx in PERSONAL_UPLOAD_PATTERNS)]


# The GO targets of rebuild Phase 0, fixed before any measurement (Notion
# Phase 0 page, PROMPT 1 section 6). p0_proof.json holds the measured numbers.
P0_TARGETS: list[tuple[str, str, Callable[[dict], bool | None]]] = [
    ("cold_start_median_s", "cold start median <= 10 s",
     lambda p: None if p.get("cold_start_median_s") is None
     else p["cold_start_median_s"] <= 10),
    ("cold_start_worst_s", "cold start worst <= 20 s",
     lambda p: None if p.get("cold_start_worst_s") is None
     else p["cold_start_worst_s"] <= 20),
    ("free_tier_max_share", "projected use <= 50% of every free-tier figure",
     lambda p: None if p.get("free_tier_max_share") is None
     else p["free_tier_max_share"] <= 0.5),
    ("garmin_ok", "Garmin login and read work from Cloud Run",
     lambda p: None if p.get("garmin_ok") is None else bool(p["garmin_ok"])),
    ("image_ok", "image fits 0.5 GB free storage, or costs under EUR 0.10 a month",
     lambda p: None if p.get("image_size_mb") is None and p.get("image_monthly_cost_eur") is None
     else ((p.get("image_size_mb") is not None and p["image_size_mb"] <= 500)
           or (p.get("image_monthly_cost_eur") is not None
               and p["image_monthly_cost_eur"] < 0.10))),
    ("upload_clean", "no personal file in the Cloud Build upload",
     lambda p: None if p.get("upload_personal_files") is None
     else p["upload_personal_files"] == 0),
    # Added 2026-10-19, after measurement and STRICTER only: Google refused the
    # first request after the engine slept ("no available instance"), which no
    # target above could see, because a refused start has no duration.
    ("cold_start_failures", "every timed cold start answered",
     lambda p: None if p.get("cold_start_failures") is None
     else p["cold_start_failures"] == 0),
]


def missed_targets(proof: dict, targets=P0_TARGETS) -> list[str]:
    """Targets that are missed OR not measured yet: an unmeasured target is
    not a passed one. A target the OWNER waived (proof["waived_targets"],
    key -> his reason in his words) is left out here and named by
    waived_targets() instead, so the report shows the waiver, never hides it."""
    waived = waived_targets(proof, targets)
    missed = []
    for key, label, check in targets:
        if key in waived:
            continue
        verdict = check(proof)
        if verdict is not True:
            missed.append(label + ("" if verdict is False else " (not measured)"))
    return missed


def waived_targets(proof: dict, targets=P0_TARGETS) -> dict[str, str]:
    """{target key: the owner's reason} for every waiver that names a real
    target and gives a reason. A waiver without a reason waives nothing."""
    keys = {key for key, _label, _check in targets}
    raw = proof.get("waived_targets") or {}
    return {k: str(v) for k, v in raw.items() if k in keys and str(v).strip()}


def _owner_check(phase: str, key: str) -> bool | None:
    if not OWNER_CHECKS.exists():
        return None
    data = json.loads(OWNER_CHECKS.read_text(encoding="utf-8"))
    return data.get(phase, {}).get(key)


# ── Phase 0 counters ─────────────────────────────────────────────────────────

def _main_gate_counter(phase: str) -> CounterResult:
    """The main suite in venv/: its failures and errors, plus 1 when the pass
    count is under the floor in CLAUDE.md's "Deterministic Gate"."""
    if not main_python().exists():
        return CounterResult(1, "venv/ is missing (python -m venv venv, then pip install -r "
                                "requirements.txt)")
    out = REPORTS_DIR / phase
    junit, log = out / "pytest-main.xml", out / "pytest-main.log"
    if not (REUSE_TEST_RUNS and junit.exists()):
        _run_pytest(main_python(), junit, log)
    if not junit.exists():
        return CounterResult(1, "pytest wrote no junit file", [f"{phase}/pytest-main.log"])
    summary = read_junit(junit)
    floor = gate_floor(CLAUDE_MD.read_text(encoding="utf-8"))
    under = 1 if floor is None or summary.passed < floor else 0
    return CounterResult(
        summary.failures + summary.errors + under,
        f"{summary.passed} passed, {summary.failures} failed, {summary.errors} errors, "
        f"{summary.skipped} skipped; floor {floor}",
        [f"{phase}/pytest-main.log"])


@counter("p0", "tests_failing",
         "main gate failures in venv/, plus 1 if the pass count is under the floor")
def p0_tests_failing() -> CounterResult:
    return _main_gate_counter("p0")


@counter("p0", "engine_venv_fail",
         "failures in the clean Python 3.12 venv (requirements-engine*), Streamlit tests excluded")
def p0_engine_venv_fail() -> CounterResult:
    python = engine_python()
    if not python.exists():
        return CounterResult(1, ".venv-engine is missing (uv venv .venv-engine --python 3.12)")
    excluded = streamlit_bound_tests()
    if not excluded:
        return CounterResult(1, "docs/rebuild/streamlit_bound_tests.md lists no tests")
    out = REPORTS_DIR / "p0"
    junit, log = out / "pytest-engine.xml", out / "pytest-engine.log"
    if not (REUSE_TEST_RUNS and junit.exists()):
        _run_pytest(python, junit, log, engine_run_exclusions(excluded))
    if not junit.exists():
        return CounterResult(1, "pytest wrote no junit file", ["p0/pytest-engine.log"])
    summary = read_junit(junit)
    return CounterResult(
        summary.failures + summary.errors,
        f"{summary.passed} passed, {summary.failures} failed, {summary.errors} errors, "
        f"{summary.skipped} skipped; {len(excluded)} Streamlit entries excluded",
        ["p0/pytest-engine.log"])


def _pnpm_test_counter(phase: str) -> CounterResult:
    """`pnpm test`: it builds the app (with its type check), then runs the app's and the
    Worker's Vitest suites. A failed build with no failed test still counts 1."""
    pnpm = shutil.which("pnpm")
    if not pnpm:
        return CounterResult(1, "pnpm is not on PATH")
    if not (REPO_ROOT / "node_modules").exists():
        return CounterResult(1, "node_modules is missing (pnpm install)")
    out = REPORTS_DIR / phase
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([pnpm, "test"], cwd=REPO_ROOT, env=_child_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = proc.stdout + proc.stderr
    (out / "pnpm-test.log").write_text(log, encoding="utf-8", newline="\n")
    failed = sum(int(n) for n in re.findall(r"Tests\s+(\d+) failed", log))
    if proc.returncode != 0 and failed == 0:
        failed = 1
    passed = sum(int(n) for n in re.findall(r"Tests\s+(\d+) passed", log))
    return CounterResult(failed, f"{passed} passed, {failed} failed", [f"{phase}/pnpm-test.log"])


@counter("p0", "pnpm_tests_failing",
         "failures in `pnpm test` (builds the app, then the app and Worker tests)")
def p0_pnpm_tests_failing() -> CounterResult:
    return _pnpm_test_counter("p0")


@counter("p0", "upload_personal_files",
         "files in the Cloud Build upload list under Input_files/, .streamlit/, *.db, .env* "
         "and the other personal patterns")
def p0_upload_personal_files() -> CounterResult:
    gcloud = shutil.which("gcloud")
    if not gcloud:
        return CounterResult(1, "gcloud is not installed, so the upload list cannot be read")
    proc = subprocess.run([gcloud, "meta", "list-files-for-upload", "."], cwd=REPO_ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return CounterResult(1, f"gcloud meta list-files-for-upload failed ({proc.returncode})")
    files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    out = REPORTS_DIR / "p0"
    out.mkdir(parents=True, exist_ok=True)
    (out / "upload-list.txt").write_text("\n".join(files) + "\n", encoding="utf-8",
                                         newline="\n")
    personal = personal_upload_files(files)
    detail = (f"{len(files)} files uploaded; personal: {', '.join(personal)}" if personal
              else f"{len(files)} files uploaded; none personal")
    return CounterResult(len(personal), detail, ["p0/upload-list.txt"])


@counter("p0", "proof_targets_missed",
         "GO targets (Phase 0 PROMPT 1 section 6) missed or not measured")
def p0_proof_targets_missed() -> CounterResult:
    path = REBUILD_DOCS / "p0_proof.json"
    proof = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    missed = missed_targets(proof)
    labels = {key: label for key, label, _check in P0_TARGETS}
    waived = [f"{labels[k]} WAIVED by the owner: {why}" for k, why in waived_targets(proof).items()]
    detail = "; ".join(missed) or "every target met or waived"
    return CounterResult(len(missed), detail + ("; " + "; ".join(waived) if waived else ""))


@counter("p0", "secrets_in_repo", "secret-shaped strings in tracked files (file:line only)")
def p0_secrets_in_repo() -> CounterResult:
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True)
    hits: list[str] = []
    for raw in proc.stdout.split(b"\0"):
        rel = raw.decode("utf-8", errors="replace")
        if not rel or rel in SECRET_SCAN_ALLOW:
            continue
        path = REPO_ROOT / rel
        try:
            if not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:          # binary
            continue
        for lineno, name in scan_text_for_secrets(data.decode("utf-8", errors="replace")):
            hits.append(f"{rel}:{lineno} ({name})")
    return CounterResult(len(hits), "; ".join(hits[:20]) or "no secret-shaped strings")


@counter("p0", "control_files_missing",
         "the CLAUDE.md rebuild section, state.md, archive.md, feature_list.json, stack.md")
def p0_control_files_missing() -> CounterResult:
    missing = [name for name in ("state.md", "archive.md", "feature_list.json", "stack.md")
               if not (REBUILD_DOCS / name).exists()]
    if REBUILD_SECTION_HEADING not in CLAUDE_MD.read_text(encoding="utf-8"):
        missing.insert(0, "CLAUDE.md rebuild section")
    return CounterResult(len(missing), ", ".join(missing) or "all present")


@counter("p0", "streamlit_app_broken",
         "1 unless the owner confirmed that the hosted Streamlit app opens after the push")
def p0_streamlit_app_broken() -> CounterResult:
    verdict = _owner_check("p0", "streamlit_app_opens")
    if verdict is True:
        return CounterResult(0, "the owner confirmed it opens")
    return CounterResult(1, "the owner reported it broken" if verdict is False
                         else "not confirmed yet (docs/rebuild/owner_checks.json)")


review("p0",
       "Open the Worker address on the iPhone: the placeholder shows \"Health\" and the version.",
       "After the push, open the hosted Streamlit app and check that it still works.",
       "Compare /api/readiness for yesterday with the Streamlit Home card's daily score.")


# ── Phase 1 counters: Voice Training leaves the health app ───────────────────

VOICE_REF_PATTERN = re.compile(
    r"voxplot|voice_training|Voice Training|views[/.]sync\b|from views import sync")
#: Tracked files that may still name the voice app, each with its reason. Docs
#: and Markdown never count: they keep the history of the move.
VOICE_REF_ALLOW = {
    "scripts/rebuild_gate.py": "this gate: it holds the patterns it looks for",
    "tests/test_rebuild_gate.py": "the gate's own tests",
    "tests/test_rebuild_secrets.py": "proves another app's [voxplot_supabase] secrets never go to the engine",
    "tests/api/test_api_phase0.py": "proves the engine's config drops another app's [voxplot_supabase] section",
    "tests/test_voice_app_moved_out.py": "the test that keeps the voice app out names what it keeps out",
}
VOICE_LIBS = ("praat-parselmouth", "scipy", "soundfile", "imageio-ffmpeg")
VOICE_REQUIREMENT_FILES = ("requirements.txt", "requirements-engine.txt")
P1_DEVICE_CHECKS = {
    "health_three_tabs": "the health app opens with three tabs (Home, Training, Insights) and no Voice Training",
    "health_pages_work": "Home, Training and Insights work in the health app",
    "voice_app_records": "the voice app opens from its own Home Screen icon and records",
}


def voice_ref_hits(files: dict[str, str]) -> list[str]:
    """"path:line" for every line of tracked code or config that still names
    Voice Training. `files` maps repo-relative paths to their text."""
    hits = []
    for rel, text in files.items():
        # .claude/ is Claude Code's own settings (its permission rules quote old
        # commands), not the health app.
        if (rel.startswith(("docs/", ".claude/")) or rel.endswith(".md")
                or rel in VOICE_REF_ALLOW):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if VOICE_REF_PATTERN.search(line):
                hits.append(f"{rel}:{lineno}")
    return hits


def voice_lib_hits(files: dict[str, str]) -> list[str]:
    """"path: library" for each voice-only library a requirements file names."""
    hits = []
    for rel, text in files.items():
        for line in text.splitlines():
            name = re.split(r"[\s<>=!~;\[#]", line.strip(), maxsplit=1)[0].lower()
            if name in VOICE_LIBS:
                hits.append(f"{rel}: {name}")
    return hits


def _tracked_texts() -> dict[str, str]:
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True)
    texts: dict[str, str] = {}
    for raw in proc.stdout.split(b"\0"):
        rel = raw.decode("utf-8", errors="replace")
        path = REPO_ROOT / rel
        try:
            if not rel or not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" not in data[:4096]:
            texts[rel] = data.decode("utf-8", errors="replace")
    return texts


@counter("p1", "tests_failing",
         "main gate failures in venv/, plus 1 if the pass count is under the floor")
def p1_tests_failing() -> CounterResult:
    return _main_gate_counter("p1")


@counter("p1", "voice_refs_left",
         "lines of tracked code or config that still name Voice Training (docs and *.md excluded)")
def p1_voice_refs_left() -> CounterResult:
    hits = voice_ref_hits(_tracked_texts())
    return CounterResult(len(hits), "; ".join(hits[:20]) or "none")


@counter("p1", "voice_libs_left",
         "voice-only libraries in requirements.txt or requirements-engine.txt")
def p1_voice_libs_left() -> CounterResult:
    files = {name: (REPO_ROOT / name).read_text(encoding="utf-8")
             for name in VOICE_REQUIREMENT_FILES if (REPO_ROOT / name).exists()}
    hits = voice_lib_hits(files)
    return CounterResult(len(hits), "; ".join(hits) or "none")


@counter("p1", "submodule_left", "1 while .gitmodules or the voice_training/voxplot gitlink exists")
def p1_submodule_left() -> CounterResult:
    proc = subprocess.run(["git", "ls-files", "-s", "voice_training/voxplot"], cwd=REPO_ROOT,
                          capture_output=True, text=True)
    left = [what for what, there in ((".gitmodules", (REPO_ROOT / ".gitmodules").exists()),
                                     ("the gitlink", proc.stdout.startswith("160000")))
            if there]
    return CounterResult(1 if left else 0, " and ".join(left) or "gone")


@counter("p1", "device_checklist_open",
         "the owner's phone checks not yet confirmed (docs/rebuild/owner_checks.json, p1)")
def p1_device_checklist_open() -> CounterResult:
    open_items = []
    for key, label in P1_DEVICE_CHECKS.items():
        verdict = _owner_check("p1", key)
        if verdict is not True:
            open_items.append(label + (" (reported failing)" if verdict is False else " (not checked)"))
    return CounterResult(len(open_items), "; ".join(open_items) or "all confirmed")


review("p1",
       "The health app opens with three tabs and no Voice Training; Home, Training and Insights work.",
       "The voice app opens from its own icon and records.",
       "The [voxplot_supabase] section is removed from the health app's Streamlit secrets.")


# ── Phase 2 counters: the engine API ─────────────────────────────────────────

SCREEN_INVENTORY = REBUILD_DOCS / "screen_inventory.md"
INVENTORY_ENDPOINTS = REBUILD_DOCS / "inventory_endpoints.json"
VIEW_LOGIC_MOVES = REBUILD_DOCS / "view_logic_moves.json"
FAULTS = REBUILD_DOCS / "faults.json"
OPENAPI_JSON = REPO_ROOT / "shared" / "openapi.json"
GENERATED_TYPES = REPO_ROOT / "app" / "src" / "generated" / "api.ts"
API_DIR = REPO_ROOT / "api" / "healthapi"
_ROW_ID = re.compile(r"^(H|T|I)\d+$")
_HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _table_rows(markdown: str):
    """(section, cells) for each table row whose first cell is an inventory row
    id. The section is the two characters after "## ": D1, D2 and D3 are the
    decision tables, anything else is a screen's own table."""
    section = ""
    for line in markdown.splitlines():
        if line.startswith("## "):
            section = line[3:5]
        if line.startswith("| "):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and _ROW_ID.match(cells[0]):
                yield section, cells


def _proposal(cell: str) -> str:
    """KEEP, MOVE or DROP from the first word of a proposal cell, else ""."""
    word = cell.replace("*", "").split(" ", 1)[0].strip("(").upper()
    return word if word in ("KEEP", "MOVE", "DROP") else ""


def inventory_rows(markdown: str) -> dict[str, str]:
    """{row id: KEEP, MOVE, DROP or ""} for every row of the screens' tables:
    the first word of the last column ("Nothing to inventory" and "(see I13)"
    read as ""). The owner's decision in D1 wins: a DROP he kept is KEEP."""
    rows: dict[str, str] = {}
    kept: list[str] = []
    for section, cells in _table_rows(markdown):
        if section == "D1":
            if _proposal(cells[-1]) == "KEEP":
                kept.append(cells[0])
        elif section not in ("D2", "D3"):
            rows[cells[0]] = _proposal(cells[-1])
    rows.update({rid: "KEEP" for rid in kept})
    return rows


def drop_decisions(markdown: str) -> set[str]:
    """Ids whose D1 row carries the owner's decision: approved, or kept."""
    return {cells[0] for section, cells in _table_rows(markdown)
            if section == "D1" and (re.search(r"(?<!not )\bapproved\b", cells[-1])
                                    or _proposal(cells[-1]) == "KEEP")}


def _as_list(value) -> list[str]:
    if not value:
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def _ref_exists(ref: str) -> bool:
    """`path::name` names a repo file that defines `name` (a function, a class
    or a module-level name). A test id may carry its class and [parameters];
    a bare path needs only the file."""
    path, _, name = (ref or "").partition("::")
    target = REPO_ROOT / path
    if not path or not target.is_file():
        return False
    name = name.rsplit("::", 1)[-1].split("[", 1)[0]
    if not name:
        return True
    pattern = (rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b"
               rf"|^{re.escape(name)}\s*[:=]")
    return re.search(pattern, target.read_text(encoding="utf-8"), flags=re.MULTILINE) is not None


def openapi_operations(spec: dict) -> set[str]:
    """"METHOD /path" for every operation in an OpenAPI document."""
    return {f"{method.upper()} {path}" for path, ops in (spec.get("paths") or {}).items()
            for method in ops if method in _HTTP_METHODS}


def unmapped_rows(rows: dict[str, str], mapping: dict[str, dict], operations: set[str],
                  ref_exists=_ref_exists) -> list[str]:
    """KEEP or MOVE rows that map neither to endpoints of the contract with
    tests that exist ({"endpoint": "GET /api/x" or a list, "test": ...}) nor to
    the phone alone with a reason ({"client": "phone", "why": "..."})."""
    missing = []
    for rid, word in rows.items():
        if word not in ("KEEP", "MOVE"):
            continue
        entry = mapping.get(rid) or {}
        phone_only = entry.get("client") == "phone" and str(entry.get("why") or "").strip()
        endpoints, tests = _as_list(entry.get("endpoint")), _as_list(entry.get("test"))
        served = (endpoints and tests and all(e in operations for e in endpoints)
                  and all(ref_exists(t) for t in tests))
        if not (phone_only or served):
            missing.append(rid)
    return missing


def open_items(entries: list[dict], needs: tuple[str, ...], ref_exists=_ref_exists) -> list[str]:
    """Ids of entries where a field in `needs` is empty, or names a file and a
    definition that do not exist ("services/x.py::fn", "tests/x.py::test_y").

    An entry the owner approved to DROP carries "dropped" (the date) and
    "gone" (what was removed) instead: it is closed once none of "gone"
    exists any more, so a drop counts only when its code is really gone."""
    def closed(e: dict) -> bool:
        if e.get("dropped"):
            gone = _as_list(e.get("gone"))
            return bool(gone) and not any(ref_exists(r) for r in gone)
        return all(_as_list(e.get(k)) and all(ref_exists(r) for r in _as_list(e.get(k)))
                   for k in needs)
    return [e.get("id", "?") for e in entries if not closed(e)]


def _open_list(ids: list[str], limit: int = 30) -> str:
    if not ids:
        return ""
    more = f" and {len(ids) - limit} more" if len(ids) > limit else ""
    return "; open: " + ", ".join(ids[:limit]) + more


def _json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _pytest_file_failures(phase: str, test_file: str) -> CounterResult:
    """Failures and errors in one test file, plus 1 when nothing in it passed:
    a missing file, an empty one or one that only skips proves nothing."""
    if not (REPO_ROOT / test_file).is_file():
        return CounterResult(1, f"{test_file} does not exist yet")
    if not main_python().exists():
        return CounterResult(1, "venv/ is missing")
    out = REPORTS_DIR / phase
    stem = Path(test_file).stem
    junit, log = out / f"{stem}.xml", out / f"{stem}.log"
    if not (REUSE_TEST_RUNS and junit.exists()):
        _run_pytest(main_python(), junit, log, target=test_file)
    if not junit.exists():
        return CounterResult(1, "pytest wrote no junit file", [f"{phase}/{stem}.log"])
    s = read_junit(junit)
    none_passed = 1 if s.passed == 0 else 0
    return CounterResult(s.failures + s.errors + none_passed,
                         f"{s.passed} passed, {s.failures} failed, {s.errors} errors"
                         + ("; nothing passed" if none_passed else ""),
                         [f"{phase}/{stem}.log"])


#: Reads of the server's own day the API may keep: "path::function" -> reason.
SERVER_CLOCK_ALLOWED = {
    "api/healthapi/routes/health.py::health":
        "the diagnostic server_local_date, shown so a missing TZ is visible",
}


def _clock_call(node: ast.AST) -> str | None:
    """"today", "now" or "utcnow" when `node` is date.X() or datetime.X()."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("today", "now", "utcnow")):
        return None
    base = node.func.value
    name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
    return node.func.attr if name in ("date", "datetime") else None


def _reads_server_day(node: ast.Call) -> bool:
    """date.today(), datetime.today(), datetime.now() with no time zone (the
    server's wall clock), and .date() taken straight off any now() or utcnow().
    datetime.now(timezone.utc) on its own is an instant (a start time, a
    token's expiry), not the caller's day."""
    kind = _clock_call(node)
    if kind == "today" or (kind == "now" and not node.args and not node.keywords):
        return True
    return (isinstance(node.func, ast.Attribute) and node.func.attr == "date"
            and not node.args and _clock_call(node.func.value) is not None)


def server_clock_hits(files: dict[str, str]) -> list[str]:
    """"path:line" for each read of the server's own day outside the allowed
    functions (rebuild rule 3: the phone sends its date)."""
    hits: list[str] = []
    for rel, text in files.items():
        lines: set[int] = set()

        def visit(node: ast.AST, function: str) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = node.name
            if (isinstance(node, ast.Call) and _reads_server_day(node)
                    and f"{rel}::{function}" not in SERVER_CLOCK_ALLOWED):
                lines.add(node.lineno)
            for child in ast.iter_child_nodes(node):
                visit(child, function)

        visit(ast.parse(text), "")
        hits += [f"{rel}:{n}" for n in sorted(lines)]
    return hits


#: Modules that reach the store without Repository: a write through one skips
#: the Supabase-first path (rebuild rule 5).
STORE_BYPASS_MODULES = {"sqlite3", "supabase_store", "datastore_writer"}


def write_bypass_hits(files: dict[str, str]) -> list[str]:
    """"path:line" for each import of sqlite3, services.supabase_store or the
    datastore writer."""
    hits = []
    for rel, text in files.items():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [module] + [f"{module}.{alias.name}" for alias in node.names]
            else:
                continue
            if any(set(name.split(".")) & STORE_BYPASS_MODULES for name in names):
                hits.append(f"{rel}:{node.lineno}")
    return hits


def _api_texts() -> dict[str, str]:
    return {str(p.relative_to(REPO_ROOT)).replace("\\", "/"): p.read_text(encoding="utf-8")
            for p in sorted(API_DIR.rglob("*.py"))}


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n")


@counter("p2", "tests_failing",
         "main gate failures in venv/ (tests/api included), plus 1 if the pass count is under the floor")
def p2_tests_failing() -> CounterResult:
    return _main_gate_counter("p2")


@counter("p2", "inventory_unmapped",
         "KEEP or MOVE inventory rows without an endpoint of the contract and a test, "
         "or a reason they live on the phone alone")
def p2_inventory_unmapped() -> CounterResult:
    rows = inventory_rows(SCREEN_INVENTORY.read_text(encoding="utf-8"))
    mapping = _json(INVENTORY_ENDPOINTS, {}).get("rows", {})
    missing = unmapped_rows(rows, mapping, openapi_operations(_json(OPENAPI_JSON, {})))
    needed = sum(1 for word in rows.values() if word in ("KEEP", "MOVE"))
    return CounterResult(len(missing), f"{needed - len(missing)} of {needed} rows mapped"
                         + _open_list(missing))


@counter("p2", "view_logic_left",
         "calculations an endpoint needs that still live only in a view "
         "(docs/rebuild/view_logic_moves.json)")
def p2_view_logic_left() -> CounterResult:
    entries = _json(VIEW_LOGIC_MOVES, {}).get("moves", [])
    left = open_items(entries, ("service", "test"))
    return CounterResult(len(left), f"{len(entries) - len(left)} of {len(entries)} moved"
                         + _open_list(left))


@counter("p2", "faults_open",
         "inventory faults (docs/rebuild/faults.json) without a test that proves the fix")
def p2_faults_open() -> CounterResult:
    entries = _json(FAULTS, {}).get("faults", [])
    left = open_items(entries, ("test",))
    return CounterResult(len(left), f"{len(entries) - len(left)} of {len(entries)} fixed"
                         + _open_list(left))


@counter("p2", "idempotency_fail", "failing save-replay tests (tests/api/test_save_idempotency.py)")
def p2_idempotency_fail() -> CounterResult:
    return _pytest_file_failures("p2", "tests/api/test_save_idempotency.py")


@counter("p2", "supabase_write_bypass",
         "API imports that reach the store around Repository (sqlite3, supabase_store, "
         "datastore_writer)")
def p2_supabase_write_bypass() -> CounterResult:
    hits = write_bypass_hits(_api_texts())
    return CounterResult(len(hits), "; ".join(hits) or "none")


@counter("p2", "date_from_server", "API reads of the server's own day (rebuild rule 3)")
def p2_date_from_server() -> CounterResult:
    hits = server_clock_hits(_api_texts())
    return CounterResult(len(hits), "; ".join(hits) or "none")


@counter("p2", "background_writer_leaks",
         "failing background_writer tests (tests/test_background_writer.py)")
def p2_background_writer_leaks() -> CounterResult:
    return _pytest_file_failures("p2", "tests/test_background_writer.py")


@counter("p2", "schema_stale", "shared/openapi.json or app/src/generated/api.ts out of date")
def p2_schema_stale() -> CounterResult:
    stale = []
    env = {**_child_env(), "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(API_DIR.parent)])}
    proc = subprocess.run([str(main_python()), "-m", "healthapi.export_openapi", "--check"],
                          cwd=REPO_ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        stale.append("shared/openapi.json")
    pnpm = shutil.which("pnpm")
    if not pnpm:
        stale.append("app/src/generated/api.ts (pnpm is not on PATH)")
    elif not GENERATED_TYPES.exists():
        stale.append("app/src/generated/api.ts (missing)")
    else:
        fresh = REPORTS_DIR / "p2" / "api.check.ts"
        fresh.parent.mkdir(parents=True, exist_ok=True)
        fresh.unlink(missing_ok=True)
        subprocess.run([pnpm, "exec", "openapi-typescript", str(OPENAPI_JSON), "-o", str(fresh)],
                       cwd=REPO_ROOT, env=_child_env(), capture_output=True)
        if not fresh.exists() or _lf(fresh.read_text(encoding="utf-8")) != _lf(
                GENERATED_TYPES.read_text(encoding="utf-8")):
            stale.append("app/src/generated/api.ts")
    return CounterResult(len(stale), ", ".join(stale) or "both current")


@counter("p2", "drops_without_approval", "DROP rows without the owner's recorded decision in D1")
def p2_drops_without_approval() -> CounterResult:
    text = SCREEN_INVENTORY.read_text(encoding="utf-8")
    decided = drop_decisions(text)
    missing = [rid for rid, word in inventory_rows(text).items()
               if word == "DROP" and rid not in decided]
    return CounterResult(len(missing), ", ".join(missing) or "every drop decided")


@counter("p2", "streamlit_app_broken",
         "1 unless the owner confirmed the hosted Streamlit app works after the Phase 2 push")
def p2_streamlit_app_broken() -> CounterResult:
    verdict = _owner_check("p2", "streamlit_app_opens")
    if verdict is True:
        return CounterResult(0, "the owner confirmed it works")
    return CounterResult(1, "the owner reported it broken" if verdict is False
                         else "not confirmed yet (docs/rebuild/owner_checks.json)")


review("p2",
       "Open Check-in on a day that already has an entry: it opens filled in, and pain can go back to 0.",
       "After the push, Home, Training, Insights and Check-in still work in the hosted app.",
       "Three sample API responses, personal values masked, look right.")


# ── Phase 3 counters ─────────────────────────────────────────────────────────

APP_SRC = REPO_ROOT / "app" / "src"
DESIGN_MD = REBUILD_DOCS / "design.md"
STRINGS_TS = APP_SRC / "strings.ts"
MAKE_MOCK = REPO_ROOT / "app" / "scripts" / "make-mock.ts"
_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
_CSS_SIZE = re.compile(r"\d(?:px|rem|em)\b")
_BASE_FONT = re.compile(r"^\s*font-size:\s*17px;")
_TS_STRING = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`")


def owner_choice(text: str) -> str | None:
    """The owner's own words on design.md's choice line:  **Owner's choice** ... *"..."*"""
    match = re.search(r"^\*\*Owner's choice\*\*[^\n]*?\*\"([^\"]+)\"\*", text, re.MULTILINE)
    return match.group(1) if match else None


def _blank_comments(text: str) -> str:
    """Comments emptied in place, so line numbers stay the file's own."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.DOTALL)
    return "\n".join("" if line.strip().startswith("//") else line for line in text.split("\n"))


def token_misses(files: dict[str, str]) -> list[str]:
    """`path:line kind` for every colour a screen file writes, and every size the
    stylesheet writes, outside app/src/design/tokens.ts (the one place they are written).
    The stylesheet's base font size (17px, the size 1rem falls back to) is the exception."""
    hits = []
    for rel, text in sorted(files.items()):
        is_css = rel.endswith(".css")
        for number, line in enumerate(_blank_comments(text).split("\n"), 1):
            if _COLOUR.search(line):
                hits.append(f"{rel}:{number} colour")
            elif is_css and ":" in line and _CSS_SIZE.search(line) and not _BASE_FONT.match(line):
                hits.append(f"{rel}:{number} size")
    return hits


def _screen_files() -> dict[str, str]:
    files = {}
    for path in sorted(APP_SRC.rglob("*")):
        if path.suffix in (".tsx", ".css") and not {"mock", "generated"} & set(path.parts):
            files[path.relative_to(REPO_ROOT).as_posix()] = path.read_text(encoding="utf-8")
    return files


def ts_string_literals(text: str) -> list[str]:
    """Every quoted or template string in a TypeScript file, comments left out."""
    return [next(g for g in m.groups() if g is not None)
            for m in _TS_STRING.finditer(_blank_comments(text))]


def text_rule_hits(literals: list[str]) -> list[str]:
    """Strings that fail the screen-text scanners already in tests/: the jargon, the
    repo-internal and the hedge lists (Key Rule 19, the patient-facing text rules), and
    no Stage 1 text."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tests.test_cluster_a import _HEDGES, _JARGON, _REPO_INTERNALS
    from tests.test_no_stage_one_on_screen import _STAGE_ONE
    hits = []
    for text in literals:
        low = text.lower()
        hits += [f"{word!r} in {text[:48]!r}" for word in (*_JARGON, *_REPO_INTERNALS, *_HEDGES)
                 if word in low]
        if _STAGE_ONE.search(text):
            hits.append(f"Stage 1 in {text[:48]!r}")
    return hits


@counter("p3", "choice_missing", "1 until the owner's choice is recorded in docs/rebuild/design.md")
def p3_choice_missing() -> CounterResult:
    if not DESIGN_MD.exists():
        return CounterResult(1, "docs/rebuild/design.md is missing")
    words = owner_choice(DESIGN_MD.read_text(encoding="utf-8"))
    if not words:
        return CounterResult(1, "design.md has no **Owner's choice** line with his words")
    return CounterResult(0, f'recorded: "{words}"')


@counter("p3", "tokens_unused",
         "colours a screen file writes, and sizes the stylesheet writes, instead of a token")
def p3_tokens_unused() -> CounterResult:
    hits = token_misses(_screen_files())
    return CounterResult(len(hits), "; ".join(hits) or "every colour and size is a token")


@counter("p3", "real_data_in_app",
         "1 when app/src/mock/data.ts is not exactly the seeded generator's output")
def p3_real_data_in_app() -> CounterResult:
    node = shutil.which("node")
    if not node:
        return CounterResult(1, "node is not on PATH")
    proc = subprocess.run([node, str(MAKE_MOCK), "--check"], cwd=REPO_ROOT, env=_child_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = (proc.stdout + proc.stderr).strip().splitlines()
    return CounterResult(0 if proc.returncode == 0 else 1,
                         lines[-1] if lines else f"make-mock --check exited {proc.returncode}")


@counter("p3", "text_rule_violations",
         "strings in app/src/strings.ts that fail the jargon, hedge and Stage 1 scans in tests/")
def p3_text_rule_violations() -> CounterResult:
    if not STRINGS_TS.exists():
        return CounterResult(1, "app/src/strings.ts is missing")
    literals = ts_string_literals(STRINGS_TS.read_text(encoding="utf-8"))
    hits = text_rule_hits(literals)
    return CounterResult(len(hits), "; ".join(hits) or f"{len(literals)} strings, none flagged")


@counter("p3", "test_failures",
         "the main gate's failures in venv/ (plus 1 under the floor) and `pnpm test`'s (Vitest)")
def p3_test_failures() -> CounterResult:
    main_gate = _main_gate_counter("p3")
    vitest = _pnpm_test_counter("p3")
    return CounterResult(main_gate.count + vitest.count,
                         f"Python: {main_gate.detail}; pnpm: {vitest.detail}",
                         main_gate.evidence + vitest.evidence)


review("p3",
       "Open the preview from the iPhone's Home Screen: Today, Training, Insights and Settings, "
       "in light and dark.",
       "On the Training tab, let the timer run and read it from 1.5 m away.",
       "Say yes to the design, or what to change.")


# ── Phase 4 counters ─────────────────────────────────────────────────────────

SW_SOURCE = APP_SRC / "sw" / "sw.ts"
WRANGLER = REPO_ROOT / "worker" / "wrangler.jsonc"
DATA_CHECK = REPO_ROOT / "scripts" / "data_check.py"
#: The owner's iPhone checklist (docs/rebuild/owner_checks.json, "p4"): true = works.
P4_CHECKLIST = {
    "install": "Safari > Share > Add to Home Screen; Health opens from its icon, with no browser bars",
    "key": "the access key, pasted once, opens the app",
    "tabs": "Today, Check-in (a sheet), Training, Insights and Settings each open",
    "airplane": "in airplane mode the app opens from the Home Screen",
    "reopen": "closed and reopened, it opens on the same data; Settings says it shows saved data",
    "engine_down": "with Settings > Testing > Act as if the engine is down, every screen still shows",
}
_PW_REPORTS: dict[str, dict | None] = {}


def playwright_report(phase: str) -> dict | None:
    """The browser tests' JSON report: run once per gate run (minutes), then reused by
    every counter that reads it. None when the run gave no report."""
    if phase in _PW_REPORTS:
        return _PW_REPORTS[phase]
    out = REPORTS_DIR / phase
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "playwright.json"
    if not (REUSE_TEST_RUNS and json_path.exists()):
        json_path.unlink(missing_ok=True)
        pnpm = shutil.which("pnpm")
        if pnpm:
            proc = subprocess.run([pnpm, "--filter", "@health/app", "exec", "playwright", "test",
                                   "--reporter=json"], cwd=REPO_ROOT, env=_child_env(),
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            json_path.write_text(proc.stdout, encoding="utf-8", newline="\n")
            (out / "playwright.log").write_text(proc.stderr, encoding="utf-8", newline="\n")
    try:
        report = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    _PW_REPORTS[phase] = report
    return report


def playwright_tests(report: dict) -> list[dict]:
    """Every test of a Playwright JSON report, flat: its title, browser, last status and
    annotations."""
    out: list[dict] = []

    def walk(suite: dict) -> None:
        for child in suite.get("suites", []):
            walk(child)
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                results = test.get("results") or []
                out.append({"title": spec.get("title", ""), "project": test.get("projectName", ""),
                            "status": results[-1].get("status") if results else "none",
                            "annotations": test.get("annotations", [])})

    for suite in report.get("suites", []):
        walk(suite)
    return out


def _browser_counter(phase: str, pick, count) -> CounterResult:
    report = playwright_report(phase)
    if report is None:
        return CounterResult(1, "the browser tests gave no report", [f"{phase}/playwright.log"])
    tests = [t for t in playwright_tests(report) if pick(t["title"])]
    if not tests:
        return CounterResult(1, "no browser test of this kind ran", [f"{phase}/playwright.json"])
    return count(tests)


def failed_tests(tests: list[dict]) -> list[str]:
    return [f'{t["project"]}: {t["title"]}' for t in tests if t["status"] != "passed"]


def outbox_losses(tests: list[dict]) -> tuple[int, list[str]]:
    """Writes lost over the outbox tests: each test's own count (its outbox_loss
    annotation), and 1 for a test that failed before it could count."""
    lost, notes = 0, []
    for t in tests:
        counts = [int(a["description"]) for a in t["annotations"]
                  if a.get("type") == "outbox_loss" and str(a.get("description", "")).lstrip("-").isdigit()]
        if counts:
            lost += sum(counts)
            notes += [f'{t["project"]}: {t["title"]}: {sum(counts)} lost'] if sum(counts) else []
        elif t["status"] != "passed":
            lost += 1
            notes.append(f'{t["project"]}: {t["title"]}: failed before it counted')
    return lost, notes


def sw_api_routes(text: str) -> list[str]:
    """Ways the service worker source could answer /api: a route other than the page
    route that names /api, or a page route without the /api denylist."""
    code = _blank_comments(text)
    calls = [m.group(0) for m in re.finditer(r"registerRoute\((?:[^()]|\([^()]*\))*\)", code)]
    hits = []
    for call in calls:
        if "NavigationRoute" in call:
            if not re.search(r"denylist:\s*\[[^\]]*\\/api", call):
                hits.append("the page route has no /api denylist")
        elif "api" in call:
            hits.append(f"a route names /api: {call[:60]}")
    return hits


def jsonc(text: str):
    """JSON with // and /* */ comments (wrangler.jsonc), strings left alone."""
    out, i, n, in_string = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            i = text.find("*/", i + 2)
            i = n if i < 0 else i + 2
            continue
        else:
            out.append(ch)
        i += 1
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))


def checklist_open(data: dict) -> list[str]:
    """The checklist items the owner has not confirmed (false = reported failing)."""
    answers = data.get("p4", {})
    return [key for key in P4_CHECKLIST if answers.get(key) is not True]


@counter("p4", "test_failures",
         "failures in the Python gate (plus 1 under the floor), `pnpm test` (the app's and the "
         "Worker's Vitest, after the build) and the browser tests (Playwright)")
def p4_test_failures() -> CounterResult:
    main_gate = _main_gate_counter("p4")
    vitest = _pnpm_test_counter("p4")
    report = playwright_report("p4")
    if report is None:
        browser = CounterResult(1, "no report", ["p4/playwright.log"])
    else:
        stats = report.get("stats", {})
        failed = int(stats.get("unexpected", 0)) + int(stats.get("flaky", 0))
        browser = CounterResult(failed, f'{stats.get("expected", 0)} passed, {failed} failed '
                                        f'or flaky', ["p4/playwright.json"])
    return CounterResult(main_gate.count + vitest.count + browser.count,
                         f"Python: {main_gate.detail}; pnpm: {vitest.detail}; "
                         f"Playwright: {browser.detail}",
                         main_gate.evidence + vitest.evidence + browser.evidence)


@counter("p4", "offline_boot_fail", "1 if the app shell fails to load offline (the @offline browser test)")
def p4_offline_boot_fail() -> CounterResult:
    def count(tests):
        failed = failed_tests(tests)
        return CounterResult(1 if failed else 0, "; ".join(failed) or "opens in airplane mode",
                             ["p4/playwright.json"])
    return _browser_counter("p4", lambda title: "airplane mode" in title, count)


@counter("p4", "blank_screen_with_engine_down",
         "screens that render nothing when the engine is down (one browser test per screen and "
         "browser)")
def p4_blank_screen_with_engine_down() -> CounterResult:
    def count(tests):
        failed = failed_tests(tests)
        return CounterResult(len(failed), "; ".join(failed) or f"{len(tests)} screen runs, none blank",
                             ["p4/playwright.json"])
    return _browser_counter("p4", lambda title: title.startswith("with the engine down, "), count)


@counter("p4", "outbox_loss", "writes lost in the outbox browser tests")
def p4_outbox_loss() -> CounterResult:
    def count(tests):
        lost, notes = outbox_losses(tests)
        return CounterResult(lost, "; ".join(notes) or f"{len(tests)} outbox tests, nothing lost",
                             ["p4/playwright.json"])
    return _browser_counter("p4", lambda title: title.endswith("@outbox"), count)


@counter("p4", "api_cached_by_sw",
         "1 if the service worker caches an /api answer: a route for /api in its source, or an "
         "/api entry in its caches in the browser test")
def p4_api_cached_by_sw() -> CounterResult:
    hits = sw_api_routes(SW_SOURCE.read_text(encoding="utf-8")) if SW_SOURCE.exists() else ["no sw.ts"]

    def count(tests):
        failed = failed_tests(tests)
        return CounterResult(1 if failed or hits else 0, "; ".join(hits + failed)
                             or "no /api route, and no /api entry in its caches", ["p4/playwright.json"])
    return _browser_counter("p4", lambda title: "caches no /api answer" in title, count)


#: The switch-over (rebuild Phase 9, docs/rebuild/switch_plan.md), done with the owner on
#: 2026-10-21: from it the engine is the one background writer and the Worker's sync
#: addresses are on (step 4). Its rollback sets this back to None with SYNC_ENABLED "false".
SWITCHED_OVER: str | None = "2026-10-21"


@counter("p4", "cron_enabled_early",
         "1 if worker/wrangler.jsonc sets SYNC_ENABLED to anything but \"false\" before the "
         "switch-over (Phase 9), or to anything but \"true\" after it")
def p4_cron_enabled_early() -> CounterResult:
    config = jsonc(WRANGLER.read_text(encoding="utf-8"))
    value = config.get("vars", {}).get("SYNC_ENABLED")
    crons = config.get("triggers", {}).get("crons", [])
    want = "true" if SWITCHED_OVER else "false"
    when = f"after the switch-over of {SWITCHED_OVER}" if SWITCHED_OVER else "before the switch-over"
    return CounterResult(0 if value == want else 1,
                         f"SYNC_ENABLED = {value!r} ({when}); triggers: {', '.join(crons) or 'none'}")


@counter("p4", "mirror_gaps_open",
         "rows the daily data check reports missing from Supabase, not repaired yet "
         "(scripts/data_check.py: the newest backup against the store, read only)")
def p4_mirror_gaps_open() -> CounterResult:
    if not main_python().exists():
        return CounterResult(1, "venv/ is missing")
    proc = subprocess.run([str(main_python()), str(DATA_CHECK), "--json"], cwd=REPO_ROOT,
                          env=_child_env(), capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    out = REPORTS_DIR / "p4"
    out.mkdir(parents=True, exist_ok=True)
    (out / "data-check.json").write_text(proc.stdout, encoding="utf-8", newline="\n")
    try:
        result = json.loads(proc.stdout)
    except ValueError:
        return CounterResult(1, f"the check gave no answer (exit {proc.returncode})", ["p4/data-check.json"])
    if "error" in result:
        return CounterResult(1, f"the check did not run: {result['error']}", ["p4/data-check.json"])
    missing = int(result.get("missing_rows", 0))
    stale = " (the backup is older than two days)" if result.get("backup_stale") else ""
    return CounterResult(missing, f"{missing} rows missing against {result.get('backup_name') or 'no backup'}"
                         f"{stale}", ["p4/data-check.json"])


@counter("p4", "device_checklist_open",
         "items of the owner's iPhone checklist not confirmed yet (docs/rebuild/owner_checks.json, p4)")
def p4_device_checklist_open() -> CounterResult:
    data = json.loads(OWNER_CHECKS.read_text(encoding="utf-8")) if OWNER_CHECKS.exists() else {}
    missing = checklist_open(data)
    return CounterResult(len(missing), ", ".join(missing) or "the owner confirmed every item")


review("p4", *P4_CHECKLIST.values())


# ── Phase 5 counters ─────────────────────────────────────────────────────────

APP_ROWS = REBUILD_DOCS / "app_rows.json"
PARITY = REPO_ROOT / "scripts" / "rebuild_parity.py"
#: The inventory's I rows that belong to Phase 5's screens (the H rows all do).
P5_SCREENS = ("Check-in", "Home", "Sleep")
#: The owner's two mornings (docs/rebuild/owner_checks.json, "p5"): true = as expected.
P5_CHECKLIST = {
    "morning1_scores": "Morning 1: the three scores in the new app equal the Streamlit app's",
    "morning1_sleep": "Morning 1: the sleep night (asleep, in bed, stages) equals the Streamlit app's",
    "morning2_scores": "Morning 2: the three scores equal again",
    "morning2_sleep": "Morning 2: the sleep night equals again",
    "morning2_checkin": "Morning 2: the check-in made in the new app saves",
    "morning2_checkin_in_streamlit": "Morning 2: the Streamlit app shows that check-in within about 15 minutes",
}
_PARITY_REPORTS: dict[str, dict | None] = {}


def p5_rows(markdown: str) -> list[str]:
    """The KEEP rows Phase 5 must build: every Home row, and the I rows of the
    Check-in, Home and Sleep screens."""
    words = inventory_rows(markdown)
    screens = {cells[0]: cells[1] for section, cells in _table_rows(markdown)
               if section not in ("D1", "D2", "D3")}
    ids = [rid for rid, word in words.items() if word == "KEEP"
           and (rid.startswith("H") or (rid.startswith("I") and screens.get(rid) in P5_SCREENS))]
    return sorted(ids, key=lambda rid: (rid[0], int(rid[1:])))


def app_rows_open(rows: list[str], mapping: dict, owner_words: str, root: Path | None = None) -> list[str]:
    """Rows not built: no entry, no file or no test named, a named file that does not
    exist, or a 'replaced' entry whose words are not the owner's recorded words."""
    root = root or REPO_ROOT
    out = []
    for rid in rows:
        entry = mapping.get(rid)
        if not entry:
            out.append(f"{rid} not mapped")
            continue
        if entry.get("replaced") is not None:
            words = str(entry["replaced"]).strip()
            if not words or words not in owner_words:
                out.append(f"{rid} replaced without the owner's recorded words")
            continue
        built = _as_list(entry.get("built"))
        test = str(entry.get("test") or "")
        if not built or not test:
            out.append(f"{rid} names no file or no test")
            continue
        missing = [f for f in [*built, test] if not (root / f).exists()]
        if missing:
            out.append(f"{rid}: {', '.join(missing)} missing")
    return out


#: The phases whose parity run compares the Insights answers (--insights).
PARITY_INSIGHTS_PHASES = {"p8"}


def parity_report(phase: str) -> dict | None:
    """scripts/rebuild_parity.py --json: run once per gate run (it reads the live
    engine and the store), then reused by the counters that read it. Phase 8 runs
    it over the Insights answers (--insights)."""
    if phase in _PARITY_REPORTS:
        return _PARITY_REPORTS[phase]
    out = REPORTS_DIR / phase
    out.mkdir(parents=True, exist_ok=True)
    path = out / "parity.json"
    if not (REUSE_TEST_RUNS and path.exists()):
        path.unlink(missing_ok=True)
        if parity_python().exists():
            mode = ["--insights"] if phase in PARITY_INSIGHTS_PHASES else []
            proc = subprocess.run([str(parity_python()), str(PARITY), *mode, "--json"], cwd=REPO_ROOT,
                                  env=_child_env(), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            path.write_text(proc.stdout, encoding="utf-8", newline="\n")
            (out / "parity.log").write_text(proc.stderr, encoding="utf-8", newline="\n")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    _PARITY_REPORTS[phase] = report
    return report


def annotation_total(tests: list[dict], kind: str) -> tuple[int, list[str]]:
    """The sum of a count the browser tests record as an annotation, and 1 for a test
    that failed before it could record it."""
    total, notes = 0, []
    for t in tests:
        counts = [int(a["description"]) for a in t["annotations"]
                  if a.get("type") == kind and str(a.get("description", "")).lstrip("-").isdigit()]
        if counts:
            total += sum(counts)
            if sum(counts):
                notes.append(f'{t["project"]}: {t["title"]}: {sum(counts)}')
        elif t["status"] != "passed":
            total += 1
            notes.append(f'{t["project"]}: {t["title"]}: failed before it counted')
    return total, notes


@counter("p5", "test_failures",
         "failures in the Python gate (plus 1 under the floor), `pnpm test` (the app's and the "
         "Worker's Vitest, after the build) and the browser tests (Playwright)")
def p5_test_failures() -> CounterResult:
    main_gate = _main_gate_counter("p5")
    vitest = _pnpm_test_counter("p5")
    report = playwright_report("p5")
    if report is None:
        browser = CounterResult(1, "no report", ["p5/playwright.log"])
    else:
        stats = report.get("stats", {})
        failed = int(stats.get("unexpected", 0)) + int(stats.get("flaky", 0))
        browser = CounterResult(failed, f'{stats.get("expected", 0)} passed, {failed} failed or flaky',
                                ["p5/playwright.json"])
    return CounterResult(main_gate.count + vitest.count + browser.count,
                         f"Python: {main_gate.detail}; pnpm: {vitest.detail}; Playwright: {browser.detail}",
                         main_gate.evidence + vitest.evidence + browser.evidence)


@counter("p5", "parity_differences",
         "fields where the live engine and services/ differ over the last 14 days, plus requests "
         "the engine did not answer (scripts/rebuild_parity.py)")
def p5_parity_differences() -> CounterResult:
    report = parity_report("p5")
    if report is None:
        return CounterResult(1, "the parity run gave no report", ["p5/parity.log"])
    diffs, unanswered = report.get("differences", []), report.get("unanswered", [])
    names = [f'{d["date"]} {d["endpoint"]} {d["field"]}' for d in diffs[:10]]
    names += [f'{u["date"]} {u["endpoint"]} unanswered' for u in unanswered[:5]]
    return CounterResult(len(diffs) + len(unanswered),
                         "; ".join(names) or f'{report.get("days")} days up to {report.get("today")}, none',
                         ["p5/parity.json"])


@counter("p5", "sleep_rule_violations",
         "dates where the engine sends a night panel without a score (the parity run's 14 days), "
         "plus failing screen tests of the rule")
def p5_sleep_rule_violations() -> CounterResult:
    report = parity_report("p5")
    dates = list(report.get("sleep_rule_violations", [])) if report else ["no parity report"]

    def count(tests):
        failed = failed_tests(tests)
        return CounterResult(len(dates) + len(failed), "; ".join(dates + failed)
                             or f"none in {report.get('days') if report else 0} days; the screen test passes",
                             ["p5/parity.json", "p5/playwright.json"])
    return _browser_counter("p5", lambda title: "no Sleep Score" in title, count)


@counter("p5", "check_in_lost", "check-ins lost in the outbox browser test")
def p5_check_in_lost() -> CounterResult:
    def count(tests):
        lost, notes = annotation_total(tests, "check_in_lost")
        return CounterResult(lost, "; ".join(notes) or "a check-in made offline was sent, none lost",
                             ["p5/playwright.json"])
    return _browser_counter("p5", lambda title: title.startswith("a check-in made offline"), count)


@counter("p5", "inventory_rows_open",
         "Home and check-in rows marked KEEP that the phone app does not build "
         "(docs/rebuild/app_rows.json: the files and the test)")
def p5_inventory_rows_open() -> CounterResult:
    rows = p5_rows(SCREEN_INVENTORY.read_text(encoding="utf-8"))
    mapping = json.loads(APP_ROWS.read_text(encoding="utf-8"))["rows"] if APP_ROWS.exists() else {}
    owner = DESIGN_MD.read_text(encoding="utf-8") if DESIGN_MD.exists() else ""
    open_ = app_rows_open(rows, mapping, owner)
    return CounterResult(len(open_), "; ".join(open_) or f"{len(rows)} rows built, each with a test")


@counter("p5", "text_rule_violations",
         "strings in app/src/strings.ts that fail the jargon, hedge and Stage 1 scans in tests/")
def p5_text_rule_violations() -> CounterResult:
    return p3_text_rule_violations()


@counter("p5", "device_checklist_open",
         "items of the owner's two-morning checklist not confirmed yet (docs/rebuild/owner_checks.json, p5)")
def p5_device_checklist_open() -> CounterResult:
    data = json.loads(OWNER_CHECKS.read_text(encoding="utf-8")) if OWNER_CHECKS.exists() else {}
    answers = data.get("p5", {})
    missing = [key for key in P5_CHECKLIST if answers.get(key) is not True]
    return CounterResult(len(missing), ", ".join(missing) or "the owner confirmed every item")


review("p5", *P5_CHECKLIST.values())


# ── Phase 6 counters ─────────────────────────────────────────────────────────

FIELD_CHECK_JSON = REPORTS_DIR / "p6" / "field_check.json"
IDEMPOTENCY_TESTS = "tests/api/test_save_idempotency.py"
TIMERS_TEST = "src/lib/timers.test.ts"
#: The training-session rows of the inventory the phone builds (the guided flow, its
#: overview before Start and its save).
P6_ROW_RANGE = range(37, 103)
#: The owner's real session (docs/rebuild/owner_checks.json, "p6"): true = as expected.
P6_CHECKLIST = {
    "session": "One real gym session in the new app, from Start to Save",
    "airplane": "Airplane mode for at least two exercises: the session went on as before",
    "lock_rest": "The phone locked during one rest: back in, the timer showed the right time, or when it ended",
    "read_timer": "The timer reads from 1.5 m away",
    "sounds": "The bells: rest end, hold end, the side switch, the set's end and the exercise's end, with the silent switch on",
    "audio_after_lock": "The sounds still play after a pause on the lock screen",
    "screen_on": "The screen stayed on during the session",
    "saved": "Save showed 'Saved on the phone', then 'Saved'",
    "field_check": "scripts/session_field_check.py: one session stored for the day, no field missing",
    "alerts": "Settings > Timer alerts turned on; a test alert arrives; a rest that ends with the phone locked shows its alert",
}
#: The engine's training and safety rules by name: none may be written into the phone's
#: source (rebuild rule 1; also in camelCase). A field the engine SENDS is not here: the
#: phone reads its value (timer_starts, ask_length_above_minutes, first_side_note).
RULE_NAMES = (
    "hold_ending", "hold_starts_next", "warning_is_due", "WARNING_STRAIN_THRESHOLD",
    "step_block_reason", "hold_for_failed_week", "failed_week_holds_load", "readiness_scales",
    "readiness_dose", "range_progression", "range_middle_bottom", "PROGRESSION_WINDOW_DAYS",
    "STEP_BACK_SESSIONS", "FAILED_WEEK_MAX_DAYS", "duration_needs_a_check", "DURATION_CHECK_RATIO",
    "REST_TAKEN_MAX_SECONDS", "session_au", "dosed_day", "estimate_duration",
    "exercise_duration_seconds", "review_figures", "hr_comparison", "is_timed_test",
    "is_run_or_walk", "GARMIN_ACTIVITY_BUFFER_MINUTES", "HR_COVERAGE_FULL", "volume_recommendation",
)
#: The engine's thresholds written as code (strings and comments are blanked first).
RULE_THRESHOLDS = (
    ("the length question's ratio (1.5 x the model)", re.compile(r"\b1\.5\s*\*|\*\s*1\.5\b")),
    ("the longest rest kept (1200 s)", re.compile(r"\b1_?200\b")),
    ("the reps a weight step costs (0.37)", re.compile(r"\b0\.37\b")),
    ("the warning's strain threshold (16)", re.compile(r"strain[^\n]{0,40}\b16\b|\b16\b[^\n]{0,40}strain", re.I)),
    ("the pain gate (above 5 of 10)", re.compile(r"pain[^\n]{0,30}[<>]=?\s*5\b", re.I)),
)
_PW_ANNOTATION_TESTS = ("a whole session runs from Start to Save", "a save whose answer is lost")
_PYTEST_FILES: dict[tuple[str, str], CounterResult] = {}


def _camel(name: str) -> str:
    head, *rest = name.lower().split("_")
    return head + "".join(w.title() for w in rest)


def _phone_code_files() -> dict[str, str]:
    """The phone's own source: app/src without the generated types, the mock data, the
    test hooks and the tests."""
    files = {}
    for path in sorted(APP_SRC.rglob("*")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if (path.suffix in (".ts", ".tsx") and not {"generated", "mock", "debug"} & set(path.parts)
                and ".test." not in path.name):
            files[rel] = path.read_text(encoding="utf-8")
    return files


def rule_hits(files: dict[str, str]) -> list[str]:
    """Training or safety rules in the phone's source: an engine rule's name (or its
    camelCase), or one of its thresholds written as code."""
    names = [(n, re.compile(rf"\b{re.escape(n)}\b")) for n in RULE_NAMES]
    names += [(_camel(n), re.compile(rf"\b{re.escape(_camel(n))}\b")) for n in RULE_NAMES if "_" in n]
    hits = []
    for rel, text in files.items():
        code = _blank_comments(text)
        bare = _TS_STRING.sub('""', code)
        for number, line in enumerate(code.splitlines(), 1):
            hits += [f"{rel}:{number} {name}" for name, rx in names if rx.search(line)]
        for number, line in enumerate(bare.splitlines(), 1):
            hits += [f"{rel}:{number} {label}" for label, rx in RULE_THRESHOLDS if rx.search(line)]
    return hits


def p6_rows(markdown: str) -> list[str]:
    """The training-session rows (T37-T102) marked KEEP."""
    words = inventory_rows(markdown)
    ids = [rid for rid, word in words.items()
           if word == "KEEP" and rid.startswith("T") and int(rid[1:]) in P6_ROW_RANGE]
    return sorted(ids, key=lambda rid: int(rid[1:]))


def field_check() -> dict | None:
    """The field check of the owner's real session (scripts/session_field_check.py
    --json), once it has run; None before."""
    try:
        return json.loads(FIELD_CHECK_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pytest_once(phase: str, test_file: str) -> CounterResult:
    """One run of a test file per gate run, however many counters read it."""
    key = (phase, test_file)
    if key not in _PYTEST_FILES:
        _PYTEST_FILES[key] = _pytest_file_failures(phase, test_file)
    return _PYTEST_FILES[key]


def _session_annotations(kind: str, real: int, real_note: str) -> CounterResult:
    """A count the session browser tests record as an annotation, plus the real
    session's own count from the field check."""
    def count(tests):
        total, notes = annotation_total(tests, kind)
        return CounterResult(total + real, "; ".join(notes + ([real_note] if real_note else []))
                             or f"{len(tests)} session test runs, none", ["p6/playwright.json"])
    return _browser_counter("p6", lambda title: title.startswith(_PW_ANNOTATION_TESTS), count)


def vitest_file(phase: str, target: str) -> dict | None:
    """One Vitest file's JSON report (numPassedTests, numFailedTests, ...)."""
    pnpm = shutil.which("pnpm")
    if not pnpm:
        return None
    out = REPORTS_DIR / phase
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"vitest-{Path(target).stem}.json"
    if not (REUSE_TEST_RUNS and path.exists()):
        path.unlink(missing_ok=True)
        subprocess.run([pnpm, "--filter", "@health/app", "exec", "vitest", "run", target,
                        "--reporter=json", f"--outputFile={path}"], cwd=REPO_ROOT, env=_child_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@counter("p6", "test_failures",
         "failures in the Python gate (plus 1 under the floor), `pnpm test` (the app's and the "
         "Worker's Vitest, after the build) and the browser tests (Playwright)")
def p6_test_failures() -> CounterResult:
    main_gate = _main_gate_counter("p6")
    vitest = _pnpm_test_counter("p6")
    report = playwright_report("p6")
    if report is None:
        browser = CounterResult(1, "no report", ["p6/playwright.log"])
    else:
        stats = report.get("stats", {})
        failed = int(stats.get("unexpected", 0)) + int(stats.get("flaky", 0))
        browser = CounterResult(failed, f'{stats.get("expected", 0)} passed, {failed} failed or flaky',
                                ["p6/playwright.json"])
    return CounterResult(main_gate.count + vitest.count + browser.count,
                         f"Python: {main_gate.detail}; pnpm: {vitest.detail}; Playwright: {browser.detail}",
                         main_gate.evidence + vitest.evidence + browser.evidence)


@counter("p6", "duplicate_sessions",
         "sessions stored more than once: the replay tests (the engine's three sends, the "
         "phone's lost answer) and, once checked, the owner's real session")
def p6_duplicate_sessions() -> CounterResult:
    engine = _pytest_once("p6", IDEMPOTENCY_TESTS)
    real = field_check()
    real_n = int(real.get("duplicates", 0)) if real else 0
    phone = _session_annotations("duplicate_sessions", real_n,
                                 f"the real session: {real_n} duplicate(s)" if real else "")
    return CounterResult(engine.count + phone.count,
                         f"engine replay: {engine.detail}; phone: {phone.detail}"
                         + ("" if real else "; the real session is checked after it happens"),
                         engine.evidence + phone.evidence)


@counter("p6", "fields_missing",
         "fields the Streamlit save writes and the new save does not: raw facts missing from the "
         "phone's save in the browser tests, the engine's record rule, and the real session's field check")
def p6_fields_missing() -> CounterResult:
    engine = _pytest_once("p6", IDEMPOTENCY_TESTS)
    real = field_check()
    missing = list(real.get("missing", [])) if real else []
    phone = _session_annotations("fields_missing", len(missing),
                                 f"the real session: {', '.join(missing)}" if missing else "")
    return CounterResult(engine.count + phone.count,
                         f"engine: {engine.detail}; phone: {phone.detail}"
                         + ("" if real else "; the real session is checked after it happens"),
                         engine.evidence + phone.evidence)


@counter("p6", "rule_in_typescript",
         "training or safety rules in app/src: an engine rule's name, or one of its thresholds written as code")
def p6_rule_in_typescript() -> CounterResult:
    files = _phone_code_files()
    hits = rule_hits(files)
    return CounterResult(len(hits), "; ".join(hits[:20]) or f"{len(files)} files, no rule")


@counter("p6", "warning_shown_when_not_due",
         "warnings drawn on an exercise the engine sent none for, in the session browser tests")
def p6_warning_shown_when_not_due() -> CounterResult:
    def count(tests):
        total, notes = annotation_total(tests, "warning_shown_when_not_due")
        return CounterResult(total, "; ".join(notes) or f"{len(tests)} session runs, none", ["p6/playwright.json"])
    return _browser_counter("p6", lambda title: title.startswith(_PW_ANNOTATION_TESTS[0]), count)


@counter("p6", "timer_drift",
         "timer errors over 1 s after a simulated background (app/src/lib/timers.test.ts): its "
         "failures, plus 1 when nothing in it passed")
def p6_timer_drift() -> CounterResult:
    report = vitest_file("p6", TIMERS_TEST)
    if report is None:
        return CounterResult(1, "the timer tests gave no report", [f"p6/vitest-timers.test.json"])
    passed, failed = int(report.get("numPassedTests", 0)), int(report.get("numFailedTests", 0))
    return CounterResult(failed + (0 if passed else 1), f"{passed} passed, {failed} failed",
                         ["p6/vitest-timers.test.json"])


@counter("p6", "text_rule_violations",
         "strings in app/src/strings.ts that fail the jargon, hedge and Stage 1 scans in tests/")
def p6_text_rule_violations() -> CounterResult:
    return p3_text_rule_violations()


@counter("p6", "inventory_rows_open",
         "training-session rows (T37-T102) marked KEEP that the phone app does not build "
         "(docs/rebuild/app_rows.json: the files and the test)")
def p6_inventory_rows_open() -> CounterResult:
    rows = p6_rows(SCREEN_INVENTORY.read_text(encoding="utf-8"))
    mapping = json.loads(APP_ROWS.read_text(encoding="utf-8"))["rows"] if APP_ROWS.exists() else {}
    owner = DESIGN_MD.read_text(encoding="utf-8") if DESIGN_MD.exists() else ""
    open_ = app_rows_open(rows, mapping, owner)
    return CounterResult(len(open_), "; ".join(open_) or f"{len(rows)} rows built, each with a test")


@counter("p6", "device_checklist_open",
         "items of the owner's real-session checklist not confirmed yet (docs/rebuild/owner_checks.json, p6)")
def p6_device_checklist_open() -> CounterResult:
    data = json.loads(OWNER_CHECKS.read_text(encoding="utf-8")) if OWNER_CHECKS.exists() else {}
    answers = data.get("p6", {})
    missing = [key for key in P6_CHECKLIST if answers.get(key) is not True]
    return CounterResult(len(missing), ", ".join(missing) or "the owner confirmed every item")


review("p6", *P6_CHECKLIST.values())


# ── Phase 7 counters ─────────────────────────────────────────────────────────

#: The training-week rows of the inventory the phone builds: the page around the session
#: (T1-T36) and the "+" menu (T103-T112).
P7_ROW_RANGES = (range(1, 37), range(103, 113))
#: The owner's training week (docs/rebuild/owner_checks.json, "p7"): true = as expected.
P7_CHECKLIST = {
    "swap": "Swap one day with today (a missed day carried forward, or a future day pulled in)",
    "decline": "Decline one proposed move; the question does not come back",
    "extra": "Log one short extra session (the + button)",
    "yoga": "Log one yoga flow",
    "outdoor": "Log one outdoor activity from Garmin",
    "past_future": "Open a past day and a future day",
    "once": "Every save of the week is stored exactly once",
}
#: The functions that may write `date_overrides`: the one checked path for a move
#: (scheduling.apply_schedule_change runs plan.reject_violating_overrides, Key Rule 18b) and
#: the week repeat, which moves a block's overrides along with its dates (Key Rule 22).
OVERRIDE_WRITERS = {("services/scheduling.py", "apply_schedule_change"),
                    ("services/week_repeat.py", "repeat_week")}
#: The training endpoints and the services behind them: day content comes only from
#: sessions.calendar_plan, never by the authored day number (a repeated week would show the
#: wrong session with no error).
TRAINING_API_FILES = ("api/healthapi/routes/training.py", "services/training_screen.py",
                      "services/training_session.py")
_AUTHORED_IMPORTS = ("training_plan", "goal_block")
_P7_MOVE_TESTS = "tests/api/test_moves_once_and_reads_write_nothing.py"
_P7_WEEK_TITLES = ("the week", "a move", "a swap", "the +", "yoga", "an outdoor", "the extra")


def override_write_hits(files: dict[str, str]) -> list[str]:
    """Writes of `date_overrides` (a keyword in a call, or an assignment to the attribute)
    outside OVERRIDE_WRITERS: a move that could skip Key Rule 18b's check."""
    hits = []
    for rel, text in files.items():
        tree = ast.parse(text)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                targets = getattr(node, "targets", None) or [getattr(node, "target", None)]
                writes = (isinstance(node, ast.keyword) and node.arg == "date_overrides") or (
                    isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)) and any(
                        isinstance(t, ast.Attribute) and t.attr == "date_overrides" for t in targets))
                if writes and (rel, fn.name) not in OVERRIDE_WRITERS:
                    hits.append(f"{rel}:{node.lineno} in {fn.name}")
    return sorted(set(hits))


def authored_lookup_hits(files: dict[str, str]) -> list[str]:
    """Content looked up by the authored day: a call of plan_dict_for_phase, or an import of
    the authored plans, where sessions.calendar_plan is the one way in."""
    hits = []
    for rel, text in files.items():
        if rel.endswith(".py"):
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr == "plan_dict_for_phase":
                    hits.append(f"{rel}:{node.lineno} plan_dict_for_phase")
                if isinstance(node, ast.Import):
                    hits += [f"{rel}:{node.lineno} import {a.name}" for a in node.names
                             if a.name.split(".")[0] in _AUTHORED_IMPORTS]
                if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in _AUTHORED_IMPORTS:
                    hits.append(f"{rel}:{node.lineno} from {node.module}")
        else:
            code = _blank_comments(text)
            for number, line in enumerate(code.splitlines(), 1):
                if "plan_dict_for_phase" in line or re.search(r"\b(training_plan|goal_block)\b", line):
                    hits.append(f"{rel}:{number} an authored plan")
    return hits


def _engine_files() -> dict[str, str]:
    files = {}
    for folder in ("services", "api"):
        for path in sorted((REPO_ROOT / folder).rglob("*.py")):
            files[path.relative_to(REPO_ROOT).as_posix()] = path.read_text(encoding="utf-8")
    return files


def p7_rows(markdown: str) -> list[str]:
    """The training-week rows (T1-T36, T103-T112) marked KEEP."""
    words = inventory_rows(markdown)
    ids = [rid for rid, word in words.items()
           if word == "KEEP" and rid.startswith("T") and any(int(rid[1:]) in r for r in P7_ROW_RANGES)]
    return sorted(ids, key=lambda rid: int(rid[1:]))


def _week_annotations(phase: str, kind: str) -> CounterResult:
    def count(tests):
        total, notes = annotation_total(tests, kind)
        return CounterResult(total, "; ".join(notes) or f"{len(tests)} week test runs, none",
                             [f"{phase}/playwright.json"])
    return _browser_counter(phase, lambda title: title.lower().startswith(_P7_WEEK_TITLES), count)


@counter("p7", "test_failures",
         "failures in the Python gate (plus 1 under the floor), `pnpm test` (the app's and the "
         "Worker's Vitest, after the build) and the browser tests (Playwright)")
def p7_test_failures() -> CounterResult:
    main_gate = _main_gate_counter("p7")
    vitest = _pnpm_test_counter("p7")
    report = playwright_report("p7")
    if report is None:
        browser = CounterResult(1, "no report", ["p7/playwright.log"])
    else:
        stats = report.get("stats", {})
        failed = int(stats.get("unexpected", 0)) + int(stats.get("flaky", 0))
        browser = CounterResult(failed, f'{stats.get("expected", 0)} passed, {failed} failed or flaky',
                                ["p7/playwright.json"])
    return CounterResult(main_gate.count + vitest.count + browser.count,
                         f"Python: {main_gate.detail}; pnpm: {vitest.detail}; Playwright: {browser.detail}",
                         main_gate.evidence + vitest.evidence + browser.evidence)


@counter("p7", "unasked_moves",
         "session moves written without a button press: the engine's reads that write, a move sent "
         "twice that applies twice (" + _P7_MOVE_TESTS + "), and moves the week browser tests saw "
         "sent with no tap")
def p7_unasked_moves() -> CounterResult:
    engine = _pytest_once("p7", _P7_MOVE_TESTS)
    phone = _week_annotations("p7", "unasked_moves")
    return CounterResult(engine.count + phone.count, f"engine: {engine.detail}; phone: {phone.detail}",
                         engine.evidence + phone.evidence)


@counter("p7", "override_writes_unchecked",
         "date_overrides writes that bypass plan.reject_violating_overrides (a scan of services/ and "
         "api/, and tests/test_schedule_change.py)")
def p7_override_writes_unchecked() -> CounterResult:
    hits = override_write_hits(_engine_files())
    tests = _pytest_once("p7", "tests/test_schedule_change.py")
    return CounterResult(len(hits) + tests.count,
                         "; ".join(hits) + (f"; tests: {tests.detail}" if hits else f"none; tests: {tests.detail}"),
                         tests.evidence)


@counter("p7", "day_number_lookups",
         "content looked up by the authored day number in app/src or the training endpoints")
def p7_day_number_lookups() -> CounterResult:
    files = {rel: (REPO_ROOT / rel).read_text(encoding="utf-8") for rel in TRAINING_API_FILES}
    files.update(_phone_code_files())
    hits = authored_lookup_hits(files)
    return CounterResult(len(hits), "; ".join(hits) or f"{len(files)} files, none")


@counter("p7", "duplicate_supplementary",
         "yoga, outdoor or extra sessions stored more than once: tests/test_supplementary_save_once.py "
         "and the week browser tests that send one twice")
def p7_duplicate_supplementary() -> CounterResult:
    engine = _pytest_once("p7", "tests/test_supplementary_save_once.py")
    phone = _week_annotations("p7", "duplicate_supplementary")
    return CounterResult(engine.count + phone.count, f"engine: {engine.detail}; phone: {phone.detail}",
                         engine.evidence + phone.evidence)


@counter("p7", "automatic_writes_in_engine",
         "automatic writes the engine runs while background_writer is \"streamlit\" "
         "(tests/test_background_writer.py)")
def p7_automatic_writes_in_engine() -> CounterResult:
    return _pytest_once("p7", "tests/test_background_writer.py")


@counter("p7", "inventory_rows_open",
         "training-week rows (T1-T36, T103-T112) marked KEEP that the phone app does not build "
         "(docs/rebuild/app_rows.json: the files and the test)")
def p7_inventory_rows_open() -> CounterResult:
    rows = p7_rows(SCREEN_INVENTORY.read_text(encoding="utf-8"))
    mapping = json.loads(APP_ROWS.read_text(encoding="utf-8"))["rows"] if APP_ROWS.exists() else {}
    owner = DESIGN_MD.read_text(encoding="utf-8") if DESIGN_MD.exists() else ""
    open_ = app_rows_open(rows, mapping, owner)
    return CounterResult(len(open_), "; ".join(open_[:30]) or f"{len(rows)} rows built, each with a test")


@counter("p7", "device_checklist_open",
         "items of the owner's training-week checklist not confirmed yet (docs/rebuild/owner_checks.json, p7)")
def p7_device_checklist_open() -> CounterResult:
    data = json.loads(OWNER_CHECKS.read_text(encoding="utf-8")) if OWNER_CHECKS.exists() else {}
    answers = data.get("p7", {})
    missing = [key for key in P7_CHECKLIST if answers.get(key) is not True]
    return CounterResult(len(missing), ", ".join(missing) or "the owner confirmed every item")


review("p7", *P7_CHECKLIST.values())


# ── Phase 8 counters ─────────────────────────────────────────────────────────

#: The Insights rows of the inventory (I1-I93) the phone builds: KEEP on Insights, MOVE to
#: Settings > Data; the rows the owner dropped are left out by their word.
P8_ROW_RANGE = range(1, 94)
#: The owner's comparison (docs/rebuild/owner_checks.json, "p8"): true = as expected.
P8_CHECKLIST = {
    "strength": "Strength: the headline, the chart, the regions and the imbalances equal the Streamlit app's",
    "metabolism": "Metabolism: the latest weigh-in, the chart and the cards equal the Streamlit app's",
    "flexibility": "Flexibility: the pattern, the ladder and the stack equal the Streamlit app's",
    "engine": "Engine data: the directive, the stage, the traffic light and the workload equal the Streamlit app's",
    "warnings": "Warnings: the calendar's days and entries equal the Streamlit app's",
    "trends": "Trends: the regions, the levels and the analysis equal the Streamlit app's",
    "sleep": "Sleep architecture: the counts and the night's strips equal the Streamlit app's",
    "data": "Settings > Data: the tables and the session checks equal the Sync tab's",
    "assessment": "A flexibility assessment, when one is due, run in the new app (or: not due)",
}
INSIGHTS_FIXTURE_SCRIPT = REPO_ROOT / "scripts" / "make_insights_fixture.py"
#: The engine's figures for the scale and for the gym scan, and for strength and for the
#: tonnage: a screen that joins one family with the other in arithmetic is the fused body
#: fat the engine refuses (services/body_composition.py) or the sum of strength and work
#: the Strength screen never shows (services/strength.py beside services/tonnage.py).
FIGURE_FAMILIES = (
    (("weight_kg", "fat_mass_kg", "fat_free_mass_kg", "body_fat_pct"), ("phase_angle_deg", "ecw_tbw")),
    (("overall", "points", "level", "measured"), ("kg", "unloaded_reps", "unloaded_seconds")),
)
_ARITHMETIC = re.compile(r"[^\s=!<>&|?:,(\[{][\s]*[-+*/][\s]*[^\s=>/*]")
#: Engine tests that pin the two refusals.
FIGURE_REFUSAL_TESTS = ("tests/test_body_composition.py", "tests/test_tonnage.py")
#: The phone's Insights code (screens and helpers), read by the scans below.
INSIGHTS_CODE_GLOB = ("Insights", "Flexibility", "Metabolism", "Strength", "Engine", "DataTables")


def _insights_code() -> dict[str, str]:
    return {rel: text for rel, text in _phone_code_files().items()
            if any(part in Path(rel).stem for part in INSIGHTS_CODE_GLOB)}


def figure_mixing_hits(files: dict[str, str]) -> list[str]:
    """Lines of the phone's Insights code where an arithmetic operator sits on a line that
    reads a figure of both families of one pair (the scale and the scan; strength and
    tonnage)."""
    hits = []
    for rel, text in files.items():
        code = _TS_STRING.sub('""', _blank_comments(text))
        for number, line in enumerate(code.splitlines(), 1):
            fields = set(re.findall(r"\.(\w+)", line))
            for one, other in FIGURE_FAMILIES:
                if fields & set(one) and fields & set(other) and _ARITHMETIC.search(line):
                    hits.append(f"{rel}:{number}")
    return hits


def battery_choice_hits(files: dict[str, str], test_keys: list[str]) -> list[str]:
    """Places where the phone's flexibility code chooses a test itself: a test key of
    the battery written in the code, or the engine's order sorted, filtered or searched
    (the step it shows is the engine's order at a position the owner moves)."""
    hits = []
    for rel, text in files.items():
        code = _blank_comments(text)
        for number, line in enumerate(code.splitlines(), 1):
            for key in test_keys:
                if re.search(rf"['\"`]{re.escape(key)}['\"`]", line):
                    hits.append(f"{rel}:{number} the test key {key}")
            if re.search(r"\border\??\.(sort|filter|find|findIndex|reverse|splice)\(", line):
                hits.append(f"{rel}:{number} the engine's order rearranged")
    return hits


def battery_test_keys() -> list[str]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import cluster_a_battery as cba
    return sorted(cba.TESTS)


def p8_rows(markdown: str) -> list[str]:
    """The Insights rows (I1-I93) marked KEEP or MOVE."""
    words = inventory_rows(markdown)
    ids = [rid for rid, word in words.items()
           if word in ("KEEP", "MOVE") and rid.startswith("I") and int(rid[1:]) in P8_ROW_RANGE]
    return sorted(ids, key=lambda rid: int(rid[1:]))


def _fixture_check() -> CounterResult:
    """1 when app/dev/insights_fixture.json is not the engine's own output any more."""
    if not main_python().exists():
        return CounterResult(1, "no venv to run the fixture check")
    proc = subprocess.run([str(main_python()), str(INSIGHTS_FIXTURE_SCRIPT), "--check"], cwd=REPO_ROOT,
                          env=_child_env(), capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    lines = (proc.stdout + proc.stderr).strip().splitlines()
    return CounterResult(0 if proc.returncode == 0 else 1,
                         lines[-1] if lines else f"the fixture check exited {proc.returncode}")


_P8_INSIGHTS_TITLES = ("insights", "strength", "metabolism", "flexibility", "the capture",
                       "engine", "warnings", "trends", "sleep architecture", "settings > data")


def _insights_annotations(phase: str, kind: str) -> CounterResult:
    def count(tests):
        total, notes = annotation_total(tests, kind)
        return CounterResult(total, "; ".join(notes) or f"{len(tests)} Insights test runs, none",
                             [f"{phase}/playwright.json"])
    return _browser_counter(phase, lambda title: title.lower().startswith(_P8_INSIGHTS_TITLES), count)


@counter("p8", "test_failures",
         "failures in the Python gate (plus 1 under the floor), `pnpm test` (the app's and the "
         "Worker's Vitest, after the build) and the browser tests (Playwright)")
def p8_test_failures() -> CounterResult:
    main_gate = _main_gate_counter("p8")
    vitest = _pnpm_test_counter("p8")
    report = playwright_report("p8")
    if report is None:
        browser = CounterResult(1, "no report", ["p8/playwright.log"])
    else:
        stats = report.get("stats", {})
        failed = int(stats.get("unexpected", 0)) + int(stats.get("flaky", 0))
        browser = CounterResult(failed, f'{stats.get("expected", 0)} passed, {failed} failed or flaky',
                                ["p8/playwright.json"])
    return CounterResult(main_gate.count + vitest.count + browser.count,
                         f"Python: {main_gate.detail}; pnpm: {vitest.detail}; Playwright: {browser.detail}",
                         main_gate.evidence + vitest.evidence + browser.evidence)


@counter("p8", "parity_differences",
         "differences between the live engine's Insights answers and the services' own over the "
         "last 28 days, and answers only one side gave (scripts/rebuild_parity.py --insights)")
def p8_parity_differences() -> CounterResult:
    report = parity_report("p8")
    if report is None:
        return CounterResult(1, "the parity run gave no report", ["p8/parity.log"])
    found = len(report.get("differences", [])) + len(report.get("unanswered", []))
    refused = sorted({f'{r["endpoint"]} ({r["error"]})' for r in report.get("refused_alike", [])})
    detail = (f'{report.get("days")} days: {len(report.get("differences", []))} differences, '
              f'{len(report.get("unanswered", []))} answered by one side only'
              + (f'; refused alike: {", ".join(refused)}' if refused else ""))
    return CounterResult(found, detail, ["p8/parity.json"])


@counter("p8", "fused_or_added_figures",
         "phone lines that join a scale figure with a scan figure, or strength with tonnage, in "
         "arithmetic; and failures of the engine tests that refuse both")
def p8_fused_or_added_figures() -> CounterResult:
    hits = figure_mixing_hits(_insights_code())
    tests = [_pytest_once("p8", t) for t in FIGURE_REFUSAL_TESTS]
    failed = sum(t.count for t in tests)
    return CounterResult(len(hits) + failed,
                         ("; ".join(hits) or f"{len(_insights_code())} files, none")
                         + "; tests: " + "; ".join(t.detail for t in tests),
                         [e for t in tests for e in t.evidence])


@counter("p8", "battery_disagreement",
         "capture steps where the screen chooses the next test instead of asking the engine: the "
         "phone's code (a test key or the order rearranged), the capture browser tests, and the "
         "mock's capture being the engine's own (make_insights_fixture.py --check)")
def p8_battery_disagreement() -> CounterResult:
    hits = battery_choice_hits(_insights_code(), battery_test_keys())
    fixture = _fixture_check()
    browser = _insights_annotations("p8", "battery_disagreement")
    return CounterResult(len(hits) + fixture.count + browser.count,
                         f'code: {"; ".join(hits) or "none"}; fixture: {fixture.detail}; '
                         f"browser: {browser.detail}", browser.evidence)


@counter("p8", "text_rule_violations",
         "strings in app/src/strings.ts that fail the jargon, hedge and Stage 1 scans in tests/ "
         "(the Cluster A screens' scans included)")
def p8_text_rule_violations() -> CounterResult:
    return p3_text_rule_violations()


@counter("p8", "inventory_rows_open",
         "Insights rows (I1-I93) marked KEEP or MOVE that the phone app does not build "
         "(docs/rebuild/app_rows.json: the files and the test)")
def p8_inventory_rows_open() -> CounterResult:
    rows = p8_rows(SCREEN_INVENTORY.read_text(encoding="utf-8"))
    mapping = json.loads(APP_ROWS.read_text(encoding="utf-8"))["rows"] if APP_ROWS.exists() else {}
    owner = DESIGN_MD.read_text(encoding="utf-8") if DESIGN_MD.exists() else ""
    open_ = app_rows_open(rows, mapping, owner)
    return CounterResult(len(open_), "; ".join(open_[:30]) or f"{len(rows)} rows built, each with a test")


@counter("p8", "device_checklist_open",
         "items of the owner's Insights comparison not confirmed yet (docs/rebuild/owner_checks.json, p8)")
def p8_device_checklist_open() -> CounterResult:
    data = json.loads(OWNER_CHECKS.read_text(encoding="utf-8")) if OWNER_CHECKS.exists() else {}
    answers = data.get("p8", {})
    missing = [key for key in P8_CHECKLIST if answers.get(key) is not True]
    return CounterResult(len(missing), ", ".join(missing) or "the owner confirmed every item")


review("p8", *P8_CHECKLIST.values())


# ── output ───────────────────────────────────────────────────────────────────

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rebuild gate {phase}</title>
<style>
:root {{ --bg:#fff; --fg:#1b1b1f; --muted:#5b5b66; --line:#d9d9e0; --red:#b3261e; --green:#1e7a3a; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#141418; --fg:#ececf1; --muted:#a3a3ad; --line:#33333b; --red:#ff8a80; --green:#7bd88f; }}
}}
body {{ background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif;
       margin:0 auto; padding:24px 16px; max-width:960px; }}
h1 {{ font-size:22px; }} .verdict {{ font-size:18px; font-weight:600; }}
.ok {{ color:var(--green); }} .open {{ color:var(--red); }}
table {{ border-collapse:collapse; width:100%; }}
td, th {{ border-bottom:1px solid var(--line); padding:6px 8px; text-align:left;
          vertical-align:top; }}
.muted {{ color:var(--muted); }}
</style></head><body>
<h1>Rebuild gate {phase}</h1>
<p class="muted">Generated {generated}</p>
<p class="verdict {verdict_class}">{verdict}</p>
<table><tr><th></th><th>Counter</th><th>What it counts</th><th>Open</th><th>Detail and evidence</th></tr>
{rows}
</table>
<h2>Check by hand</h2>
<ul>{review}</ul>
</body></html>
"""


def write_reports(phase: str, rows: list[GateRow]) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    total = sum(r.count for r in rows)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ordered = sorted(rows, key=lambda r: (r.count == 0, r.name))
    body = []
    for r in ordered:
        links = " ".join(f'<a href="{html.escape(e)}">{html.escape(e)}</a>' for e in r.evidence)
        err = f"<br><span class=\"open\">{html.escape(r.error)}</span>" if r.error else ""
        body.append(
            f"<tr><td>{GREEN if r.count == 0 else RED}</td><td>{html.escape(r.name)}</td>"
            f"<td>{html.escape(r.description)}</td><td>{r.count}</td>"
            f"<td>{html.escape(r.detail)}{err} {links}</td></tr>")
    review_html = "".join(f"<li>{html.escape(i)}</li>" for i in REVIEW_ITEMS.get(phase, []))
    page = _PAGE.format(
        phase=html.escape(phase), generated=generated,
        verdict=f"{GREEN} all counters at 0" if total == 0 else f"{RED} {total} open item(s)",
        verdict_class="ok" if total == 0 else "open", rows="\n".join(body),
        review=review_html or "<li>none</li>")
    html_path = REPORTS_DIR / f"{phase}_gate.html"
    json_path = REPORTS_DIR / f"{phase}_gate.json"
    html_path.write_text(page, encoding="utf-8", newline="\n")
    json_path.write_text(json.dumps({"phase": phase, "generated_at": generated, "total": total,
                                     "counters": [asdict(r) for r in rows]},
                                    indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8", newline="\n")
    return html_path, json_path


def update_feature_list(phase: str, rows: list[GateRow], path: Path = FEATURE_LIST) -> int:
    """Flip `passes` for this phase's tasks from their counter; returns flips."""
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    counts = {r.name: r.count for r in rows}
    flips = 0
    for task in data.get("tasks", []):
        if task.get("phase", "").lower() != phase or task.get("gate") not in counts:
            continue
        passes = counts[task["gate"]] == 0
        if task.get("passes") != passes:
            task["passes"] = passes
            flips += 1
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")
    return flips


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):        # emoji on a cp1252 console
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="The phone-app rebuild's counter gate.")
    parser.add_argument("phase", help="p0, p1, ...")
    parser.add_argument("--update-features", action="store_true",
                        help="flip passes in docs/rebuild/feature_list.json")
    parser.add_argument("--reuse-test-runs", action="store_true",
                        help="read the last junit files instead of running the suites")
    args = parser.parse_args(argv)
    phase = args.phase.lower()
    if phase not in REGISTRY:
        print(f"No counters registered for {phase}.")
        return 2
    global REUSE_TEST_RUNS
    REUSE_TEST_RUNS = args.reuse_test_runs
    rows = run_gate(phase)
    width = max(len(r.name) for r in rows)
    for r in sorted(rows, key=lambda r: (r.count == 0, r.name)):
        print(f"{GREEN if r.count == 0 else RED} {r.name:<{width}}  {r.count:>3}  {r.detail}"
              + (f"  [{r.error}]" if r.error else ""))
    total = sum(r.count for r in rows)
    html_path, json_path = write_reports(phase, rows)
    print(f"\nTotal open items: {total} -> {GREEN if total == 0 else RED}")
    print(f"Report: {html_path.relative_to(REPO_ROOT)}")
    if args.update_features:
        print(f"feature_list.json: {update_feature_list(phase, rows)} task(s) changed")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
