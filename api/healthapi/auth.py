"""The shared key between the Cloudflare Worker and the engine.

Every route needs `X-Engine-Key`. The Worker adds it after checking the
owner's access key, so the engine never sees the owner's key and the phone
never sees this one. Constant-time compare; a missing key on the server side
answers 503 rather than letting anything through. Why a shared key and not
Cloud Run IAM: docs/rebuild/stack.md.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from . import settings


def require_engine_key(x_engine_key: str | None = Header(default=None)) -> None:
    expected = settings.engine_key()
    if expected is None:
        raise HTTPException(status_code=503, detail="not_configured")
    if not x_engine_key or not hmac.compare_digest(x_engine_key.encode("utf-8"),
                                                   expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="unauthorized")
