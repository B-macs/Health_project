"""scripts/rebuild_secrets.py -- the rebuild's secrets, moved without being shown.

The OWNER runs these (CLAUDE.md rebuild rule 12). No value is ever printed,
logged or written to a file here: each one goes from where it is made or kept
straight into the program that stores it, through a pipe this script opens.
A shell pipe is avoided on purpose: Windows PowerShell adds a line break to
piped text, and the Worker's copy of a key would then not match Google's.

    python scripts/rebuild_secrets.py engine-secrets      put the engine's keys from secrets.toml into Secret Manager
    python scripts/rebuild_secrets.py engine-key          make health-engine-key in Secret Manager
    python scripts/rebuild_secrets.py worker-engine-key   copy it into the Worker as ENGINE_KEY
    python scripts/rebuild_secrets.py worker-access-key   copy .env's HEALTH_ACCESS_KEY into the Worker as ACCESS_KEY
    python scripts/rebuild_secrets.py worker-engine-url   put the Cloud Run address into the Worker as ENGINE_URL

engine-secrets uploads ONLY the keys the engine reads (ENGINE_SECRET_KEYS), not
the whole .streamlit/secrets.toml. With Supabase as the only store (2026-10-09)
the engine never calls Notion or Google Sheets, so their token and service-
account key, and the voice app's keys, stay on this PC.
"""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WRANGLER = REPO_ROOT / "worker" / "node_modules" / "wrangler" / "bin" / "wrangler.js"
SECRETS_TOML = REPO_ROOT / ".streamlit" / "secrets.toml"
ENGINE_SECRETS_SECRET = "health-engine-secrets"
ENGINE_KEY_SECRET = "health-engine-key"
ENGINE_SERVICE = "health-engine"
REGION = "europe-west1"

# What services/config.py load_config reads in Supabase mode and the engine
# uses: the store, the Garmin login, and the Oura app (the refresh after the
# switch-over). Both spellings of the Oura app's keys are accepted there.
ENGINE_SECRET_KEYS = (
    "SUPABASE_URL", "SUPABASE_SECRET_KEY",
    "GARMIN_EMAIL", "GARMIN_PASSWORD",
    "OURA_CLIENT_ID", "OURA_CLIENT_SECRET", "CLIENT_ID", "CLIENT_SECRET",
)
ENGINE_REQUIRED_KEYS = ("SUPABASE_URL", "SUPABASE_SECRET_KEY")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def engine_secrets_toml(data: dict) -> tuple[str, list[str]]:
    """The engine's keys as TOML text, and the names of everything left out.

    Each value is written as a TOML basic string through json.dumps (TOML
    shares JSON's escapes; DEL is escaped by hand, as TOML requires and json
    does not), and the text must read back as exactly the kept values, or
    nothing is returned at all."""
    kept = {k: data[k] for k in ENGINE_SECRET_KEYS if isinstance(data.get(k), str) and data[k]}
    text = "".join(f"{k} = {_toml_string(v)}\n" for k, v in kept.items())
    if tomllib.loads(text) != kept:
        raise ValueError("the engine's keys do not read back identically")
    return text, sorted(k for k in data if k not in kept)


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


def engine_secrets() -> None:
    if not SECRETS_TOML.exists():
        sys.exit(".streamlit/secrets.toml is missing.")
    with SECRETS_TOML.open("rb") as fh:
        data = tomllib.load(fh)
    text, left_out = engine_secrets_toml(data)
    kept = sorted(tomllib.loads(text))
    missing = [k for k in ENGINE_REQUIRED_KEYS if k not in kept]
    if missing:
        sys.exit(f"secrets.toml has no {', '.join(missing)}; the engine cannot start without it.")
    _run([_gcloud(), "secrets", "create", ENGINE_SECRETS_SECRET,
          "--replication-policy=automatic", "--data-file=-"], data=text.encode("utf-8"))
    print(f"Secret Manager: {ENGINE_SECRETS_SECRET} created with {len(kept)} keys: "
          f"{', '.join(kept)}.")
    print(f"Left on this PC (the engine does not use them): {', '.join(left_out)}.")


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
    "engine-secrets": engine_secrets,
    "engine-key": engine_key,
    "worker-engine-key": worker_engine_key,
    "worker-access-key": worker_access_key,
    "worker-engine-url": worker_engine_url,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
