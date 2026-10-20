"""scripts/rebuild_gate.py: the phone-app rebuild's counter gate.

The gate decides when a rebuild phase may be called green, so the parts that
could make it read green WRONGLY are pinned here: a crashing counter must count
as open, an unmeasured target must count as missed, the floor must be read
from CLAUDE.md's own line, and the secret scan must find a secret's shape
without ever echoing it. Nothing here runs a test suite or a cloud command.
"""

from __future__ import annotations

import json

import pytest

from scripts import rebuild_gate as gate


@pytest.fixture
def isolated_registry(monkeypatch):
    monkeypatch.setattr(gate, "REGISTRY", {})
    monkeypatch.setattr(gate, "REVIEW_ITEMS", {})
    return gate.REGISTRY


def test_a_crashing_counter_is_one_open_item(isolated_registry):
    @gate.counter("px", "boom", "always raises")
    def _boom():
        raise RuntimeError("nope")

    @gate.counter("px", "fine", "always zero")
    def _fine():
        return gate.CounterResult(0, "ok")

    rows = {r.name: r for r in gate.run_gate("px")}
    assert rows["boom"].count == 1 and "RuntimeError" in rows["boom"].error
    assert rows["fine"].count == 0


def test_unknown_phase_exits_2(isolated_registry):
    assert gate.main(["p99"]) == 2


def test_the_floor_is_read_from_the_claude_md_line():
    text = "blah\nExpected: **4226/4226 passed** (1 skipped ...)\n"
    assert gate.gate_floor(text) == 4226
    assert gate.gate_floor("no floor here") is None


def test_the_real_claude_md_has_a_readable_floor():
    assert gate.gate_floor(gate.CLAUDE_MD.read_text(encoding="utf-8")) is not None


def test_junit_sums_every_suite(tmp_path):
    path = tmp_path / "j.xml"
    path.write_text(
        '<testsuites><testsuite tests="10" failures="1" errors="1" skipped="2"/>'
        '<testsuite tests="5" failures="0" errors="0" skipped="0"/></testsuites>',
        encoding="utf-8")
    s = gate.read_junit(path)
    assert (s.tests, s.failures, s.errors, s.skipped, s.passed) == (15, 1, 1, 2, 11)


def test_an_unmeasured_target_is_missed_not_passed():
    assert len(gate.missed_targets({})) == len(gate.P0_TARGETS)
    good = {"cold_start_median_s": 6.0, "cold_start_worst_s": 12.0,
            "free_tier_max_share": 0.2, "garmin_ok": True, "image_size_mb": 180,
            "upload_personal_files": 0, "cold_start_failures": 0}
    assert gate.missed_targets(good) == []
    slow = dict(good, cold_start_median_s=11.0)
    assert gate.missed_targets(slow) == ["cold start median <= 10 s"]


def test_a_refused_cold_start_is_a_miss_even_when_the_timed_ones_are_fast():
    good = {"cold_start_median_s": 6.0, "cold_start_worst_s": 12.0,
            "free_tier_max_share": 0.2, "garmin_ok": True, "image_size_mb": 180,
            "upload_personal_files": 0}
    assert gate.missed_targets(dict(good, cold_start_failures=1)) == ["every timed cold start answered"]
    assert gate.missed_targets(good) == ["every timed cold start answered (not measured)"]


def test_an_owners_waiver_needs_a_reason_and_names_a_real_target():
    good = {"cold_start_median_s": 10.08, "cold_start_worst_s": 11.0,
            "free_tier_max_share": 0.2, "garmin_ok": True, "image_size_mb": 180,
            "upload_personal_files": 0, "cold_start_failures": 0}
    assert gate.missed_targets(good) == ["cold start median <= 10 s"]
    waived = dict(good, waived_targets={"cold_start_median_s": "owner: the timing does not matter"})
    assert gate.missed_targets(waived) == []
    assert gate.waived_targets(waived) == {"cold_start_median_s": "owner: the timing does not matter"}
    # No reason, or a name that is not a target: nothing is waived.
    assert gate.missed_targets(dict(good, waived_targets={"cold_start_median_s": " "})) == [
        "cold start median <= 10 s"]
    assert gate.waived_targets(dict(good, waived_targets={"tests_failing": "x"})) == {}


