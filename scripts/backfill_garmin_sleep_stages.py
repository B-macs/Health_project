"""
scripts/backfill_garmin_sleep_stages.py -- historical Garmin sleep-stage capture.

The live sync captures sleepLevels for free (the payload was already being
fetched), but only for the rolling window. Anything older needs one
get_sleep_data call per night, against an unofficial API that rate-limits by
IP -- so this script is deliberately cautious.

PROBE FIRST. --probe samples ~10 dates spread across the requested range and
reports which have stage data. If the watch is newer than the ring, most
historical nights have nothing, and spending hundreds of calls to discover
that would deepen the very rate-limit that makes those calls expensive.

Deferring the backfill entirely is fine. Every night without Garmin stage data
simply fuses as source="oura_only", with the master hypnogram equal to Oura's
own -- see services/sleep_fusion.py::fuse.

Usage:
    python scripts/backfill_garmin_sleep_stages.py --probe
    python scripts/backfill_garmin_sleep_stages.py                  # dry run
    python scripts/backfill_garmin_sleep_stages.py --apply
    python scripts/backfill_garmin_sleep_stages.py --apply --limit 50 --sleep-seconds 3
    python scripts/backfill_garmin_sleep_stages.py --apply --range 2026-01-01:2026-07-31
    python scripts/backfill_garmin_sleep_stages.py --from-export --apply

Resumable: dates already in the Garmin Sleep Stages tab are skipped, so
re-running after a rate-limit picks up where it stopped. Raw payloads are
archived to Input_files/garmin_export/ (gitignored) so a
sleep_fusion.RULES_VERSION bump never needs to call Garmin again.

--from-export cashes that promise in. It rebuilds rows from the archived
payloads and makes ZERO Garmin calls — it does not even log in, so it cannot
be rate-limited and works while the circuit breaker is open. This is the
correct way to populate NEW COLUMNS over already-captured nights: adding the
movement and HR columns did not need a single API call for the 53 nights
already on disk. Use --refresh (with the live path) only for dates that have
no archived payload.

Reads credentials from .streamlit/secrets.toml or environment variables via
services.config.load_config -- nothing here imports streamlit.
"""

from __future__ import annotations

import json
import sys
import time
import tomllib
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.clients import garmin
from services.config import load_config
from services.repository import Repository

ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT / "Input_files" / "garmin_export"

# The ring's first day -- the widest range worth probing. The watch may well
# start much later; that is exactly what --probe is for.
DEFAULT_START = "2023-07-04"
PROBE_SAMPLES = 10
DEFAULT_LIMIT = 50
DEFAULT_SLEEP_SECONDS = 3.0


def _load_repo() -> Repository:
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    overrides = {}
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            overrides = tomllib.load(f)
    return Repository(load_config(overrides))


def _arg(argv: list[str], name: str, default):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def _parse_range(argv: list[str]) -> tuple[date, date]:
    raw = _arg(argv, "--range", None)
    if raw:
        start, _, end = raw.partition(":")
        if not start or not end:
            raise SystemExit(f"--range needs START:END (got {raw!r})")
        return date.fromisoformat(start.strip()), date.fromisoformat(end.strip())
    return date.fromisoformat(DEFAULT_START), date.today()


def _has_stages(payload: dict) -> bool:
    return bool((payload or {}).get("sleepLevels"))


