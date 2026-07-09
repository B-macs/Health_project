"""
scripts/garmin_login_test.py -- Standalone Garmin Connect login diagnostic.

Run this from your own terminal, on your own network -- NOT from a shared/
cloud sandbox. Garmin's anti-bot layer (Cloudflare) is known to block
datacenter/cloud IPs much more aggressively than home ISPs, and the
"Portal login failed (non-JSON): HTTP 403" error the Sync page showed is
exactly the kind of failure that produces (see garminconnect's own
client.py docstring -- it tries 5 fallback strategies before giving up,
and a 403 that survives all 5 usually means the network path is being
blocked, not that the credentials are wrong).

Nothing here touches .streamlit/secrets.toml. Your email is read from it
for convenience if present; your password is always typed fresh via a
hidden getpass() prompt, never read from disk, and never printed or logged.

Usage:
    python scripts/garmin_login_test.py

If your account has MFA/2FA enabled, you'll be prompted for the code from
your email/authenticator app -- the login will otherwise fail immediately.

On success, this also prints the raw JSON from get_stats/get_sleep_data/
get_stress_data/get_activities, so we can check the app's field mapping
(services/repository.py's _garmin_daily_row/_garmin_activity_row) against
real data instead of assumptions.
"""

import getpass
import json
import logging
import sys
from datetime import date
from pathlib import Path

try:
    import garminconnect
except ImportError:
    print("garminconnect isn't installed in this environment.")
    print("Run: pip install garminconnect")
    sys.exit(1)

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")


def _email_from_secrets() -> str | None:
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return None
    try:
        import tomllib
        with open(secrets_path, "rb") as f:
            return tomllib.load(f).get("GARMIN_EMAIL")
    except Exception:
        return None


def _prompt_mfa() -> str:
    return input("\nMFA required -- enter the code from your email/authenticator app: ").strip()


def _print_json(label: str, data) -> None:
    print(f"\n--- {label} ---")
    try:
        print(json.dumps(data, indent=2, default=str)[:3000])
    except Exception as exc:
        print(f"(couldn't serialize: {exc})")


def main() -> None:
    default_email = _email_from_secrets()
    prompt = f"Garmin email [{default_email}]: " if default_email else "Garmin email: "
    email = input(prompt).strip() or default_email
    if not email:
        print("No email provided. Exiting.")
        sys.exit(1)

    password = getpass.getpass("Garmin password (hidden, not stored): ")

    print(f"\nLogging in as {email} ...")
    print("(watch the DEBUG lines below -- they show which of the 5 fallback")
    print(" login strategies succeeded or failed, and why)\n")

    client = garminconnect.Garmin(email, password, prompt_mfa=_prompt_mfa)
    try:
        client.login()
    except Exception as exc:
        print(f"\nLOGIN FAILED: {type(exc).__name__}: {exc}")
        print(
            "\nIf this says 'All login strategies exhausted' or mentions 403/"
            "Cloudflare: that's a network-level block, not necessarily bad "
            "credentials -- try a different network (mobile hotspot, etc.) "
            "if this also fails from your home connection.\n"
            "If it says 'Invalid Username or Password' from a SPECIFIC "
            "strategy (not after exhausting all 5): the credentials "
            "themselves are the problem.\n"
            "If it mentions MFA and you weren't prompted for a code: 2FA is "
            "on and something about the prompt failed -- check your email/"
            "authenticator app arrived in time."
        )
        sys.exit(1)

    print("\nLogin succeeded.\n")

    today = date.today().isoformat()
    stats = client.get_stats(today)
    sleep = client.get_sleep_data(today)
    stress = client.get_stress_data(today)
    activities = client.get_activities(0, 10)

    _print_json(f"get_stats({today})", stats)

    # Sleep score: confirmed dailySleepDTO doesn't nest "sleepScores" on at
    # least one account/day. Print exactly where (if anywhere) a score
    # exists instead of a truncated full-payload dump.
    dto = sleep.get("dailySleepDTO") or {}
    print("\n--- sleep score investigation ---")
    print("top-level sleep keys:", list(sleep.keys()))
    print("dailySleepDTO keys:  ", list(dto.keys()))
    print("dailySleepDTO.sleepScores:", dto.get("sleepScores"))
    print("sleep.sleepScores (sibling):", sleep.get("sleepScores"))
    print("sleep.overallSleepScore:", sleep.get("overallSleepScore"))

    _print_json(f"get_stress_data({today})", stress)

    # Activities: a bare "Stopwatch"/timer entry often lacks distance/HR/
    # calories, so it doesn't tell us much about a real run/walk. Show the
    # type of everything returned, then the full fields of the first one
    # that looks like an actual tracked activity.
    print("\n--- activities ---")
    for act in activities:
        print(f"  {act.get('activityId')}: {act.get('activityName')!r} "
              f"({(act.get('activityType') or {}).get('typeKey')})")
    real_activity = next(
        (a for a in activities
         if (a.get("activityType") or {}).get("typeKey") not in (None, "stop_watch", "uncategorized")),
        None,
    )
    if real_activity:
        print(f"\n--- full fields for first tracked activity ({real_activity.get('activityName')!r}) ---")
        for key in ("activityId", "activityName", "activityType", "startTimeLocal",
                    "duration", "distance", "averageHR", "maxHR", "calories"):
            print(f"  {key}: {real_activity.get(key)!r}")
    else:
        print("\n(No non-stopwatch tracked activity in the most recent 10 -- "
              "can't confirm distance/averageHR/maxHR/calories field names yet.)")

    print(
        "\nDone. If you're happy the field names above line up with what "
        "services/repository.py expects (steps/resting_hr/avg_stress/"
        "sleep_score/sleep_hours/calories_total/min_hr/max_hr, and the "
        "activity fields), the Sync page should work the same way from "
        "this network. If any of it looks wrong/missing, paste the output "
        "back and I'll fix the mapping."
    )


if __name__ == "__main__":
    main()
