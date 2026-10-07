"""scripts/rebuild_secrets.py -- the rebuild's secrets, moved without being shown.

The OWNER runs these (CLAUDE.md rebuild rule 12). No value is ever printed,
logged or written to a file here: each one goes from where it is made or kept
straight into the program that stores it, through a pipe this script opens.
A shell pipe is avoided on purpose: Windows PowerShell adds a line break to
piped text, and the Worker's copy of a key would then not match Google's.

    python scripts/rebuild_secrets.py engine-key          make health-engine-key in Secret Manager
    python scripts/rebuild_secrets.py worker-engine-key   copy it into the Worker as ENGINE_KEY
    python scripts/rebuild_secrets.py worker-access-key   copy .env's HEALTH_ACCESS_KEY into the Worker as ACCESS_KEY
    python scripts/rebuild_secrets.py worker-engine-url   put the Cloud Run address into the Worker as ENGINE_URL

health-engine-secrets (the copy of .streamlit/secrets.toml) is made by gcloud
directly from the file: `gcloud secrets create health-engine-secrets
--replication-policy=automatic --data-file=.streamlit/secrets.toml`.
"""

from __future__ import annotations

import secrets
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WRANGLER = REPO_ROOT / "worker" / "node_modules" / "wrangler" / "bin" / "wrangler.js"
ENGINE_KEY_SECRET = "health-engine-key"
ENGINE_SERVICE = "health-engine"
REGION = "europe-west1"


def _gcloud() -> str:
    path = shutil.which("gcloud")
    if not path:
        sys.exit("gcloud is not installed or not on PATH (open a new terminal after installing).")
    return path


def _run(cmd: list[str], *, data: bytes | None = None,
         cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, input=data, cwd=cwd, capture_output=True)
    if proc.returncode != 0:
        # The tool's own error text, never the value sent to it.
        sys.exit(f"{Path(cmd[0]).name} failed ({proc.returncode}): "
                 + proc.stderr.decode("utf-8", "replace").strip()[-400:])
    return proc


def _wrangler_put(name: str, value: bytes) -> None:
    node = shutil.which("node")
    if not node or not WRANGLER.exists():
        sys.exit("node or worker/node_modules/wrangler is missing (run pnpm install).")
    _run([node, str(WRANGLER), "secret", "put", name], data=value, cwd=REPO_ROOT / "worker")
    print(f"Worker secret {name} set.")


def engine_key() -> None:
    value = secrets.token_urlsafe(32).encode("ascii")
    _run([_gcloud(), "secrets", "create", ENGINE_KEY_SECRET,
          "--replication-policy=automatic", "--data-file=-"], data=value)
    print(f"Secret Manager: {ENGINE_KEY_SECRET} created (32 random bytes, never shown).")


def worker_engine_key() -> None:
    proc = _run([_gcloud(), "secrets", "versions", "access", "latest",
                 f"--secret={ENGINE_KEY_SECRET}"])
    _wrangler_put("ENGINE_KEY", proc.stdout)


def worker_access_key() -> None:
    env = REPO_ROOT / ".env"
    value = None
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("HEALTH_ACCESS_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not value:
        sys.exit("HEALTH_ACCESS_KEY is not in Health_project/.env.")
    _wrangler_put("ACCESS_KEY", value.encode("utf-8"))


def worker_engine_url() -> None:
    proc = _run([_gcloud(), "run", "services", "describe", ENGINE_SERVICE,
                 f"--region={REGION}", "--format=value(status.url)"])
    url = proc.stdout.strip()
    if not url.startswith(b"https://"):
        sys.exit("Cloud Run did not return an https address for health-engine.")
    _wrangler_put("ENGINE_URL", url)


COMMANDS = {
    "engine-key": engine_key,
    "worker-engine-key": worker_engine_key,
    "worker-access-key": worker_access_key,
    "worker-engine-url": worker_engine_url,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
