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

## 2026-10-19 — STOP 1 done; the engine and the Worker deployed
- The owner's steps, with help: the Google Cloud CLI from Google's installer (`winget` and `python` were not on his user PATH; he was given the Environment Variables fix and wants `python` to mean 3.12); the project ID `health_project` was refused (no `_` allowed), so the project is `health-project-512108`, made in the console; a business billing account and a €1 budget; the five services; the two secrets, the engine's keys trimmed to six; `wrangler login`; the access key in `.env`; time zone Europe/Berlin.
- Checked before the deploy, on the live pages: europe-west1 is Tier 1; the request-based free tier is 180,000 vCPU-s, 360,000 GiB-s and 2 million requests a month per billing account; start-up and shut-down time are billed; a mounted `latest` secret is fetched at every read, and `latest` is discouraged for environment variables — so both secrets are pinned to version 1.
- M4: deployed in 124 s. The engine has its own service account with no project role. Startup CPU boost came on by default. The engine refuses a missing or wrong key (401) and has no docs routes (404).
- M6 Oura: one read of yesterday's readiness from Cloud Run, 1 row, the token untouched.
- M7: the Worker deployed; ENGINE_URL set; the two keys wait for the owner.
- The owner's later plan: the engine may move to an HP EliteBook 1040 G4 behind a Cloudflare Tunnel in a few months; only ENGINE_URL would change.
