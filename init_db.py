"""
Bucket 2 — Database Initialization & Migration
Run once to create health_engine.db and seed the diagnostic baseline.
Safe to re-run: schema uses IF NOT EXISTS; seed only fires on a fresh database;
migration adds any missing columns to existing tables without data loss.
"""

import json
import os
import sqlite3

DB_PATH = "health_engine.db"
SCHEMA_PATH = "schema.sql"

# ── Seed data from MRI report (DIE RADIOLOGIE München, 10.11.2025) ────────────

INJURY_FOCUS = (
    "L5/S1: activated osteochondrosis with paradiscal bone edema and mild erosive changes; "
    "narrow retrolisthesis + broad-based disc protrusion right dorsolateral; "
    "moderate right foraminal stenosis, mild left. "
    "L4/5: flat disc protrusion left dorsolateral, covered annulus tear, retrolisthesis, mild foraminal stenosis. "
    "L3/4: flat disc protrusion left dorsolateral, covered annulus tear, mild foraminal stenosis. "
    "Cleared: spinal canal (myelography clear), facet joints, ISG, back musculature (no atrophy). "
    "Downstream: chronic hip flexor/glute tightness — psoas (L1-L4 origin) amplifies L5/S1 foraminal compression."
)

HISTORICAL_COMPENSATIONS = (
    "Mid-back muscle strain (fully resolved). "
    "Was a compensation pattern driven by lower back tightness — no structural residual. "
    "Psoas shortening from prolonged sitting is the primary ongoing compensation mechanism, "
    "pulling lumbar spine into extension and compressing stenotic foramina at L5/S1."
)

MRI_RAW_TEXT = (
    "Magnetresonanztomographie der LWS mit Myelographie und knöch. Becken, 10.11.2025, "
    "DIE RADIOLOGIE MVZ Schwabing, München. Arzt: Dr. med. Michael Röttinger, FA für Radiologie/Neuroradiologie. "
    "LWK5/SWK1: Moderat ausgeprägte aktivierte Osteochondrose mit bandförmigem paradiscalem Knochenödem "
    "und geringen erosiven Veränderungen. Schmale breitbasige Retrospondylose und Bandscheibenprotrusion "
    "mit rechts dorsolateraler Betonung. Dadurch moderate Foramenstenose rechts, geringgradig links. "
    "LWK 3/4: Geringgradige reizlose Chondrose. Flache breitbasige Bandscheibenprotrusion links dorsolateral "
    "mit gedecktem Riss im Anulus fibrosus. Geringgradige Foramenstenose. "
    "LWK 4/5: Geringgradige reizlose Chondrose. Flache Retrospondylose und Bandscheibenprotrusion links "
    "dorsolateral mit gedecktem Riss im Anulus fibrosus. Geringgradige Foramenstenose. "
    "Myelon/Cauda equina: Konus unauffällig in Höhe BWK 12. Unauffällige Cauda. "
    "Die MR-Myelografie zeigt keine auffällige Aussparung im Spinalkanal oder im Bereich der Wurzeltaschen. "
    "Rückenmuskulatur: Seitengleiche Muskulatur ohne wesentliche Atrophie oder Ödeme. "
    "ISG: Keine wesentlichen Auffälligkeiten."
)

DECAY_LAMBDA = 0.05

# ── Biomechanical Assessment (2026-06-28) — valid for 2-4 weeks ───────────────

