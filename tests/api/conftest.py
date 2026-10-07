"""Puts api/ on the import path so the tests can import `healthapi`.

The engine API lives in api/healthapi (rebuild Phase 0). In the container it is
started with `uvicorn ... --app-dir api`; here the same directory is added to
sys.path once.
"""

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parents[2] / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))
