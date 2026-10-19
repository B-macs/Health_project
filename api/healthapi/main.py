"""The FastAPI app: `uvicorn healthapi.main:app` with PYTHONPATH=<repo root>:<repo root>/api.

create_app() is the factory the tests use with `startup=False` (no Config, no
cache rebuild, a fake Repository through a dependency override). The module
attribute `app` is the hosted one: it rebuilds the cache at startup.

No /docs, /redoc or /openapi.json route: the schema is exported to
shared/openapi.json by healthapi.export_openapi instead, so nothing about the
engine is published by the engine itself.
"""

from __future__ import annotations

import time

_T0 = time.perf_counter()

import logging  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from . import __version__, engine, settings  # noqa: E402
from .auth import require_engine_key  # noqa: E402
from .routes import checkin, health, probes, readiness, status, today, today_detail  # noqa: E402

_IMPORT_SECONDS = time.perf_counter() - _T0

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def create_app(startup: bool = True, with_probes: bool | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if startup:
            engine.startup(import_seconds=_IMPORT_SECONDS)
        yield

    app = FastAPI(title="Health engine", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None,
                  dependencies=[Depends(require_engine_key)])

    @app.exception_handler(HTTPException)
    async def _one_error_shape(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)},
                            headers={"Cache-Control": "no-store"})

    # The router's own refusals (an unknown route, a wrong method) are
    # Starlette's, not FastAPI's, and answered {"detail": ...} until
    # 2026-10-19: one error shape for everything (Phase 0's open item).
    _ROUTER_ERRORS = {404: "not_found", 405: "method_not_allowed"}

    @app.exception_handler(StarletteHTTPException)
    async def _router_error_shape(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content={"error": _ROUTER_ERRORS.get(exc.status_code, str(exc.detail))},
                            headers={"Cache-Control": "no-store"})

    @app.exception_handler(RequestValidationError)
    async def _invalid_request_shape(_request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        return JSONResponse(status_code=422,
                            content={"error": f"invalid_request: {where} {first.get('msg', '')}".strip()},
                            headers={"Cache-Control": "no-store"})

    @app.exception_handler(Exception)
    async def _crash_is_json_too(_request: Request, _exc: Exception) -> JSONResponse:
        # Every engine answer is JSON, a crash included: the Worker retries a
        # non-JSON 5xx as Google's own refusal, which the engine never saw.
        # The traceback still reaches the log (Starlette re-raises after this).
        return JSONResponse(status_code=500, content={"error": "internal"},
                            headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def _no_store(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health.router)
    app.include_router(readiness.router)
    app.include_router(today.router)
    app.include_router(today_detail.router)
    app.include_router(status.router)
    app.include_router(checkin.router)
    if settings.probes_enabled() if with_probes is None else with_probes:
        app.include_router(probes.router)
    return app


app = create_app()
