"""
scripts/build_datastore.py -- rebuilds the project's own consolidated
database (default: datastore.db at repo root) from the app's live Notion +
Google Sheets data, via services/datastore.py::rebuild(). Unlike every
other script in this directory, this ONLY writes to a local .db file --
never to Notion/Sheets -- so it has no dry-run/--apply gate; every
invocation just rebuilds the datastore from scratch, full history.

Builds into a temp file beside the target path and only replaces the real
file (os.replace, atomic on the same filesystem) once rebuild() returns
successfully -- so a failed rebuild (a Notion/Sheets call raising, e.g. a
transient API error) leaves any previously-built datastore at the target
path completely untouched, rather than replacing a good file with a
half-built or missing one. See services/datastore.py's module docstring
for why this safety net lives here and not inside rebuild() itself.

Usage:
    python scripts/build_datastore.py                  # writes ./datastore.db
    python scripts/build_datastore.py --path custom.db # writes elsewhere (e.g. ad hoc backups)

Reads credentials from .streamlit/secrets.toml (same file the Streamlit app
uses) or environment variables, via services.config.load_config -- nothing
here reads st.secrets/imports streamlit.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import datastore
from services.config import load_config
from services.repository import Repository

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "datastore.db"


def _load_repo() -> Repository:
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    overrides = {}
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            overrides = tomllib.load(f)
    return Repository(load_config(overrides))


def build(repo: Repository, db_path: Path) -> dict[str, int]:
    """Builds into `db_path`.tmp, then atomically replaces `db_path` only on
    success. Raises (and cleans up the .tmp file) if rebuild() fails,
    leaving any pre-existing file at `db_path` exactly as it was."""
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    conn = sqlite3.connect(tmp_path)
    try:
        counts = datastore.rebuild(repo, conn)
    except Exception:
        conn.close()
        tmp_path.unlink(missing_ok=True)
        raise
    else:
        conn.close()
    os.replace(tmp_path, db_path)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=str(DEFAULT_DB_PATH),
                         help=f"Output .db path (default: {DEFAULT_DB_PATH})")
    args = parser.parse_args()

    repo = _load_repo()
    counts = build(repo, Path(args.path))

    print(f"Rebuilt datastore at {args.path}\n")
    width = max(len(k) for k in counts)
    for table, count in counts.items():
        print(f"  {table:<{width}}  {count}")
    print(f"\n{sum(counts.values())} total rows across {len(counts)} tables.")


if __name__ == "__main__":
    main()
