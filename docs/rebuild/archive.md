# Rebuild archive (full history, newest last)

## 2026-10-07 — the decision and the prompt set
- The owner chose to leave Streamlit and build a Home-Screen phone app on Cloudflare, like Lauscher, with a better UI, and to separate Voice Training from the health app (health first, voice later).
- Engine hosting, compared: Google Cloud Run free tier (chosen: free, engine unchanged), a Cloudflare Container ($5–8 a month, the fallback), Python Workers (no threads; the Garmin, Sheets and Oura libraries need requests and curl_cffi), a TypeScript rewrite (no maintained Garmin library; 4,226 tests to port), GitHub Actions jobs (buttons wait 1–2 minutes; public logs; late or stopped schedules). The owner asked for a free option "like Lauscher" and picked Cloud Run.
- The prompt set (Stack verification + Phases 0–10) is in Notion under Health Project: "Health App — Cloudflare phone app (prompt set)".

## 2026-10-07 — Phase 0 started
- Plan approved by the owner, with one change from the Notion prompt: the Google Cloud CLI was missing, so the owner installs it while the local work runs, and one STOP 1 collects every owner task.
- M1 measured: the engine suite on Python 3.12.9 without Streamlit, 3895 passed, 1 skipped, 0 failed (11 Streamlit test files excluded).
