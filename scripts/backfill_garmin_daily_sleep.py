"""
scripts/backfill_garmin_daily_sleep.py -- historical Garmin sleep DURATION.

Why this exists alongside backfill_garmin_sleep_stages.py. Probing 2026-08-05
over 2024-10-31..2026-05-18 found `sleepLevels` on 0 of 10 sampled dates but
`sleepTimeSeconds` on 6 of 10, reaching back to 2024-10-31. Garmin keeps the
DAILY TOTAL for years and discards the per-minute hypnogram, so:

  * a STAGE backfill buys nothing and is permanently impossible -- the 53
    nights already archived are all there will ever be;
  * a DURATION backfill is available, and is the only way to give the
    readiness baselines a Garmin history rather than starting them empty.

ONE API CALL PER NIGHT. sync_garmin_daily spends four (summary + sleep +
stress + hrv), which over this span would be ~2,200 calls against an endpoint
that rate-limits by IP and has already returned 429s for this account. This
script fetches the sleep payload only.

ARCHIVE FIRST, WRITE SECOND. --apply fetches and archives raw payloads to
Input_files/garmin_export/sleep_<date>.json -- the same convention
backfill_garmin_sleep_stages.py uses, so a night captured by either script is
never re-fetched by the other. --to-sheets then writes into the Garmin Daily
tab from the archive alone, with ZERO Garmin calls, so a rate-limit interrupts
the fetch without ever leaving the sheet half-written.

    python scripts/backfill_garmin_daily_sleep.py                       # dry run
    python scripts/backfill_garmin_daily_sleep.py --apply --limit 60
    python scripts/backfill_garmin_daily_sleep.py --apply --range 2025-01-01:2025-06-30
    python scripts/backfill_garmin_daily_sleep.py --to-sheets           # dry run
    python scripts/backfill_garmin_daily_sleep.py --to-sheets --apply   # zero API calls

Resumable: dates already archived are skipped, so re-running after a 429
picks up where it stopped. Run --apply in chunks and watch for RATE LIMITED.

TRUST THE TOTALS ONLY AS FAR AS sleepWindowConfirmationType. Garmin infers a
sleep window when the watch was not clearly worn, and an unconfirmed window is
Garmin guessing rather than measuring. Both are archived and the counts are
reported; --to-sheets writes UNCONFIRMED nights as blank rather than as a
number, because a guess that reads like a measurement is worse than a gap.
That is the same principle as biometrics.blend_hrv returning None rather than
a silently rescaled wrist value.
"""

from __future__ import annotations

import json
import sys
import time
import tomllib
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.clients import garmin                  # noqa: E402
from services.config import load_config              # noqa: E402
from services.repository import Repository           # noqa: E402
from services.repository import _GARMIN_DAILY_HEADER # noqa: E402

EXPORT_DIR = ROOT / "Input_files" / "garmin_export"
DEFAULT_LIMIT = 60
DEFAULT_SLEEP_SECONDS = 2.0
# The Sleep Cycle export's own span -- the window where a Garmin duration
# actually buys a comparison. Narrow with --range.
DEFAULT_START = date(2024, 10, 31)
DEFAULT_END = date(2026, 5, 18)

# Garmin returns these lower-cased in practice ("enhanced_confirmed"), so every
# comparison against this set is case-folded. Getting that wrong silently
# classifies every good night as a guess and writes nothing.
CONFIRMED_OK = {"enhanced_confirmed", "enhanced_confirmed_final",
                "manual_confirmed", "confirmed"}


def _is_confirmed(conf: str) -> bool:
    return conf.strip().lower() in CONFIRMED_OK


def _arg(argv: list[str], name: str, default):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def _parse_range(argv: list[str]) -> tuple[date, date]:
    raw = _arg(argv, "--range", None)
    if not raw:
        return DEFAULT_START, DEFAULT_END
    try:
        a, b = raw.split(":")
        return date.fromisoformat(a), date.fromisoformat(b)
    except ValueError:
        raise SystemExit(f"--range needs START:END (got {raw!r})")


def _sleep_from_payload(payload: dict) -> tuple[float | None, str]:
    """(hours, confirmation) from an archived get_sleep_data payload."""
    dto = (payload or {}).get("dailySleepDTO") or {}
    secs = dto.get("sleepTimeSeconds")
    conf = str(dto.get("sleepWindowConfirmationType") or "")
    hours = round(secs / 3600, 6) if isinstance(secs, (int, float)) and secs else None
    return hours, conf


def _archived_dates() -> set[str]:
    return {f.stem.replace("sleep_", "") for f in EXPORT_DIR.glob("sleep_*.json")}


