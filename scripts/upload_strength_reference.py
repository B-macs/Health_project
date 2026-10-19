"""scripts/upload_strength_reference.py — the Strength screen's personal
reference into the store, for the engine (rebuild Phase 2, milestone 5).

The engine computes the Strength screen (GET /api/insights/strength) against
the 2025 peaks that "100" means and the profile's muscle imbalances. Those
are personal records: strength_baselines.py and patient_profile.py stay out
of the engine's image (rebuild rule 7), so the engine reads them from one
config row of the store instead (services/insights_screens.REFERENCE_KEY).
This script builds that row from the two local files and writes it.

Dry run by default: it prints what it would write as counts only, never a
value. --apply writes the row through the Repository (Supabase first, rule 5)
and reads it back.

    python scripts/upload_strength_reference.py            # dry run
    python scripts/upload_strength_reference.py --apply    # write the row

Run it again after either file changes. The Streamlit app does not read the
row; it keeps reading the two files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def build_reference() -> dict:
    """The reference as services/strength_screen.read_data takes it."""
    import patient_profile
    import strength_baselines as sb
    return {
        "peaks": sb.PEAKS_2025, "region_prior": sb.REGION_PRIOR, "pr_rir": sb.PR_RIR,
        "anchor_date": sb.ANCHOR_DATE, "anchor_value": sb.ANCHOR_VALUE,
        "hold_baselines": sb.HOLD_BASELINES_2025,
        "imbalances": patient_profile.PROFILE.get("imbalances", {}),
    }


def summary(reference: dict) -> str:
    """Counts only: what the row holds, never a value."""
    return (f"{len(reference['peaks'])} peaks, {len(reference['hold_baselines'])} hold "
            f"baselines, {len(reference['region_prior'])} region priors, "
            f"{sum(len(v) for v in reference['imbalances'].values() if isinstance(v, list))} "
            f"imbalance entries")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the row (default: dry run)")
    args = parser.parse_args(argv)

    from services import insights_screens as ins
    reference = build_reference()
    payload = ins.reference_json(reference)
    print(f"Reference: {summary(reference)}; {len(payload)} characters as JSON.")
    if not args.apply:
        print("Dry run: nothing written. Run with --apply to write the row.")
        return 0

    from services.config import load_config
    from services.repository import Repository
    import tomllib
    secrets = ROOT / ".streamlit" / "secrets.toml"
    overrides = tomllib.loads(secrets.read_text(encoding="utf-8")) if secrets.exists() else {}
    repo = Repository(load_config(overrides))
    repo.set_config(ins.REFERENCE_KEY, payload)
    back = ins.reference_from_store(repo)
    if back is None or len(back["peaks"]) != len(reference["peaks"]):
        print("Written, but the read-back does not match: check the config row.")
        return 1
    print(f"Written and read back: {ins.REFERENCE_KEY}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
