# Rebuild archive (full history, newest last)

## 2026-10-07 — the decision and the prompt set
- The owner chose to leave Streamlit and build a Home-Screen phone app on Cloudflare, like Lauscher, with a better UI, and to separate Voice Training from the health app (health first, voice later).
- Engine hosting, compared: Google Cloud Run free tier (chosen: free, engine unchanged), a Cloudflare Container ($5–8 a month, the fallback), Python Workers (no threads; the Garmin, Sheets and Oura libraries need requests and curl_cffi), a TypeScript rewrite (no maintained Garmin library; 4,226 tests to port), GitHub Actions jobs (buttons wait 1–2 minutes; public logs; late or stopped schedules). The owner asked for a free option "like Lauscher" and picked Cloud Run.
- The prompt set (Stack verification + Phases 0–10) is in Notion under Health Project: "Health App — Cloudflare phone app (prompt set)".

## 2026-10-07 — Phase 0 started
- Plan approved by the owner, with one change from the Notion prompt: the Google Cloud CLI was missing, so the owner installs it while the local work runs, and one STOP 1 collects every owner task.
- M1 measured: the engine suite on Python 3.12.9 without Streamlit, 3895 passed, 1 skipped, 0 failed (11 Streamlit test files excluded).

## 2026-10-07 — Phase 0 local work done, STOP 1
- M2 and M3 built and tested locally (commit 06f1cdb). The image's file set (only the allow-listed files, copied to a scratch folder) imports healthapi and every services/ module.
- The first `pnpm install` added minimum-release-age exceptions for three packages released days earlier. They were removed, and the Worker pins Lauscher's proven wrangler 4.147.0 and test plugin 1.3.6.
- Hono's bearerAuth answers a header in another scheme ("Basic ...") with 400, not 401; the Worker test records that.
- The placeholder page was checked at phone width in the browser pane: title, line, version line with the commit; no console errors.
- Main gate: 4276 passed, 1 skipped.

## 2026-10-16 — Phase 0 re-checked after the app changed
- The owner asked whether Phase 0 must be done again after his updates (84 commits since 2026-10-07: Supabase the only store, the twenty work packages, the 12-week block). No: Phase 0 was paused at STOP 1 and nothing was deployed. The local half was re-checked against the new code.
- Broken: the engine image's allow-list. services/ had started importing `goal_block`, the Dockerfile, .gcloudignore and .dockerignore did not admit it, and a scratch copy of the allowed files failed to import 12 services/ modules. Fixed, and `tests/api/test_image_file_set.py` (5 tests, static) now checks the list against the code both ways.
- Stale: `tests/test_core_hold_score.py` gained one test that renders a Streamlit screen; the Streamlit list can now name a single test (deselected in the engine run).
- Holding: the API, the gate, the Worker and the app tests; the startup path under Supabase record mode; the readiness rule of 2026-10-13, which lives in services/.
