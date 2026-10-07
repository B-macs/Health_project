# Rebuild state (rolling)

*The phone-app rebuild: see the "Phone app rebuild (from 2026-10-07)" section of CLAUDE.md. Update this file during every rebuild session.*

## Now
**Phase 0 — Foundation & engine proof on Cloud Run.** PROMPT 1, at **STOP 1**: waiting for the owner's Google Cloud and Cloudflare steps (2026-10-07).

## Done
- CLAUDE.md rebuild section added (word for word from the Notion Phase 0 page). Commit fa7afc1.
- docs/rebuild/ control files; scripts/rebuild_gate.py with 30 tests.
- M1: requirements-engine.txt; the suite passes in `.venv-engine` (Python 3.12.9): 3895 passed, 1 skipped, 0 failed, with the 11 Streamlit tests excluded (docs/rebuild/streamlit_bound_tests.md).
- M2: api/healthapi (GET /api/health, GET /api/readiness, X-Engine-Key, X-Local-Date, the probes off by default) with 20 tests; shared/openapi.json and app/src/generated/api.ts. Commit 06f1cdb.
- M3 files: Dockerfile (3.12-slim, OS tzdata, non-root), .gcloudignore and .dockerignore as allow-lists. The image's file set imports every services/ module. The upload list itself waits for gcloud.
- app/ placeholder (checked at phone width in the browser pane) and worker/ (10 workerd tests).
- Main gate: 4276 passed, 1 skipped (floor 4226 + 50).

## Next
- STOP 1 (owner): install the Google Cloud CLI and run `gcloud init`; billing with a EUR 1 budget alert; enable the five APIs; the two secrets; `npx wrangler login`; HEALTH_ACCESS_KEY in .env; the project ID and the time zone.
- Then: the upload list, M4 deploy (europe-west1), M7 Worker deploy and its three secrets, M5 cold starts, M6 Oura probe and (with the owner's OK) the Garmin probe, M8 cost, the go or no-go.

## Open items
- The Home card's choice between the 14-day and the 60-day window lives in app.py (and today.py). The Phase 0 /api/readiness endpoint repeats that choice; Phase 2 moves it into services/ and makes app.py call it.
- `services/clients/local_cache.py` writes `.sync_state.json` next to the repo root with no setting to move it; the container makes /app writable for its user. Phase 2 can add a setting if needed.
- Starlette 1.7 warns that its TestClient on httpx is deprecated (httpx2). A warning only; revisit in Phase 2.