def test_a_large_image_passes_only_when_its_cost_is_small():
    base = {"cold_start_median_s": 6.0, "cold_start_worst_s": 12.0,
            "free_tier_max_share": 0.2, "garmin_ok": True, "upload_personal_files": 0,
            "cold_start_failures": 0}
    assert gate.missed_targets(dict(base, image_size_mb=900, image_monthly_cost_eur=0.04)) == []
    assert gate.missed_targets(dict(base, image_size_mb=900, image_monthly_cost_eur=0.20))


@pytest.mark.parametrize("path", [
    "Input_files/injury_profile.md", ".streamlit/secrets.toml", ".env", ".env.local",
    "datastore.db", "x/y.sqlite3", ".sync_state.json", "patient_profile.py",
    "voice_training/voxplot/app.py", "./Input_files/MRI.pdf", "reports/rebuild/p0_gate.html",
])
def test_personal_files_are_flagged_in_an_upload_list(path):
    assert gate.personal_upload_files([path]) != []


@pytest.mark.parametrize("path", [
    "Dockerfile", "requirements-engine.txt", "api/healthapi/main.py",
    "services/repository.py", "training_plan.py", "cluster_a_battery.py",
])
def test_engine_files_are_not_flagged(path):
    assert gate.personal_upload_files([path]) == []


def test_the_secret_scan_finds_shapes_and_reports_only_line_and_kind():
    fake_key = "-----BEGIN " + "PRIVATE KEY-----"
    fake_notion = "secret_" + "A" * 43
    text = f"ok line\n{fake_key}\nNOTION = '{fake_notion}'\nnothing"
    hits = gate.scan_text_for_secrets(text)
    assert hits == [(2, "private key block"), (3, "Notion token")]
    assert all(fake_notion not in name for _, name in hits)


def test_placeholders_are_not_secrets():
    assert gate.scan_text_for_secrets("APP_TOKEN = 'test-token'\nkey = '<paste here>'") == []


def test_streamlit_bound_list_is_parsed(tmp_path):
    md = tmp_path / "list.md"
    md.write_text("# x\n- `tests/test_a.py` imports streamlit\n- not a test\n"
                  "- `tests/test_b.py` imports views\n", encoding="utf-8")
    assert gate.streamlit_bound_tests(md) == ["tests/test_a.py", "tests/test_b.py"]


def test_one_test_can_be_listed_and_is_deselected_not_ignored(tmp_path):
    md = tmp_path / "list.md"
    md.write_text("- `tests/test_a.py` whole file\n- `tests/test_b.py::test_card` one test\n",
                  encoding="utf-8")
    listed = gate.streamlit_bound_tests(md)
    assert listed == ["tests/test_a.py", "tests/test_b.py::test_card"]
    assert gate.engine_run_exclusions(listed) == [
        "--ignore=tests/test_a.py", "--deselect=tests/test_b.py::test_card"]


def test_the_real_streamlit_bound_list_names_existing_tests():
    listed = gate.streamlit_bound_tests()
    assert listed, "docs/rebuild/streamlit_bound_tests.md lists no tests"
    for entry in listed:
        file, _, name = entry.partition("::")
        assert (gate.REPO_ROOT / file).exists(), entry
        if name:
            source = (gate.REPO_ROOT / file).read_text(encoding="utf-8")
            assert f"def {name}(" in source, entry


# ── Phase 1: Voice Training leaves the health app ────────────────────────────

def test_phase_1_has_the_five_counters_its_prompt_names():
    assert set(gate.REGISTRY["p1"]) == {"tests_failing", "voice_refs_left", "voice_libs_left",
                                        "submodule_left", "device_checklist_open"}


def test_a_voice_reference_in_code_is_found_with_its_line():
    files = {
        "app.py": "x = 1\nelif _page == 'sync':\n    from views import sync as _view\n",
        "nav.py": '    ("↻",  "Voice Training", "sync"),\n',
        "views/insights.py": "with tab_sync:\n    st.button('Sync')\n",     # the Insights Sync tab stays
        ".gitmodules": '[submodule "voice_training/voxplot"]\n',
    }
    assert gate.voice_ref_hits(files) == ["app.py:3", "nav.py:1", ".gitmodules:1"]


