"""Find and store the heart-rate match of past plan sessions that have none.

The athlete, 2026-11-11: "review previous sessions when I said I had the Garmin
watch cardio tracking but we dont have the connection in the app. Find those
connections in the Garmin server and download them".

Two faults kept those sessions without a match. The match searched Garmin's 20
newest activities, so a session older than about two weeks could never be
found (the 35-day catch-up asked and found nothing); and the phone's match
after a save was shown, never stored. Both are fixed (2026-11-11). This finds
every logged plan session in [--from, --to] with no Session HR row, asks Garmin
for that day's activities (Repository.match_session_hr_for_date), and prints
what each one matches: the activity, the minutes it covers, the heart rate. A
day with no match lists the day's Garmin activities, so it says whether the
watch recorded anything.

Nothing is written without --apply. With it: an off-site copy of every table
first (Input_files/backups/), then each match stored the way the sync stores
one (Repository.store_session_hr: the day's row, then each exercise's own
effort), then read back from Supabase. A day the watch cannot place (the
travel case: activities on the day, none lining up with the session's clock)
is listed and never stored; the athlete picks the activity, not this script.

`--shift DATE=HOURS` matches one day with its set times moved: the first
sessions with per-set times (early August 2026) were stamped by the hosted
server's clock in UTC with no time zone, so they read 2 hours early against
the watch (Berlin summer time). 2026-08-06 lines up exactly at +2 h.

    python scripts/backfill_session_hr.py --from 2026-08-01 --to 2026-11-11
    python scripts/backfill_session_hr.py --from 2026-08-01 --to 2026-11-11 --shift 2026-08-06=2 --apply
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
import tomllib
from datetime import date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from services import backup, record_cache, supabase_store, switchover  # noqa: E402
from services.config import load_config  # noqa: E402
from services.repository import Repository  # noqa: E402

#: The wait between two days, so Garmin's unofficial API is not asked in a burst.
PAUSE_SECONDS = 2.0


def _config(secrets: Path):
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    # A copy of the store rebuilt for this run only, never the checkout's datastore.db.
    copy = Path(tempfile.mkdtemp(prefix="session_hr_")) / "record.db"
    return load_config({**overrides, "HEALTH_SYSTEM_OF_RECORD": "supabase",
                        "HEALTH_DATASTORE_MODE": "cache", "HEALTH_DATASTORE_PATH": str(copy)})


def missing_dates(repo: Repository, start: date, end: date) -> list[date]:
    """Logged plan sessions in [start, end] with no Session HR row, oldest first
    (session_hr_catch_up_dates' rule over any range)."""
    logged = repo.get_logged_session_dates(start, end, include_supplementary=False)
    have = {row["date"] for row in repo.get_session_hr_history(start=start.isoformat())}
    return sorted(date.fromisoformat(d) for d in logged if d not in have)


def parse_shift(text: str) -> tuple[date, float]:
    """'2026-08-06=2' -> (2026-08-06, 2.0): a day and the hours its set times move."""
    day, _, hours = text.partition("=")
    return date.fromisoformat(day.strip()), float(hours)


def _num(v, fmt="{:.0f}"):
    try:
        return fmt.format(float(v))
    except (TypeError, ValueError):
        return "?"


def describe_match(summary: dict) -> str:
    covered, total = summary.get("hr_covered_exercises"), summary.get("hr_total_exercises")
    return (f"MATCH  {summary.get('activity_name') or summary.get('activity_type') or 'activity'} "
            f"({summary.get('activity_type') or '?'}), started {str(summary.get('start_time_local') or '?')[11:16]}, "
            f"{_num(summary.get('duration_minutes'))} min; covers {_num(summary.get('overlap_minutes'))} min "
            f"of the session; average {_num(summary.get('avg_hr'))}, top {_num(summary.get('max_hr'))} bpm; "
            f"{covered if covered is not None else '?'} of {total if total is not None else '?'} exercises "
            f"with heart rate ({_num((summary.get('hr_coverage') or 0) * 100)}% of the time)")


def describe_activities(rows: list[dict]) -> str:
    if not rows:
        return "Garmin has no activity on this day"
    return "Garmin's activities that day: " + "; ".join(
        f"{str(r.get('start_time_local') or '?')[11:16]} {r.get('name') or r.get('type') or '?'} "
        f"({_num(r.get('duration_minutes'))} min)" for r in rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True, type=date.fromisoformat)
    ap.add_argument("--to", dest="end", default=date.today(), type=date.fromisoformat)
    ap.add_argument("--secrets", type=Path, default=_ROOT / ".streamlit" / "secrets.toml")
    ap.add_argument("--shift", action="append", default=[], type=parse_shift, metavar="DATE=HOURS",
                    help="match this day with its set times moved by HOURS (set times with no time zone)")
    ap.add_argument("--apply", action="store_true", help="back up, then store each match")
    args = ap.parse_args()
    shifts = dict(args.shift)

    cfg = _config(args.secrets)
    store = supabase_store.SupabaseStore(cfg.supabase_url, cfg.supabase_secret_key)
    since = record_cache.record_since(store)
    caught_up = store.select_value("config", f"key=eq.{switchover.CATCH_UP_KEY}", "value")
    if not since or not caught_up:
        print("Refused: the Supabase switch has not finished; nothing read or written.")
        return 2
    repo = Repository(cfg)
    if not repo.garmin_configured():
        print("Refused: Garmin is not configured in these secrets.")
        return 2

    days = missing_dates(repo, args.start, args.end)
    print(f"{len(days)} plan sessions from {args.start} to {args.end} have no heart-rate row.")
    found: dict[date, dict] = {}
    for i, d in enumerate(days):
        if i:
            time.sleep(PAUSE_SECONDS)
        try:
            summary = repo.match_session_hr_for_date(d, shift_hours=shifts.get(d, 0.0))
        except Exception as exc:          # one day's failure never stops the others
            print(f"{d}  FAILED  {type(exc).__name__}: {str(exc)[:120]}")
            continue
        if summary and not summary.get("needs_choice"):
            found[d] = summary
            moved = f" (set times moved {shifts[d]:+g} h)" if d in shifts else ""
            print(f"{d}  {describe_match(summary)}{moved}")
            continue
        try:
            listing = describe_activities(repo.get_garmin_activities_for_date(d))
        except Exception as exc:
            listing = f"Garmin's list could not be read ({type(exc).__name__})"
        if summary and summary.get("needs_choice"):
            print(f"{d}  ASKS WHICH  {summary.get('reason') or ''}; {listing}")
        else:
            print(f"{d}  NO MATCH  {listing}")
    print(f"{len(found)} of {len(days)} sessions match a Garmin activity.")

    if not args.apply:
        print("Dry run: nothing written. Run with --apply to store the matches.")
        return 0
    if not found:
        print("Nothing to store.")
        return 0
    out = _ROOT / "Input_files" / "backups"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"health-{date.today().isoformat()}-before-session-hr-{datetime.now():%H%M%S}.db.gz"
    path.write_bytes(backup.snapshot(store))
    print(f"Backup: {path} ({path.stat().st_size / 1e6:.1f} MB)")
    for d, summary in found.items():
        repo.store_session_hr(d, summary)
    fresh = {str(r["date"]): r for r in store.select_all("session_hr")}
    stored = [d for d in found if d.isoformat() in fresh
              and str(fresh[d.isoformat()].get("activity_id")) == str(found[d].get("activity_id"))]
    print(f"Read back from Supabase: {len(stored)} of {len(found)} matches stored.")
    return 0 if len(stored) == len(found) else 1


if __name__ == "__main__":
    sys.exit(main())
