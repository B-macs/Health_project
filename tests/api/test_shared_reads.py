"""Identical reads that arrive together share one answer (api/healthapi/shared_reads.py).

The owner's first open of 2026-10-22 sent /api/training/day fifteen times and
/api/training/session five times in about a minute, and the engine computed
every copy side by side on its one processor: today's session took 45-64 s.
What these tests pin:

- a GET that arrives while the same GET is computed gets that answer, and the
  engine computes it once;
- "the same" is the path, the query, the caller's day, the access key and the
  write counter: a read never takes another day's, another key's, or a
  pre-write answer;
- nothing is kept after the answer: the next GET computes again;
- a first copy that fails leaves the next one to compute on its own;
- only `limit` GETs compute at once, and the quick or device-bound reads never
  wait for a place;
- the real app has the layer, with the limit from HEALTH_READ_SLOTS.

No network.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")

import httpx  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402

from healthapi import shared_reads  # noqa: E402
from healthapi.main import create_app  # noqa: E402
from healthapi.shared_reads import SharedReads  # noqa: E402

KEY = {"X-Engine-Key": "k", "X-Local-Date": "2026-10-22"}


class Engine:
    """A tiny app: /slow answers once `release` is set, and counts its computations."""

    def __init__(self, limit=None, fail_first=False):
        self.computed = 0
        self.active = 0
        self.most = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.fail_first = fail_first
        self.generation = 0

        async def slow(request: Request):
            self.computed += 1
            n = self.computed
            self.active += 1
            self.most = max(self.most, self.active)
            self.entered.set()
            try:
                await self.release.wait()
                if self.fail_first and n == 1:
                    raise RuntimeError("the first copy fails")
                return JSONResponse({"n": n, "q": str(request.query_params)})
            finally:
                self.active -= 1

        async def write(_request: Request):
            self.computed += 1
            return JSONResponse({"n": self.computed})

        inner = Starlette(routes=[
            Route("/api/slow", slow), Route("/api/other", slow), Route("/api/status", slow),
            Route("/api/slow", write, methods=["POST"]),
        ])
        self.layer = SharedReads(inner, limit=limit, generation=lambda: self.generation)

    def client(self) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=self.layer, raise_app_exceptions=False)
        return httpx.AsyncClient(transport=transport, base_url="http://engine")


async def _second_waits(engine: Engine, client: httpx.AsyncClient, first_path: str, second_path: str,
                        first_headers=KEY, second_headers=KEY, between=None, method="GET"):
    """Send the first read, wait until it computes, send the second, then let both answer."""
    first = asyncio.create_task(client.get(first_path, headers=first_headers))
    await engine.entered.wait()
    if between:
        between()
    second = asyncio.create_task(client.request(method, second_path, headers=second_headers))
    for _ in range(20):          # let the second reach the layer
        await asyncio.sleep(0)
    engine.release.set()
    return await first, await second


def run(coro):
    return asyncio.run(coro)


def test_the_same_read_arriving_meanwhile_gets_the_same_answer_computed_once():
    async def main():
        engine = Engine()
        async with engine.client() as c:
            a, b = await _second_waits(engine, c, "/api/slow?x=1", "/api/slow?x=1")
        assert (a.status_code, b.status_code) == (200, 200)
        assert a.json() == b.json() == {"n": 1, "q": "x=1"}
        assert a.headers.get("content-length") == b.headers.get("content-length")
        assert engine.computed == 1
        assert engine.layer.inflight == {}, "nothing is kept after the answer"
    run(main())


@pytest.mark.parametrize("first, second", [
    ("/api/slow?x=1", "/api/slow?x=2"),                       # another query
    ("/api/slow", "/api/other"),                              # another path
])
def test_another_address_is_computed_on_its_own(first, second):
    async def main():
        engine = Engine()
        async with engine.client() as c:
            await _second_waits(engine, c, first, second)
        assert engine.computed == 2
    run(main())


def test_another_day_is_computed_on_its_own():
    async def main():
        engine = Engine()
        async with engine.client() as c:
            await _second_waits(engine, c, "/api/slow", "/api/slow",
                                second_headers={**KEY, "X-Local-Date": "2026-10-23"})
        assert engine.computed == 2
    run(main())


def test_another_key_never_gets_the_answer():
    async def main():
        engine = Engine()
        async with engine.client() as c:
            _, b = await _second_waits(engine, c, "/api/slow", "/api/slow",
                                       second_headers={**KEY, "X-Engine-Key": "someone else"})
        assert engine.computed == 2, "a request with another key computes on its own"
        assert b.json()["n"] == 2
    run(main())


def test_a_read_after_a_write_never_gets_the_answer_from_before_it():
    async def main():
        engine = Engine()

        def write():
            engine.generation += 1
        async with engine.client() as c:
            a, b = await _second_waits(engine, c, "/api/slow", "/api/slow", between=write)
        assert engine.computed == 2
        assert a.json()["n"] != b.json()["n"]
    run(main())


def test_a_write_is_never_shared():
    async def main():
        engine = Engine()
        async with engine.client() as c:
            _, b = await _second_waits(engine, c, "/api/slow", "/api/slow", method="POST")
        assert engine.computed == 2
        assert b.status_code == 200
    run(main())


def test_the_next_read_computes_again():
    async def main():
        engine = Engine()
        engine.release.set()
        async with engine.client() as c:
            a = await c.get("/api/slow", headers=KEY)
            b = await c.get("/api/slow", headers=KEY)
        assert (a.json()["n"], b.json()["n"]) == (1, 2)
    run(main())


def test_a_failed_first_copy_leaves_the_second_to_compute_on_its_own():
    async def main():
        engine = Engine(fail_first=True)
        async with engine.client() as c:
            a, b = await _second_waits(engine, c, "/api/slow", "/api/slow")
        assert a.status_code == 500
        assert b.status_code == 200 and b.json()["n"] == 2
        assert engine.layer.inflight == {}
    run(main())


def test_only_limit_reads_compute_at_once():
    async def main():
        engine = Engine(limit=1)
        async with engine.client() as c:
            first = asyncio.create_task(c.get("/api/slow", headers=KEY))
            await engine.entered.wait()
            second = asyncio.create_task(c.get("/api/other", headers=KEY))
            for _ in range(20):
                await asyncio.sleep(0)
            assert engine.computed == 1, "the second read waits for the place"
            engine.release.set()
            await first, await second
        assert engine.computed == 2 and engine.most == 1
    run(main())


def test_with_no_limit_different_reads_compute_together():
    async def main():
        engine = Engine(limit=None)
        async with engine.client() as c:
            first = asyncio.create_task(c.get("/api/slow", headers=KEY))
            await engine.entered.wait()
            second = asyncio.create_task(c.get("/api/other", headers=KEY))
            for _ in range(20):
                await asyncio.sleep(0)
            engine.release.set()
            await first, await second
        assert engine.most == 2
    run(main())


def test_the_quick_and_device_reads_never_wait_for_a_place():
    async def main():
        engine = Engine(limit=1)
        async with engine.client() as c:
            first = asyncio.create_task(c.get("/api/slow", headers=KEY))
            await engine.entered.wait()
            status = asyncio.create_task(c.get("/api/status", headers=KEY))
            for _ in range(20):
                await asyncio.sleep(0)
            assert engine.most == 2, "the status read runs beside the one holding the place"
            engine.release.set()
            await first, await status
    run(main())
    for path in ("/api/status", "/api/health", "/api/oura/start", "/api/probe/oura",
                 "/api/training/garmin/open-activity", "/api/training/outdoor"):
        assert path.startswith(shared_reads.UNLIMITED), path
    for path in ("/api/today", "/api/training/day", "/api/training/session", "/api/insights/trends"):
        assert not path.startswith(shared_reads.UNLIMITED), path


@pytest.mark.parametrize("raw, slots", [("", 2), ("1", 1), ("3", 3), ("off", None), ("0", None),
                                        ("many", 2)])
def test_the_limit_comes_from_health_read_slots(monkeypatch, raw, slots):
    monkeypatch.setenv("HEALTH_READ_SLOTS", raw)
    assert shared_reads.slots_from_env() == slots


def test_the_app_has_the_layer_outside_its_own_others(monkeypatch):
    monkeypatch.setenv("HEALTH_READ_SLOTS", "2")
    app = create_app(startup=False)
    first = app.user_middleware[0]
    assert first.cls is SharedReads
    assert first.kwargs == {"limit": 2}