def test_docs_markdown_and_the_named_exceptions_do_not_count():
    files = {
        "docs/resume.md": "Voxplot (voice_training/voxplot) moved out on 2026-10-19\n",
        "CLAUDE.md": "- Voice Training: its own Streamlit app\n",
        "tests/test_rebuild_secrets.py": '"voxplot_supabase": {"url": "x"}\n',
        ".claude/settings.local.json": '"Bash(python -c \\"open(\'views/sync.py\')\\")"\n',
    }
    assert gate.voice_ref_hits(files) == []
    assert all(reason for reason in gate.VOICE_REF_ALLOW.values())


def test_a_voice_library_is_found_by_its_name_not_by_a_longer_one():
    text = ("streamlit>=1.58.0\npraat-parselmouth>=0.4.3\nscipy>=1.11\n"
            "soundfile>=0.12\nimageio-ffmpeg>=0.5\nscipy-stubs==1.0\n# scipy left in 2026\n")
    assert gate.voice_lib_hits({"requirements.txt": text}) == [
        "requirements.txt: praat-parselmouth", "requirements.txt: scipy",
        "requirements.txt: soundfile", "requirements.txt: imageio-ffmpeg"]


def test_the_phone_checks_count_until_the_owner_confirms_each(tmp_path, monkeypatch):
    checks = tmp_path / "owner_checks.json"
    monkeypatch.setattr(gate, "OWNER_CHECKS", checks)
    checks.write_text('{"p1": {"health_three_tabs": true, "health_pages_work": false}}', encoding="utf-8")
    result = gate.p1_device_checklist_open()
    assert result.count == 2
    assert "reported failing" in result.detail and "not checked" in result.detail


def test_update_feature_list_flips_only_this_phases_tasks(tmp_path):
    path = tmp_path / "fl.json"
    path.write_text(json.dumps({"phase": "P0", "tasks": [
        {"id": "P0-01", "phase": "P0", "gate": "a", "passes": False},
        {"id": "P0-02", "phase": "P0", "gate": "b", "passes": True},
        {"id": "P1-01", "phase": "P1", "gate": "a", "passes": False},
    ]}), encoding="utf-8")
    rows = [gate.GateRow("a", "", 0, "", []), gate.GateRow("b", "", 2, "", [])]
    assert gate.update_feature_list("p0", rows, path) == 2
    tasks = {t["id"]: t["passes"] for t in json.loads(path.read_text("utf-8"))["tasks"]}
    assert tasks == {"P0-01": True, "P0-02": False, "P1-01": False}


