"""Writes shared/openapi.json from the app's models.

    PYTHONPATH=api python -m healthapi.export_openapi           (from the repo root)
    PYTHONPATH=api python -m healthapi.export_openapi --check   (exit 1 if stale)

The Phase 0 probes are diagnostics and stay out of the contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .main import create_app

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "shared" / "openapi.json"


def render() -> str:
    spec = create_app(startup=False, with_probes=False).openapi()
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        current = OPENAPI_PATH.read_text(encoding="utf-8") if OPENAPI_PATH.exists() else ""
        if current != text:
            print("shared/openapi.json is stale: run PYTHONPATH=api python -m healthapi.export_openapi")
            return 1
        return 0
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OPENAPI_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
