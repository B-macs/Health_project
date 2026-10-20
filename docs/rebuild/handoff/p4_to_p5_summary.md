# Phase 4 → Phase 5 handoff (2026-10-20)

**Done: the iPhone app shell.** Every p4 counter is 0 except the owner's iPhone checklist (6 items, not done yet: he was training on the Streamlit app). Signed off under his standing instruction; the checklist stays open in his batch.

**Address:** https://health.lauscher-worker.workers.dev (Worker version be3cb6b4; engine revision health-engine-00008-gk6, commit 5a9b5eb).

## What exists
- **Install:** the manifest (Health, standalone, #07090E), icons and iPhone splash screens from one logo; in the browser the first open shows the Add to Home Screen steps, then the access key (kept in the phone's database, never in an address).
- **The phone's database** (Dexie `health`, schema v1): `cache` (the last answer of every read), `outbox` (every write), `session` (the training session), `settings`, `debuglog`. Migration plan: add only; never drop the outbox or the session while they hold something; the cache can be cleared and rebuilt.
- **Cache first:** `useCached(db, path, day, ctx)` shows the saved answer at once, then the engine's; with the engine down the saved answer stays with the reason; `<Freshness>` says how old it is. A failing screen shows a message, never a blank app.
- **The outbox:** `enqueue()` mints a ULID; sent in order with each write's own day; waits 5 s → 15 min after a failure, nothing overtakes; a refusal is kept for Settings; a wrong key stops the queue; an item leaves only on a 2xx.
- **The service worker:** the shell precached; no /api route; a new version waits while a training session runs.
- **Shell:** hash routes (/, /checkin as a sheet over Today, /training, /insights, /settings); Settings shows the engine status, the saves waiting, the daily data check, the key, storage, appearance, an "act as if the engine is down" switch, the debug log and the version line (seven taps open Eruda).
- **Worker:** the daily data check at 04:15 UTC, kept in KV and shown in Settings; SYNC_ENABLED "false" closes the syncs and the Oura login at the edge until Phase 9. No trigger syncs: the owner's one sync a day at the first open.
- **Engine:** GET /api/data/check — the newest backup against the store, read only (it replaced the Notion-against-Supabase check: Notion is a frozen archive). Today: 0 rows missing against the 2026-10-19 backup.

## Phase 5 may rely on
Read with `useCached` and show `<Freshness>`; write only through `enqueue()`; mint ids on the phone; keep the session in the session store; every word in `strings.ts`; every colour and size from the tokens; extend `dev/mockApi.ts` with each endpoint a screen uses; types only from `app/src/generated/api.ts`.

## Open
- The owner's iPhone checklist (owner_checks.json p4).
- The daily check reads the newest backup, which the Streamlit app takes only when its Home page loads; a stale backup is reported.
- The image store: about 525 MiB for a day after revision 8; check it before the next engine deploy.
- Carried: the hosted-app check (P2-11), the Strength reference, the voice app's address, the voice secrets.