def test_reports_list_open_counters_first(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPORTS_DIR", tmp_path)
    rows = [gate.GateRow("zero", "d", 0, "fine", []),
            gate.GateRow("open", "d", 2, "<b>escaped</b>", ["p0/log.txt"])]
    html_path, json_path = gate.write_reports("p0", rows)
    page = html_path.read_text(encoding="utf-8")
    assert page.index(">open<") < page.index(">zero<")
    assert "&lt;b&gt;escaped&lt;/b&gt;" in page
    assert json.loads(json_path.read_text("utf-8"))["total"] == 2


# ── Phase 2: the engine API ──────────────────────────────────────────────────

_INVENTORY = """\
## D1. DROP proposals

| Id | Screen | Feature | Why it can go | Decision |
|---|---|---|---|---|
| H3 | Shell | Toast | Cannot appear | **DROP** — approved 2026-10-19 |
| I4 | BioAge | Cardio card | A placeholder | **KEEP** — the owner, 2026-10-19 |
| T9 | Training | Old banner | Dead | **DROP** — proposed, not approved |

## D2. MOVE proposals

| Id | From | Feature | New place | Decision |
|---|---|---|---|---|
| H2 | Shell | Banner | Shell status | **MOVE** — approved 2026-10-19 |

## Home (`app.py`) — 4 rows

| Id | Area | Feature | Source | Computed | Writes | Proposal |
|---|---|---|---|---|---|---|
| H1 | Shell | Layout | css | — | — | KEEP (becomes the phone shell) |
| H2 | Shell | Banner | repo | x | — | MOVE (app-wide status) |
| H3 | Shell | Toast | repo | — | — | DROP (cannot appear) |
| H61 | Home | Summary | — | — | — | Nothing to inventory |

## Training (`views/training.py`) — 1 row

### Banners

| Id | Area | Feature | Source | Computed | Writes | Proposal |
|---|---|---|---|---|---|---|
| T9 | Banner | Old banner | — | — | — | DROP (dead) |

## Insights, Check-in and the shell — 1 row

| Id | Tab | Feature | What it shows | Source | Computed | Writes | Proposal |
|---|---|---|---|---|---|---|---|
| I4 | BioAge | Cardio | Coming soon | — | — | — | DROP (placeholder) |

## Computations that must move into `services/` (milestone 3)

| HOME-1 | not an inventory row | KEEP |
"""


def test_phase_2_has_the_counters_its_prompt_names():
    assert set(gate.REGISTRY["p2"]) == {
        "tests_failing", "inventory_unmapped", "view_logic_left", "faults_open",
        "idempotency_fail", "supabase_write_bypass", "date_from_server",
        "background_writer_leaks", "schema_stale", "drops_without_approval",
        "streamlit_app_broken"}


def test_inventory_rows_read_the_proposal_and_the_owners_keep_wins():
    assert gate.inventory_rows(_INVENTORY) == {
        "H1": "KEEP", "H2": "MOVE", "H3": "DROP", "H61": "", "T9": "DROP", "I4": "KEEP"}


def test_a_drop_counts_as_decided_only_with_the_owners_word():
    assert gate.drop_decisions(_INVENTORY) == {"H3", "I4"}


def test_the_drop_counter_names_a_drop_without_a_decision(tmp_path, monkeypatch):
    inventory = tmp_path / "inventory.md"
    inventory.write_text(_INVENTORY, encoding="utf-8")
    monkeypatch.setattr(gate, "SCREEN_INVENTORY", inventory)
    result = gate.p2_drops_without_approval()
    assert (result.count, result.detail) == (1, "T9")


def test_the_real_inventory_has_every_drop_decided_and_the_cardio_card_kept():
    text = gate.SCREEN_INVENTORY.read_text(encoding="utf-8")
    rows = gate.inventory_rows(text)
    drops = {rid for rid, word in rows.items() if word == "DROP"}
    assert drops and drops <= gate.drop_decisions(text)
    assert rows["I4"] == "KEEP"


def test_openapi_operations_list_method_and_path():
    spec = {"paths": {"/api/x": {"get": {}, "post": {}, "parameters": []},
                      "/api/y": {"delete": {}}}}
    assert gate.openapi_operations(spec) == {"GET /api/x", "POST /api/x", "DELETE /api/y"}
    assert gate.openapi_operations({}) == set()


def test_a_row_is_mapped_by_a_contract_endpoint_with_a_test_or_by_a_phone_reason():
    rows = {"H1": "KEEP", "H2": "MOVE", "H3": "DROP", "H4": "KEEP", "H5": "KEEP",
            "H6": "KEEP", "H7": "", "H8": "KEEP", "H9": "MOVE"}
    test = "tests/api/t.py::test_status"
    mapping = {
        "H1": {"client": "phone", "why": "styling only"},
        "H2": {"endpoint": "GET /api/status", "test": test},
        "H4": {"endpoint": "GET /api/gone", "test": test},                  # not in the contract
        "H5": {"endpoint": "GET /api/status", "test": "tests/api/t.py::test_gone"},
        "H6": {"client": "phone", "why": "  "},                             # no reason given
        "H8": {"endpoint": ["GET /api/status", "POST /api/save"], "test": [test]},
    }
    operations = {"GET /api/status", "POST /api/save"}
    assert gate.unmapped_rows(rows, mapping, operations,
                              ref_exists=lambda ref: ref == test) == ["H4", "H5", "H6", "H9"]


def test_the_inventory_counter_reads_the_contract_file(tmp_path, monkeypatch):
    inventory, mapping, spec = (tmp_path / n for n in ("inv.md", "map.json", "openapi.json"))
    inventory.write_text(_INVENTORY, encoding="utf-8")
    real_test = "tests/test_rebuild_gate.py::test_phase_2_has_the_counters_its_prompt_names"
    mapping.write_text(json.dumps({"rows": {
        "H1": {"client": "phone", "why": "styling"},
        "H2": {"endpoint": "GET /api/status", "test": real_test}}}), encoding="utf-8")
    spec.write_text(json.dumps({"paths": {"/api/status": {"get": {}}}}), encoding="utf-8")
    monkeypatch.setattr(gate, "SCREEN_INVENTORY", inventory)
    monkeypatch.setattr(gate, "INVENTORY_ENDPOINTS", mapping)
    monkeypatch.setattr(gate, "OPENAPI_JSON", spec)
    result = gate.p2_inventory_unmapped()
    assert result.count == 1 and result.detail == "2 of 3 rows mapped; open: I4"


def test_a_move_or_a_fault_is_open_until_its_service_and_test_exist():
    entries = [
        {"id": "A", "service": "services/x.py::f", "test": "tests/t.py::test_f"},
        {"id": "B", "service": None, "test": "tests/t.py::test_f"},
        {"id": "C", "service": "services/x.py::gone", "test": "tests/t.py::test_f"},
        {"id": "D", "service": ["services/x.py::f", "services/x.py::g"], "test": "tests/t.py::test_f"},
        {"id": "E", "service": ["services/x.py::f", "services/x.py::gone"], "test": "tests/t.py::test_f"},
        {"id": "F", "service": "services/x.py::f", "test": ""},
    ]
    known = {"services/x.py::f", "services/x.py::g", "tests/t.py::test_f"}
    assert gate.open_items(entries, ("service", "test"), ref_exists=known.__contains__) == [
        "B", "C", "E", "F"]


def test_a_dropped_move_closes_only_once_its_code_is_gone():
    entries = [
        {"id": "A", "dropped": "2026-10-19", "gone": ["services/old.py"]},
        {"id": "B", "dropped": "2026-10-19", "gone": ["services/still_here.py"]},
        {"id": "C", "dropped": "2026-10-19", "gone": []},
    ]
    known = {"services/still_here.py"}
    assert gate.open_items(entries, ("service", "test"), ref_exists=known.__contains__) == [
        "B", "C"]


def test_a_reference_must_name_a_real_definition(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    (tmp_path / "services").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "services" / "x.py").write_text(
        "LIMIT: int = 4\nCONSTANT = 3\n# def ghost(): only a comment\n\n"
        "def f():\n    pass\n\nclass Thing:\n    pass\n\nasync def g():\n    pass\n",
        encoding="utf-8")
    (tmp_path / "tests" / "test_t.py").write_text(
        "class TestGroup:\n    def test_inside(self):\n        pass\n\n"
        "def test_param(x):\n    pass\n", encoding="utf-8")
    for ref in ("services/x.py::f", "services/x.py::Thing", "services/x.py::g",
                "services/x.py::CONSTANT", "services/x.py::LIMIT", "services/x.py",
                "tests/test_t.py::TestGroup::test_inside", "tests/test_t.py::test_param[1]"):
        assert gate._ref_exists(ref), ref
    for ref in ("services/x.py::ghost", "services/x.py::Thin", "services/missing.py::f",
                "", None):
        assert not gate._ref_exists(ref), ref


@pytest.mark.parametrize("xml, count, words", [
    (None, 1, "no junit file"),
    ('<testsuite tests="2" failures="0" errors="0" skipped="2"/>', 1, "nothing passed"),
    ('<testsuite tests="0" failures="0" errors="0" skipped="0"/>', 1, "nothing passed"),
    ('<testsuite tests="3" failures="1" errors="0" skipped="0"/>', 1, "2 passed, 1 failed"),
    ('<testsuite tests="3" failures="0" errors="0" skipped="0"/>', 0, "3 passed"),
])
def test_a_test_file_counts_green_only_when_something_in_it_passed(tmp_path, monkeypatch,
                                                                   xml, count, words):
    venv_python = _fake_repo(tmp_path, monkeypatch)
    seen = []

    def fake_run(python, junit, log, extra=None, target="tests/"):
        seen.append((python, target))
        junit.parent.mkdir(parents=True, exist_ok=True)
        if xml is not None:
            junit.write_text(xml, encoding="utf-8")
        return 0

    monkeypatch.setattr(gate, "_run_pytest", fake_run)
    result = gate._pytest_file_failures("p2", "tests/test_x.py")
    assert result.count == count and words in result.detail
    assert seen == [(venv_python, "tests/test_x.py")]      # the repo's venv, one file


def _fake_repo(tmp_path, monkeypatch):
    """A repo in tmp_path with one test file and a venv/ Python; returns it."""
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gate, "REPORTS_DIR", tmp_path / "reports")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("", encoding="utf-8")
    venv_python = tmp_path / "venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    return venv_python


