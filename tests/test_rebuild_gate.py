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
            "upload_personal_files": 0}
    assert gate.missed_targets(good) == []
    slow = dict(good, cold_start_median_s=11.0)
    assert gate.missed_targets(slow) == ["cold start median <= 10 s"]


def test_a_large_image_passes_only_when_its_cost_is_small():
    base = {"cold_start_median_s": 6.0, "cold_start_worst_s": 12.0,
            "free_tier_max_share": 0.2, "garmin_ok": True, "upload_personal_files": 0}
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
