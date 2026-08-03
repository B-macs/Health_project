"""
services/home_snapshot.py — the durable record of what the Home page's three
cards last showed, so reopening the app repaints them instantly instead of
re-deriving them from Google Sheets.

Why this exists. app.py's card values are the tail end of ~6 Sheets tab
reads (biometric rolling blend, session AU, metrics history, wake
adjustments, session HR, current stage) before
dashboard.compute_daily_metrics_snapshot can run at all — roughly 18 seconds
on a cold start, paid on every single open. The numbers themselves barely
move: Oura uploads once overnight and the readiness/sleep pair is settled
for the rest of the day. Spending a full read pass to re-derive a number
that has not changed is the wrong trade, so the derived values are written
to local disk and served straight back on the next open.

Three rules keep that from silently freezing wrong data on screen.

1. **Entries are keyed by date, and today is gated on completeness.**
   A past date's numbers are final, so they are always serveable. TODAY's
   are serveable only once they are complete — readiness AND sleep both
   scored. That is exactly the failure this cache would otherwise create:
   the first open of the morning happens BEFORE app.py's startup sync has
   pulled the night into Sheets, so the live computation at that moment
   legitimately yields sleep_score=None. Caching that as the day's answer
   would pin "No Readings" on the Sleep card until midnight. Instead the
   incomplete entry is stored but never served, the background sync fills
   the gap, and the recompute that follows overwrites it with real numbers.

2. **The entry carries computed_at, and the page shows it.** This codebase
   treats "looks live while serving a snapshot" as the one failure never to
   produce silently — see app.py's offline-datastore banner and its
   _bio_rows_failed warning. A cached card is a snapshot, so it says so.

3. **Anything that can move a card drops the entry.** Logging a session
   changes strain; a check-in or a wake-time correction changes the sleep
   score. Those call sites already clear Streamlit's in-memory caches, and
   they now drop this durable one too (Repository.invalidate_home_snapshot)
   — a disk cache that outlives the process would otherwise survive exactly
   the events that invalidate it.

No I/O and no Streamlit here (CLAUDE.md rule 10): the store is a plain dict
that services/repository.py persists through clients/local_cache.py, the
same local JSON file the Oura sync-throttle marker already lives in.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

# Bumped whenever the entry shape changes. Entries written by an older
# version are ignored rather than migrated — they are at most a few days of
# re-derivable numbers, and a silent shape mismatch on a health metric is
# worth far less than the migration code would cost.
SCHEMA_VERSION = 1

# Entries older than this are pruned on every write. The Home page can browse
# back further than 14 days, and those older dates simply take the normal
# live path — this cache exists for the day you are actually living in, not
# as a general history store (that is the Metrics History tab's job).
KEEP_DAYS = 14


def build(snapshot: dict,
          sleep_need_hours: float | None,
          sleep_baseline_window: int | None,
          computed_at: datetime | None = None) -> dict:
    """One entry: the six values app.py's three cards render from, plus the
    provenance that makes serving them auditable.

    `snapshot` is a dashboard.compute_daily_metrics_snapshot result. Only
    the card-facing keys are kept — the drill-downs' inputs (hr_detail, the
    per-source strain breakdown) are deliberately not cached, because
    opening a drill-down is a deliberate click that can afford a live read,
    and caching them would double the entry size for a screen most visits
    never reach.
    """
    return {
        "schema": SCHEMA_VERSION,
        "computed_at": (computed_at or datetime.now()).isoformat(timespec="seconds"),
        "readiness_score": snapshot.get("readiness_score"),
        "sleep_score": snapshot.get("sleep_score"),
        "strain": snapshot.get("strain"),
        "strain_is_rolling": bool(snapshot.get("strain_is_rolling")),
        "sleep_need_hours": sleep_need_hours,
        "sleep_baseline_window": sleep_baseline_window,
    }


def is_complete(entry: dict | None) -> bool:
    """True when both device-derived cards actually scored.

    Strain is deliberately NOT required. It is None on any day with no
    logged session and no rolling history to stand in for one — a normal
    rest day, not a missing read — so requiring it would keep the cache
    permanently cold on exactly the days nothing is wrong.
    """
    if not entry:
        return False
    return (entry.get("readiness_score") is not None
            and entry.get("sleep_score") is not None)


def is_serveable(entry: dict | None, for_date: date, today: date) -> bool:
    """Whether `entry` may be painted instead of reading Sheets.

    Past dates: yes, unconditionally — their inputs cannot change any more,
    so an entry that was incomplete when written stays a faithful record of
    a night the ring genuinely did not capture.

    Today: only when complete, per rule 1 in the module docstring.

    Future dates: never. The Home page's next-day arrow is disabled past
    today, so this is defensive only — a hand-typed ?d= in the URL.
    """
    if not entry or entry.get("schema") != SCHEMA_VERSION:
        return False
    if for_date > today:
        return False
    if for_date < today:
        return True
    return is_complete(entry)


def get(store: dict, d: date) -> dict | None:
    entry = (store or {}).get(d.isoformat())
    return entry if isinstance(entry, dict) else None


def put(store: dict, d: date, entry: dict) -> dict:
    """Returns a NEW store with `d` set — never mutates the argument, so a
    caller that fails between building the store and writing it to disk
    leaves the on-disk copy untouched."""
    updated = dict(store or {})
    updated[d.isoformat()] = entry
    return updated


def drop(store: dict, d: date) -> dict:
    updated = dict(store or {})
    updated.pop(d.isoformat(), None)
    return updated


def prune(store: dict, today: date, keep_days: int = KEEP_DAYS) -> dict:
    """Drops entries older than `keep_days` before today, and anything whose
    key is not an ISO date (a hand-edited or corrupted file should shrink
    back to something valid rather than being served)."""
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    kept: dict = {}
    for key, entry in (store or {}).items():
        try:
            date.fromisoformat(key)
        except (TypeError, ValueError):
            continue
        if key >= cutoff and isinstance(entry, dict):
            kept[key] = entry
    return kept


def computed_at(entry: dict | None) -> datetime | None:
    """The entry's timestamp as a datetime, or None if absent/unparseable —
    app.py renders it as the "as of" caption under the cards."""
    if not entry:
        return None
    try:
        return datetime.fromisoformat(entry.get("computed_at", ""))
    except (TypeError, ValueError):
        return None
