"""A "JWT issued at future" refusal from Supabase is tried again; nothing else is.

With the new secret keys Supabase's gateway mints a short JWT for each request,
and a moment of clock difference between it and PostgREST answers 401 PGRST303.
On 2026-10-19 one such refusal stopped the hosted engine's start, and the same
requests worked minutes later. A refused request never ran, so a retry cannot
write twice. Every other error still fails at once. No network.
"""

from __future__ import annotations

import email.message
import io
import json
import urllib.error

import pytest

from services import supabase_store

ROWS = [{"date": "2026-10-19"}]
SKEW = b'{"code":"PGRST303","details":null,"hint":null,"message":"JWT issued at future"}'
EXPIRED = b'{"code":"PGRST301","details":null,"hint":null,"message":"JWT expired"}'


def _refusal(body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://project.example/rest/v1/x", 401, "Unauthorized",
                                  email.message.Message(), io.BytesIO(body))


class _Answer(io.BytesIO):
    headers = email.message.Message()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def store():
    return supabase_store.SupabaseStore("https://project.example", "not-a-real-key")


@pytest.fixture
def waits(monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(supabase_store, "_sleep", slept.append)
    return slept


def _serve(monkeypatch, answers: list):
    def fake_urlopen(request, timeout):
        answer = answers.pop(0)()
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(supabase_store.urllib.request, "urlopen", fake_urlopen)


def test_a_clock_skew_refusal_is_tried_again(monkeypatch, store, waits):
    _serve(monkeypatch, [lambda: _refusal(SKEW), lambda: _refusal(SKEW),
                         lambda: _Answer(json.dumps(ROWS).encode())])
    assert store.select("metrics_history") == ROWS
    assert waits == [0.5, 1.0]


def test_a_lasting_clock_skew_still_fails_after_three_more_tries(monkeypatch, store, waits):
    _serve(monkeypatch, [lambda: _refusal(SKEW)] * 4)
    with pytest.raises(supabase_store.SupabaseError, match="PGRST303"):
        store.select("metrics_history")
    assert waits == list(supabase_store.CLOCK_SKEW_RETRY_S)


def test_any_other_refusal_fails_at_once(monkeypatch, store, waits):
    _serve(monkeypatch, [lambda: _refusal(EXPIRED)])
    with pytest.raises(supabase_store.SupabaseError, match="PGRST301"):
        store.select("metrics_history")
    assert waits == []