def test_the_suites_never_run_in_the_python_that_started_the_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    assert gate.main_python() == tmp_path / "venv" / "bin" / "python"
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("", encoding="utf-8")
    result = gate._pytest_file_failures("p2", "tests/test_x.py")
    assert result.count == 1 and "venv/ is missing" in result.detail
    assert gate._main_gate_counter("p2").count == 1


def test_a_test_file_that_does_not_exist_is_open(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    result = gate._pytest_file_failures("p2", "tests/api/test_save_idempotency.py")
    assert result.count == 1 and "does not exist yet" in result.detail


def test_a_crashed_run_cannot_leave_the_last_runs_results(tmp_path, monkeypatch):
    junit = tmp_path / "run.xml"
    junit.write_text('<testsuite tests="5"/>', encoding="utf-8")

    class _Crashed:
        stdout, stderr, returncode = "", "collection error", 2

    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: _Crashed())
    gate._run_pytest("python", junit, tmp_path / "run.log")
    assert not junit.exists()


_CLOCK_CODE = '''\
"""Reads date.today() in a docstring: not a call."""
from datetime import date, datetime, timezone
import datetime as dt

# date.today() in a comment
STARTED = datetime.now(timezone.utc)

def route():
    a = date.today()
    b = datetime.now()
    c = datetime.now(timezone.utc).date()
    d = dt.datetime.utcnow().date()
    e = dt.date.today()
    f = datetime.now(tz=timezone.utc)
    return a, b, c, d, e, f

def health():
    return date.today()
'''


