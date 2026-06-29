"""
init_notion.py -- Notion Backend Setup and Verification.

Run once after creating your four Notion databases and setting credentials.
Verifies connectivity, checks all databases are accessible, and seeds
the diagnostic profile and default config values.

Usage:
    Set environment variables, then run:
        py init_notion.py

    Or set credentials in .streamlit/secrets.toml and run:
        py init_notion.py
"""

import json
import os
import sys

# Allow running from the project root
sys.path.insert(0, os.path.dirname(__file__))

from notion_client import Client
from notion_client.errors import APIResponseError

# ── Diagnostic profile seed data (from MRI 10.11.2025) ──────────────────────

DIAGNOSTIC_PROFILE = {
    "injury_focus": (
        "L5/S1: activated osteochondrosis with paradiscal bone edema and mild erosive changes; "
        "narrow retrolisthesis + broad-based disc protrusion right dorsolateral; "
        "moderate right foraminal stenosis, mild left. "
        "L4/5: flat disc protrusion left dorsolateral, covered annulus tear, retrolisthesis, mild foraminal stenosis. "
        "L3/4: flat disc protrusion left dorsolateral, covered annulus tear, mild foraminal stenosis. "
        "Downstream: chronic hip flexor/glute tightness (psoas, L1-L4 origin)."
    ),
    "historical_compensations": (
        "Mid-back muscle strain (fully resolved). "
        "Compensation pattern from lower back tightness. "
        "Psoas shortening amplifies L5/S1 foraminal compression."
    ),
    "mri_raw_text": (
        "MRI LWS mit Myelographie und knöch. Becken, 10.11.2025, DIE RADIOLOGIE München. "
        "LWK5/SWK1: Moderat ausgeprägte aktivierte Osteochondrose mit bandförmigem paradiscalem "
        "Knochenödem und geringen erosiven Veränderungen. Schmale breitbasige Retrospondylose und "
        "Bandscheibenprotrusion mit rechts dorsolateraler Betonung. Moderate Foramenstenose rechts, "
        "geringgradig links. LWK 3/4 + LWK 4/5: Flache Bandscheibenprotrusionen links dorsolateral "
        "mit gedecktem Riss im Anulus fibrosus. Geringgradige Foramenstenose. "
        "Kein Nachweis einer Myelonkompression. Rückenmuskulatur seitengleich ohne wesentliche Atrophie."
    ),
    "injury_weight_decay_lambda": 0.05,
}


def _secret(key: str) -> str:
    val = os.getenv(key)
    if val:
        return val
    raise EnvironmentError(
        f"'{key}' not set. Export it as an environment variable before running this script.\n"
        f"  Windows: $env:{key} = 'your-value-here'\n"
        f"  Mac/Linux: export {key}='your-value-here'"
    )


def _check_db(client: Client, db_id: str, label: str) -> bool:
    try:
        info = client.databases.retrieve(db_id)
        title = "".join(
            t.get("plain_text", "")
            for t in info.get("title", [])
        )
        print(f"  OK  {label}: '{title}' ({db_id[:8]}...)")
        return True
    except APIResponseError as exc:
        print(f"  FAIL  {label}: {exc.message} (ID: {db_id[:8]}...)")
        return False


def _seed_config(client: Client, config_db_id: str, key: str, value: str, label: str) -> None:
    """Create or update a config entry."""
    from datetime import date
    existing = client.databases.query(
        database_id=config_db_id,
        filter={"property": "Key", "title": {"equals": key}},
    )["results"]

    props = {
        "Key":     {"title":     [{"text": {"content": key}}]},
        "Value":   {"rich_text": [{"text": {"content": value[:2000]}}]},
        "Updated": {"date":      {"start": str(date.today())}},
    }

    if existing:
        client.pages.update(page_id=existing[0]["id"], properties=props)
        print(f"  UPDATED  {label}")
    else:
        client.pages.create(parent={"database_id": config_db_id}, properties=props)
        print(f"  CREATED  {label}")


def main():
    print("=" * 55)
    print("  Health Engine -- Notion Backend Setup")
    print("=" * 55)

    # ── Read credentials ──────────────────────────────────────────────────────
    try:
        api_key      = _secret("NOTION_API_KEY")
        db_readiness = _secret("NOTION_DB_READINESS")
        db_training  = _secret("NOTION_DB_TRAINING")
        db_biometrics= _secret("NOTION_DB_BIOMETRICS")
        db_config    = _secret("NOTION_DB_CONFIG")
    except EnvironmentError as exc:
        print(f"\nERROR: {exc}")
        sys.exit(1)

    client = Client(auth=api_key)

    # ── Verify API connection ─────────────────────────────────────────────────
    print("\n[1] Verifying Notion API connection...")
    try:
        client.users.me()
        print("  OK  Connected to Notion API.")
    except APIResponseError as exc:
        print(f"  FAIL  Cannot connect: {exc.message}")
        print("        Check your NOTION_API_KEY value.")
        sys.exit(1)

    # ── Verify all four databases ─────────────────────────────────────────────
    print("\n[2] Checking database access...")
    all_ok = True
    all_ok &= _check_db(client, db_readiness,  "Daily Readiness")
    all_ok &= _check_db(client, db_training,   "Training Log")
    all_ok &= _check_db(client, db_biometrics, "Daily Biometrics")
    all_ok &= _check_db(client, db_config,     "App Config")

    if not all_ok:
        print("\nERROR: One or more databases could not be accessed.")
        print("  - Make sure the integration is shared with each database.")
        print("  - In Notion: open the database → ··· → Connections → add your integration.")
        sys.exit(1)

    # ── Seed config values ────────────────────────────────────────────────────
    print("\n[3] Seeding App Config database...")
    _seed_config(
        client, db_config,
        "current_stage", "1",
        "current_stage = 1 (Rehab)",
    )
    _seed_config(
        client, db_config,
        "diagnostic_profile",
        json.dumps(DIAGNOSTIC_PROFILE),
        "diagnostic_profile (MRI 10.11.2025)",
    )

    print("\n" + "=" * 55)
    print("  Setup complete. All databases verified and seeded.")
    print("  Launch the app with:  streamlit run app.py")
    print("=" * 55)


if __name__ == "__main__":
    main()
