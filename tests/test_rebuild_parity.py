"""scripts/rebuild_parity.py (rebuild Phase 5): the parts that decide what it
reports. It names the FIELD where two answers differ and never a value, and it
counts a night with no score that still carries a night panel or the stepper.
No network: the live run is the script's own job."""

from __future__ import annotations

from scripts import rebuild_parity as parity


def test_equal_answers_have_no_difference():
    answer = {"a": 1, "b": [1, {"c": None}]}
    assert parity.differences(answer, {"a": 1, "b": [1, {"c": None}]}) == []


def test_a_difference_names_its_field_path_and_never_its_value():
    live = {"readiness": {"headline": 72.0, "pair": [{"value": "72"}]}, "only_live": 1}
    local = {"readiness": {"headline": 71.0, "pair": [{"value": "71"}]}}
    found = parity.differences(live, local)
    assert found == ["only_live", "readiness.headline", "readiness.pair[0].value"]
    assert not any(v in " ".join(found) for v in ("72", "71"))


def test_lists_of_another_length_differ_once():
    assert parity.differences({"x": [1, 2]}, {"x": [1]}) == ["x[length]"]


def test_the_sleep_rule_flags_a_panel_without_a_score_only():
    scored = {"contributors": {"scored": True}, "night": {}, "wake": {}}
    unscored_clean = {"contributors": {"scored": False}, "night": None, "wake": None}
    unscored_panel = {"contributors": {"scored": False}, "night": {}, "wake": None}
    unscored_stepper = {"contributors": {"scored": False}, "night": None, "wake": {}}
    assert not parity.sleep_rule_broken(scored)
    assert not parity.sleep_rule_broken(unscored_clean)
    assert parity.sleep_rule_broken(unscored_panel)
    assert parity.sleep_rule_broken(unscored_stepper)


def test_the_parity_run_reads_every_today_endpoint():
    assert set(parity._paths(__import__("datetime").date(2026, 10, 20))) == set(parity.ENDPOINTS)


# ── Phase 8: the Insights answers ────────────────────────────────────────────

def _report() -> dict:
    return {"differences": [], "refused_alike": [], "unanswered": []}


def test_an_insights_answer_both_sides_give_alike_adds_nothing():
    from datetime import date
    report = _report()
    parity.compare_insight(report, "engine", date(2026, 10, 20),
                           {"status": 200, "answer": {"x": 1}}, (200, {"x": 1}))
    assert report == _report()


def test_an_insights_difference_names_the_day_the_endpoint_and_the_field():
    from datetime import date
    report = _report()
    parity.compare_insight(report, "strength", date(2026, 10, 20),
                           {"status": 200, "answer": {"overall": 59.0}}, (200, {"overall": 58.5}))
    assert report["differences"] == [{"date": "2026-10-20", "endpoint": "strength", "field": "overall"}]


def test_a_refusal_both_sides_give_is_listed_apart_and_is_no_difference():
    from datetime import date
    report = _report()
    refused = {"error": "strength_reference_missing"}
    parity.compare_insight(report, "strength", date(2026, 10, 20),
                           {"status": 409, "answer": refused}, (409, refused))
    assert report["differences"] == [] and report["unanswered"] == []
    assert report["refused_alike"] == [{"date": "2026-10-20", "endpoint": "strength",
                                        "error": "strength_reference_missing"}]


def test_one_side_answering_and_the_other_not_is_counted():
    from datetime import date
    report = _report()
    parity.compare_insight(report, "trends", date(2026, 10, 20),
                           {"status": 503, "answer": {"error": "engine_unavailable"}}, (200, {"gate": {}}))
    assert report["unanswered"] == [{"date": "2026-10-20", "endpoint": "trends", "status": 503,
                                     "local_status": 200}]


def test_every_insights_endpoint_has_a_local_answer():
    assert set(parity.INSIGHTS_DAILY) | set(parity.INSIGHTS_ONCE) == {
        "strength", "metabolism", "flexibility", "engine", "queue", "trends", "sleep_architecture",
        "engine_view", "session_checks", "blend_history", "metrics_history"}
