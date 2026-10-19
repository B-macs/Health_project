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

## 2026-10-19 — Phase 0 measured, three faults fixed, at the gate
- Garmin from Cloud Run: one login and one read with the owner's OK, tokens storable — the move's largest risk, passed.
- Cost: the owner asked why Lauscher is free and this is not quite. Answer: Lauscher's code runs inside the Worker, and Cloudflare charges no egress; the engine needs a container, and two of Google's free amounts (egress, Cloud Storage) are US-only, so Belgium costs about $0.01 a month. Measured on the way: the engine copies 9.24 MB from Supabase at every cold start, uncompressed, which at ~22 starts a day passes Supabase's free 5 GB of egress. With the owner's OK every Data API request asks for gzip (1.36 MB).
- Owner's choices: one sync a day at the first morning open, retried at a later open (at most hourly) while last night is missing; transform the whole app first; no fix to the live Streamlit app; the cost does not decide the switch.
- His live app showed no data all morning. Read-only checks found the data synced at 11:37 and the cause in the live app's design: the sync runs only when Home loads to its end, a sync that finds nothing waits 2 hours, and Home keeps its reads 30 minutes without re-reading after a sync. Recorded for the new app; the live app is left as it is.
- Faults found by timing cold starts, all fixed: Google refused the first request after the engine slept ("no available instance") — the Worker retries a non-JSON 429/5xx (1, 2, 4, 8 s) and the engine answers JSON for every error; Supabase refused a request with "JWT issued at future" during a start (revision 3 never started) — that error is retried; the copy took 4–6 s — four tables at a time (1.5 s from the PC, 1.9 s at the next start). The timing script itself had to learn Cloudflare's 403 for Python's default User-Agent and this PC's expired Let's Encrypt cross-signature.
- Two timed cold starts through the Worker on revision 4: 9.13 s and 11.02 s, both answered.

## 2026-10-19 — Phase 1 built: Voice Training is its own app
- The owner started Phase 1's part before the build: the voice app on Streamlit Community Cloud from its own repo. It failed with "could not reach the database": its own Supabase project had paused, and a paused project's address stops resolving (Supabase's NXDOMAIN note). He restored it, and trimmed the app's secrets to `[voxplot_supabase]` after first pasting all of the health app's.
- Removed from the health app: the Voice Training tab (three remain), the `sync` route and `views/sync.py`, the `voice_training/voxplot` submodule, the four voice-only libraries. An unknown page now lands on Home. Comments that still named `views/sync.py` as a caller now name the real callers.
- A mistake, recorded: `git rm` of the submodule failed because the checkout kept its own (hidden) git folder, and the clean-up then deleted the superproject's second, stale copy of the voice repo's git data in `.git/modules` before it had been checked on its own. Nothing was lost: the owner's voice repo (`AIProject/Voxplot`) matches GitHub, and the checkout itself had nothing unpushed. Lesson: check every copy before deleting, and list hidden files (`Get-ChildItem -Force`).
- Tests: no test retired; two parametrised cases ended with `views/sync.py` (the manual-sync lock and the no-Stage-1 scans run per page file); nine added. Floor 4963 → 4970. The owner then stopped the timing (*"the cold start timing doesnt matter"*); the 10 s median target is recorded as waived in his words. The image is now precompiled (revision 5), and revision 6 removes the probes.
