"""Identical reads that arrive together share one answer (2026-10-22).

The owner's first open of 2026-10-22 sent about 35 reads in the first minute,
most of them the same few addresses again and again: /api/training/day fifteen
times, /api/training/session five times. The phone sends a screen's reads
again at every tab change, and it stops waiting after 30 s while the engine
goes on working. On the engine's one processor every copy was computed in
full, side by side, so each took longer: today's session took 45-64 s, and the
phone had stopped waiting at 30 s and said there was no connection. Measured on
this PC over a read-only copy, the same 24 reads at once took 13.3 s; the 8
different ones, each computed once, took 3.0 s.

A GET that arrives while the same GET is being computed waits for that
computation and gets its answer; nothing is kept after it, so the next GET
computes again. "The same" is the whole address (path and query), the caller's
day (X-Local-Date), the access key and the write counter
(services.clients.sheets.write_generation): a read never takes an answer from
another key, another day, or from before a write it came after. A read whose
first copy failed (a server error, a crash, an answer cut off) is computed
again on its own.

`limit` (HEALTH_READ_SLOTS, default 2) caps how many GETs compute at once: on
one processor, parallel reads slow each other down (the 8 different reads above
took 3.0 s at once and 2.1 s one at a time; with sharing, 2 at a time took the
24 reads from 12.4 s to 1.7 s). The status and health reads never wait for a
slot, being quick; nor do the reads that wait on another server rather than on
this processor (Oura, the probes, the Garmin taps and the outdoor list).
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import weakref
from collections.abc import Callable

from services.clients import sheets

#: GETs that never wait for a slot (prefixes): quick, or waiting on another server.
UNLIMITED = ("/api/status", "/api/health", "/api/oura", "/api/probe", "/api/training/garmin/",
             "/api/training/outdoor")
DEFAULT_SLOTS = 2


def slots_from_env() -> int | None:
    """HEALTH_READ_SLOTS: how many GETs compute at once; "off" or 0 for no limit."""
    raw = os.environ.get("HEALTH_READ_SLOTS", "").strip().lower()
    if raw in ("off", "0", "none"):
        return None
    try:
        return max(1, int(raw)) if raw else DEFAULT_SLOTS
    except ValueError:
        return DEFAULT_SLOTS


class SharedReads:
    """Pure ASGI middleware; see the module docstring."""

    def __init__(self, app, limit: int | None = DEFAULT_SLOTS,
                 generation: Callable[[], int] = sheets.write_generation):
        self.app = app
        self._generation = generation
        self._limit = limit
        # One event loop in the server; the tests' clients may run one per request, and an
        # asyncio future or semaphore belongs to the loop it was made in: both are kept per loop.
        self._slots: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        #: The GETs being computed now, by key: their answer when it comes (None: none).
        self.inflight: dict[tuple, asyncio.Future] = {}

    def _key(self, scope) -> tuple:
        headers = dict(scope.get("headers") or [])
        engine_key = hashlib.sha256(headers.get(b"x-engine-key", b"")).hexdigest()
        return (id(asyncio.get_running_loop()), scope.get("path", ""), scope.get("query_string", b""),
                headers.get(b"x-local-date", b""), engine_key, self._generation())

    async def _compute(self, scope, receive, send) -> None:
        path = scope.get("path", "")
        if self._limit is None or path.startswith(UNLIMITED):
            await self.app(scope, receive, send)
            return
        loop = asyncio.get_running_loop()
        slots = self._slots.get(loop)
        if slots is None:
            slots = self._slots.setdefault(loop, asyncio.Semaphore(self._limit))
        async with slots:
            await self.app(scope, receive, send)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("method") != "GET":
            await self.app(scope, receive, send)
            return
        key = self._key(scope)
        first = self.inflight.get(key)
        if first is not None:
            messages = await asyncio.shield(first)
            if messages is not None:
                for message in messages:
                    await send(message)
                return
            await self._compute(scope, receive, send)
            return
        answer: asyncio.Future = asyncio.get_running_loop().create_future()
        self.inflight[key] = answer
        sent: list[dict] = []

        async def keep(message) -> None:
            sent.append(message)
            await send(message)

        try:
            await self._compute(scope, receive, keep)
        finally:
            if self.inflight.get(key) is answer:
                del self.inflight[key]
            whole = (len(sent) >= 2 and sent[0]["type"] == "http.response.start"
                     and sent[0].get("status", 500) < 500
                     and sent[-1]["type"] == "http.response.body"
                     and not sent[-1].get("more_body", False))
            answer.set_result(sent if whole else None)
