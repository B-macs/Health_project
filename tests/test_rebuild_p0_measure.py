"""scripts/rebuild_p0_measure.py: Phase 0's timings, taken without showing a key.

These pin the three things the measurement must get right: a cold start is
counted only when the answering instance started inside the request's own
window (the first request after a deploy is usually warm); the proof numbers
come from cold samples only; and nothing the script keeps or prints carries
the engine key, the access key or the engine's address. No network.
"""

from __future__ import annotations

import io
import json

from scripts import rebuild_p0_measure as m

KEY = "engine-key-that-must-never-show"
URL = "https://engine-address-kept-out-of-the-repo.example"


def test_an_instance_started_inside_the_request_is_cold():
    assert m.is_cold("2026-10-19T10:00:00+00:00", 8.4, "2026-10-19T10:00:03+00:00") is True
    # started_at is written to the second, so a start just before "sent" still counts
    assert m.is_cold("2026-10-19T10:00:01+00:00", 8.4, "2026-10-19T10:00:00+00:00") is True


def test_an_instance_from_before_the_request_is_warm():
    assert m.is_cold("2026-10-19T10:20:00+00:00", 0.2, "2026-10-19T10:00:03+00:00") is False
    assert m.is_cold("2026-10-19T10:20:00+00:00", 0.2, None) is None


def test_the_summary_reads_cold_samples_only():
    samples = [
        {"kind": "cold", "via": "direct", "status": 200, "seconds": 0.3, "cold": False},
        {"kind": "cold", "via": "direct", "status": 200, "seconds": 7.0, "cold": True,
         "engine_timings": {"imports_s": 2.0, "cache_rebuild_s": 4.0}},
        {"kind": "cold", "via": "direct", "status": 200, "seconds": 9.0, "cold": True,
         "engine_timings": {"imports_s": 2.2, "cache_rebuild_s": 5.0}},
        {"kind": "cold", "via": "direct", "status": 200, "seconds": 12.0, "cold": True,
         "engine_timings": {"imports_s": 2.4, "cache_rebuild_s": 6.0}},
        {"kind": "warm_after_cold", "via": "direct", "status": 200, "seconds": 0.10, "cold": False},
        {"kind": "warm_after_cold", "via": "worker", "status": 200, "seconds": 0.16, "cold": False},
    ]
    out = m.summarise(samples)
    assert out["cold_start_runs_s"] == [7.0, 9.0, 12.0]       # the warm "cold" try is left out
    assert out["cold_start_median_s"] == 9.0
    assert out["cold_start_worst_s"] == 12.0
    assert out["warm_request_ms"] == 100
    assert out["worker_to_engine_ms"] == 60
    assert out["cold_start_engine_timings_median_s"] == {"cache_rebuild_s": 5.0, "imports_s": 2.2}


def test_no_cold_sample_means_no_number():
    out = m.summarise([{"kind": "cold", "status": 200, "seconds": 0.2, "cold": False}])
    assert out["cold_start_median_s"] is None and out["cold_start_worst_s"] is None


def test_the_summary_can_keep_to_one_build(monkeypatch, tmp_path, capsys):
    log = tmp_path / "p0_measure.jsonl"
    log.write_text("\n".join(json.dumps(s) for s in [
        {"kind": "cold", "status": 200, "seconds": 10.7, "cold": True, "build": "old"},
        {"kind": "cold", "status": 200, "seconds": 8.0, "cold": True, "build": "new"},
    ]), encoding="utf-8")
    monkeypatch.setattr(m, "LOG", log)
    m.main(["summary", "--build", "new"])
    assert json.loads(capsys.readouterr().out)["cold_start_runs_s"] == [8.0]


def test_a_monitoring_total_adds_doubles_and_int64_strings():
    series = [{"points": [{"value": {"doubleValue": 10.5}}, {"value": {"doubleValue": 2.0}}]},
              {"points": [{"value": {"int64Value": "7"}}]},
              {"points": []}]
    assert m.series_total(series) == 19.5
    assert m.series_total([]) == 0.0


def test_the_access_key_is_read_from_env_with_or_without_a_bom(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes(b"\xef\xbb\xbfHEALTH_ACCESS_KEY=\"abc-DEF_123\"\n")
    assert m.access_key(env) == "abc-DEF_123"


class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_sample_and_its_printed_line_carry_no_key_and_no_address(monkeypatch, tmp_path, capsys):
    sent = {}

    def fake_urlopen(request, timeout, context=None):
        sent["url"], sent["headers"] = request.full_url, dict(request.header_items())
        return _Response(json.dumps({"started_at": None, "timings": {}}).encode())

    monkeypatch.setattr(m.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(m, "LOG", tmp_path / "p0_measure.jsonl")
    sample = m.health_sample("warm", "direct", target=(URL, KEY))
    m.record(sample)
    assert sent["url"] == URL + "/api/health"
    assert sent["headers"]["X-engine-key"] == KEY                 # it IS sent ...
    # Cloudflare answers Python's default User-Agent with a 403 page.
    assert sent["headers"]["User-agent"] == m.USER_AGENT
    written = (tmp_path / "p0_measure.jsonl").read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    for text in (json.dumps(sample), written, printed):           # ... and never kept or shown
        assert KEY not in text and URL not in text


def test_auto_goes_through_the_worker_only_once_it_holds_its_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "LOG", tmp_path / "p0_measure.jsonl")
    calls = []

    def fake_health_sample(kind, via, target=None):
        calls.append(via)
        status = worker_status if via == "worker" else 200
        return {"kind": kind, "via": via, "status": status, "seconds": 0.1}

    monkeypatch.setattr(m, "health_sample", fake_health_sample)
    worker_status = 503                                           # no keys yet: the engine stays asleep
    assert m.cold_sample("auto", (URL, KEY))["via"] == "direct" and calls == ["worker", "direct"]
    calls.clear()
    worker_status = 200                                           # keys set: the Worker's answer IS the sample
    assert m.cold_sample("auto", (URL, KEY))["via"] == "worker" and calls == ["worker"]


def test_the_garmin_probe_needs_the_owners_ok(monkeypatch):
    monkeypatch.setattr(m, "call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    try:
        m.main(["garmin"])
    except SystemExit as exc:
        assert "owner" in str(exc)
    else:
        raise AssertionError("the Garmin probe ran without --confirm owner-approved")
