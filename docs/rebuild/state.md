# Rebuild state (rolling)

*The phone-app rebuild: see the "Phone app rebuild (from 2026-10-07)" section of CLAUDE.md. Update this file during every rebuild session.*

## Now
**Phase 0 — Foundation & engine proof on Cloud Run.** PROMPT 1 is running (started 2026-10-07).

## Done
- CLAUDE.md rebuild section added (word for word from the Notion Phase 0 page).
- docs/rebuild/ control files; scripts/rebuild_gate.py with tests.
- M1: requirements-engine.txt; the suite passes in `.venv-engine` (Python 3.12.9): 3895 passed, 1 skipped, 0 failed, with the 11 Streamlit tests excluded (docs/rebuild/streamlit_bound_tests.md).

## Next
- M2 API skeleton, M3 container files, the app and Worker skeletons (local, tested).
- STOP 1: the owner installs the Google Cloud CLI, turns on billing with a EUR 1 budget alert, creates the two secrets, runs `wrangler login`, and adds HEALTH_ACCESS_KEY to .env.
- M4 deploy, M7 Worker, M5 cold start, M6 Oura and Garmin probes, M8 cost, then the go or no-go.

## Open items
- The Home card's choice between the 14-day and the 60-day window lives in app.py (and today.py). The Phase 0 /api/readiness endpoint repeats that choice; Phase 2 moves it into services/ and makes app.py call it.
- `services/clients/local_cache.py` writes `.sync_state.json` next to the repo root with no setting to move it; the container makes /app writable for its user. Phase 2 can add a setting if needed.
