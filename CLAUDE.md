# CLAUDE.md — Health Engine

*Last updated: 2026-06-30 after Phase 1-4 codebase review and refiling.*

---

## Required Reading (in order)

Before writing any new code, read these files in this sequence:

1. **`docs/resume.md`** — architecture decisions, data model, stage machine, design philosophy, keyword library, rules for future development. All locked decisions live here.
2. **`patient_profile.py`** — MRI findings, biomechanical assessment (2026-06-28), muscle imbalances, pre-session release protocol, stage exit criteria. Updated before each new training block.
3. **`rules.py`** — `STAGE_CONSTRAINTS` (ACWR ceilings, RPE caps, volume caps per stage). `MOVEMENT_RULES` (contraindicated / caution / cleared). Single source of truth for safety guardrails.
4. **`engine.py`** — deterministic math: strain, ACWR, traffic light, injury weight decay, volume recommendation. Derives ceilings from `rules.STAGE_CONSTRAINTS`. No I/O.

---

## Deterministic Gate

Run after every change before committing:

```
python tests.py
```

Expected: **141/141 passed**

- Never delete or weaken a test to make the gate pass.
- Never weaken a `rules.py` guardrail.
- If you add new engine/stats/rules logic, add a corresponding test.

---

## Definition of Done

A change is complete when:

1. `python tests.py` → 141/141 (or higher if new tests were added)
2. All affected imports resolve without error: `python -c "import app"` (or the relevant module)
3. The change is committed with a descriptive message explaining the *why*
4. No behaviour was changed without explicit approval — filing moves files and fixes imports only

---

## Architecture in One Page

```
app.py (entry point — SPA router)
  │  reads st.session_state["_nav_page"]
  ├── "home"      → inline home dashboard
  ├── "checkin"   → views/checkin.py
  ├── "training"  → views/training.py
  ├── "insights"  → views/insights.py
  └── "sync"      → views/sync.py

Pure logic (no I/O, no Streamlit):
  engine.py · readiness.py · stats.py · rules.py · ai.py

Data layer:
  db.py          → Notion API (4 databases: Readiness, Training, Biometrics, Config)
  sync_sheets.py → Google Sheets read-only (HRV, RHR, sleep via gspread)

UI helpers:
  nav.py   — bottom nav bar + JS bridge (stNav() in parent window)
  styles.py — dual-theme CSS: Oura palette ≤768px / Whoop palette ≥769px

Reference data:
  training_plan.py      — PLAN dict (14 exercise days, exercise objects)
  training_constants.py — EXERCISES catalogue, ANATOMICAL_LOCATIONS, SENSATION_TAGS
  patient_profile.py    — clinical data (not imported by active code — human reference)

_pages/      — removed; SPA router handles all routing; Streamlit 1.36+ auto-detects this dir
scripts/     — one-shot CLI tools (init_notion.py)
legacy/      — SQLite era, not used at runtime (init_db.py, schema.sql)
docs/        — INVENTORY.md, resume.md, training/*.md, playbook.md, focus.md
```

---

## Key Rules (non-negotiable)

1. **Deterministic before AI** — implement the rule-based version first; AI layer is only added on top once the deterministic version is tested and working.
2. **AI never controls safety** — traffic light multiplier, ACWR ceiling, stage transitions, and final prescribed volume are always deterministic. AI output is advisory only.
3. **`rules.STAGE_CONSTRAINTS` is the single source of truth** for per-stage ACWR ceilings, RPE ceilings, and volume caps. `engine.py` derives from it; do not duplicate values.
4. **Notion is the write backend; Google Sheets is the biometric read source.** Do not add manual biometric entry anywhere.
5. **Training sessions are logged automatically by Training Plan.** No manual entry page.
6. **Pre-session release protocol precedes every training session.** Inhibit overactive structures (glute medius, piriformis) before activating underactive ones (glute max, deep core). Preserve this order in all new training blocks.
7. **Right-side asymmetry is a clinical finding.** All exercises involving right hip flexion >60° require a neutral/internal rotation cue. Right posterior hip capsule mobilisation is unilateral (right only).
8. **`patient_profile.py` is updated before each new training block**, after the Day 14 assessment updates findings, imbalances, and stage exit criteria.
9. **Secrets stay in `.streamlit/secrets.toml`** (gitignored). Never commit API keys or service account credentials.

---

## Known Open Issues

| Issue | Status |
|-------|--------|
| `Training plan/` folder at root | Stale duplicate of `docs/training/` — delete manually (`Remove-Item -Recurse "Training plan"`) |
| Stage 2 training plan | Not yet built — begins after Day 14 physiotherapist sign-off |
| Apple Health direct sync | Pending — would replace Google Sheets intermediary |
| Biomechanical review due | 2026-07-19 — update `patient_profile.py` and `init_db.py` seed before Stage 2 |
| `patient_profile.py` not imported | Informational reference only — not wired into active code |