def _fetch(repo: Repository, start: date, end: date, limit: int,
           pause: float, apply: bool) -> None:
    have = _archived_dates()
    wanted = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    todo = [d for d in wanted if str(d) not in have]

    print(f"Span {start} .. {end}  =  {len(wanted)} nights")
    print(f"Already archived: {len(wanted) - len(todo)}   to fetch: {len(todo)}"
          f"   this run (--limit): {min(limit, len(todo))}")
    print(f"One API call per night, {pause}s apart "
          f"(~{min(limit, len(todo)) * pause / 60:.1f} min).")
    if not todo:
        print("\nNothing to fetch. Run --to-sheets to write what is on disk.")
        return
    if not apply:
        print("\nDry run only -- nothing fetched. Re-run with --apply.")
        return

    client = repo._gc
    if client is None:
        raise SystemExit("Garmin is not configured -- add GARMIN_EMAIL/"
                         "GARMIN_PASSWORD to .streamlit/secrets.toml.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    got = miss = unconf = 0
    for d in todo[:limit]:
        try:
            payload = garmin.get_sleep_data(client, d)
        except garmin.RateLimited as exc:
            print(f"  {d}  RATE LIMITED -- stopping. Re-run to resume. ({exc})")
            break
        except Exception as exc:
            print(f"  {d}  FAILED: {exc}")
            time.sleep(pause)
            continue
        # Archive even an empty payload: it is the durable record that this
        # night was asked about and Garmin had nothing, which is what makes
        # the resume skip correct rather than a permanent re-fetch loop.
        (EXPORT_DIR / f"sleep_{d}.json").write_text(
            json.dumps(payload or {}), encoding="utf-8")
        hours, conf = _sleep_from_payload(payload)
        if hours is None:
            miss += 1
        else:
            got += 1
            if conf and not _is_confirmed(conf):
                unconf += 1
        print(f"  {d}  {'—' if hours is None else f'{hours:5.2f}h'}"
              f"   {conf or '(no confirmation field)'}")
        time.sleep(pause)

    print(f"\nArchived: {got} with a duration, {miss} with none"
          f"{f', of which {unconf} UNCONFIRMED windows' if unconf else ''}.")
    remaining = len([d for d in wanted if str(d) not in _archived_dates()])
    print(f"Remaining in span: {remaining}."
          + ("  Re-run --apply to continue." if remaining else
             "  Span complete — run --to-sheets --apply."))


def _to_sheets(repo: Repository, start: date, end: date, apply: bool) -> None:
    """Zero Garmin calls. Reads the archive, writes sleep_hours into Garmin
    Daily, and carries every existing row and column through untouched."""
    rows: dict[str, dict] = {}
    unconf = blank = 0
    for f in sorted(EXPORT_DIR.glob("sleep_*.json")):
        try:
            d = date.fromisoformat(f.stem.replace("sleep_", ""))
        except ValueError:
            continue
        if not (start <= d <= end):
            continue
        try:
            hours, conf = _sleep_from_payload(json.loads(f.read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"  {d}  UNREADABLE: {exc}")
            continue
        if hours is None:
            blank += 1
            continue
        if conf and not _is_confirmed(conf):
            unconf += 1
            continue
        rows[str(d)] = hours

    print(f"Archived payloads in {start} .. {end} with a CONFIRMED duration: "
          f"{len(rows)}   (skipped {unconf} unconfirmed, {blank} with no duration)")
    if not rows:
        print("\nNothing to write. Fetch first with --apply.")
        return

    existing = {
        str(r.get("date")): dict(r)
        for r in repo._read_records(repo._garmin_daily_ws())
        if str(r.get("date") or "").strip()
    }
    fresh: dict[str, dict] = {}
    overwritten = 0
    for d, hours in rows.items():
        # rebuild_tab REPLACES a row wholesale, so carry the existing one
        # forward and set one field rather than blanking steps/HR/stress.
        row = dict(existing.get(d) or {})
        if str(row.get("sleep_hours", "")).strip() != "":
            continue                      # never overwrite a real synced value
        row["date"] = d
        row["sleep_hours"] = hours
        fresh[d] = {k: row.get(k, "") for k in _GARMIN_DAILY_HEADER}
        if d in existing:
            overwritten += 1

    print(f"New date rows: {len(fresh) - overwritten}   "
          f"existing rows gaining sleep_hours: {overwritten}   "
          f"left alone (already populated): {len(rows) - len(fresh)}")
    if not apply:
        print("\nDry run only -- nothing written. Re-run with --to-sheets --apply.")
        return
    total = repo.rebuild_garmin_daily(fresh)
    print(f"\nGarmin Daily now holds {total} row(s).")
    print("Rebuild the local snapshot with: python scripts/build_datastore.py")


def main() -> None:
    argv = sys.argv[1:]
    apply = "--apply" in argv
    start, end = _parse_range(argv)
    limit = int(_arg(argv, "--limit", DEFAULT_LIMIT))
    pause = float(_arg(argv, "--sleep-seconds", DEFAULT_SLEEP_SECONDS))

    with open(ROOT / ".streamlit" / "secrets.toml", "rb") as fh:
        secrets = tomllib.load(fh)
    repo = Repository(load_config(secrets))

    if "--to-sheets" in argv:
        _to_sheets(repo, start, end, apply)
    else:
        _fetch(repo, start, end, limit, pause, apply)


if __name__ == "__main__":
    main()