def test_the_clock_check_finds_each_read_of_the_servers_day_and_allows_an_instant():
    path = "api/healthapi/routes/x.py"
    assert gate.server_clock_hits({path: _CLOCK_CODE}) == [
        f"{path}:{n}" for n in (9, 10, 11, 12, 13, 18)]


def test_the_allowed_diagnostic_function_is_the_only_exception():
    path = "api/healthapi/routes/health.py"
    assert gate.server_clock_hits({path: _CLOCK_CODE}) == [
        f"{path}:{n}" for n in (9, 10, 11, 12, 13)]
    for key, reason in gate.SERVER_CLOCK_ALLOWED.items():
        assert reason and gate._ref_exists(key), key


def test_an_api_import_that_goes_around_repository_is_found():
    code = ('"""import sqlite3 in a docstring is not an import."""\n'
            "import json\n"
            "import sqlite3\n"
            "from services import supabase_store\n"
            "from services.clients import datastore_writer\n"
            "from services.clients.datastore_writer import apply_rows\n"
            "import services.supabase_store as store\n"
            "from services import record_cache, repository\n"
            "from .engine import STATE\n")
    assert gate.write_bypass_hits({"api/x.py": code}) == [
        "api/x.py:3", "api/x.py:4", "api/x.py:5", "api/x.py:6", "api/x.py:7"]


def test_the_real_api_reads_no_server_day_and_writes_only_through_repository():
    texts = gate._api_texts()
    assert texts, "api/healthapi has no Python files"
    assert gate.server_clock_hits(texts) == []
    assert gate.write_bypass_hits(texts) == []


