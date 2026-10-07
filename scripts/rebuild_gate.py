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
    docs/rebuild/streamlit_bound_tests.md (lines like "- `tests/x.py` ...")."""
    if not md_path.exists():
        return []
    return re.findall(r"^- `(tests/[^`]+\.py)`", md_path.read_text(encoding="utf-8"),
                      flags=re.MULTILINE)


def engine_python(root: Path = REPO_ROOT) -> Path:
    windows = root / ".venv-engine" / "Scripts" / "python.exe"
    return windows if windows.exists() else root / ".venv-engine" / "bin" / "python"


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({"NO_COLOR": "1", "FORCE_COLOR": "0", "CI": "1",
                "PYTHONIOENCODING": "utf-8"})
    return env


def _run_pytest(python: Path | str, junit: Path, log: Path,
                extra: list[str] | None = None) -> int:
    junit.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(python), "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
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
]


def missed_targets(proof: dict, targets=P0_TARGETS) -> list[str]:
    """Targets that are missed OR not measured yet: an unmeasured target is
    not a passed one."""
    missed = []
    for key, label, check in targets:
        verdict = check(proof)
        if verdict is not True:
            missed.append(label + ("" if verdict is False else " (not measured)"))
    return missed


def _owner_check(phase: str, key: str) -> bool | None:
    if not OWNER_CHECKS.exists():
        return None
    data = json.loads(OWNER_CHECKS.read_text(encoding="utf-8"))
    return data.get(phase, {}).get(key)


# ── Phase 0 counters ─────────────────────────────────────────────────────────

@counter("p0", "tests_failing",
         "main gate failures in venv/, plus 1 if the pass count is under the floor")
def p0_tests_failing() -> CounterResult:
    out = REPORTS_DIR / "p0"
    junit, log = out / "pytest-main.xml", out / "pytest-main.log"
    if not (REUSE_TEST_RUNS and junit.exists()):
        _run_pytest(sys.executable, junit, log)
    if not junit.exists():
        return CounterResult(1, "pytest wrote no junit file", ["p0/pytest-main.log"])
    summary = read_junit(junit)
    floor = gate_floor(CLAUDE_MD.read_text(encoding="utf-8"))
    under = 1 if floor is None or summary.passed < floor else 0
    return CounterResult(
        summary.failures + summary.errors + under,
        f"{summary.passed} passed, {summary.failures} failed, {summary.errors} errors, "
        f"{summary.skipped} skipped; floor {floor}",
        ["p0/pytest-main.log"])


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
        _run_pytest(python, junit, log, [f"--ignore={t}" for t in excluded])
    if not junit.exists():
        return CounterResult(1, "pytest wrote no junit file", ["p0/pytest-engine.log"])
    summary = read_junit(junit)
    return CounterResult(
        summary.failures + summary.errors,
        f"{summary.passed} passed, {summary.failures} failed, {summary.errors} errors, "
        f"{summary.skipped} skipped; {len(excluded)} Streamlit tests excluded",
        ["p0/pytest-engine.log"])


@counter("p0", "pnpm_tests_failing",
         "failures in `pnpm test` (builds the app, then the app and Worker tests)")
def p0_pnpm_tests_failing() -> CounterResult:
    pnpm = shutil.which("pnpm")
    if not pnpm:
        return CounterResult(1, "pnpm is not on PATH")
    if not (REPO_ROOT / "node_modules").exists():
        return CounterResult(1, "node_modules is missing (pnpm install)")
    out = REPORTS_DIR / "p0"
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([pnpm, "test"], cwd=REPO_ROOT, env=_child_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = proc.stdout + proc.stderr
    (out / "pnpm-test.log").write_text(log, encoding="utf-8", newline="\n")
    failed = sum(int(n) for n in re.findall(r"Tests\s+(\d+) failed", log))
    if proc.returncode != 0 and failed == 0:
        failed = 1
    passed = sum(int(n) for n in re.findall(r"Tests\s+(\d+) passed", log))
    return CounterResult(failed, f"{passed} passed, {failed} failed", ["p0/pnpm-test.log"])


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
    return CounterResult(len(missed), "; ".join(missed) or "every target met")


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
