"""services/decision.py: the day's training decision, for a given day.

Home and the Training page read it through today.py's cache; the phone's API
reads it for the phone's own date. What this pins:

  * every read behind the directive ends on the day asked for, never on the
    server's own today (rebuild rule 3);
  * a failed read degrades to "no opinion", and the HRV caption failing never
    takes the directive down;
  * the HRV run crosses as ONE sentence, and no guardrail can import the
    module where it crosses;
  * the failed-week hold is folded into the day's load policy;
  * today.py keeps only the caching around these.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from services import decision
from services import sessions as sess
from services import week_repeat as wr
from services.models import Phase

ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 10, 27)
BLOCK = Phase(5, "12-week block", "2026-10-19", 84, "active")


class FakeRepo:
    """The reads behind the directive; each records the day it was asked for."""

    def __init__(self, fail=(), oura=None):
        self.days: list[tuple[str, date | None]] = []
        self.fail = set(fail)
        self.oura = oura or {}

    def get_biometric_rolling(self, days=28, today=None):
        self.days.append(("bio", today))
        if "bio" in self.fail:
            raise RuntimeError("bio failed")
        return []

    def get_daily_session_au_weighted(self, days=28, today=None):
        self.days.append(("au", today))
        return []

    def get_diagnostic_profile(self):
        return {}

    def get_current_stage(self):
        return 2

    def get_pain_free_streak(self, today=None):
        self.days.append(("streak", today))
        return 0

    def get_phases(self):
        return [BLOCK]

    def hrv_trend_series(self, days=90, today=None):
        self.days.append(("hrv", today))
        if "hrv" in self.fail:
            raise RuntimeError("hrv failed")
        return {"oura": self.oura}


def test_every_read_behind_the_directive_ends_on_the_day_asked_for():
    repo = FakeRepo()
    directive = decision.directive(repo, DAY)
    assert directive != decision.NO_OPINION
    assert {kind for kind, _ in repo.days} == {"bio", "au", "streak"}
    assert {day for _, day in repo.days} == {DAY}


def test_a_failed_read_gives_no_opinion():
    assert decision.directive(FakeRepo(fail={"bio"}), DAY) == decision.NO_OPINION


def test_the_hrv_note_costs_no_read_when_hrv_already_drives_the_light():
    reads = []
    note = decision.hrv_note({"_traffic_drivers": ("hrv_ms",)}, DAY,
                             lambda: reads.append(1) or {})
    assert note == "" and reads == []


def test_a_failed_hrv_read_is_an_empty_caption_not_a_grey_directive():
    repo = FakeRepo(fail={"hrv"})
    verdict = decision.day_verdict(repo, DAY)
    assert verdict.hrv_note == ""
    assert decision.directive(repo, DAY) != decision.NO_OPINION


def test_the_verdict_reads_its_rows_for_the_day():
    repo = FakeRepo()
    decision.day_verdict(repo, DAY)
    assert ("hrv", DAY) in repo.days
    assert all(day == DAY for _, day in repo.days)


def _imported_names(rel: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse((ROOT / rel).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.update(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            names.update((node.module or "").split("."))
            names.update(alias.name for alias in node.names)
    return names


def test_no_guardrail_can_import_the_module_where_the_trend_crosses():
    for guardrail in ("engine", "rules", "readiness", "biometrics", "scheduling",
                      "dashboard", "metrics", "metrics_logic", "sessions", "verdict",
                      "week_repeat", "plan", "strain_regions"):
        assert "decision" not in _imported_names(f"services/{guardrail}.py"), guardrail


def test_the_trend_crosses_only_as_its_advisory_sentence():
    tree = ast.parse((ROOT / "services" / "decision.py").read_text(encoding="utf-8"))
    used = {node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "hrv_trend"}
    assert used == {"ring_run_advisory"}


def test_a_failed_week_holds_the_load_in_the_days_policy():
    failed, _ = wr.apply_failed_week_rule([BLOCK], {"2026-10-19"}, date(2026, 10, 26))
    assert wr.failed_week_holds_load(failed, DAY)
    policy = sess.load_policy(None, None)
    assert decision.training_policy(policy, failed, DAY) == sess.hold_for_failed_week(policy)
    assert decision.training_policy(policy, [BLOCK], DAY) is policy
    assert decision.training_policy(policy, [], DAY) is policy


def test_today_py_only_caches_the_composition():
    tree = ast.parse((ROOT / "today.py").read_text(encoding="utf-8"))
    bodies = {node.name: ast.unparse(node) for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef)}
    assert "decision.directive(" in bodies["today_directive"]
    assert "decision.readiness_rows(" in bodies["_bio_for_readiness"]
    assert "decision.readiness_modifier(" in bodies["today_readiness_modifier"]
    assert "decision.readiness_raw(" in bodies["today_readiness_raw"]
    assert "decision.hrv_note(" in bodies["today_hrv_note"]
    assert "engine." not in "".join(bodies.values())
