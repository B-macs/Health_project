# -*- coding: utf-8 -*-
"""Name the process that runs the background writes: the switch-over's one write (rebuild
Phase 9, switch step 3) and its undo.

    python scripts/set_background_writer.py                         # what the store names
    python scripts/set_background_writer.py --to engine             # dry run: what it would write
    python scripts/set_background_writer.py --to engine --apply     # write it, then read it back
    python scripts/set_background_writer.py --to streamlit --apply  # the undo

The setting is one row of the store's config table (services/background_writer), read live
by both processes: from it on, the named process runs the device syncs and the automatic
writes, the other refuses them, and the Streamlit app shows its retired banner when the
engine is named. Nothing else is written. This PC's local state file (it holds a real Oura
login) is pointed at a temporary copy, and the store copy is a temporary file.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import tomllib
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import background_writer  # noqa: E402


def plan(current: str | None, target: str) -> str:
    """What --apply would do, in words."""
    if current == target:
        return f"The store already names {target}; nothing to write."
    return f"Would set {background_writer.CONFIG_KEY} from {current or 'unreadable'} to {target}."


def apply(repo, target: str, today: date) -> str | None:
    """Write `target` and read it back; the value read back (None when unreadable)."""
    if target not in background_writer.WRITERS:
        raise ValueError(f"unknown writer: {target}")
    repo.set_config(background_writer.CONFIG_KEY, target, today=today)
    return background_writer.current(repo)


def _repository():
    from services.clients import local_cache
    tmp = Path(tempfile.mkdtemp(prefix="writer_"))
    local_cache._DEFAULT_PATH = tmp / "sync_state.json"
    from services.config import load_config
    from services.repository import Repository
    secrets = _ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    return Repository(load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase",
                                   "HEALTH_DATASTORE_MODE": "cache",
                                   "HEALTH_DATASTORE_PATH": str(tmp / "record.db")}))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", choices=background_writer.WRITERS, help="the process to name")
    ap.add_argument("--apply", action="store_true", help="write it (otherwise a dry run)")
    args = ap.parse_args(argv)
    repo = _repository()
    current = background_writer.current(repo)
    print(f"The store names: {current or 'nothing readable (nobody writes)'}.")
    if not args.to:
        return 0
    print(plan(current, args.to))
    if not args.apply or current == args.to:
        if not args.apply:
            print("Dry run: nothing written. Add --apply to write.")
        return 0
    read_back = apply(repo, args.to, date.today())
    if read_back != args.to:
        print(f"Read back {read_back!r}, not {args.to!r}: check the store.")
        return 1
    print(f"Written and read back: {read_back}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
