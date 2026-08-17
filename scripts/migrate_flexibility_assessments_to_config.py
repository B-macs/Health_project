# -*- coding: utf-8 -*-
"""One-time: push the locally-held flexibility assessments into Notion Config.

Why this exists. Assessments lived ONLY in .sync_state.json — gitignored,
local, wiped by any hosted redeploy — and that has already cost three of the
four cold-morning battery captures (the surviving entry is itself stamped
"RECONSTRUCTED after the only copy was lost"). save_flexibility_assessment now
writes through to the Notion Config row `flexibility_assessments` on every
save, but the one existing assessment predates that and sits local-only until
either the athlete re-runs the battery (he should not have to) or this script
pushes it once.

Idempotent: re-running overwrites the config row with the same local content.
Refuses to run offline (set_config raises there, which is correct).

Usage:  python scripts/migrate_flexibility_assessments_to_config.py
"""
from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.clients import local_cache
from services.config import load_config
from services.repository import Repository

_KEY = "flexibility_assessments"


def main() -> int:
    raw = local_cache.read().get(_KEY)
    if not raw:
        print("nothing to migrate: no local assessments in .sync_state.json")
        return 0

    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    overrides = {}
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            overrides = tomllib.load(f)
    repo = Repository(load_config(overrides))

    payload = json.dumps(raw)
    repo.set_config(_KEY, payload)
    print("pushed %d assessment(s), %d chars, to Notion Config %r"
          % (len(raw), len(payload), _KEY))

    # Read back through the repository's own path, as the app would after a
    # redeploy wiped the local file — not just "the write returned".
    stored = repo.get_config_value(_KEY)
    if stored is None:
        print("VERIFY FAILED: config row reads back empty")
        return 1
    if json.loads(stored) != raw:
        print("VERIFY FAILED: config row does not match local content")
        return 1
    print("verified: config round-trips identical to local")
    return 0


if __name__ == "__main__":
    sys.exit(main())