def test_the_tracking_files_are_well_formed():
    faults = gate._json(gate.FAULTS, {})["faults"]
    ids = [f["id"] for f in faults]
    assert len(set(ids)) == len(ids)
    assert {f"F{n}" for n in range(1, 22)} <= set(ids)      # the owner's 21 stay listed
    moves = gate._json(gate.VIEW_LOGIC_MOVES, {})["moves"]
    assert moves and len({m["id"] for m in moves}) == len(moves)
    for entry in faults + moves:
        for key in ("service", "test"):
            for ref in gate._as_list(entry.get(key)):
                assert gate._ref_exists(ref), f"{entry['id']}: {ref} does not exist"
    rows = gate.inventory_rows(gate.SCREEN_INVENTORY.read_text(encoding="utf-8"))
    assert set(gate._json(gate.INVENTORY_ENDPOINTS, {})["rows"]) <= set(rows)


# ── Phase 3 ──────────────────────────────────────────────────────────────────

def test_phase_3_has_the_counters_its_prompt_names():
    assert set(gate.REGISTRY["p3"]) == {
        "choice_missing", "tokens_unused", "real_data_in_app", "text_rule_violations",
        "test_failures"}


def test_the_owners_choice_needs_his_own_words_on_the_choice_line():
    assert gate.owner_choice('**Owner\'s choice** (2026-10-20): *"Yes, this one"*') == "Yes, this one"
    assert gate.owner_choice("**Owner's choice**: not yet") is None
    assert gate.owner_choice('Somewhere else: *"Yes"*') is None


def test_a_colour_or_a_stylesheet_size_outside_the_tokens_is_found_with_its_line():
    files = {
        "app/src/a.tsx": "const ok = 'var(--accent)'\nconst bad = '#FF0000'\n",
        "app/src/b.css": ".x {\n  padding: var(--sp-m);\n  margin: 12px;\n  color: rgba(0, 0, 0, 0.5);\n}\n",
        "app/src/c.css": "html {\n  font-size: 17px;\n}\n/* a #comment 12px */\n",
    }
    assert gate.token_misses(files) == [
        "app/src/a.tsx:2 colour", "app/src/b.css:3 size", "app/src/b.css:4 colour"]


def test_string_literals_are_read_from_typescript_without_its_comments():
    text = "// 'not this'\nconst S = { a: 'one', b: \"two's\", c: (n: number) => `three ${n}` }\n"
    assert gate.ts_string_literals(text) == ["one", "two's", "three ${n}"]


def test_the_text_scan_flags_a_hedge_and_stage_one_and_passes_plain_words():
    hits = gate.text_rule_hits(["Pick either works for you", "Back to Stage 1 work", "Start session"])
    assert len(hits) == 2 and "either works" in hits[0] and "Stage 1" in hits[1]


def test_the_real_strings_file_passes_the_text_scan():
    literals = gate.ts_string_literals(gate.STRINGS_TS.read_text(encoding="utf-8"))
    assert len(literals) > 50
    assert gate.text_rule_hits(literals) == []


def test_the_real_screen_files_write_no_colour_or_size_of_their_own():
    assert gate.token_misses(gate._screen_files()) == []


# ── Phase 4 ──────────────────────────────────────────────────────────────────

def test_phase_4_has_the_counters_its_prompt_names():
    assert set(gate.REGISTRY["p4"]) == {
        "test_failures", "offline_boot_fail", "blank_screen_with_engine_down", "outbox_loss",
        "api_cached_by_sw", "cron_enabled_early", "mirror_gaps_open", "device_checklist_open"}


_REPORT = {"stats": {"expected": 3, "unexpected": 1}, "suites": [{"suites": [{"specs": [
    {"title": "with the engine down, Today renders and shows the saved data",
     "tests": [{"projectName": "chromium", "results": [{"status": "passed"}], "annotations": []},
               {"projectName": "webkit", "results": [{"status": "failed"}], "annotations": []}]},
    {"title": "writes made offline go out in order @outbox",
     "tests": [{"projectName": "chromium", "results": [{"status": "passed"}],
                "annotations": [{"type": "outbox_loss", "description": "0"}]}]},
    {"title": "writes made while the engine is down wait @outbox",
     "tests": [{"projectName": "chromium", "results": [{"status": "failed"}], "annotations": []}]},
]}]}]}


