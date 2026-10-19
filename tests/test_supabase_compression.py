"""Supabase answers come compressed, and are unpacked before they are read.

The hosted engine (rebuild Phase 0) copies every table from Supabase at each
cold start: 9.24 MB uncompressed on 2026-10-19, against 5 GB of egress a month
on the Free plan. So every Data API request asks for gzip, and an answer the
server compressed is unpacked before json.loads. These pin both halves, keep
the uncompressed path working, keep a compressed error readable, and keep the
Storage calls of services/backup.py (which share _headers() and read their
answers as they come) from asking for gzip. No network: urlopen is replaced.
"""

from __future__ import annotations

import email.message
import gzip
import io
import json
import urllib.error

import pytest

from services import backup, supabase_store

ROWS = [{"date": "2026-10-18", "value": 1}, {"date": "2026-10-19", "value": 2}]


def _headers(**items) -> email.message.Message:
    msg = email.message.Message()
    for name, value in items.items():
        msg[name.replace("_", "-")] = value
    return msg


class _Answer(io.BytesIO):
    def __init__(self, body: bytes, headers: email.message.Message):
        super().__init__(body)
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def store():
    return supabase_store.SupabaseStore("https://project.example", "not-a-real-key")


def _serve(monkeypatch, answer):
    sent = []

    def fake_urlopen(request, timeout):
        sent.append(dict(request.header_items()))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(supabase_store.urllib.request, "urlopen", fake_urlopen)
    return sent


def test_every_data_api_request_asks_for_gzip(monkeypatch, store):
    sent = _serve(monkeypatch, _Answer(json.dumps(ROWS).encode(), _headers()))
    store.select("garmin_sleep_stages")
    assert sent[0]["Accept-encoding"] == "gzip"


def test_a_compressed_answer_is_unpacked_before_it_is_read(monkeypatch, store):
    body = gzip.compress(json.dumps(ROWS).encode())
    _serve(monkeypatch, _Answer(body, _headers(Content_Encoding="gzip")))
    assert store.select("garmin_sleep_stages") == ROWS


def test_an_uncompressed_answer_still_reads(monkeypatch, store):
    _serve(monkeypatch, _Answer(json.dumps(ROWS).encode(), _headers()))
    assert store.select("garmin_sleep_stages") == ROWS


def test_a_compressed_error_still_names_the_complaint(monkeypatch, store):
    complaint = b'{"message":"column \\"nope\\" does not exist"}'
    error = urllib.error.HTTPError("https://project.example/rest/v1/x", 400, "Bad Request",
                                   _headers(Content_Encoding="gzip"),
                                   io.BytesIO(gzip.compress(complaint)))
    _serve(monkeypatch, error)
    with pytest.raises(supabase_store.SupabaseError, match='column .*nope.* does not exist'):
        store.select("garmin_sleep_stages")


def test_a_caller_header_does_not_drop_the_gzip_ask(monkeypatch, store):
    sent = _serve(monkeypatch, _Answer(b"", _headers(Content_Range="0-0/7")))
    assert store.count("garmin_sleep_stages") == 7                # sends Prefer and Range
    assert sent[0]["Accept-encoding"] == "gzip" and sent[0]["Range"] == "0-0"


def test_the_backup_storage_calls_do_not_ask_for_gzip(store):
    # backup.Storage reads its answers without unpacking them, so the gzip ask
    # must stay in _request and out of the shared _headers().
    assert "Accept-Encoding" not in backup.Storage(store)._headers()
    assert "Accept-Encoding" not in store._headers()
