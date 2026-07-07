# CLAUDE.md — Health Engine

*Last updated: 2026-07-07 after the services/ extraction (framework-agnostic backend + logic layer, zero Streamlit imports).*

---

## Required Reading (in order)

Before writing any new code, read these files in this sequence:

1. **`docs/resume.md`** — architecture decisions, data model, stage machine, design philosophy, keyword library, rules for future development. All locked decisions live here.
2. **`patient_profile.py`** — MRI findings, biomechanical assessment (2026-06-28), muscle imbalances, pre-session release protocol, stage exit criteria. Updated before each new training block.
3. **`services/rules.py`** — `STAGE_CONSTRAINTS` (ACWR ceilings, RPE caps, volume caps per stage). `MOVEMENT_RULES` (contraindicated / caution / cleared). Single source of truth for safety guardrails.
4. **`services/engine.py`** — deterministic math: strain, ACWR, traffic light, injury weight decay, volume recommendation. Derives ceilings from `services.rules.STAGE_CONSTRAINTS`. No I/O, no Streamlit, no buried clock reads (`today` is always an explicit param).

---

## Deterministic Gate

Run after every change before committing:

```
python -m pytest tests/
```

Expected: **192/192 passed**

- Never delete or weaken a test to make the gate pass.
- Never weaken a `services/rules.py` guardrail.
- If you add new engine/stats/rules logic, add a corresponding test.
- `tests/test_no_streamlit_in_services.py` enforces that `services/` never imports `streamlit` — don't weaken it either.

---

## Definition of Done

A change is complete when:

1. `python -m pytest tests/` → 192/192 (or higher if new tests were added)
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

repo.py — Streamlit-layer bootstrap: builds a services.config.Config from
  st.secrets and hands back a cached services.repository.Repository
  (@st.cache_resource). This is the ONLY place st.secrets is read.

services/ — framework-agnostic backend + business logic. ZERO Streamlit
  imports anywhere (enforced by tests/test_no_streamlit_in_services.py).
  Pure logic:      engine.py · readiness.py · stats.py · rules.py · ai.py ·
                    plan.py · sessions.py · dashboard.py · insights.py
  Typed models:     models.py (Phase, SessionRecord, ExerciseEntry, DayCell,
                    CheckInRecord, BiometricRecord — dataclasses)
  I/O clients:      clients/notion.py, clients/sheets.py (generic primitives
                    only, no column/property names)
  Data access:      repository.py — the ONLY place Notion property names /
                    Sheet column names live; ~40 methods, wraps clients/
  Config:           config.py — Config dataclass + load_config(overrides),
                    env-var-first. Never reads st.secrets directly.

  Streamlit pages are thin presentation shells: they call
  repo.get_repository().*() and services.*, and own all @st.cache_data
  wrapping (the service layer itself is cache-agnostic).

UI helpers:
  nav.py   — bottom nav bar + JS bridge (stNav() in parent window)
  styles.py — dual-theme CSS: Oura palette ≤768px / Whoop palette ≥769px

Reference data:
  training_plan.py      — PLAN dict (14 exercise days, exercise objects)
  training_constants.py — EXERCISES catalogue, ANATOMICAL_LOCATIONS, SENSATION_TAGS
  patient_profile.py    — clinical data (not imported by active code — human reference)

tests/       — pytest suite (192 tests), the sole deterministic gate
_pages/      — removed; SPA router handles all routing; Streamlit 1.36+ auto-detects this dir
scripts/     — one-shot CLI tools (init_notion.py)
legacy/      — SQLite era, not used at runtime (init_db.py, schema.sql)
docs/        — INVENTORY.md, resume.md, training/*.md, playbook.md, focus.md,
               REFACTOR_NOTES.md (services/ extraction: smells found, not fixed)
```

---

## Key Rules (non-negotiable)

1. **Deterministic before AI** — implement the rule-based version first; AI layer is only added on top once the deterministic version is tested and working.
2. **AI never controls safety** — traffic light multiplier, ACWR ceiling, stage transitions, and final prescribed volume are always deterministic. AI output is advisory only.
3. **`services.rules.STAGE_CONSTRAINTS` is the single source of truth** for per-stage ACWR ceilings, RPE ceilings, and volume caps. `services/engine.py` derives from it; do not duplicate values.
4. **Notion is the write backend; Google Sheets is the biometric read source.** Do not add manual biometric entry anywhere.
5. **Training sessions are logged automatically by Training Plan.** No manual entry page.
6. **Pre-session release protocol precedes every training session.** Inhibit overactive structures (glute medius, piriformis) before activating underactive ones (glute max, deep core). Preserve this order in all new training blocks.
7. **Right-side asymmetry is a clinical finding.** All exercises involving right hip flexion >60° require a neutral/internal rotation cue. Right posterior hip capsule mobilisation is unilateral (right only).
8. **`patient_profile.py` is updated before each new training block**, after the Day 14 assessment updates findings, imbalances, and stage exit criteria.
9. **Secrets stay in `.streamlit/secrets.toml`** (gitignored). Never commit API keys or service account credentials. `services/` must never read `st.secrets` directly — only `repo.py` adapts it into a `Config` at startup.
10. **`services/` has zero Streamlit imports.** All backend I/O (Notion, Google Sheets) and business/plan logic lives there so it can be reused by a future non-Streamlit frontend. Streamlit pages (`app.py`, `views/*.py`) are thin presentation shells that call `repo.get_repository()` and `services.*`.

---

## Known Open Issues

| Issue | Status |
|-------|--------|
| `Training plan/` folder at root | Stale duplicate of `docs/training/` — delete manually (`Remove-Item -Recurse "Training plan"`) |
| Stage 2 training plan | Not yet built — begins after Day 14 physiotherapist sign-off |
| Apple Health direct sync | Pending — would replace Google Sheets intermediary |
| Biomechanical review due | 2026-07-19 — update `patient_profile.py` and `init_db.py` seed before Stage 2 |
| `patient_profile.py` not imported | Informational reference only — not wired into active code |
| See `docs/REFACTOR_NOTES.md` | Smells/bugs found during the services/ extraction, noted but not fixed beyond what the extraction itself required |