def test_a_browser_report_is_read_flat_with_each_browsers_last_result():
    tests = gate.playwright_tests(_REPORT)
    assert [(t["project"], t["status"]) for t in tests] == [
        ("chromium", "passed"), ("webkit", "failed"), ("chromium", "passed"), ("chromium", "failed")]
    assert gate.failed_tests(tests[:2]) == [
        "webkit: with the engine down, Today renders and shows the saved data"]


def test_an_outbox_test_that_failed_before_counting_counts_one_lost_write():
    tests = [t for t in gate.playwright_tests(_REPORT) if t["title"].endswith("@outbox")]
    lost, notes = gate.outbox_losses(tests)
    assert lost == 1 and "failed before it counted" in notes[0]
    tests[0]["annotations"] = [{"type": "outbox_loss", "description": "2"}]
    assert gate.outbox_losses(tests)[0] == 3


def test_a_missing_browser_report_or_test_is_an_open_item(monkeypatch):
    monkeypatch.setattr(gate, "playwright_report", lambda phase: None)
    assert gate.p4_offline_boot_fail().count == 1
    monkeypatch.setattr(gate, "playwright_report", lambda phase: {"suites": []})
    assert gate.p4_blank_screen_with_engine_down().count == 1


def test_the_service_worker_scan_finds_an_api_route_and_a_page_route_without_its_denylist():
    good = r"registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }))"
    assert gate.sw_api_routes(good) == []
    assert gate.sw_api_routes("registerRoute(new NavigationRoute(handler))") == [
        "the page route has no /api denylist"]
    hits = gate.sw_api_routes(good + "\nregisterRoute(({ url }) => url.pathname.startsWith('/api/'), new NetworkFirst())")
    assert len(hits) == 1 and hits[0].startswith("a route names /api")
    assert gate.sw_api_routes("// registerRoute(api)\n" + good) == []


def test_the_real_service_worker_has_no_api_route():
    assert gate.sw_api_routes(gate.SW_SOURCE.read_text(encoding="utf-8")) == []


def test_wrangler_jsonc_is_read_with_its_comments_and_a_url_in_a_string():
    text = '{\n  // a comment\n  "url": "https://x.test/a",  /* block */\n  "vars": { "SYNC_ENABLED": "false", },\n}\n'
    assert gate.jsonc(text) == {"url": "https://x.test/a", "vars": {"SYNC_ENABLED": "false"}}


def test_the_sync_switch_is_off_in_the_real_worker_config():
    assert gate.p4_cron_enabled_early().count == 0


def test_the_sync_switch_counts_one_when_it_is_on(tmp_path, monkeypatch):
    config = tmp_path / "wrangler.jsonc"
    config.write_text('{ "vars": { "SYNC_ENABLED": "true" } }', encoding="utf-8")
    monkeypatch.setattr(gate, "WRANGLER", config)
    assert gate.p4_cron_enabled_early().count == 1


def test_the_iphone_checklist_is_open_until_the_owner_confirms_each_item():
    assert gate.checklist_open({}) == list(gate.P4_CHECKLIST)
    every = {key: True for key in gate.P4_CHECKLIST}
    assert gate.checklist_open({"p4": every}) == []
    assert gate.checklist_open({"p4": {**every, "airplane": False}}) == ["airplane"]


def test_the_data_check_counter_reads_the_checks_answer(tmp_path, monkeypatch):
    class Done:
        returncode = 0
        stdout = json.dumps({"missing_rows": 2, "backup_name": "health-2026-10-19.db.gz",
                             "backup_stale": False})
    monkeypatch.setattr(gate, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: Done())
    result = gate.p4_mirror_gaps_open()
    assert result.count == 2 and "health-2026-10-19" in result.detail
    Done.stdout = json.dumps({"error": "store_unavailable"})
    assert gate.p4_mirror_gaps_open().count == 1
