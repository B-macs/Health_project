"""
services/switchover.py — the one-time step the hosted app takes the first time
it starts with Supabase as the system of record (2026-10-09).

The switch happens when the new code is deployed, which is the athlete's push,
not a moment this repo controls. Until then the old app keeps writing Notion
and Google Sheets first and Supabase second, through a queue that a restart
can lose — the failure that hid three sessions on 2026-10-09. So the first
start on Supabase:

  1. records the switch time (record_cache.RECORD_SINCE_KEY). From here Notion
     and Sheets are a frozen archive, and the tools that copy them into
     Supabase refuse to delete or overwrite anything;
  2. reads Notion and Sheets once, live, copies every row they hold that
     Supabase does not, and fills every column Supabase holds blank where
     they hold a value — ADD-ONLY: nothing is deleted and no value is
     overwritten, because Supabase may already hold newer ones;
  3. records that the catch-up is done (CATCH_UP_KEY), so it runs once.

Step 1 comes first on purpose: the marker is what stops a full reconcile from
deleting rows logged after the switch, so it must exist before anything else
can go wrong. A failed catch-up is retried at the next start; it never stops
the app, which is already serving from Supabase.

Runs on its own thread with its OWN Repository objects (key rule 12): one in
Supabase-record mode for the writes, one reading the legacy stores live.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import datetime

from services import datastore, reconcile, record_cache
from services.repository import Repository

CATCH_UP_KEY = "supabase_catch_up_done"


def legacy_config(config):
    """The same credentials, reading Notion and Sheets live."""
    return dataclasses.replace(config, system_of_record="notion",
                               datastore_path="", datastore_mode="readonly")


def _read_legacy(config) -> sqlite3.Connection:
    source = sqlite3.connect(":memory:")
    datastore.rebuild(Repository(legacy_config(config)), source)
    return source


def finish(config, now: datetime | None = None, read_legacy=_read_legacy,
           record_factory=Repository) -> dict:
    """Mark the switch, then copy what only the archive holds; returns
    {table: rows copied} ({} when there was nothing to do). Never raises."""
    try:
        if not record_cache.is_supabase_record(config):
            return {}
        record = record_factory(config)
        record.mark_record_since(now)
        if record.get_config_value(CATCH_UP_KEY):
            return {}
        source = read_legacy(config)
        diffs = reconcile.diff_all(source, record._ds)
        fills = reconcile.blank_fills(source, record._ds, diffs)
        copied = reconcile.copy_missing(record, source, reconcile.missing_only(diffs))
        for table, n in reconcile.fill_blanks(record, fills).items():
            copied[f"{table} (blanks filled)"] = n
        record.set_config(CATCH_UP_KEY, json.dumps({
            "at": (now or datetime.now()).isoformat(timespec="seconds"),
            "rows": copied}))
        return copied
    except Exception:
        return {}
