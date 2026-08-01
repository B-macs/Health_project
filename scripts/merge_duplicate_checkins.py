"""
scripts/merge_duplicate_checkins.py -- One-time cleanup for same-day
duplicate Morning Check-In pages in the Notion Readiness database, created
before Repository.save_check_in became an upsert (see services/repository.py
's _CHECKIN_FIELD_MAP / _merge_check_in / _find_check_in_page). Going
forward save_check_in folds a same-day resubmission into the existing page
itself; this script retroactively fixes duplicates that already exist.

For each date with more than one check-in page, folds them into the oldest
page (services.repository.Repository.merge_check_in_group):
  - A scalar field (Tightness, Pain, Condition, ...) that's still at its
    untouched-widget default on every page keeps that default; if exactly
    one page has a real (non-default) value, that value wins.
  - If two pages have two DIFFERENT real values for the same scalar field,
    that's a genuine conflict -- this script skips the date and reports it
    rather than silently picking one; resolve those by hand in Notion.
  - List fields (Body Areas, Sensations) are unioned across all of that
    date's pages, and the Note field is concatenated, rather than one
    page's entry replacing another's -- this is the "if there's overlap,
    add them both in" case, for whenever two check-ins each recorded real,
    distinct information rather than one being a strict superset.

The surviving (oldest) page is updated with the merged fields; the other
page(s) for that date are archived (Notion's own trash, restorable from
there -- never a hard delete).

Usage:
    python scripts/merge_duplicate_checkins.py          # dry run (default)
    python scripts/merge_duplicate_checkins.py --apply  # actually writes + archives

Reads credentials from .streamlit/secrets.toml (same file the Streamlit app
uses) or environment variables, via services.config.load_config -- nothing
here reads st.secrets/imports streamlit.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.config import load_config
from services.repository import Repository


def _load_repo() -> Repository:
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    overrides = {}
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            overrides = tomllib.load(f)
    return Repository(load_config(overrides))


def main() -> None:
    apply = "--apply" in sys.argv
    repo = _load_repo()

    dupes = repo.find_duplicate_check_in_dates()
    if not dupes:
        print("No duplicate same-day check-ins found -- nothing to do.")
        return

    print(f"Found {len(dupes)} date(s) with duplicate check-ins:")
    to_apply: list[tuple[str, dict, list[str]]] = []
    conflicts: list[str] = []
    for d, pages in sorted(dupes.items()):
        result = repo.merge_check_in_group(pages)
        if result is None:
            print(f"  {d}: {len(pages)} pages -- CONFLICT (two different real values "
                  f"for the same field). Skipping; resolve by hand in Notion.")
            conflicts.append(d)
            continue
        primary_id, properties, archive_ids = result
        print(f"  {d}: merging {len(pages)} pages into {primary_id}, archiving {archive_ids}")
        to_apply.append((primary_id, properties, archive_ids))

    if not to_apply:
        print("\nNothing mergeable without manual review.")
        return

    if not apply:
        print(f"\nDry run only -- no changes written. {len(to_apply)} date(s) ready to merge, "
              f"{len(conflicts)} need manual review. Re-run with --apply to write these merges.")
        return

    for primary_id, properties, archive_ids in to_apply:
        repo.apply_check_in_merge(primary_id, properties, archive_ids)
    archived_count = sum(len(a) for _, _, a in to_apply)
    print(f"\nMerged {len(to_apply)} date(s); archived {archived_count} duplicate page(s).")


if __name__ == "__main__":
    main()
