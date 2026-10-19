# Phase 0 → Phase 1 handoff (2026-10-19)

**Verdict: GO.** One target, the cold-start median (10 s), was waived by the owner: two timed starts through the Worker took 9.13 s and 11.02 s, both answered, and he stopped the timing (*"the cold start timing doesnt matter"*). All numbers are in `p0_proof.json`.

## What now exists
- **Engine** on Google Cloud Run (europe-west1, project `health-project-512108`): FastAPI over the unchanged `services/`, revision 6, scale to zero, one instance at most. Only the Worker's key opens it; every error is JSON.
- **Worker** `health` on Cloudflare (https://health.lauscher-worker.workers.dev): serves the placeholder app, checks the owner's access key, passes `/api` to the engine, and retries when Google refuses a request while the engine starts.
- **Measured:** Garmin and Oura both work from Google; projected use at most 37% of any free amount; about $0.01 a month for data sent out of Belgium; no personal file in the 84-file upload.
- **Three faults found by measuring and fixed:** Google's "no available instance" refusal on the first request after sleep; Supabase's "JWT issued at future" refusal; an uncompressed 9.24 MB copy at every start (now 1.36 MB, fetched four tables at a time).

## Decisions the next phases must keep
- One sync a day at the first morning open, retried at a later open (at most hourly) while last night is missing.
- The whole app is transformed first; parts are removed after.
- The live Streamlit app gets no more fixes. What was found about its sync is recorded in `state.md` so the new app does not repeat it.

## Open
- The owner's push, and his check that the live app still opens.
- The Notion Phase 2 and Phase 9 pages still describe Notion as the store.
- Lazy imports if the starts feel slow; Starlette's 404 shape; Supabase's 7-day pause (Phase 9).

## Phase 1 may rely on
The engine and the Worker stay as they are; Phase 1 (Voice Training as its own app) does not touch them. Only the Streamlit app syncs until Phase 9.
