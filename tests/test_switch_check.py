"""The checks before the switch-over (rebuild Phase 9, 9.1; scripts/switch_check.py).

The switch waits until every check passes and the owner confirms his own: a failed check
is named, a missing report is a failure (never a pass), and the owner's phone check is
his, never ticked by the script.
"""

from __future__ import annotations

import json
from datetime import date

from scripts import switch_check as sc


def test_the_verdict_is_ready_only_when_every_check_passed():
    passed = [sc.result(n, True, "") for n in ("rows", "parity")]
    assert sc.verdict(passed) == "ready"
    assert sc.verdict(passed + [sc.result("outbox", None, "")]) == "waits for the owner: outbox"
    assert sc.verdict(passed + [sc.result("backups", False, ""), sc.result("outbox", None, "")]) \
        == "not ready: backups"


def test_parity_fails_on_any_difference_and_on_a_missing_report():
    clean = {"differences": [], "unanswered": [], "sleep_rule_violations": []}
    assert sc.check_parity(run=lambda insights, days: clean)["ok"] is True
    one = {**clean, "differences": [{"date": "2026-10-15", "endpoint": "x", "field": "y"}]}
    assert sc.check_parity(run=lambda insights, days: one if insights else clean)["ok"] is False
    assert sc.check_parity(run=lambda insights, days: None)["ok"] is False


def test_backups_name_each_day_without_a_copy_and_a_failed_listing_fails():
    from services import backup
    today = date(2026, 10, 20)
    every = [backup.object_name(date(2026, 10, d)) for d in range(13, 20)]
    assert sc.check_backups(today, names=lambda: every)["ok"] is True
    gap = sc.check_backups(today, names=lambda: [n for n in every if "10-17" not in n])
    assert gap["ok"] is False and "2026-10-17" in gap["detail"]

    def broken():
        raise RuntimeError("no answer")
    assert sc.check_backups(today, names=broken)["ok"] is False


def test_the_rehearsal_passes_only_inside_its_limit(tmp_path):
    assert sc.check_rehearsal(tmp_path / "none.json")["ok"] is False
    record = tmp_path / "rehearsal.json"
    record.write_text(json.dumps({"ok": True, "seconds": 41.2, "limit_seconds": 280}))
    assert sc.check_rehearsal(record)["ok"] is True
    record.write_text(json.dumps({"ok": True, "seconds": 300, "limit_seconds": 280}))
    assert sc.check_rehearsal(record)["ok"] is False


def test_the_owners_phone_is_his_check():
    assert sc.check_outbox()["ok"] is None