BIOMECHANICAL_PROFILE_SUMMARY = (
    "Assessment date: 2026-06-28. Review due: 2026-07-19.\n\n"
    "PRIMARY TIGHTNESS / COMPRESSION AREAS:\n"
    "Upper glute stabilizers (gluteus medius, piriformis): constant deep muscular gripping just below "
    "the posterior iliac crest — the primary anchor compressing lower back and hip joints. "
    "Deep right hip flexors and outer TFL. Right posterior hip capsule (tight, restricting posterior femoral glide). "
    "Upper hamstring attachments at ischial tuberosity (right). "
    "Lumbar facet joints at lumbosacral junction (horizontal compression from chronic sitting).\n\n"
    "PRIMARY WEAKNESS / UNDER-ACTIVITY:\n"
    "Gluteus maximus (primary hip extension driver under-firing). "
    "Deep core stabilisers. Because these are under-firing, upper glutes and hip flexors grip "
    "to create artificial stability, producing compressed joints and snapping tendons.\n\n"
    "MOVEMENT PATTERN FINDINGS:\n"
    "1. Upper glute/hip crest tightness — bilateral but constant; direct downstream cause of lumbar compression.\n"
    "2. Standing hinge crack (SL-RDL position) — deep posterior hip/ischial tuberosity; bilateral; "
    "joint gas or hamstring tendon shift over sit bone; builds over days, releases every few days.\n"
    "3. Mid-back thoracic crack — isolated thoracic vertebral release in seated forward flexion; "
    "compensation for lumbar stiffness.\n"
    "4. Lower back horizontal click — lumbosacral junction; lumbar facet joint horizontal slide under "
    "chronic sitting compression.\n"
    "5. Right hip snapping (Coxa Saltans) — RIGHT SIDE ONLY; repeatable on command at 90-degree "
    "active external rotation; iliopsoas tendon snapping over pelvic/femoral head; painless; "
    "confirms right-side iliopsoas dominance and hip capsule restriction."
)

BIOMECHANICAL_TIGHT_AREAS = [
    "glute_medius_bilateral",
    "piriformis_bilateral",
    "right_iliopsoas",
    "right_TFL",
    "right_posterior_hip_capsule",
    "bilateral_upper_hamstring_attachment",
    "lumbosacral_facet_joints",
    "thoracic_spine_mid"
]

BIOMECHANICAL_WEAK_AREAS = [
    "gluteus_maximus_bilateral",
    "deep_core_stabilisers"
]

BIOMECHANICAL_MOVEMENT_PATTERNS = [
    {
        "finding": "upper_glute_hip_crest_tightness",
        "location": "posterior_iliac_crest_shelf",
        "side": "bilateral",
        "mechanism": "overactive_glute_medius_piriformis_artificial_pelvic_stability",
        "frequency": "constant"
    },
    {
        "finding": "standing_hinge_crack",
        "location": "ischial_tuberosity_posterior_hip",
        "side": "bilateral",
        "mechanism": "posterior_hip_capsule_restriction_or_hamstring_tendon_shift",
        "frequency": "every_few_days"
    },
    {
        "finding": "thoracic_crack_seated_flexion",
        "location": "mid_thoracic_spine",
        "side": "central",
        "mechanism": "vertebral_facet_decompression_compensation_for_lumbar_stiffness",
        "frequency": "daily"
    },
    {
        "finding": "lumbosacral_horizontal_click",
        "location": "lumbosacral_junction",
        "side": "central",
        "mechanism": "lumbar_facet_horizontal_slide_chronic_sitting_compression",
        "frequency": "daily"
    },
    {
        "finding": "coxa_saltans_snapping_hip",
        "location": "right_hip_groin",
        "side": "right_only",
        "mechanism": "iliopsoas_tendon_snapping_over_pelvic_femoral_head_at_90deg_external_rotation",
        "frequency": "every_repetition_painless"
    }
]

BIOMECHANICAL_REVIEW_DATE = "2026-07-19"


