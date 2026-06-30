# focus.md — Live Context Stub

*Update this file whenever the active stage or next action changes.*

---

## Current State (2026-06-30)

| Item | Value |
|------|-------|
| Stage | **Stage 1** — Rehab (load sensitivity monitoring) |
| Day | ~Day 14 of 14-day plan |
| Gate | 141/141 tests passing |
| Last commit | Phase 4 docs (CLAUDE.md, resume.md, playbook.md, progress.json, focus.md) |
| Next action | **Day 14 physiotherapist assessment** → determines Stage 2 entry |

---

## Stage 1 Exit Criteria (from `rules.STAGE_CONSTRAINTS[1]`)

- 14 consecutive pain-free training days
- Average tightness score ≤ 3.0 over the last 7 days
- Physiotherapist sign-off (manual, external — not automated)

---

## What Happens at Stage 2 Entry

1. Update `patient_profile.py` with post-assessment findings (new tightness areas, cleared areas)
2. Build Stage 2 training plan in `training_plan.py` (higher RPE / volume / bilateral loading)
3. Run `python tests.py` — still must be 141/141 (or higher with new Stage 2 tests)
4. Update biomechanical review date in `legacy/init_db.py` (`BIOMECHANICAL_REVIEW_DATE`)
5. Update this file: Stage → 2, next action → Day 28 assessment

---

## Open Questions Before Stage 2

- [ ] Apple Health sync (replace Google Sheets intermediary)?
- [ ] Add anterior knee cues to Stage 2 exercises? (right TFL offload)
- [ ] Will `coxa saltans` (right snapping hip) resolve or persist into Stage 2 loading?