def _probe(repo: Repository, client, start: date, end: date) -> None:
    span = (end - start).days
    step = max(1, span // (PROBE_SAMPLES - 1)) if span else 1
    samples = [start + timedelta(days=i * step) for i in range(PROBE_SAMPLES)]
    samples = [d for d in samples if d <= end]

    print(f"Probing {len(samples)} dates across {start} .. {end} "
          f"({span} days), 1 API call each.\n")
    found = 0
    for d in samples:
        try:
            payload = garmin.get_sleep_data(client, d)
        except garmin.RateLimited as exc:
            print(f"  {d}  RATE LIMITED -- stopping probe. ({exc})")
            break
        segments = (payload or {}).get("sleepLevels") or []
        dto = (payload or {}).get("dailySleepDTO") or {}
        secs = dto.get("sleepTimeSeconds")
        if segments:
            found += 1
        print(f"  {d}  segments={len(segments):3d}  sleepTimeSeconds={secs}")
        time.sleep(1.0)

    print(f"\n{found}/{len(samples)} probed dates have sleepLevels data.")
    if found == 0:
        print("No historical stage data at all -- a backfill would buy nothing. "
              "Fusion will report oura_only for these nights, which is correct.")
    else:
        print("Re-run with --apply (add --range to narrow to where data actually starts).")


def _row_flags(row: dict) -> str:
    """Surface the two stored self-checks. Both are diagnostics rather than
    hard failures, so they have to be VISIBLE here or they are worthless."""
    flags = []
    if not row["totals_match"]:
        flags.append("totals_match FALSE")
    if not row.get("movement_contiguous", True):
        flags.append(f"movement gaps={row.get('movement_gap_slots')}")
    return "  [!] " + ", ".join(flags) if flags else ""


def _from_export(repo, start: date, end: date, apply: bool) -> None:
    """Rebuild rows from archived payloads. No Garmin client, no login, no
    rate limit — see the module docstring for why this is the right tool for
    a schema change rather than re-fetching nights already on disk."""
    files = sorted(EXPORT_DIR.glob("sleep_*.json"))
    dated = []
    for f in files:
        try:
            d = date.fromisoformat(f.stem.replace("sleep_", ""))
        except ValueError:
            continue
        if start <= d <= end:
            dated.append((d, f))

    print(f"Archived payloads in {start} .. {end}: {len(dated)} "
          f"(of {len(files)} on disk). Zero Garmin calls.")
    if not dated:
        print("\nNothing to rebuild. Capture nights live first (--apply).")
        return
    if not apply:
        print("\nDry run only -- nothing written. Re-run with --apply.")
        return

    fresh: dict[str, dict] = {}
    failed = 0
    for d, f in dated:
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
            row = repo._garmin_sleep_stages_row({"sleep": payload}, d)
        except Exception as exc:                      # one bad file must not
            failed += 1                               # abort the whole rebuild
            print(f"  {d}  FAILED: {exc}")
            continue
        fresh[str(d)] = row
        print(f"  {d}  segments={row['segment_count']:3d}  "
              f"movement_slots={row['movement_slot_count']:4d}"
              f"{_row_flags(row)}")

    # One batched rewrite, not 53 upserts: upsert cannot widen the header, and
    # at two API calls each it would walk into Sheets' write quota.
    total = repo.rebuild_garmin_sleep_stages(fresh)
    print(f"\nRebuilt {len(fresh)} night(s)" + (f", {failed} failed" if failed else "")
          + f"; tab now holds {total} row(s).")
    print("Then rebuild fused hypnograms: repo.sync_sleep_fusion(days=1000)")


def main() -> None:
    argv = sys.argv[1:]
    probe = "--probe" in argv
    apply = "--apply" in argv
    from_export = "--from-export" in argv
    refresh = "--refresh" in argv
    limit = int(_arg(argv, "--limit", DEFAULT_LIMIT))
    pause = float(_arg(argv, "--sleep-seconds", DEFAULT_SLEEP_SECONDS))
    start, end = _parse_range(argv)

    repo = _load_repo()

    # Deliberately BEFORE the Garmin checks: rebuilding from disk needs
    # Sheets and nothing else, and must stay usable while Garmin is
    # unreachable or the circuit breaker is open.
    if from_export:
        _from_export(repo, start, end, apply)
        return

    if not repo.garmin_configured():
        raise SystemExit("Garmin is not configured -- add GARMIN_EMAIL/GARMIN_PASSWORD "
                         "to .streamlit/secrets.toml.")
    client = repo._gc
    if client is None:
        raise SystemExit("Garmin login unavailable.")

    if probe:
        _probe(repo, client, start, end)
        return

    have = repo.get_garmin_sleep_stages_dates()
    archived = {f.stem.replace("sleep_", "") for f in EXPORT_DIR.glob("sleep_*.json")}
    wanted = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if refresh:
        # Re-fetch everything EXCEPT what is already archived — those nights
        # can be rebuilt for free with --from-export, so spending a rate-
        # limited call on them would be pure waste.
        todo = [d for d in wanted if str(d) not in archived]
    else:
        todo = [d for d in wanted if str(d) not in have]
    todo.sort(reverse=True)          # newest first -- most useful data soonest

    print(f"Range {start} .. {end}: {len(wanted)} nights, "
          f"{len(have)} already captured, {len(archived)} archived on disk, "
          f"{len(todo)} outstanding.")
    if refresh and archived:
        print(f"--refresh: skipping the {len(archived)} archived night(s); "
              f"rebuild those with --from-export --apply (zero calls).")
    batch = todo[:limit]
    print(f"This run would fetch {len(batch)} night(s) at {pause}s apart "
          f"(~{len(batch) * pause / 60:.1f} min).")

    if not batch:
        print("\nNothing to do.")
        return
    if not apply:
        print("\nDry run only -- no calls made, nothing written. "
              "Re-run with --apply, or --probe first if unsure the data exists.")
        return

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    for i, d in enumerate(batch):
        try:
            payload = garmin.get_sleep_data(client, d)
        except garmin.RateLimited as exc:
            print(f"\nRATE LIMITED after {written} night(s). ({exc})")
            print(f"Resume with: python scripts/backfill_garmin_sleep_stages.py --apply "
                  f"--range {start}:{end} --limit {limit}")
            raise SystemExit(1)

        if not _has_stages(payload):
            skipped += 1
            print(f"  {d}  no stage data -- skipped")
        else:
            (EXPORT_DIR / f"sleep_{d}.json").write_text(json.dumps(payload), encoding="utf-8")
            row = repo._garmin_sleep_stages_row({"sleep": payload}, d)
            repo.upsert_garmin_sleep_stages_row(row)
            written += 1
            print(f"  {d}  segments={row['segment_count']:3d}  "
                  f"deep/light/rem/awake="
                  f"{row['deep_seconds']}/{row['light_seconds']}/"
                  f"{row['rem_seconds']}/{row['awake_seconds']}s"
                  f"  movement_slots={row['movement_slot_count']}"
                  f"{_row_flags(row)}")
        if i < len(batch) - 1:
            time.sleep(pause)

    print(f"\nWrote {written} night(s), skipped {skipped} with no stage data.")
    remaining = len(todo) - len(batch)
    if remaining > 0:
        print(f"{remaining} night(s) still outstanding -- re-run to continue.")
    print("Then rebuild fused hypnograms: repo.sync_sleep_fusion(days=1000)")


if __name__ == "__main__":
    main()