def _get_columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _get_tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _migrate(conn):
    """Add columns introduced in Bucket 3 to existing tables without data loss."""
    tables = _get_tables(conn)

    # daily_readiness — Bucket 3 columns
    if "daily_readiness" in tables:
        cols = _get_columns(conn, "daily_readiness")
        bucket3_cols = {
            "tightness_score":      "INTEGER",
            "anatomical_locations": "TEXT",
            "sensation_tags":       "TEXT",
            "alcohol_units":        "REAL DEFAULT 0",
            "travel_flag":          "INTEGER DEFAULT 0",
            "psych_stress_score":   "INTEGER",
        }
        for col, coltype in bucket3_cols.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE daily_readiness ADD COLUMN {col} {coltype}")
                print(f"[migrate] daily_readiness.{col} added.")

    # training_log — add session_id FK to training_sessions
    if "training_log" in tables:
        cols = _get_columns(conn, "training_log")
        if "session_id" not in cols:
            conn.execute("ALTER TABLE training_log ADD COLUMN session_id INTEGER")
            print("[migrate] training_log.session_id added.")

    # training_set_log — Bucket 3 velocity & TUT columns
    if "training_set_log" in tables:
        cols = _get_columns(conn, "training_set_log")
        bucket3_cols = {
            "time_under_tension_seconds": "INTEGER",
            "movement_velocity":          "TEXT",
        }
        for col, coltype in bucket3_cols.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE training_set_log ADD COLUMN {col} {coltype}")
                print(f"[migrate] training_set_log.{col} added.")

    # daily_readiness — Bucket 5 AI output columns
    if "daily_readiness" in tables:
        cols = _get_columns(conn, "daily_readiness")
        bucket5_cols = {
            "ai_tightness_severity": "REAL",
            "ai_body_parts":         "TEXT",
            "ai_sensation_type":     "TEXT",
            "ai_warning_level":      "TEXT",
            "ai_parsed":             "INTEGER DEFAULT 0",
        }
        for col, coltype in bucket5_cols.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE daily_readiness ADD COLUMN {col} {coltype}")
                print(f"[migrate] daily_readiness.{col} added.")

    # session_notes — Bucket 5: warning_level column
    if "session_notes" in tables:
        cols = _get_columns(conn, "session_notes")
        if "warning_level" not in cols:
            conn.execute("ALTER TABLE session_notes ADD COLUMN warning_level TEXT")
            print("[migrate] session_notes.warning_level added.")

    # biomechanical_assessment — new table; CREATE IF NOT EXISTS in schema handles it,
    # but we also seed if the table is empty after schema execution.
    if "biomechanical_assessment" in _get_tables(conn):
        count = conn.execute("SELECT COUNT(*) FROM biomechanical_assessment").fetchone()[0]
        if count == 0:
            _seed_biomechanical_profile(conn)
            print("[migrate] biomechanical_assessment seeded (table existed but was empty).")


def init_db():
    is_fresh = not os.path.exists(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    _migrate(conn)

    if is_fresh:
        _seed_diagnostic_profile(conn)
        _seed_biomechanical_profile(conn)
        _seed_user_config(conn)

    conn.commit()
    conn.close()

    status = "created and seeded" if is_fresh else "schema verified, migrations applied"
    print(f"[init_db] {DB_PATH}: {status}.")


def _seed_user_config(conn):
    conn.execute(
        "INSERT OR IGNORE INTO user_config (key, value) VALUES ('current_stage', '1')"
    )
    print("[init_db] user_config seeded: current_stage = 1.")


def _seed_biomechanical_profile(conn):
    conn.execute(
        """
        INSERT INTO biomechanical_assessment
            (assessment_date, profile_summary, tight_areas_json, weak_areas_json,
             movement_patterns_json, review_date, is_current)
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (
            "2026-06-28",
            BIOMECHANICAL_PROFILE_SUMMARY,
            json.dumps(BIOMECHANICAL_TIGHT_AREAS),
            json.dumps(BIOMECHANICAL_WEAK_AREAS),
            json.dumps(BIOMECHANICAL_MOVEMENT_PATTERNS),
            BIOMECHANICAL_REVIEW_DATE,
        ),
    )
    print("[init_db] Biomechanical assessment seeded (2026-06-28, review due 2026-07-19).")


def _seed_diagnostic_profile(conn):
    conn.execute(
        """
        INSERT INTO diagnostic_profile
            (injury_focus, mri_raw_text, historical_compensations, injury_weight_decay_lambda)
        VALUES (?, ?, ?, ?)
        """,
        (INJURY_FOCUS, MRI_RAW_TEXT, HISTORICAL_COMPENSATIONS, DECAY_LAMBDA),
    )
    print("[init_db] Diagnostic baseline seeded from MRI report (10.11.2025).")


if __name__ == "__main__":
    init_db()
